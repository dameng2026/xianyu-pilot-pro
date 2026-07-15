from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_ws_credential_gate_message_uses_readable_chinese():
    source = (SERVICE_ROOT / "app/api/v1/routes/misc.py").read_text(encoding="utf-8")

    assert "统一登录校验" in source
    assert "账号管理或连接管理页" in source


def test_ws_credential_query_prefers_latest_auth_record():
    source = (SERVICE_ROOT / "app/api/v1/routes/misc.py").read_text(encoding="utf-8")

    assert "ORDER BY COALESCE(auth.updated_time, auth.created_time) DESC, auth.id DESC" in source


def test_ws_startup_prefers_latest_auth_record():
    source = (SERVICE_ROOT / "app/services/ws_startup.py").read_text(encoding="utf-8")

    assert "ORDER BY COALESCE(auth2.updated_time, auth2.created_time) DESC, auth2.id DESC" in source
    assert "SELECT auth2.id" in source


def test_ws_restart_and_refresh_flows_use_latest_auth_record():
    ws_client_source = (SERVICE_ROOT / "app/services/ws_client.py").read_text(encoding="utf-8")
    refresher_source = (SERVICE_ROOT / "app/services/cookie_token_refresher.py").read_text(encoding="utf-8")

    assert "ORDER BY COALESCE(auth2.updated_time, auth2.created_time) DESC, auth2.id DESC" in ws_client_source
    assert refresher_source.count("ORDER BY COALESCE(auth2.updated_time, auth2.created_time) DESC, auth2.id DESC") >= 3
