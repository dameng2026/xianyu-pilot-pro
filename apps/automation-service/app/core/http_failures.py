"""Safe, stable error responses for HTTP route boundaries."""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token

from .response import ResultObject


INTERNAL_ERROR_CODE = 500
INTERNAL_ERROR_MESSAGE = "系统繁忙，请稍后重试"

_request_id: ContextVar[str | None] = ContextVar("http_request_id", default=None)


class PublicRouteValidationError(ValueError):
    """A validation error whose explicitly authored message is client-safe."""

    def __init__(self, public_message: str):
        self.public_message = public_message
        super().__init__(public_message)


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind a validated request ID for route helpers in the current task."""

    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request context after a request completes."""

    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


def log_route_failure(
    logger: logging.Logger,
    exc: BaseException,
    *,
    operation: str,
) -> None:
    """Log only non-sensitive exception metadata for a route failure."""

    logger.error(
        "routeFailure operation=%s errorType=%s requestId=%s",
        operation,
        type(exc).__name__,
        get_request_id() or "-",
    )


def safe_route_failure(
    logger: logging.Logger,
    exc: BaseException,
    *,
    operation: str,
    user_message: str = INTERNAL_ERROR_MESSAGE,
    code: int = INTERNAL_ERROR_CODE,
) -> ResultObject:
    """Return a generic failure while logging only safe diagnostic metadata.

    Exception values can contain SQL, credentials, provider payloads, local paths,
    or user content.  They must never be interpolated into either the response or
    the log record at this HTTP boundary.
    """

    request_id = get_request_id()
    log_route_failure(logger, exc, operation=operation)
    message = user_message
    if request_id:
        message = f"{message}（请求编号：{request_id}）"
    return ResultObject.failed(message, code=code)


__all__ = [
    "INTERNAL_ERROR_CODE",
    "INTERNAL_ERROR_MESSAGE",
    "PublicRouteValidationError",
    "bind_request_id",
    "get_request_id",
    "log_route_failure",
    "reset_request_id",
    "safe_route_failure",
]
