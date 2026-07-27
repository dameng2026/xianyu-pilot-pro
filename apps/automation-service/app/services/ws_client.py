"""
闲鱼 WebSocket 连接管理器。

管理到 wss://wss-goofish.dingtalk.com/ 的 WebSocket 连接生命周期：
- 连接建立
- /reg 注册
- /r/SyncStatus/ackDiff 同步
- 消息接收与 ACK
- 15秒心跳保活
- 断线自动重连
"""
import asyncio
import json
import logging
import ssl
import threading
import time
from typing import Any, Callable, Optional

import websocket

from .ws_token import get_ws_token, get_ws_token_with_refreshed_m_h5_tk, extract_m_h5_tk_from_cookie
from ..core.cookie_crypto import encrypt_cookie_for_storage
from ..core.failure_logging import log_service_failure
from .ws_protocol import (
    _normalize_goofish_target,
    build_reg_message,
    build_sync_message,
    build_ack_message,
    build_heartbeat_message,
    build_send_message,
    build_send_image_message,
    generate_mid,
    parse_sync_package,
    parse_send_response,
    normalize_peer_name,
)
from .ws_sse import broadcaster

logger = logging.getLogger(__name__)

WS_URL = "wss://wss-goofish.dingtalk.com/"
HEARTBEAT_INTERVAL = 15  # 心跳间隔（秒）
RECONNECT_DELAY_INITIAL = 5       # 初始重连延迟（秒）
RECONNECT_DELAY_MAX = 300         # 最大重连延迟（5 分钟，避免长时间失联）
RECONNECT_BACKOFF_FACTOR = 2      # 退避倍数
MESSAGE_TIMEOUT = 10  # 发送消息超时（秒）

# ackDiff 短轮询间隔（秒）：服务端无新消息时，客户端等待多长时间再发下一轮 ackDiff。
# 闲鱼 IM 的 ackDiff 是短轮询模式——客户端发请求，服务端立即返回（有消息就带消息，没消息就返回空）。
# 空响应后必须等待再发下一轮，否则会形成每秒几十次的疯狂循环，
# 触发服务端限流并消耗大量 CPU。
ACKDIFF_POLL_INTERVAL = 3.0


IMAGE_MESSAGE_ACK_TIMEOUT = 2  # Image ACK can be missing; avoid false failure.


# ============================================================
# 发送层去重：防止短时间内向同一会话重复发送相同内容
# ============================================================
# 当多个并发任务（自动发货竞态、Java 桥接重试、手动触发）调用 send_text_message
# 发送完全相同的内容时，只实际发送第一条，其余直接返回成功，避免触发闲鱼滑块验证。
_TEXT_MESSAGE_ACK_TIMEOUT = 6  # 文本消息 ACK 超时（秒）；IMAGE_MESSAGE_ACK_TIMEOUT=2 过短易误判失败触发重试
_RECENT_SEND_DEDUP_TTL = 60  # 最近发送缓存保留时长（秒）
_RECENT_SEND_DEDUP_MAX = 500  # 最近发送缓存最大条数（防止内存增长）
_recent_text_sends: dict[str, dict[str, Any]] = {}  # key=f"{account_id}:{cid}:{to_id}:{text}"
_RECENT_TEXT_SENDS_LOCK = None  # lazy asyncio.Lock for _recent_text_sends dict access


def _get_recent_text_sends_lock() -> asyncio.Lock:
    """惰性初始化 _recent_text_sends 的访问锁，避免并发写入去重缓存导致数据竞争。

    返回模块级单例 asyncio.Lock，供 send_text_message 中
    async with _get_recent_text_sends_lock() 使用。必须是同步函数，否则
    `async with async_func():` 会拿到 coroutine 而非 Lock，导致 TypeError。
    """
    global _RECENT_TEXT_SENDS_LOCK
    if _RECENT_TEXT_SENDS_LOCK is None:
        _RECENT_TEXT_SENDS_LOCK = asyncio.Lock()
    return _RECENT_TEXT_SENDS_LOCK


def _cleanup_recent_text_sends(now: float) -> None:
    """清理过期的发送去重缓存条目。"""
    expired = [k for k, v in _recent_text_sends.items() if (now - v.get("ts", 0)) > _RECENT_SEND_DEDUP_TTL]
    for k in expired:
        _recent_text_sends.pop(k, None)


# 注：自动滑块求解去重和串行化已迁移至 captcha_queue.py 的优先级队列管理器，
# 由 CaptchaQueueManager 统一管理去重（30 分钟同账号冷却）和并发（2 worker）。
# 原 _AUTO_SOLVE_LAST_TS / _AUTO_SOLVE_GLOBAL_LOCK 已移除。


async def _lookup_account_name_safe(tenant_id: int, account_id: int) -> str:
    """查询账号昵称，失败时回退为账号 ID 字符串。供通知文案使用。"""
    try:
        from ..core.database import async_session
        from sqlalchemy import text as _sa_text
        async with async_session() as db:
            row = (await db.execute(
                _sa_text(
                    "SELECT nickname FROM xianyu_account "
                    "WHERE id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
            if row and row.get("nickname"):
                return str(row["nickname"])
    except Exception as exc:
        log_service_failure(
            logger, exc, operation="lookup_ws_account_name",
            tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
        )
    return str(account_id)


class _ThreadedWebSocketAdapter:
    """基于 websocket-client 的最小异步适配层。"""

    def __init__(self, account_id: int, tenant_id: int, url: str, headers: dict[str, str]):
        self.account_id = account_id
        self.tenant_id = tenant_id
        self.url = url
        self.headers = headers
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_app: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._recv_queue: Optional[asyncio.Queue[str]] = None
        self._open_event: Optional[asyncio.Event] = None
        self._close_event: Optional[asyncio.Event] = None
        self._connected = False
        self._close_code: Optional[int] = None
        self._close_reason: Optional[str] = None
        self._connect_error: Optional[Exception] = None

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, timeout: float = 10.0):
        self._loop = asyncio.get_running_loop()
        self._recv_queue = asyncio.Queue()
        self._open_event = asyncio.Event()
        self._close_event = asyncio.Event()
        self._connected = False
        self._close_code = None
        self._close_reason = None
        self._connect_error = None

        header_lines = [f"{key}: {value}" for key, value in self.headers.items()]
        self._ws_app = websocket.WebSocketApp(
            self.url,
            header=header_lines,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(
            target=self._run_forever,
            name=f"xianyu-ws-{self.account_id}",
            daemon=True,
        )
        self._thread.start()

        try:
            await asyncio.wait_for(self._open_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            await self.close()
            raise TimeoutError(f"WS 连接超时 accountId={self.account_id}")

        if self._connect_error and not self._connected:
            raise self._connect_error

    def _run_forever(self):
        try:
            assert self._ws_app is not None
            self._ws_app.run_forever(
                ping_interval=0,
                ping_timeout=None,
                skip_utf8_validation=False,
                sslopt={"cert_reqs": ssl.CERT_REQUIRED},
                origin="https://www.goofish.com",
                host="wss-goofish.dingtalk.com",
                suppress_origin=False,
            )
        except Exception as exc:
            self._connect_error = exc
            self._notify_open()
            self._notify_close()

    def _on_open(self, _ws_app):
        self._connected = True
        logger.info("WS 底层连接已打开 accountId=%d", self.account_id)
        self._notify_open()

    def _on_message(self, _ws_app, message):
        if self._loop and self._recv_queue:
            asyncio.run_coroutine_threadsafe(self._recv_queue.put(message), self._loop)

    def _on_error(self, _ws_app, error):
        if not self._connected and self._connect_error is None:
            self._connect_error = error if isinstance(error, Exception) else ConnectionError("WebSocket 连接失败")
            self._notify_open()
        log_service_failure(
            logger, error, operation="websocket_transport_error",
            tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
        )

    def _on_close(self, _ws_app, close_status_code, close_msg):
        self._connected = False
        self._close_code = close_status_code
        self._close_reason = ""
        logger.info(
            "WS 底层连接已关闭 accountId=%d code=%s",
            self.account_id,
            close_status_code,
        )
        # 必须在 recv_queue 中放入 None，否则 _message_loop 会永久阻塞在
        # recv_queue.get() 上，_connect 的 finally 块无法执行，_connected
        # 保持 True，后续消息发送到死连接上导致超时。
        if self._loop and self._recv_queue:
            asyncio.run_coroutine_threadsafe(self._recv_queue.put(None), self._loop)
        self._notify_close()
        self._notify_open()
        if self._loop and self._recv_queue:
            asyncio.run_coroutine_threadsafe(self._recv_queue.put(None), self._loop)
        # 账号掉线通知（失败不影响主流程；仅在非主动关闭时通知，避免正常重连刷屏）
        if self._loop and close_status_code not in (1000, 1001, None):
            try:
                from .notify_dispatcher import notify_account_offline
                reason = f"code={close_status_code}"
                asyncio.run_coroutine_threadsafe(
                    notify_account_offline(self.tenant_id, self.account_id, reason),
                    self._loop,
                )
            except Exception as exc:
                log_service_failure(
                    logger, exc, operation="notify_ws_account_offline",
                    tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
                )

    def _notify_open(self):
        if self._loop and self._open_event:
            self._loop.call_soon_threadsafe(self._open_event.set)

    def _notify_close(self):
        if self._loop and self._close_event:
            self._loop.call_soon_threadsafe(self._close_event.set)

    async def send(self, data: str):
        if not self._ws_app or not self._connected:
            raise RuntimeError("WebSocket 未连接")
        await asyncio.to_thread(self._ws_app.send, data)

    async def recv(self) -> str:
        if not self._recv_queue:
            raise RuntimeError("WebSocket 接收队列未初始化")
        message = await self._recv_queue.get()
        if message is None:
            raise ConnectionError(
                f"WebSocket 连接已关闭 code={self._close_code} reason={self._close_reason}"
            )
        return message

    async def close(self):
        ws_app = self._ws_app
        thread = self._thread
        self._connected = False

        if ws_app:
            await asyncio.to_thread(ws_app.close)

        if self._close_event:
            try:
                await asyncio.wait_for(self._close_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

        if thread and thread.is_alive():
            await asyncio.to_thread(thread.join, 5)

        self._ws_app = None
        self._thread = None


class XianyuWebSocketClient:
    """闲鱼 WebSocket 客户端。

    每个账号一个实例，管理独立的 WebSocket 连接。
    """

    def __init__(
        self,
        account_id: int,
        tenant_id: int,
        cookie_str: str,
        m_h5_tk: str,
        unb: str,
        on_message_callback: Optional[Callable] = None,
    ):
        self.account_id = account_id
        self.tenant_id = tenant_id
        self.cookie_str = cookie_str
        self.m_h5_tk = m_h5_tk
        self.unb = unb

        # 连接状态
        self._ws: Optional[_ThreadedWebSocketAdapter] = None
        self._running = False
        self._connected = False
        self.phase = "stopped"
        self._sid: Optional[str] = None  # 注册后获取的 sid
        self._access_token: Optional[str] = None
        self._tasks: list[asyncio.Task] = []

        # 发送消息的 Future 映射 (uuid -> asyncio.Future)
        self._send_futures: dict[str, asyncio.Future] = {}

        # 同步状态
        self._sync_pts = 0  # 当前同步基点时间戳
        self._sync_high_pts = 0  # 当前同步高点水印
        # 当前等待响应的 ackDiff 请求 mid，用于识别服务端的空响应（无 lwp，仅 code+headers）。
        # 服务端在 ackDiff 长轮询超时（无新消息）时返回这种格式，客户端必须识别并发起下一轮。
        self._sync_pending_mid: Optional[str] = None

        # 外部回调（如消息存储）
        self.on_message_callback = on_message_callback

        # 最近一次收到服务端消息的时间戳（用于检测连接是否静默断开）
        self._last_recv_time: float = time.time()

        # 诊断状态：前端连接管理页可据此区分"已提交但未连接"、
        # “Token/Cookie 异常”、“已注册并同步”等状态。
        self.phase = "created"
        self.last_error = ""

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def device_id(self) -> str:
        """生成 /reg 使用的 did。

        必须与 accessToken 获取阶段的 deviceId 保持一致，统一使用
        _m_h5_tk 前半段 token，避免服务端因设备标识不一致而丢弃注册。
        """
        if self.m_h5_tk:
            token_device_id = self.m_h5_tk.split("_")[0] if "_" in self.m_h5_tk else self.m_h5_tk
            if token_device_id:
                return token_device_id
        logger.error("device_id: m_h5_tk 为空，无法生成 did accountId=%d", self.account_id)
        return ""

    async def start(self):
        """启动 WebSocket 连接。"""
        if self._running:
            logger.warning("WS 客户端 accountId=%d 已在运行", self.account_id)
            return

        self._running = True
        self.phase = "starting"
        self.last_error = ""
        logger.info("WS 客户端启动 accountId=%d", self.account_id)

        # 启动连接任务
        task = asyncio.create_task(self._connect_loop())
        self._tasks.append(task)

    async def stop(self):
        """停止 WebSocket 连接。"""
        self._running = False
        self._connected = False
        self.phase = "stopped"

        # 关闭 WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                logger.debug("stop 时关闭 WS 连接失败（可忽略）accountId=%d", self.account_id)
            self._ws = None

        # 取消所有任务
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        # 清理发送 Future
        for fut in self._send_futures.values():
            if not fut.done():
                fut.set_exception(asyncio.CancelledError())
        self._send_futures.clear()

        logger.info("WS 客户端停止 accountId=%d", self.account_id)

        # 关键修复：主动停止时必须持久化 ws_status=0，否则 DB 中 ws_status
        # 仍保持旧值 1，前端显示"WS 已连接"但实际收不到消息。
        # 场景：滑块求解成功但 Cookie Session 过期时，captcha_solver 调用
        # stop_client() 断开 WS，若不写 ws_status=0，用户会看到 WS 状态
        # 异常显示为连接、但实际无法接收最新消息。
        # 注意：若紧接着 start_client()，连接成功后 _persist_ws_online()
        # 会覆盖为 1，所以这里设 0 是安全的。
        await self._persist_ws_offline("stopped: 客户端主动停止")

    async def send_text_message(
        self, cid: str, to_id: str, text: str, persist: bool = False,
        is_auto_reply: int = 0,
    ) -> dict[str, Any]:
        """发送文本消息。

        Args:
            cid: 会话 ID (格式: xxx@goofish)
            to_id: 接收者 ID (格式: xxx@goofish)
            text: 消息文本
            persist: 是否在发送成功后自动持久化 OUT 消息到数据库。
                     默认 False，由调用方自行决定是否入库（手动发送、自动回复
                     均在各自路径中调用 save_chat_message，避免重复入库）。
            is_auto_reply: 是否 AI 自动回复 0否 1是。仅在 persist=True 时透传给
                           _persist_outbound_message 用于消息标记。调用方自行入库时
                           应在 save_chat_message 调用中显式传入。

        Returns:
            {"code": 200, "uuid": "..."} 或 {"code": 500, "error": "..."}
        """
        # 预检：如果连接断开，等待最多 3 秒让自动重连完成
        if not self._connected or not self._ws:
            for _ in range(30):
                await asyncio.sleep(0.1)
                if self._connected and self._ws:
                    break
            else:
                return {"code": 500, "error": "WebSocket 未连接"}

        if not self._sid:
            return {"code": 500, "error": "WebSocket 未注册（无 sid）"}

        if not cid:
            return {"code": 500, "error": "会话 ID 为空"}
        if not to_id:
            return {"code": 500, "error": "接收者 ID 为空"}

        # 预检：如果超过 30 秒未收到服务端消息，连接可能已静默断开
        idle_secs = time.time() - self._last_recv_time
        if idle_secs > HEARTBEAT_INTERVAL * 2:
            logger.warning(
                "发送消息前检测到连接可能已断开 accountId=%d (%.0f秒无消息), "
                "跳过本次发送, 等待重连",
                self.account_id, idle_secs,
            )
            return {"code": 500, "error": "WebSocket 连接已断开, 正在重连"}

        # === 发送层去重：60秒内向同一会话同一接收者发送相同内容直接返回成功 ===
        # 防止并发竞态、Java 桥接重试、手动触发等导致重复发送触发闲鱼滑块验证
        dedup_key = f"{self.account_id}:{cid}:{to_id}:{text}"
        now = time.time()
        cached = _recent_text_sends.get(dedup_key)
        if cached and (now - cached["ts"]) < _RECENT_SEND_DEDUP_TTL:
            logger.info(
                "发送层去重命中，跳过重复发送 accountId=%d cid=%s contentLen=%d age=%.1fs",
                self.account_id, cid, len(text), now - cached["ts"],
            )
            return {"code": 200, "uuid": cached.get("uuid", ""), "deduplicated": True}
        # 清理过期条目（最多保留 _RECENT_SEND_DEDUP_MAX 条）
        async with _get_recent_text_sends_lock():
            if len(_recent_text_sends) >= _RECENT_SEND_DEDUP_MAX:
                _cleanup_recent_text_sends(now)

        # 获取发送者 ID
        from_id = f"{self.unb}@goofish" if self.unb else ""

        logger.info(
            "WS send_text_message: accountId=%d contentLen=%d sessionReady=%s",
            self.account_id,
            len(text),
            bool(self._sid),
        )

        msg = build_send_message(cid, to_id, from_id, text, self._sid)
        msg_mid = msg["headers"]["mid"]

        # 创建 Future 等待响应
        # 注意：用 headers 中的 mid 做 key，因为服务端 ACK 只回复 mid，不回复 uuid
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._send_futures[msg_mid] = fut

        try:
            logger.debug(
                "WS 发送消息 accountId=%d contentLen=%d",
                self.account_id,
                len(text),
            )
            await self._ws.send(json.dumps(msg, ensure_ascii=False))
            # 等待响应（带超时）- 文本消息使用 6 秒超时（而非 IMAGE_MESSAGE_ACK_TIMEOUT=2）
            # 原 2 秒超时过短，易误判失败导致上层重试，进而触发重复发送
            result = await asyncio.wait_for(fut, timeout=_TEXT_MESSAGE_ACK_TIMEOUT)
            # 记录成功发送到去重缓存
            async with _get_recent_text_sends_lock():
                _recent_text_sends[dedup_key] = {
                    "ts": now,
                    "uuid": result.get("uuid", "") if isinstance(result, dict) else "",
                }
            return result
        except asyncio.TimeoutError:
            logger.error(
                "发送消息超时 accountId=%d connected=%s phase=%s",
                self.account_id,
                self._connected,
                getattr(self, "phase", "unknown"),
            )
            # 仅标记单条消息发送失败，不再主动关闭整个 WS 连接。
            # 旧实现会在超时后 close() 整个连接，导致后续所有消息发送全部失败，
            # 即使连接实际仍然健康（只是这一条消息因为 toId 无效等原因无法收到 ACK）。
            # 真正的连接死亡会由 _heartbeat_loop 中的"静默断开检测"负责回收。
            self.last_error = "发送消息超时（单条消息失败，连接保持）"
            return {"code": 500, "error": "发送消息超时"}
        except Exception as e:
            log_service_failure(
                logger, e, operation="send_ws_text_message",
                tenant_id=self.tenant_id, account_id=self.account_id,
            )
            return {"code": 500, "errorCode": "WS_SEND_FAILED", "error": "WebSocket 消息发送失败，请稍后重试"}
        finally:
            self._send_futures.pop(msg_mid, None)

    async def send_image_message(
        self,
        cid: str,
        to_id: str,
        image_url: str,
        width: int = 800,
        height: int = 600,
    ) -> dict[str, Any]:
        """发送图片消息。

        Args:
            cid: 会话 ID (格式: xxx@goofish)
            to_id: 接收者 ID (格式: xxx@goofish)
            image_url: 图片 URL

        Returns:
            {"code": 200, "uuid": "..."} 或 {"code": 500, "error": "..."}
        """
        if not self._connected or not self._ws:
            for _ in range(30):
                await asyncio.sleep(0.1)
                if self._connected and self._ws:
                    break
            else:
                return {"code": 500, "error": "WebSocket 未连接"}

        if not self._sid:
            return {"code": 500, "error": "WebSocket 未注册（无 sid）"}

        if not cid:
            return {"code": 500, "error": "会话 ID 为空"}
        if not to_id:
            return {"code": 500, "error": "接收者 ID 为空"}

        idle_secs = time.time() - self._last_recv_time
        if idle_secs > HEARTBEAT_INTERVAL * 2:
            logger.warning(
                "发送图片前检测到连接可能已断开 accountId=%d (%.0f秒无消息), 跳过本次发送, 等待重连",
                self.account_id, idle_secs,
            )
            return {"code": 500, "error": "WebSocket 连接已断开, 正在重连"}

        from_id = f"{self.unb}@goofish" if self.unb else ""

        logger.info(
            "WS send_image_message: accountId=%d imagePresent=%s dimensions=%dx%d",
            self.account_id,
            bool(image_url),
            width,
            height,
        )

        msg = build_send_image_message(
            cid,
            to_id,
            from_id,
            image_url,
            self._sid,
            width=width,
            height=height,
        )
        msg_mid = msg["headers"]["mid"]

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._send_futures[msg_mid] = fut

        try:
            await self._ws.send(json.dumps(msg, ensure_ascii=False))
            result = await asyncio.wait_for(fut, timeout=MESSAGE_TIMEOUT)
            return result
        except asyncio.TimeoutError:
            logger.error(
                "发送图片超时 accountId=%d",
                self.account_id,
            )
            # 与 send_text_message 保持一致：超时不主动关闭整个 WS 连接
            self.last_error = "发送图片超时（单条消息失败，连接保持）"
            return {"code": 500, "error": "发送图片超时"}
        except Exception as e:
            log_service_failure(
                logger, e, operation="send_ws_image_message",
                tenant_id=self.tenant_id, account_id=self.account_id,
            )
            return {"code": 500, "errorCode": "WS_IMAGE_SEND_FAILED", "error": "WebSocket 图片发送失败，请稍后重试"}
        finally:
            self._send_futures.pop(msg_mid, None)

    async def _persist_outbound_message(
        self,
        cid: str,
        to_id: str,
        text: str = "",
        image_url: str = "",
        width: int = 0,
        height: int = 0,
        content_type: int = 1,
        is_auto_reply: int = 0,
    ) -> None:
        """发送消息成功后主动保存到数据库，避免依赖 IM 推送回环导致漏收。

        旧实现：发送消息后只等待 ACK，不入库。自己/AI 发的消息完全依赖 IM 服务器
        推送回来（sync package）才会入库，如果推送丢失则消息消失——这是
        "仅显示对方消息、不显示自己消息和 AI 回复"的核心根因。

        新实现：发送成功后立即构造 OUT 消息并调用 on_message_callback 入库。
        如果推送回环也来了，save_chat_message 的 message_uid/pnm_id 去重逻辑
        会处理重复，不会产生双份数据。
        """
        if not self.on_message_callback:
            return

        from_id = f"{self.unb}@goofish" if self.unb else ""

        # sId 在协议中通常不带 @goofish 后缀，入库也以裸 sId 为准
        s_id_raw = cid
        if s_id_raw and s_id_raw.endswith("@goofish"):
            s_id_raw = s_id_raw[:-8]

        # messageTime 设为 0：不用本地时间（本地时间是"获取时间"不是"发送时间"）。
        # save_chat_message 兜底为 created_time（入库时间）作为临时值。
        # 当 IM 推送回环到来时（actualReceivers 包含自己），推送包带服务端时间戳（字段 5），
        # save_chat_message 的去重命中逻辑会用服务端时间戳更新 message_time。
        msg: dict[str, Any] = {
            "direction": "OUT",
            "senderUserId": from_id,
            "receiverUserId": to_id,
            "sId": s_id_raw,
            "msgContent": text,
            "contentType": content_type,
            "messageTime": 0,
            "pnmId": "",
            "xyGoodsId": "",
            "readStatus": 1,
            "isAutoReply": int(is_auto_reply or 0),
        }

        # 图片消息需要携带完整图片结构，前端 extractImageMessageUrls 会从
        # completeMsg 中提取 imageUrls/images 字段，避免从 msgContent 推断失败。
        if content_type == 2 and image_url:
            msg["msgContent"] = ""
            msg["imageUrls"] = [image_url]
            msg["images"] = [{"url": image_url, "width": width, "height": height}]

        try:
            await self.on_message_callback(self.tenant_id, self.account_id, msg)
        except Exception as exc:
            log_service_failure(
                logger, exc, operation="persist_outbound_ws_message",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
            )

    async def _connect_loop(self):
        """连接循环（自动重连，指数退避）。"""
        reconnect_delay = RECONNECT_DELAY_INITIAL
        while self._running:
            try:
                await self._connect()
                reconnect_delay = RECONNECT_DELAY_INITIAL  # 成功后重置退避
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.last_error = "WebSocket 连接异常，正在重连"
                self.phase = "error"
                log_service_failure(
                    logger, e, operation="ws_connect_loop",
                    tenant_id=self.tenant_id, account_id=self.account_id,
                )

            if self._running:
                logger.info("WS 将在 %d 秒后重连 accountId=%d", reconnect_delay, self.account_id)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(
                    reconnect_delay * RECONNECT_BACKOFF_FACTOR,
                    RECONNECT_DELAY_MAX,
                )

    async def _send_and_wait(self, msg: dict[str, Any], timeout: float = MESSAGE_TIMEOUT) -> dict[str, Any]:
        if not self._connected or not self._ws:
            raise RuntimeError("WebSocket 未连接")

        headers = msg.setdefault("headers", {})
        msg_mid = str(headers.get("mid") or generate_mid())
        headers["mid"] = msg_mid

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._send_futures[msg_mid] = fut

        try:
            await self._ws.send(json.dumps(msg, ensure_ascii=False))
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._send_futures.pop(msg_mid, None)

    async def list_conversations(
        self,
        start_timestamp: int | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if start_timestamp is None:
            start_timestamp = 9007199254740991

        response = await self._send_and_wait(
            {
                "lwp": "/r/Conversation/listNewestPagination",
                "headers": {"mid": generate_mid()},
                "body": [int(start_timestamp), max(int(limit or 20), 1)],
            },
            timeout=max(MESSAGE_TIMEOUT, 8),
        )
        return response.get("body") or {}

    async def list_messages(
        self,
        cid: str,
        start_timestamp: int | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if start_timestamp is None:
            start_timestamp = 9007199254740991

        response = await self._send_and_wait(
            {
                "lwp": "/r/MessageManager/listUserMessages",
                "headers": {"mid": generate_mid()},
                "body": [
                    _normalize_goofish_target(cid),
                    False,
                    int(start_timestamp),
                    max(int(limit or 20), 1),
                    False,
                ],
            },
            timeout=max(MESSAGE_TIMEOUT, 8),
        )
        return response.get("body") or {}

    def _ensure_cookie_has_mh5tk(self):
        """确保 self.cookie_str 中包含 _m_h5_tk 且与 self.m_h5_tk 一致。

        关键：WebSocket 升级时会发送 Cookie 头，服务端会检查 cookie 中的 _m_h5_tk
        是否与 accessToken 匹配。如果 cookie 中不含 _m_h5_tk 或值不匹配，
        服务端会静默丢弃连接后的所有消息。

        注意：self.m_h5_tk 此时已是最新值（_refresh_token 已更新），
        accessToken 是使用 self.m_h5_tk 生成的。因此 cookie 中必须包含
        完全相同的 _m_h5_tk 值，不能使用 cookie 中旧的/不同的值。
        """
        import re

        cookie_m_h5_tk = extract_m_h5_tk_from_cookie(self.cookie_str)

        logger.info(
            "_ensure_cookie_has_mh5tk: accountId=%d cookieTokenPresent=%s dbTokenPresent=%s matches=%s",
            self.account_id,
            bool(cookie_m_h5_tk),
            bool(self.m_h5_tk),
            bool(cookie_m_h5_tk and self.m_h5_tk and cookie_m_h5_tk == self.m_h5_tk),
        )

        if cookie_m_h5_tk and self.m_h5_tk and cookie_m_h5_tk != self.m_h5_tk:
            # cookie 中的 _m_h5_tk 与生成 accessToken 所用的不一致！
            # 必须修复 cookie，否则服务端会因 _m_h5_tk 不匹配而静默丢弃连接
            logger.warning(
                "_ensure_cookie_has_mh5tk: accountId=%d, cookie 中的 _m_h5_tk 与 "
                "生成 accessToken 所用的不同, 正在修复 cookie",
                self.account_id,
            )
            self.cookie_str = re.sub(
                r'_m_h5_tk=[^;]+',
                f'_m_h5_tk={self.m_h5_tk}',
                self.cookie_str
            )
            logger.info(
                "_ensure_cookie_has_mh5_tk: accountId=%d 已修复 cookie 中的 _m_h5_tk",
                self.account_id,
            )

        if not cookie_m_h5_tk and self.m_h5_tk:
            # cookie 中不含 _m_h5_tk，需要追加进去
            logger.warning(
                "_ensure_cookie_has_mh5tk: accountId=%d, cookie 中缺少 _m_h5_tk, "
                "将生成 accessToken 所用的值追加到 cookie",
                self.account_id,
            )
            if self.cookie_str:
                self.cookie_str = f"_m_h5_tk={self.m_h5_tk}; {self.cookie_str}"
            else:
                self.cookie_str = f"_m_h5_tk={self.m_h5_tk}"
            logger.info(
                "_ensure_cookie_has_mh5tk: accountId=%d 已追加 _m_h5_tk 到 cookie",
                self.account_id,
            )

    async def _connect(self):
        """建立 WebSocket 连接并初始化。"""
        # Step 1: 获取 accessToken
        self.phase = "refresh_token"
        if not await self._refresh_token():
            self.last_error = "获取 WebSocket Token 失败，Cookie/_m_h5_tk 可能已过期或触发滑块验证"
            self.phase = "token_failed"
            logger.error("获取 WebSocket Token 失败 accountId=%d", self.account_id)
            # 关键修复：Token 获取失败时持久化离线状态，避免 ws_status 保持旧值 1 误导前端
            await self._persist_ws_offline("token_failed: 获取 WebSocket Token 失败")
            # 不在此处 sleep，由 _connect_loop 的指数退避统一控制重连节奏
            return

        # === 关键：确保 cookie 中的 _m_h5_tk 与 accessToken 匹配 ===
        # 必须在 _refresh_token 之后（此时 self.m_h5_tk 已是最新的有效值）
        self._ensure_cookie_has_mh5tk()

        # 仅记录凭证存在性/一致性，不记录任何前缀。
        cookie_m_h5_tk = extract_m_h5_tk_from_cookie(self.cookie_str)

        logger.info(
            "获取 accessToken 成功 accountId=%d tokenDevicePresent=%s deviceIdPresent=%s accessTokenLength=%d",
            self.account_id,
            bool(self.m_h5_tk),
            bool(self.device_id),
            len(self._access_token) if self._access_token else 0,
        )
        logger.info(
            "deviceId 一致性检查: accountId=%d cookieTokenPresent=%s tokenDevicePresent=%s deviceIdPresent=%s",
            self.account_id,
            bool(cookie_m_h5_tk),
            bool(self.m_h5_tk),
            bool(self.device_id),
        )
        if self.m_h5_tk and cookie_m_h5_tk:
            logger.info(
                "cookie _m_h5_tk 一致性检查: accountId=%d matches=%s",
                self.account_id,
                "是" if cookie_m_h5_tk == self.m_h5_tk else "否",
            )
        elif not cookie_m_h5_tk:
            logger.error(
                "cookie _m_h5_tk 一致性检查: accountId=%d, cookie 中仍然缺少 _m_h5_tk! "
                "WebSocket 连接很可能被服务端静默丢弃",
                self.account_id,
            )

        # Step 2: 建立 WSS 连接（不添加 ?token= 参数，token 只在 /reg 消息中传递）
        ws_url = WS_URL
        additional_headers = {
            "Cookie": self.cookie_str,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.7680.177 Safari/537.36"
            ),
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
            "Host": "wss-goofish.dingtalk.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "Upgrade",
            "Upgrade": "websocket",
        }

        ws = _ThreadedWebSocketAdapter(
            account_id=self.account_id,
            tenant_id=self.tenant_id,
            url=ws_url,
            headers=additional_headers,
        )

        try:
            self.phase = "connecting"
            logger.info("连接 WS accountId=%d 使用 websocket-client 底层实现", self.account_id)
            await ws.connect(timeout=10)
            self._ws = ws
            self.phase = "connected_socket"
            logger.info("WS 已连接 accountId=%d", self.account_id)

            # Step 3: 注册
            self.phase = "registering"
            if not await self._do_reg(ws):
                self.last_error = "WebSocket 已连接但注册失败，可能是 accessToken/deviceId/Cookie 不匹配"
                self.phase = "register_failed"
                return

            # Step 4: 等 1 秒再发同步消息（与 Java 实现对齐）
            await asyncio.sleep(1)

            # Step 5: 同步
            self.phase = "syncing"
            await self._do_sync(ws)

            # 连接成功
            self._connected = True
            self.last_error = ""
            self.phase = "connected"
            # 持久化在线状态到 DB，确保刷新页面/重载列表时仍显示"在线"
            await self._persist_ws_online()

            # Step 6: 消息接收循环 + 心跳
            await self._message_loop(ws)

        except ConnectionError as e:
            self.last_error = "WebSocket 连接已关闭，正在重连"
            self.phase = "closed"
            # 关键修复：连接异常时持久化离线状态，避免 ws_status 保持旧值 1 误导前端
            await self._persist_ws_offline("closed: WebSocket 连接已关闭")
            log_service_failure(
                logger, e, operation="ws_connection_closed",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
            )
        except Exception as e:
            self.last_error = "WebSocket 连接异常，正在重连"
            self.phase = "error"
            # 关键修复：连接异常时持久化离线状态，避免 ws_status 保持旧值 1 误导前端
            await self._persist_ws_offline("error: WebSocket 连接异常")
            log_service_failure(
                logger, e, operation="ws_connection",
                tenant_id=self.tenant_id, account_id=self.account_id,
            )
        finally:
            self._connected = False
            self._sid = None
            self._ws = None
            try:
                await ws.close()
            except Exception:
                logger.debug("连接异常后关闭 WS 失败（可忽略）accountId=%d", self.account_id)

    async def _update_token_in_db(self, new_m_h5_tk: str):
        """将刷新后的 _m_h5_tk 写回数据库。"""
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            async with async_session() as db:
                await db.execute(
                    text(
                        "UPDATE xianyu_account_auth SET encrypted_token = :tk, updated_time = NOW() "
                        "WHERE account_id = :aid AND tenant_id = :tid"
                    ),
                    {
                        "tk": encrypt_cookie_for_storage(new_m_h5_tk),
                        "aid": self.account_id,
                        "tid": self.tenant_id,
                    },
                )
                await db.commit()
            logger.info(
                "已更新 DB 中的 _m_h5_tk: accountId=%d, token_len=%d",
                self.account_id, len(new_m_h5_tk or ""),
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="persist_ws_m_h5_tk",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
            )

    async def _update_cookie_in_db(self, new_cookie_str: str):
        """将刷新后的 cookie 字符串写回数据库。"""
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            async with async_session() as db:
                await db.execute(
                    text(
                        "UPDATE xianyu_account_auth SET encrypted_cookie = :cookie, updated_time = NOW() "
                        "WHERE account_id = :aid AND tenant_id = :tid"
                    ),
                    {
                        "cookie": encrypt_cookie_for_storage(new_cookie_str),
                        "aid": self.account_id,
                        "tid": self.tenant_id,
                    },
                )
                await db.commit()
            logger.info(
                "已更新 DB 中的 cookie: accountId=%d, cookie_len=%d",
                self.account_id, len(new_cookie_str),
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="persist_ws_cookie",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
            )

    async def _persist_ws_online(self):
        """连接成功后持久化在线状态到 DB。

        更新 online_status=1, ws_status=1, last_heartbeat_time, last_online_time。
        确保刷新页面或重载账号列表时仍显示"在线"。
        临时断开（_connect_loop 会自动重连）不调用此方法，保持 DB 在线状态，
        避免"保持在线，除非 Cookie 失效或弹窗"的预期被破坏。

        同时自动恢复因 WS 断开导致连续失败被禁用的 auto_delivery 定时兜底任务。
        根因：auto_delivery 任务依赖 WS 发送发货消息，WS 短暂断开时发货失败，
        连续失败达到阈值后被 disabled_after_failures 自动禁用；WS 恢复后若不恢复任务，
        后续所有自动发货都无法触发。
        """
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            from .automation_runtime import update_ws_heartbeat
            async with async_session() as db:
                await update_ws_heartbeat(db, {
                    "tenantId": self.tenant_id,
                    "accountId": self.account_id,
                    "onlineStatus": 1,
                    "wsStatus": 1,
                    "latency": 0,
                })
                # WS 恢复连接时，自动恢复因 WS 断开导致连续失败被禁用的自动发货定时任务
                reenabled = await db.execute(text("""
                    UPDATE scheduled_task
                    SET enabled = 1,
                        consecutive_failure_count = 0,
                        last_status = 'pending',
                        updated_time = NOW()
                    WHERE tenant_id = :tenant_id
                      AND deleted = 0
                      AND task_type = 'auto_delivery'
                      AND enabled = 0
                      AND last_status = 'disabled_after_failures'
                """), {"tenant_id": self.tenant_id})
                if (reenabled.rowcount or 0) > 0:
                    logger.info(
                        "WS 恢复连接，已自动重新启用被禁用的自动发货定时任务: tenantId=%d accountId=%d count=%d",
                        self.tenant_id, self.account_id, reenabled.rowcount,
                    )
                await db.commit()
            logger.info("已持久化 WS 在线状态: accountId=%d", self.account_id)
        except Exception as e:
            log_service_failure(
                logger, e, operation="persist_ws_online",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
            )

    async def _persist_ws_offline(self, reason: str = "WS 连接失败"):
        """关键修复：WS 连接失败时主动持久化离线状态到 DB。

        原先 _persist_ws_online() 只在连接成功时设 ws_status=1，
        连接失败时不会设 ws_status=0，导致 ws_status 保持旧值（仍为 1），
        前端显示"WS 已连接"但实际未连接，收不到新消息。

        现在在 token_failed / closed / error 阶段调用此方法，
        将 ws_status 和 online_status 设为 0，让前端显示真实状态。
        注意：不修改 cookie_status（Cookie 可能仍有效，只是 WS 未连接）。
        """
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            async with async_session() as db:
                await db.execute(
                    text(
                        "UPDATE xianyu_account_runtime "
                        "SET ws_status = 0, online_status = 0, updated_time = NOW() "
                        "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0"
                    ),
                    {"aid": self.account_id, "tid": self.tenant_id},
                )
                await db.commit()
            logger.info(
                "已持久化 WS 离线状态: accountId=%d reason=%s",
                self.account_id, reason,
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="persist_ws_offline",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
            )

    async def _persist_heartbeat(self):
        """心跳成功后更新 DB 的 last_heartbeat_time，保持心跳活跃。

        只更新 last_heartbeat_time，不改动 online_status/ws_status，
        避免每 15 秒刷新 last_online_time 导致"最后上线时间"失真。
        """
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            async with async_session() as db:
                await db.execute(
                    text(
                        "UPDATE xianyu_account_runtime "
                        "SET last_heartbeat_time = NOW(), updated_time = NOW() "
                        "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0"
                    ),
                    {"aid": self.account_id, "tid": self.tenant_id},
                )
                await db.commit()
        except Exception as e:
            log_service_failure(
                logger, e, operation="persist_ws_heartbeat",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
            )

    async def _update_cookie_status(self, status: int, code: str | None = None, message: str | None = None):
        """更新 cookie_status（如遇到滑块验证时标记为失效）。"""
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            async with async_session() as db:
                await db.execute(
                    text(
                        "UPDATE xianyu_account_auth SET cookie_status = :st, "
                        "last_login_status_code = :code, last_login_status_message = :message, "
                        "last_login_check_time = NOW(), updated_time = NOW() "
                        "WHERE account_id = :aid AND tenant_id = :tid"
                    ),
                    {
                        "st": status,
                        "code": code,
                        "message": message,
                        "aid": self.account_id,
                        "tid": self.tenant_id,
                    },
                )
                await db.execute(
                    text(
                        "UPDATE xianyu_account_runtime SET cookie_status = :st, "
                        "ws_status = CASE WHEN :st = 0 THEN 0 ELSE ws_status END, "
                        "online_status = CASE WHEN :st = 0 THEN 0 ELSE online_status END, "
                        "last_login_status_code = :code, last_login_status_message = :message, "
                        "last_login_check_time = NOW(), updated_time = NOW() "
                        "WHERE account_id = :aid AND tenant_id = :tid"
                    ),
                    {
                        "st": status,
                        "code": code,
                        "message": message,
                        "aid": self.account_id,
                        "tid": self.tenant_id,
                    },
                )
                await db.commit()
            logger.info(
                "已更新 cookie_status=%d: accountId=%d", status, self.account_id
            )
            # SSE 广播 cookie 状态变更，前端实时更新
            try:
                await broadcaster.broadcast(self.tenant_id, "cookie_status_changed", {
                    "accountId": self.account_id,
                    "tenantId": self.tenant_id,
                    "cookieStatus": status,
                })
                logger.info(
                    "SSE 已广播 cookie_status_changed: accountId=%d, status=%d",
                    self.account_id, status
                )
            except Exception as sse_err:
                log_service_failure(
                    logger, sse_err, operation="broadcast_ws_cookie_status",
                    tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
                )
            # Cookie 失效时推送飞书机器人通知（失败不影响主流程）
            if status == 0:
                try:
                    from .notify_dispatcher import notify_cookie_expired
                    await notify_cookie_expired(self.tenant_id, self.account_id, status)
                except Exception as exc:
                    log_service_failure(
                        logger, exc, operation="notify_ws_cookie_expired",
                        tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
                    )
        except Exception as e:
            log_service_failure(
                logger, e, operation="update_ws_cookie_status",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
            )

    async def _load_cookie_status_snapshot(self) -> dict[str, Any] | None:
        try:
            from ..core.database import async_session
            from sqlalchemy import text as _sa_text

            async with async_session() as db:
                row = (await db.execute(
                    _sa_text(
                        "SELECT cookie_status AS auth_cookie_status, "
                        "last_login_status_code AS auth_login_status_code "
                        "FROM xianyu_account_auth "
                        "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 "
                        "LIMIT 1"
                    ),
                    {"aid": self.account_id, "tid": self.tenant_id},
                )).mappings().first()
                return dict(row) if row else None
        except Exception as e:
            log_service_failure(
                logger, e, operation="load_ws_cookie_status",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
            )
            return None

    @staticmethod
    def _cookie_status_snapshot_healthy(snapshot: dict[str, Any] | None) -> bool:
        if not snapshot:
            return False
        status = int(snapshot.get("auth_cookie_status") or 0)
        code = str(snapshot.get("auth_login_status_code") or "").upper()
        return status == 1 and code == "OK"

    async def _restore_cookie_status_if_needed(self) -> None:
        snapshot = await self._load_cookie_status_snapshot()
        # 无论 cookie_status 快照是否健康，只要 Token 刷新成功就说明账号正在恢复
        # （如 WS 重连成功），清除所有账号状态通知去重标记（内存 + DB），确保下次失效时能重新通知。
        try:
            from .notify_dispatcher import clear_all_account_status_notifications
            await clear_all_account_status_notifications(self.tenant_id, self.account_id)
        except Exception as exc:
            log_service_failure(
                logger, exc, operation="clear_ws_account_status_notifications",
                tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
            )
        if self._cookie_status_snapshot_healthy(snapshot):
            return
        await self._update_cookie_status(1, "OK", "账号登录状态正常")

    async def _refresh_token(self) -> bool:
        """获取/刷新 accessToken。如果 DB 中的 _m_h5_tk 过期，自动从 cookie 提取并更新 DB。
        如果 cookie 中的 _m_h5_tk 也已过期，尝试调用 refresh_m_h5_tk 刷新令牌。
        遇到滑块验证时自动更新 cookie_status 为 0（失效）。
        """
        access_token, effective_m_h5_tk, error_type, refreshed_cookie = await asyncio.to_thread(
            get_ws_token_with_refreshed_m_h5_tk, self.cookie_str, self.m_h5_tk
        )
        if access_token:
            self._access_token = access_token
            # 如果用了刷新后的 token，更新 DB 中的 token 和 cookie
            if effective_m_h5_tk and effective_m_h5_tk != self.m_h5_tk:
                self.m_h5_tk = effective_m_h5_tk
                await self._update_token_in_db(effective_m_h5_tk)
                logger.info(
                    "WS Token 获取: accountId=%d 使用了刷新后的 m_h5_tk，已更新 DB",
                    self.account_id,
                )
            else:
                logger.info(
                    "WS Token 获取: accountId=%d 使用现有的 m_h5_tk",
                    self.account_id,
                )
            # 如果 cookie 被刷新了（含新的 _m_h5_tk），更新 DB 中的 cookie
            if refreshed_cookie and refreshed_cookie != self.cookie_str:
                self.cookie_str = refreshed_cookie
                await self._update_cookie_in_db(refreshed_cookie)
            await self._restore_cookie_status_if_needed()
            return True

        # 如果是滑块验证，不立即标记 cookie_status=0：
        # WS Token API（mtop.taobao.idlemessage.pc.login.token）需要完整的 bx-ua / bx-umidtoken / bx_et
        # 反爬令牌，Python/Java 直接 POST 不带这些令牌，容易被 Baxia 风控判定为异常请求返回
        # FAIL_SYS_USER_VALIDATE。这是"调用方式缺陷"导致的误判，不代表 Cookie 真的失效。
        # 改为只触发滑块求解，由求解器内部通过 hasLogin / page.head 二次验证判断 Cookie 是否真的失效。
        # 只有求解器确认 Cookie 失效时才更新 cookie_status=0（在 captcha_solver.py 中处理）。
        if error_type == "captcha":
            logger.warning(
                "WS Token 获取遇到滑块验证（Cookie 可能仍有效，等待求解器二次验证）: accountId=%d",
                self.account_id
            )
            try:
                from .notify_dispatcher import notify_captcha_required
                await notify_captcha_required(self.tenant_id, self.account_id, "WS Token 获取触发滑块验证")
            except Exception as exc:
                log_service_failure(
                    logger, exc, operation="notify_ws_captcha_required",
                    tenant_id=self.tenant_id, account_id=self.account_id, level=logging.DEBUG,
                )
            # 自动触发滑块求解（失败不影响主流程，状态由求解器内部决定）
            await self._auto_solve_captcha_after_failure(scene="captcha")
        elif error_type == "expired":
            logger.warning(
                "WS Token 获取失败（Cookie 已过期）: accountId=%d",
                self.account_id
            )
            await self._update_cookie_status(0, "COOKIE_EXPIRED", "Cookie 已过期，请重新登录闲鱼账号")
            # 自动触发滑块求解：Session 过期场景下闲鱼可能要求重新过滑块，
            # 求解器内部会通过 Token API 二次验证判断 Cookie 是否真的可用，
            # 若 Token API 仍返回 expired 则保持 cookie_status=0 让用户重新登录
            await self._auto_solve_captcha_after_failure(scene="expired")

        return False

    async def _auto_solve_captcha_after_failure(self, scene: str = "captcha") -> None:
        """WS Token 获取失败后自动触发滑块求解（通过优先级队列）。

        将求解任务入队到 CaptchaQueueManager 优先级队列，由 worker 按优先级
        （SVIP > VIP > 普通）依次处理。队列内部处理：
        1. 同账号 30 分钟去重
        2. 三重预校验（账号活跃度 + Cookie 状态 + 退避检查）
        3. Playwright 检测/求解滑块
        4. Token API 二次验证 Cookie
        5. 成功后恢复 cookie_status=1 + 刷新 _m_h5_tk + 自动重连 WS
        6. Cookie 失效时更新状态 + 发送飞书通知
        7. 滑块失败时自动重试（最多 3 次）

        功能开关：
        - 查询 auto-slider-solve 开关，关闭时静默跳过（不入队、不写记录、不广播 SSE）
        - 用户级会员（sys_user.vip_level）控制开关，与 Java FeatureSwitchService 一致

        优先级：基于用户级会员（sys_user.vip_level），SVIP=2 > VIP=1 > 普通=0。
        一个用户的所有闲鱼账号共享同一等级。

        Args:
            scene: 触发场景，"captcha" 表示滑块验证，"expired" 表示 Session 过期
        """
        # 根据场景确定具体的求解原因（写入滑块求解记录）
        if scene == "expired":
            solve_reason = "WS Token 获取失败：Cookie Session 已过期，尝试通过滑块求解恢复"
        else:
            solve_reason = "WS Token 获取遇到滑块验证（FAIL_SYS_USER_VALIDATE）"

        try:
            from .captcha_queue import enqueue_solve
            from .captcha_precheck import is_auto_slider_solve_allowed, lookup_user_level

            # 功能开关校验：auto-slider-solve 关闭时静默跳过，不占用服务器资源
            allowed, level_code = await is_auto_slider_solve_allowed(self.tenant_id)
            if not allowed:
                logger.info(
                    "WS Token 失败后自动滑块求解被开关拦截（静默跳过）"
                    "accountId=%d tenantId=%d level=%s scene=%s",
                    self.account_id, self.tenant_id, level_code, scene,
                )
                return

            # 查询用户级优先级（SVIP=2, VIP=1, 普通=0），一个用户的所有账号共享同一等级
            _level, priority = await lookup_user_level(self.tenant_id)

            # 入队到优先级队列（队列内部处理去重、预校验、求解、重试、后处理）
            record_id = await enqueue_solve(
                account_id=self.account_id,
                tenant_id=self.tenant_id,
                trigger_scene="token_refresh",
                open_reason="WS Token 获取失败自动触发",
                solve_reason=solve_reason,
                priority=priority,
            )

            if record_id is None:
                logger.info(
                    "WS Token 失败后自动滑块求解入队去重跳过 accountId=%d scene=%s（30 分钟内已入队）",
                    self.account_id, scene,
                )
            else:
                logger.info(
                    "WS Token 失败后自动滑块求解已入队 accountId=%d scene=%s priority=%d recordId=%d",
                    self.account_id, scene, priority, record_id,
                )
        except Exception as e:
            log_service_failure(
                logger, e, operation="enqueue_auto_solve_ws_captcha",
                tenant_id=self.tenant_id, account_id=self.account_id,
            )

    async def _do_reg(self, ws: _ThreadedWebSocketAdapter) -> bool:
        """发送 /reg 注册消息并等待响应。使用循环接收，捕获服务端所有回包。"""
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.177 Safari/537.36 "
            "DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/146.0.7680.177) "
            "DingWeb/2.1.5 IMPaaS DingWeb/2.1.5"
        )

        device_id = self.device_id

        # === deviceId 一致性检查 ===
        if not device_id:
            logger.error(
                "WS 注册无法发送: deviceId 为空 accountId=%d credentialPresent=%s",
                self.account_id,
                bool(self.m_h5_tk),
            )
            return False

        logger.info(
            "WS 注册 did 检查: accountId=%d deviceIdPresent=%s tokenDeviceIdPresent=%s",
            self.account_id,
            bool(device_id),
            bool(self.m_h5_tk),
        )

        msg = build_reg_message(self._access_token, device_id, ua=ua)

        # === 调试日志：打印注册消息关键字段 ===
        logger.info(
            "WS 注册消息已构建: accountId=%d accessTokenLength=%d appKeyPresent=%s",
            self.account_id,
            len(self._access_token) if self._access_token else 0,
            bool(msg.get("headers", {}).get("app-key")),
        )

        # === 发送前短暂延迟：让服务端有足够时间完成 WebSocket 握手后的初始化 ===
        # 某些 WebSocket 服务端在 HTTP Upgrade 后需要短暂时间准备会话状态
        await asyncio.sleep(0.5)
        logger.info("WS 注册消息发送中: accountId=%d", self.account_id)

        await ws.send(json.dumps(msg, ensure_ascii=False))
        logger.info("WS 注册消息已发送: accountId=%d, 开始等待响应(10秒超时)", self.account_id)

        # === 循环接收：捕获 10 秒内服务端发来的所有消息 ===
        deadline = time.time() + 10
        all_received = []
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
                all_received.append(resp)
                data = json.loads(resp)
                lwp = data.get("lwp", "")

                logger.info(
                    "WS 注册等待中收到消息: accountId=%d lwp=%s code=%s dataKeys=%s",
                    self.account_id,
                    lwp,
                    data.get("code"),
                    sorted(str(key) for key in data.keys()),
                )

                # 检查 401 / token 失效
                if data.get("code") == 401:
                    logger.error(
                        "WS 注册失败: token 无效/过期 accountId=%d code=401",
                        self.account_id,
                    )
                    return False

                # 注册成功响应有两种形态：
                # 1. lwp == /reg 且 code == 200
                # 2. lwp 为空，但 headers 中直接返回 reg-sid / sid
                if data.get("code") == 200:
                    headers = data.get("headers", {})
                    reg_sid = headers.get("reg-sid") or headers.get("sid")
                    if reg_sid:
                        self._sid = reg_sid
                        logger.info(
                            "WS 注册成功 accountId=%d sessionReady=%s lwp=%s",
                            self.account_id,
                            bool(self._sid),
                            lwp,
                        )
                        return True

                # 非注册消息：继续等待
                logger.info(
                    "WS 注册等待中忽略非注册消息: accountId=%d, lwp=%s",
                    self.account_id, lwp,
                )

            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError:
                logger.warning(
                    "WS 注册等待中收到非 JSON 消息: accountId=%d payloadBytes=%d",
                    self.account_id,
                    len(resp.encode("utf-8")) if isinstance(resp, str) else len(resp),
                )
                continue

        # === 超时：打印所有收到的消息 ===
        if not all_received:
            logger.error(
                "WS 注册超时 accountId=%d (10秒内服务端未发送任何消息)",
                self.account_id,
            )
        else:
            logger.error(
                "WS 注册超时 accountId=%d (10秒内共收到 %d 条消息，但未收到 /reg 成功响应)",
                self.account_id, len(all_received),
            )
            for i, raw in enumerate(all_received):
                logger.error(
                    "WS 注册超时前收到的第 %d 条消息: accountId=%d payloadBytes=%d",
                    i + 1,
                    self.account_id,
                    len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw),
                )

        return False

    async def _do_sync(self, ws: _ThreadedWebSocketAdapter):
        """发送 /r/SyncStatus/ackDiff 同步消息。"""
        if self._sync_pts <= 0:
            self._sync_pts = int(time.time() * 1000000)  # 微秒
        msg = build_sync_message(self._sync_pts, self._sync_high_pts)
        # 记录 mid 用于识别 ackDiff 空响应（无 lwp，仅 code+headers）。
        # 服务端在长轮询超时（无新消息）时返回这种格式，必须识别并发起下一轮 sync。
        try:
            self._sync_pending_mid = str(msg.get("headers", {}).get("mid") or "")
        except Exception:
            self._sync_pending_mid = ""
        await ws.send(json.dumps(msg, ensure_ascii=False))
        logger.info(
            "WS 同步请求已发送 accountId=%d pts=%s highPts=%s",
            self.account_id, self._sync_pts, self._sync_high_pts
        )

    async def _message_loop(self, ws: _ThreadedWebSocketAdapter):
        """消息接收循环，包含心跳。"""
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

        try:
            while True:
                raw_msg = await ws.recv()
                try:
                    await self._handle_message(raw_msg, ws)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="handle_ws_message",
                        tenant_id=self.tenant_id, account_id=self.account_id,
                    )
        except ConnectionError:
            logger.warning("WS 接收循环连接关闭 accountId=%d", self.account_id)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self, ws: _ThreadedWebSocketAdapter):
        """心跳保活循环（15秒间隔）。"""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                # 如果超过 45 秒未收到服务端任何消息，很可能连接已静默断开
                idle_secs = time.time() - self._last_recv_time
                if idle_secs > HEARTBEAT_INTERVAL * 3:
                    logger.warning(
                        "WS 连接已静默断开 accountId=%d (%.0f秒无消息), "
                        "主动关闭连接以触发重连",
                        self.account_id, idle_secs,
                    )
                    # 必须关闭 WS，否则 _message_loop 会阻塞在 ws.recv() 上，
                    # _connect 的 finally 块不会执行，_connected 保持 True，
                    # 后续消息会发送到死连接上导致超时。
                    await ws.close()
                    break

                msg = build_heartbeat_message()
                await ws.send(json.dumps(msg, ensure_ascii=False))
                logger.debug("WS 心跳发送 accountId=%d", self.account_id)
                # 心跳发送成功，更新 DB 心跳时间，保持 last_heartbeat_time 活跃
                await self._persist_heartbeat()
            except Exception as e:
                log_service_failure(
                    logger, e, operation="send_ws_heartbeat",
                    tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
                )
                # 同样需要关闭 WS 以确保状态正确回收
                try:
                    await ws.close()
                except Exception:
                    logger.debug("心跳失败后关闭 WS 失败（可忽略）accountId=%d", self.account_id)
                break

    async def _handle_message(self, raw_msg: str, ws: _ThreadedWebSocketAdapter):
        """处理收到的 WebSocket 消息。"""
        self._last_recv_time = time.time()
        try:
            data = json.loads(raw_msg)
        except json.JSONDecodeError:
            logger.warning(
                "WS 消息 JSON 解析失败 payloadBytes=%d",
                len(raw_msg.encode("utf-8")),
            )
            return

        lwp = data.get("lwp", "")

        # === ACK 响应处理（必须在 lwp 分发之前）===
        # 闲鱼发送消息后的 ACK 响应没有 lwp 字段，格式为:
        #   {"code": 200, "headers": {"mid": "...", "sid": "..."}}
        # 或失败 ACK:
        #   {"code": 500, "headers": {"mid": "..."}, "body": {"message": "..."}}
        # 与心跳响应格式完全相同。唯一区别是 mid 是否在 _send_futures 中。
        # 必须优先查 _send_futures，否则 ACK 会被当作心跳静默丢弃，
        # 导致 send_text_message 中的 Future 永远不被 resolve，10 秒后超时。
        code = data.get("code")
        headers = data.get("headers", {})
        if isinstance(headers, dict):
            mid = headers.get("mid", "")
            if mid and mid in self._send_futures:
                logger.info(
                    "WS 收到消息 ACK accountId=%d code=%s",
                    self.account_id,
                    code,
                )
                fut = self._send_futures.pop(mid)
                if not fut.done():
                    # 构造结果：包含 code 和 mid，失败时从 body 提取错误消息
                    result: dict[str, Any] = {
                        "code": code if code else 200,
                        "mid": mid,
                        "lwp": lwp,
                        "headers": headers,
                        "body": data.get("body"),
                    }
                    final_code = code if code else 200
                    if final_code != 200:
                        body = data.get("body", {})
                        if isinstance(body, dict):
                            error_msg = (
                                body.get("message")
                                or body.get("msg")
                                or body.get("error")
                                or body.get("reason")
                                or body.get("developerMessage")
                                or ""
                            )
                            if error_msg:
                                result["error"] = str(error_msg)
                            else:
                                result["error"] = f"服务端返回错误 code={final_code}"
                        else:
                            result["error"] = f"服务端返回错误 code={final_code}"
                    fut.set_result(result)
                return

            # 修复：识别 ackDiff 长轮询的空响应（无 lwp，仅有 code 和 headers，且 mid 匹配 _sync_pending_mid）。
            # 服务端在 ackDiff 短轮询无新消息时返回这种格式：
            #   {"code": 200, "headers": {"mid": "..."}}
            # 之前这种消息被当作"未处理"丢弃，导致 ackDiff 轮询链路断裂，
            # 客户端不再 sync，服务端不推送新消息，自动回复无法触发。
            # 注意：空响应后必须等待 ACKDIFF_POLL_INTERVAL 秒再发下一轮，
            # 否则会形成疯狂循环触发服务端限流。
            if (
                not lwp
                and code is not None
                and mid
                and self._sync_pending_mid
                and mid == self._sync_pending_mid
            ):
                logger.info(
                    "WS ackDiff 空响应 accountId=%d code=%s，%.1fs 后发起下一轮 sync",
                    self.account_id,
                    code,
                    ACKDIFF_POLL_INTERVAL,
                )
                self._sync_pending_mid = None
                try:
                    await asyncio.sleep(ACKDIFF_POLL_INTERVAL)
                    await self._do_sync(ws)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="resync_after_empty_ackdiff",
                        tenant_id=self.tenant_id, account_id=self.account_id,
                    )
                return

        if lwp in ("/s/para", "/s/sync", "/s/vulcan", "/r/SyncStatus/ackDiff"):
            # 同步包（聊天消息/增量推送）
            await self._handle_sync_package(data, ws)
        elif lwp == "/r/MessageSend/sendByReceiverScope":
            # 发送消息的响应
            await self._handle_send_response(data)
        elif lwp == "/!":
            # 心跳响应（此时 mid 不在 _send_futures 中，是真正的心跳）
            pass
        elif lwp == "/reg":
            # 注册响应（已在 _do_reg 处理）
            pass
        else:
            # 未识别的 lwp 类型：旧实现仅 debug 日志，导致可能遗漏的消息类型完全不可见。
            # 升级为 warning 级别并打印消息片段，便于发现闲鱼新增的协议类型（防止漏收消息）。
            logger.warning(
                "WS 未处理的消息类型 accountId=%d lwp=%s dataKeys=%s",
                self.account_id,
                lwp,
                sorted(str(key) for key in data.keys()),
            )

    async def _handle_sync_package(self, data: dict, ws: _ThreadedWebSocketAdapter):
        """处理同步包（聊天消息）。"""
        lwp = data.get("lwp", "")
        is_ack_diff = lwp == "/r/SyncStatus/ackDiff"

        # 提取同步响应中的高点水印
        if is_ack_diff:
            try:
                body = data.get("body", {})
                if isinstance(body, dict):
                    sync_push = body.get("syncPushPackage") or body
                    max_high_pts = sync_push.get("maxHighPts", 0)
                    max_pts = sync_push.get("maxPts", 0)
                    if max_high_pts:
                        self._sync_high_pts = max_high_pts
                    if max_pts:
                        self._sync_pts = max_pts
                    logger.info(
                        "WS ackDiff 响应 accountId=%d maxHighPts=%s maxPts=%s",
                        self.account_id, max_high_pts, max_pts
                    )
            except Exception as e:
                log_service_failure(
                    logger, e, operation="parse_ws_ack_diff",
                    tenant_id=self.tenant_id, account_id=self.account_id, level=logging.WARNING,
                )

        result = parse_sync_package(data)
        if not result:
            # 任何 sync 响应（/s/vulcan、/s/para、/s/sync、/r/SyncStatus/ackDiff）
            # 都必须发起下一轮 sync 维持轮询链路。之前仅在 is_ack_diff=True 时发起，
            # 导致 /s/vulcan 响应后链路断裂，客户端不再 sync，服务端不推送新消息，
            # 自动回复无法触发。
            # 注意：无消息时延迟 ACKDIFF_POLL_INTERVAL 秒再发下一轮，避免疯狂循环。
            try:
                await asyncio.sleep(ACKDIFF_POLL_INTERVAL)
                await self._do_sync(ws)
            except Exception as e:
                log_service_failure(
                    logger, e, operation="resync_after_no_result",
                    tenant_id=self.tenant_id, account_id=self.account_id,
                )
            return

        messages = result.get("messages", [])
        ack_ids = result.get("ack_pnm_ids", [])

        if not messages:
            body_keys = list((data.get("body") or {}).keys()) if isinstance(data.get("body"), dict) else []
            logger.info(
                "WS 同步包未解析出可入库消息 accountId=%d lwp=%s bodyKeys=%s",
                self.account_id,
                lwp,
                body_keys,
            )
            # 无消息时延迟 ACKDIFF_POLL_INTERVAL 秒再发下一轮，避免疯狂循环。
            try:
                await asyncio.sleep(ACKDIFF_POLL_INTERVAL)
                await self._do_sync(ws)
            except Exception as e:
                log_service_failure(
                    logger, e, operation="resync_after_no_messages",
                    tenant_id=self.tenant_id, account_id=self.account_id,
                )
            return

        logger.info("WS 收到 %d 条消息 accountId=%d lwp=%s", len(messages), self.account_id, lwp)

        # 1. 回复 ACK
        for pnm_id in ack_ids:
            try:
                ack_msg = build_ack_message(pnm_id)
                await ws.send(json.dumps(ack_msg, ensure_ascii=False))
            except Exception as e:
                log_service_failure(
                    logger, e, operation="send_ws_ack",
                    tenant_id=self.tenant_id, account_id=self.account_id,
                )

        # 2. 先发起下一轮 ackDiff，避免当前批次的消息处理阻塞后续同步。
        # 有消息时立即发下一轮（可能还有积压），维持轮询链路确保服务端持续推送新消息。
        await self._do_sync(ws)

        # 3. 处理当前批次消息（落库 + SSE 广播）。
        for msg in messages:
            await self._process_message(msg)

    async def _process_message(self, msg: dict):
        """处理单条消息（保存 + 回调 + 广播）。"""
        s_id = msg.get("sId", "")
        pnm_id = msg.get("pnmId", "")
        msg_content = msg.get("msgContent", "")
        sender_id = msg.get("senderUserId", "")
        logger.info(
            "WS 处理消息 accountId=%d sessionRefPresent=%s messageRefPresent=%s "
            "senderRefPresent=%s contentLen=%d",
            self.account_id,
            bool(s_id),
            bool(pnm_id),
            bool(sender_id),
            len(str(msg_content)) if msg_content else 0,
        )
        # 当关键引用缺失时只记录结构元数据，不回显买家消息。
        if not msg_content and (s_id in ("", "1") or pnm_id in ("", "1")):
            logger.info(
                "WS 诊断: 内容为空且消息引用异常 accountId=%d messageKeys=%s",
                self.account_id,
                sorted(str(key) for key in msg.keys()),
            )
        # 1. 外部回调（如数据库保存）
        if self.on_message_callback:
            try:
                await self.on_message_callback(self.tenant_id, self.account_id, msg)
            except Exception as e:
                log_service_failure(
                    logger, e, operation="persist_inbound_ws_message",
                    tenant_id=self.tenant_id, account_id=self.account_id,
                )

        # 2. SSE 广播到前端
        try:
            direction = str(msg.get("direction") or "IN").upper()
            sender_id = str(msg.get("senderUserId") or "")
            receiver_id = str(msg.get("receiverUserId") or "")
            peer_user_id = receiver_id if direction == "OUT" and receiver_id else sender_id
            if not peer_user_id and msg.get("sId"):
                peer_user_id = f"sid:{msg.get('sId')}"
            # 使用 normalize_peer_name 过滤系统文本
            raw_user_name = "" if direction == "OUT" else str(msg.get("senderUserName") or "")
            peer_user_name = normalize_peer_name(raw_user_name)
            if not peer_user_name and peer_user_id.startswith("sid:"):
                peer_user_name = "闲鱼买家"
            await broadcaster.broadcast(self.tenant_id, "message", {
                "accountId": self.account_id,
                "sId": msg.get("sId", ""),
                "sid": msg.get("sId", ""),
                "pnmId": msg.get("pnmId", ""),
                "senderUserId": sender_id,
                "senderUserName": msg.get("senderUserName", ""),
                "receiverUserId": receiver_id,
                "peerUserId": peer_user_id,
                "peerUserName": peer_user_name,
                "peerNick": peer_user_name,
                "msgContent": msg.get("msgContent", ""),
                "message": msg.get("msgContent", ""),
                "content": msg.get("msgContent", ""),
                "contentType": msg.get("contentType", 1),
                "messageTime": msg.get("messageTime", 0),
                "direction": msg.get("direction", ""),
                "reminderContent": msg.get("reminderContent", ""),
                "reminderUrl": msg.get("reminderUrl", ""),
                "xyGoodsId": msg.get("xyGoodsId", ""),
                "readStatus": 1 if direction == "OUT" else 0,
            })
        except Exception as e:
            log_service_failure(
                logger, e, operation="broadcast_ws_message",
                tenant_id=self.tenant_id, account_id=self.account_id,
            )

    async def _handle_send_response(self, data: dict):
        """处理发送消息的响应。"""
        result = parse_send_response(data)
        if not result:
            return

        # 先尝试 uuid 匹配（兼容有 lwp 且带 uuid 的完整响应）
        uuid_val = result.get("uuid")
        if uuid_val and uuid_val in self._send_futures:
            fut = self._send_futures.pop(uuid_val)
            if not fut.done():
                fut.set_result(result)
            return

        # 再尝试 mid 匹配兜底（某些响应可能带 lwp 但仍以 mid 作为标识）
        headers = data.get("headers", {})
        mid = headers.get("mid", "") if isinstance(headers, dict) else ""
        if mid and mid in self._send_futures:
            fut = self._send_futures.pop(mid)
            if not fut.done():
                fut.set_result(result)


class WebSocketManager:
    """WebSocket 连接管理器。

    管理多个账号的 WebSocket 客户端实例。
    """

    def __init__(self):
        self._clients: dict[int, XianyuWebSocketClient] = {}
        self._on_message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """设置消息回调函数。"""
        self._on_message_callback = callback

    async def start_client(
        self,
        account_id: int,
        tenant_id: int,
        cookie_str: str,
        m_h5_tk: str,
        unb: str,
    ) -> bool:
        """启动指定账号的 WebSocket 客户端。"""
        # 停止已有客户端
        await self.stop_client(account_id)

        client = XianyuWebSocketClient(
            account_id=account_id,
            tenant_id=tenant_id,
            cookie_str=cookie_str,
            m_h5_tk=m_h5_tk,
            unb=unb,
            on_message_callback=self._on_message_callback,
        )
        self._clients[account_id] = client

        asyncio.create_task(client.start())
        logger.info("WS 管理器: 启动客户端 accountId=%d", account_id)
        return True

    async def stop_client(self, account_id: int):
        """停止指定账号的 WebSocket 客户端。"""
        client = self._clients.pop(account_id, None)
        if client:
            await client.stop()
            logger.info("WS 管理器: 停止客户端 accountId=%d", account_id)

    async def stop_all(self):
        """停止所有 WebSocket 客户端。"""
        for account_id in list(self._clients.keys()):
            await self.stop_client(account_id)

    def get_client(self, account_id: int) -> Optional[XianyuWebSocketClient]:
        """获取指定账号的 WebSocket 客户端。"""
        return self._clients.get(account_id)

    def get_status(self, account_id: int) -> dict:
        """获取指定账号的连接状态。"""
        client = self._clients.get(account_id)
        if client:
            return {
                "connected": client.is_connected,
                "hasSid": client._sid is not None,
                "deviceId": client.device_id,
                "tokenDeviceId": client.m_h5_tk.split("_")[0] if client.m_h5_tk and "_" in client.m_h5_tk else client.m_h5_tk,
                "phase": getattr(client, "phase", "unknown"),
                "lastError": getattr(client, "last_error", ""),
            }
        return {
            "connected": False,
            "hasSid": False,
            "deviceId": "",
            "tokenDeviceId": "",
            "phase": "not_started",
            "lastError": "",
        }

    async def restart_account(self, account_id: int) -> bool:
        """重启指定账号的 WebSocket 客户端（自动从 DB 读取最新 Cookie/Token）。

        供自动滑块求解成功后调用，让 WS 立即重连而不等下一次重连周期。

        Returns:
            True 表示已触发重启，False 表示账号未找到或启动失败
        """
        try:
            from ..core.database import async_session
            from sqlalchemy import text
            from .cookie_token_refresher import _load_active_accounts  # noqa: F401

            # 从 DB 读取最新账号信息
            async with async_session() as db:
                row = (await db.execute(
                    text(
                        "SELECT a.id AS account_id, a.tenant_id, a.external_uid AS unb, "
                        "auth.encrypted_cookie, auth.encrypted_token "
                        "FROM xianyu_account a "
                        "JOIN xianyu_account_auth auth "
                        "  ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id "
                        " AND COALESCE(auth.deleted, 0) = 0 "
                        " AND auth.id = ("
                        "   SELECT auth2.id FROM xianyu_account_auth auth2 "
                        "   WHERE auth2.account_id = a.id AND auth2.tenant_id = a.tenant_id "
                        "     AND COALESCE(auth2.deleted, 0) = 0 "
                        "   ORDER BY COALESCE(auth2.updated_time, auth2.created_time) DESC, auth2.id DESC "
                        "   LIMIT 1"
                        " ) "
                        "WHERE a.id = :aid AND a.deleted = 0 "
                        "LIMIT 1"
                    ),
                    {"aid": account_id},
                )).mappings().first()
            if not row:
                logger.warning("restart_account: 账号不存在 accountId=%d", account_id)
                return False

            from ..core.cookie_crypto import decrypt_cookie_if_needed
            cookie_str = decrypt_cookie_if_needed(row["encrypted_cookie"])
            m_h5_tk = decrypt_cookie_if_needed(row["encrypted_token"]) if row["encrypted_token"] else None
            tenant_id = int(row["tenant_id"])
            unb = str(row["unb"] or "")

            if not cookie_str or not m_h5_tk:
                logger.warning(
                    "restart_account: Cookie 或 _m_h5_tk 为空，无法重启 accountId=%d",
                    account_id,
                )
                return False

            await self.start_client(
                account_id=account_id,
                tenant_id=tenant_id,
                cookie_str=cookie_str,
                m_h5_tk=m_h5_tk,
                unb=unb,
            )
            logger.info("restart_account: 已触发重启 accountId=%d", account_id)
            return True
        except Exception as e:
            log_service_failure(logger, e, operation="restart_ws_account", account_id=account_id)
            return False


# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()
