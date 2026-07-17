"""卡密发货（_execute_kami_delivery）全方位单元测试。

覆盖以下场景：
1. 卡密发货成功路径（认领→发送→标记已使用→刷新组统计→记录→确认发货→更新订单状态）
2. 卡密库存不足（claimed_count=0 → 插入失败记录，不发送消息）
3. 卡密认领成功但读取失败（claimed_count>0 但 SELECT 返回空 → 回滚卡密）
4. 发送失败回滚（认领后发送失败，回滚 status=0）
5. 确认发货失败（卡密已发送但闲鱼API失败，本地订单状态不变，不再向用户告警）
6. 多卡密批量认领（buy_quantity > 1，组装多张卡密内容并用 "---" 连接）
7. 模板替换正确（{kmKey} → card_value 优先，否则 card_key）
8. card_group_id 为 None 时不刷新组统计
9. order_id 为空时不调用确认发货
10. is_bargain=True 时调用免拼发货接口
11. 未配置 kami_delivery_template 时使用默认 '{kmKey}'
12. 发送消息抛异常：捕获后视为发送失败，回滚卡密

错误兜底专项测试（新增）：
13. 认领 SQL 异常：兜底插入失败记录，不向上抛出
14. 读取卡密 SQL 异常：兜底回滚卡密，插入失败记录
15. 卡密内容为空：兜底插入失败记录，不发送空消息
16. 发送消息返回临时性错误（is_transient=True）：fail_reason 提示"系统将自动重试"
17. 发送消息返回永久性错误（is_transient=False）：fail_reason 提示"请检查账号登录状态"
18. 确认发货失败不再触发用户告警（卡密已发送给买家，用户感知已发货）
19. _friendly_confirm_error 已知错误码映射为用户友好消息
20. _send_delivery_message 空内容返回 (False, False) 永久性错误

参考：apps/automation-service/app/services/ws_delivery_handler.py:1228 _execute_kami_delivery
"""
from unittest.mock import AsyncMock

import pytest

from app.services import ws_delivery_handler


# ============================================================
# 测试用 Fake DB / Fake Result 工具类
# ============================================================

class _FakeResult:
    """模拟 SQLAlchemy Result 对象。"""

    def __init__(self, *, rows=None, row=None, rowcount=0):
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None


class _KamiDeliveryDB:
    """模拟 AsyncSession，能根据 SQL 模式匹配返回不同结果。

    通过构造参数控制关键分支：
    - claimed_rowcount: UPDATE card_item ... SET status=1 影响行数
    - claimed_items: SELECT 已认领卡密项的返回行
    - is_bargain: SELECT is_bargain FROM xianyu_trade_order 的返回值
    - claim_exception: 若非 None，认领 SQL 抛出该异常（测试兜底）
    - read_exception: 若非 None，读取 SQL 抛出该异常（测试兜底）
    """

    def __init__(self, *, claimed_rowcount=1, claimed_items=None, is_bargain=0,
                 claim_exception=None, read_exception=None):
        self.claimed_rowcount = claimed_rowcount
        self.claimed_items = claimed_items or []
        self.is_bargain = is_bargain
        self.claim_exception = claim_exception
        self.read_exception = read_exception
        self.execute_calls = []  # [(sql, params), ...]

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.execute_calls.append((sql, params or {}))

        # Step 1: 原子认领卡密
        if "UPDATE card_item" in sql and "SET status = 1" in sql:
            if self.claim_exception is not None:
                raise self.claim_exception
            return _FakeResult(rowcount=self.claimed_rowcount)

        # Step 2: 读取已认领卡密
        if "SELECT id, card_key, card_value, extra_info" in sql and "FROM card_item" in sql:
            if self.read_exception is not None:
                raise self.read_exception
            return _FakeResult(rows=self.claimed_items)

        # Step 5: 标记已使用 / 回滚 status
        if "UPDATE card_item" in sql and ("SET status = 2" in sql or "SET status = 0" in sql):
            return _FakeResult(rowcount=1)

        # Step 6: 刷新卡密组统计
        if "UPDATE card_group g SET" in sql:
            return _FakeResult(rowcount=1)

        # _detect_bargain_from_message_or_db: SELECT is_bargain
        if "SELECT is_bargain FROM xianyu_trade_order" in sql:
            return _FakeResult(row={"is_bargain": self.is_bargain})

        # Step 8: 更新订单状态为已发货
        if "UPDATE xianyu_trade_order" in sql and "order_status = 3" in sql:
            return _FakeResult(rowcount=1)

        # 默认返回空结果
        return _FakeResult(row=None)


# ============================================================
# 公共测试参数
# ============================================================

def _common_kwargs(**overrides):
    """构造 _execute_kami_delivery 的标准参数。"""
    base = dict(
        db=None,  # 由各测试用例传入
        tenant_id=1,
        account_id=10,
        order_id="ORDER-KAMI-001",
        s_id="62965262020",
        pnm_id="4182068955155.PNM",
        buyer_user_id="4182068955155@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1060794911332",
        buy_quantity=1,
        rule={"id": 200, "kami_delivery_template": "您的卡密: {kmKey}"},
        card_group_id=300,
        trigger_source="payment",
    )
    base.update(overrides)
    return base


# ============================================================
# 测试用例
# ============================================================

@pytest.mark.asyncio
async def test_kami_delivery_success_path_marks_card_used_and_updates_order_status(monkeypatch):
    """1. 成功路径：认领→发送成功→标记 status=2→刷新组统计→记录→确认发货成功→更新 order_status=3。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "KEY-AAA", "card_value": "VAL-AAA", "extra_info": ""}],
        is_bargain=0,
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True, "ship_method": "consign"})
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 1. 发送了卡密消息，内容包含 card_value（优先于 card_key）
    send_mock.assert_awaited_once()
    assert send_mock.await_args.args[0] == 10  # account_id
    assert send_mock.await_args.args[1] == "62965262020"  # s_id
    assert send_mock.await_args.args[2] == "4182068955155@goofish"  # buyer_user_id
    assert "VAL-AAA" in send_mock.await_args.args[3]
    assert "您的卡密:" in send_mock.await_args.args[3]

    # 2. 标记卡密为 status=2（已使用）
    assert any(
        "UPDATE card_item" in sql and "SET status = 2" in sql
        for sql, _ in db.execute_calls
    ), "应执行 UPDATE card_item SET status=2 标记卡密为已使用"

    # 3. 刷新了卡密组统计
    assert any(
        "UPDATE card_group g SET" in sql and "total_count" in sql
        for sql, _ in db.execute_calls
    ), "应刷新 card_group 统计"

    # 4. 插入了成功的发货记录（status=2 表示成功）
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["delivery_type"] == ws_delivery_handler.MODE_KAMI
    assert insert_mock.await_args.kwargs["status"] == 2  # 成功

    # 5. 调用了闲鱼确认发货 API（普通订单，非小刀）
    confirm_mock.assert_awaited_once()
    assert confirm_mock.await_args.kwargs["is_bargain"] is False

    # 6. 更新了本地订单状态为 3
    assert any(
        "UPDATE xianyu_trade_order" in sql and "order_status = 3" in sql
        for sql, _ in db.execute_calls
    ), "应更新 xianyu_trade_order.order_status=3"

    # 7. 没有触发失败通知
    notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_kami_delivery_insufficient_stock_inserts_failed_record_without_sending(monkeypatch):
    """2. 库存不足：claimed_count=0 → 插入失败记录（status=3），不发送消息，触发失败通知。"""
    db = _KamiDeliveryDB(claimed_rowcount=0, claimed_items=[])
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 不发送消息
    send_mock.assert_not_awaited()
    # 不调用确认发货
    confirm_mock.assert_not_awaited()
    # 库存不足会触发失败通知（提醒用户补充库存）
    notify_mock.assert_awaited_once()
    # 插入失败记录，fail_reason 含"卡密库存不足"
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["status"] == 3
    assert "卡密库存不足" in insert_mock.await_args.kwargs["fail_reason"]
    assert insert_mock.await_args.kwargs["content"] is None


@pytest.mark.asyncio
async def test_kami_delivery_claim_succeeds_but_read_returns_empty(monkeypatch):
    """3. 认领成功（claimed_count>0）但读取已认领卡密返回空：回滚卡密，插入失败记录。"""
    db = _KamiDeliveryDB(claimed_rowcount=1, claimed_items=[])  # 认领影响 1 行，但 SELECT 返回空
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    send_mock.assert_not_awaited()
    confirm_mock.assert_not_awaited()
    # 应回滚卡密状态
    assert any(
        "UPDATE card_item" in sql and "SET status = 0" in sql
        for sql, _ in db.execute_calls
    ), "读取失败时应回滚卡密状态"
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["status"] == 3
    assert "卡密读取失败" in insert_mock.await_args.kwargs["fail_reason"]


@pytest.mark.asyncio
async def test_kami_delivery_send_failure_rolls_back_card_status(monkeypatch):
    """4. 发送失败：认领→发送返回 (False, False) → 回滚 card_item.status=0，used_order_id=NULL。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "KEY-AAA", "card_value": "", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(False, False))  # 发送失败，永久性错误
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 发送失败时 card_value 为空，应回退使用 card_key
    send_mock.assert_awaited_once()
    assert "KEY-AAA" in send_mock.await_args.args[3]

    # 应执行回滚 UPDATE card_item SET status=0
    rollback_calls = [
        (sql, params) for sql, params in db.execute_calls
        if "UPDATE card_item" in sql and "SET status = 0" in sql
    ]
    assert len(rollback_calls) == 1, "应回滚 card_item.status=0"
    # 不应执行标记 status=2
    assert not any(
        "UPDATE card_item" in sql and "SET status = 2" in sql
        for sql, _ in db.execute_calls
    ), "发送失败不应标记卡密为已使用"

    # 不应调用确认发货
    confirm_mock.assert_not_awaited()

    # 不应更新订单状态为 3
    assert not any(
        "UPDATE xianyu_trade_order" in sql and "order_status = 3" in sql
        for sql, _ in db.execute_calls
    )

    # 应记录失败状态的发货记录
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["status"] == 3
    # 永久性错误的 fail_reason 应提示账号登录状态
    assert "账号登录状态" in insert_mock.await_args.kwargs["fail_reason"]

    # 仍应刷新组统计（统计需要反映回滚后的状态）
    assert any(
        "UPDATE card_group g SET" in sql for sql, _ in db.execute_calls
    ), "应刷新组统计（即使发送失败）"


@pytest.mark.asyncio
async def test_kami_delivery_confirm_shipment_failure_keeps_local_order_status(monkeypatch):
    """5. 确认发货失败：卡密已发送（status=2）但 confirm_result.success=False
    → 本地订单状态不变（不更新 order_status=3）→ 不再向用户告警（卡密已发给买家）。
    """
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "KEY-AAA", "card_value": "VAL-AAA", "extra_info": ""}],
        is_bargain=0,
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={
        "success": False,
        "error": "ORDER_CLOSED",
        "message": "ORDER_ALREADY_CLOSED",
    })
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 卡密已发送 → 应标记 status=2
    assert any(
        "UPDATE card_item" in sql and "SET status = 2" in sql
        for sql, _ in db.execute_calls
    ), "卡密已发送，应标记 status=2"

    # 不应更新订单状态为 3
    assert not any(
        "UPDATE xianyu_trade_order" in sql and "order_status = 3" in sql
        for sql, _ in db.execute_calls
    ), "确认发货失败时不应更新本地 order_status=3"

    # 不再向用户告警（卡密已发给买家，用户感知已发货，由下次订单同步自动校正）
    notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_kami_delivery_multi_quantity_claims_multiple_cards_and_joins_content(monkeypatch):
    """6. 多卡密批量认领：buy_quantity=3 → 认领 3 张卡密 → 内容用 '\\n---\\n' 连接。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=3,
        claimed_items=[
            {"id": 5001, "card_key": "K1", "card_value": "V1", "extra_info": ""},
            {"id": 5002, "card_key": "K2", "card_value": "V2", "extra_info": ""},
            {"id": 5003, "card_key": "K3", "card_value": "V3", "extra_info": ""},
        ],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True})
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db, buy_quantity=3))

    # 发送的内容应包含三张卡密，并用 \n---\n 连接
    send_mock.assert_awaited_once()
    sent_content = send_mock.await_args.args[3]
    assert "V1" in sent_content
    assert "V2" in sent_content
    assert "V3" in sent_content
    assert "\n---\n" in sent_content

    # 应执行 3 次 UPDATE card_item SET status=2
    mark_used_calls = [
        sql for sql, _ in db.execute_calls
        if "UPDATE card_item" in sql and "SET status = 2" in sql
    ]
    assert len(mark_used_calls) == 3, f"应标记 3 张卡密为已使用，实际 {len(mark_used_calls)}"

    # LIMIT 参数应为 3
    claim_call = next(
        (sql, params) for sql, params in db.execute_calls
        if "UPDATE card_item" in sql and "SET status = 1" in sql
    )
    assert claim_call[1]["limit"] == 3, f"认领 LIMIT 应为 3，实际 {claim_call[1]['limit']}"

    # 插入的发货记录 content 应包含三张卡密
    insert_mock.assert_awaited_once()
    assert "V1" in insert_mock.await_args.kwargs["content"]
    assert "V2" in insert_mock.await_args.kwargs["content"]
    assert "V3" in insert_mock.await_args.kwargs["content"]


@pytest.mark.asyncio
async def test_kami_delivery_template_prefers_card_value_over_card_key(monkeypatch):
    """7. 模板替换：card_value 非空时优先使用 card_value；为空时回退到 card_key。"""
    # 场景 A：card_value 非空
    db_a = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "KEY-A", "card_value": "VALUE-A", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db_a))
    sent_a = send_mock.await_args.args[3]
    assert "VALUE-A" in sent_a
    assert "KEY-A" not in sent_a, "card_value 非空时不应包含 card_key"

    # 场景 B：card_value 为空，回退到 card_key
    db_b = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5002, "card_key": "KEY-B", "card_value": "", "extra_info": ""}],
    )
    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db_b))
    sent_b = send_mock.await_args.args[3]
    assert "KEY-B" in sent_b


@pytest.mark.asyncio
async def test_kami_delivery_without_card_group_id_skips_group_stats_refresh(monkeypatch):
    """8. card_group_id=None 时不刷新组统计（避免 SQL 错误）。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db, card_group_id=None))

    # 不应执行 UPDATE card_group
    assert not any(
        "UPDATE card_group" in sql for sql, _ in db.execute_calls
    ), "card_group_id=None 时不应刷新组统计"


@pytest.mark.asyncio
async def test_kami_delivery_without_order_id_skips_confirm_shipment(monkeypatch):
    """9. order_id 为空时不调用确认发货（部分付款消息没有真实 orderId）。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db, order_id=""))

    # 卡密已发送
    send_mock.assert_awaited_once()
    # 但不调用确认发货（无订单号）
    confirm_mock.assert_not_awaited()
    # 也不更新订单状态
    assert not any(
        "UPDATE xianyu_trade_order" in sql for sql, _ in db.execute_calls
    )
    # 发货记录应为处理中状态（status=1，已发送但无法确认）
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["status"] == 1


@pytest.mark.asyncio
async def test_kami_delivery_is_bargain_calls_freeshipping_endpoint(monkeypatch):
    """10. is_bargain=True 时调用免拼发货接口（_auto_confirm_shipment 收到 is_bargain=True）。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
        is_bargain=1,
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True, "ship_method": "freeshipping"})
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db, trigger_source="bargain"))

    confirm_mock.assert_awaited_once()
    # 小刀订单应传递 is_bargain=True，并提供 xy_goods_id 和 buyer_user_id
    assert confirm_mock.await_args.kwargs["is_bargain"] is True
    assert confirm_mock.await_args.kwargs["xy_goods_id"] == "1060794911332"
    assert confirm_mock.await_args.kwargs["buyer_user_id"] == "4182068955155@goofish"


@pytest.mark.asyncio
async def test_kami_delivery_default_template_uses_kmkey_when_not_configured(monkeypatch):
    """11. 未配置 kami_delivery_template 时使用默认 '{kmKey}'。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K-DEFAULT", "card_value": "", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    # rule 中不提供 kami_delivery_template
    rule_without_template = {"id": 200}
    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db, rule=rule_without_template))

    send_mock.assert_awaited_once()
    # 默认模板就是直接输出卡密
    assert send_mock.await_args.args[3] == "K-DEFAULT"


@pytest.mark.asyncio
async def test_kami_delivery_send_exception_treated_as_failure_and_rolls_back(monkeypatch):
    """12. 发送消息抛异常：捕获后视为发送失败，回滚卡密，记录友好失败原因（不暴露异常细节）。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
    )
    send_mock = AsyncMock(side_effect=RuntimeError("WebSocket disconnected"))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 应执行回滚
    assert any(
        "UPDATE card_item" in sql and "SET status = 0" in sql
        for sql, _ in db.execute_calls
    ), "异常时应回滚卡密 status=0"

    # 不调用确认发货
    confirm_mock.assert_not_awaited()

    # 记录的失败原因应是用户友好的，不包含原始异常字符串
    insert_mock.assert_awaited_once()
    fail_reason = insert_mock.await_args.kwargs["fail_reason"]
    assert "WebSocket disconnected" not in fail_reason, "不应暴露原始异常细节给用户"
    assert "自动重试" in fail_reason or "异常" in fail_reason


# ============================================================
# 错误兜底专项测试（新增）
# ============================================================

@pytest.mark.asyncio
async def test_kami_delivery_claim_sql_exception_inserts_friendly_failure_record(monkeypatch):
    """13. 认领 SQL 抛异常：兜底插入失败记录（status=3），fail_reason 用户友好，不向上抛出。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
        claim_exception=RuntimeError("ORA-00942: table or view does not exist"),
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    # 不应抛出异常
    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 不发送消息，不调用确认发货
    send_mock.assert_not_awaited()
    confirm_mock.assert_not_awaited()
    # 应插入失败记录
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["status"] == 3
    fail_reason = insert_mock.await_args.kwargs["fail_reason"]
    # 不应暴露原始 SQL 错误
    assert "ORA-00942" not in fail_reason
    assert "table or view" not in fail_reason
    # 应是用户友好的消息
    assert "卡密仓库" in fail_reason or "稍后重试" in fail_reason
    # 应触发失败通知
    notify_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_kami_delivery_read_sql_exception_rolls_back_and_inserts_failure_record(monkeypatch):
    """14. 读取卡密 SQL 抛异常：兜底回滚卡密，插入失败记录，不向上抛出。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[],
        read_exception=RuntimeError("connection lost to mysql://user@10.0.0.1:3306"),
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 不发送消息
    send_mock.assert_not_awaited()
    # 应回滚卡密
    assert any(
        "UPDATE card_item" in sql and "SET status = 0" in sql
        for sql, _ in db.execute_calls
    ), "读取异常时应回滚卡密"
    # 应插入失败记录
    insert_mock.assert_awaited_once()
    fail_reason = insert_mock.await_args.kwargs["fail_reason"]
    # 不应暴露连接串等敏感信息
    assert "mysql://" not in fail_reason
    assert "10.0.0.1" not in fail_reason
    assert "connection lost" not in fail_reason
    assert "卡密读取失败" in fail_reason


@pytest.mark.asyncio
async def test_kami_delivery_empty_card_content_does_not_send_empty_message(monkeypatch):
    """15. 卡密内容为空（card_key 和 card_value 均为空）：兜底插入占位提示，不发送空卡号。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "", "card_value": "", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    send_mock.assert_awaited_once()
    sent_content = send_mock.await_args.args[3]
    # 不应是空消息或只有模板前缀
    assert sent_content.strip() != "", "不应发送空消息"
    assert "您的卡密:" not in sent_content or "缺失" in sent_content or "联系" in sent_content, \
        "卡密为空时应发送占位提示，而非空卡号"


@pytest.mark.asyncio
async def test_kami_delivery_transient_send_failure_message_indicates_auto_retry(monkeypatch):
    """16. 发送消息返回临时性错误（is_transient=True）：fail_reason 应提示"系统将自动重试"。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(False, True))  # 临时性错误
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    insert_mock.assert_awaited_once()
    fail_reason = insert_mock.await_args.kwargs["fail_reason"]
    assert "自动重试" in fail_reason, "临时性错误应提示系统将自动重试"
    assert "账号登录状态" not in fail_reason, "临时性错误不应提示账号登录问题"


@pytest.mark.asyncio
async def test_kami_delivery_permanent_send_failure_message_indicates_account_issue(monkeypatch):
    """17. 发送消息返回永久性错误（is_transient=False）：fail_reason 应提示"请检查账号登录状态"。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(False, False))  # 永久性错误
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    insert_mock.assert_awaited_once()
    fail_reason = insert_mock.await_args.kwargs["fail_reason"]
    assert "账号登录状态" in fail_reason, "永久性错误应提示检查账号登录状态"


@pytest.mark.asyncio
async def test_kami_delivery_confirm_failure_does_not_alert_user_when_card_already_sent(monkeypatch):
    """18. 确认发货失败时不再向用户告警（卡密已发给买家，用户感知已发货）。"""
    db = _KamiDeliveryDB(
        claimed_rowcount=1,
        claimed_items=[{"id": 5001, "card_key": "K", "card_value": "V", "extra_info": ""}],
    )
    send_mock = AsyncMock(return_value=(True, False))
    insert_mock = AsyncMock()
    confirm_mock = AsyncMock(return_value={
        "success": False,
        "error": "FAIL_SYS_TOKEN_EXPIRED",
        "message": "token expired",
    })
    notify_mock = AsyncMock()
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_mock)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_mock)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", confirm_mock)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_mock)

    await ws_delivery_handler._execute_kami_delivery(**_common_kwargs(db=db))

    # 卡密已发送，不应触发失败通知
    notify_mock.assert_not_awaited()
    # 发货记录应为成功状态（卡密已发送）
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["status"] == 2


def test_friendly_confirm_error_maps_known_error_codes():
    """19. _friendly_confirm_error 将已知错误码映射为用户友好消息。"""
    # token 过期
    msg = ws_delivery_handler._friendly_confirm_error({"error": "TOKEN_EXPIRED", "message": "raw"})
    assert "重新登录" in msg
    assert "raw" not in msg

    # 频率限制
    msg = ws_delivery_handler._friendly_confirm_error({"error": "RATE_LIMIT_429", "message": "raw"})
    assert "频率限制" in msg

    # 订单关闭
    msg = ws_delivery_handler._friendly_confirm_error({"error": "ORDER_CLOSED", "message": "raw"})
    assert "订单已关闭" in msg

    # 能力不可用
    msg = ws_delivery_handler._friendly_confirm_error({"error": "CAPABILITY_UNAVAILABLE", "message": "raw"})
    assert "不可用" in msg

    # 未知错误：不暴露原始 message
    msg = ws_delivery_handler._friendly_confirm_error({"error": "UNKNOWN_XYZ", "message": "internal stack trace"})
    assert "internal stack trace" not in msg
    assert "自动重试" in msg

    # None 输入
    msg = ws_delivery_handler._friendly_confirm_error(None)
    assert "不可用" in msg


@pytest.mark.asyncio
async def test_send_delivery_message_empty_content_returns_permanent_failure():
    """20. _send_delivery_message 空内容返回 (False, False) 永久性错误。"""
    result = await ws_delivery_handler._send_delivery_message(10, "sid", "buyer@goofish", "")
    assert result == (False, False)

    result = await ws_delivery_handler._send_delivery_message(10, "sid", "buyer@goofish", "   ")
    assert result == (False, False)


@pytest.mark.asyncio
async def test_send_delivery_message_missing_sid_returns_permanent_failure():
    """21. _send_delivery_message 会话 ID 或买家 ID 为空返回 (False, False)。"""
    result = await ws_delivery_handler._send_delivery_message(10, "", "buyer@goofish", "content")
    assert result == (False, False)

    result = await ws_delivery_handler._send_delivery_message(10, "sid", "", "content")
    assert result == (False, False)
