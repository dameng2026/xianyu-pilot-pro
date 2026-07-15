from app.services import xianyu_api_service


def test_fetch_sold_orders_page_returns_failed_when_payload_shape_is_unexpected(monkeypatch):
    monkeypatch.setattr(xianyu_api_service, "_get_account_auth", lambda _account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(xianyu_api_service, "_decrypt_value", lambda _value: "_m_h5_tk=test; unb=demo")
    monkeypatch.setattr(
        xianyu_api_service,
        "_post_mtop_with_token_retry",
        lambda *_args, **_kwargs: {"success": True, "data": {"module": []}},
    )

    result = xianyu_api_service.fetch_sold_orders_page(8)

    assert result["success"] is False
    assert "结构异常" in result["error"]


def test_fetch_sold_orders_page_tolerates_non_numeric_total_count(monkeypatch):
    monkeypatch.setattr(xianyu_api_service, "_get_account_auth", lambda _account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(xianyu_api_service, "_decrypt_value", lambda _value: "_m_h5_tk=test; unb=demo")
    monkeypatch.setattr(
        xianyu_api_service,
        "_post_mtop_with_token_retry",
        lambda *_args, **_kwargs: {
            "success": True,
            "data": {
                "module": {
                    "items": [{"id": "1"}],
                    "nextPage": "true",
                    "totalCount": "not-a-number",
                }
            },
        },
    )

    result = xianyu_api_service.fetch_sold_orders_page(8)

    assert result["success"] is True
    assert result["data"] == {
        "items": [{"id": "1"}],
        "nextPage": True,
        "totalCount": 0,
    }
