import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services import ws_startup


class _FakeResult:
    def __init__(self, scalar_value=None):
        self._scalar_value = scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value


class _FakeSession:
    def __init__(self, *, seller_external_uid="2211422464341"):
        self.seller_external_uid = seller_external_uid
        self.execute_calls = []
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement, params=None):
        self.execute_calls.append((str(statement), params or {}))
        return _FakeResult(self.seller_external_uid)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_on_message_callback_offloads_heavy_followups(monkeypatch):
    session = _FakeSession()
    saved_messages = []
    delivery_started = asyncio.Event()
    queue_started = asyncio.Event()

    def _session_factory():
        return session

    async def _fake_save_chat_message(db, tenant_id, account_id, msg, seller_external_uid="", is_auto_reply=0):
        saved_messages.append({
            "db": db,
            "tenant_id": tenant_id,
            "account_id": account_id,
            "msg": dict(msg),
            "seller_external_uid": seller_external_uid,
            "is_auto_reply": is_auto_reply,
        })
        await asyncio.sleep(0)
        return 1

    async def _slow_delivery(tenant_id, account_id, msg):
        delivery_started.set()
        await asyncio.sleep(0)

    async def _slow_queue(tenant_id, account_id, msg, seller_external_uid):
        queue_started.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(ws_startup, "async_session", _session_factory)
    monkeypatch.setattr(ws_startup, "save_chat_message", _fake_save_chat_message)
    monkeypatch.setattr(ws_startup, "_run_delivery_after_message_saved", _slow_delivery)
    monkeypatch.setattr(ws_startup, "_queue_ai_auto_reply_after_message_saved", _slow_queue)

    msg = {
        "sId": "63247704189",
        "pnmId": "4182068955155.PNM",
        "senderUserId": "4182068955155@goofish",
        "senderUserName": "测试买家",
        "msgContent": "买完什么时候发货呢？",
        "contentType": 1,
        "direction": "IN",
    }

    await asyncio.wait_for(ws_startup.on_message_callback(tenant_id=1, account_id=9, msg=msg), timeout=0.1)

    assert session.committed is True
    assert session.rolled_back is False
    assert saved_messages
    assert saved_messages[0]["seller_external_uid"] == "2211422464341"

    await asyncio.wait_for(delivery_started.wait(), timeout=0.1)
    await asyncio.wait_for(queue_started.wait(), timeout=0.1)


@pytest.mark.anyio
async def test_on_message_callback_skips_followups_for_duplicate_message(monkeypatch):
    session = _FakeSession()
    delivery = AsyncMock()
    queue = AsyncMock()

    def _session_factory():
        return session

    async def _fake_save_chat_message(db, tenant_id, account_id, msg, seller_external_uid="", is_auto_reply=0):
        return None

    monkeypatch.setattr(ws_startup, "async_session", _session_factory)
    monkeypatch.setattr(ws_startup, "save_chat_message", _fake_save_chat_message)
    monkeypatch.setattr(ws_startup, "_run_delivery_after_message_saved", delivery)
    monkeypatch.setattr(ws_startup, "_queue_ai_auto_reply_after_message_saved", queue)

    await ws_startup.on_message_callback(tenant_id=1, account_id=9, msg={
        "sId": "63247704189",
        "pnmId": "4182068955155.PNM",
        "senderUserId": "4182068955155@goofish",
        "senderUserName": "测试买家",
        "msgContent": "还在吗",
        "contentType": 1,
        "direction": "IN",
    })
    await asyncio.sleep(0.05)

    assert session.committed is True
    delivery.assert_not_awaited()
    queue.assert_not_awaited()


@pytest.mark.anyio
async def test_queue_ai_auto_reply_merges_consecutive_messages(monkeypatch):
    await ws_startup._reset_ai_auto_reply_batch_state()
    triggered = []

    async def _fake_run(tenant_id, account_id, msg, seller_external_uid):
        triggered.append({
            "tenant_id": tenant_id,
            "account_id": account_id,
            "msg": dict(msg),
            "seller_external_uid": seller_external_uid,
        })

    monkeypatch.setattr(ws_startup, "AI_AUTO_REPLY_DEBOUNCE_SECONDS", 0.01)
    monkeypatch.setattr(ws_startup, "_run_ai_auto_reply_after_message_saved", _fake_run)

    base_msg = {
        "sId": "63247704189",
        "senderUserId": "4182068955155@goofish",
        "senderUserName": "测试买家",
        "contentType": 1,
        "direction": "IN",
    }
    await ws_startup._queue_ai_auto_reply_after_message_saved(1, 9, {
        **base_msg,
        "pnmId": "pnm-1",
        "msgContent": "你好",
        "messageTime": 1000,
    }, "2211422464341")
    await ws_startup._queue_ai_auto_reply_after_message_saved(1, 9, {
        **base_msg,
        "pnmId": "pnm-2",
        "msgContent": "这个怎么用",
        "messageTime": 1001,
    }, "2211422464341")

    await asyncio.sleep(0.05)
    await ws_startup._reset_ai_auto_reply_batch_state()

    assert len(triggered) == 1
    assert triggered[0]["tenant_id"] == 1
    assert triggered[0]["account_id"] == 9
    assert triggered[0]["seller_external_uid"] == "2211422464341"
    assert triggered[0]["msg"]["msgContent"] == "你好\n这个怎么用"
    assert triggered[0]["msg"]["mergedMessageCount"] == 2
    assert triggered[0]["msg"]["pnmId"] == "pnm-2"


@pytest.mark.anyio
async def test_extract_auto_reply_role_hints_prefers_session_extensions():
    hints = ws_startup._extract_auto_reply_role_hints({
        "receiverUserId": "2211422464341",
        "rawPayload": {
            "sessionInfo": {
                "groupOwnerId": "1678242685",
                "extensions": {
                    "ownerUserId": "1678242685",
                    "itemSellerId": "1678242685",
                    "extUserId": "2211422464341",
                },
            }
        },
    })

    assert hints["receiverUserId"] == "2211422464341"
    assert hints["ownerUserId"] == "1678242685"
    assert hints["itemSellerId"] == "1678242685"
    assert hints["groupOwnerId"] == "1678242685"
    assert hints["extUserId"] == "2211422464341"


@pytest.mark.anyio
async def test_should_trigger_ai_auto_reply_allows_partial_buyer_text():
    should_trigger, content_type_int, sender_user_id, reminder_content = ws_startup._should_trigger_ai_auto_reply({
        "direction": "IN",
        "contentType": 1,
        "senderUserId": "",
        "msgContent": "买完什么时候发货呢？",
        "sId": "63247704189",
        "reminderContent": "",
    })

    assert should_trigger is True
    assert content_type_int == 1
    assert sender_user_id == ""
    assert reminder_content == ""


@pytest.mark.anyio
async def test_should_trigger_ai_auto_reply_skips_business_notification():
    should_trigger, content_type_int, sender_user_id, reminder_content = ws_startup._should_trigger_ai_auto_reply({
        "direction": "IN",
        "contentType": 26,
        "senderUserId": "",
        "msgContent": "",
        "sId": "63247704189",
        "reminderContent": "PIC_DEAL_ERROR",
    })

    assert should_trigger is False
    assert content_type_int == 26
    assert sender_user_id == ""
    assert reminder_content == "PIC_DEAL_ERROR"
