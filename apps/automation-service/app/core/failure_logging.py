"""Safe exception metadata logging for service and background-task boundaries."""

from __future__ import annotations

import logging
from typing import Any

from .http_failures import get_request_id


_ALLOWED_EVENT_ERROR_TYPES = frozenset({"ProviderRejected"})


def log_service_failure(
    logger: logging.Logger,
    error: Any,
    *,
    operation: str,
    tenant_id: Any = None,
    account_id: Any = None,
    level: int = logging.ERROR,
    error_type: str | None = None,
) -> None:
    """Log only bounded metadata; never interpolate an exception or provider value."""

    resolved_error_type = (
        error_type
        if error_type in _ALLOWED_EVENT_ERROR_TYPES
        else type(error).__name__
    )
    logger.log(
        level,
        "serviceFailure operation=%s errorType=%s requestId=%s tenantId=%s accountId=%s",
        operation,
        resolved_error_type,
        get_request_id() or "-",
        tenant_id if tenant_id is not None else "-",
        account_id if account_id is not None else "-",
    )


__all__ = ["log_service_failure"]
