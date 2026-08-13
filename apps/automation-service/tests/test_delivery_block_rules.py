"""发货拦截规则（禁止发货规则引擎）单元测试。"""

from unittest.mock import AsyncMock

import pytest

from app.services import ws_delivery_handler


class _FakeResult:
    def __init__(self, rows=None, row=None, scalar_value=None):
        self._rows = rows or []
        self._row = row
        self._scalar_value = scalar_value

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._row

    def scalar(self):
        return self._scalar_value


class _RuleDB:
    def __init__(self, rule_rows, order_count=0):
        self._rule_rows = rule_rows
        self._order_count = order_count

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM delivery_block_rule" in sql:
            return _FakeResult(rows=self._rule_rows)
        if "FROM xianyu_trade_order" in sql:
            return _FakeResult(scalar_value=self._order_count)
        raise AssertionError(f"unexpected SQL: {sql}")


@pytest.mark.asyncio
async def test_check_delivery_block_rules_blocks_when_buyer_has_order():
    db = _RuleDB(
        rule_rows=[{"rule_code": "buyer_has_order", "rule_name": "买家已有其他订单"}],
        order_count=1,
    )

    reason = await ws_delivery_handler._check_delivery_block_rules(
        db, tenant_id=1, account_id=1, buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001", order_id="ORDER-001",
    )

    assert reason == "买家已有其他订单，已拦截发货"


@pytest.mark.asyncio
async def test_check_delivery_block_rules_blocks_when_buyer_unconfirmed():
    db = _RuleDB(
        rule_rows=[{"rule_code": "buyer_unconfirmed", "rule_name": "买家存在未确认收货订单"}],
        order_count=1,
    )

    reason = await ws_delivery_handler._check_delivery_block_rules(
        db, tenant_id=1, account_id=1, buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001", order_id="ORDER-001",
    )

    assert reason == "买家存在未确认收货订单，已拦截发货"


@pytest.mark.asyncio
async def test_check_delivery_block_rules_returns_none_without_rules():
    db = _RuleDB(rule_rows=[])

    reason = await ws_delivery_handler._check_delivery_block_rules(
        db, tenant_id=1, account_id=1, buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001", order_id="ORDER-001",
    )

    assert reason is None


@pytest.mark.asyncio
async def test_check_delivery_block_rules_returns_none_when_no_matching_order():
    db = _RuleDB(
        rule_rows=[{"rule_code": "buyer_has_order", "rule_name": "买家已有其他订单"}],
        order_count=0,
    )

    reason = await ws_delivery_handler._check_delivery_block_rules(
        db, tenant_id=1, account_id=1, buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001", order_id="ORDER-001",
    )

    assert reason is None


@pytest.mark.asyncio
async def test_text_delivery_blocks_when_block_rule_hits(monkeypatch):
    class _NoCallDB:
        async def execute(self, statement, params=None):
            raise AssertionError("规则拦截时不应继续执行任何 SQL")

    send_delivery = AsyncMock(return_value=(True, False))
    safe_insert = AsyncMock()
    notify_failure = AsyncMock()

    monkeypatch.setattr(
        ws_delivery_handler,
        "_check_delivery_block_rules",
        AsyncMock(return_value="买家已有其他订单，已拦截发货"),
    )
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_delivery)
    monkeypatch.setattr(ws_delivery_handler, "_safe_insert_delivery_record", safe_insert)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_failure)

    await ws_delivery_handler._execute_text_delivery(
        db=_NoCallDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="sid-1",
        pnm_id="PNM-1",
        buyer_user_id="buyer-1@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1001",
        buy_quantity=1,
        rule={"id": 1, "delivery_timing": ws_delivery_handler.DELIVERY_TIMING_AFTER_PAYMENT},
        delivery_content="发货内容",
        trigger_source="payment",
    )

    send_delivery.assert_not_awaited()
    safe_insert.assert_awaited_once()
    assert safe_insert.await_args.kwargs["status"] == 3
    assert "已拦截发货" in safe_insert.await_args.kwargs["fail_reason"]
    notify_failure.assert_awaited_once()
