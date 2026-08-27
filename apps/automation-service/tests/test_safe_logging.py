from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.safe_logging import (
    REDACTED,
    SafeLogFormatter,
    configure_safe_logging,
    sanitize_log_text,
)


def test_sanitize_log_text_redacts_common_credentials_and_database_passwords():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzZWNyZXQifQ.signature"
    raw = (
        "Authorization: Bearer bearer-secret "
        "Cookie='unb=12345; _m_h5_tk=cookie-token; sessionid=session-secret' "
        "password=hunter2 api_key='provider-secret' "
        f"jwt={jwt} mysql=mysql://service:database-secret@db:3306/app "
        "keyword=private-search title='customer listing'"
    )

    sanitized = sanitize_log_text(raw)

    for secret in (
        "bearer-secret",
        "12345",
        "cookie-token",
        "session-secret",
        "hunter2",
        "provider-secret",
        jwt,
        "database-secret",
        "private-search",
        "customer listing",
    ):
        assert secret not in sanitized
    assert REDACTED in sanitized
    assert "mysql://service:" in sanitized
    assert sanitize_log_text(sanitized) == sanitized


def test_safe_formatter_caps_a_formatted_message():
    formatter = SafeLogFormatter("%(message)s", max_message_chars=80)
    record = logging.LogRecord(
        name="privacy-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="prefix=%s",
        args=("x" * 500,),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert len(rendered) <= 80
    assert rendered.endswith("...[truncated]")


def test_safe_formatter_keeps_exception_frames_without_exception_message():
    formatter = SafeLogFormatter("%(levelname)s %(message)s")

    try:
        raise RuntimeError("password=frame-secret private customer message")
    except RuntimeError:
        record = logging.LogRecord(
            name="privacy-test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="operation failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    rendered = formatter.format(record)

    assert "RuntimeError" in rendered
    assert "test_safe_formatter_keeps_exception_frames_without_exception_message" in rendered
    assert "frame-secret" not in rendered
    assert "private customer message" not in rendered
    assert "raise RuntimeError" not in rendered


def test_safe_formatter_replaces_exception_arguments_with_their_type():
    formatter = SafeLogFormatter("%(message)s")
    secret_exception = ValueError("token=argument-secret")
    record = logging.LogRecord(
        name="privacy-test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="operation failed: %s",
        args=(secret_exception,),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert "argument-secret" not in rendered
    assert "<ValueError>" in rendered


def test_configure_safe_logging_protects_existing_named_handlers():
    logger = logging.getLogger("privacy-test-existing-handler")
    handler = logging.StreamHandler()
    original_handlers = list(logger.handlers)
    original_propagate = logger.propagate
    logger.handlers = [handler]
    logger.propagate = False
    try:
        configure_safe_logging()
        assert isinstance(handler.formatter, SafeLogFormatter)
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate


def test_sensitive_blob_fields_are_redacted_without_hiding_safe_metadata():
    formatter = SafeLogFormatter("%(message)s")
    record = logging.LogRecord(
        name="privacy-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            "accountId=42 errorType=RuntimeError dataKeys=['code'] "
            "title=%s count=3 payload=%s"
        ),
        args=("private listing", {"message": "private buyer text"}),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert "private listing" not in rendered
    assert "private buyer text" not in rendered
    assert "accountId=42" in rendered
    assert "errorType=RuntimeError" in rendered

    serialized_message = sanitize_log_text(
        '{"senderUserId":"external-user-42","msgContent":"buyer private text",'
        '"cookieStr":"cookie-secret","loginPassword":"password-secret",'
        '"buyerName":"private buyer","webhookUrl":"https://secret.example/hook"}'
    )
    assert "external-user-42" not in serialized_message
    assert "buyer private text" not in serialized_message
    assert "cookie-secret" not in serialized_message
    assert "password-secret" not in serialized_message
    assert "private buyer" not in serialized_message
    assert "secret.example" not in serialized_message


def test_sanitizer_handles_escaped_quotes_multiline_blobs_and_truncated_private_keys():
    quoted = sanitize_log_text("api_key='provider\\'quoted-secret'")
    multiline = sanitize_log_text(
        "payload=first line\nprivate second line\nthird line",
    )
    private_key = sanitize_log_text(
        # Split so the literal PEM markers do not appear verbatim in this
        # source file (which would self-trigger the embedded-secret preflight).
        "-----BEGIN" + " PRIVATE KEY" + "-----\n" + ("A" * 10_000),
        max_chars=512,
    )

    assert "quoted-secret" not in quoted
    assert "private second line" not in multiline
    assert "third line" not in multiline
    assert "BEGIN PRIVATE KEY" not in private_key
    assert REDACTED in quoted
    assert REDACTED in multiline
    assert REDACTED in private_key


def test_formatter_honors_tiny_and_zero_message_limits():
    record = logging.LogRecord(
        name="privacy-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="long message",
        args=(),
        exc_info=None,
    )

    assert len(SafeLogFormatter("%(message)s", max_message_chars=3).format(record)) <= 3
    assert SafeLogFormatter("%(message)s", max_message_chars=0).format(record) == ""


def test_stack_info_keeps_frame_metadata_without_paths_or_source_lines():
    record = logging.LogRecord(
        name="privacy-test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="operation failed",
        args=(),
        exc_info=None,
    )
    record.stack_info = (
        "Stack (most recent call last):\n"
        f'  File "{Path(__file__).resolve()}", line 1, in private_function\n'
        '    password = "source-line-secret"'
    )

    rendered = SafeLogFormatter("%(message)s").format(record)

    assert Path(__file__).name in rendered
    assert "private_function" in rendered
    assert str(Path(__file__).resolve().parent) not in rendered
    assert "source-line-secret" not in rendered


def test_entrypoints_install_safe_logging_and_high_risk_raw_logs_stay_removed():
    service_root = Path(__file__).resolve().parents[1]
    main_source = (service_root / "app" / "main.py").read_text(encoding="utf-8")
    worker_source = (service_root / "run-worker.py").read_text(encoding="utf-8")

    assert "configure_safe_logging()" in main_source
    assert "configure_safe_logging()" in worker_source
    assert main_source.index("configure_safe_logging()") < main_source.index("from .api.v1.api import api_router")
    assert worker_source.index("configure_safe_logging()") < worker_source.index("from app.worker import run_forever")

    forbidden_by_file = {
        "app/services/ws_client.py": (
            "WS 消息完整结构诊断",
            "WS 注册消息完整 JSON",
            "m_h5_tk前缀=%s",
            "raw_msg[:200]",
        ),
        "app/services/ws_protocol.py": (
            "WS 原始消息样本",
            "raw_data=%s",
            "reminderContent=%s",
            "senderUserId=%s msgContent=%s",
            "original_sId=%s",
            "recovered_content=%s",
        ),
        "app/services/ws_token.py": (
            "DB 中的 _m_h5_tk = %s",
            "token_prefix=%s",
            "完整响应",
        ),
        "app/api/v1/routes/auto_reply_scope.py": ("payload=%s",),
        "app/api/v1/routes/misc.py": ("keyword=%s", "unb=%s"),
        "app/services/xianyu_goods_sync.py": (
            "title=%s",
            "data=%s",
            "图片上传响应: %s",
            "未解析到 CDN URL, 响应=%s",
        ),
        "app/services/automation_runtime.py": (
            "AI判断通过: %s",
            "AI判断移除: %s -> %s",
            "AI筛选异常，保留商品: %s",
            "使用数据库中的常用地址: %s",
            "店铺=%s",
            "命中黑名单关键词 %s",
            "随机选中 %d 个: %s",
            "生图失败: %s",
            "DB-AI HTTP %d: %s",
        ),
    }
    for relative_path, forbidden_fragments in forbidden_by_file.items():
        source = (service_root / relative_path).read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in source, f"unsafe log fragment remains in {relative_path}: {fragment}"
