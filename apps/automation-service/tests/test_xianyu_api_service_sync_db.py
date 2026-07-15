from app.core import cookie_crypto
from app.services import xianyu_api_service


class _FakeCursor:
    def __init__(self, row=None, calls=None):
        self._row = row
        self._calls = calls if calls is not None else []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self._calls.append((sql, params))

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, row=None):
        self.calls = []
        self.closed = False
        self._row = row

    def cursor(self):
        return _FakeCursor(self._row, self.calls)

    def close(self):
        self.closed = True


def test_get_account_auth_uses_sync_connection(monkeypatch):
    fake_connection = _FakeConnection(
        {
            "encrypted_cookie": "enc-cookie",
            "encrypted_token": "enc-token",
            "external_uid": "2216920957000",
        }
    )
    monkeypatch.setattr(
        xianyu_api_service,
        "_open_sync_db_connection",
        lambda: fake_connection,
    )

    result = xianyu_api_service._get_account_auth(3)

    assert result == {
        "encrypted_cookie": "enc-cookie",
        "encrypted_token": "enc-token",
        "external_uid": "2216920957000",
    }
    assert fake_connection.closed is True
    assert fake_connection.calls[0][1] == (3,)


def test_persist_account_auth_cookies_uses_sync_connection(monkeypatch):
    fake_connection = _FakeConnection()
    monkeypatch.setattr(
        xianyu_api_service,
        "_open_sync_db_connection",
        lambda: fake_connection,
    )
    monkeypatch.setattr(
        cookie_crypto,
        "encrypt_cookie_for_storage",
        lambda value: f"enc:{value}",
    )

    xianyu_api_service._persist_account_auth_cookies(8, "_m_h5_tk=newtoken_456; other=1")

    assert fake_connection.closed is True
    assert fake_connection.calls[0][1] == (
        "enc:_m_h5_tk=newtoken_456; other=1",
        "enc:newtoken_456",
        8,
    )
