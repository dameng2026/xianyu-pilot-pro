from unittest.mock import AsyncMock

import pytest

from app.services import ws_client


@pytest.mark.asyncio
async def test_refresh_token_restores_cookie_status_when_auth_state_is_stale(monkeypatch):
    client = ws_client.XianyuWebSocketClient(
        account_id=1,
        tenant_id=1,
        cookie_str="k=v",
        m_h5_tk="2211422464341_token",
        unb="2211422464341",
    )

    monkeypatch.setattr(
        ws_client,
        "get_ws_token_with_refreshed_m_h5_tk",
        lambda cookie_str, m_h5_tk: ("access-token", m_h5_tk, None, None),
    )
    client._load_cookie_status_snapshot = AsyncMock(
        return_value={"auth_cookie_status": 0, "auth_login_status_code": "COOKIE_EXPIRED"}
    )
    client._update_cookie_status = AsyncMock()
    client._update_token_in_db = AsyncMock()
    client._update_cookie_in_db = AsyncMock()

    result = await client._refresh_token()

    assert result is True
    client._update_cookie_status.assert_awaited_once_with(1, "OK", "账号登录状态正常")


@pytest.mark.asyncio
async def test_refresh_token_skips_cookie_status_write_when_auth_state_is_already_healthy(monkeypatch):
    client = ws_client.XianyuWebSocketClient(
        account_id=1,
        tenant_id=1,
        cookie_str="k=v",
        m_h5_tk="2211422464341_token",
        unb="2211422464341",
    )

    monkeypatch.setattr(
        ws_client,
        "get_ws_token_with_refreshed_m_h5_tk",
        lambda cookie_str, m_h5_tk: ("access-token", m_h5_tk, None, None),
    )
    client._load_cookie_status_snapshot = AsyncMock(
        return_value={"auth_cookie_status": 1, "auth_login_status_code": "OK"}
    )
    client._update_cookie_status = AsyncMock()
    client._update_token_in_db = AsyncMock()
    client._update_cookie_in_db = AsyncMock()

    result = await client._refresh_token()

    assert result is True
    client._update_cookie_status.assert_not_awaited()
