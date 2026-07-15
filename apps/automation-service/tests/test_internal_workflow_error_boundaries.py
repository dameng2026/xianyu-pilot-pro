from __future__ import annotations

import json

import pytest

from app.api.v1.routes import internal


class _CaptureDb:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), dict(params or {})))
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _SessionContext:
    def __init__(self, db: _CaptureDb):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def _install_session(monkeypatch, db: _CaptureDb):
    monkeypatch.setattr(internal, "_async_session", lambda: _SessionContext(db))


@pytest.mark.asyncio
async def test_workflow_background_persistence_redacts_provider_errors_and_secrets(monkeypatch):
    db = _CaptureDb()
    _install_session(monkeypatch, db)

    async def _execute(*_args, **_kwargs):
        return {
            "status": "failed",
            "errorMessage": "provider response Authorization=secret-token SQL syntax error",
            "nodeResults": [
                {
                    "status": "failed",
                    "apiKey": "secret-api-key",
                    "output": {
                        "error": "raw provider body",
                        "message": "upstream database details",
                    },
                }
            ],
            "artifacts": [{"accessToken": "artifact-secret"}],
            "timeline": [{"lastError": "timeline-secret"}],
        }

    monkeypatch.setattr(internal, "execute_workflow", _execute)

    await internal._internal_run_workflow_bg(
        tenant_id=7,
        workflow_id=8,
        execution_id=9,
        wf_name="test",
        execute_payload={},
    )

    execution_updates = [params for sql, params in db.calls if "UPDATE workflow_execution" in sql]
    assert len(execution_updates) == 1
    update = execution_updates[0]
    persisted = json.loads(update["o"])
    serialized = json.dumps(persisted, ensure_ascii=False)
    assert update["err"] == "工作流执行失败，请查看失败节点并重试"
    assert update["tid"] == 7
    assert "secret" not in serialized
    assert "provider" not in serialized
    assert "SQL" not in serialized
    assert "[REDACTED]" in serialized

    assert all("tenant_id" in sql for sql, _params in db.calls if sql.lstrip().startswith("UPDATE"))


@pytest.mark.asyncio
async def test_workflow_background_exception_persists_only_stable_error(monkeypatch):
    db = _CaptureDb()
    _install_session(monkeypatch, db)

    async def _execute(*_args, **_kwargs):
        raise RuntimeError("Authorization=secret-token provider response body")

    monkeypatch.setattr(internal, "execute_workflow", _execute)

    await internal._internal_run_workflow_bg(
        tenant_id=3,
        workflow_id=4,
        execution_id=5,
        wf_name="test",
        execute_payload={},
    )

    update = next(params for sql, params in db.calls if "UPDATE workflow_execution" in sql)
    assert update["err"] == "工作流执行失败，请查看失败节点并重试"
    assert "secret-token" not in json.dumps(update, ensure_ascii=False)


@pytest.mark.asyncio
async def test_continue_workflow_persistence_uses_stable_failure(monkeypatch):
    db = _CaptureDb()
    _install_session(monkeypatch, db)

    async def _continue(*_args, **_kwargs):
        return {
            "status": "failed",
            "errorMessage": "provider response body secret-token",
            "nodeResults": [{"status": "failed", "errorMessage": "raw body"}],
        }

    monkeypatch.setattr(internal, "continue_workflow_execution", _continue)

    await internal._internal_continue_workflow_bg(tenant_id=11, execution_id=12)

    update = next(params for sql, params in db.calls if "UPDATE workflow_execution" in sql)
    assert update["err"] == "工作流继续执行失败，请查看失败节点并重试"
    assert "secret-token" not in update["o"]
    assert "raw body" not in update["o"]
    assert update["tid"] == 11


@pytest.mark.asyncio
async def test_scheduled_task_does_not_echo_runtime_failure_message(monkeypatch):
    async def _fail(*_args, **_kwargs):
        return {
            "ok": False,
            "error": "RUNTIME_FAILURE",
            "message": "provider response body Authorization=secret-token",
        }

    monkeypatch.setattr(internal, "execute_scheduled_task", _fail)

    result = await internal.internal_run_task(
        1,
        body={"tenantId": 2},
        db=None,
        _=None,
    )

    assert result.code == 500
    assert "secret-token" not in result.msg
    assert "provider response" not in result.msg


@pytest.mark.asyncio
async def test_manual_scheduled_task_conflict_returns_409_and_requests_manual_claim(monkeypatch):
    captured = {}

    async def _conflict(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "ok": False,
            "claimed": False,
            "error": "TASK_ALREADY_RUNNING",
            "message": "internal lease detail",
        }

    monkeypatch.setattr(internal, "execute_scheduled_task", _conflict)

    result = await internal.internal_run_task(
        1,
        body={"tenantId": 2},
        db=None,
        _=None,
    )

    assert captured["manual"] is True
    assert result.code == 409
    assert result.data is None
    assert "internal lease detail" not in result.msg


@pytest.mark.asyncio
async def test_workflow_dispatch_rejects_execution_from_another_tenant(monkeypatch):
    class _NoExecutionResult:
        def scalar_one_or_none(self):
            return None

    class _NoExecutionDb:
        async def execute(self, _statement):
            return _NoExecutionResult()

    def _must_not_schedule(_coroutine):
        _coroutine.close()
        raise AssertionError("cross-tenant workflow must not be scheduled")

    monkeypatch.setattr(internal._asyncio, "create_task", _must_not_schedule)

    started = await internal.internal_execute_workflow(
        workflow_id=2,
        body={"tenantId": 3, "executionId": 4},
        db=_NoExecutionDb(),
        _=None,
    )
    continued = await internal.internal_continue_workflow(
        execution_id=4,
        body={"tenantId": 3},
        db=_NoExecutionDb(),
        _=None,
    )

    assert started.code == 404
    assert continued.code == 404


@pytest.mark.asyncio
async def test_workflow_status_endpoints_redact_error_payloads(monkeypatch):
    async def _timeline(*_args, **_kwargs):
        return [{
            "event_level": "ERROR",
            "content": "provider response Authorization=secret-token",
            "payload_json": {"responseBody": "raw upstream body"},
        }]

    async def _variables(*_args, **_kwargs):
        return [{
            "var_name": "publish_results",
            "var_value": '{"status":"failed","error":"raw provider body"}',
            "var_value_parsed": {
                "status": "failed",
                "error": "raw provider body",
                "accessToken": "secret-token",
            },
        }]

    monkeypatch.setattr(internal, "list_workflow_timeline", _timeline)
    monkeypatch.setattr(internal, "list_workflow_state_variables", _variables)

    timeline = await internal.internal_workflow_timeline(
        execution_id=1,
        tenantId=2,
        db=None,
        _=None,
    )
    variables = await internal.internal_workflow_state_variables(
        execution_id=1,
        tenantId=2,
        db=None,
        _=None,
    )

    serialized = json.dumps({"timeline": timeline.data, "variables": variables.data}, ensure_ascii=False)
    assert "secret-token" not in serialized
    assert "raw provider" not in serialized
    assert "upstream body" not in serialized
    assert "[REDACTED]" in serialized
