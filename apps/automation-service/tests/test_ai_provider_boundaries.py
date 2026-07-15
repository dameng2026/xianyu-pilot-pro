from __future__ import annotations

import httpx
import pytest

from app.services import ai_provider, automation_runtime, rag_service
from app.core.outbound_network import PinnedHttpsTarget


async def _configured_provider() -> dict:
    return {
        "base_url": "https://provider.example/v1",
        "api_key": "top-secret-key",
        "model": "safe-model",
        "enabled": True,
        "source": "test",
    }


@pytest.fixture(autouse=True)
def _pin_test_provider_without_network(monkeypatch: pytest.MonkeyPatch):
    async def pin_provider(url: str) -> PinnedHttpsTarget:
        return PinnedHttpsTarget(
            request_url=url,
            host_header="provider.example",
            sni_hostname="provider.example",
            peer_ip="93.184.216.34",
        )

    monkeypatch.setattr(
        ai_provider.public_https_outbound_policy,
        "pin_public_https",
        pin_provider,
    )


@pytest.mark.asyncio
async def test_generate_text_rejects_provider_endpoint_before_sending_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def reject_private_endpoint(_url: str) -> str:
        raise ValueError("provider resolves to a private address")

    class ForbiddenClient:
        def __init__(self, **_kwargs):
            raise AssertionError("unsafe provider must be rejected before HTTP")

    monkeypatch.setattr(ai_provider, "_resolve_ai_config", _configured_provider)
    monkeypatch.setattr(
        ai_provider.public_https_outbound_policy,
        "pin_public_https",
        reject_private_endpoint,
    )
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", ForbiddenClient)

    result = await ai_provider.generate_text("test_scene", "system", "user")

    assert result["ok"] is False
    assert result["errorCode"] == "AI_PROVIDER_UNSAFE_ENDPOINT"
    assert "private address" not in str(result)


@pytest.mark.asyncio
async def test_generate_text_connects_to_pinned_provider_with_original_host_and_sni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient

    async def pin_provider(url: str) -> PinnedHttpsTarget:
        assert url == "https://provider.example/v1/chat/completions"
        return PinnedHttpsTarget(
            request_url="https://93.184.216.34/v1/chat/completions",
            host_header="provider.example",
            sni_hostname="provider.example",
            peer_ip="93.184.216.34",
        )

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "93.184.216.34"
        assert request.headers["Host"] == "provider.example"
        assert request.extensions["sni_hostname"] == "provider.example"
        assert request.headers["Authorization"] == "Bearer top-secret-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "safe response"}}]},
        )

    transport = httpx.MockTransport(respond)

    def client_factory(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_provider, "_resolve_ai_config", _configured_provider)
    monkeypatch.setattr(
        ai_provider.public_https_outbound_policy,
        "pin_public_https",
        pin_provider,
    )
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", client_factory)

    result = await ai_provider.generate_text("test_scene", "system", "user")

    assert result["ok"] is True
    assert result["content"] == "safe response"


@pytest.mark.asyncio
async def test_generate_text_rejects_oversized_input_before_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_provider, "_resolve_ai_config", _configured_provider)

    class ForbiddenClient:
        def __init__(self, **_kwargs):
            raise AssertionError("HTTP client must not be created for oversized input")

    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", ForbiddenClient)

    result = await ai_provider.generate_text(
        "test_scene",
        "system",
        "x" * (ai_provider._MAX_MESSAGE_CHARS + 1),
    )

    assert result["ok"] is False
    assert result["errorCode"] == "AI_INPUT_TOO_LARGE"


@pytest.mark.asyncio
async def test_generate_text_stops_streaming_when_response_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    oversized = b"x" * (ai_provider._MAX_PROVIDER_RESPONSE_BYTES + 1)
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=oversized))

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_provider, "_resolve_ai_config", _configured_provider)
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", client_factory)

    result = await ai_provider.generate_text("test_scene", "system", "user")

    assert result["ok"] is False
    assert result["errorCode"] == "AI_RESPONSE_TOO_LARGE"
    assert "x" * 100 not in result["error"]


@pytest.mark.asyncio
async def test_generate_text_never_returns_transport_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "dial failed for https://secret.internal/path?token=leaked-token",
            request=request,
        )

    transport = httpx.MockTransport(fail)

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_provider, "_resolve_ai_config", _configured_provider)
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", client_factory)

    result = await ai_provider.generate_text("test_scene", "system", "user")

    serialized = str(result)
    assert result["ok"] is False
    assert result["errorCode"] == "AI_PROVIDER_UNAVAILABLE"
    assert "secret.internal" not in serialized
    assert "leaked-token" not in serialized


@pytest.mark.asyncio
async def test_runtime_direct_provider_boundary_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"x" * 1025)
    )

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(automation_runtime.PublicRuntimeError) as exc_info:
        await automation_runtime._post_provider_json_bounded(
            "https://provider.example/v1/generate",
            payload={"prompt": "safe"},
            headers={"Authorization": "Bearer secret"},
            timeout_seconds=5,
            max_response_bytes=1024,
        )

    assert exc_info.value.error_code == "AI_PROVIDER_RESPONSE_TOO_LARGE"
    assert "secret" not in exc_info.value.public_message


@pytest.mark.asyncio
async def test_runtime_direct_provider_rejects_unsafe_endpoint_before_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def reject_endpoint(_url: str):
        raise ValueError("private provider endpoint")

    class ForbiddenClient:
        def __init__(self, **_kwargs):
            raise AssertionError("unsafe provider must be rejected before HTTP")

    monkeypatch.setattr(
        automation_runtime.public_https_outbound_policy,
        "pin_public_https",
        reject_endpoint,
    )
    monkeypatch.setattr(httpx, "AsyncClient", ForbiddenClient)

    with pytest.raises(automation_runtime.PublicRuntimeError) as exc_info:
        await automation_runtime._post_provider_json_bounded(
            "https://provider.example/v1/generate",
            payload={"prompt": "safe"},
            headers={"Authorization": "Bearer secret"},
            timeout_seconds=5,
            max_response_bytes=1024,
        )

    assert exc_info.value.error_code == "AI_PROVIDER_UNSAFE_ENDPOINT"
    assert "private provider" not in exc_info.value.public_message


@pytest.mark.asyncio
async def test_embedding_provider_rejects_unsafe_endpoint_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def configured():
        return {
            "base_url": "https://embedding.example/v1",
            "api_key": "embedding-secret",
            "model": "embedding-model",
        }

    async def reject(_url: str):
        raise ValueError("169.254.169.254?token=embedding-secret")

    class ForbiddenClient:
        def __init__(self, **_kwargs):
            raise AssertionError("unsafe embedding endpoint must fail before HTTP")

    monkeypatch.setattr(rag_service, "_load_embedding_config", configured)
    monkeypatch.setattr(
        rag_service.public_https_outbound_policy,
        "pin_public_https",
        reject,
    )
    monkeypatch.setattr(rag_service.httpx, "AsyncClient", ForbiddenClient)

    with pytest.raises(RuntimeError) as exc_info:
        await rag_service.generate_embedding("safe text")

    assert str(exc_info.value) == "Embedding service endpoint failed security validation"
    assert "169.254.169.254" not in str(exc_info.value)
    assert "embedding-secret" not in str(exc_info.value)
