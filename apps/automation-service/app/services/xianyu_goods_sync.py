"""
闲鱼商品同步服务模块。
负责调用闲鱼 mtop API 获取商品列表和详情，解析并入库。
"""

import hashlib
import io
import json
import logging
import os
import random
import ipaddress
import socket
import time
import threading
import asyncio
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlencode, urlsplit

import re
import requests
from PIL import Image

from ..core.config import settings
from ..core.failure_logging import log_service_failure
from ..core.image_security import MAX_IMAGE_BYTES, validate_image_bytes

logger = logging.getLogger(__name__)

GOODS_SYNC_FAILURE_MESSAGE = "商品同步失败，请检查账号状态后重试"


def _verify_active_storage_asset(tenant_id: int, public_url: str, storage_key: str) -> int:
    """Return the recorded size for an active tenant-owned upload.

    The publisher runs in a worker thread, so this deliberately uses the
    synchronous PyMySQL driver that aiomysql already depends on.  Failing to
    prove ownership is fatal: legacy/untracked files are never published.
    """

    import pymysql

    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT size_bytes FROM tenant_storage_asset "
                "WHERE tenant_id=%s AND public_url=%s AND storage_key=%s "
                "AND status='active' LIMIT 1",
                (tenant_id, public_url, storage_key),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if not row:
        raise ValueError("publish image is not an active tenant storage asset")
    size_bytes = int(row[0])
    if size_bytes <= 0 or size_bytes > MAX_IMAGE_BYTES:
        raise ValueError("publish image asset size is invalid")
    return size_bytes


def _connected_peer_address(response: requests.Response) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    raw = getattr(response, "raw", None)
    candidates = [
        getattr(getattr(raw, "_connection", None), "sock", None),
        getattr(getattr(raw, "connection", None), "sock", None),
    ]
    for sock in candidates:
        if sock is None:
            continue
        try:
            peer = sock.getpeername()
            address = peer[0] if isinstance(peer, (tuple, list)) else peer
            return ipaddress.ip_address(str(address).split("%", 1)[0])
        except (AttributeError, OSError, TypeError, ValueError):
            continue
    raise ValueError("publish image connection peer cannot be verified")


def _download_public_image_sync(raw_url: str) -> bytes:
    parsed = urlsplit(str(raw_url or "").strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("publish image URL must be public HTTPS")
    if parsed.fragment:
        raise ValueError("publish image URL fragment is not allowed")
    try:
        addresses = {
            ipaddress.ip_address(item[4][0].split("%", 1)[0])
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as exc:
        raise ValueError("publish image host cannot be resolved") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("publish image resolved to a non-public address")

    response = requests.get(
        parsed.geturl(),
        timeout=(5, 10),
        allow_redirects=False,
        stream=True,
        headers={
            "Accept": "image/jpeg,image/png,image/gif,image/webp",
            "User-Agent": "xianyu-assistant-image-publisher/1.0",
        },
    )
    try:
        if 300 <= response.status_code < 400:
            raise ValueError("publish image redirects are not allowed")
        response.raise_for_status()
        if not _connected_peer_address(response).is_global:
            raise ValueError("publish image connected to a non-public address")
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise ValueError("publish image content length is invalid") from exc
            if declared_length < 0 or declared_length > MAX_IMAGE_BYTES:
                raise ValueError("publish image exceeds the size limit")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:
                raise ValueError("publish image exceeds the size limit")
            chunks.append(chunk)
        validated = validate_image_bytes(
            b"".join(chunks),
            declared_media_type=response.headers.get("Content-Type"),
        )
        return validated.content
    finally:
        response.close()


class XianyuRiskControlError(RuntimeError):
    """平台风控/人机验证，不携带上游响应正文。"""


class XianyuAuthExpiredError(RuntimeError):
    """账号登录态过期。"""


class XianyuAlreadyPolishedError(RuntimeError):
    """商品当日已擦亮，属于软成功。"""


class XianyuProviderRejectedError(RuntimeError):
    """平台拒绝业务请求，不暴露响应正文。"""


def _safe_price_to_cent(price: Any) -> int:
    """将价格安全转换为分（int）。

    处理以下情况：
    - 数字：7 / 7.5 / "7" / "7.5"
    - 含货币符号：¥7 / ￥7 / RMB 7 / $7
    - 含单位：7元 / 7块钱 / 7.5 元
    - 范围价格：7-15 / 7~15（取最低价）
    - 空值：返回 0

    抛出 ValueError 当无法提取数字时。
    """
    if price is None or price == "":
        return 0
    if isinstance(price, (int, float)):
        return int(float(price) * 100)
    s = str(price).strip()
    if not s:
        return 0
    # 去除货币符号和单位
    cleaned = re.sub(r'[¥￥$￥RMBrmb元块毛分]', ' ', s)
    # 处理范围价格：取最低价
    cleaned = re.split(r'[~\-—到]', cleaned)[0]
    # 提取第一个数字（支持小数）
    m = re.search(r'\d+(?:\.\d+)?', cleaned)
    if not m:
        raise ValueError(f"无法从价格字符串提取数字: {price!r}")
    return int(float(m.group(0)) * 100)


# ==================== 常量 ====================

APP_KEY = "34839810"
H5_API_BASE = "https://h5api.m.goofish.com/h5"

# 商品列表 API
ITEM_LIST_API = "mtop.idle.web.xyh.item.list"
ITEM_LIST_URL = f"{H5_API_BASE}/{ITEM_LIST_API}/1.0/"

# 商品详情 API
ITEM_DETAIL_API = "mtop.taobao.idle.pc.detail"
ITEM_DETAIL_URL = f"{H5_API_BASE}/{ITEM_DETAIL_API}/1.0/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.goofish.com/",
    "Origin": "https://www.goofish.com",
}

# 同步状态跟踪
_sync_tasks: dict[str, dict] = {}
_sync_lock = threading.Lock()
# 保存详情同步后台任务的强引用，避免被 GC 回收导致任务中途消失
# （asyncio.create_task 不保存引用时，task 可能被垃圾回收，详见 Python 官方文档）
_detail_sync_tasks: set = set()

# 风控错误码
RGV587 = "RGV587"
# 闲鱼 MTOP 接口实际返回的拼写为 FAIL_SYS_TOKEN_EXOIRED（存在拼写错误，多了一个 I）
# 同时兼容正确拼写 FAIL_SYS_TOKEN_EXPIRED，便于上游统一按 Cookie 失效处理
TOKEN_EXPIRED = "FAIL_SYS_TOKEN_EXOIRED"
TOKEN_EXPIRED_ALIAS = "FAIL_SYS_TOKEN_EXPIRED"
SESSION_EXPIRED = "FAIL_SYS_SESSION_EXPIRED"
# 擦亮接口"已擦亮过"软成功码：商品当天已擦亮，视为成功（擦亮目标本就是让商品处于擦亮状态）
POLISH_ALREADY_DONE = "FAIL_BIZ_IDLEITEM_POLISH_AGAIN"
# 擦亮接口其他可视为软成功的业务码（如冷却中）
POLISH_SOFT_SUCCESS_MARKERS = (POLISH_ALREADY_DONE,)

# 闲鱼发布 API 常见业务错误码 → 中文友好提示
# 用于把 ret_msg 中的 FAIL_XXX::描述 翻译成用户能看懂的原因
PUBLISH_REJECT_CODE_MAP = {
    "FAIL_BIZ_ITEM_PICTURE_VIOLATION": "商品图片涉嫌违规（涉黄/涉暴/涉政/水印等）",
    "FAIL_BIZ_ITEM_TITLE_VIOLATION": "商品标题含有违禁词或敏感词",
    "FAIL_BIZ_ITEM_DESC_VIOLATION": "商品描述含有违禁词或敏感词",
    "FAIL_BIZ_ITEM_TITLE_REQUIRED": "商品标题不能为空",
    "FAIL_BIZ_ITEM_DESC_REQUIRED": "商品描述不能为空",
    "FAIL_BIZ_ITEM_PRICE_REQUIRED": "商品价格不能为空",
    "FAIL_BIZ_ITEM_PRICE_INVALID": "商品价格异常，请检查价格区间",
    "FAIL_BIZ_SKU_PRICE_ILLEGAL": "商品价格未设置或为 0，请检查商品来源是否带价格",
    "FAIL_BIZ_ITEM_IMAGE_REQUIRED": "请至少上传一张商品图片",
    "FAIL_BIZ_ITEM_EDIT_INVALID_MAP_LOCATION": "发布地址信息不完整，请补全省市区、GPS 和 POI 信息",
    "FAIL_BIZ_ITEM_CATEGORY_NOT_MATCH": "商品分类与内容不匹配，请重新选择分类",
    "FAIL_BIZ_ITEM_CATEGORY_INVALID": "商品分类无效，请重新选择",
    "FAIL_BIZ_ITEM_QUANTITY_INVALID": "商品库存数量异常",
    "FAIL_BIZ_USER_NOT_LOGIN": "闲鱼登录已失效，请重新扫码登录",
    "FAIL_BIZ_USER_BAN_PUBLISH": "账号被限制发布，请到闲鱼 App 查看账号状态",
    "FAIL_BIZ_USER_PUBLISH_LIMIT": "今日发布数量已达上限，请明天再试",
    "FAIL_BIZ_ITEM_DUPLICATE": "检测到重复发布相同商品，请修改后重试",
    "FAIL_BIZ_ITEM_RISK_CONTENT": "商品内容被风控判定为风险内容",
    "FAIL_BIZ_ITEM_BRAND_VIOLATION": "商品涉嫌品牌侵权，请修改后重试",
    "FAIL_BIZ_ITEM_FAKE_VIOLATION": "商品涉嫌售假，请修改后重试",
    "FAIL_SYS_USER_VALIDATE": "触发了闲鱼安全验证，请稍后重试或在闲鱼 App 中完成验证",
    "FAIL_SYS_PARAM_ERROR": "请求参数有误，请检查商品信息后重试",
    "FAIL_SYS_ILLEGAL_ACCESS": "访问被拒绝，请稍后重试",
    "FAIL_SYS_API_NOT_FOUNDED": "闲鱼接口已下线，请联系管理员",
}


def _explain_publish_rejection(ret_msg: str, data: object) -> str:
    """把闲鱼发布接口返回的 ret_msg 翻译成用户能看懂的中文原因。

    ret 格式通常为 ``"FAIL_XXX::中文描述"``，也可能仅为 ``"FAIL_XXX"``。
    当无法识别错误码时，至少把原始描述透传出来，避免前端只看到"平台暂未接受该商品"。

    Args:
        ret_msg: 闲鱼 ret 数组首项
        data: 闲鱼 data 字段，可能携带额外 subMsg / message

    Returns:
        用户可读的中文错误说明
    """
    raw = str(ret_msg or "").strip()
    # 提取错误码与平台描述：FAIL_XXX::desc 或 FAIL_XXX[]::desc
    code_part = raw
    desc_part = ""
    if "::" in raw:
        code_part, _, desc_part = raw.partition("::")
        code_part = code_part.strip()
        desc_part = desc_part.strip()
    # 兼容形如 "FAIL_XXX[xxx]" 的带参错误码
    code_key = code_part.split("[", 1)[0].strip()

    # data 里偶尔会带更具体的 subMsg / message / msg
    extra_desc = ""
    if isinstance(data, dict):
        for k in ("subMsg", "message", "msg", "errorMessage"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                extra_desc = v.strip()
                break

    friendly = PUBLISH_REJECT_CODE_MAP.get(code_key)
    parts = ["商品发布被平台拒绝"]
    if friendly:
        parts.append(friendly)
    elif desc_part:
        parts.append(desc_part)
    elif extra_desc:
        parts.append(extra_desc)
    else:
        parts.append("平台暂未接受该商品，请检查内容后重试")
    msg = "：".join(parts[:2])

    # 末尾附原始错误码便于排查（仅当代码能识别时）
    if code_key and code_key not in ("None", "", "[]"):
        msg = f"{msg}（错误码：{code_key}）"
    return msg


# 搜索 API 常量（用于商品获取节点和商机发掘页面）
SEARCH_MTOP_API = "mtop.taobao.idlemtopsearch.pc.search"


def _normalize_mtop_search_item(raw: dict) -> dict:
    """将 MTOP 搜索返回的商品标准化为前端期望的格式。

    mtop.taobao.idlemtopsearch.pc.search 新 API 返回深度嵌套结构:
        raw["data"]["item"]["main"]["exContent"]["detailParams"]["title"]
        raw["data"]["item"]["main"]["exContent"]["detailParams"]["itemId"]
        raw["data"]["item"]["main"]["exContent"]["detailParams"]["soldPrice"]
        raw["data"]["item"]["main"]["exContent"]["area"]
        raw["data"]["item"]["main"]["exContent"]["userNickName"]
        raw["data"]["item"]["main"]["exContent"]["title"]  # description
        raw["data"]["item"]["main"]["clickParam"]["args"]["price"]

    同时向后兼容旧的扁平格式。
    """
    # 尝试提取新 API 的嵌套结构
    main = raw.get("data", {}).get("item", {}).get("main", {}) or raw
    ex = main.get("exContent", {})
    dp = ex.get("detailParams", {})
    cp_args = main.get("clickParam", {}).get("args", {})

    # 从嵌套结构中提取字段，兜底到扁平结构
    title = (
        dp.get("title")
        or ex.get("title")
        or raw.get("title")
        or raw.get("itemName")
        or raw.get("name", "")
    )
    price = (
        dp.get("soldPrice")
        or cp_args.get("price")
        or main.get("price")
        or raw.get("price")
        or raw.get("reservePrice")
        or raw.get("currentPrice", "")
    )
    item_id = (
        dp.get("itemId")
        or raw.get("itemId")
        or raw.get("id")
        or raw.get("item_id", "")
    )
    image_url = (
        ex.get("picUrl")
        or dp.get("picUrl")
        or dp.get("pic")
        or main.get("image")
        or raw.get("image")
        or raw.get("picUrl")
        or raw.get("imageUrl")
        or raw.get("pic", "")
    )
    area = (
        ex.get("area")
        or raw.get("area")
        or raw.get("location")
        or raw.get("prov", "")
    )
    seller = (
        ex.get("userNickName")
        or dp.get("userNickName")
        or raw.get("seller")
        or raw.get("userNick")
        or raw.get("nick")
        or raw.get("sellerNick", "")
    )
    description = (
        ex.get("title")
        or dp.get("description")
        or raw.get("description")
        or raw.get("desc", "")
    )

    return {
        "title": title,
        "price": price,
        "imageUrl": image_url,
        "link": f"https://www.goofish.com/item?itemId={item_id}" if item_id else "",
        "itemId": item_id,
        "seller": seller,
        "area": area,
        "soldCount": int(
            cp_args.get("soldCount")
            or raw.get("soldCount")
            or raw.get("sales")
            or 0
        ),
        "wantCount": int(
            cp_args.get("wantCount")
            or raw.get("wantCount")
            or raw.get("want")
            or raw.get("likeCount")
            or 0
        ),
        "description": description,
    }


async def _resolve_account_cookie(
    db: "AsyncSession",
    tenant_id: int,
    account_id: Optional[int],
    current_user: dict,
) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """根据 accountId 解析账号 Cookie 和 _m_h5_tk。

    返回 (cookie_str, error_msg, resolved_account_id)。
    resolved_account_id 用于搜索失败时反向回写 cookie_status。
    """
    from sqlalchemy import select
    from ..models.entities import XianyuAccountAuth
    from ..core.cookie_crypto import decrypt_cookie_if_needed

    try:
        if account_id:
            result = await db.execute(
                select(XianyuAccountAuth).where(
                    XianyuAccountAuth.account_id == account_id,
                    XianyuAccountAuth.tenant_id == tenant_id,
                    XianyuAccountAuth.deleted == 0,
                )
            )
            auth = result.scalar_one_or_none()
            logger.info("[RESOLVE-COOKIE] account_id=%d tenant_id=%d auth_found=%s encrypted_cookie_len=%s",
                        account_id, tenant_id, auth is not None,
                        len(auth.encrypted_cookie) if auth and auth.encrypted_cookie else 0)
        else:
            result = await db.execute(
                select(XianyuAccountAuth)
                .where(
                    XianyuAccountAuth.tenant_id == tenant_id,
                    XianyuAccountAuth.deleted == 0,
                )
                .order_by(XianyuAccountAuth.updated_time.desc())
                .limit(1)
            )
            auth = result.scalar_one_or_none()

        if not auth or not auth.encrypted_cookie:
            logger.warning("[RESOLVE-COOKIE] 返回失败: auth=%s encrypted_cookie=%s account_id=%d tenant_id=%d",
                           auth is not None, bool(auth and auth.encrypted_cookie) if auth else False,
                           account_id or -1, tenant_id)
            return None, "账号未登录或Cookie已失效，请先到「账号管理」扫码登录闲鱼账号", None

        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
        token = _get_token_from_cookie(cookie_str)
        if not token:
            return None, "Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号", auth.account_id

        return cookie_str, None, auth.account_id
    except Exception as e:
        log_service_failure(
            logger, e, operation="resolve_goods_sync_cookie",
            tenant_id=tenant_id, account_id=account_id,
        )
        return None, "读取账号登录状态失败，请稍后重试", None


async def _mark_account_cookie_expired(
    db: "AsyncSession",
    tenant_id: int,
    account_id: int,
    source: str = "unknown",
) -> None:
    """检测到 cookie 失效后反向回写数据库 cookie_status=2（过期）。

    让账号管理页面能立即显示异常状态，无需用户主动切换页面查看。
    同时更新 runtime 表，保持两表状态一致。
    """
    from sqlalchemy import select, update
    from ..models.entities import XianyuAccountAuth, XianyuAccountRuntime
    from datetime import datetime

    try:
        # 更新 auth 表 cookie_status=2（过期）
        await db.execute(
            update(XianyuAccountAuth)
            .where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
            .values(
                cookie_status=2,
                last_login_status_code="COOKIE_EXPIRED",
                last_login_status_message=f"Cookie 已失效（由 {source} 检测）",
                last_login_check_time=datetime.now(),
            )
        )
        # 同步更新 runtime 表（如果存在记录）
        await db.execute(
            update(XianyuAccountRuntime)
            .where(
                XianyuAccountRuntime.account_id == account_id,
                XianyuAccountRuntime.tenant_id == tenant_id,
            )
            .values(
                cookie_status=2,
                last_login_status_code="COOKIE_EXPIRED",
                last_login_status_message=f"Cookie 已失效（由 {source} 检测）",
                last_login_check_time=datetime.now(),
            )
        )
        await db.commit()
        logger.info("[COOKIE-EXPIRED] account_id=%d tenant_id=%d source=%s 已回写 cookie_status=2",
                    account_id, tenant_id, source)
    except Exception as e:
        await db.rollback()
        log_service_failure(
            logger, e, operation="mark_account_cookie_expired",
            tenant_id=tenant_id, account_id=account_id,
        )


async def _persist_sync_task(sync_id: str, **fields) -> None:
    """Best-effort persist of sync task state so progress survives process restarts."""
    try:
        from ..core.database import async_session
        from ..models.entities import XianyuGoodsSyncTask
        from sqlalchemy import select, update

        async with async_session() as db:
            result = await db.execute(select(XianyuGoodsSyncTask).where(XianyuGoodsSyncTask.sync_id == sync_id))
            task = result.scalar_one_or_none()
            now = datetime.now()
            safe_error = GOODS_SYNC_FAILURE_MESSAGE if fields.get("status") == "failed" else None
            db_fields = {
                "status": fields.get("status"),
                "progress": fields.get("progress"),
                "total_count": fields.get("total"),
                "new_count": fields.get("new"),
                "updated_count": fields.get("updated"),
                "skipped_count": fields.get("skipped"),
                "off_shelf_count": fields.get("off_shelf"),
                "detail_synced_count": fields.get("detail_synced"),
                "duration_seconds": fields.get("duration_seconds"),
                "error_message": safe_error,
                "finished_time": now if fields.get("status") in {"completed", "failed"} else None,
                "updated_time": now,
            }
            db_fields = {k: v for k, v in db_fields.items() if v is not None}
            if task:
                await db.execute(update(XianyuGoodsSyncTask).where(XianyuGoodsSyncTask.sync_id == sync_id).values(**db_fields))
            else:
                db.add(XianyuGoodsSyncTask(
                    sync_id=sync_id,
                    tenant_id=int(fields.get("tenant_id") or 0),
                    account_id=int(fields.get("account_id") or 0),
                    status=str(fields.get("status") or "queued"),
                    progress=int(fields.get("progress") or 0),
                    total_count=int(fields.get("total") or 0),
                    new_count=int(fields.get("new") or 0),
                    updated_count=int(fields.get("updated") or 0),
                    skipped_count=int(fields.get("skipped") or 0),
                    off_shelf_count=int(fields.get("off_shelf") or 0),
                    detail_synced_count=int(fields.get("detail_synced") or 0),
                    duration_seconds=float(fields.get("duration_seconds") or 0),
                    error_message=safe_error,
                    started_time=now,
                    finished_time=now if fields.get("status") in {"completed", "failed"} else None,
                    deleted=0,
                    created_time=now,
                    updated_time=now,
                ))
            await db.commit()
    except Exception as exc:
        log_service_failure(
            logger, exc, operation="persist_goods_sync_task", level=logging.WARNING,
        )


def _task_snapshot(sync_id: str) -> Optional[dict]:
    with _sync_lock:
        task = _sync_tasks.get(sync_id)
        return dict(task) if task else None


def _build_sign(token: str, timestamp: int, data_json: str) -> str:
    """构建 MD5 签名：MD5(token + "&" + timestamp + "&" + APP_KEY + "&" + dataJson)"""
    raw = f"{token}&{timestamp}&{APP_KEY}&{data_json}"
    return hashlib.md5(raw.encode()).hexdigest()


def _refresh_m_h5_tk(cookie_str: str) -> str:
    """
    刷新 _m_h5_tk 令牌。
    
    _m_h5_tk 具有时效性，扫码登录保存后可能已过期。
    此函数用存储的 cookie 重建会话，执行 3 步刷新流程获取新令牌。
    
    流程（同 xianyu_qr_login._get_m_h5_tk）:
    1. GET h5api → 获取 cookie2
    2. POST 空 token → 触发服务端下发 _m_h5_tk
    3. POST 真实 token → 刷新并激活令牌
    
    返回: 包含新 _m_h5_tk 的 cookie 字符串
    """
    session = requests.Session()
    # 将存储的 cookie 还原到会话
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, value = part.partition("=")
            session.cookies.set(key.strip(), value.strip(), domain=".goofish.com")

    try:
        # Step 1: GET 获取初始 Cookie
        session.get(ITEM_DETAIL_URL.replace(ITEM_DETAIL_API + "/1.0/", "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get/1.0/"),
                    headers=HEADERS, timeout=15)

        # Step 2: 空 token POST — 触发 _m_h5_tk 下发
        t_ms1 = int(time.time() * 1000)
        data_str = '{"bizScene":"home"}'
        empty_sign = hashlib.md5(f"&{t_ms1}&{APP_KEY}&{data_str}".encode()).hexdigest()
        refresh_url = f"{H5_API_BASE}/mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get/1.0/"

        session.post(refresh_url, headers=HEADERS, data={
            "jsv": "2.7.2", "appKey": APP_KEY, "t": str(t_ms1), "sign": empty_sign,
            "v": "1.0", "type": "originaljson", "dataType": "json",
            "timeout": "20000", "api": "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
            "data": data_str,
        }, timeout=15)

        # 提取新 _m_h5_tk
        m_h5_tk = session.cookies.get("_m_h5_tk")
        if not m_h5_tk:
            logger.warning("刷新 _m_h5_tk 失败：服务器未下发新令牌，继续使用原 cookie")
            return cookie_str

        token = m_h5_tk.split("_")[0]

        # Step 3: 真实 token POST — 激活令牌
        t_ms2 = int(time.time() * 1000)
        real_sign = hashlib.md5(f"{token}&{t_ms2}&{APP_KEY}&{data_str}".encode()).hexdigest()

        session.post(refresh_url, headers=HEADERS, data={
            "jsv": "2.7.2", "appKey": APP_KEY, "t": str(t_ms2), "sign": real_sign,
            "v": "1.0", "type": "originaljson", "dataType": "json",
            "timeout": "20000", "api": "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
            "data": data_str,
        }, timeout=15)

        # 仅合并签名/会话关键字段，禁止用空值或无关 cookie 覆盖原登录态。
        # 历史实现会遍历 session.cookies 全量覆盖，容易把 unb/cookie2/sgcookie 等
        # 覆盖成空或不完整值：MTOP 搜索仍可用，但 stream-upload 发布上传鉴权失败。
        updated_cookies = _parse_cookie(cookie_str)
        for name in (
            "_m_h5_tk",
            "_m_h5_tk_enc",
            "cookie2",
            "_tb_token_",
            "sgcookie",
            "unb",
            "cna",
            "t",
            "isg",
            "tfstk",
        ):
            value = session.cookies.get(name)
            if value:
                updated_cookies[name] = value

        new_cookie_str = "; ".join(f"{k}={v}" for k, v in updated_cookies.items())
        logger.info("_m_h5_tk 已刷新 tokenPresent=%s cookieLen=%d", bool(token), len(new_cookie_str))
        return new_cookie_str

    except Exception as e:
        log_service_failure(logger, e, operation="refresh_goods_sync_m_h5_tk", level=logging.WARNING)
        return cookie_str


def _parse_cookie(cookie_str: str) -> dict:
    """将 Cookie 字符串解析为 dict"""
    if not cookie_str:
        return {}
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, value = part.partition("=")
            cookies[key.strip()] = value.strip()
    return cookies


def _get_token_from_cookie(cookie_str: str) -> Optional[str]:
    """从 Cookie 中提取 _m_h5_tk 的 token 部分"""
    cookies = _parse_cookie(cookie_str)
    m_h5_tk = cookies.get("_m_h5_tk", "")
    if not m_h5_tk:
        return None
    return m_h5_tk.split("_")[0]


def _make_api_request(
    cookie_str: str,
    api_name: str,
    data: dict,
    timeout: int = 30,
    extra_form: Optional[dict] = None,
) -> dict:
    """
    调用闲鱼 mtop API。
    返回解析后的 JSON 响应体。
    """
    token = _get_token_from_cookie(cookie_str)
    if not token:
        raise RuntimeError("Cookie 中缺少 _m_h5_tk，无法签名")

    t_ms = int(time.time() * 1000)
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    sign = _build_sign(token, t_ms, data_json)

    url = f"{H5_API_BASE}/{api_name}/1.0/"

    session = requests.Session()
    # 设置 Cookie，指定 domain 确保发送到 goofish.com
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, value = part.partition("=")
            session.cookies.set(key.strip(), value.strip(), domain=".goofish.com")

    form_data = {
        "jsv": "2.7.2",
        "appKey": APP_KEY,
        "t": str(t_ms),
        "sign": sign,
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": str(timeout * 1000),
        "api": api_name,
        "sessionOption": "AutoLoginOnly",
        "data": data_json,
    }
    if extra_form:
        form_data.update(extra_form)

    resp = session.post(url, headers=HEADERS, data=form_data, timeout=timeout + 10)
    resp.raise_for_status()

    result = resp.json()
    return result


def _parse_item_list_response(response: dict) -> list[dict]:
    """
    解析商品列表 API 响应，提取商品数据列表。
    响应结构: { ret: ["SUCCESS::调用成功"], data: { cardList: [{ cardData: {...} }, ...] } }
    """
    ret = response.get("ret", [])
    if isinstance(ret, list) and ret:
        ret_msg = ret[0] if ret else ""
    else:
        ret_msg = str(ret)

    if RGV587 in ret_msg:
        raise XianyuRiskControlError("商品同步触发平台风控验证")
    if TOKEN_EXPIRED in ret_msg or TOKEN_EXPIRED_ALIAS in ret_msg:
        raise XianyuAuthExpiredError("账号 Token 已过期")

    if "SUCCESS" not in ret_msg:
        raise XianyuProviderRejectedError("闲鱼接口返回错误，请稍后重试")

    data = response.get("data", {})
    if not isinstance(data, dict):
        return []

    card_list = data.get("cardList", [])
    if not isinstance(card_list, list):
        return []

    items = []
    for card in card_list:
        if not isinstance(card, dict):
            continue
        card_data = card.get("cardData", {})
        if isinstance(card_data, dict):
            items.append(card_data)

    return items


def _parse_item_detail_response(response: dict) -> dict:
    """解析商品详情 API 响应，提取详情数据"""
    ret = response.get("ret", [])
    if isinstance(ret, list) and ret:
        ret_msg = ret[0] if ret else ""
    else:
        ret_msg = str(ret)

    if "SUCCESS" not in ret_msg:
        return {}

    data = response.get("data", {})
    if not isinstance(data, dict):
        return {}

    return data


def _safe_get_nested(d: dict, *keys, default=""):
    """安全地从嵌套字典中取值，如 _safe_get_nested(d, 'priceInfo', 'price')"""
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current if current is not None else default


def _parse_card_to_goods(card_data: dict, account_id: int, tenant_id: int) -> dict:
    """
    将闲鱼 API 返回的 cardData 解析为统一的商品字典。
    映射关系基于闲鱼 mtop.idle.web.xyh.item.list 接口的实际返回字段。
    
    闲鱼 API 返回结构:
        cardData = {
            "id": "商品ID",
            "title": "商品标题",
            "itemStatus": 0,          # 0=在售, 1=下架, 2=已售
            "priceInfo": { "price": "99.00", "preText": "¥" },
            "picInfo": { "picUrl": "https://..." },
            "detailParams": { "itemId": "xxx", "soldPrice": "99.00", "picUrl": "..." },
            "detailUrl": "https://...",
            "quantity": 999,
            "exposureCount": 100,
            "viewCount": 50,
            "wantCount": 10,
        }
    """
    # 兼容两套状态枚举：
    # 新版: 0=在售, 1=下架, 2=已售
    # 旧版: 1=在售, 2=下架, 3=已售
    raw_item_status = card_data.get("itemStatus", 0)
    if raw_item_status in (0, 1, 2) and ("priceInfo" in card_data or "picInfo" in card_data or "id" in card_data):
        status_map = {0: 0, 1: 1, 2: 2}
    else:
        status_map = {1: 0, 2: 1, 3: 2}
    status = status_map.get(raw_item_status, 1)

    # 商品ID: 顶层 id 字段 / detailParams.itemId / 兼容旧字段 itemId
    item_id = str(card_data.get("id", "") or _safe_get_nested(card_data, "detailParams", "itemId") or card_data.get("itemId", ""))

    # 价格: 新结构 priceInfo.price / detailParams.soldPrice，兼容旧字段 soldPrice/price
    price = _safe_get_nested(card_data, "priceInfo", "price") or card_data.get("price", "") or card_data.get("soldPrice", "")
    sold_price = _safe_get_nested(card_data, "detailParams", "soldPrice") or card_data.get("soldPrice", "") or price

    # 封面图: 新结构 picInfo.picUrl / detailParams.picUrl，兼容旧字段 coverPic/imageUrl/picUrl
    cover_pic = (
        _safe_get_nested(card_data, "picInfo", "picUrl")
        or _safe_get_nested(card_data, "detailParams", "picUrl")
        or card_data.get("coverPic", "")
        or card_data.get("imageUrl", "")
        or card_data.get("picUrl", "")
    )

    goods = {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "external_goods_id": item_id,
        "title": card_data.get("title", "") or card_data.get("itemName", ""),
        "price": str(price),
        "sold_price": str(sold_price),
        "cover_pic": cover_pic,
        "image_url": cover_pic,
        "stock": str(card_data.get("quantity", "") or card_data.get("stock", "")),
        "quantity": int(card_data.get("quantity", 0) or card_data.get("stock", 0)),
        "exposure_count": int(card_data.get("exposureCount", 0) or 0),
        "view_count": int(card_data.get("viewCount", 0) or card_data.get("ipv", 0) or 0),
        "want_count": int(card_data.get("wantCount", 0) or card_data.get("want", 0) or 0),
        "detail_url": card_data.get("detailUrl", "") or card_data.get("itemUrl", ""),
        "detail_info": card_data.get("detailInfo", "") or card_data.get("desc", ""),
        "description": card_data.get("detailInfo", "") or card_data.get("desc", ""),
        "category": str(card_data.get("categoryId", "") or card_data.get("category", "") or card_data.get("cateName", "")),
        "sort_order": int(card_data.get("sortOrder", 0) or 0),
        "status": status,
        "deleted": 0,
    }

    return goods


def _merge_detail_info(goods_dict: dict, detail_data: dict):
    """将详情 API 返回的数据合并到商品字典中"""
    if not detail_data:
        return

    # 详情 API (mtop.taobao.idle.pc.detail) 的统计数据位于 data.itemDO
    item_info = detail_data.get("itemDO", {}) or detail_data.get("item", {}) or detail_data
    if not isinstance(item_info, dict):
        return

    desc = item_info.get("desc", "")
    if desc:
        goods_dict["detail_info"] = str(desc)
        goods_dict["description"] = str(desc)

    detail_url = item_info.get("detailUrl", "") or item_info.get("itemUrl", "")
    if detail_url:
        goods_dict["detail_url"] = str(detail_url)

    image_urls = []
    for key in ("images", "imageList", "picList", "albumPics"):
        candidates = item_info.get(key)
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, str) and candidate.strip():
                    image_urls.append(candidate.strip())
                elif isinstance(candidate, dict):
                    url = (
                        candidate.get("url")
                        or candidate.get("picUrl")
                        or candidate.get("imageUrl")
                        or candidate.get("imgUrl")
                    )
                    if url:
                        image_urls.append(str(url).strip())
        if image_urls:
            break

    if image_urls:
        deduped = []
        seen = set()
        for url in image_urls:
            if url and url not in seen:
                seen.add(url)
                deduped.append(url)
        goods_dict["image_urls"] = deduped
        goods_dict["cover_pic"] = goods_dict.get("cover_pic") or deduped[0]
        goods_dict["image_url"] = goods_dict.get("image_url") or deduped[0]

    quantity = item_info.get("quantity")
    try:
        if quantity is not None and str(quantity).strip() != "":
            quantity_int = int(quantity)
            goods_dict["quantity"] = quantity_int
            goods_dict["stock"] = quantity_int
    except (ValueError, TypeError):
        pass

    # 提取商品统计字段：浏览量、想要数（来自 data.itemDO.browseCnt / wantCnt）
    for src_key, dst_key in (("browseCnt", "view_count"), ("wantCnt", "want_count")):
        stat_val = item_info.get(src_key)
        if stat_val is not None:
            try:
                goods_dict[dst_key] = int(stat_val)
            except (ValueError, TypeError):
                pass

    sold_price = (
        item_info.get("soldPrice")
        or _safe_get_nested(item_info, "priceInfo", "price")
        or item_info.get("price")
    )
    if sold_price not in (None, ""):
        goods_dict["sold_price"] = str(sold_price)
        goods_dict["price"] = str(sold_price)

    goods_dict["raw_payload"] = detail_data


def _normalize_image_urls(image_urls: Any) -> list[str]:
    if not isinstance(image_urls, list):
        return []
    deduped = []
    seen = set()
    for item in image_urls:
        if item is None:
            continue
        url = str(item).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _clean_goods_update_values(goods_dict: dict, *, partial: bool) -> dict:
    values = {}
    for key, value in goods_dict.items():
        if key in {"tenant_id", "account_id"}:
            continue
        if value is None:
            continue
        if partial and isinstance(value, str) and value.strip() == "":
            continue
        if partial and isinstance(value, list) and not value:
            continue
        if partial and isinstance(value, dict) and not value:
            continue
        values[key] = value
    return values


def _build_goods_insert_values(goods_dict: dict) -> dict:
    values = _clean_goods_update_values(goods_dict, partial=False)
    ext_id = str(goods_dict.get("external_goods_id") or goods_dict.get("goods_id") or "").strip()
    values["tenant_id"] = goods_dict.get("tenant_id")
    values["account_id"] = goods_dict.get("account_id")
    values["goods_id"] = ext_id or values.get("goods_id")
    values["external_goods_id"] = ext_id or values.get("external_goods_id")
    values["image_urls"] = _normalize_image_urls(values.get("image_urls"))
    if "status" in values:
        values["status"] = 1 if int(values["status"]) == 0 else 0 if int(values["status"]) == 1 else 2
    if "quantity" in values:
        try:
            qty = int(values["quantity"])
            # 列表 API 不返回库存：新增商品默认 999（闲鱼常见库存值），
            # 详情同步成功后会覆盖为真实值；避免本地库存为 0 导致 AI 客服误报"没库存"
            values["quantity"] = qty if qty > 0 else 999
        except (ValueError, TypeError):
            values["quantity"] = 999
    if "stock" in values:
        try:
            st = int(values["stock"])
            values["stock"] = st if st > 0 else 999
        except (ValueError, TypeError):
            values["stock"] = 999
    if values.get("detail_info") and not values.get("description"):
        values["description"] = values["detail_info"]
    if values.get("description") and not values.get("detail_info"):
        values["detail_info"] = values["description"]
    if not values.get("cover_pic"):
        if values.get("image_urls"):
            values["cover_pic"] = values["image_urls"][0]
        elif values.get("image_url"):
            values["cover_pic"] = values["image_url"]
    if not values.get("image_url") and values.get("cover_pic"):
        values["image_url"] = values["cover_pic"]
    values["deleted"] = 0
    values["created_time"] = datetime.now()
    values["updated_time"] = datetime.now()
    return values


def _build_goods_update_values(existing, goods_dict: dict, *, partial: bool) -> dict:
    values = _clean_goods_update_values(goods_dict, partial=partial)

    ext_id = str(goods_dict.get("external_goods_id") or goods_dict.get("goods_id") or "").strip()
    if ext_id:
        values["goods_id"] = ext_id
        values["external_goods_id"] = ext_id

    if "status" in values:
        values["status"] = 1 if int(values["status"]) == 0 else 0 if int(values["status"]) == 1 else 2

    if "quantity" in values:
        try:
            values["quantity"] = int(values["quantity"])
        except (ValueError, TypeError):
            values.pop("quantity", None)

    if "stock" in values:
        try:
            values["stock"] = int(values["stock"])
        except (ValueError, TypeError):
            values.pop("stock", None)

    if "image_urls" in values:
        values["image_urls"] = _normalize_image_urls(values["image_urls"])
        if partial and not values["image_urls"]:
            values.pop("image_urls", None)

    if partial:
        for text_key in ("detail_info", "description", "detail_url", "category", "cover_pic", "image_url"):
            if text_key in values and isinstance(values[text_key], str) and not values[text_key].strip():
                values.pop(text_key, None)

    if "cover_pic" not in values:
        candidate_cover = getattr(existing, "cover_pic", None)
        if not candidate_cover and values.get("image_urls"):
            candidate_cover = values["image_urls"][0]
        if not candidate_cover:
            candidate_cover = values.get("image_url")
        if candidate_cover:
            values["cover_pic"] = candidate_cover

    if "image_url" not in values:
        candidate_image = values.get("cover_pic") or getattr(existing, "image_url", None)
        if candidate_image:
            values["image_url"] = candidate_image

    if "detail_info" in values and "description" not in values:
        values["description"] = values["detail_info"]
    if "description" in values and "detail_info" not in values:
        values["detail_info"] = values["description"]

    # 同步时确保商品 deleted=0：若商品仍在闲鱼上（在 synced_ids 中），
    # 应恢复显示（复活之前被 Step 4 标记 deleted=1 的记录）。
    # 幽灵商品反复出现的根因不在同步链路，而在订单补全链路
    # （_backfill_missing_goods_from_orders 对软删除商品创建 deleted=0 重复记录），
    # 那里已修复，本处保持 deleted=0 以支持商品重新上架后恢复显示。
    values["deleted"] = 0
    values["updated_time"] = datetime.now()
    return values


def _is_goods_changed(existing: dict, new_data: dict) -> bool:
    """
    比较商品是否有变化。
    比较关键字段：标题、价格、封面图、状态、库存、曝光、浏览、想要数。
    """
    compare_fields = [
        "title", "sold_price", "cover_pic", "status",
        "quantity", "exposure_count", "view_count", "want_count",
        "detail_info",
    ]
    for field in compare_fields:
        old_val = str(existing.get(field, "")) if existing.get(field) is not None else ""
        new_val = str(new_data.get(field, "")) if new_data.get(field) is not None else ""
        if old_val != new_val:
            return True
    return False



def fetch_goods_list(
    cookie_str: str,
    page_size: int = 20,
    max_pages: int = 50
) -> list[dict]:
    """
    分页获取闲鱼商品列表。
    按最小请求模型调用：pageNumber/pageSize/needGroupInfo/userId。
    """
    cookies_dict = _parse_cookie(cookie_str)
    user_id = cookies_dict.get("unb", "")
    if not user_id:
        raise RuntimeError("Cookie 中缺少 unb，无法同步商品")

    all_items = []
    page_num = 1

    while page_num <= max_pages:
        data = {
            "pageNumber": page_num,
            "pageSize": page_size,
            "needGroupInfo": True,
            "userId": user_id,
        }

        try:
            response = _make_api_request(cookie_str, ITEM_LIST_API, data)
            items = _parse_item_list_response(response)

            if not items:
                break

            all_items.extend(items)
            logger.info(
                "获取商品列表 page=%d, 本页=%d, 累计=%d",
                page_num, len(items), len(all_items)
            )

            # 如果本页数量少于 pageSize，说明是最后一页
            if len(items) < page_size:
                break

            page_num += 1

            # 请求间隔，避免触发风控。该函数保持同步，便于单元测试与脚本复用；
            # 异步调用方应通过 asyncio.to_thread 调用，避免阻塞事件循环。
            time.sleep(random.uniform(0.5, 1.5))

        except Exception as e:
            log_service_failure(logger, e, operation="fetch_goods_page")
            raise

    return all_items


def fetch_item_detail(
    cookie_str: str,
    item_id: str,
) -> dict:
    """
    获取单个商品详情。
    
    参数:
        cookie_str: 闲鱼账号 Cookie
        item_id: 商品 ID
    
    返回: 商品详情数据
    """
    # 从 Cookie 中提取 unb
    cookies_dict = _parse_cookie(cookie_str)
    user_id = cookies_dict.get("unb", "")
    if not user_id:
        logger.warning("Cookie 中缺少 unb，无法获取商品详情")
        return {}

    data = {
        "itemId": item_id,
        "userId": user_id,
    }

    try:
        response = _make_api_request(cookie_str, ITEM_DETAIL_API, data)
        result = _parse_item_detail_response(response)
        if not result:
            ret = response.get("ret", []) if isinstance(response, dict) else "?"
            ret_msg = ret[0] if isinstance(ret, list) and ret else str(ret)
            # 检测风控：触发 Baxia 验证或 RGV587 时抛异常，让上层停止详情同步
            if "FAIL_SYS_USER_VALIDATE" in ret_msg or "RGV587" in ret_msg:
                raise XianyuRiskControlError("商品详情同步触发平台验证")
            logger.warning("详情API返回空 itemId=%s", item_id)
        return result
    except XianyuRiskControlError:
        raise  # 风控异常向上抛，让详情同步停止
    except Exception as e:
        log_service_failure(logger, e, operation="fetch_goods_detail")
        return {}


async def sync_goods_for_account(
    account_id: int,
    tenant_id: int,
    cookie_str: str,
    sync_id: str,
    db_session_factory,
    async_fetch_detail: bool = True,
) -> dict:
    """
    为指定账号执行完整商品同步流程。
    
    流程:
    1. 分页获取全部商品列表（在售+已售）
    2. 增量保存：比对已有数据，只更新变化的商品
    3. 标记本地多余商品为下架
    4. 异步获取商品详情（如有变化）
    
    返回: 同步结果摘要
    """
    start_time = time.time()

    # 更新任务状态
    with _sync_lock:
        _sync_tasks[sync_id] = {
            "status": "running",
            "progress": 0,
            "total": 0,
            "updated": 0,
            "skipped": 0,
            "new": 0,
            "off_shelf": 0,
            "account_id": account_id,
            "started_at": datetime.now().isoformat(),
        }
    await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="running", progress=0)

    try:
        # Step 0: 刷新 _m_h5_tk 令牌，确保同步时使用有效令牌
        logger.info("开始同步商品: account_id=%d, 正在刷新令牌...", account_id)
        cookie_str = await asyncio.to_thread(_refresh_m_h5_tk, cookie_str)

        # Step 1: 直接按最小模型分页获取商品列表
        all_items = await asyncio.to_thread(fetch_goods_list, cookie_str)
        total_count = len(all_items)
        logger.info("商品列表获取完成: %d 件", total_count)

        with _sync_lock:
            _sync_tasks[sync_id]["total"] = total_count
            _sync_tasks[sync_id]["progress"] = 10
        await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="running", progress=10, total=total_count)

        if total_count == 0:
            with _sync_lock:
                _sync_tasks[sync_id]["status"] = "completed"
                _sync_tasks[sync_id]["progress"] = 100
            await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="completed", progress=100, total=0, new=0, updated=0, skipped=0, off_shelf=0, duration_seconds=round(time.time() - start_time, 1))
            return {
                "sync_id": sync_id,
                "total": 0,
                "updated": 0,
                "skipped": 0,
                "new": 0,
                "off_shelf": 0,
                "duration_seconds": round(time.time() - start_time, 1),
            }

        # Step 3: 使用同步数据库会话进行入库
        from ..core.database import async_session
        from ..models.entities import XianyuGoods
        from sqlalchemy import select, update, and_, desc

        async def _do_sync():
            updated_count = 0
            new_count = 0
            synced_ids = set()

            async with async_session() as db:
                for i, card_data in enumerate(all_items):
                    goods_dict = _parse_card_to_goods(card_data, account_id, tenant_id)
                    ext_id = goods_dict["external_goods_id"]
                    synced_ids.add(ext_id)

                    # 查询是否已存在
                    result = await db.execute(
                        select(XianyuGoods)
                        .where(
                            and_(
                                XianyuGoods.tenant_id == tenant_id,
                                XianyuGoods.account_id == account_id,
                                XianyuGoods.external_goods_id == ext_id,
                            )
                        )
                        .order_by(desc(XianyuGoods.updated_time), desc(XianyuGoods.id))
                    )
                    existing = result.scalars().first()

                    if existing:
                        # 直接更新已有商品（不跳过任何商品，确保所有同步商品都在列表中展示）
                        # 闲鱼列表 API 不返回库存：当远程库存为 0 时保留本地 stock，
                        # 避免把"发布时填写的库存"或"详情同步填入的真实库存"清零。
                        update_values = _build_goods_update_values(existing, goods_dict, partial=True)
                        if "quantity" in update_values and int(update_values["quantity"]) <= 0:
                            update_values.pop("quantity", None)
                        if "stock" in update_values and int(update_values["stock"]) <= 0:
                            update_values.pop("stock", None)
                        # 列表 API 不返回库存：若本地库存仍为 0 或缺失（详情同步尚未完成或失败），
                        # 设为 999（闲鱼常见库存值）兜底，避免 AI 客服误报"没库存"。
                        # 详情同步成功后会覆盖为真实值；若本地已有真实库存（>0）则保留。
                        local_qty = int(getattr(existing, "quantity", 0) or 0)
                        local_st = int(getattr(existing, "stock", 0) or 0)
                        if local_qty <= 0 and "quantity" not in update_values:
                            update_values["quantity"] = 999
                        if local_st <= 0 and "stock" not in update_values:
                            update_values["stock"] = 999
                        stmt = (
                            update(XianyuGoods)
                            .where(XianyuGoods.id == existing.id)
                            .values(**update_values)
                        )
                        await db.execute(stmt)
                        updated_count += 1
                    else:
                        # 新增
                        new_goods = XianyuGoods(**_build_goods_insert_values(goods_dict))
                        db.add(new_goods)
                        new_count += 1

                    # 更新进度
                    progress = 10 + int((i + 1) / total_count * 70)
                    with _sync_lock:
                        _sync_tasks[sync_id]["progress"] = min(progress, 80)
                        _sync_tasks[sync_id]["updated"] = updated_count
                        _sync_tasks[sync_id]["skipped"] = 0
                        _sync_tasks[sync_id]["new"] = new_count
                    if (i + 1) == total_count or (i + 1) % 10 == 0:
                        await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="running", progress=min(progress, 80), total=total_count, updated=updated_count, skipped=0, new=new_count)

                # Step 4: 标记本地多余商品为下架
                off_shelf_count = 0
                if synced_ids:
                    # 查找本地有但远程没有的商品（在售状态）
                    local_result = await db.execute(
                        select(XianyuGoods).where(
                            and_(
                                XianyuGoods.tenant_id == tenant_id,
                                XianyuGoods.account_id == account_id,
                                XianyuGoods.deleted == 0,
                            )
                        )
                    )
                    local_goods = local_result.scalars().all()

                    for local_g in local_goods:
                        if local_g.external_goods_id not in synced_ids:
                            stmt = (
                                update(XianyuGoods)
                                .where(XianyuGoods.id == local_g.id)
                                .values(
                                    deleted=1,
                                    status=0 if local_g.status != 2 else 2,
                                    updated_time=datetime.now(),
                                )
                            )
                            await db.execute(stmt)
                            off_shelf_count += 1

                await db.commit()

                with _sync_lock:
                    _sync_tasks[sync_id]["off_shelf"] = off_shelf_count
                    _sync_tasks[sync_id]["progress"] = 90
                await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="running", progress=90, total=total_count, updated=updated_count, skipped=0, new=new_count, off_shelf=off_shelf_count)

                return {
                    "updated": updated_count,
                    "skipped": 0,
                    "new": new_count,
                    "off_shelf": off_shelf_count,
                    "synced_ids": synced_ids,
                }

        sync_result = await _do_sync()

        # Step 5: 异步获取详情（如果有变化的商品）
        # 修复：只要有任何商品（新增或更新）就触发详情同步
        # 原逻辑仅 updated > 0 触发，导致首次同步全是新商品时（updated=0）跳过详情同步，
        # 新商品库存永远为 0（列表 API 不返回库存字段）
        detail_synced = 0
        total_changed = sync_result.get("updated", 0) + sync_result.get("new", 0)
        if async_fetch_detail and total_changed > 0:
            logger.info("创建详情同步任务: account_id=%d, items_count=%d, updated=%d, new=%d",
                        account_id, len(all_items), sync_result.get("updated", 0), sync_result.get("new", 0))
            task = asyncio.create_task(_async_fetch_details(cookie_str, all_items, account_id, tenant_id, sync_id))
            _detail_sync_tasks.add(task)
            task.add_done_callback(_detail_sync_tasks.discard)
            detail_synced = total_changed
        else:
            logger.info("跳过详情同步: async_fetch_detail=%s, updated=%s, new=%s",
                        async_fetch_detail, sync_result.get("updated", 0), sync_result.get("new", 0))

        duration = round(time.time() - start_time, 1)

        with _sync_lock:
            _sync_tasks[sync_id]["status"] = "completed"
            _sync_tasks[sync_id]["progress"] = 100
            _sync_tasks[sync_id]["detail_synced"] = detail_synced
            _sync_tasks[sync_id]["duration_seconds"] = duration
        await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="completed", progress=100, total=total_count, new=sync_result["new"], updated=sync_result["updated"], skipped=sync_result["skipped"], off_shelf=sync_result["off_shelf"], detail_synced=detail_synced, duration_seconds=duration)

        logger.info(
            "商品同步完成: account_id=%d, total=%d, new=%d, updated=%d, skipped=%d, off_shelf=%d, duration=%.1fs",
            account_id, total_count,
            sync_result["new"], sync_result["updated"],
            sync_result["skipped"], sync_result["off_shelf"],
            duration,
        )

        return {
            "sync_id": sync_id,
            "total": total_count,
            "new": sync_result["new"],
            "updated": sync_result["updated"],
            "skipped": sync_result["skipped"],
            "off_shelf": sync_result["off_shelf"],
            "detail_synced": detail_synced,
            "duration_seconds": duration,
        }

    except Exception as e:
        log_service_failure(
            logger, e, operation="sync_goods_for_account",
            tenant_id=tenant_id, account_id=account_id,
        )
        with _sync_lock:
            _sync_tasks[sync_id]["status"] = "failed"
            _sync_tasks[sync_id]["error"] = GOODS_SYNC_FAILURE_MESSAGE
            _sync_tasks[sync_id]["errorCode"] = "GOODS_SYNC_FAILED"
            _sync_tasks[sync_id]["progress"] = 0
        await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, status="failed", progress=0, error=GOODS_SYNC_FAILURE_MESSAGE, duration_seconds=round(time.time() - start_time, 1))
        raise


async def _async_fetch_details(
    cookie_str: str,
    items: list[dict],
    account_id: int,
    tenant_id: int,
    sync_id: str,
):
    """
    异步获取商品详情（后台线程）。
    延迟策略：在售商品 1.5~4s，已售商品 5~10s。
    """
    import asyncio
    from ..core.database import async_session
    from ..models.entities import XianyuGoods
    from sqlalchemy import select, update, and_

    logger.info("详情同步任务启动: account_id=%d, sync_id=%s, items_count=%d", account_id, sync_id, len(items))

    async def _do_detail_sync():
        detail_count = 0
        logger.info("详情同步循环开始: account_id=%d, items=%d", account_id, len(items))
        for i, card_data in enumerate(items):
            item_id = str(card_data.get("id", "") or _safe_get_nested(card_data, "detailParams", "itemId") or card_data.get("itemId", ""))
            if not item_id:
                logger.warning("详情同步: 跳过无 item_id 的商品 (index=%d)", i)
                continue

            item_status = card_data.get("itemStatus", 0)

            # 延迟策略（增大延迟，降低风控触发概率）
            if item_status == 0:  # 在售
                delay = 3.0 + random.uniform(0, 3.0)
            else:  # 已售/已下架
                delay = 6.0 + random.uniform(0, 6.0)

            await asyncio.sleep(delay)

            try:
                # 用 asyncio.to_thread 包装同步 HTTP 调用，避免阻塞事件循环
                detail_data = await asyncio.to_thread(fetch_item_detail, cookie_str, item_id)
                if not detail_data:
                    logger.warning("详情同步: itemId=%s 返回空数据 (index=%d/%d)", item_id, i + 1, len(items))
                    continue

                # 兼容详情数据的不同结构：data.itemDO / data.item / 顶层
                item_info = detail_data.get("itemDO", {}) or detail_data.get("item", {}) or detail_data
                if not isinstance(item_info, dict):
                    item_info = detail_data

                desc = item_info.get("desc", "") or item_info.get("description", "")

                # 提取真实库存：优先 itemDO.quantity，兜底用 SKU 库存求和
                # 闲鱼列表 API 不返回库存，详情 API 才有 data.itemDO.quantity
                remote_quantity = 0
                try:
                    remote_quantity = int(item_info.get("quantity", 0) or 0)
                except (ValueError, TypeError):
                    remote_quantity = 0
                if remote_quantity <= 0:
                    sku_list = item_info.get("skuList") or item_info.get("idleItemSkuList") or []
                    if isinstance(sku_list, list):
                        sku_sum = 0
                        for sku in sku_list:
                            if isinstance(sku, dict):
                                try:
                                    sku_sum += int(sku.get("quantity", 0) or 0)
                                except (ValueError, TypeError):
                                    pass
                        if sku_sum > 0:
                            remote_quantity = sku_sum

                # 提取商品统计字段：浏览量、想要数（来自 data.itemDO.browseCnt / wantCnt）
                remote_view_count = 0
                try:
                    remote_view_count = int(item_info.get("browseCnt", 0) or 0)
                except (ValueError, TypeError):
                    remote_view_count = 0
                remote_want_count = 0
                try:
                    remote_want_count = int(item_info.get("wantCnt", 0) or 0)
                except (ValueError, TypeError):
                    remote_want_count = 0

                # 有描述、库存或统计字段任一可更新时才写库
                if desc or remote_quantity > 0 or remote_view_count > 0 or remote_want_count > 0:
                    async with async_session() as db:
                        goods_result = await db.execute(
                            select(XianyuGoods).where(
                                and_(
                                    XianyuGoods.tenant_id == tenant_id,
                                    XianyuGoods.account_id == account_id,
                                    XianyuGoods.external_goods_id == item_id,
                                    XianyuGoods.deleted == 0,
                                )
                            )
                        )
                        existing = goods_result.scalar_one_or_none()
                        if existing:
                            detail_goods_dict = {
                                "external_goods_id": item_id,
                                "detail_info": str(desc) if desc else "",
                                "description": str(desc) if desc else "",
                                "quantity": remote_quantity if remote_quantity > 0 else None,
                                "stock": remote_quantity if remote_quantity > 0 else None,
                                "view_count": remote_view_count if remote_view_count > 0 else None,
                                "want_count": remote_want_count if remote_want_count > 0 else None,
                            }
                            _merge_detail_info(detail_goods_dict, detail_data)
                            update_values = _build_goods_update_values(existing, detail_goods_dict, partial=True)
                            stmt = (
                                update(XianyuGoods)
                                .where(XianyuGoods.id == existing.id)
                                .values(**update_values)
                            )
                            await db.execute(stmt)
                            await db.commit()

                    detail_count += 1
                    logger.info(
                        "详情同步: itemId=%s, quantity=%s, view=%d, want=%d (%d/%d)",
                        item_id, remote_quantity or "-", remote_view_count, remote_want_count,
                        detail_count, len(items)
                    )

            except XianyuRiskControlError as e:
                log_service_failure(
                    logger, e, operation="sync_goods_detail_risk_control",
                    tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                )
                break
            except Exception as e:
                log_service_failure(
                    logger, e, operation="sync_goods_detail",
                    tenant_id=tenant_id, account_id=account_id,
                )

            # 更新进度
            with _sync_lock:
                if sync_id in _sync_tasks:
                    detail_progress = 90 + int((i + 1) / len(items) * 10)
                    _sync_tasks[sync_id]["detail_progress"] = min(detail_progress, 100)
                    _sync_tasks[sync_id]["detail_count"] = detail_count

        logger.info("详情同步循环结束: account_id=%d, 成功=%d, 总计=%d", account_id, detail_count, len(items))
        with _sync_lock:
            if sync_id in _sync_tasks:
                _sync_tasks[sync_id]["detail_completed"] = True
                _sync_tasks[sync_id]["detail_count"] = detail_count
        await _persist_sync_task(sync_id, tenant_id=tenant_id, account_id=account_id, detail_synced=detail_count)

    try:
        await _do_detail_sync()
    except Exception as e:
        log_service_failure(
            logger, e, operation="async_goods_detail_sync",
            tenant_id=tenant_id, account_id=account_id,
        )


async def upsert_goods_record(
    db,
    *,
    tenant_id: int,
    account_id: int,
    goods_dict: dict,
    partial: bool = False,
):
    from ..models.entities import XianyuGoods
    from sqlalchemy import select, and_, desc

    ext_id = str(goods_dict.get("external_goods_id") or goods_dict.get("goods_id") or "").strip()
    if not ext_id:
        return None, False

    result = await db.execute(
        select(XianyuGoods)
        .where(
            and_(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.account_id == account_id,
                XianyuGoods.external_goods_id == ext_id,
            )
        )
        .order_by(desc(XianyuGoods.updated_time), desc(XianyuGoods.id))
    )
    existing = result.scalars().first()

    if existing:
        update_values = _build_goods_update_values(existing, goods_dict, partial=partial)
        # upsert_goods_record 仅被 persist_published_goods 调用（发布商品场景）。
        # 用户主动发布商品时应复活软删除记录：显式设置 deleted=0。
        # _build_goods_update_values 不再无条件设 deleted=0（避免同步链路复活幽灵商品），
        # 但发布是用户主动行为，应恢复商品显示。
        update_values["deleted"] = 0
        for key, value in update_values.items():
            setattr(existing, key, value)
        return existing, False

    insert_values = _build_goods_insert_values(
        {
            **goods_dict,
            "tenant_id": tenant_id,
            "account_id": account_id,
        }
    )
    new_goods = XianyuGoods(**insert_values)
    db.add(new_goods)
    return new_goods, True


async def persist_published_goods(
    db,
    *,
    tenant_id: int,
    account_id: int,
    cookie_str: str,
    publish_result: dict,
    publish_payload: dict,
) -> Optional[dict]:
    item_id = str(publish_result.get("itemId") or "").strip()
    if not item_id:
        return None

    image_urls = publish_payload.get("imageUrls") or []
    primary_image = image_urls[0] if image_urls else ""
    goods_dict = {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "goods_id": item_id,
        "external_goods_id": item_id,
        "title": str(publish_payload.get("title") or "").strip(),
        "price": str(publish_payload.get("price") or ""),
        "sold_price": str(publish_payload.get("price") or ""),
        "cover_pic": primary_image,
        "image_url": primary_image,
        "image_urls": image_urls,
        "stock": int(publish_payload.get("quantity") or 0),
        "quantity": int(publish_payload.get("quantity") or 0),
        "detail_info": str(publish_payload.get("desc") or "").strip(),
        "description": str(publish_payload.get("desc") or "").strip(),
        "category": str((publish_payload.get("category") or {}).get("catName") or ""),
        "detail_url": publish_result.get("itemUrl") or "",
        "status": 0,
        "deleted": 0,
        "raw_payload": {
            "publishPayload": publish_payload,
            "publishResult": publish_result,
        },
    }

    detail_data = await asyncio.to_thread(fetch_item_detail, cookie_str, item_id)
    if detail_data:
        _merge_detail_info(goods_dict, detail_data)
        raw_payload = goods_dict.get("raw_payload") or {}
        raw_payload["detailData"] = detail_data
        goods_dict["raw_payload"] = raw_payload

    goods, _ = await upsert_goods_record(
        db,
        tenant_id=tenant_id,
        account_id=account_id,
        goods_dict=goods_dict,
        partial=False,
    )
    return {
        "itemId": item_id,
        "title": getattr(goods, "title", None) if goods else goods_dict.get("title"),
        "detailFetched": bool(detail_data),
    }


def get_sync_progress(sync_id: str) -> Optional[dict]:
    """获取同步任务进度"""
    with _sync_lock:
        return _sync_tasks.get(sync_id)


def is_account_syncing(account_id: int) -> bool:
    """检查指定账号是否正在同步"""
    with _sync_lock:
        for task in _sync_tasks.values():
            if task.get("account_id") == account_id and task.get("status") == "running":
                return True
    return False


# ==================== 商品操作（下架/删除） ====================


def extract_token_from_cookie(cookie_str: str) -> Optional[str]:
    """
    从 cookie 字符串中提取 _m_h5_tk 的值，取 _ 前面的部分作为 token。
    """
    for part in cookie_str.split(";"):
        part = part.strip()
        if part.startswith("_m_h5_tk="):
            return part.split("=", 1)[1].split("_")[0]
    return None


class XianyuItemOperator:
    """
    闲鱼商品操作器。
    支持下架、删除等操作，根据账号类型（普通账号/鱼小铺）使用不同的 API。
    """

    # 擦亮 API（mtop.taobao.idle.item.polish 是闲鱼官方擦亮接口，已通过实测定可用）
    # 注：曾经存在的备用 API "mtop.idle.item.polish" 已被官方下线（返回 FAIL_SYS_API_NOT_FOUNDED），故移除
    POLISH_API = "mtop.taobao.idle.item.polish"
    POLISH_VERSION = "1.0"

    # 普通账号 API
    NORMAL_OFF_SHELF_API = "mtop.taobao.idle.item.downshelf"
    NORMAL_OFF_SHELF_VERSION = "2.0"
    NORMAL_DELETE_API = "com.taobao.idle.item.delete"
    NORMAL_DELETE_VERSION = "1.1"

    # 鱼小铺 API
    SELLER_OFF_SHELF_API = "mtop.alibaba.idle.seller.pc.item.offline"
    SELLER_OFF_SHELF_VERSION = "1.0"
    SELLER_DELETE_API = "mtop.alibaba.idle.seller.pc.item.delete"
    SELLER_DELETE_VERSION = "1.0"
    SELLER_SEARCH_API = "mtop.alibaba.idle.seller.pc.common.item.search"
    SELLER_SEARCH_VERSION = "1.0"
    SELLER_UPDATE_API = "mtop.alibaba.idle.seller.pc.item.info.update"
    SELLER_UPDATE_VERSION = "1.0"

    def __init__(self, cookie_str: str, is_fish_shop: bool = False):
        self.cookie_str = cookie_str
        self.is_seller = is_fish_shop
        self.token = extract_token_from_cookie(cookie_str)
        if not self.token:
            raise RuntimeError("Cookie 中缺少 _m_h5_tk，无法签名")

    def _build_sign(self, t_ms: str, data_json: str) -> str:
        """构建 MD5 签名"""
        raw = f"{self.token}&{t_ms}&{APP_KEY}&{data_json}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_url(self, api_name: str, version: str, t_ms: str, sign: str) -> str:
        """构建请求 URL"""
        params = {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": t_ms,
            "sign": sign,
            "v": version,
            "type": "json" if self.is_seller else "originaljson",
            "dataType": "json",
            "accountSite": "xianyu",
            "timeout": "20000",
            "api": api_name,
        }
        if self.is_seller:
            params["sessionOption"] = "AutoLoginOnly"
            params["spm_cnt"] = "a21ybx.item.0.0"

        query = urlencode(params)
        return f"{H5_API_BASE}/{api_name}/{version}/?{query}"

    def _get_headers(self) -> dict:
        """构建请求头"""
        if self.is_seller:
            return {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": self.cookie_str,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Origin": "https://seller.goofish.com",
                "Referer": "https://seller.goofish.com/",
                "idle_site_biz_code": "COMMONPRO",
                "idle_user_group_member_id": "",
            }
        else:
            return {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": self.cookie_str,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Origin": "https://www.goofish.com",
                "Referer": "https://www.goofish.com/",
            }

    def _call_api(self, api_name: str, version: str, data: dict) -> dict:
        """
        调用闲鱼 mtop API。
        返回解析后的 JSON 响应。
        """
        t_ms = str(int(time.time() * 1000))
        data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        sign = self._build_sign(t_ms, data_json)

        url = self._build_url(api_name, version, t_ms, sign)
        headers = self._get_headers()

        resp = requests.post(
            url,
            headers=headers,
            data={"data": data_json},
            timeout=30,
        )
        resp.raise_for_status()

        result = resp.json()

        # 检查响应
        ret = result.get("ret", [])
        ret_msg = ret[0] if isinstance(ret, list) and ret else str(ret)
        if RGV587 in str(ret_msg):
            raise XianyuRiskControlError("商品操作触发平台验证")
        if TOKEN_EXPIRED in str(ret_msg) or TOKEN_EXPIRED_ALIAS in str(ret_msg) or SESSION_EXPIRED in str(ret_msg):
            raise XianyuAuthExpiredError("账号登录状态已过期")
        if not any("SUCCESS" in str(r) for r in ret):
            if any(marker in str(ret) for marker in POLISH_SOFT_SUCCESS_MARKERS):
                raise XianyuAlreadyPolishedError("商品当日已擦亮")
            raise XianyuProviderRejectedError("闲鱼商品操作未被平台接受")

        # 鱼小铺接口额外检查 data.data
        if self.is_seller:
            data_body = result.get("data", {})
            if isinstance(data_body, dict) and data_body.get("data") is False:
                msg = data_body.get("msg", "未知错误")
                if any(marker in str(msg) for marker in POLISH_SOFT_SUCCESS_MARKERS):
                    raise XianyuAlreadyPolishedError("商品当日已擦亮")
                raise XianyuProviderRejectedError("鱼小铺操作未被平台接受")

        return result

    def _call_polish_api(self, item_id: str) -> dict:
        """
        调用擦亮 API。
        Args:
            item_id: 闲鱼商品ID
        Returns:
            API 响应结果
        """
        data = {"itemId": item_id}
        return self._call_api(self.POLISH_API, self.POLISH_VERSION, data)

    def polish(self, item_id: str) -> dict:
        """
        擦亮商品（一键擦亮）。
        返回包含 success、error、need_manual、already_done 等信息的字典。
        - success=True 表示擦亮成功或商品已处于擦亮状态（视为成功）
        - already_done=True 表示商品当天已擦亮过（FAIL_BIZ_IDLEITEM_POLISH_AGAIN）
        - need_manual=True 表示触发风控，需要人工完成滑块验证
        """
        result = {"success": False, "error": None, "need_manual": False, "already_done": False}

        def _needs_manual_retry(error_message: str) -> bool:
            manual_markers = ("RGV587", "需要验证", "FAIL_SYS_USER_VALIDATE")
            return any(marker in error_message for marker in manual_markers)

        def _is_already_polished(error_message: str) -> bool:
            return any(marker in error_message for marker in POLISH_SOFT_SUCCESS_MARKERS)

        # 调用擦亮 API
        try:
            self._call_polish_api(item_id)
            result["success"] = True
            return result
        except XianyuRiskControlError:
            result["error"] = "商品擦亮触发平台验证，请完成人工验证后重试"
            result["errorCode"] = "POLISH_CAPTCHA_REQUIRED"
            result["need_manual"] = True
            return result
        except XianyuAlreadyPolishedError:
            result["success"] = True
            result["already_done"] = True
            result["error"] = None
            return result
        except XianyuAuthExpiredError:
            result["error"] = "账号登录状态已过期，请重新登录"
            result["errorCode"] = "ACCOUNT_AUTH_EXPIRED"
        except XianyuProviderRejectedError:
            result["error"] = "商品擦亮失败，请稍后重试"
            result["errorCode"] = "POLISH_FAILED"
        except RuntimeError as error:
            # 兼容仍以 RuntimeError 表达平台状态的旧调用方。异常正文只在内存中
            # 用于分类，绝不写入返回值、日志或任务状态。
            error_message = error.args[0] if error.args and isinstance(error.args[0], str) else ""
            if _is_already_polished(error_message):
                result["success"] = True
                result["already_done"] = True
                return result
            if _needs_manual_retry(error_message):
                result["error"] = "商品擦亮触发平台验证，请完成人工验证后重试"
                result["errorCode"] = "POLISH_CAPTCHA_REQUIRED"
                result["need_manual"] = True
                return result
            result["error"] = "商品擦亮失败，请稍后重试"
            result["errorCode"] = "POLISH_FAILED"

        return result

    def polish_batch(self, item_ids: list[str]) -> dict[str, dict]:
        """
        批量擦亮商品。
        返回 { item_id: {success, error, need_manual, already_done} } 字典。
        """
        results = {}
        for item_id in item_ids:
            try:
                r = self.polish(item_id)
                results[item_id] = r
                logger.info(
                    "擦亮结果: itemId=%s, success=%s, need_manual=%s, already_done=%s",
                    item_id, r["success"], r["need_manual"], r.get("already_done", False)
                )
            except Exception as e:
                log_service_failure(logger, e, operation="polish_goods_item")
                results[item_id] = {"success": False, "errorCode": "POLISH_FAILED", "error": "商品擦亮失败，请稍后重试", "need_manual": False, "already_done": False}
            # 商品间模拟人工延迟 1~3 秒，避免风控
            time.sleep(random.uniform(1.0, 3.0))
        return results

    def off_shelf(self, item_id: str) -> bool:
        """
        下架商品。
        返回 True 表示操作成功。
        """
        if self.is_seller:
            api = self.SELLER_OFF_SHELF_API
            version = self.SELLER_OFF_SHELF_VERSION
        else:
            api = self.NORMAL_OFF_SHELF_API
            version = self.NORMAL_OFF_SHELF_VERSION

        data = {"itemId": item_id}
        self._call_api(api, version, data)
        return True

    def delete(self, item_id: str) -> bool:
        """
        从闲鱼删除商品。
        返回 True 表示操作成功。
        """
        if self.is_seller:
            api = self.SELLER_DELETE_API
            version = self.SELLER_DELETE_VERSION
        else:
            api = self.NORMAL_DELETE_API
            version = self.NORMAL_DELETE_VERSION

        data = {"itemId": item_id}
        if self.is_seller:
            data["draftId"] = None

        self._call_api(api, version, data)
        return True

    def off_shelf_batch(self, item_ids: list[str]) -> dict[str, bool]:
        """
        批量下架商品。
        返回 { item_id: success_status } 字典。
        """
        results = {}
        for item_id in item_ids:
            try:
                self.off_shelf(item_id)
                results[item_id] = True
                logger.info("下架成功: itemId=%s", item_id)
            except Exception as e:
                log_service_failure(logger, e, operation="off_shelf_goods_item")
                results[item_id] = False
            # 避免触发风控
            time.sleep(random.uniform(0.5, 1.5))
        return results

    def delete_batch(self, item_ids: list[str]) -> dict[str, bool]:
        """
        批量删除商品。
        返回 { item_id: success_status } 字典。
        """
        results = {}
        for item_id in item_ids:
            try:
                self.delete(item_id)
                results[item_id] = True
                logger.info("删除成功: itemId=%s", item_id)
            except Exception as e:
                log_service_failure(logger, e, operation="delete_goods_item")
                results[item_id] = False
            # 避免触发风控
            time.sleep(random.uniform(0.5, 1.5))
        return results

    # ==================== 改价相关方法（仅鱼小铺） ====================

    @staticmethod
    def _seller_search_payload(item_id: str, item_status: str | None = None) -> dict:
        """
        构建卖家工作台商品搜索请求 payload。
        
        Args:
            item_id: 闲鱼商品ID
            item_status: 商品状态筛选，None=不限，'0,-9'=在售，'1'=下架
        """
        search_request = json.dumps({"itemId": item_id}, ensure_ascii=False, separators=(',', ':'))
        payload = {
            "pageNo": 1,
            "pageSize": 20,
            "bizType": "commonPro",
            "searchRequest": search_request,
        }
        if item_status is not None:
            payload["itemStatus"] = item_status
        return payload

    def _find_seller_item(self, item_id: str) -> dict:
        """
        在卖家工作台搜索指定商品，获取完整商品信息（含 SKU 数据）。
        
        按不同状态（不限/在售/下架）搜索，找到即返回。
        改价接口需要商品完整信息（包括 idleItemSkuList），不能仅传 itemId。
        
        Returns:
            商品的完整 JSON 数据节点
            
        Raises:
            RuntimeError: 在所有状态中都未找到该商品
        """
        payloads = [
            self._seller_search_payload(item_id, None),       # 不限状态
            self._seller_search_payload(item_id, "0,-9"),     # 在售/出售中
            self._seller_search_payload(item_id, "1"),        # 已下架
        ]

        for payload in payloads:
            try:
                response = self._call_api(self.SELLER_SEARCH_API, self.SELLER_SEARCH_VERSION, payload)
                ret = response.get("ret", [])
                if not any("SUCCESS" in str(r) for r in ret):
                    continue

                data_body = response.get("data", {})
                if not isinstance(data_body, dict):
                    continue

                item_list = data_body.get("data", {})
                if isinstance(item_list, dict):
                    search_response_list = item_list.get("itemSearchResponseList", [])
                    if isinstance(search_response_list, list):
                        for item in search_response_list:
                            if isinstance(item, dict) and str(item.get("itemId", "")) == str(item_id):
                                logger.info("在卖家工作台找到商品: itemId=%s", item_id)
                                return item
            except Exception as e:
                log_service_failure(logger, e, operation="search_seller_goods", level=logging.DEBUG)
                continue

        raise XianyuProviderRejectedError("鱼小铺工作台未找到待改价商品")

    @staticmethod
    def _safe_quantity(seller_item: dict) -> int:
        """安全读取商品库存，兜底返回 0"""
        try:
            raw = seller_item.get("quantity", 0)
            if raw is None:
                return 0
            return int(raw)
        except (ValueError, TypeError):
            return 0

    def _build_seller_price_update_payload(self, seller_item: dict, price: str) -> dict:
        """
        构建卖家工作台改价请求 payload。
        
        有 SKU 的商品需要同时更新每个 SKU 的价格（itemSkuListStr），
        无 SKU 的商品直接设置 quantity 和 price。
        """
        item_id = seller_item.get("itemId", "")
        if not item_id:
            raise RuntimeError("卖家商品数据中缺少 itemId")

        data = {"itemId": item_id}

        sku_list = seller_item.get("idleItemSkuList", [])
        if isinstance(sku_list, list) and len(sku_list) > 0:
            # 有SKU：构建 itemSkuListStr
            items = []
            for sku in sku_list:
                if not isinstance(sku, dict):
                    continue
                sku_id = sku.get("skuId", "")
                if not sku_id:
                    continue
                items.append({
                    "skuId": str(sku_id),
                    "quantity": self._safe_quantity(sku),
                    "price": price,
                })
            if items:
                data["itemSkuListStr"] = json.dumps(items, ensure_ascii=False, separators=(',', ':'))
                return data

        # 无SKU：直接设置库存和价格
        data["quantity"] = self._safe_quantity(seller_item)
        data["price"] = price
        return data

    def update_price(self, item_id: str, price: str) -> bool:
        """
        修改闲鱼商品价格（仅鱼小铺账号支持）。
        
        流程：
        1. 在卖家工作台搜索商品，获取完整信息（含 SKU）
        2. 构建改价请求 payload（有SKU则更新每个SKU的价格）
        3. 调用卖家工作台改价 API
        
        Args:
            item_id: 闲鱼商品ID
            price: 新价格（字符串，如 "99.99"）
            
        Returns:
            True 表示操作成功
            
        Raises:
            RuntimeError: 如果不是鱼小铺账号、未找到商品或 API 调用失败
        """
        if not self.is_seller:
            raise RuntimeError("当前账号不是鱼小铺，无法改价")

        # Step 1: 在卖家工作台搜索商品
        seller_item = self._find_seller_item(item_id)

        # Step 2: 构建改价请求参数
        payload = self._build_seller_price_update_payload(seller_item, price)

        # Step 3: 调用改价 API
        self._call_api(self.SELLER_UPDATE_API, self.SELLER_UPDATE_VERSION, payload)
        logger.info("商品改价成功: itemId=%s, newPrice=%s", item_id, price)
        return True

    def update_price_batch(self, item_ids: list[str], price: str) -> dict[str, bool]:
        """
        批量修改商品价格。
        返回 { item_id: success_status } 字典。
        """
        results = {}
        for item_id in item_ids:
            try:
                self.update_price(item_id, price)
                results[item_id] = True
                logger.info("批量改价成功: itemId=%s, price=%s", item_id, price)
            except Exception as e:
                log_service_failure(logger, e, operation="update_goods_price")
                results[item_id] = False
            time.sleep(random.uniform(1.0, 3.0))
        return results


class XianyuItemPublisher:
    """
    闲鱼商品发布器（增强版）。
    流程：
      Step 1: 类目推荐 (mtop.taobao.idle.kgraph.property.recommend)
      Step 2: 构建发布数据 (mtop.idle.pc.idleitem.publish)
      Step 3: 发布调用与响应解析

    API: mtop.idle.pc.idleitem.publish v1.0
    """

    PUBLISH_API = "mtop.idle.pc.idleitem.publish"
    PUBLISH_VERSION = "1.0"

    CATEGORY_RECOMMEND_API = "mtop.taobao.idle.kgraph.property.recommend"
    CATEGORY_RECOMMEND_VERSION = "2.0"

    # 图片上传 API（闲鱼 stream-upload）
    IMAGE_UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
    IMAGE_UPLOAD_APPKEY = "xy_chat"

    # 默认类目（软件安装包/序列号/激活码）
    DEFAULT_CAT_ID = "50025461"
    DEFAULT_CAT_NAME = "软件安装包/序列号/激活码"
    DEFAULT_CHANNEL_CAT_ID = "201449620"
    DEFAULT_TB_CAT_ID = "50003316"

    def __init__(
        self,
        cookie_str: str,
        tenant_id: int,
        *,
        asset_verifier: Callable[[int, str, str], int] = _verify_active_storage_asset,
        remote_image_loader: Callable[[str], bytes] = _download_public_image_sync,
    ):
        self.cookie_str = cookie_str
        self.tenant_id = int(tenant_id)
        if self.tenant_id <= 0:
            raise ValueError("tenant_id must be positive")
        self._asset_verifier = asset_verifier
        self._remote_image_loader = remote_image_loader
        self.token = extract_token_from_cookie(cookie_str)
        if not self.token:
            raise RuntimeError("Cookie 中缺少 _m_h5_tk，无法签名")

    # ---- 签名 & 请求 ----

    def _build_sign(self, t_ms: str, data_json: str) -> str:
        raw = f"{self.token}&{t_ms}&{APP_KEY}&{data_json}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_url(self, api_name: str, version: str, t_ms: str, sign: str) -> str:
        params = {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": t_ms,
            "sign": sign,
            "v": version,
            "type": "originaljson",
            "dataType": "json",
            "timeout": "30000",
            "api": api_name,
            "spm_cnt": "a21ybx.item.0.0",
        }
        query = urlencode(params)
        return f"{H5_API_BASE}/{api_name}/{version}/?{query}"

    def _get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": self.cookie_str,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
        }

    def _call_api(self, api_name: str, version: str, data: dict) -> dict:
        """统一调用闲鱼 MTop API"""
        t_ms = str(int(time.time() * 1000))
        data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        sign = self._build_sign(t_ms, data_json)

        url = self._build_url(api_name, version, t_ms, sign)
        headers = self._get_headers()

        logger.info(
            "调用闲鱼 API: api=%s version=%s dataKeys=%s dataBytes=%d",
            api_name,
            version,
            sorted(str(key) for key in data.keys()),
            len(data_json.encode("utf-8")),
        )

        resp = requests.post(url, headers=headers, data={"data": data_json}, timeout=60)
        resp.raise_for_status()

        result = resp.json()
        ret = result.get("ret", [])
        ret_msg = ret[0] if isinstance(ret, list) and ret else str(ret)

        if RGV587 in str(ret_msg):
            raise RuntimeError("触发风控(RGV587)，请稍后再试")
        if TOKEN_EXPIRED in str(ret_msg) or TOKEN_EXPIRED_ALIAS in str(ret_msg) or SESSION_EXPIRED in str(ret_msg):
            raise RuntimeError("登录已过期，请重新登录闲鱼账号")

        response_data = result.get("data")
        api_success = "SUCCESS" in str(ret_msg)
        data_keys = sorted(str(key) for key in response_data.keys()) if isinstance(response_data, dict) else []
        logger.info(
            "闲鱼 API 返回 api=%s success=%s dataKeys=%s",
            api_name,
            api_success,
            data_keys,
        )
        return result

    # ---- 图片压缩 ----

    @staticmethod
    def _compress_image(img_data: bytes, max_size: int = 5 * 1024 * 1024) -> bytes:
        """
        压缩图片：缩放到 ≤1920×1920，转 JPEG，文件 ≤ max_size。
        参考闲鱼平台图片上传要求。
        """
        try:
            img_data = validate_image_bytes(img_data, max_bytes=max_size).content
            img = Image.open(io.BytesIO(img_data))

            # 转换为 RGB（去除 alpha 通道）
            if img.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 尺寸缩放：超过 1920px 时等比缩小
            max_width, max_height = 1920, 1920
            width, height = img.size
            if width > max_width or height > max_height:
                scale = min(max_width / width, max_height / height)
                new_size = (int(width * scale), int(height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info("图片缩放: %dx%d → %dx%d", width, height, new_size[0], new_size[1])

            # JPEG 压缩，逐步降低质量直到文件 ≤ max_size
            quality = 85
            for attempt in range(3):
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=quality, optimize=True)
                compressed = out.getvalue()
                if len(compressed) <= max_size:
                    logger.info("图片压缩完成: %d bytes (quality=%d)", len(compressed), quality)
                    return validate_image_bytes(compressed, max_bytes=max_size).content
                quality = max(30, quality - 25)
                logger.info("图片仍过大 %d bytes, 降低 quality 至 %d", len(compressed), quality)

            # 最后一次尝试
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=quality, optimize=True)
            compressed = out.getvalue()
            logger.info("图片压缩完成(最低质量): %d bytes (quality=%d)", len(compressed), quality)
            return validate_image_bytes(compressed, max_bytes=max_size).content

        except Exception as e:
            log_service_failure(logger, e, operation="compress_publish_image", level=logging.WARNING)
            raise ValueError("publish image content is invalid") from e

    def _read_publish_image(self, image_url: str) -> bytes:
        raw_url = str(image_url or "").strip()
        if raw_url.startswith("/uploads/") or raw_url.startswith("uploads/"):
            normalized_url = raw_url if raw_url.startswith("/") else f"/{raw_url}"
            parsed = urlsplit(normalized_url)
            if parsed.query or parsed.fragment or parsed.netloc or parsed.scheme:
                raise RuntimeError("商品图片地址无效，请重新上传图片后再发布")
            decoded_path = unquote(parsed.path)
            if decoded_path != parsed.path or "\\" in decoded_path:
                raise RuntimeError("商品图片地址无效，请重新上传图片后再发布")
            expected_prefix = f"/uploads/images/tenant-{self.tenant_id}/"
            if not decoded_path.startswith(expected_prefix):
                raise RuntimeError("商品图片不属于当前租户，请重新上传图片后再发布")

            uploads_root = os.path.realpath(
                os.path.join(os.path.dirname(__file__), "../../uploads")
            )
            filesystem_key = decoded_path[len("/uploads/"):]
            asset_storage_key = decoded_path[len("/uploads/images/"):]
            local_path = os.path.realpath(os.path.join(uploads_root, *filesystem_key.split("/")))
            if os.path.commonpath([uploads_root, local_path]) != uploads_root:
                raise RuntimeError("商品图片路径非法，请重新上传图片后再发布")
            try:
                expected_size = self._asset_verifier(
                    self.tenant_id, decoded_path, asset_storage_key
                )
            except ValueError as exc:
                # 资产校验失败（未入库/已清理/不属于租户）
                logger.warning(
                    "publish image asset verification failed errorType=%s",
                    type(exc).__name__,
                )
                raise RuntimeError("商品图片已失效或不存在，请重新上传图片后再发布") from exc
            except Exception as exc:
                log_service_failure(logger, exc, operation="verify_publish_image_asset", level=logging.WARNING)
                raise RuntimeError("商品图片校验失败，请稍后重试或重新上传图片") from exc
            if not os.path.isfile(local_path):
                raise RuntimeError("商品图片文件不存在，请重新上传图片后再发布")
            with open(local_path, "rb") as file:
                img_data = file.read(MAX_IMAGE_BYTES + 1)
            if len(img_data) != expected_size:
                raise RuntimeError("商品图片与存储记录不一致，请重新上传图片后再发布")
            try:
                return validate_image_bytes(img_data).content
            except ValueError as exc:
                raise RuntimeError("商品图片内容无效，请更换图片后重试") from exc

        try:
            return self._remote_image_loader(raw_url)
        except ValueError as exc:
            raise RuntimeError("远程商品图片无法安全下载，请改用本地上传后再发布") from exc

    # ---- 图片上传到闲鱼 CDN ----

    @staticmethod
    def _extract_publish_cdn_url(response: Any) -> str:
        """
        从 stream-upload 响应中提取 CDN URL。

        兼容多种返回格式，并正确处理 Python 条件表达式优先级
        （`a or b if c else d` 不等于 `a or (b if c else d)`）。
        """
        def _pick_url(node: Any) -> str:
            if isinstance(node, str):
                text = node.strip()
                return text if text.startswith(("http://", "https://", "//")) else ""
            if not isinstance(node, dict):
                return ""
            for key in ("url", "cdnUrl", "cdn_url", "fileUrl", "file_url", "picUrl", "imageUrl"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""

        if isinstance(response, list) and response:
            for item in response:
                found = _pick_url(item)
                if found:
                    return found
            return ""

        if not isinstance(response, dict):
            return ""

        # 顶层 url / 常见嵌套容器（必须给三元表达式加括号，避免 or/if 优先级吞掉顶层 url）
        data = response.get("data")
        obj = response.get("object")
        result = response.get("result")
        found = (
            _pick_url(response)
            or (_pick_url(data) if isinstance(data, dict) else "")
            or (_pick_url(obj) if isinstance(obj, dict) else "")
            or (_pick_url(result) if isinstance(result, dict) else "")
        )
        if found:
            return found

        # 任意一层 list 容器
        for value in response.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                found = _pick_url(value[0])
                if found:
                    return found

        # 兜底：从整段 JSON 里捞 alicdn / goofish 图片地址
        response_str = json.dumps(response, ensure_ascii=False)
        match = re.search(
            r'https?://(?:img|gw|g\.|pic)\.alicdn\.com[^"\'\\\s,]+|'
            r'https?://[^"\'\\\s,]*\.(?:alicdn|goofish)\.com[^"\'\\\s,]+|'
            r'//(?:img|gw)\.alicdn\.com[^"\'\\\s,]+',
            response_str,
        )
        return match.group(0) if match else ""

    @staticmethod
    def _normalize_cdn_url(cdn_url: str) -> str:
        """将协议相对地址规范为 https，并拒绝非公网 CDN。"""
        text = str(cdn_url or "").strip()
        if not text:
            raise RuntimeError("图片上传未返回 CDN 地址")
        if text.startswith("//"):
            text = "https:" + text
        elif text.startswith("http://"):
            text = "https://" + text[len("http://"):]
        parsed = urlsplit(text)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise RuntimeError("图片上传返回了不安全的 CDN 地址")
        host = (parsed.hostname or "").lower()
        # 闲鱼/淘宝 CDN 常见域名；其它 https 公网地址也允许（部分账号返回自定义加速域）
        if not host or " " in host:
            raise RuntimeError("图片上传返回了不安全的 CDN 地址")
        return text

    @staticmethod
    def _response_host(resp: requests.Response) -> str:
        final_url = str(getattr(resp, "url", "") or "")
        location = str((getattr(resp, "headers", None) or {}).get("Location") or "")
        for candidate in (final_url, location):
            host = (urlsplit(candidate).hostname or "").lower()
            if host:
                return host
        return ""

    @classmethod
    def _is_passport_redirect(cls, resp: requests.Response) -> bool:
        """仅当明确落到 passport 登录域时才视为登录跳转（禁止用 /login 子串误判）。"""
        host = cls._response_host(resp)
        return host in {
            "passport.goofish.com",
            "passport.taobao.com",
            "login.taobao.com",
            "login.m.taobao.com",
        }

    def _apply_refreshed_cookie(self, cookie_str: str) -> None:
        self.cookie_str = cookie_str
        refreshed_token = extract_token_from_cookie(cookie_str)
        if refreshed_token:
            self.token = refreshed_token

    def _mtop_session_alive(self) -> bool:
        """
        用轻量 MTOP 探测当前 cookie 是否仍可用于平台业务。

        商机搜索/账号页 Cookie 状态都走 MTOP；stream-upload 失败时不能单凭 HTTP 状态
        判定“登录已失效”，否则会出现搜索正常却提示重新登录的矛盾。
        """
        try:
            t_ms = str(int(time.time() * 1000))
            data_json = "{}"
            sign = self._build_sign(t_ms, data_json)
            url = self._build_url(
                "mtop.taobao.idlemessage.pc.loginuser.get",
                "1.0",
                t_ms,
                sign,
            )
            headers = self._get_headers()
            resp = requests.post(url, headers=headers, data={"data": data_json}, timeout=15)
            if resp.status_code >= 500:
                # 平台抖动：无法证明登录失效
                return True
            result = resp.json()
            ret = result.get("ret", [])
            ret_msg = str(ret[0] if isinstance(ret, list) and ret else ret)
            if any(
                code in ret_msg
                for code in (TOKEN_EXPIRED, TOKEN_EXPIRED_ALIAS, SESSION_EXPIRED, "FAIL_SYS_USER_VALIDATE")
            ):
                return False
            # SUCCESS 或其它业务码都视为 cookie 仍可用；只有明确过期才算失效
            return True
        except Exception as exc:
            log_service_failure(
                logger, exc, operation="probe_mtop_session_for_upload", level=logging.WARNING
            )
            # 探测失败时默认“未证明失效”，避免误伤正常账号
            return True

    def _raise_upload_failure(self, technical: str) -> None:
        """上传失败时结合 MTOP 探活给出准确中文错误，避免误报登录失效。"""
        if self._mtop_session_alive():
            raise RuntimeError(
                "闲鱼图片上传失败，但账号登录状态正常（搜索等功能可用）。"
                "请稍后重试或更换图片；若持续失败请检查网络/代理后重试"
            )
        raise RuntimeError("闲鱼登录已失效，请到「账号管理」重新登录后再发布")

    def upload_image_to_xianyu(self, image_url: str) -> str:
        """
        上传单张图片到闲鱼 CDN。

        实现与自动分类/聊天发图共用同一 stream-upload 通道；
        不再把 401/403 或 HTML 里出现 login 字样直接判成 Cookie 失效。
        """
        cookie_for_upload = self.cookie_str
        last_error: Exception | None = None
        configured_upload_url = (settings.xianyu_mtop_upload_url or "").strip()
        default_upload_url = (
            f"{self.IMAGE_UPLOAD_URL}?floderId=0&appkey={self.IMAGE_UPLOAD_APPKEY}"
        )
        upload_url = configured_upload_url or default_upload_url

        for attempt in range(2):
            try:
                img_data = self._compress_image(self._read_publish_image(image_url))
                filename = f"publish_{int(time.time() * 1000)}.jpg"
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Origin": "https://www.goofish.com",
                    "Referer": "https://www.goofish.com/",
                    # Cookie 头完整透传：与浏览器一致，避免 CookieJar domain 漏带
                    "Cookie": cookie_for_upload,
                }

                session = requests.Session()
                for part in cookie_for_upload.split(";"):
                    part = part.strip()
                    if "=" not in part:
                        continue
                    key, _, value = part.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        session.cookies.set(key, value, domain=".goofish.com")

                resp = session.post(
                    upload_url,
                    headers=headers,
                    files={"file": (filename, img_data, "image/jpeg")},
                    timeout=60,
                    allow_redirects=True,
                )

                logger.info(
                    "图片上传 HTTP 返回 status=%s finalHost=%s contentType=%s",
                    resp.status_code,
                    self._response_host(resp) or "-",
                    (resp.headers or {}).get("Content-Type", ""),
                )

                # 明确跳到 passport：先刷新 _m_h5_tk 重试；仍失败再结合 MTOP 探活报错
                if self._is_passport_redirect(resp):
                    if attempt == 0:
                        logger.warning("图片上传跳转到 passport，尝试刷新 _m_h5_tk 后重试")
                        cookie_for_upload = _refresh_m_h5_tk(cookie_for_upload)
                        self._apply_refreshed_cookie(cookie_for_upload)
                        continue
                    self._raise_upload_failure("passport_redirect")

                if resp.status_code >= 400:
                    # 401/403 可能是 stream-upload 风控/签名，不一定是 Cookie 全局失效
                    if attempt == 0 and resp.status_code in (401, 403):
                        cookie_for_upload = _refresh_m_h5_tk(cookie_for_upload)
                        self._apply_refreshed_cookie(cookie_for_upload)
                        continue
                    logger.warning(
                        "图片上传 HTTP 失败 status=%s bodyLen=%d",
                        resp.status_code,
                        len(resp.text or ""),
                    )
                    self._raise_upload_failure(f"http_{resp.status_code}")

                try:
                    result = resp.json()
                except ValueError as exc:
                    logger.warning(
                        "图片上传响应不是 JSON status=%s contentType=%s bodyLen=%d",
                        resp.status_code,
                        (resp.headers or {}).get("Content-Type", ""),
                        len(resp.text or ""),
                    )
                    if attempt == 0:
                        time.sleep(1)
                        continue
                    raise RuntimeError("图片上传失败，闲鱼服务返回了无法识别的内容，请稍后重试或更换图片") from exc

                logger.info(
                    "图片上传响应 responseType=%s responseKeys=%s",
                    type(result).__name__,
                    sorted(str(key) for key in result.keys()) if isinstance(result, dict) else [],
                )

                cdn_url = self._extract_publish_cdn_url(result)
                if not cdn_url:
                    logger.warning(
                        "图片上传未解析到 CDN URL responseKeys=%s",
                        sorted(str(key) for key in result.keys()) if isinstance(result, dict) else [],
                    )
                    if attempt == 0:
                        time.sleep(1)
                        continue
                    raise RuntimeError("图片上传失败，未能获取闲鱼图片地址，请稍后重试或更换图片")

                normalized = self._normalize_cdn_url(cdn_url)
                logger.info("图片上传到闲鱼 CDN 成功")
                return normalized

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning("图片上传超时 (attempt %d/2)", attempt + 1)
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise RuntimeError("图片上传超时") from e
            except RuntimeError as e:
                last_error = e
                log_service_failure(logger, e, operation="upload_publish_image", level=logging.WARNING)
                message = str(e)
                # 已分类的用户错误直接抛出
                if any(token in message for token in (
                    "登录已失效",
                    "登录状态正常",
                    "商品图片",
                    "远程商品图片",
                    "图片上传失败",
                    "超时",
                )):
                    raise
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise
            except Exception as e:
                last_error = e
                log_service_failure(logger, e, operation="upload_publish_image", level=logging.WARNING)
                if attempt == 0:
                    time.sleep(1)
                    continue
                self._raise_upload_failure(type(e).__name__)

        if last_error is not None:
            raise RuntimeError("图片上传失败") from last_error
        raise RuntimeError("图片上传失败")

    def upload_images_to_xianyu(self, image_urls: list[str]) -> list[str]:
        """批量上传图片到闲鱼 CDN"""
        xianyu_urls = []
        for url in image_urls:
            result_url = self.upload_image_to_xianyu(url)
            xianyu_urls.append(result_url)
            time.sleep(random.uniform(0.3, 0.8))
        return xianyu_urls

    # ---- Step 1: 类目推荐 ----

    def category_recommend(self, title: str, desc: str, image_urls: list[str]) -> dict:
        """
        调用类目推荐 API 获取推荐类目和标签。

        返回:
        {
            "catId": str,
            "catName": str,
            "channelCatId": str,
            "tbCatId": str,
            "cardList": list[dict],   # 推荐标签，可用于 itemLabelExtList
        }
        """
        try:
            data = {
                "itemInfo": {
                    "title": title,
                    "desc": desc,
                    "images": image_urls[:3],  # 最多传 3 张
                }
            }

            logger.info("调用类目推荐 API titleLen=%d", len(title))
            result = self._call_api(self.CATEGORY_RECOMMEND_API, self.CATEGORY_RECOMMEND_VERSION, data)

            ret = result.get("ret", [])
            ret_msg = ret[0] if isinstance(ret, list) and ret else str(ret)

            if "SUCCESS" in ret_msg:
                data_body = result.get("data", {})

                # 解析推荐类目
                category_predict = data_body.get("categoryPredictResult", [])
                recommended_cat = {}
                if category_predict and isinstance(category_predict, list) and len(category_predict) > 0:
                    best = category_predict[0]
                    recommended_cat = {
                        "catId": str(best.get("catId", "")),
                        "catName": best.get("catName", ""),
                        "channelCatId": str(best.get("channelCatId", "")),
                        "tbCatId": str(best.get("tbCatId", "")),
                    }

                # 解析推荐标签
                card_list = data_body.get("cardList", [])
                if isinstance(card_list, dict):
                    # 有时 cardList 可能是 dict 而非 list
                    card_list = [card_list]

                logger.info(
                    "类目推荐成功: cat=%s, tags=%d",
                    recommended_cat.get("catName", ""),
                    len(card_list),
                )

                return {
                    "recommended": True,
                    "catId": recommended_cat.get("catId", ""),
                    "catName": recommended_cat.get("catName", ""),
                    "channelCatId": recommended_cat.get("channelCatId", ""),
                    "tbCatId": recommended_cat.get("tbCatId", ""),
                    "cardList": card_list,
                }

            log_service_failure(
                logger,
                None,
                operation="recommend_goods_category",
                level=logging.WARNING,
                error_type="ProviderRejected",
            )
            return {"recommended": False}

        except Exception as e:
            log_service_failure(logger, e, operation="recommend_goods_category", level=logging.WARNING)
            return {"recommended": False}

    def _build_item_label_ext_list(self, card_list: list) -> list:
        """将类目推荐返回的 cardList 转换为 itemLabelExtList"""
        if not card_list:
            return []

        labels = []
        for card in card_list:
            if not isinstance(card, dict):
                continue
            label = {
                "channelCateName": card.get("channelCateName", ""),
                "channelCateId": str(card.get("channelCateId", "")),
                "tbCatId": str(card.get("tbCatId", "")),
                "labelType": card.get("labelType", "common"),
                "propertyId": str(card.get("propertyId", "-10000")),
                "propertyName": card.get("propertyName", "分类"),
                "text": card.get("text", ""),
                "properties": card.get("properties", ""),
                "from": card.get("from", "newPublishChoice"),
                "labelFrom": card.get("labelFrom", "newPublish"),
                "isUserClick": card.get("isUserClick", "1"),
            }
            labels.append(label)

        return labels

    # ---- Step 2: 构建发布数据 ----

    def _build_publish_data(self, item_data: dict, category_info: dict,
                            xianyu_image_urls: list[str]) -> dict:
        """构建完整的发布数据结构（参考 MTop 协议）"""

        # 基础字段
        # ★ 价格清洗：商品来源可能携带 ¥/￥/RMB/元 等货币符号或单位（例如店铺爬取保留原格式 ¥7），
        #   直接 float() 会抛 ValueError。这里统一提取数字部分。
        price_in_cent = _safe_price_to_cent(item_data.get("price", 0))
        quantity = int(item_data.get("quantity", 1))
        if quantity < 1:
            quantity = 1
        if quantity > 9999:
            quantity = 9999

        # ---- 图片信息 ----
        image_info_list = []
        for idx, url in enumerate(xianyu_image_urls):
            image_info_list.append({
                "url": url,
                "heightSize": 0,
                "widthSize": 0,
                "major": idx == 0,
                "type": 0,
                "status": "done",
                "isQrCode": False,
                "extraInfo": {"isH": "false", "isT": "false", "raw": "false"},
            })

        # ---- 标题与描述 ----
        item_text_dto = {
            "desc": item_data.get("desc", ""),
            "title": item_data.get("title", ""),
            "titleDescSeparate": False,
        }

        # ---- 类目 ----
        cat_id = category_info.get("catId") or self.DEFAULT_CAT_ID
        cat_name = category_info.get("catName") or self.DEFAULT_CAT_NAME
        channel_cat_id = category_info.get("channelCatId") or self.DEFAULT_CHANNEL_CAT_ID
        tb_cat_id = category_info.get("tbCatId") or self.DEFAULT_TB_CAT_ID

        item_cat_dto = {
            "catId": cat_id,
            "catName": cat_name,
            "channelCatId": channel_cat_id,
            "tbCatId": tb_cat_id,
        }

        # ---- 推荐标签 ----
        card_list = category_info.get("cardList", [])
        item_label_ext_list = self._build_item_label_ext_list(card_list)

        # ---- 价格 ----
        item_price_dto = {
            "priceInCent": str(price_in_cent),
        }
        orig_price = item_data.get("origPrice")
        if orig_price:
            try:
                orig_price_in_cent = _safe_price_to_cent(orig_price)
                item_price_dto["origPriceInCent"] = str(orig_price_in_cent)
            except (ValueError, TypeError):
                pass

        # ---- 服务协议（全部关闭） ----
        user_rights_protocols = [
            {"enable": False, "serviceCode": "FAST_DELIVERY_48_HOUR"},
            {"enable": False, "serviceCode": "FAST_DELIVERY_24_HOUR"},
            {"enable": False, "serviceCode": "VIRTUAL_NONCONFORMITY_FREE_REFUND_SERVICE"},
            {"enable": False, "serviceCode": "SKILL_PLAY_NO_MIND"},
        ]

        # ---- 运费 ----
        shipping_mode = item_data.get("shippingMode", "free")
        support_self_pick = item_data.get("supportSelfPick", False)

        if shipping_mode == "none":
            # 无需邮寄
            item_post_fee_dto = {
                "supportFreight": False,
                "templateId": "0",
            }
        elif shipping_mode == "fixed":
            # 一口价运费
            post_fee = item_data.get("postFee", 0)
            post_price_in_cent = str(_safe_price_to_cent(post_fee)) if post_fee else "0"
            item_post_fee_dto = {
                "canFreeShipping": False,
                "supportFreight": True,
                "onlyTakeSelf": support_self_pick,
                "templateId": "0",
                "postPriceInCent": post_price_in_cent,
            }
        else:
            # 包邮（默认）
            item_post_fee_dto = {
                "canFreeShipping": True,
                "supportFreight": True,
                "onlyTakeSelf": support_self_pick,
            }

        # ---- 地址 ----
        location = item_data.get("location", {})
        division_id = location.get("divisionId", "")
        try:
            division_id = int(division_id)
        except (ValueError, TypeError):
            division_id = 0

        item_addr_dto = {
            "prov": location.get("prov", ""),
            "city": location.get("city", ""),
            "area": location.get("area", ""),
            "divisionId": division_id,
            "gps": location.get("gps", ""),
            "poiId": location.get("poiId", ""),
            "poiName": location.get("poiName", ""),
        }

        # ---- SKU（至少一个空属性 SKU） ----
        # ★ 防御：价格 <= 0 时直接抛出本地错误，避免发送到平台后被 FAIL_BIZ_SKU_PRICE_ILLEGAL 拒绝
        #   单规格商品也会构造一个空属性 SKU，priceInCent=0 会被闲鱼判定为多规格价格非法
        if price_in_cent <= 0:
            raise ValueError(
                "商品价格未设置或为 0，无法发布（闲鱼会以 FAIL_BIZ_SKU_PRICE_ILLEGAL 拒绝）"
            )
        item_sku_list = []
        sku_list = item_data.get("skuList", [])
        if sku_list:
            for sku in sku_list:
                property_list = []
                if sku.get("propertyKey") and sku.get("propertyValue"):
                    property_list.append({
                        "propertyText": sku.get("propertyKey", ""),
                        "valueText": sku.get("propertyValue", ""),
                    })
                if sku.get("secondPropertyKey") and sku.get("secondPropertyValue"):
                    property_list.append({
                        "propertyText": sku["secondPropertyKey"],
                        "valueText": sku["secondPropertyValue"],
                    })
                sku_entry = {
                    "priceInCent": str(_safe_price_to_cent(sku.get("price", 0))) if sku.get("price") else str(price_in_cent),
                    "quantity": str(int(sku.get("quantity", 1))),
                    "propertyList": property_list,
                }
                item_sku_list.append(sku_entry)
        else:
            # 无多规格：一个空属性 SKU
            item_sku_list.append({
                "priceInCent": str(price_in_cent),
                "quantity": str(quantity),
                "propertyList": [],
            })

        # ---- 商品属性 ----
        item_properties = item_data.get("itemProperties", [])

        # 组装最终数据
        publish_data = {
            "freebies": False,
            "itemTypeStr": "b",
            "quantity": str(quantity),
            "simpleItem": "true",
            "defaultPrice": False,
            "uniqueCode": str(int(time.time() * 1000)),
            "sourceId": "pcMainPublish",
            "bizcode": "pcMainPublish",
            "publishScene": "pcMainPublish",
            "imageInfoDOList": image_info_list,
            "itemTextDTO": item_text_dto,
            "itemCatDTO": item_cat_dto,
            "itemPriceDTO": item_price_dto,
            "itemPostFeeDTO": item_post_fee_dto,
            "itemAddrDTO": item_addr_dto,
            "userRightsProtocols": user_rights_protocols,
            "itemSkuList": item_sku_list,
        }

        # 有推荐标签时添加
        if item_label_ext_list:
            publish_data["itemLabelExtList"] = item_label_ext_list

        # 有商品属性时添加
        if item_properties:
            publish_data["itemProperties"] = item_properties

        return publish_data

    # ---- Step 3: 发布 ----

    def publish(self, item_data: dict) -> dict:
        """
        三步发布商品：

        1. 类目推荐：根据标题/描述/图片获取推荐类目和标签
        2. 图片上传：将图片上传到闲鱼 CDN
        3. 构建数据并调用发布 API
        """
        # ---- Step 0: 刷新 session，避免因 session 过期导致发布失败 ----
        logger.info("Step 0/3: 刷新 session / _m_h5_tk")
        refreshed_cookie = _refresh_m_h5_tk(self.cookie_str)
        if refreshed_cookie != self.cookie_str:
            self.cookie_str = refreshed_cookie
            self.token = extract_token_from_cookie(refreshed_cookie)
            logger.info("Session 已刷新 tokenPresent=%s", bool(self.token))

        title = item_data.get("title", "")
        desc = item_data.get("desc", "")
        image_urls = item_data.get("imageUrls", [])

        if not image_urls:
            raise RuntimeError("至少需要一张商品图片")

        # ---- Step 1: 类目推荐 ----
        logger.info("Step 1/3: 类目推荐 titleLen=%d", len(title))
        recommend_result = self.category_recommend(title, desc, image_urls)

        if recommend_result.get("recommended"):
            category_info = recommend_result
            logger.info("类目推荐成功: %s (catId=%s)", category_info["catName"], category_info["catId"])
        else:
            # 回退到手动指定的类目
            logger.info("类目推荐失败，使用手动指定类目")
            user_cat = item_data.get("category", {})
            category_info = {
                "recommended": False,
                "catId": user_cat.get("catId") or self.DEFAULT_CAT_ID,
                "catName": user_cat.get("catName") or self.DEFAULT_CAT_NAME,
                "channelCatId": user_cat.get("channelCatId") or self.DEFAULT_CHANNEL_CAT_ID,
                "tbCatId": user_cat.get("tbCatId") or self.DEFAULT_TB_CAT_ID,
                "cardList": [],
            }

        # ---- Step 2: 图片上传到闲鱼 CDN ----
        logger.info("Step 2/3: 图片上传 - %d 张", len(image_urls))
        xianyu_image_urls = self.upload_images_to_xianyu(image_urls)

        # ---- Step 3: 构建发布数据并调用 API ----
        logger.info("Step 3/3: 构建发布数据并调用发布 API")
        publish_data = self._build_publish_data(item_data, category_info, xianyu_image_urls)

        logger.info(
            "开始发布商品 titleLen=%d price=%s quantity=%s",
            len(title),
            publish_data["itemPriceDTO"]["priceInCent"],
            quantity := publish_data["quantity"],
        )

        result = self._call_api(self.PUBLISH_API, self.PUBLISH_VERSION, publish_data)

        # ---- 解析响应 ----
        ret = result.get("ret", [])
        ret_msg = ret[0] if isinstance(ret, list) and ret else str(ret)

        if "SUCCESS" in ret_msg:
            data_body = result.get("data", {})
            if isinstance(data_body, dict):
                item_id = (
                    data_body.get("itemId", "")
                    or data_body.get("itemIdStr", "")
                    or data_body.get("idleItemId", "")
                )
                if isinstance(item_id, (int, float)):
                    item_id = str(int(item_id))

                if not item_id:
                    # 尝试从 data.data 中取
                    nested = data_body.get("data", {})
                    if isinstance(nested, dict):
                        item_id = str(nested.get("itemId", ""))

            logger.info("商品发布成功 itemId=%s titleLen=%d", item_id, len(title))
            return {
                "success": True,
                "itemId": item_id,
                "itemUrl": f"https://www.goofish.com/item/{item_id}" if item_id else "",
                "message": "发布成功",
            }

        log_service_failure(
            logger,
            None,
            operation="publish_goods",
            level=logging.WARNING,
            error_type="ProviderRejected",
        )
        # 闲鱼返回的 ret 格式通常为 "FAIL_XXX::中文描述"，把真实原因带给上层
        # 避免前端只看到"平台暂未接受该商品"而不知具体违规点
        friendly = _explain_publish_rejection(ret_msg, result.get("data"))
        return {
            "success": False,
            "itemId": "",
            "errorCode": "PUBLISH_PROVIDER_REJECTED",
            "message": friendly,
            "retMsg": ret_msg,
        }
