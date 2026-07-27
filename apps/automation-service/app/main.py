import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .core.safe_logging import configure_safe_logging
from .core.http_failures import bind_request_id, reset_request_id
from .core.failure_logging import log_service_failure

configure_safe_logging()

from .core.config import is_production_like, settings
from .core.database import engine, Base
from sqlalchemy import text
from .core.response import ResultObject
from .api.v1.api import api_router
from .services.ws_startup import auto_start_all, stop_all
from .services.upload_governance import probe_upload_storage, reconcile_storage_assets

if os.name == "nt":
    for stream_name in ("stdout", "stderr"):
        stream = getattr(__import__("sys"), stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass  # 已知非关键异常：Windows 下重配置标准流编码失败时保持默认编码即可

logger = logging.getLogger(__name__)
UPLOADS_ROOT = (Path(__file__).resolve().parent.parent / "uploads").resolve()
UPLOAD_IMAGES_ROOT = (UPLOADS_ROOT / "images").resolve()


async def _storage_reconcile_loop() -> None:
    while True:
        await asyncio.sleep(300)
        try:
            await reconcile_storage_assets(str(UPLOAD_IMAGES_ROOT))
        except Exception as exc:
            log_service_failure(logger, exc, operation="reconcile_upload_storage")


def runtime_compatibility_columns():
    return {
        "xianyu_chat_message": {
            "seller_external_uid": "VARCHAR(64) NULL COMMENT '卖家真实UID'",
            "message_uid": "VARCHAR(128) NULL COMMENT '稳定消息ID'",
            "receiver_user_id": "VARCHAR(64) NULL COMMENT '接收者ID'",
            "peer_external_uid": "VARCHAR(64) NULL COMMENT '买家UID'",
            "parse_status": "VARCHAR(16) DEFAULT 'ok' COMMENT '解析状态'",
            "raw_payload": "JSON NULL COMMENT '原始消息'",
            "read_status": "TINYINT DEFAULT 0 COMMENT '已读状态'",
        },
        "xianyu_conversation": {
            "seller_external_uid": "VARCHAR(64) NULL COMMENT '卖家真实UID'",
            "peer_external_uid": "VARCHAR(64) NULL COMMENT '买家UID'",
            "peer_key": "VARCHAR(200) NULL COMMENT '稳定对端标识'",
        },
        "xianyu_goods": {
            "image_urls": "JSON NULL COMMENT '图片URL列表'",
            "raw_payload": "JSON NULL COMMENT '原始商品数据快照'",
            # 售整自动上架功能字段（V1.20）
            "auto_relist_enabled": "INT NOT NULL DEFAULT 0 COMMENT '售整自动上架开关：0关 1开'",
            "next_relist_goods_id": "BIGINT NULL COMMENT '重发后的新商品记录ID'",
            "relist_source_goods_id": "BIGINT NULL COMMENT '本商品是从哪个原商品重发来的'",
            "last_relist_at": "DATETIME NULL COMMENT '上次重发时间'",
            "has_snapshot": "INT NOT NULL DEFAULT 0 COMMENT '是否有完整数据快照'",
            "original_quantity": "INT NULL COMMENT '商品原始库存'",
            # 鱼小铺商品编辑能力字段（V1.21）
            "can_edit": "TINYINT NOT NULL DEFAULT 1 COMMENT '鱼小铺商品是否支持编辑：1=可编辑，0=不可编辑'",
            "edit_note": "VARCHAR(500) NOT NULL DEFAULT '' COMMENT '鱼小铺商品不可编辑时的提示文案'",
        },
        "xianyu_goods_edit_snapshot": {
            "account_type": "VARCHAR(16) NOT NULL DEFAULT 'fish_shop' COMMENT '账号类型：fish_shop / normal'",
        },
    }


async def ensure_runtime_schema_compatibility():
    """补齐旧库缺失的消息字段。

    SQLAlchemy create_all 只会建新表，不会给旧表补字段。用户本地库如果停留在旧版本，
    xianyu_chat_message / xianyu_conversation 缺少 message_uid、parse_status、peer_key 等字段时，
    WS 消息会收到但无法入库或无法聚合到在线会话。这里做轻量幂等迁移。
    """
    if not str(engine.url).startswith("mysql"):
        return

    columns = runtime_compatibility_columns()

    async with engine.begin() as conn:
        for table_name, table_columns in columns.items():
            exists_result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :table_name"
            ), {"table_name": table_name})
            if not (exists_result.scalar() or 0):
                continue
            for column_name, definition in table_columns.items():
                col_result = await conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = :table_name AND column_name = :column_name"
                ), {"table_name": table_name, "column_name": column_name})
                if col_result.scalar() or 0:
                    continue
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
                logger.info("已补齐旧库字段 %s.%s", table_name, column_name)


async def validate_runtime_schema_compatibility():
    """Verify the ORM and compatibility schema without executing any DDL."""
    if not str(engine.url).startswith("mysql"):
        return

    missing: list[str] = []
    expected_tables = sorted(Base.metadata.tables)
    if not expected_tables:
        raise RuntimeError("database schema metadata is empty")
    compatibility = runtime_compatibility_columns()
    expected_columns = {
        table_name: {column.name for column in Base.metadata.tables[table_name].columns}
        for table_name in expected_tables
    }
    for table_name, table_columns in compatibility.items():
        expected_columns.setdefault(table_name, set()).update(table_columns)
    async with engine.connect() as conn:
        for table_name in expected_tables:
            result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :table_name"
            ), {"table_name": table_name})
            if not (result.scalar() or 0):
                missing.append(table_name)
        for table_name, table_columns in expected_columns.items():
            for column_name in sorted(table_columns):
                result = await conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = :table_name AND column_name = :column_name"
                ), {"table_name": table_name, "column_name": column_name})
                if not (result.scalar() or 0):
                    missing.append(f"{table_name}.{column_name}")
    if missing:
        raise RuntimeError(f"database schema is incomplete ({len(missing)} required object(s) missing)")



@asynccontextmanager
async def lifespan(app: FastAPI):
    app_env = str(getattr(settings, "app_env", "dev") or "dev").strip().lower()
    production_like = is_production_like(app_env)
    if production_like:
        if not getattr(settings, "internal_api_token", ""):
            raise RuntimeError("生产环境必须配置 INTERNAL_API_TOKEN")
        if getattr(settings, "admin_jwt_secret", "") == "please-change-this-admin-jwt-secret-at-least-32-chars":
            raise RuntimeError("生产环境必须配置非默认 ADMIN_JWT_SECRET")
        if getattr(settings, "cookie_crypto_secret", "") == "dev-only-cookie-crypto-secret-change-me-32-chars":
            raise RuntimeError("生产环境必须配置非默认 COOKIE_CRYPTO_SECRET")
    mutations_allowed = settings.runtime_schema_mutations_allowed
    logger.info("验证数据库结构，runtime_schema_mutations_allowed=%s", mutations_allowed)
    try:
        if mutations_allowed:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await ensure_runtime_schema_compatibility()
        else:
            await validate_runtime_schema_compatibility()
        logger.info("数据库结构验证完成")
    except Exception as e:
        log_service_failure(logger, e, operation="initialize_database")
        if production_like:
            raise RuntimeError("数据库初始化失败，生产环境拒绝启动") from None

    try:
        await probe_upload_storage(str(UPLOAD_IMAGES_ROOT))
    except Exception as e:
        log_service_failure(logger, e, operation="initialize_upload_storage")
        raise RuntimeError("上传存储不可用，服务拒绝启动") from None
    # reconcile_storage_assets 是崩溃恢复操作，失败不应阻止启动；
    # _storage_reconcile_loop 会每 5 分钟重试。
    try:
        await reconcile_storage_assets(str(UPLOAD_IMAGES_ROOT))
    except Exception as e:
        log_service_failure(logger, e, operation="initialize_upload_storage_reconcile")
    storage_reconcile_task = asyncio.create_task(_storage_reconcile_loop())
    
    # 启动 WebSocket 连接。
    # 即使启用了 Java 消息网关模式，真实闲鱼 WS 连接仍由 Python 维护；
    # Java 仅负责前端网关/转发，不能替代 Python 本地消息接入。
    ws_task = asyncio.create_task(auto_start_all())
    if getattr(settings, "use_java_message_gateway", True):
        logger.info("已启用 Java 消息网关模式，但 Python 本地 WS 仍会启动以维持真实消息接入")
    else:
        logger.info("Python 本地 WS 已启用")

    # 启动 Cookie/Token 自动刷新调度器
    # 策略：Cookie保活30分钟、_m_h5_tk 1.5-2.5小时、ws_token 10-14小时、账号间隔 2-5秒
    refresh_started = False
    try:
        from .services.cookie_token_refresher import start_dispatcher, stop_dispatcher
        await start_dispatcher()
        refresh_started = True
        logger.info("Cookie/Token 自动刷新调度器已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_cookie_token_dispatcher")

    # 启动定时任务 Worker（内嵌模式）
    # 将 worker 集成到 web 服务进程中，避免需要单独启动 run-worker.py
    # worker 每 60 秒扫描到期任务（auto_delivery / sync_orders / redelivery / polish_goods）
    worker_task = None
    try:
        from .worker import run_forever as worker_run_forever
        worker_interval = int(os.getenv("WORKER_INTERVAL_SECONDS", "60"))
        worker_task = asyncio.create_task(worker_run_forever(worker_interval))
        logger.info("定时任务 Worker 已内嵌启动，interval=%ss", worker_interval)
    except Exception as e:
        log_service_failure(logger, e, operation="start_inline_worker")

    # 启动 AI 计费待补扣定时循环
    # 当 Java 计费服务暂不可用时，自动回复的计费请求会被暂存到 pending_ai_billing 表，
    # 此循环每 60 秒扫描一次，在 Java 恢复后自动补扣，避免漏计费。
    pending_billing_task = None
    try:
        from .services.pending_billing import run_pending_billing_loop
        pending_billing_task = asyncio.create_task(run_pending_billing_loop())
        logger.info("AI 计费待补扣循环已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_pending_billing_loop")

    # 启动 Token 余额预警定时循环
    # 每 30 分钟扫描所有用户余额，对余额 < 用户配置阈值的用户触发预警通知，
    # 余额恢复到阈值以上时自动清除预警标记，允许下次再次触发。
    token_balance_warning_task = None
    try:
        from .services.token_balance_monitor import run_token_balance_warning_loop
        token_balance_warning_task = asyncio.create_task(run_token_balance_warning_loop())
        logger.info("Token 余额预警循环已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_token_balance_warning_loop")

    # 启动滑块求解优先级队列管理器
    # 替换原有的全局 asyncio.Lock 串行化方案，支持 SVIP>VIP>普通 优先级调度 + 2 并发 worker
    # 自动触发场景（WS Token 失败 / Cookie 保活失败）通过 enqueue_solve() 入队
    captcha_queue_started = False
    try:
        from .services.captcha_queue import get_queue_manager, stop_queue_manager
        await get_queue_manager()  # 惰性初始化 + 自动启动 worker
        captcha_queue_started = True
        logger.info("滑块求解优先级队列管理器已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_captcha_queue_manager")

    # 启动滑块求解记录僵尸状态清理循环
    # 每 5 分钟扫描 status=retrying 且 started_at 超过 15 分钟的记录，标记为 stale_terminated
    stale_cleanup_task = None
    try:
        from .services.captcha_solve_record import run_stale_cleanup_loop
        stale_cleanup_task = asyncio.create_task(run_stale_cleanup_loop())
        logger.info("滑块求解僵尸记录清理循环已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_stale_cleanup_loop")

    # 启动不活跃账号扫描循环
    # 每小时扫描 sys_user.last_login_time 超过 3 天的用户，
    # 将其闲鱼账号录入 xianyu_account_solve_exclusion 排除表，
    # 避免不活跃账号进入滑块求解队列占用资源。
    # 用户在前台登录时会自动从排除表移出（由 UserAuthService 登录钩子处理）。
    inactive_scanner_task = None
    try:
        from .services.inactive_account_scanner import run_inactive_account_scanner_loop
        inactive_scanner_task = asyncio.create_task(run_inactive_account_scanner_loop())
        logger.info("不活跃账号扫描循环已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_inactive_account_scanner")

    # 启动 WS 连接健康检查循环
    # 每 2 分钟扫描 cookie_status=1 但 ws_status=0 且无心跳超过 5 分钟的账号，
    # 触发滑块求解入队（trigger_scene="ws_health_check"）。
    # 修复场景：滑块求解成功但 WS 实际未连上，或 WS 运行中又遇到滑块验证，
    # 导致用户看到"WS 未连接"且无法接收最新消息。captcha_queue 的去重机制
    # 会自动防止重复入队。
    ws_health_check_task = None
    try:
        from .services.ws_health_check import run_ws_health_check_loop
        ws_health_check_task = asyncio.create_task(run_ws_health_check_loop())
        logger.info("WS 连接健康检查循环已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_ws_health_check")

    # 启动售整自动上架调度器
    # 每 3 分钟扫描所有 auto_relist_enabled=1 且 has_snapshot=1 且 status in (0,2) 且
    # next_relist_goods_id IS NULL 且 original_quantity=1 的商品，调用发布接口重发。
    # 重发后新商品继承 auto_relist_enabled=1，支持链式重发。
    relist_scheduler_started = False
    try:
        from .services.relist_scheduler import start_relist_scheduler, stop_relist_scheduler
        await start_relist_scheduler()
        relist_scheduler_started = True
        logger.info("售整自动上架调度器已启动")
    except Exception as e:
        log_service_failure(logger, e, operation="start_relist_scheduler")

    yield

    storage_reconcile_task.cancel()
    try:
        await storage_reconcile_task
    except asyncio.CancelledError:
        pass

    # 停止滑块求解僵尸记录清理循环
    if stale_cleanup_task is not None:
        stale_cleanup_task.cancel()
        try:
            await stale_cleanup_task
        except asyncio.CancelledError:
            pass

    # 停止不活跃账号扫描循环
    if inactive_scanner_task is not None:
        inactive_scanner_task.cancel()
        try:
            await inactive_scanner_task
        except asyncio.CancelledError:
            pass

    # 停止 WS 连接健康检查循环
    if ws_health_check_task is not None:
        ws_health_check_task.cancel()
        try:
            await ws_health_check_task
        except asyncio.CancelledError:
            pass

    # 停止滑块求解优先级队列管理器
    if captcha_queue_started:
        try:
            await stop_queue_manager()
        except Exception:
            logger.warning("关闭滑块求解优先级队列管理器失败，继续关闭流程")

    # 停止 AI 计费待补扣循环
    if pending_billing_task is not None:
        pending_billing_task.cancel()
        try:
            await pending_billing_task
        except asyncio.CancelledError:
            pass

    # 停止 Token 余额预警循环
    if token_balance_warning_task is not None:
        token_balance_warning_task.cancel()
        try:
            await token_balance_warning_task
        except asyncio.CancelledError:
            pass

    # 停止定时任务 Worker
    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    # 停止 Cookie/Token 刷新调度器
    if refresh_started:
        try:
            await stop_dispatcher()
        except Exception:
            logger.warning("关闭 Cookie/Token 刷新调度器失败，继续关闭流程")

    # 停止售整自动上架调度器
    if relist_scheduler_started:
        try:
            await stop_relist_scheduler()
        except Exception:
            logger.warning("关闭售整自动上架调度器失败，继续关闭流程")

    # 停止 WebSocket 连接
    if ws_task is not None:
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
        await stop_all()

    logger.info("关闭数据库连接...")
    try:
        await engine.dispose()
    except Exception:
        logger.warning("关闭数据库连接失败，继续完成关闭流程")
    logger.info("应用关闭完成")


app = FastAPI(
    title="闲鱼自动助手 API (Python 版本)",
    description="闲鱼自动发货、自动回复后端 API",
    version="1.0.0",
    lifespan=lifespan
)


def _normalize_request_id(value: str | None) -> str:
    if not value:
        return uuid.uuid4().hex
    value = value.strip()
    if not value or len(value) > 128:
        return uuid.uuid4().hex
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
    if any(ch not in allowed for ch in value):
        return uuid.uuid4().hex
    return value


@app.middleware("http")
async def request_trace_middleware(request: Request, call_next):
    request_id = _normalize_request_id(request.headers.get("X-Request-Id"))
    request.state.request_id = request_id
    request_id_token = bind_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    finally:
        try:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            # response 可能由异常处理器生成；Starlette 会在 call_next 后统一回写 header。
            try:
                response.headers["X-Request-Id"] = request_id  # type: ignore[name-defined]
            except Exception:
                pass  # 已知非关键异常：异常处理器生成的 response 可能无 headers 属性
            response_status = getattr(locals().get("response", None), "status_code", "unknown")
            logger.info(
                "request_id=%s method=%s path=%s status=%s elapsed_ms=%s client=%s",
                request_id,
                request.method,
                request.url.path,
                response_status,
                elapsed_ms,
                request.client.host if request.client else "unknown",
            )
        finally:
            reset_request_id(request_id_token)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        response = JSONResponse(
            status_code=401,
            content=ResultObject(code=401, msg="暂未登录或token已经过期", data=None).model_dump()
        )
    else:
        response = JSONResponse(
            status_code=exc.status_code,
            content=ResultObject(code=exc.status_code, msg=exc.detail, data=None).model_dump()
        )
    response.headers["X-Request-Id"] = getattr(request.state, "request_id", uuid.uuid4().hex)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    response = JSONResponse(
        status_code=400,
        content=ResultObject(code=400, msg="参数验证失败", data={"errors": exc.errors()}).model_dump()
    )
    response.headers["X-Request-Id"] = getattr(request.state, "request_id", uuid.uuid4().hex)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_service_failure(logger, exc, operation="global_exception_handler")
    response = JSONResponse(
        status_code=500,
        content=ResultObject(code=500, msg="系统繁忙，请稍后重试", data=None).model_dump()
    )
    response.headers["X-Request-Id"] = getattr(request.state, "request_id", uuid.uuid4().hex)
    return response


cors_allowed_origins = [
    origin.strip()
    for origin in (getattr(settings, "cors_allowed_origins", "") or "").split(",")
    if origin.strip()
]

if cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id", "X-Internal-Token", "X-Internal-Tenant-Id"],
    )

app.include_router(api_router, prefix="/api")

# The worker and publisher share this directory with core-api, but automation
# never serves it directly. All browser reads must cross MediaAssetController,
# which checks the media cookie, tenant, active DB record, size and SHA-256.
UPLOAD_IMAGES_ROOT.mkdir(parents=True, exist_ok=True)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "automation-service",
        "check": "liveness",
        "message": "Python backend is running",
    }


@app.get("/ready")
async def readiness_check():
    database_ok = False
    upload_storage_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:
        log_service_failure(
            logger, exc, operation="readiness_database_check", level=logging.WARNING,
        )
    try:
        await probe_upload_storage(str(UPLOAD_IMAGES_ROOT))
        upload_storage_ok = True
    except Exception as exc:
        log_service_failure(
            logger, exc, operation="readiness_upload_storage_check", level=logging.WARNING,
        )
    if not database_ok or not upload_storage_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "service": "automation-service",
                "dependencies": {
                    "database": database_ok,
                    "uploadStorage": upload_storage_ok,
                },
            },
        )
    return {
        "status": "ready",
        "service": "automation-service",
        "dependencies": {"database": True, "uploadStorage": True},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.server_port,
        reload=True
    )
