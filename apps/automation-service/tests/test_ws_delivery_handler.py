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
    # _send_delivery_message 返回 (success, is_transient) 元组，mock 需匹配签名
    send_delivery = AsyncMock(return_value=(True, False))
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
            # 交叉维度去重 SQL（移除 pnmId 条件后）：用 REPLACE 归一化匹配
            if "REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid'))" in sql:
                # sid 传入值为 "62965262020"（不带 @goofish），SQL 中 REPLACE 归一化
                assert params["sid"] == "62965262020"
                assert params["buyer_user_id"] == "4182068955155@goofish"
                assert params["xy_goods_id"] == "1060794911332"
                assert params["delivery_content"] == "same content"
                # 确认 pnm_id 不再参与去重 SQL（移除后不应出现在参数中）
                assert "pnm_id" not in params, "pnmId 不应参与去重判断"
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
async def test_has_existing_realtime_delivery_returns_true_when_local_order_already_shipped_by_order_id():
    """delivery_record 无记录但本地订单表 order_status=3（按 order_id 精确匹配）应视为已发货。"""

    class _OrderShippedDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            # delivery_record 按 order_id 查不到
            if "FROM delivery_record" in sql and "order_id = :order_id" in sql:
                return _FakeResult(row=None)
            # 交叉维度去重也查不到
            if "FROM delivery_record" in sql and "REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info" in sql:
                return _FakeResult(row=None)
            # 本地订单表 order_status=3 命中
            if "FROM xianyu_trade_order" in sql and "external_order_id = :external_order_id" in sql:
                assert params["external_order_id"] == "ORDER-001"
                return _FakeResult(row={"1": 1})
            raise AssertionError(f"unexpected SQL: {sql}")

    exists = await ws_delivery_handler._has_existing_realtime_delivery(
        db=_OrderShippedDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="62965262020",
        xy_goods_id="1060794911332",
        buyer_user_id="4182068955155@goofish",
        pnm_id="4182068955155.PNM",
        delivery_content="",
    )

    assert exists is True


@pytest.mark.asyncio
async def test_has_existing_realtime_delivery_returns_true_when_local_order_shipped_by_item_buyer_fallback():
    """order_id 为空时，按 商品+买家+近 1 小时 兜底匹配 order_status=3 也应视为已发货。"""

    class _OrderShippedByItemBuyerDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            # delivery_record 按 order_id 查询路径不会触发（order_id 为空跳过）
            if "FROM delivery_record" in sql and "order_id = :order_id" in sql:
                raise AssertionError("order_id 为空不应进入精确匹配路径")
            # 交叉维度去重查不到
            if "FROM delivery_record" in sql and "REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info" in sql:
                return _FakeResult(row=None)
            # 本地订单表 order_status=3 兜底匹配命中
            if "FROM xianyu_trade_order" in sql and "item_id = :item_id" in sql:
                assert params["item_id"] == "1060794911332"
                assert params["buyer_id"] == "4182068955155"  # 归一化后去掉了 @goofish
                return _FakeResult(row={"1": 1})
            raise AssertionError(f"unexpected SQL: {sql}")

    exists = await ws_delivery_handler._has_existing_realtime_delivery(
        db=_OrderShippedByItemBuyerDB(),
        tenant_id=1,
        account_id=1,
        order_id=None,
        s_id="62965262020",
        xy_goods_id="1060794911332",
        buyer_user_id="4182068955155@goofish",
        pnm_id="4182068955155.PNM",
        delivery_content="",
    )

    assert exists is True


@pytest.mark.asyncio
async def test_has_existing_realtime_delivery_returns_false_when_neither_record_nor_order_shipped():
    """delivery_record 无记录 + 本地订单表无 order_status=3 → 不视为已发货，允许触发。"""

    class _NoExistingDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "FROM delivery_record" in sql:
                return _FakeResult(row=None)
            if "FROM xianyu_trade_order" in sql:
                return _FakeResult(row=None)
            raise AssertionError(f"unexpected SQL: {sql}")

    exists = await ws_delivery_handler._has_existing_realtime_delivery(
        db=_NoExistingDB(),
        tenant_id=1,
        account_id=1,
        order_id=None,
        s_id="62965262020",
        xy_goods_id="1060794911332",
        buyer_user_id="4182068955155@goofish",
        pnm_id="4182068955155.PNM",
        delivery_content="",
    )

    assert exists is False


@pytest.mark.asyncio
async def test_resolve_order_id_for_confirm_returns_input_order_id_unchanged():
    """order_id 已存在时直接返回，不查数据库。"""
    result = await ws_delivery_handler._resolve_order_id_for_confirm(
        db=None,
        tenant_id=1,
        account_id=1,
        order_id="ORDER-EXISTING",
        xy_goods_id="1060794911332",
        buyer_user_id="4182068955155@goofish",
    )
    assert result == "ORDER-EXISTING"


@pytest.mark.asyncio
async def test_resolve_order_id_for_confirm_queries_local_order_table_when_order_id_missing():
    """order_id 为空时按 商品+买家 反查本地订单表 external_order_id。"""

    class _ResolveOrderDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "FROM xianyu_trade_order" in sql and "item_id = :item_id" in sql:
                assert params["item_id"] == "1060794911332"
                assert params["buyer_id"] == "4182068955155"
                return _FakeResult(row={"external_order_id": "REMOTE-ORDER-001"})
            raise AssertionError(f"unexpected SQL: {sql}")

    result = await ws_delivery_handler._resolve_order_id_for_confirm(
        db=_ResolveOrderDB(),
        tenant_id=1,
        account_id=1,
        order_id=None,
        xy_goods_id="1060794911332",
        buyer_user_id="4182068955155@goofish",
    )
    assert result == "REMOTE-ORDER-001"


@pytest.mark.asyncio
async def test_resolve_order_id_for_confirm_returns_none_when_missing_goods_or_buyer():
    """order_id 为空且 xy_goods_id 或 buyer_user_id 缺失时直接返回 None，不查库。"""

    async def _no_call_db(_stmt, _params=None):
        raise AssertionError("不应查询数据库")

    result = await ws_delivery_handler._resolve_order_id_for_confirm(
        db=_no_call_db,
        tenant_id=1,
        account_id=1,
        order_id=None,
        xy_goods_id="",
        buyer_user_id="4182068955155@goofish",
    )
    assert result is None


@pytest.mark.asyncio
async def test_process_delivery_skips_duplicate_same_order(monkeypatch):
    db = _RealtimeDeliveryDB()
    # _send_delivery_message 返回 (success, is_transient) 元组，mock 需匹配签名
    send_delivery = AsyncMock(return_value=(True, False))
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
    # _send_delivery_message 返回 (success, is_transient) 元组，mock 需匹配签名
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", AsyncMock(return_value=(True, False)))
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


def _reset_order_sync_throttle():
    """清理订单同步节流状态，确保测试之间相互独立。"""
    ws_delivery_handler._order_sync_last_run.clear()
    ws_delivery_handler._order_sync_tasks.clear()


@pytest.mark.asyncio
async def test_trigger_account_orders_sync_invokes_sync_sold_orders(monkeypatch):
    """收到付款消息触发的账号订单同步应调用 sync_sold_orders_for_account。"""
    _reset_order_sync_throttle()

    sync_mock = AsyncMock(return_value={
        "ok": True,
        "processed": 1,
        "inserted": 1,
        "updated": 0,
        "failed": 0,
        "message": "订单同步完成",
    })
    monkeypatch.setattr(
        "app.services.automation_runtime.sync_sold_orders_for_account",
        sync_mock,
    )

    ws_delivery_handler._trigger_account_orders_sync(tenant_id=1, account_id=42)

    # 等待后台任务执行完毕
    task = ws_delivery_handler._order_sync_tasks.get(42)
    assert task is not None
    await task

    sync_mock.assert_awaited_once()
    call_kwargs = sync_mock.await_args
    assert call_kwargs.args[1] == 1   # tenant_id
    assert call_kwargs.args[2] == 42  # account_id


@pytest.mark.asyncio
async def test_trigger_account_orders_sync_throttles_repeated_calls(monkeypatch):
    """同一账号节流窗口内的重复调用应被跳过，只触发一次实际同步。"""
    _reset_order_sync_throttle()

    sync_mock = AsyncMock(return_value={
        "ok": True, "processed": 0, "inserted": 0, "updated": 0, "failed": 0,
        "message": "",
    })
    monkeypatch.setattr(
        "app.services.automation_runtime.sync_sold_orders_for_account",
        sync_mock,
    )

    ws_delivery_handler._trigger_account_orders_sync(tenant_id=1, account_id=7)
    task1 = ws_delivery_handler._order_sync_tasks.get(7)
    assert task1 is not None

    # 节流窗口内再次调用，不应创建新任务
    ws_delivery_handler._trigger_account_orders_sync(tenant_id=1, account_id=7)
    task2 = ws_delivery_handler._order_sync_tasks.get(7)
    assert task2 is task1

    await task1
    sync_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_incoming_message_for_delivery_triggers_order_sync_on_payment(monkeypatch):
    """handle_incoming_message_for_delivery 收到付款消息时应触发账号订单同步。"""
    _reset_order_sync_throttle()

    trigger_spy = AsyncMock()
    captured: dict = {}

    def _capture(tenant_id, account_id):
        captured["tenant_id"] = tenant_id
        captured["account_id"] = account_id
        return None

    monkeypatch.setattr(ws_delivery_handler, "_trigger_account_orders_sync", _capture)
    monkeypatch.setattr(
        ws_delivery_handler,
        "_should_send_statement",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        ws_delivery_handler,
        "_process_delivery",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.notify_dispatcher.notify_new_order",
        AsyncMock(),
    )

    msg = {
        "contentType": 26,
        "sId": "62965262020",
        "reminderContent": "[我已付款，等待你发货]",
        "xyGoodsId": "1060794911332",
    }

    await ws_delivery_handler.handle_incoming_message_for_delivery(
        tenant_id=1,
        account_id=99,
        msg=msg,
    )

    assert captured == {"tenant_id": 1, "account_id": 99}
    trigger_spy.assert_not_awaited()  # _trigger_account_orders_sync 不是 async，不会被 await


@pytest.mark.asyncio
async def test_handle_incoming_message_for_delivery_does_not_trigger_sync_on_irrelevant_message(monkeypatch):
    """非付款/小刀成功消息不应触发账号订单同步。"""
    _reset_order_sync_throttle()

    captured: list = []

    def _capture(tenant_id, account_id):
        captured.append((tenant_id, account_id))

    monkeypatch.setattr(ws_delivery_handler, "_trigger_account_orders_sync", _capture)

    # 普通文本消息，既非付款也非小刀成功
    msg = {
        "contentType": 1,
        "sId": "62965262020",
        "msgContent": "你好",
    }

    await ws_delivery_handler.handle_incoming_message_for_delivery(
        tenant_id=1,
        account_id=99,
        msg=msg,
    )

    assert captured == []
