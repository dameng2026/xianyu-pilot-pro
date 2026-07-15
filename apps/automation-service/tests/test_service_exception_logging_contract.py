from __future__ import annotations

import ast
import logging
from pathlib import Path

from app.core.failure_logging import log_service_failure
from app.core.http_failures import bind_request_id, reset_request_id


SERVICE_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "app/services/automation_runtime.py",
    "app/services/captcha_solver.py",
    "app/services/ws_client.py",
    "app/services/ws_token.py",
    "app/services/cookie_token_refresher.py",
    "app/services/xianyu_api_service.py",
    "app/services/xianyu_goods_sync.py",
    "app/main.py",
)
UNTRUSTED_LOG_NAMES = {
    "body_text",
    "close_msg",
    "err",
    "error",
    "error_msg",
    "reason",
    "response_body",
    "ret",
    "ret_msg",
}
UNTRUSTED_GET_KEYS = {
    "body",
    "error",
    "errorMessage",
    "failedReason",
    "message",
    "reason",
    "response",
    "responseBody",
    "ret",
    "url",
}


def _is_logger_call(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
    )


def _contains_untrusted_log_value(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in UNTRUSTED_LOG_NAMES:
            return True
        if isinstance(child, ast.Attribute) and child.attr in {"text", "content"}:
            return True
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "get"
            and child.args
            and isinstance(child.args[0], ast.Constant)
            and child.args[0].value in UNTRUSTED_GET_KEYS
        ):
            return True
    return False


def test_service_exception_boundaries_never_log_values_or_provider_bodies():
    violations: list[str] = []

    for relative_path in TARGETS:
        path = SERVICE_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        if "exc_info" in source:
            violations.append(f"{relative_path}: exc_info is forbidden")
        if "logger.exception" in source:
            violations.append(f"{relative_path}: logger.exception is forbidden")

        exception_names = {
            handler.name
            for handler in ast.walk(tree)
            if isinstance(handler, ast.ExceptHandler) and handler.name
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_logger_call(node):
                for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                    loaded_names = {
                        child.id
                        for child in ast.walk(argument)
                        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
                    }
                    leaked_exception_names = loaded_names & exception_names
                    if leaked_exception_names:
                        violations.append(
                            f"{relative_path}:{node.lineno}: logger received exception variable "
                            f"{sorted(leaked_exception_names)}"
                        )
                    if _contains_untrusted_log_value(argument):
                        violations.append(
                            f"{relative_path}:{node.lineno}: logger received upstream error/body value"
                        )

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str":
                if any(isinstance(arg, ast.Name) and arg.id in exception_names for arg in node.args):
                    violations.append(f"{relative_path}:{node.lineno}: exception converted with str()")

            if isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name):
                if node.value.id in exception_names:
                    violations.append(f"{relative_path}:{node.lineno}: exception interpolated in f-string")

    assert violations == [], "\n".join(violations)


def test_service_failure_logger_emits_only_metadata(caplog):
    token = bind_request_id("req-service-safe-123")
    try:
        with caplog.at_level(logging.WARNING, logger="safe-service-contract"):
            log_service_failure(
                logging.getLogger("safe-service-contract"),
                RuntimeError("Authorization=Bearer log-secret https://vendor.example/private"),
                operation="contract_test",
                tenant_id=7,
                account_id=8,
                level=logging.WARNING,
            )
    finally:
        reset_request_id(token)

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "operation=contract_test" in rendered
    assert "errorType=RuntimeError" in rendered
    assert "requestId=req-service-safe-123" in rendered
    assert "tenantId=7" in rendered
    assert "accountId=8" in rendered
    assert "log-secret" not in rendered
    assert "vendor.example" not in rendered


def test_service_failure_logger_allows_only_registered_event_types(caplog):
    token = bind_request_id("req-provider-rejected-123")
    try:
        with caplog.at_level(logging.WARNING, logger="safe-provider-contract"):
            logger = logging.getLogger("safe-provider-contract")
            log_service_failure(
                logger,
                None,
                operation="provider_rejection",
                level=logging.WARNING,
                error_type="ProviderRejected",
            )
            log_service_failure(
                logger,
                RuntimeError(),
                operation="invalid_error_type",
                level=logging.WARNING,
                error_type="AuthorizationBearerSecret",
            )
    finally:
        reset_request_id(token)

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "errorType=ProviderRejected" in rendered
    assert "errorType=RuntimeError" in rendered
    assert "requestId=req-provider-rejected-123" in rendered
    assert "AuthorizationBearerSecret" not in rendered
