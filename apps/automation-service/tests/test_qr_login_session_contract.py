from pathlib import Path


AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AUTOMATION_ROOT.parents[1]


def test_feishu_qr_flow_preserves_capture_session_for_solve():
    source = (AUTOMATION_ROOT / "app/services/feishu_chat.py").read_text(encoding="utf-8")

    assert "Optional[tuple[bytes, str]]" in source
    assert 'session_id = str(data.get("sessionId") or "")' in source
    assert '"sessionId": qr_session_id' in source
    assert '"cookie": old_cookie' not in source
    assert "_cancel_qr_session(tenant_id, qr_session_id)" in source


def test_crawler_qr_sessions_are_tenant_bound_one_time_resources():
    source = (REPO_ROOT / "apps/crawler-service/src/server.ts").read_text(encoding="utf-8")

    assert "const qrLoginSessions = new Map<string, QrLoginSession>()" in source
    assert "session.tenantId !== tenantId" in source
    assert "session.consuming" in source
    assert "closeQrLoginSession(sessionId)" in source
    assert "completeQrLoginSession(session.context, session.page" in source
    assert "solveQrLoginInBrowser" not in source
