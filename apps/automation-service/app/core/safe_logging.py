"""Process-wide logging safeguards.

The service talks to browser sessions, payment-adjacent APIs and AI providers, so
an exception or a debug statement can easily contain a reusable credential.  All
production entry points install the formatter in this module before importing
the rest of the application.
"""

from __future__ import annotations

import copy
import logging
import os
import re
import traceback
from collections.abc import Mapping
from typing import Any


REDACTED = "[REDACTED]"
DEFAULT_MAX_MESSAGE_CHARS = 4096
DEFAULT_MAX_TRACE_FRAMES = 32
_TRUNCATION_MARKER = "...[truncated]"
_DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

_SENSITIVE_KEY = r"(?:" + "|".join(
    (
        r"authorization",
        r"proxy[-_]?authorization",
        r"cookie(?:[-_]?(?:str|string|header|value|text))?",
        r"set[-_]?cookie",
        r"encrypted[-_]?cookie",
        r"encrypted[-_]?token",
        r"encrypted[-_]?(?:login|proxy)?[-_]?password",
        r"x[-_]?internal[-_]?token",
        r"internal[-_]?api[-_]?token",
        r"tenant[-_]?access[-_]?token",
        r"verification[-_]?token",
        r"access[-_]?token",
        r"refresh[-_]?token",
        r"id[-_]?token",
        r"ws[-_]?token",
        r"token[-_]?prefix",
        r"token",
        r"jwt",
        r"password",
        r"login[-_]?password",
        r"proxy[-_]?password",
        r"passwd",
        r"pwd",
        r"secret",
        r"client[-_]?secret",
        r"app[-_]?secret",
        r"api[-_]?key",
        r"apikey",
        r"credential",
        r"signature",
        r"sign",
        r"session(?:[-_]?id)?",
        r"_m_h5_tk(?:_enc)?",
        r"m[-_]?h5[-_]?tk(?:[-_]?enc)?",
        r"_tb_token_?",
        r"x5sec",
        r"cookie2",
        r"unb",
        # Free-form customer or upstream content.  These keys are safe to log
        # as presence/length/count metadata, never as their raw values.
        r"payload",
        r"raw(?:[-_]?payload)?",
        r"request(?:[-_]?body)?",
        r"response(?:[-_]?body)?",
        r"body",
        r"prompt",
        r"query",
        r"keyword",
        r"title",
        r"content",
        r"msg[-_]?content",
        r"message[-_]?content",
        r"reminder[-_]?content",
        r"reminder[-_]?title",
        r"topic[-_]?title",
        r"message",
        r"msg",
        r"text",
        r"username",
        r"login[-_]?username",
        r"proxy[-_]?username",
        r"nickname",
        r"account[-_]?(?:name|nickname)",
        r"(?:sender|receiver|peer|buyer|seller)(?:[-_]?user)?[-_]?(?:name|nick)",
        r"sender(?:[-_]?user)?[-_]?id",
        r"receiver(?:[-_]?user)?[-_]?id",
        r"peer(?:[-_]?(?:user|external))?[-_]?(?:id|uid)",
        r"buyer[-_]?(?:id|uid)",
        r"seller[-_]?(?:id|uid)",
        r"external[-_]?uid",
        r"s[-_]?id",
        r"cid",
        r"pnm[-_]?id",
        r"message[-_]?id",
        r"to[-_]?id",
        r"from[-_]?id",
        r"device[-_]?id",
        r"order[-_]?id",
        r"external[-_]?order[-_]?id",
        r"order",
        r"error",
        r"err",
        r"exception",
        r"detail",
        r"reason",
        r"url",
        r"uri",
        r"base[-_]?url",
        r"shop[-_]?url",
        r"image[-_]?url",
        r"cdn[-_]?url",
        r"filename",
        r"file",
        r"path",
        r"headers?",
        r"config",
        r"data",
        r"result",
        r"ret",
        r"keywords?",
        r"titles?",
        r"reasons?",
        r"hits",
        r"address",
        r"shop",
        r"webhook[-_]?url",
        r"encrypt[-_]?key",
        r"phone",
        r"mobile",
        r"email",
        r"id[-_]?card",
        r"real[-_]?name",
        r"kami[-_]?content",
        r"delivery[-_]?content",
        r"关键词",
        r"标题",
        r"正文",
        r"内容",
        r"消息",
        r"地址",
        r"用户名",
        r"昵称",
    )
) + r")"

_QUOTED_VALUE = re.compile(
    rf"(?P<prefix>(?<![\w-])(?P<key_quote>[\"']?){_SENSITIVE_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?P<value_quote>[\"'])"
    rf"(?P<value>(?:\\.|(?!(?P=value_quote)).)*)"
    rf"(?P=value_quote)",
    re.IGNORECASE | re.DOTALL,
)
_UNTERMINATED_QUOTED_VALUE = re.compile(
    rf"(?P<prefix>(?<![\w-])(?P<key_quote>[\"']?){_SENSITIVE_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?P<value_quote>[\"'])"
    rf"(?P<value>(?:\\.|(?!(?P=value_quote)).)*)\Z",
    re.IGNORECASE | re.DOTALL,
)
_PLAIN_BLOB_VALUE = re.compile(
    r"(?P<prefix>(?<![\w-])(?:cookie|set[-_]?cookie|payload|raw(?:[-_]?payload)?|"
    r"request(?:[-_]?body)?|response(?:[-_]?body)?|body|prompt|query|keyword|"
    r"title|content|message|msg|text|error|err|exception|detail|reason|url|uri|"
    r"base[-_]?url|shop[-_]?url|image[-_]?url|cdn[-_]?url|filename|file|path|"
    r"headers?|config|data|result|ret|order|keywords?|titles?|reasons?|hits|address|shop|"
    r"webhook[-_]?url|phone|mobile|email|id[-_]?card|real[-_]?name|"
    r"kami[-_]?content|delivery[-_]?content|"
    r"关键词|标题|正文|内容|消息|地址|店铺|响应|请求|结果|详情)"
    r"\s*[:=]\s*)"
    r"(?![\"'])(?P<value>.*)\Z",
    re.IGNORECASE | re.DOTALL,
)
_UNQUOTED_VALUE = re.compile(
    rf"(?P<prefix>(?<![\w-])(?P<key_quote>[\"']?){_SENSITIVE_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?![\"']|\[REDACTED\])"
    rf"(?P<value>(?:(?:bearer|basic)\s+)?"
    rf"[^\s,;}}\]\r\n]+)",
    re.IGNORECASE,
)
_AUTH_SCHEME = re.compile(
    r"\b(?P<scheme>bearer|basic)\s+[A-Za-z0-9._~+/=-]+",
    re.IGNORECASE,
)
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"\.[A-Za-z0-9_-]{4,}(?![A-Za-z0-9_-])"
)
_COMMON_API_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?:sk|xox[baprs]|gh[pousr])-[A-Za-z0-9_-]{12,}"
)
_PASSWORD_IN_URL = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9+.-]*://[^\s:/@]+:)"
    r"(?P<password>[^\s/@]+)(?P<suffix>@)",
    re.IGNORECASE,
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?"
    r"(?:-----END(?: [A-Z0-9]+)? PRIVATE KEY-----|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _truncate(value: str, max_chars: int) -> str:
    limit = max(int(max_chars), 0)
    if len(value) <= limit:
        return value
    if not limit:
        return ""
    marker = _TRUNCATION_MARKER[:limit]
    return value[: limit - len(marker)] + marker


def sanitize_log_text(value: Any, *, max_chars: int = DEFAULT_MAX_MESSAGE_CHARS) -> str:
    """Return a bounded, credential-redacted representation suitable for logs."""
    try:
        text = str(value)
    except Exception:
        text = "<unprintable>"

    # Bound regex work as well as final output.  Keeping twice the output limit
    # leaves enough room for redaction to shorten serialized headers first.
    work_limit = max(int(max_chars) * 2, 0)
    text = text[:work_limit]
    text = _PRIVATE_KEY.sub(f"<private-key>{REDACTED}</private-key>", text)
    text = _PASSWORD_IN_URL.sub(
        lambda match: f"{match.group('prefix')}{REDACTED}{match.group('suffix')}",
        text,
    )
    text = _QUOTED_VALUE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('value_quote')}"
            f"{REDACTED}{match.group('value_quote')}"
        ),
        text,
    )
    text = _UNTERMINATED_QUOTED_VALUE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('value_quote')}"
            f"{REDACTED}{match.group('value_quote')}"
        ),
        text,
    )
    text = _PLAIN_BLOB_VALUE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED}",
        text,
    )
    text = _UNQUOTED_VALUE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED}",
        text,
    )
    text = _AUTH_SCHEME.sub(
        lambda match: f"{match.group('scheme')} {REDACTED}",
        text,
    )
    text = _JWT.sub(REDACTED, text)
    text = _COMMON_API_TOKEN.sub(REDACTED, text)
    return _truncate(text, max_chars)


def _replace_exception_values(value: Any) -> Any:
    """Keep %-formatting useful without calling ``str(exception)``."""
    if isinstance(value, BaseException):
        return f"<{type(value).__name__}>"
    if isinstance(value, tuple):
        return tuple(
            f"<{type(item).__name__}>" if isinstance(item, BaseException) else item
            for item in value
        )
    if isinstance(value, Mapping):
        return {
            key: f"<{type(item).__name__}>" if isinstance(item, BaseException) else item
            for key, item in value.items()
        }
    return value


class SafeLogFormatter(logging.Formatter):
    """Formatter that redacts messages and omits exception values/source lines."""

    def __init__(
        self,
        fmt: str = _DEFAULT_FORMAT,
        datefmt: str | None = None,
        style: str = "%",
        *,
        max_message_chars: int = DEFAULT_MAX_MESSAGE_CHARS,
        max_trace_frames: int = DEFAULT_MAX_TRACE_FRAMES,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self.max_message_chars = max_message_chars
        self.max_trace_frames = max(int(max_trace_frames), 0)

    def format(self, record: logging.LogRecord) -> str:
        safe_record = copy.copy(record)
        safe_record.args = _replace_exception_values(record.args)
        safe_record.exc_text = None
        try:
            message = safe_record.getMessage()
        except Exception:
            message = "<unformattable-log-message>"
        safe_record.msg = sanitize_log_text(
            message,
            max_chars=self.max_message_chars,
        )
        safe_record.args = ()
        return super().format(safe_record)

    def formatException(self, exc_info: tuple[type[BaseException], BaseException, Any]) -> str:
        exc_type, _exc_value, exc_traceback = exc_info
        frames = traceback.extract_tb(exc_traceback)
        if len(frames) > self.max_trace_frames:
            omitted = len(frames) - self.max_trace_frames
            frames = frames[-self.max_trace_frames :]
        else:
            omitted = 0

        lines = ["Traceback (frames only; exception message suppressed):"]
        if omitted:
            lines.append(f"  ... {omitted} earlier frame(s) omitted")
        for frame in frames:
            # Source lines and absolute directories can themselves contain
            # credentials or workstation identities, so retain only the
            # diagnostic filename, line number and function name.
            filename = os.path.basename(frame.filename) or "<unknown>"
            lines.append(
                f'  File "{sanitize_log_text(filename, max_chars=256)}", '
                f"line {frame.lineno}, in "
                f"{sanitize_log_text(frame.name, max_chars=256)}"
            )
        type_name = getattr(exc_type, "__name__", "Exception")
        lines.append(sanitize_log_text(type_name, max_chars=256))
        return _truncate("\n".join(lines), self.max_message_chars)

    def formatStack(self, stack_info: str) -> str:
        # logging's default stack text includes source-code lines.  Keep only
        # frame descriptors so literals and user payloads cannot be echoed.
        frames: list[str] = []
        for line in str(stack_info).splitlines():
            match = re.match(
                r'^\s*File "(?P<filename>[^"]+)", line (?P<line>\d+), in (?P<name>.+)$',
                line,
            )
            if not match:
                continue
            frames.append(
                f'  File "{os.path.basename(match.group("filename"))}", '
                f'line {match.group("line")}, in '
                f'{sanitize_log_text(match.group("name"), max_chars=256)}'
            )
        if not frames:
            return "Stack (frame details unavailable)"
        return _truncate(
            "Stack (frames only):\n" + "\n".join(frames),
            self.max_message_chars,
        )


def _all_existing_handlers() -> list[logging.Handler]:
    handlers: list[logging.Handler] = []
    seen: set[int] = set()
    loggers: list[logging.Logger] = [logging.getLogger()]
    loggers.extend(
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    )
    for logger in loggers:
        for handler in logger.handlers:
            identity = id(handler)
            if identity not in seen:
                handlers.append(handler)
                seen.add(identity)
    return handlers


def configure_safe_logging(*, level: int = logging.INFO) -> None:
    """Install safe formatting on root and already-created named handlers.

    This is intentionally idempotent.  Calling it from ``app.main`` after
    Uvicorn configures its loggers also protects Uvicorn's handlers.
    """
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in _all_existing_handlers():
        handler.setFormatter(SafeLogFormatter())


__all__ = [
    "DEFAULT_MAX_MESSAGE_CHARS",
    "REDACTED",
    "SafeLogFormatter",
    "configure_safe_logging",
    "sanitize_log_text",
]
