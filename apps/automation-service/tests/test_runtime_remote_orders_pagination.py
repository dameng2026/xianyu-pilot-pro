import pytest

from app.services import automation_runtime


@pytest.mark.asyncio
async def test_fetch_remote_sold_orders_continues_paging_when_total_count_exceeds_first_page(monkeypatch):
    page_calls = []

    async def fake_fetch_page(_account_id, page_number, query_code="ALL"):
        page_calls.append((page_number, query_code))
        return {
            1: {
                "items": [{"externalOrderId": "ORDER-001"}],
                "nextPage": False,
                "totalCount": 61,
            },
            2: {
                "items": [{"externalOrderId": "ORDER-002"}],
                "nextPage": False,
                "totalCount": 61,
            },
            3: {
                "items": [{"externalOrderId": "ORDER-003"}],
                "nextPage": False,
                "totalCount": 61,
            },
        }[page_number]

    monkeypatch.setattr(automation_runtime, "_fetch_remote_sold_orders_page", fake_fetch_page)
    monkeypatch.setattr(automation_runtime, "_parse_remote_sold_order_item", lambda item: item)

    result = await automation_runtime._fetch_remote_sold_orders(8)

    assert [item["externalOrderId"] for item in result] == [
        "ORDER-001",
        "ORDER-002",
        "ORDER-003",
    ]
    assert page_calls == [(1, "ALL"), (2, "ALL"), (3, "ALL")]
