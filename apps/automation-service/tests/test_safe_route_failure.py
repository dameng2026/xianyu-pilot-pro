import logging

from app.core.http_failures import (
    bind_request_id,
    reset_request_id,
    safe_route_failure,
)


def test_safe_route_failure_never_exposes_exception_detail(caplog):
    secret_detail = "mysql://root:super-secret@database/internal"
    token = bind_request_id("request-safe-123")

    try:
        with caplog.at_level(logging.ERROR):
            result = safe_route_failure(
                logging.getLogger("test.route"),
                RuntimeError(secret_detail),
                operation="load dashboard",
            )
    finally:
        reset_request_id(token)

    assert result.code == 500
    assert result.data is None
    assert result.msg == "系统繁忙，请稍后重试（请求编号：request-safe-123）"
    assert secret_detail not in result.msg
    assert secret_detail not in caplog.text
    assert "errorType=RuntimeError" in caplog.text
    assert "requestId=request-safe-123" in caplog.text
