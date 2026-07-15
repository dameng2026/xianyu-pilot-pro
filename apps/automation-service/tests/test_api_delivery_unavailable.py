from pathlib import Path

import pytest

from app.services import ws_delivery_handler


@pytest.mark.asyncio
async def test_legacy_api_delivery_is_fail_closed_without_network_calls(monkeypatch):
    records = []
    notices = []

    async def capture_record(*args, **kwargs):
        records.append((args, kwargs))

    async def capture_notice(**kwargs):
        notices.append(kwargs)

    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", capture_record)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", capture_notice)

    await ws_delivery_handler._execute_api_delivery(
        db=object(),
        tenant_id=9,
        account_id=7,
        order_id="order-1",
        s_id="session-1",
        pnm_id="message-1",
        buyer_user_id="buyer-1",
        buyer_user_name="buyer",
        xy_goods_id="goods-1",
        buy_quantity=1,
        rule={"id": 3, "api_allocate_url": "https://attacker.example"},
        trigger_source="payment",
    )

    assert records[0][1]["status"] == 3
    assert "暂不可用" in records[0][1]["fail_reason"]
    assert notices and notices[0]["tenant_id"] == 9


def test_api_delivery_implementation_contains_no_http_client():
    source = Path(ws_delivery_handler.__file__).read_text(encoding="utf-8")

    assert "aiohttp.ClientSession" not in source
    assert 'session.post(api_url' not in source
