from unittest.mock import AsyncMock

import pytest

from app.services import ws_delivery_handler


class _FakeResult:
    def __init__(self, *, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None


class _RealtimeDeliveryDB:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.execute_calls.append((sql, params or {}))

        if "SELECT id, status FROM delivery_record" in sql:
            return _FakeResult(row=None)

        if "SELECT id" in sql and "FROM delivery_record" in sql:
            return _FakeResult(row=None)

        if "SELECT * FROM delivery_rule" in sql:
            return _FakeResult(rows=[])

        if "FROM xianyu_account" in sql:
            return _FakeResult(row={"status": 1})

        if "FROM xianyu_goods" in sql:
            return _FakeResult(row={
                "id": 170,
                "title": "WAVES独立降噪插件 PSE+NS1 自动发货",
                "external_goods_id": "1060794911332",
            })

        if "FROM delivery_goods_config" in sql:
            return _FakeResult(row={
                "id": 2,
                "goods_id": 170,
                "config_json": (
                    '{"payDelivery":{"enabled":1,"mode":"text","sourceId":1,'
                    '"content":"通过网盘分享的文件：\\n链接: https://pan.baidu.com/s/demo?pwd=a003"}}'
                ),
            })

        if "FROM delivery_text_source" in sql:
            return _FakeResult(row={
                "id": 1,
                "title": "waver 独立降噪插件",
                "content": "通过网盘分享的文件：\n链接: https://pan.baidu.com/s/demo?pwd=a003",
                "remark": "自动发货文本",
            })

        if "INSERT INTO delivery_record" in sql:
            return _FakeResult(row=None)

        raise AssertionError(f"unexpected SQL: {sql}")


def test_extract_order_id_from_url_does_not_treat_sid_as_order_id():
    order_id = ws_delivery_handler.extract_order_id_from_url(
        "fleamarket://message_chat?itemId=1060794911332&peerUserId=3672669710&sid=62965262020&messageId=abc"
    )

    assert order_id is None


def test_is_payment_message_rejects_waiting_payment_reminder():
    msg = {
        "contentType": 26,
        "reminderContent": "[我已拍下，待付款]",
    }

    assert ws_delivery_handler.is_payment_message(msg) is False


def test_is_payment_message_accepts_paid_waiting_shipment_reminder():
    msg = {
        "contentType": 26,
        "reminderContent": "[我已付款，等待你发货]",
    }

    assert ws_delivery_handler.is_payment_message(msg) is True


@pytest.mark.asyncio
async def test_process_delivery_uses_goods_level_text_source_when_payment_message_has_no_real_order_id(monkeypatch):
    db = _RealtimeDeliveryDB()
    send_delivery = AsyncMock(return_value=True)
    insert_record = AsyncMock()

    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_delivery)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_record)

    msg = {
        "contentType": 26,
        "sId": "62965262020",
        "pnmId": "4182068955155.PNM",
        "reminderUrl": "fleamarket://message_chat?itemId=1060794911332&peerUserId=3672669710&sid=62965262020&messageId=abc",
        "reminderContent": "[我已付款，等待你发货]",
        "xyGoodsId": "1060794911332",
        "senderUserId": "4182068955155@goofish",
        "senderUserName": "测试买家",
    }

    await ws_delivery_handler._process_delivery(
        db=db,
        tenant_id=1,
        account_id=1,
        msg=msg,
    )

    send_delivery.assert_awaited_once()
    send_args = send_delivery.await_args.args
    assert send_args[0] == 1
    assert send_args[1] == "62965262020"
    assert send_args[2] == "4182068955155@goofish"
    assert "https://pan.baidu.com/s/demo" in send_args[3]

    insert_record.assert_awaited_once()
    record_args = insert_record.await_args.args
    assert record_args[3] is None
    assert record_args[8] == "1060794911332"
    assert insert_record.await_args.kwargs["delivery_type"] == ws_delivery_handler.MODE_TEXT
    assert insert_record.await_args.kwargs["status"] == 2


@pytest.mark.asyncio
async def test_has_existing_realtime_delivery_matches_full_receiver_info_payload():
    class _ExistingDeliveryDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "AND order_id = :order_id" in sql:
                return _FakeResult(row=None)
            if "JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')) = :sid" in sql:
                assert params["sid"] == "62965262020@goofish"
                assert params["buyer_user_id"] == "4182068955155@goofish"
                assert params["xy_goods_id"] == "1060794911332"
                assert params["delivery_content"] == "same content"
                return _FakeResult(row={"id": 99})
            raise AssertionError(f"unexpected SQL: {sql}")

    exists = await ws_delivery_handler._has_existing_realtime_delivery(
        db=_ExistingDeliveryDB(),
        tenant_id=1,
        account_id=1,
        order_id=None,
        s_id="62965262020",
        xy_goods_id="1060794911332",
        buyer_user_id="4182068955155@goofish",
        pnm_id="4182068955155.PNM",
        delivery_content="same content",
    )

    assert exists is True


@pytest.mark.asyncio
async def test_process_delivery_skips_duplicate_same_order(monkeypatch):
    db = _RealtimeDeliveryDB()
    send_delivery = AsyncMock(return_value=True)
    insert_record = AsyncMock()

    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_delivery)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_record)
    monkeypatch.setattr(ws_delivery_handler, "_has_existing_realtime_delivery", AsyncMock(return_value=True))

    msg = {
        "contentType": 26,
        "sId": "62965262020",
        "pnmId": "4182068955155.PNM",
        "reminderUrl": "fleamarket://message_chat?orderId=ORDER-001&itemId=1060794911332&peerUserId=3672669710&sid=62965262020&messageId=abc",
        "reminderContent": "[鎴戝凡浠樻锛岀瓑寰呬綘鍙戣揣]",
        "xyGoodsId": "1060794911332",
        "senderUserId": "4182068955155@goofish",
        "senderUserName": "娴嬭瘯涔板",
    }

    await ws_delivery_handler._process_delivery(
        db=db,
        tenant_id=1,
        account_id=1,
        msg=msg,
    )

    send_delivery.assert_not_awaited()
    insert_record.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_text_delivery_updates_local_state_without_calling_xianyu_confirm(monkeypatch):
    class _UpdateOrderDB:
        def __init__(self):
            self.calls = []

        async def execute(self, statement, params=None):
            self.calls.append((str(statement), params or {}))
            return _FakeResult(row=None)

    db = _UpdateOrderDB()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", AsyncMock(return_value=True))
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", AsyncMock())
    auto_confirm = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", auto_confirm)

    await ws_delivery_handler._execute_text_delivery(
        db=db,
        tenant_id=1,
        account_id=1,
        order_id="ORDER-LOCAL-001",
        s_id="62965262020",
        pnm_id="4182068955155.PNM",
        buyer_user_id="4182068955155@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1060794911332",
        buy_quantity=1,
        rule={"id": 2, "auto_confirm_shipment": 1, "delivery_timing": ws_delivery_handler.DELIVERY_TIMING_AFTER_PAYMENT},
        delivery_content="发货内容",
        trigger_source="payment",
    )

    assert any("UPDATE xianyu_trade_order" in sql for sql, _ in db.calls)
    auto_confirm.assert_awaited_once()
