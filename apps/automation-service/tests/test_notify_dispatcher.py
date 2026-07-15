from unittest.mock import AsyncMock

import pytest

from app.services import notify_dispatcher


def _clear_notify_dedup_state() -> None:
    for cache_name in ("_COOKIE_EXPIRED_NOTIFIED", "_NEW_ORDER_NOTIFIED"):
        cache = getattr(notify_dispatcher, cache_name, None)
        if isinstance(cache, dict):
            cache.clear()


@pytest.fixture(autouse=True)
def clear_notify_dedup_state():
    _clear_notify_dedup_state()
    yield
    _clear_notify_dedup_state()


@pytest.mark.asyncio
async def test_notify_new_order_deduplicates_replayed_same_order(monkeypatch):
    dispatch_notification = AsyncMock()
    monkeypatch.setattr(notify_dispatcher, "dispatch_notification", dispatch_notification)

    msg = {
        "reminderUrl": "fleamarket://message_chat?orderId=ORDER-001&itemId=1060794911332&sid=62965262020&messageId=abc",
        "reminderContent": "[我已付款，等待你发货]",
        "xyGoodsId": "1060794911332",
        "senderUserName": "测试买家",
    }

    await notify_dispatcher.notify_new_order(tenant_id=1, account_id=2, msg=msg)
    await notify_dispatcher.notify_new_order(tenant_id=1, account_id=2, msg=msg)

    dispatch_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_new_order_allows_different_orders(monkeypatch):
    dispatch_notification = AsyncMock()
    monkeypatch.setattr(notify_dispatcher, "dispatch_notification", dispatch_notification)

    first_msg = {
        "reminderUrl": "fleamarket://message_chat?orderId=ORDER-001&itemId=1060794911332&sid=62965262020&messageId=abc",
        "reminderContent": "[我已付款，等待你发货]",
        "xyGoodsId": "1060794911332",
        "senderUserName": "测试买家",
    }
    second_msg = {
        "reminderUrl": "fleamarket://message_chat?orderId=ORDER-002&itemId=1060794911332&sid=62965262020&messageId=def",
        "reminderContent": "[我已付款，等待你发货]",
        "xyGoodsId": "1060794911332",
        "senderUserName": "测试买家",
    }

    await notify_dispatcher.notify_new_order(tenant_id=1, account_id=2, msg=first_msg)
    await notify_dispatcher.notify_new_order(tenant_id=1, account_id=2, msg=second_msg)

    assert dispatch_notification.await_count == 2


@pytest.mark.asyncio
async def test_notify_new_order_releases_dedup_key_after_dispatch_failure(monkeypatch):
    dispatch_notification = AsyncMock(side_effect=[RuntimeError("network"), None])
    monkeypatch.setattr(notify_dispatcher, "dispatch_notification", dispatch_notification)

    msg = {
        "reminderUrl": "fleamarket://message_chat?orderId=ORDER-001&itemId=1060794911332&sid=62965262020&messageId=abc",
        "reminderContent": "[我已付款，等待你发货]",
        "xyGoodsId": "1060794911332",
        "senderUserName": "测试买家",
    }

    with pytest.raises(RuntimeError, match="network"):
        await notify_dispatcher.notify_new_order(tenant_id=1, account_id=2, msg=msg)

    await notify_dispatcher.notify_new_order(tenant_id=1, account_id=2, msg=msg)

    assert dispatch_notification.await_count == 2
