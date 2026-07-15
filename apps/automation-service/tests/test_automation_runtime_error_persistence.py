from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

import pytest

import app.services.automation_runtime as runtime
from app.core.http_failures import bind_request_id, reset_request_id


class _CaptureDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.commits = 0

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), dict(params or {})))
        return None

    async def commit(self) -> None:
        self.commits += 1


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _RowsDb:
    def __init__(self, rows) -> None:
        self.rows = rows

    async def execute(self, _statement, _params=None):
        return _Rows(self.rows)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_execute_workflow_does_not_persist_or_return_unknown_exception_text(monkeypatch):
    secret = "Authorization=Bearer secret-runtime-token https://vendor.example/private"
    db = _CaptureDb()

    async def _raise_unknown(*_args, **_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(runtime, "_execute_workflow_node", _raise_unknown)

    result = await runtime.execute_workflow(
        db,
        {
            "tenantId": 7,
            "workflowId": 8,
            "executionId": 9,
            "workflow": {
                "id": 8,
                "name": "安全回归",
                "nodes": [{"id": "node-1", "type": "action", "name": "测试节点"}],
                "edges": [],
            },
            "input": {},
        },
    )

    serialized_result = json.dumps(result, ensure_ascii=False)
    serialized_writes = json.dumps(db.calls, ensure_ascii=False)

    assert result["status"] == "failed"
    assert result["errorCode"] == "WORKFLOW_NODE_RUNTIME_ERROR"
    assert result["errorMessage"] == "节点执行异常，请稍后重试"
    assert secret not in serialized_result
    assert "secret-runtime-token" not in serialized_writes
    assert "vendor.example" not in serialized_writes


@pytest.mark.anyio
async def test_execute_workflow_normalizes_untrusted_node_failure_before_any_persistence(monkeypatch):
    db = _CaptureDb()

    async def _return_untrusted_failure(*_args, **_kwargs):
        return {
            "ok": False,
            "status": "failed",
            "message": "provider said secret-body at https://vendor.example/private",
            "error": "Authorization=Bearer nested-secret-token",
            "responseBody": "raw upstream response",
            "accessToken": "nested-secret-token",
            "images": [
                {
                    "status": "failed",
                    "aiReason": "HTTP 500: raw provider body",
                    "imageUrl": "https://vendor.example/private-image",
                }
            ],
            "artifactType": "json",
            "artifactTitle": "失败产物",
            "artifact": {
                "status": "failed",
                "lastError": "SQL syntax with password=hunter2",
                "requestUrl": "https://vendor.example/private-request",
            },
        }

    monkeypatch.setattr(runtime, "_execute_workflow_node", _return_untrusted_failure)

    result = await runtime.execute_workflow(
        db,
        {
            "tenantId": 7,
            "workflowId": 8,
            "executionId": 9,
            "workflow": {
                "id": 8,
                "name": "供应商失败回归",
                "nodes": [{"id": "node-1", "type": "action", "name": "供应商节点"}],
                "edges": [],
            },
            "input": {},
        },
    )

    serialized = json.dumps({"result": result, "writes": db.calls}, ensure_ascii=False)

    assert result["status"] == "failed"
    assert result["errorCode"] == "WORKFLOW_NODE_FAILED"
    assert result["errorMessage"] == "节点执行失败，请检查配置后重试"
    for forbidden in (
        "secret-body",
        "nested-secret-token",
        "raw upstream",
        "raw provider",
        "hunter2",
        "vendor.example",
    ):
        assert forbidden not in serialized


@pytest.mark.anyio
async def test_execute_workflow_preserves_registered_public_business_failure(monkeypatch):
    db = _CaptureDb()

    async def _return_public_failure(*_args, **_kwargs):
        return {
            "ok": False,
            "errorCode": "SHOP_URL_REQUIRED",
            "message": "untrusted caller text must not select the public message",
        }

    monkeypatch.setattr(runtime, "_execute_workflow_node", _return_public_failure)

    result = await runtime.execute_workflow(
        db,
        {
            "tenantId": 7,
            "workflowId": 8,
            "executionId": 9,
            "workflow": {
                "id": 8,
                "name": "业务校验回归",
                "nodes": [{"id": "node-1", "type": "shop_fetch", "name": "店铺获取"}],
                "edges": [],
            },
            "input": {},
        },
    )

    serialized = json.dumps({"result": result, "writes": db.calls}, ensure_ascii=False)

    assert result["errorCode"] == "SHOP_URL_REQUIRED"
    assert result["errorMessage"] == "请先配置店铺链接"
    assert "untrusted caller text" not in serialized


@pytest.mark.anyio
async def test_timeline_reader_neutralizes_legacy_error_content_and_payload():
    db = _RowsDb([
        {
            "id": 1,
            "node_key": "node-1",
            "event_level": "ERROR",
            "event_type": "node_failed",
            "title": "节点失败",
            "content": "opaque upstream response body",
            "payload_json": json.dumps({
                "error": "provider database details",
                "responseBody": "raw upstream response",
                "accessToken": "legacy-secret-token",
                "requestUrl": "https://vendor.example/private",
            }),
        }
    ])

    result = await runtime.list_workflow_timeline(db, tenant_id=1, execution_id=2)
    serialized = json.dumps(result, ensure_ascii=False)

    assert result[0]["errorCode"] == "RUNTIME_OPERATION_FAILED"
    assert result[0]["content"] == "操作失败，请稍后重试"
    for forbidden in ("opaque upstream", "provider database", "raw upstream", "legacy-secret", "vendor.example"):
        assert forbidden not in serialized


@pytest.mark.anyio
async def test_state_reader_neutralizes_legacy_nested_failure_details():
    db = _RowsDb([
        {
            "id": 1,
            "node_key": "publish",
            "var_name": "publish_results",
            "var_value": json.dumps([
                {
                    "status": "failed",
                    "error": "opaque provider rejection",
                    "accessToken": "legacy-secret-token",
                    "imageUrl": "https://vendor.example/private",
                }
            ]),
            "var_type": "json",
        }
    ])

    result = await runtime.list_workflow_state_variables(db, tenant_id=1, execution_id=2)
    serialized = json.dumps(result, ensure_ascii=False)

    failure = result[0]["var_value_parsed"][0]
    assert failure["errorCode"] == "RUNTIME_OPERATION_FAILED"
    assert failure["errorMessage"] == "操作失败，请稍后重试"
    for forbidden in ("opaque provider", "legacy-secret", "vendor.example"):
        assert forbidden not in serialized


def test_runtime_failure_logging_contains_only_error_type_and_request_id(caplog):
    secret = "Authorization=Bearer log-secret https://vendor.example/private"
    request_token = bind_request_id("req-runtime-safe-123")
    try:
        with caplog.at_level(logging.ERROR, logger=runtime.__name__):
            runtime._log_runtime_failure("contract_test", RuntimeError(secret))
    finally:
        reset_request_id(request_token)

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "operation=contract_test" in rendered
    assert "errorType=RuntimeError" in rendered
    assert "requestId=req-runtime-safe-123" in rendered
    assert "log-secret" not in rendered
    assert "vendor.example" not in rendered


def test_runtime_source_forbids_exception_values_and_provider_bodies_at_error_boundaries():
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "exc_info" not in source
    assert "logger.exception" not in source
    assert "aiResponsePreview" not in source
    assert ".text[:" not in source
    assert 'return {"raw": raw}' not in source

    violations: list[str] = []
    for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler) and node.name):
        exception_name = handler.name
        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "str":
                    if any(isinstance(arg, ast.Name) and arg.id == exception_name for arg in node.args):
                        violations.append(f"line {node.lineno}: str({exception_name})")
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "logger" and any(
                        isinstance(arg, ast.Name) and arg.id == exception_name for arg in node.args
                    ):
                        violations.append(f"line {node.lineno}: logger received {exception_name}")
            if isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name):
                if node.value.id == exception_name:
                    violations.append(f"line {node.lineno}: f-string contains {exception_name}")

    assert violations == []
