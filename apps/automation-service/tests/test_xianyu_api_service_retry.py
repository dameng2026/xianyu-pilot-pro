from app.services import xianyu_api_service


class _FakeCookieJar:
    def __init__(self, cookies):
        self._cookies = dict(cookies)

    def get_dict(self):
        return dict(self._cookies)


class _FakeResponse:
    def __init__(self, payload, cookies=None):
        self._payload = payload
        self.cookies = _FakeCookieJar(cookies or {})

    def json(self):
        return self._payload


def test_fetch_conversation_user_info_retries_with_refreshed_cookie(monkeypatch):
    saved_cookies = []
    call_index = {"value": 0}

    monkeypatch.setattr(
        xianyu_api_service,
        "_get_account_auth",
        lambda account_id: {"encrypted_cookie": "enc-cookie", "encrypted_token": "enc-token"},
    )
    monkeypatch.setattr(
        xianyu_api_service,
        "_decrypt_value",
        lambda value: "_m_h5_tk=oldtoken_123; other=1" if value == "enc-cookie" else "oldtoken_123",
    )
    monkeypatch.setattr(
        xianyu_api_service,
        "_persist_account_auth_cookies",
        lambda account_id, cookie_str: saved_cookies.append((account_id, cookie_str)),
    )

    def fake_post(*_args, **kwargs):
        call_index["value"] += 1
        if call_index["value"] == 1:
            return _FakeResponse(
                {"ret": ["FAIL_SYS_TOKEN_EXPIRED::token expired"]},
                cookies={"_m_h5_tk": "newtoken_456", "x5sec": "guard"},
            )
        assert "_m_h5_tk=newtoken_456" in kwargs["headers"]["Cookie"]
        return _FakeResponse(
            {
                "ret": ["SUCCESS::ok"],
                "data": {
                    "userInfo": {
                        "logo": "https://img.alicdn.com/imgextra/avatar-retry.png",
                        "nick": "buyer-b",
                    }
                },
            }
        )

    monkeypatch.setattr(xianyu_api_service.requests, "post", fake_post)

    result = xianyu_api_service.fetch_conversation_user_info(8, "63247704189")

    assert result == {
        "success": True,
        "data": {
            "avatar": "https://img.alicdn.com/imgextra/avatar-retry.png",
            "nick": "buyer-b",
        },
    }
    assert call_index["value"] == 2
    assert saved_cookies == [
        (8, "_m_h5_tk=newtoken_456; other=1; x5sec=guard"),
    ]
