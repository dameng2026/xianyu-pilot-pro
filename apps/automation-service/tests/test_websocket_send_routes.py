import hashlib

import pytest

from app.api.v1.routes import misc


class _DummyDb:
    async def rollback(self):
        return None

    async def commit(self):
        return None


class _MappingResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _DummyClient:
    is_connected = True
    unb = "2211422464341"

    async def send_image_message(self, cid, to_id, image_url, width=800, height=600):
        return {
            "code": 200,
            "uuid": "img-uuid",
            "cid": cid,
            "toId": to_id,
            "imageUrl": image_url,
            "width": width,
            "height": height,
        }


@pytest.mark.asyncio
async def test_websocket_start_uses_module_ws_manager_without_shadowing(monkeypatch):
    monkeypatch.setattr(misc, "_parse_account_id", lambda value: 1)
    monkeypatch.setattr(misc, "_account_belongs_to_tenant", _owned_account)
    monkeypatch.setattr(misc.ws_manager, "get_client", lambda account_id: None)

    async def _restart(*_args, **_kwargs):
        return object(), None

    async def _wait(*_args, **_kwargs):
        return "connected", {"hasSid": True, "phase": "connected", "lastError": ""}

    async def _precheck(*_args, **_kwargs):
        return True, None

    monkeypatch.setattr(misc, "_precheck_ws_token", _precheck)
    monkeypatch.setattr(misc, "_restart_ws_client_from_db", _restart)
    monkeypatch.setattr(misc, "_wait_ws_connect_result", _wait)

    result = await misc.websocket_start(
        data={"xianyuAccountId": 1},
        db=_DummyDb(),
        current_user={"tenant_id": 1},
    )

    assert result.code == 200
    assert result.data["connected"] is True
    assert result.data["status"] == "connected"
    assert result.data["hasSid"] is True


@pytest.mark.asyncio
async def test_websocket_send_image_message_uses_resolved_goods_id(monkeypatch):
    saved_messages = []
    broadcasts = []

    monkeypatch.setattr(misc, "_parse_account_id", lambda value: 1)
    monkeypatch.setattr(misc, "_account_belongs_to_tenant", _owned_account)
    monkeypatch.setattr(misc, "_restart_ws_client_from_db", _unexpected_async_call)
    monkeypatch.setattr(misc, "_wait_ws_connect_result", _unexpected_async_call)
    monkeypatch.setattr(misc, "_resolve_ws_sid", _resolved_sid)
    monkeypatch.setattr(misc, "_resolve_ws_peer_id", _resolved_peer_id)
    monkeypatch.setattr(misc, "_resolve_ws_goods_id", _resolved_goods_id)
    monkeypatch.setattr(misc, "save_chat_message", _capture_async(saved_messages))
    monkeypatch.setattr(misc.broadcaster, "broadcast", _capture_event_async(broadcasts))
    monkeypatch.setattr(misc.ws_manager, "get_client", lambda account_id: _DummyClient())

    result = await misc.websocket_send_image_message(
        data={
            "xianyuAccountId": 1,
            "cid": "63247704189",
            "peerUserId": "3672669710",
            "imageUrl": "https://example.com/demo.png",
        },
        db=_DummyDb(),
        current_user={"tenant_id": 1},
    )

    assert result.code == 200
    assert saved_messages
    assert saved_messages[0][0][3]["xyGoodsId"] == "goods-123"
    assert broadcasts == []


@pytest.mark.asyncio
async def test_websocket_send_image_message_accepts_local_upload_path(monkeypatch):
    sent_image_urls = []
    sent_sizes = []

    class _LocalPathClient(_DummyClient):
        async def send_image_message(self, cid, to_id, image_url, width=800, height=600):
            sent_image_urls.append(image_url)
            sent_sizes.append((width, height))
            return {
                "code": 200,
                "uuid": "img-uuid",
                "cid": cid,
                "toId": to_id,
                "imageUrl": image_url,
                "width": width,
                "height": height,
            }

    async def _resolve_local_upload_url(*_args, **_kwargs):
        return "https://cdn.goofish.com/uploaded/demo.png"

    monkeypatch.setattr(misc, "_parse_account_id", lambda value: 1)
    monkeypatch.setattr(misc, "_account_belongs_to_tenant", _owned_account)
    monkeypatch.setattr(misc, "_restart_ws_client_from_db", _unexpected_async_call)
    monkeypatch.setattr(misc, "_wait_ws_connect_result", _unexpected_async_call)
    monkeypatch.setattr(misc, "_resolve_ws_sid", _resolved_sid)
    monkeypatch.setattr(misc, "_resolve_ws_peer_id", _resolved_peer_id)
    monkeypatch.setattr(misc, "_resolve_ws_goods_id", _resolved_goods_id)
    monkeypatch.setattr(misc, "_resolve_outbound_image_url", _resolve_local_upload_url, raising=False)
    monkeypatch.setattr(misc, "_resolve_outbound_image_dimensions", lambda *_args, **_kwargs: (1280, 720))
    monkeypatch.setattr(misc, "save_chat_message", _capture_async([]))
    monkeypatch.setattr(misc.broadcaster, "broadcast", _capture_event_async([]))
    monkeypatch.setattr(misc.ws_manager, "get_client", lambda account_id: _LocalPathClient())

    result = await misc.websocket_send_image_message(
        data={
            "xianyuAccountId": 1,
            "cid": "63247704189",
            "peerUserId": "3672669710",
            "imageUrl": "/uploads/images/demo.png",
        },
        db=_DummyDb(),
        current_user={"tenant_id": 1},
    )

    assert result.code == 200
    assert sent_image_urls == ["https://cdn.goofish.com/uploaded/demo.png"]
    assert sent_sizes == [(1280, 720)]


@pytest.mark.asyncio
async def test_local_message_image_requires_active_matching_asset(monkeypatch):
    content = b"validated-image"

    class _AssetDb:
        async def execute(self, _statement, params):
            assert params == {
                "tenant_id": 7,
                "storage_key": "tenant-7/photo.png",
                "public_url": "/uploads/images/tenant-7/photo.png",
            }
            return _MappingResult({
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })

    monkeypatch.setattr(
        misc,
        "_read_uploaded_image_bytes",
        lambda image_url, tenant_id: content,
    )

    loaded = await misc._read_active_uploaded_image_bytes(
        _AssetDb(), "/uploads/images/tenant-7/photo.png", 7
    )

    assert loaded == content


@pytest.mark.asyncio
async def test_local_message_image_rejects_missing_or_tampered_asset(monkeypatch):
    class _MissingDb:
        async def execute(self, *_args, **_kwargs):
            return _MappingResult(None)

    with pytest.raises(ValueError, match="unavailable"):
        await misc._read_active_uploaded_image_bytes(
            _MissingDb(), "/uploads/images/tenant-7/photo.png", 7
        )

    content = b"tampered"

    class _TamperedDb:
        async def execute(self, *_args, **_kwargs):
            return _MappingResult({
                "size_bytes": len(content),
                "sha256": "0" * 64,
            })

    monkeypatch.setattr(
        misc,
        "_read_uploaded_image_bytes",
        lambda image_url, tenant_id: content,
    )
    with pytest.raises(ValueError, match="storage record"):
        await misc._read_active_uploaded_image_bytes(
            _TamperedDb(), "/uploads/images/tenant-7/photo.png", 7
        )


@pytest.mark.asyncio
async def test_websocket_routes_reject_cross_tenant_account_before_shared_client_access(monkeypatch):
    async def _not_owned(*_args, **_kwargs):
        return False

    def _must_not_get_client(_account_id):
        raise AssertionError("shared websocket client must not be read before tenant ownership check")

    monkeypatch.setattr(misc, "_account_belongs_to_tenant", _not_owned)
    monkeypatch.setattr(misc.ws_manager, "get_client", _must_not_get_client)

    result = await misc.websocket_status(
        data={"accountId": 99},
        db=_DummyDb(),
        current_user={"tenant_id": 7},
    )

    assert result.code == 404
    assert result.msg == "账号不存在"


@pytest.mark.asyncio
async def test_websocket_status_redacts_provider_error_body(monkeypatch):
    monkeypatch.setattr(misc, "_account_belongs_to_tenant", _owned_account)
    monkeypatch.setattr(misc.ws_manager, "get_client", lambda _account_id: _DummyClient())
    monkeypatch.setattr(
        misc.ws_manager,
        "get_status",
        lambda _account_id: {
            "phase": "token_failed",
            "hasSid": False,
            "lastError": "provider body Authorization=secret-token SQL syntax error",
        },
    )

    result = await misc.websocket_status(
        data={"accountId": 1},
        db=_DummyDb(),
        current_user={"tenant_id": 1},
    )

    assert result.code == 200
    assert result.data["status"] == "token_failed"
    assert "secret-token" not in result.data["lastError"]
    assert "SQL" not in result.data["lastError"]


@pytest.mark.asyncio
async def test_websocket_account_scope_includes_authenticated_user_or_shared_account():
    class _NoMatchResult:
        def scalar_one_or_none(self):
            return None

    class _CaptureQueryDb:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return _NoMatchResult()

    db = _CaptureQueryDb()
    owned = await misc._account_belongs_to_tenant(db, tenant_id=4, account_id=5, user_id=6)

    assert owned is False
    sql = str(db.statement)
    assert "xianyu_account.tenant_id" in sql
    assert "xianyu_account.user_id" in sql
    assert "IS NULL" in sql


async def _resolved_sid(*_args, **_kwargs):
    return "63247704189"


async def _resolved_peer_id(*_args, **_kwargs):
    return "3672669710"


async def _resolved_goods_id(*_args, **_kwargs):
    return "goods-123"


async def _owned_account(*_args, **_kwargs):
    return True


def _capture_async(bucket):
    async def _inner(*args, **kwargs):
        bucket.append((args, kwargs))
    return _inner


def _capture_event_async(bucket):
    async def _inner(tenant_id, event_name, payload):
        bucket.append((tenant_id, event_name, payload))
    return _inner


async def _unexpected_async_call(*_args, **_kwargs):
    raise AssertionError("unexpected async path")
