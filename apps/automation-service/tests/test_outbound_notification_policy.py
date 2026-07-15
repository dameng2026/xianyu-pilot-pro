import httpx
import pytest

from app.core.outbound_network import OutboundNetworkPolicy, PinnedHttpsTarget
from app.services import notify_dispatcher


async def public_resolver(_host, _port):
    return ["93.184.216.34"]


@pytest.mark.asyncio
async def test_generic_webhooks_require_operator_allowlist():
    policy = OutboundNetworkPolicy(resolver=public_resolver)

    with pytest.raises(ValueError):
        await policy.validate_webhook("webhook", "https://hooks.example/notify")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example/notify",
        "https://user:pass@hooks.example/notify",
        "https://hooks.example:8443/notify",
        "https://localhost/notify",
    ],
)
async def test_webhook_policy_rejects_unsafe_url_shapes(url):
    policy = OutboundNetworkPolicy("hooks.example", resolver=public_resolver)

    with pytest.raises(ValueError):
        await policy.validate_webhook("webhook", url)


@pytest.mark.asyncio
async def test_webhook_policy_rejects_private_or_metadata_dns_answers():
    async def private_resolver(host, _port):
        return ["169.254.169.254" if host.startswith("metadata") else "10.0.0.8"]

    policy = OutboundNetworkPolicy("hooks.example", resolver=private_resolver)

    with pytest.raises(ValueError):
        await policy.validate_webhook("webhook", "https://metadata.hooks.example/notify")
    with pytest.raises(ValueError):
        await policy.validate_webhook("webhook", "https://private.hooks.example/notify")


@pytest.mark.asyncio
async def test_provider_and_smtp_targets_are_bound_to_expected_hosts():
    policy = OutboundNetworkPolicy("", "smtp.example", resolver=public_resolver)

    assert await policy.validate_webhook(
        "feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/token"
    )
    with pytest.raises(ValueError):
        await policy.validate_webhook(
            "feishu", "https://attacker.example/open-apis/bot/v2/hook/token"
        )
    assert await policy.validate_smtp("smtp.example", 465) == ("smtp.example", 465)
    with pytest.raises(ValueError):
        await policy.validate_smtp("smtp.example", 25)


@pytest.mark.asyncio
async def test_public_https_target_is_pinned_to_the_validated_dns_answer():
    policy = OutboundNetworkPolicy(resolver=public_resolver)

    target = await policy.pin_public_https(
        "https://images.example/path/file.png?version=1"
    )

    assert target.request_url == "https://93.184.216.34/path/file.png?version=1"
    assert target.host_header == "images.example"
    assert target.sni_hostname == "images.example"
    assert target.peer_ip == "93.184.216.34"


@pytest.mark.asyncio
async def test_webhook_delivery_rejects_dns_rebinding_to_private_connected_peer(monkeypatch):
    real_client = httpx.AsyncClient

    class PrivatePeer:
        def get_extra_info(self, name):
            assert name == "server_addr"
            return ("169.254.169.254", 443)

    def rebound(request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["Host"] == "hooks.example"
        assert request.extensions["sni_hostname"] == "hooks.example"
        return httpx.Response(
            200,
            content=b'{"ok":true}',
            extensions={"network_stream": PrivatePeer()},
        )

    transport = httpx.MockTransport(rebound)

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    async def pin_public_dns(_channel_type, _raw_url):
        return PinnedHttpsTarget(
            request_url="https://93.184.216.34/notify",
            host_header="hooks.example",
            sni_hostname="hooks.example",
            peer_ip="93.184.216.34",
        )

    monkeypatch.setattr(notify_dispatcher.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(
        notify_dispatcher.notification_outbound_policy,
        "pin_webhook",
        pin_public_dns,
    )

    result = await notify_dispatcher._send_webhook(
        {"webhookUrl": "https://hooks.example/notify", "method": "POST"},
        "title",
        "body",
        5,
    )

    assert result["success"] is False
