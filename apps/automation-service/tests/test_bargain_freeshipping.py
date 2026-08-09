"""免拼发货接口与小刀订单识别的测试覆盖。

覆盖点：
1. confirm_order_shipment 调度：小刀订单走 confirm_freeshipping，普通订单走 confirm_shipment
2. confirm_freeshipping：参数校验、幂等成功、失败传播
3. _detect_bargain_from_message_or_db：数据库 is_bargain=1 → True，trigger_source=bargain → True
4. _normalize_numeric_id：带 @goofish 后缀、纯数字、无效值
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import ws_delivery_handler, xianyu_api_service
from app.services.xianyu_api_service import (
    MAX_CONFIRM_RETRY,
    _normalize_numeric_id,
    confirm_freeshipping,
    confirm_order_shipment,
    confirm_shipment,
)


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


# ============================================================
# _normalize_numeric_id 单元测试
# ============================================================

def test_normalize_numeric_id_strips_goofish_suffix():
    assert _normalize_numeric_id("3672669710@goofish") == 3672669710


def test_normalize_numeric_id_handles_pure_digits():
    assert _normalize_numeric_id("1060794911332") == 1060794911332


def test_normalize_numeric_id_handles_int_input():
    assert _normalize_numeric_id(12345) == 12345


def test_normalize_numeric_id_returns_none_for_invalid():
    assert _normalize_numeric_id("abc") is None
    assert _normalize_numeric_id(None) is None
    assert _normalize_numeric_id("") is None


# ============================================================
# confirm_order_shipment 调度测试
# ============================================================

def test_confirm_order_shipment_routes_bargain_to_freeshipping():
    """小刀订单 is_bargain=True 时应调用 confirm_freeshipping。"""
    with patch("app.services.xianyu_api_service.confirm_freeshipping") as mock_free, \
         patch("app.services.xianyu_api_service.confirm_shipment") as mock_normal:
        mock_free.return_value = {"success": True, "ship_method": "freeshipping"}
        result = confirm_order_shipment(
            account_id=1,
            order_id="ORDER-001",
            is_bargain=True,
            item_id="1060794911332",
            buyer_id="3672669710",
        )
        assert result["success"] is True
        assert result["ship_method"] == "freeshipping"
        mock_free.assert_called_once_with(1, "ORDER-001", "1060794911332", "3672669710")
        mock_normal.assert_not_called()


def test_confirm_order_shipment_routes_normal_to_consign():
    """普通订单 is_bargain=False 时应调用 confirm_shipment。"""
    with patch("app.services.xianyu_api_service.confirm_freeshipping") as mock_free, \
         patch("app.services.xianyu_api_service.confirm_shipment") as mock_normal:
        mock_normal.return_value = {"success": True}
        result = confirm_order_shipment(
            account_id=1,
            order_id="ORDER-002",
            is_bargain=False,
        )
        assert result["success"] is True
        mock_normal.assert_called_once_with(1, "ORDER-002")
        mock_free.assert_not_called()


# ============================================================
# confirm_freeshipping 参数校验测试
# ============================================================

def test_confirm_freeshipping_rejects_empty_order_id():
    result = confirm_freeshipping(1, "", "item-1", "buyer-1")
    assert result["success"] is False
    assert result["error"] == "MISSING_ORDER_ID"


def test_confirm_freeshipping_rejects_non_numeric_ids():
    result = confirm_freeshipping(1, "ORDER-001", "not-a-number", "buyer-1")
    assert result["success"] is False
    assert result["error"] == "INVALID_ITEM_OR_BUYER_ID"


def test_confirm_freeshipping_rejects_missing_auth():
    """账号认证不存在时应返回 ACCOUNT_AUTH_NOT_FOUND。"""
    with patch("app.services.xianyu_api_service._get_account_auth", return_value=None):
        result = confirm_freeshipping(1, "ORDER-001", "1060794911332", "3672669710")
        assert result["success"] is False
        assert result["error"] == "ACCOUNT_AUTH_NOT_FOUND"


# ============================================================
# _detect_bargain_from_message_or_db 测试
# ============================================================

class _BargainDetectionDB:
    """模拟数据库，根据 SQL 返回不同的 is_bargain 值。"""

    def __init__(self, is_bargain_value: int = 0):
        self._is_bargain = is_bargain_value

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT is_bargain FROM xianyu_trade_order" in sql:
            return _FakeResult(row={"is_bargain": self._is_bargain})
        raise AssertionError(f"unexpected SQL: {sql}")


@pytest.mark.asyncio
async def test_detect_bargain_returns_true_when_db_is_bargain():
    db = _BargainDetectionDB(is_bargain_value=1)
    result = await ws_delivery_handler._detect_bargain_from_message_or_db(
        db=db,
        account_id=1,
        order_id="ORDER-001",
        xy_goods_id="1060794911332",
        buyer_user_id="3672669710",
        rule={"trigger_source": "payment"},
    )
    assert result is True


@pytest.mark.asyncio
async def test_detect_bargain_returns_false_when_db_not_bargain():
    db = _BargainDetectionDB(is_bargain_value=0)
    result = await ws_delivery_handler._detect_bargain_from_message_or_db(
        db=db,
        account_id=1,
        order_id="ORDER-001",
        xy_goods_id="1060794911332",
        buyer_user_id="3672669710",
        rule={"trigger_source": "payment"},
    )
    assert result is False


@pytest.mark.asyncio
async def test_detect_bargain_returns_true_when_trigger_source_is_bargain():
    """数据库查不到时，从 rule.trigger_source=bargain 推断为小刀订单。"""
    db = _BargainDetectionDB(is_bargain_value=0)

    async def _always_none(*args, **kwargs):
        return _FakeResult(row=None)

    db.execute = _always_none
    result = await ws_delivery_handler._detect_bargain_from_message_or_db(
        db=db,
        account_id=1,
        order_id="ORDER-001",
        xy_goods_id="1060794911332",
        buyer_user_id="3672669710",
        rule={"trigger_source": "bargain"},
    )
    assert result is True


@pytest.mark.asyncio
async def test_detect_bargain_returns_false_when_no_evidence():
    """数据库查不到且 trigger_source 不是 bargain 时返回 False。"""
    db = _BargainDetectionDB(is_bargain_value=0)

    async def _always_none(*args, **kwargs):
        return _FakeResult(row=None)

    db.execute = _always_none
    result = await ws_delivery_handler._detect_bargain_from_message_or_db(
        db=db,
        account_id=1,
        order_id="ORDER-001",
        xy_goods_id="1060794911332",
        buyer_user_id="3672669710",
        rule={"trigger_source": "payment"},
    )
    assert result is False


# ============================================================
# _auto_confirm_shipment 调度测试（验证小刀订单走免拼发货）
# ============================================================

@pytest.mark.asyncio
async def test_auto_confirm_shipment_calls_freeshipping_for_bargain(monkeypatch):
    """小刀订单 _auto_confirm_shipment 应调用 confirm_order_shipment 且 is_bargain=True。"""
    captured = {}

    def _fake_confirm_order_shipment(account_id, order_id, is_bargain=False, item_id=None, buyer_id=None):
        captured["is_bargain"] = is_bargain
        captured["item_id"] = item_id
        captured["buyer_id"] = buyer_id
        return {"success": True, "ship_method": "freeshipping"}

    import app.services.ws_delivery_handler as handler_module
    monkeypatch.setattr(
        "app.services.xianyu_api_service.confirm_order_shipment",
        _fake_confirm_order_shipment,
    )

    result = await ws_delivery_handler._auto_confirm_shipment(
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        is_bargain=True,
        xy_goods_id="1060794911332",
        buyer_user_id="3672669710",
    )
    assert result["success"] is True
    assert captured["is_bargain"] is True
    assert captured["item_id"] == "1060794911332"
    assert captured["buyer_id"] == "3672669710"


@pytest.mark.asyncio
async def test_auto_confirm_shipment_calls_consign_for_normal(monkeypatch):
    """普通订单 _auto_confirm_shipment 应调用 confirm_order_shipment 且 is_bargain=False。"""
    captured = {}

    def _fake_confirm_order_shipment(account_id, order_id, is_bargain=False, item_id=None, buyer_id=None):
        captured["is_bargain"] = is_bargain
        return {"success": True}

    monkeypatch.setattr(
        "app.services.xianyu_api_service.confirm_order_shipment",
        _fake_confirm_order_shipment,
    )

    result = await ws_delivery_handler._auto_confirm_shipment(
        tenant_id=1,
        account_id=1,
        order_id="ORDER-002",
        is_bargain=False,
    )
    assert result["success"] is True
    assert captured["is_bargain"] is False


# ============================================================
# 发送顺序验证：确保发卡/文本之后才确认发货
# ============================================================

@pytest.mark.asyncio
async def test_text_delivery_sends_message_before_confirm(monkeypatch):
    """文本发货：先发消息、再更新订单状态、最后确认发货。"""
    call_order = []

    async def _fake_send(account_id, s_id, buyer_user_id, content):
        call_order.append("send_message")
        return (True, False)

    async def _fake_insert(*args, **kwargs):
        call_order.append("insert_record")

    async def _fake_detect(*args, **kwargs):
        return False

    async def _fake_confirm(*args, **kwargs):
        call_order.append("confirm_shipment")
        return {"success": True}

    class _OrderUpdateDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "UPDATE xianyu_trade_order" in sql:
                call_order.append("update_order_status")
            return _FakeResult(row=None)

    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", _fake_send)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", _fake_insert)
    monkeypatch.setattr(ws_delivery_handler, "_detect_bargain_from_message_or_db", _fake_detect)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", _fake_confirm)

    await ws_delivery_handler._execute_text_delivery(
        db=_OrderUpdateDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
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

    # 确认发货必须在发送消息之后
    assert "send_message" in call_order
    assert "confirm_shipment" in call_order
    send_idx = call_order.index("send_message")
    confirm_idx = call_order.index("confirm_shipment")
    assert send_idx < confirm_idx, f"发送消息({send_idx})必须在确认发货({confirm_idx})之前"


# ============================================================
# 确认发货重试策略测试（与成熟项目 MAX_RETRY=4 对齐）
# ============================================================

def _patch_auth_and_post(monkeypatch, post_fn):
    """Mock 账号认证与 MTOP 请求，供确认发货重试测试复用。"""
    monkeypatch.setattr(
        xianyu_api_service,
        "_get_account_auth",
        lambda account_id: {"encrypted_cookie": "enc"},
    )
    monkeypatch.setattr(
        xianyu_api_service,
        "_decrypt_value",
        lambda v: "_m_h5_tk=token_abc",
    )
    monkeypatch.setattr(
        xianyu_api_service,
        "_post_mtop_with_token_retry",
        post_fn,
    )


def test_confirm_shipment_retries_up_to_max_then_fails(monkeypatch):
    """普通发货持续失败时最多尝试 MAX_CONFIRM_RETRY 次后返回失败。"""
    calls = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        calls["n"] += 1
        return {"success": False, "error": "FAIL::临时错误", "ret": ["FAIL::临时错误"]}

    _patch_auth_and_post(monkeypatch, _fake_post)
    result = confirm_shipment(1, "order-1")

    assert result["success"] is False
    assert calls["n"] == MAX_CONFIRM_RETRY


def test_confirm_shipment_succeeds_on_retry(monkeypatch):
    """普通发货瞬时失败后第 3 次成功，应返回成功并停止重试。"""
    calls = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return {"success": False, "error": "FAIL::临时错误", "ret": ["FAIL::临时错误"]}
        return {"success": True, "ret": ["SUCCESS::调用成功"]}

    _patch_auth_and_post(monkeypatch, _fake_post)
    result = confirm_shipment(1, "order-1")

    assert result["success"] is True
    assert calls["n"] == 3


def test_confirm_freeshipping_no_retry_error_returns_immediately(monkeypatch):
    """免拼发货命中不可重试错误时直接返回失败（no_retry=True），不做重试。"""
    calls = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        calls["n"] += 1
        return {
            "success": False,
            "error": "FAIL::GROUPON_ACTIVITY_ITEM_CHECK_ERROR",
            "ret": ["FAIL::GROUPON_ACTIVITY_ITEM_CHECK_ERROR"],
        }

    _patch_auth_and_post(monkeypatch, _fake_post)
    result = confirm_freeshipping(1, "ORDER-001", "1060794911332", "3672669710")

    assert result["success"] is False
    assert result.get("no_retry") is True
    assert calls["n"] == 1


def test_confirm_freeshipping_retries_up_to_max_then_fails(monkeypatch):
    """免拼发货瞬时失败时最多尝试 MAX_CONFIRM_RETRY 次后返回失败。"""
    calls = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        calls["n"] += 1
        return {"success": False, "error": "FAIL::系统繁忙", "ret": ["FAIL::系统繁忙"]}

    _patch_auth_and_post(monkeypatch, _fake_post)
    result = confirm_freeshipping(1, "ORDER-001", "1060794911332", "3672669710")

    assert result["success"] is False
    assert calls["n"] == MAX_CONFIRM_RETRY


def test_confirm_freeshipping_succeeds_on_retry(monkeypatch):
    """免拼发货瞬时失败后第 2 次成功，应返回成功并停止重试。"""
    calls = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            return {"success": False, "error": "FAIL::系统繁忙", "ret": ["FAIL::系统繁忙"]}
        return {"success": True, "ret": ["SUCCESS::调用成功"]}

    _patch_auth_and_post(monkeypatch, _fake_post)
    result = confirm_freeshipping(1, "ORDER-001", "1060794911332", "3672669710")

    assert result["success"] is True
    assert result.get("ship_method") == "freeshipping"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_kami_delivery_sends_message_before_confirm(monkeypatch):
    """卡密发货：先发消息、再确认发货（确保不漏发）。"""
    call_order = []

    async def _fake_send(account_id, s_id, buyer_user_id, content):
        call_order.append("send_message")
        return (True, False)

    async def _fake_insert(*args, **kwargs):
        call_order.append("insert_record")

    async def _fake_detect(*args, **kwargs):
        return False

    async def _fake_confirm(*args, **kwargs):
        call_order.append("confirm_shipment")
        return {"success": True}

    class _KamiDeliveryDB:
        async def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            sql_norm = sql.replace(",", " ,")
            if "UPDATE card_item" in sql_norm and "SET status = 1" in sql_norm and "status = 0" in sql_norm:
                # 模拟认领 1 张卡密（认领是 status 0→1；自愈是 status 1→0，不在此分支）
                return MagicMock(rowcount=1)
            if "UPDATE card_item" in sql_norm and "SET status = 0" in sql_norm and "status = 1" in sql_norm:
                # 卡密自愈：回收孤儿卡密，无孤儿
                return MagicMock(rowcount=0)
            if "SELECT id, card_key, card_value, extra_info FROM card_item" in sql:
                return _FakeResult(rows=[{"id": 1, "card_key": "KEY-001", "card_value": "VAL-001", "extra_info": None}])
            if "SELECT id FROM card_item" in sql and "claim_before" in sql:
                return _FakeResult(rows=[{"id": 1}])
            if "UPDATE card_item" in sql and "status = 2" in sql:
                call_order.append("mark_card_used")
            if "UPDATE card_group" in sql:
                pass
            return _FakeResult(row=None)

    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", _fake_send)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", _fake_insert)
    monkeypatch.setattr(ws_delivery_handler, "_detect_bargain_from_message_or_db", _fake_detect)
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", _fake_confirm)

    await ws_delivery_handler._execute_kami_delivery(
        db=_KamiDeliveryDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="62965262020",
        pnm_id="4182068955155.PNM",
        buyer_user_id="4182068955155@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1060794911332",
        buy_quantity=1,
        rule={"id": 2, "kami_delivery_template": "{kmKey}"},
        card_group_id=1,
        trigger_source="payment",
    )

    # 确认发货必须在发送消息之后
    assert "send_message" in call_order
    assert "confirm_shipment" in call_order
    send_idx = call_order.index("send_message")
    confirm_idx = call_order.index("confirm_shipment")
    assert send_idx < confirm_idx, f"发送消息({send_idx})必须在确认发货({confirm_idx})之前"
