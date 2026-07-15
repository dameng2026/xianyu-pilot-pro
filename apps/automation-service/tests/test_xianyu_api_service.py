import pytest

from app.services import xianyu_api_service


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_conversation_user_info_supports_nested_module_user_info(monkeypatch):
    monkeypatch.setattr(
        xianyu_api_service,
        "_get_account_auth",
        lambda account_id: {"encrypted_cookie": "enc-cookie", "encrypted_token": "enc-token"},
    )
    monkeypatch.setattr(
        xianyu_api_service,
        "_decrypt_value",
        lambda value: "_m_h5_tk=testtoken_123; other=1" if value == "enc-cookie" else "testtoken_123",
    )
    monkeypatch.setattr(
        xianyu_api_service.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            {
                "ret": ["SUCCESS::调用成功"],
                "data": {
                    "module": {
                        "userInfo": {
                            "logo": "//img.alicdn.com/imgextra/avatar-demo.png",
                            "nick": "买家A",
                        }
                    }
                },
            }
        ),
    )

    result = xianyu_api_service.fetch_conversation_user_info(8, "63247704189")

    assert result == {
        "success": True,
        "data": {
            "avatar": "//img.alicdn.com/imgextra/avatar-demo.png",
            "nick": "买家A",
        },
    }
