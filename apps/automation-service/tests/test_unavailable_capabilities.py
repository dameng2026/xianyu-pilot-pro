import pytest

from app.api.v1.routes import auto_delivery, items, order
from app.schemas.common import TriggerAutoDeliveryReqDTO
from app.schemas.order import SoldOrderSyncReqDTO
from app.services import ws_delivery_handler, xianyu_api_service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        items.update_item_stock,
        items.update_auto_delivery_status,
        items.update_auto_confirm_shipment,
        items.auto_delivery_records,
        items.auto_reply_records,
        items.get_rag_auto_reply_config,
        items.update_rag_auto_reply_config,
        items.get_sku_specs,
    ],
)
async def test_legacy_item_stubs_report_unavailable_instead_of_success(endpoint):
    result = await endpoint({}, db=None, _=None)

    assert result.code == 503
    assert "未执行" in result.msg or "请使用" in result.msg


@pytest.mark.asyncio
async def test_legacy_auto_delivery_trigger_does_not_claim_task_was_submitted():
    result = await auto_delivery.trigger_auto_delivery(
        TriggerAutoDeliveryReqDTO(xianyu_account_id=1, order_id="order-1"),
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert "未提交" in result.msg


@pytest.mark.asyncio
async def test_legacy_auto_delivery_mutations_report_unavailable():
    stock_result = await auto_delivery.update_delivery_stock(
        id=1,
        stock=10,
        current_user={"tenant_id": 1},
    )
    return_result = await auto_delivery.manual_return_auto_delivery(
        {"recordId": 1},
        current_user={"tenant_id": 1},
    )

    assert stock_result.code == 503
    assert return_result.code == 503


@pytest.mark.asyncio
async def test_legacy_order_sync_does_not_report_zero_as_a_successful_sync():
    result = await order.sync_sold_orders(
        SoldOrderSyncReqDTO(xianyu_account_id=1),
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert "未启动" in result.msg


def test_confirm_shipment_capability_is_explicitly_fail_closed(monkeypatch):
    monkeypatch.setattr(
        xianyu_api_service.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("unavailable capability must not call the platform"),
    )

    result = xianyu_api_service.confirm_shipment(1, "order-1")

    assert result == {
        "success": False,
        "error": "LOCAL_ONLY_SHIPMENT_STATUS",
        "message": "闲鱼确认发货 API 当前不可用，仅更新本地发货状态",
        "account_id": 1,
        "order_id": "order-1",
    }


@pytest.mark.asyncio
async def test_ws_auto_confirm_uses_fail_closed_capability(monkeypatch):
    monkeypatch.setattr(
        xianyu_api_service,
        "call_xianyu_api",
        lambda *args, **kwargs: pytest.fail("unverified MTOP endpoint must not be called"),
    )

    result = await ws_delivery_handler._auto_confirm_shipment(1, 2, "order-1")

    assert result["success"] is False
    assert result["error"] == "LOCAL_ONLY_SHIPMENT_STATUS"
