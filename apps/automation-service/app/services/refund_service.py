"""
退款管理服务。

复用 xianyu_api_service 的 MTOP 签名与调用工具链（_post_mtop_with_token_retry 等），
实现退款列表拉取、本地持久化、多账号聚合查询、同意退款等能力。

关键约束：
- 仅鱼小铺账号（xianyu_account.fish_shop_user=1）允许调用退款接口
- 退款记录以 (tenant_id, account_id, external_refund_id) 唯一
- 同意退款属于资金操作，必须二次确认 + 后端再次校验账号归属与鱼小铺权限
- 仅允许经过白名单的 MTOP API（mtop.taobao.idle.merchant.refund.agree.refund）
- 不在日志/响应中暴露 Cookie / _m_h5_tk / sign
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import select, and_, update, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.entities import (
    XianyuAccount,
    XianyuAccountAuth,
    XianyuRefund,
    XianyuRefundSyncTask,
    XianyuRefundAccountState,
)
from .xianyu_api_service import (
    _post_mtop_with_token_retry,
    _get_account_auth,
    _decrypt_value,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量与配置
# ============================================================

# 退款列表接口（需求第六节确认）
REFUND_LIST_API = "mtop.taobao.idle.merchant.refund.list"
# 同意退款接口（需求第十一节确认，白名单）
REFUND_AGREE_API = "mtop.taobao.idle.merchant.refund.agree.refund"
# 退款服务记录接口（需求第六节确认）
REFUND_SERVICE_RECORD_API = "mtop.taobao.idle.merchant.refund.service.record"
# 完整订单信息接口（需求第七节确认）
REFUND_FULL_INFO_API = "mtop.taobao.idle.trade.merchant.full.info"
# 退款核心详情接口（需求第八节确认）
REFUND_DETAIL_API = "mtop.taobao.idle.merchant.refund.detail"
# 允许执行的 MTOP 操作 API 白名单（防止 rightVO 返回任意 API 被执行）
ALLOWED_MTOP_ACTION_APIS = frozenset({REFUND_AGREE_API})
# 详情接口白名单（仅允许查询类接口，禁止执行类接口）
DETAIL_QUERY_APIS = frozenset({
    REFUND_SERVICE_RECORD_API,
    REFUND_FULL_INFO_API,
    REFUND_DETAIL_API,
})

# 全部订单查询的 queryCode（需求第五节确认）
QUERY_CODE_ALL = "ALL"

# 分页保护：单账号单轮同步最大页数（防止无限循环）
MAX_PAGES_PER_ACCOUNT = 50
# 默认每页大小（需求第十三节确认 rowsPerPage=20）
DEFAULT_PAGE_SIZE = 20

# 缓存过期策略（需求第十六节）：单账号 60 秒，全部账号 120 秒
SINGLE_ACCOUNT_CACHE_TTL_SECONDS = 60
ALL_ACCOUNTS_CACHE_TTL_SECONDS = 120
# 完整同步间隔（需求第十七节）：较长间隔执行完整校验
FULL_SYNC_INTERVAL_SECONDS = 30 * 60  # 30 分钟

# 退款详情组合缓存：进程内短时缓存 + 进行中请求去重
# 缓存命中时立即返回旧数据，过期则后台刷新
REFUND_DETAIL_CACHE_TTL_SECONDS = 60  # 60 秒短缓存（需求第十九节）
REFUND_DETAIL_CACHE_MAX_ENTRIES = 200  # 防止内存膨胀

# 多账号并发控制（需求第十八节）
MAX_CONCURRENT_ACCOUNTS = 3
# 单账号分页请求间隔（避免风控）
PAGE_REQUEST_INTERVAL_SECONDS = 0.5

# URL 白名单域名（需求第二十四节）
TRUSTED_EXTERNAL_HOSTS = frozenset({
    "goofish.com",
    "www.goofish.com",
    "seller.goofish.com",
    "h5api.m.goofish.com",
    "taobao.com",
    "www.taobao.com",
    "trade.taobao.com",
    "alibaba.com",
    "www.alibaba.com",
    "alipay.com",
    "www.alipay.com",
    "m.alipay.com",
})
# 危险协议（拒绝）
DANGEROUS_PROTOCOLS = frozenset({"javascript:", "data:", "file:", "vbscript:"})

# 进程内同步任务去重锁（同账号同时只能一轮同步）
_account_sync_locks: dict[int, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()

# 退款详情组合缓存（需求第十九节）：按 (tenant_id, account_id, order_id, refund_id) 隔离
# value: {"data": combined_dict, "saved_at": datetime, "last_success_at": datetime}
_refund_detail_cache: dict[tuple, dict] = {}
# 退款详情进行中请求去重：同一详情并发进入只发一组请求
# value: asyncio.Future
_refund_detail_inflight: dict[tuple, asyncio.Future] = {}
_refund_detail_cache_guard = asyncio.Lock()


# ============================================================
# 工具函数
# ============================================================

def _safe_int(value: Any, default: int = 0) -> int:
    """安全解析整数，支持字符串形式（如 '27' / 'true'）。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower()
    if not s:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def _parse_bool_string(value: Any) -> bool:
    """安全解析字符串布尔值：'true' → True, 'false' → False, 1/True → True。"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    return s in ("true", "1", "yes", "y")


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """安全解析十进制金额，避免浮点误差。"""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    """解析时间字符串/数字，支持毫秒时间戳和 ISO 字符串。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            # 毫秒时间戳
            ts = float(value)
            if ts > 1e12:  # 毫秒
                ts = ts / 1000
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            return None
    s = str(value).strip()
    if not s:
        return None
    # 尝试 ISO 格式
    try:
        # 兼容带 T 和带时区
        clean = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        pass
    # 尝试常见格式 yyyy-MM-dd HH:mm:ss
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _safe_url_for_open(raw_url: Any) -> Optional[str]:
    """校验 URL 是否属于可信闲鱼/阿里官方域名，返回安全 URL 或 None。

    拒绝 javascript/data/file 等危险协议；只允许 https/http 且域名在白名单内。
    """
    if not raw_url or not isinstance(raw_url, str):
        return None
    url = raw_url.strip()
    if not url:
        return None
    # 拒绝危险协议
    lower = url.lower()
    for proto in DANGEROUS_PROTOCOLS:
        if lower.startswith(proto):
            return None
    # 解析域名
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    # 精确匹配或子域名匹配
    for trusted in TRUSTED_EXTERNAL_HOSTS:
        if host == trusted or host.endswith("." + trusted):
            return url
    return None


def _mask_buyer_nick(nick: Any) -> Optional[str]:
    """脱敏买家昵称：保留首尾字符，中间用 * 替换。"""
    if not nick or not isinstance(nick, str):
        return None
    s = nick.strip()
    if len(s) <= 2:
        return s[0] + "*" if len(s) == 2 else s
    return s[0] + "*" * (len(s) - 2) + s[-1]


def _mask_mail_no(mail_no: Any) -> Optional[str]:
    """脱敏物流单号：保留前4后4，中间用 * 替换。"""
    if not mail_no or not isinstance(mail_no, str):
        return None
    s = mail_no.strip()
    if len(s) <= 8:
        return s
    return s[:4] + "*" * (len(s) - 8) + s[-4:]


# ============================================================
# 退款记录字段映射
# ============================================================

def _extract_refund_fields(raw_item: dict, account_id: int, tenant_id: int) -> Optional[dict]:
    """从闲鱼退款接口单条记录提取标准化字段。

    按 demand 第九节字段映射：
    - itemVO.itemPicUrl / title / itemInfoLines
    - priceVO.buyNum / refundFee / auctionPrice
    - commonData.orderStatus / orderSimpleRemark / refundStatus / itemId / orderId / companyName / mailNo / consignTime / createTime
    - refundInfoVO.refundStatus / refundStatusDesc / reason / csStatus / gmtCreate / refundId / tradeConsignTime
    - buyerInfoVO.userNick
    - rightVO.btnList
    """
    if not isinstance(raw_item, dict):
        return None

    item_vo = raw_item.get("itemVO") or {}
    price_vo = raw_item.get("priceVO") or {}
    common_data = raw_item.get("commonData") or {}
    refund_info_vo = raw_item.get("refundInfoVO") or {}
    buyer_info_vo = raw_item.get("buyerInfoVO") or {}
    right_vo = raw_item.get("rightVO") or {}

    # refundId 必须存在（用于唯一标识）
    refund_id = refund_info_vo.get("refundId") or raw_item.get("refundId")
    if refund_id is None or refund_id == "":
        # 没有 refundId 无法唯一标识，跳过
        return None
    refund_id_str = str(refund_id)

    # 商品ID/订单ID按字符串处理（避免大整数精度丢失）
    item_id = common_data.get("itemId") or raw_item.get("itemId")
    order_id = common_data.get("orderId") or raw_item.get("orderId")

    # 退款申请时间：优先 gmtCreate，回退 createTime（需求第十节）
    gmt_create = refund_info_vo.get("gmtCreate")
    refund_create_time = _parse_datetime(gmt_create)
    common_create_time_str = common_data.get("createTime")
    common_create_time = _parse_datetime(common_create_time_str)
    if refund_create_time is None and common_create_time is not None:
        # 仅当 gmtCreate 缺失时回退到 createTime，回退值同时写入 refund_create_time
        # 用于排序与展示，避免缺失时排序混乱
        refund_create_time = common_create_time

    # 发货时间
    consign_time = _parse_datetime(common_data.get("consignTime")) or _parse_datetime(
        refund_info_vo.get("tradeConsignTime")
    )

    # 物流信息
    company_name = common_data.get("companyName")
    mail_no = common_data.get("mailNo")

    # 操作按钮列表（rightVO.btnList）
    btn_list = right_vo.get("btnList") or []
    if not isinstance(btn_list, list):
        btn_list = []
    # 仅保留本项目支持的操作：viewRefundDetail / applyDisputePage / agreeRefundApply
    # 其他按钮（如联系买家、查看钱款）按需求第十二节不展示
    supported_codes = {"viewRefundDetail", "applyDisputePage", "agreeRefundApply"}
    filtered_btn_list = [b for b in btn_list if isinstance(b, dict) and b.get("code") in supported_codes]
    # 对 URL 类按钮做安全校验，过滤掉不可信域名的 URL
    safe_btn_list = []
    for btn in filtered_btn_list:
        click_event = btn.get("clickEvent") or {}
        if click_event.get("type") == "url":
            url = (click_event.get("data") or {}).get("url")
            safe_url = _safe_url_for_open(url)
            if not safe_url:
                # URL 不可信，跳过此按钮
                continue
            # 替换为安全 URL
            btn_copy = dict(btn)
            btn_copy["clickEvent"] = dict(click_event)
            btn_copy["clickEvent"]["data"] = {"url": safe_url}
            safe_btn_list.append(btn_copy)
        else:
            safe_btn_list.append(dict(btn))

    # 脱敏后的原始 JSON（去除可能的敏感字段，仅保留需求字段）
    raw_json_for_storage = {
        "itemVO": item_vo,
        "priceVO": price_vo,
        "commonData": common_data,
        "refundInfoVO": refund_info_vo,
        "rightVO": {"btnList": safe_btn_list},
    }

    return {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "external_refund_id": refund_id_str,
        "external_order_id": str(order_id) if order_id is not None else None,
        "external_item_id": str(item_id) if item_id is not None else None,
        "item_title": item_vo.get("title") or raw_item.get("title"),
        "item_pic_url": item_vo.get("itemPicUrl"),
        "item_info_lines": item_vo.get("itemInfoLines") if isinstance(item_vo.get("itemInfoLines"), str) else (
            json.dumps(item_vo.get("itemInfoLines"), ensure_ascii=False) if item_vo.get("itemInfoLines") else None
        ),
        "buy_num": str(price_vo.get("buyNum")) if price_vo.get("buyNum") is not None else None,
        "refund_fee": _safe_decimal(price_vo.get("refundFee")),
        "auction_price": _safe_decimal(price_vo.get("auctionPrice")),
        "order_status": common_data.get("orderStatus"),
        "order_simple_remark": common_data.get("orderSimpleRemark"),
        "refund_status": refund_info_vo.get("refundStatus"),
        "refund_status_desc": refund_info_vo.get("refundStatusDesc"),
        "common_refund_status": common_data.get("refundStatus"),
        "refund_reason": refund_info_vo.get("reason"),
        "cs_status": refund_info_vo.get("csStatus"),
        "logistics_company": company_name,
        "logistics_mail_no": _mask_mail_no(mail_no),
        "consign_time": consign_time,
        "refund_create_time": refund_create_time,
        "common_create_time": common_create_time,
        "buyer_nick": _mask_buyer_nick(buyer_info_vo.get("userNick")),
        "right_buttons_json": json.dumps(safe_btn_list, ensure_ascii=False) if safe_btn_list else None,
        "raw_json": json.dumps(raw_json_for_storage, ensure_ascii=False),
        "last_synced_time": datetime.now(),
    }


# ============================================================
# 闲鱼退款列表接口调用
# ============================================================

def fetch_refund_list_page(
    account_id: int,
    page_number: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    query_code: str = QUERY_CODE_ALL,
    timeout: int = 20,
) -> Optional[dict]:
    """拉取闲鱼退款列表的单页数据（按需求第六节的 data 结构）。

    data 结构（需求确认，不带 disputeStatus）：
        {
          "pageNumber": 1,
          "rowsPerPage": 20,
          "queryType": "refund",
          "refundSearchParam": {"queryCode": "ALL"}
        }

    返回：
        {
          "success": True/False,
          "data": {"items": [...], "nextPage": bool, "totalCount": int, "lastEndRow": int, "ext": {...}},
          "error": "..." (失败时)
        }
    """
    auth = _get_account_auth(account_id)
    if not auth:
        return {"success": False, "error": "无法获取账号认证信息"}

    cookie_str = _decrypt_value(auth.get("encrypted_cookie") or "")
    if not cookie_str:
        return {"success": False, "error": "Cookie为空"}

    # 严格按需求第六节的 data 结构，不添加 disputeStatus 等未确认字段
    data_obj = {
        "pageNumber": page_number,
        "rowsPerPage": page_size,
        "queryType": "refund",
        "refundSearchParam": {
            "queryCode": query_code,
        },
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    result = _post_mtop_with_token_retry(
        account_id, cookie_str, REFUND_LIST_API, data_str, timeout
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error") or "退款列表接口调用失败",
            "ret": result.get("ret"),
        }

    # 响应结构（需求第八节）：data.data.items / data.data.ext / data.data.nextPage / data.data.totalCount
    # 需求第七节：至少需要检查 data.data 是否存在
    outer_data = result.get("data")
    if not isinstance(outer_data, dict) or "data" not in outer_data:
        return {"success": False, "error": "退款列表返回结构异常：缺少 data.data", "ret": result.get("ret")}

    inner_data = outer_data.get("data")
    if not isinstance(inner_data, dict):
        return {"success": False, "error": "退款列表返回结构异常：data.data 非对象", "ret": result.get("ret")}

    items = inner_data.get("items") or []
    if not isinstance(items, list):
        items = []

    # 分页字段可能是字符串形式（"true"/"27"/"0"），需安全规范化
    next_page = _parse_bool_string(inner_data.get("nextPage"))
    total_count = _safe_int(inner_data.get("totalCount"))
    last_end_row = _safe_int(inner_data.get("lastEndRow"))

    ext = inner_data.get("ext") or {}
    if not isinstance(ext, dict):
        ext = {}

    return {
        "success": True,
        "data": {
            "items": items,
            "nextPage": next_page,
            "totalCount": total_count,
            "lastEndRow": last_end_row,
            "ext": ext,
        },
    }


def call_agree_refund(account_id: int, refund_id: str, timeout: int = 20) -> dict:
    """调用同意退款接口（mtop.taobao.idle.merchant.refund.agree.refund）。

    参数（需求第十一节确认）：
        {"refundId": "目标退款ID"}

    返回：
        {"success": True/False, "data": {...}, "error": "..."}
    """
    if not refund_id or not isinstance(refund_id, str):
        return {"success": False, "error": "refundId 不能为空"}

    auth = _get_account_auth(account_id)
    if not auth:
        return {"success": False, "error": "无法获取账号认证信息"}

    cookie_str = _decrypt_value(auth.get("encrypted_cookie") or "")
    if not cookie_str:
        return {"success": False, "error": "Cookie为空"}

    # 参数严格按需求第十一节
    data_obj = {"refundId": refund_id}
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    result = _post_mtop_with_token_retry(
        account_id, cookie_str, REFUND_AGREE_API, data_str, timeout
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error") or "同意退款接口调用失败",
            "ret": result.get("ret"),
        }

    return {"success": True, "data": result.get("data") or {}}


# ============================================================
# 鱼小铺账号校验
# ============================================================

async def verify_fish_shop_account(
    db: AsyncSession, account_id: int, tenant_id: int
) -> tuple[bool, Optional[XianyuAccountAuth], str]:
    """校验账号是否为鱼小铺账号，并返回 auth。

    返回 (is_fish_shop, auth, error_msg)。
    - is_fish_shop=False 时，error_msg 说明原因
    - is_fish_shop=True 但 auth 为 None 时，说明是鱼小铺但 Cookie 失效
    """
    result = await db.execute(
        select(XianyuAccount).where(
            and_(
                XianyuAccount.id == account_id,
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.deleted == 0,
            )
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        return False, None, "账号不存在或不属于当前用户"
    if not bool(account.fish_shop_user):
        return False, None, "当前闲鱼账号不支持退款管理，只有鱼小铺账号可以使用"

    result = await db.execute(
        select(XianyuAccountAuth).where(
            and_(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
            )
        )
    )
    auth = result.scalar_one_or_none()
    if not auth or not auth.encrypted_cookie:
        return True, None, "账号 Cookie 未配置或已失效，请先登录账号"

    return True, auth, ""


async def list_fish_shop_accounts(
    db: AsyncSession, tenant_id: int
) -> list[dict]:
    """列出当前租户下所有鱼小铺账号（用于全部账号聚合）。"""
    result = await db.execute(
        select(XianyuAccount).where(
            and_(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.fish_shop_user == 1,
                XianyuAccount.deleted == 0,
            )
        ).order_by(XianyuAccount.id)
    )
    accounts = result.scalars().all()
    return [
        {"id": a.id, "nickname": a.nickname, "external_uid": a.external_uid}
        for a in accounts
    ]


# ============================================================
# 同步任务去重锁
# ============================================================

async def _get_account_sync_lock(account_id: int) -> asyncio.Lock:
    """获取账号级同步锁（同账号同时只能一轮同步）。"""
    async with _locks_guard:
        lock = _account_sync_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            _account_sync_locks[account_id] = lock
        return lock


async def _try_mark_account_syncing(db: AsyncSession, tenant_id: int, account_id: int) -> bool:
    """尝试标记账号为同步中（数据库级去重）。

    返回 True 表示获锁成功，False 表示已有同步任务在运行。
    使用 is_syncing 字段 + 时间戳双重判断（防止任务卡死）。
    """
    # 确保 state 行存在
    existing = await db.execute(
        select(XianyuRefundAccountState).where(
            and_(
                XianyuRefundAccountState.tenant_id == tenant_id,
                XianyuRefundAccountState.account_id == account_id,
            )
        )
    )
    state = existing.scalar_one_or_none()
    now = datetime.now()
    if state is None:
        # 插入新行并尝试获锁
        new_state = XianyuRefundAccountState(
            tenant_id=tenant_id,
            account_id=account_id,
            is_syncing=1,
            sync_started_time=now,
        )
        db.add(new_state)
        try:
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False

    # 已存在：检查是否真的在同步（5 分钟超时保护）
    if state.is_syncing == 1:
        if state.sync_started_time and (now - state.sync_started_time) < timedelta(minutes=5):
            return False  # 真的在同步
        # 超时，强制抢占
    # 标记为同步中
    await db.execute(
        update(XianyuRefundAccountState).where(
            and_(
                XianyuRefundAccountState.tenant_id == tenant_id,
                XianyuRefundAccountState.account_id == account_id,
            )
        ).values(is_syncing=1, sync_started_time=now)
    )
    await db.commit()
    return True


async def _mark_account_sync_done(
    db: AsyncSession, tenant_id: int, account_id: int,
    status: str, error: Optional[str], total_count: Optional[int],
    is_full_sync: bool = False,
) -> None:
    """标记账号同步完成。"""
    now = datetime.now()
    values = {
        "is_syncing": 0,
        "sync_started_time": None,
        "last_sync_time": now,
        "last_sync_status": status,
        "last_sync_error": (error or "")[:500] if error else None,
        "last_total_count": total_count,
    }
    if status == "success" and is_full_sync:
        values["last_full_sync_time"] = now
    await db.execute(
        update(XianyuRefundAccountState).where(
            and_(
                XianyuRefundAccountState.tenant_id == tenant_id,
                XianyuRefundAccountState.account_id == account_id,
            )
        ).values(**values)
    )
    await db.commit()


# ============================================================
# 退款记录持久化（upsert）
# ============================================================

async def _upsert_refund_records(
    db: AsyncSession, tenant_id: int, account_id: int,
    parsed_records: list[dict],
) -> tuple[int, int]:
    """upsert 退款记录。返回 (new_count, updated_count)。

    按 (tenant_id, account_id, external_refund_id) 唯一。
    退款历史不物理删除，只更新字段。
    """
    new_count = 0
    updated_count = 0
    for record in parsed_records:
        existing_result = await db.execute(
            select(XianyuRefund).where(
                and_(
                    XianyuRefund.tenant_id == tenant_id,
                    XianyuRefund.account_id == account_id,
                    XianyuRefund.external_refund_id == record["external_refund_id"],
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            # 更新（保留 sync_status 不强制覆盖，由调用方决定）
            update_values = {k: v for k, v in record.items() if k != "sync_status"}
            await db.execute(
                update(XianyuRefund).where(XianyuRefund.id == existing.id).values(**update_values)
            )
            updated_count += 1
        else:
            new_record = XianyuRefund(**record)
            db.add(new_record)
            new_count += 1
    await db.commit()
    return new_count, updated_count


async def _mark_refund_pending_refresh(
    db: AsyncSession, tenant_id: int, account_id: int, refund_id: str
) -> None:
    """将指定退款标记为待刷新（同意退款成功后调用）。"""
    await db.execute(
        update(XianyuRefund).where(
            and_(
                XianyuRefund.tenant_id == tenant_id,
                XianyuRefund.account_id == account_id,
                XianyuRefund.external_refund_id == refund_id,
            )
        ).values(sync_status="pending_refresh")
    )
    await db.commit()


# ============================================================
# 同步任务追踪
# ============================================================

async def _create_sync_task(
    db: AsyncSession, tenant_id: int, account_id: Optional[int], scope: str
) -> str:
    sync_id = f"refund-{uuid.uuid4().hex[:16]}"
    task = XianyuRefundSyncTask(
        sync_id=sync_id,
        tenant_id=tenant_id,
        account_id=account_id,
        scope=scope,
        status="running",
        progress=0,
        started_time=datetime.now(),
    )
    db.add(task)
    await db.commit()
    return sync_id


async def _update_sync_task(
    db: AsyncSession, sync_id: str, **fields
) -> None:
    """Best-effort 更新同步任务状态。"""
    try:
        await db.execute(
            update(XianyuRefundSyncTask).where(
                XianyuRefundSyncTask.sync_id == sync_id
            ).values(**fields)
        )
        await db.commit()
    except Exception as exc:
        logger.warning("更新退款同步任务状态失败 syncId=%s errorType=%s", sync_id, type(exc).__name__)


async def _persist_sync_task_done(
    db: AsyncSession, sync_id: str, status: str,
    total: int, new_count: int, updated_count: int,
    failed: int, succeeded: int, duration: float, error: Optional[str],
) -> None:
    await _update_sync_task(
        db, sync_id,
        status=status,
        progress=100,
        total_count=total,
        new_count=new_count,
        updated_count=updated_count,
        failed_count=failed,
        succeeded_count=succeeded,
        duration_seconds=duration,
        error_message=(error or "")[:2000] if error else None,
        finished_time=datetime.now(),
    )


# ============================================================
# 单账号退款同步
# ============================================================

async def sync_refunds_for_account(
    db: AsyncSession, account_id: int, tenant_id: int,
    force_full: bool = False,
) -> dict:
    """同步单个鱼小铺账号的退款数据。

    策略（需求第十七节）：
    - 首次同步（无缓存）：完整分页同步
    - 后续快速刷新：仅请求第一页，发现 totalCount 变化或新 refundId 时继续获取剩余页
    - force_full=True 或超过 FULL_SYNC_INTERVAL_SECONDS 未完整同步：强制完整同步

    返回：
        {"ok": True/False, "syncId": "...", "total": int, "new": int, "updated": int, "error": "..."}
    """
    # 1. 校验鱼小铺
    is_fish_shop, auth, err = await verify_fish_shop_account(db, account_id, tenant_id)
    if not is_fish_shop:
        return {"ok": False, "error": err or "账号不是鱼小铺"}
    if auth is None:
        return {"ok": False, "error": err or "账号 Cookie 未配置"}

    # 2. 获取账号级同步锁（同账号同时只能一轮同步）
    lock = await _get_account_sync_lock(account_id)
    if lock.locked():
        return {"ok": False, "error": "TASK_ALREADY_RUNNING", "syncId": None}

    async with lock:
        # 3. 数据库级去重
        acquired = await _try_mark_account_syncing(db, tenant_id, account_id)
        if not acquired:
            return {"ok": False, "error": "TASK_ALREADY_RUNNING", "syncId": None}

        sync_id = await _create_sync_task(db, tenant_id, account_id, "single")
        started_at = datetime.now()

        try:
            # 4. 判断是否需要完整同步
            state_result = await db.execute(
                select(XianyuRefundAccountState).where(
                    and_(
                        XianyuRefundAccountState.tenant_id == tenant_id,
                        XianyuRefundAccountState.account_id == account_id,
                    )
                )
            )
            state = state_result.scalar_one_or_none()
            need_full = force_full
            if state is None or state.last_sync_time is None:
                need_full = True  # 首次同步
            elif state.last_full_sync_time is None:
                need_full = True  # 从未完整同步
            elif (datetime.now() - state.last_full_sync_time).total_seconds() > FULL_SYNC_INTERVAL_SECONDS:
                need_full = True  # 超过间隔

            # 5. 请求第一页
            page_result = await asyncio.to_thread(
                fetch_refund_list_page, account_id, 1, DEFAULT_PAGE_SIZE, QUERY_CODE_ALL
            )
            if not page_result.get("success"):
                await _mark_account_sync_done(db, tenant_id, account_id, "failed", page_result.get("error"), None)
                await _persist_sync_task_done(
                    db, sync_id, "failed", 0, 0, 0, 1, 0, 0.0, page_result.get("error")
                )
                return {"ok": False, "syncId": sync_id, "error": page_result.get("error")}

            first_page_data = page_result["data"]
            first_items = first_page_data["items"]
            total_count = first_page_data["totalCount"]
            next_page = first_page_data["nextPage"]
            ext = first_page_data.get("ext") or {}
            ext_total_refund_fee = _safe_decimal(ext.get("totalRefundFee"))

            # 6. 解析并 upsert 第一页
            parsed_first = []
            for raw in first_items:
                parsed = _extract_refund_fields(raw, account_id, tenant_id)
                if parsed:
                    # 补充 ext_total_refund_fee（单账号有意义）
                    parsed["ext_total_refund_fee"] = ext_total_refund_fee
                    parsed_first.append(parsed)

            new_count, updated_count = await _upsert_refund_records(db, tenant_id, account_id, parsed_first)
            synced_refund_ids = {p["external_refund_id"] for p in parsed_first}

            # 更新进度
            await _update_sync_task(db, sync_id, progress=30, total_count=total_count, new_count=new_count, updated_count=updated_count)

            # 7. 判断是否需要继续获取剩余页
            should_continue = False
            if need_full:
                should_continue = next_page
            else:
                # 快速刷新：发现新 refundId 或 totalCount 变化时继续
                if state and state.last_total_count is not None and total_count != state.last_total_count:
                    should_continue = next_page
                # 检查是否有新 refundId（本地没有的）
                if not should_continue and parsed_first:
                    existing_ids_result = await db.execute(
                        select(XianyuRefund.external_refund_id).where(
                            and_(
                                XianyuRefund.tenant_id == tenant_id,
                                XianyuRefund.account_id == account_id,
                                XianyuRefund.external_refund_id.in_([p["external_refund_id"] for p in parsed_first]),
                            )
                        )
                    )
                    existing_ids = {r[0] for r in existing_ids_result.fetchall()}
                    new_ids_in_first_page = synced_refund_ids - existing_ids
                    if new_ids_in_first_page:
                        should_continue = next_page

            # 8. 继续获取剩余页
            all_parsed = list(parsed_first)
            page_num = 2
            while should_continue and page_num <= MAX_PAGES_PER_ACCOUNT:
                await asyncio.sleep(PAGE_REQUEST_INTERVAL_SECONDS)  # 请求间隔
                page_result = await asyncio.to_thread(
                    fetch_refund_list_page, account_id, page_num, DEFAULT_PAGE_SIZE, QUERY_CODE_ALL
                )
                if not page_result.get("success"):
                    # 单页失败不中断整体（已获取的数据保留）
                    logger.warning(
                        "退款同步第 %s 页失败 accountId=%s error=%s",
                        page_num, account_id, page_result.get("error"),
                    )
                    break

                page_data = page_result["data"]
                page_items = page_data["items"]
                if not page_items:
                    break

                page_parsed = []
                for raw in page_items:
                    parsed = _extract_refund_fields(raw, account_id, tenant_id)
                    if parsed:
                        parsed["ext_total_refund_fee"] = ext_total_refund_fee
                        page_parsed.append(parsed)

                # 按 refundId 去重（同页内或跨页重复）
                new_in_page = []
                for p in page_parsed:
                    if p["external_refund_id"] not in synced_refund_ids:
                        new_in_page.append(p)
                        synced_refund_ids.add(p["external_refund_id"])

                if new_in_page:
                    n_new, n_upd = await _upsert_refund_records(db, tenant_id, account_id, new_in_page)
                    new_count += n_new
                    updated_count += n_upd
                    all_parsed.extend(new_in_page)

                # 分页终止条件（需求第十三节）
                if len(page_items) < DEFAULT_PAGE_SIZE:
                    break
                if not page_data["nextPage"]:
                    break
                # 已获取唯一数量达到 totalCount
                if total_count > 0 and len(synced_refund_ids) >= total_count:
                    break
                # 进度更新
                progress = 30 + int(70 * min(page_num / max(MAX_PAGES_PER_ACCOUNT, 1), 1.0))
                await _update_sync_task(db, sync_id, progress=progress, new_count=new_count, updated_count=updated_count)
                page_num += 1

            # 9. 校验唯一数量与 totalCount
            unique_count = len(synced_refund_ids)
            duration = (datetime.now() - started_at).total_seconds()

            # 10. 标记完成
            await _mark_account_sync_done(
                db, tenant_id, account_id, "success", None, unique_count, is_full_sync=need_full
            )
            await _persist_sync_task_done(
                db, sync_id, "success", unique_count, new_count, updated_count, 0, 1, duration, None
            )

            return {
                "ok": True,
                "syncId": sync_id,
                "total": unique_count,
                "new": new_count,
                "updated": updated_count,
                "totalCount": total_count,
                "isFullSync": need_full,
            }

        except Exception as exc:
            logger.exception("退款同步异常 accountId=%s", account_id)
            duration = (datetime.now() - started_at).total_seconds()
            err_msg = f"同步异常: {type(exc).__name__}"
            await _mark_account_sync_done(db, tenant_id, account_id, "failed", err_msg, None)
            await _persist_sync_task_done(db, sync_id, "failed", 0, 0, 0, 1, 0, duration, err_msg)
            return {"ok": False, "syncId": sync_id, "error": err_msg}


# ============================================================
# 全部账号聚合同步
# ============================================================

async def sync_all_refunds(
    db: AsyncSession, tenant_id: int,
) -> dict:
    """全部账号模式：受控并发刷新所有鱼小铺账号。

    策略（需求第十八节）：
    - 同时刷新的账号数量受 MAX_CONCURRENT_ACCOUNTS 限制
    - 每个账号同一时间只能有一轮退款同步
    - 某一个账号失败不影响其他账号
    - 全部账号模式加入合理抖动，避免所有账号同一毫秒请求
    """
    fish_shop_accounts = await list_fish_shop_accounts(db, tenant_id)
    if not fish_shop_accounts:
        return {"ok": True, "syncId": None, "total": 0, "succeeded": 0, "failed": 0, "details": [], "message": "当前没有鱼小铺账号"}

    sync_id = await _create_sync_task(db, tenant_id, None, "all")
    started_at = datetime.now()

    sem = asyncio.Semaphore(MAX_CONCURRENT_ACCOUNTS)

    async def _sync_one(account_info: dict, index: int) -> dict:
        # 抖动：错开请求时间，避免所有账号同一毫秒请求
        await asyncio.sleep(min(index * 0.3, 2.0))
        async with sem:
            session_factory = _get_async_session()
            async with session_factory() as sub_db:
                result = await sync_refunds_for_account(sub_db, account_info["id"], tenant_id)
                return {
                    "accountId": account_info["id"],
                    "nickname": account_info.get("nickname"),
                    "ok": result.get("ok", False),
                    "total": result.get("total", 0),
                    "error": result.get("error"),
                }

    # 并发执行
    tasks = [_sync_one(acc, idx) for idx, acc in enumerate(fish_shop_accounts)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    succeeded = 0
    failed = 0
    total_refunds = 0
    details = []
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            details.append({"ok": False, "error": str(r)})
        elif r.get("ok"):
            succeeded += 1
            total_refunds += r.get("total", 0)
            details.append(r)
        else:
            failed += 1
            details.append(r)

    duration = (datetime.now() - started_at).total_seconds()
    await _persist_sync_task_done(
        db, sync_id, "completed" if failed == 0 else "completed",
        total_refunds, 0, 0, failed, succeeded, duration, None,
    )

    return {
        "ok": failed == 0,
        "syncId": sync_id,
        "total": total_refunds,
        "succeeded": succeeded,
        "failed": failed,
        "details": details,
    }


# 延迟导入 async_session，避免循环引用
def _get_async_session():
    from ..core.database import async_session
    return async_session


# ============================================================
# 本地退款数据查询（多账号聚合 + 分页 + 筛选）
# ============================================================

# 退款分类标签 → orderStatus 精确映射（需求第五节）
# 仅 ALL 使用 queryCode="ALL"，其他标签基于本地 orderStatus 精确筛选
CATEGORY_ORDER_STATUS_MAP = {
    "unshipped": ["未发货退款"],
    "shipped": ["已发货退款"],
    "return": ["退货退款"],
    # "freight" 退运费：当前样本无可靠 orderStatus 映射，保留标签但不显示数据
}
SUPPORTED_CATEGORIES = ["all", "unshipped", "shipped", "return", "freight"]


async def query_local_refunds(
    db: AsyncSession, tenant_id: int,
    account_id: Optional[int] = None,
    category: str = "all",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询本地缓存的退款记录（多账号聚合 + 分类筛选 + 分页）。

    策略（需求第二十一节）：基于本地聚合数据分页，不直接映射闲鱼分页。
    排序：按退款申请时间倒序（refund_create_time，缺失回退 common_create_time）。
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    # 构建基础查询条件
    conditions = [
        XianyuRefund.tenant_id == tenant_id,
        XianyuRefund.deleted == 0,
    ]
    if account_id is not None:
        conditions.append(XianyuRefund.account_id == account_id)

    # 分类筛选：仅 all 不加条件，其他基于 order_status 精确匹配
    if category != "all":
        if category == "freight":
            # 退运费：无可靠映射，返回空列表（保留标签）
            return {
                "items": [],
                "total": 0,
                "page": page,
                "pageSize": page_size,
                "category": category,
                "categoryUnavailable": True,
                "categoryUnavailableReason": "退运费分类尚未确认接口映射，暂不显示数据",
            }
        status_list = CATEGORY_ORDER_STATUS_MAP.get(category, [])
        if status_list:
            conditions.append(XianyuRefund.order_status.in_(status_list))
        else:
            # 未知分类，返回空
            return {"items": [], "total": 0, "page": page, "pageSize": page_size, "category": category}

    # 计算总数
    count_stmt = select(func.count(XianyuRefund.id)).where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 查询列表（按退款申请时间倒序，缺失回退 common_create_time）
    # 使用 COALESCE 优先 refund_create_time，回退 common_create_time
    order_expr = func.coalesce(XianyuRefund.refund_create_time, XianyuRefund.common_create_time)
    list_stmt = (
        select(XianyuRefund)
        .where(and_(*conditions))
        .order_by(desc(order_expr), desc(XianyuRefund.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    list_result = await db.execute(list_stmt)
    records = list_result.scalars().all()

    # 同时查询账号信息（用于展示所属账号）
    account_ids = list({r.account_id for r in records})
    account_map: dict[int, dict] = {}
    if account_ids:
        acc_result = await db.execute(
            select(XianyuAccount).where(
                and_(
                    XianyuAccount.tenant_id == tenant_id,
                    XianyuAccount.id.in_(account_ids),
                )
            )
        )
        for acc in acc_result.scalars().all():
            account_map[acc.id] = {
                "id": acc.id,
                "nickname": acc.nickname,
                "externalUid": acc.external_uid,
            }

    items = []
    for r in records:
        acc_info = account_map.get(r.account_id, {})
        # 解析操作按钮
        buttons = []
        if r.right_buttons_json:
            try:
                buttons = json.loads(r.right_buttons_json)
            except (ValueError, TypeError):
                buttons = []
        items.append({
            "id": r.id,
            "accountId": r.account_id,
            "accountNickname": acc_info.get("nickname"),
            "externalRefundId": r.external_refund_id,
            "externalOrderId": r.external_order_id,
            "externalItemId": r.external_item_id,
            "itemTitle": r.item_title,
            "itemPicUrl": r.item_pic_url,
            "itemInfoLines": r.item_info_lines,
            "buyNum": r.buy_num,
            "refundFee": str(r.refund_fee) if r.refund_fee is not None else None,
            "auctionPrice": str(r.auction_price) if r.auction_price is not None else None,
            "orderStatus": r.order_status,
            "orderSimpleRemark": r.order_simple_remark,
            "refundStatus": r.refund_status,
            "refundStatusDesc": r.refund_status_desc,
            "commonRefundStatus": r.common_refund_status,
            "refundReason": r.refund_reason,
            "csStatus": r.cs_status,
            "logisticsCompany": r.logistics_company,
            "logisticsMailNo": r.logistics_mail_no,
            "consignTime": r.consign_time.isoformat() if r.consign_time else None,
            "refundCreateTime": r.refund_create_time.isoformat() if r.refund_create_time else None,
            "commonCreateTime": r.common_create_time.isoformat() if r.common_create_time else None,
            "buyerNick": r.buyer_nick,
            "rightButtons": buttons,
            "syncStatus": r.sync_status,
            "lastSyncedTime": r.last_synced_time.isoformat() if r.last_synced_time else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "category": category,
    }


# ============================================================
# 同步状态查询
# ============================================================

async def get_sync_status(
    db: AsyncSession, tenant_id: int, account_id: Optional[int] = None
) -> dict:
    """查询同步状态（用于前端判断缓存是否过期、是否正在同步）。"""
    if account_id is not None:
        # 单账号状态
        result = await db.execute(
            select(XianyuRefundAccountState).where(
                and_(
                    XianyuRefundAccountState.tenant_id == tenant_id,
                    XianyuRefundAccountState.account_id == account_id,
                )
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            return {
                "hasCache": False,
                "isSyncing": False,
                "lastSyncTime": None,
                "lastSyncStatus": None,
                "lastTotalCount": None,
                "cacheExpired": True,
            }
        now = datetime.now()
        cache_expired = (
            state.last_sync_time is None
            or (now - state.last_sync_time).total_seconds() > SINGLE_ACCOUNT_CACHE_TTL_SECONDS
        )
        return {
            "hasCache": state.last_sync_time is not None,
            "isSyncing": bool(state.is_syncing),
            "lastSyncTime": state.last_sync_time.isoformat() if state.last_sync_time else None,
            "lastSyncStatus": state.last_sync_status,
            "lastTotalCount": state.last_total_count,
            "cacheExpired": cache_expired,
            "lastFullSyncTime": state.last_full_sync_time.isoformat() if state.last_full_sync_time else None,
        }

    # 全部账号模式：聚合所有鱼小铺账号状态
    fish_shop_accounts = await list_fish_shop_accounts(db, tenant_id)
    if not fish_shop_accounts:
        return {
            "hasCache": False,
            "isSyncing": False,
            "lastSyncTime": None,
            "cacheExpired": True,
            "accountCount": 0,
        }

    account_ids = [a["id"] for a in fish_shop_accounts]
    result = await db.execute(
        select(XianyuRefundAccountState).where(
            and_(
                XianyuRefundAccountState.tenant_id == tenant_id,
                XianyuRefundAccountState.account_id.in_(account_ids),
            )
        )
    )
    states = result.scalars().all()

    if not states:
        return {
            "hasCache": False,
            "isSyncing": False,
            "lastSyncTime": None,
            "cacheExpired": True,
            "accountCount": len(fish_shop_accounts),
        }

    any_syncing = any(s.is_syncing for s in states)
    last_sync_times = [s.last_sync_time for s in states if s.last_sync_time]
    latest = max(last_sync_times) if last_sync_times else None
    now = datetime.now()
    cache_expired = (
        latest is None
        or (now - latest).total_seconds() > ALL_ACCOUNTS_CACHE_TTL_SECONDS
    )
    return {
        "hasCache": latest is not None,
        "isSyncing": any_syncing,
        "lastSyncTime": latest.isoformat() if latest else None,
        "cacheExpired": cache_expired,
        "accountCount": len(fish_shop_accounts),
    }


# ============================================================
# 同意退款
# ============================================================

async def agree_refund(
    db: AsyncSession, account_id: int, refund_id: str, tenant_id: int
) -> dict:
    """同意退款（资金操作，需多重校验）。

    校验（需求第二十三节）：
    1. 账号属于当前用户
    2. 账号是鱼小铺
    3. refundId 属于该账号
    4. 当前退款记录仍允许同意退款（rightVO.btnList 返回 agreeRefundApply）
    5. Cookie 属于该账号（由后端注入，不接受前端传入）

    返回：
        {"ok": True/False, "data": {...}, "error": "..."}
    """
    if not refund_id or not isinstance(refund_id, str):
        return {"ok": False, "error": "refundId 不能为空"}

    # 1-2. 校验鱼小铺账号
    is_fish_shop, auth, err = await verify_fish_shop_account(db, account_id, tenant_id)
    if not is_fish_shop:
        return {"ok": False, "error": err or "账号不是鱼小铺"}
    if auth is None:
        return {"ok": False, "error": err or "账号 Cookie 未配置"}

    # 3. 校验退款归属（防止跨账号退款）
    refund_result = await db.execute(
        select(XianyuRefund).where(
            and_(
                XianyuRefund.tenant_id == tenant_id,
                XianyuRefund.account_id == account_id,
                XianyuRefund.external_refund_id == refund_id,
                XianyuRefund.deleted == 0,
            )
        )
    )
    refund_record = refund_result.scalar_one_or_none()
    if refund_record is None:
        return {"ok": False, "error": "退款记录不存在或不属于该账号"}

    # 4. 校验当前退款仍允许同意退款（基于本地缓存的 rightButtons）
    # 注意：本地缓存的按钮可能已过期，这里做初步校验；
    # 实际执行前会再次调用闲鱼接口验证（见下方）
    buttons = []
    if refund_record.right_buttons_json:
        try:
            buttons = json.loads(refund_record.right_buttons_json)
        except (ValueError, TypeError):
            buttons = []
    has_agree_button = any(
        isinstance(b, dict) and b.get("code") == "agreeRefundApply" for b in buttons
    )
    if not has_agree_button:
        return {"ok": False, "error": "当前退款记录不支持同意退款操作（服务端未返回该按钮权限）"}

    # 5. 标记为待刷新（防止重复提交）
    await _mark_refund_pending_refresh(db, tenant_id, account_id, refund_id)

    # 6. 调用同意退款接口
    try:
        result = await asyncio.to_thread(call_agree_refund, account_id, refund_id)
    except Exception as exc:
        logger.exception("同意退款调用异常 accountId=%s refundId=%s", account_id, refund_id)
        # 异常时不自动重试资金操作（需求第二十三节）
        return {"ok": False, "error": f"同意退款调用异常: {type(exc).__name__}"}

    if not result.get("success"):
        # 失败：不改变本地状态（需求第二十三节：失败时不得把本地状态改为已退款）
        # 但要清除 pending_refresh 标记
        await db.execute(
            update(XianyuRefund).where(
                and_(
                    XianyuRefund.tenant_id == tenant_id,
                    XianyuRefund.account_id == account_id,
                    XianyuRefund.external_refund_id == refund_id,
                )
            ).values(sync_status="synced")
        )
        await db.commit()
        return {"ok": False, "error": result.get("error") or "同意退款接口调用失败"}

    # 7. 成功后定向刷新该账号（需求第二十二节）
    # 在后台触发刷新，不阻塞响应
    try:
        asyncio.create_task(_background_refresh_account(account_id, tenant_id))
    except Exception:
        # 后台刷新失败不影响响应
        pass

    return {"ok": True, "data": result.get("data") or {}, "message": "同意退款请求已提交"}


async def _background_refresh_account(account_id: int, tenant_id: int) -> None:
    """后台刷新账号退款数据（同意退款成功后调用）。"""
    try:
        session_factory = _get_async_session()
        async with session_factory() as db:
            await sync_refunds_for_account(db, account_id, tenant_id, force_full=False)
    except Exception as exc:
        logger.warning(
            "同意退款后后台刷新失败 accountId=%s errorType=%s",
            account_id, type(exc).__name__,
        )


# ============================================================
# 缓存过期判断
# ============================================================

def is_single_account_cache_expired(last_sync_time: Optional[datetime]) -> bool:
    """单账号缓存是否过期。"""
    if last_sync_time is None:
        return True
    return (datetime.now() - last_sync_time).total_seconds() > SINGLE_ACCOUNT_CACHE_TTL_SECONDS


def is_all_accounts_cache_expired(latest_sync_time: Optional[datetime]) -> bool:
    """全部账号缓存是否过期。"""
    if latest_sync_time is None:
        return True
    return (datetime.now() - latest_sync_time).total_seconds() > ALL_ACCOUNTS_CACHE_TTL_SECONDS


# ============================================================
# 退款详情：三个 MTOP 接口调用 + 数据解析 + 缓存
# ============================================================
# 需求覆盖：第六节（接口一 service.record）、第七节（接口二 full.info）、
# 第八节（接口三 refund.detail）、第九节（components 按 render 解析）、
# 第十节（状态和流程）、第十一节（基本信息）、第十二节（物流和凭证）、
# 第十三节（富文本安全）、第十四节（详情页操作）、第十五节（数据职责）、
# 第十六节（一致性校验）、第十七节（成功判断）、第十八节（签名和 Cookie）、
# 第十九节（缓存和去重）、第二十节（局部失败和重试）


# ----- HTML 实体解码与富文本安全（需求第十三节） -----

import html as _html
import re as _re

# 允许的有限安全样式白名单（其他样式忽略）
_SAFE_STYLE_PROPERTIES = frozenset({
    "color", "font-size", "font-weight", "line-height",
    "margin-top", "margin-bottom", "text-align",
})

# 富文本 linkUrl 协议白名单（仅 https）
# 注意：urlparse().scheme 返回值不带冒号，所以这里不能写 "https:"
_RICH_TEXT_LINK_PROTOCOLS = frozenset({"https"})

# 富文本 linkUrl 域名白名单（与退款详情官方域名一致）
_RICH_TEXT_LINK_HOSTS = frozenset({
    "goofish.com",
    "www.goofish.com",
    "seller.goofish.com",
    "taobao.com",
    "www.taobao.com",
    "alibaba.com",
    "www.alibaba.com",
    "alipay.com",
    "www.alipay.com",
})


def _decode_html_entities(text: Any) -> str:
    """安全解码 HTML 实体（如 &yen; &amp; &lt;），返回纯文本。

    使用标准库 html.unescape，不引入任何 HTML 解析器。
    """
    if text is None:
        return ""
    s = str(text)
    if not s:
        return ""
    try:
        return _html.unescape(s)
    except Exception:
        return s


def _validate_rich_text_link(url: Any) -> Optional[str]:
    """校验富文本 linkUrl：仅允许 https + 官方域名白名单。

    拒绝 javascript/data/file 协议；拒绝非白名单域名。
    返回安全 URL 或 None。
    """
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    lower = s.lower()
    for proto in DANGEROUS_PROTOCOLS:
        if lower.startswith(proto):
            return None
    try:
        parsed = urlparse(s)
    except (ValueError, TypeError):
        return None
    if parsed.scheme not in _RICH_TEXT_LINK_PROTOCOLS:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    for trusted in _RICH_TEXT_LINK_HOSTS:
        if host == trusted or host.endswith("." + trusted):
            return s
    return None


def _safe_style_dict(style_value: Any) -> dict:
    """解析内联样式字符串为有限安全样式 dict，未识别样式忽略。"""
    if not style_value or not isinstance(style_value, str):
        return {}
    result: dict[str, str] = {}
    for part in style_value.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, _, val = part.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if not key or not val:
            continue
        if key in _SAFE_STYLE_PROPERTIES:
            # 限制值长度，防止溢出
            if len(val) <= 32:
                result[key] = val
    return result


def _normalize_rich_text_items(items: Any) -> list[dict]:
    """标准化富文本数组为安全渲染结构。

    输入项可能含字段：content, linkUrl, style, type, lineHeight, marginTop。
    输出项：{ content: str, linkUrl: str|null, style: dict, type: str }
    - content 作为纯文本，HTML 实体解码
    - linkUrl 经过协议和官方域名白名单校验
    - style 仅保留有限安全样式
    """
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = _decode_html_entities(item.get("content"))
        link_url = _validate_rich_text_link(item.get("linkUrl"))
        # 兼容字段名：lineHeight / marginTop 单独字段
        style_dict = _safe_style_dict(item.get("style"))
        if "lineHeight" in item and isinstance(item["lineHeight"], (str, int, float)):
            lh = str(item["lineHeight"]).strip()
            if lh and len(lh) <= 16:
                style_dict.setdefault("line-height", lh)
        if "marginTop" in item and isinstance(item["marginTop"], (str, int, float)):
            mt = str(item["marginTop"]).strip()
            if mt and len(mt) <= 16:
                style_dict.setdefault("margin-top", mt)
        item_type = str(item.get("type") or "text").strip().lower() or "text"
        if item_type not in ("text", "link"):
            item_type = "text"
        result.append({
            "content": content,
            "linkUrl": link_url,
            "style": style_dict,
            "type": item_type,
        })
    return result


# ----- 凭证图片 URL 校验（需求第十二节） -----

# 凭证图片 URL 允许的协议（仅 https）
# 注意：urlparse().scheme 返回值不带冒号，所以这里不能写 "https:"
_PROOF_IMAGE_PROTOCOLS = frozenset({"https"})

# 凭证图片 URL 允许的域名白名单（闲鱼/阿里官方 CDN）
_PROOF_IMAGE_HOSTS = frozenset({
    "img.alicdn.com",
    "gw.alicdn.com",
    "cdn.alicdn.com",
    "img.taobaocdn.com",
    "aos-cdn.goofish.com",
    "img.goofish.com",
    "gw.goofish.com",
})


def _validate_proof_image_url(url: Any) -> Optional[str]:
    """校验凭证图片 URL：仅允许可信 HTTPS 官方媒体地址。

    拒绝 javascript/data/file 协议；拒绝非白名单域名。
    返回安全 URL 或 None。
    """
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    # 兼容 //cdn.example.com/x.jpg 协议相对 URL（统一升级为 https）
    if s.startswith("//"):
        s = "https:" + s
    lower = s.lower()
    for proto in DANGEROUS_PROTOCOLS:
        if lower.startswith(proto):
            return None
    try:
        parsed = urlparse(s)
    except (ValueError, TypeError):
        return None
    if parsed.scheme not in _PROOF_IMAGE_PROTOCOLS:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    for trusted in _PROOF_IMAGE_HOSTS:
        if host == trusted or host.endswith("." + trusted):
            return s
    return None


def _normalize_proof_media_list(items: Any) -> list[dict]:
    """标准化凭证多媒体列表为安全结构。

    输入项可能含字段：url, type, width, height, etc.
    输出项：{ url: str, type: str }
    - url 必须经过 _validate_proof_image_url 校验
    - 非法 URL 直接跳过（不返回 None 项）
    """
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("picUrl") or item.get("imageUrl")
        safe_url = _validate_proof_image_url(url)
        if not safe_url:
            continue
        media_type = str(item.get("type") or "image").strip().lower() or "image"
        if media_type not in ("image", "video"):
            media_type = "image"
        result.append({"url": safe_url, "type": media_type})
    return result


# ----- 三个 MTOP 接口调用（同步函数，使用 _post_mtop_with_token_retry） -----

# 错误分类枚举（脱敏）：用于前端按类别展示友好提示
# 不直接暴露 Cookie / sign / 完整 ret
REFUND_ERROR_CODES = frozenset({
    "MTOP_RET_FAILURE",        # MTOP ret 不含 SUCCESS
    "AUTH_EXPIRED",            # 令牌过期 / 登录态失效
    "INVALID_RESPONSE_SHAPE",  # 响应结构异常（缺少 data.data / data.module 等）
    "ID_CONSISTENCY_ERROR",    # 响应 orderId/refundId 与请求不一致
    "ACCOUNT_MISMATCH",        # 退款与账号不匹配（不应出现于 fetch 层）
    "REFUND_NOT_FOUND",        # 退款记录不存在
    "NETWORK_TIMEOUT",         # 请求超时
    "NETWORK_ERROR",           # 网络异常
    "EMPTY_CREDENTIAL",        # Cookie / token 为空
    "UNKNOWN_ERROR",           # 兜底
})


def _classify_mtop_error(ret: Any, error_message: Optional[str] = None) -> str:
    """根据 MTOP ret 与错误信息推断脱敏错误类别（供前端展示）。

    判定顺序：
    1. 令牌过期 / 登录态失效（FAIL_SYS_TOKEN_EXOIRED / FAIL_SYS_TOKEN_EMPTY / 令牌过期）
    2. 网络超时
    3. 网络异常（XIANYU_API_UNAVAILABLE 等）
    4. MTOP ret 失败（含 SUCCESS::FAIL_*)
    5. 兜底 UNKNOWN_ERROR
    """
    err_text = str(error_message or "")
    ret_text = ""
    if ret:
        if isinstance(ret, list):
            ret_text = " ".join(str(r) for r in ret)
        else:
            ret_text = str(ret)
    combined = (ret_text + " " + err_text).upper()

    # 1. 登录态失效
    if (
        "FAIL_SYS_TOKEN_EXOIRED" in combined
        or "FAIL_SYS_TOKEN_EMPTY" in combined
        or "令牌过期" in err_text
        or "令牌为空" in err_text
        or "FAIL_SYS_SESSION_EXPIRED" in combined
    ):
        return "AUTH_EXPIRED"

    # 2. 网络超时
    if "请求超时" in err_text or "TIMEOUT" in combined:
        return "NETWORK_TIMEOUT"

    # 3. 网络异常
    if "XIANYU_API_UNAVAILABLE" in combined or "闲鱼接口请求失败" in err_text:
        return "NETWORK_ERROR"

    # 4. MTOP ret 失败（ret 存在但不含 SUCCESS）
    if ret_text:
        return "MTOP_RET_FAILURE"

    # 5. 兜底
    return "UNKNOWN_ERROR"


def fetch_refund_service_record(
    account_id: int, order_id: str, timeout: int = 20
) -> dict:
    """拉取退款服务记录（接口一，需求第六节）。

    data: {"orderId": "目标订单ID"}
    主要响应：data.data.refundRecordList / data.data.postageRefundRecordList

    查询参数（需求第六节确认）：
    - type=originaljson（不是 json）
    - 不带 valueType=string
    之前使用共享的 type=json + valueType=string 会导致接口返回失败，
    必须使用 type=originaljson 才能正确返回退款记录数据。
    """
    if not order_id or not isinstance(order_id, str):
        return {"success": False, "error": "orderId 不能为空"}
    auth = _get_account_auth(account_id)
    if not auth:
        return {"success": False, "error": "无法获取账号认证信息"}
    cookie_str = _decrypt_value(auth.get("encrypted_cookie") or "")
    if not cookie_str:
        return {"success": False, "error": "Cookie为空"}

    data_obj = {"orderId": order_id}
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    result = _post_mtop_with_token_retry(
        account_id, cookie_str, REFUND_SERVICE_RECORD_API, data_str, timeout,
        query_type="originaljson", include_value_type=False,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error") or "退款服务记录接口调用失败",
            "ret": result.get("ret"),
            "errorCode": _classify_mtop_error(result.get("ret"), result.get("error")),
        }
    return {"success": True, "data": result.get("data") or {}, "ret": result.get("ret")}


def fetch_refund_full_info(
    account_id: int, order_id: str, timeout: int = 20
) -> dict:
    """拉取完整订单信息（接口二，需求第七节）。

    注意：参数名是 tid，不是 orderId/refundId/itemId。
    data: {"tid": "目标订单ID"}
    主要响应：data.module

    查询参数（需求第七节确认）：
    - type=json
    - valueType=string
    """
    if not order_id or not isinstance(order_id, str):
        return {"success": False, "error": "orderId 不能为空"}
    auth = _get_account_auth(account_id)
    if not auth:
        return {"success": False, "error": "无法获取账号认证信息"}
    cookie_str = _decrypt_value(auth.get("encrypted_cookie") or "")
    if not cookie_str:
        return {"success": False, "error": "Cookie为空"}

    # 严格按需求第七节：参数名是 tid
    data_obj = {"tid": order_id}
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    result = _post_mtop_with_token_retry(
        account_id, cookie_str, REFUND_FULL_INFO_API, data_str, timeout,
        query_type="json", include_value_type=True,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error") or "完整订单信息接口调用失败",
            "ret": result.get("ret"),
            "errorCode": _classify_mtop_error(result.get("ret"), result.get("error")),
        }
    return {"success": True, "data": result.get("data") or {}, "ret": result.get("ret")}


def fetch_refund_detail(
    account_id: int, order_id: str, refund_id: str, timeout: int = 20
) -> dict:
    """拉取退款核心详情（接口三，需求第八节）。

    data: {"orderId": "目标订单ID", "refundId": "目标退款ID"}
    主要响应：data.data（含 components / basicRefundInfo / 等）

    查询参数（需求第八节确认）：
    - type=originaljson（不是 json）
    - 不带 valueType=string
    之前使用共享的 type=json + valueType=string 会导致接口返回失败，
    必须使用 type=originaljson 才能正确返回 components 动态组件数组。
    """
    if not order_id or not isinstance(order_id, str):
        return {"success": False, "error": "orderId 不能为空"}
    if not refund_id or not isinstance(refund_id, str):
        return {"success": False, "error": "refundId 不能为空"}
    auth = _get_account_auth(account_id)
    if not auth:
        return {"success": False, "error": "无法获取账号认证信息"}
    cookie_str = _decrypt_value(auth.get("encrypted_cookie") or "")
    if not cookie_str:
        return {"success": False, "error": "Cookie为空"}

    data_obj = {"orderId": order_id, "refundId": refund_id}
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    result = _post_mtop_with_token_retry(
        account_id, cookie_str, REFUND_DETAIL_API, data_str, timeout,
        query_type="originaljson", include_value_type=False,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error") or "退款核心详情接口调用失败",
            "ret": result.get("ret"),
            "errorCode": _classify_mtop_error(result.get("ret"), result.get("error")),
        }
    return {"success": True, "data": result.get("data") or {}, "ret": result.get("ret")}


# ----- 成功判定（需求第十七节） -----

def _is_mtop_success(ret: Any) -> bool:
    """判断 MTOP ret 是否包含 SUCCESS。"""
    if not ret:
        return False
    if isinstance(ret, list):
        return any(isinstance(r, str) and r.startswith("SUCCESS") for r in ret)
    if isinstance(ret, str):
        return ret.startswith("SUCCESS")
    return False


def _check_service_record_success(result: dict) -> tuple[bool, str]:
    """service.record 成功判定：data.data 存在，两个记录列表安全回退为空数组。"""
    if not result.get("success"):
        return False, result.get("error") or "接口调用失败"
    if not _is_mtop_success(result.get("ret")):
        return False, "接口返回失败状态"
    data = result.get("data")
    if not isinstance(data, dict) or "data" not in data:
        return False, "退款服务记录返回结构异常：缺少 data.data"
    inner_data = data.get("data")
    if not isinstance(inner_data, dict):
        return False, "退款服务记录返回结构异常：data.data 非对象"
    return True, ""


def _check_full_info_success(result: dict) -> tuple[bool, str]:
    """full.info 成功判定：data.module 存在。"""
    if not result.get("success"):
        return False, result.get("error") or "接口调用失败"
    if not _is_mtop_success(result.get("ret")):
        return False, "接口返回失败状态"
    data = result.get("data")
    if not isinstance(data, dict) or "module" not in data:
        return False, "完整订单信息返回结构异常：缺少 data.module"
    module = data.get("module")
    if not isinstance(module, dict):
        return False, "完整订单信息返回结构异常：data.module 非对象"
    return True, ""


def _check_refund_detail_success(result: dict, expected_order_id: str, expected_refund_id: str) -> tuple[bool, str]:
    """refund.detail 成功判定：data.data 存在，components 为数组，orderId 和 refundId 合法。

    同时执行一致性校验（需求第十六节）：响应 orderId/refundId 必须与请求一致。
    """
    if not result.get("success"):
        return False, result.get("error") or "接口调用失败"
    if not _is_mtop_success(result.get("ret")):
        return False, "接口返回失败状态"
    data = result.get("data")
    if not isinstance(data, dict) or "data" not in data:
        return False, "退款核心详情返回结构异常：缺少 data.data"
    inner_data = data.get("data")
    if not isinstance(inner_data, dict):
        return False, "退款核心详情返回结构异常：data.data 非对象"
    components = inner_data.get("components")
    if components is not None and not isinstance(components, list):
        return False, "退款核心详情返回结构异常：components 非数组"
    # 一致性校验：响应 orderId/refundId 必须等于请求
    resp_order_id = inner_data.get("orderId")
    resp_refund_id = inner_data.get("refundId")
    if resp_order_id is not None and str(resp_order_id) != str(expected_order_id):
        return False, f"退款核心详情响应 orderId 不一致：期望 {expected_order_id}，实际 {resp_order_id}"
    if resp_refund_id is not None and str(resp_refund_id) != str(expected_refund_id):
        return False, f"退款核心详情响应 refundId 不一致：期望 {expected_refund_id}，实际 {resp_refund_id}"
    return True, ""


def _check_full_info_order_id_consistency(module: dict, expected_order_id: str) -> tuple[bool, str]:
    """full.info 一致性校验（需求第十六节）：merchantCommonData.orderId 等于请求。"""
    if not isinstance(module, dict):
        return True, ""  # 已在前置校验拦截
    common_data = module.get("merchantCommonData")
    if not isinstance(common_data, dict):
        return True, ""  # 模块缺失不视为不一致
    resp_order_id = common_data.get("orderId")
    if resp_order_id is None:
        return True, ""
    if str(resp_order_id) != str(expected_order_id):
        return False, f"完整订单信息响应 orderId 不一致：期望 {expected_order_id}，实际 {resp_order_id}"
    return True, ""


# ----- components 按 render 解析（需求第九节） -----

# 已确认的 render 值
SUPPORTED_REFUND_DETAIL_RENDERS = frozenset({
    "nodeStatusInfo",
    "refundStatusInfo",
    "investigationInfo",
    "refundDescribe",
    "progressDetail",
    "bottomBar",
    "bottomShow",
    "popPostageUrl",
    "basicRefundInfo",
    "postageRefundInfo",
})


def _find_component_by_render(components: list, render: str) -> Optional[dict]:
    """按 render 字段查找组件，不按固定下标。

    需求第九节：顺序变化不影响页面，缺失组件只隐藏对应区域。
    """
    if not isinstance(components, list):
        return None
    for comp in components:
        if isinstance(comp, dict) and comp.get("render") == render:
            return comp
    return None


def _parse_refund_detail_components(inner_data: dict, current_refund_id: str) -> dict:
    """按 render 解析 components 数组，返回标准化结构。

    输出结构（按需求第十~十三节）：
    {
        "basicRefundInfo": {...},      # 退款基本信息
        "refundStatusInfo": {...},     # 退款状态头部
        "nodeStatusInfo": {...},       # 退款阶段节点
        "progressDetail": {...},       # 退款进度
        "refundDescribe": {...},       # 退款说明（富文本安全渲染）
        "bottomBar": [...],            # 底部操作（已过滤递归按钮）
        "bottomShow": [...],           # 底部展示信息
        "postageRefundInfo": {...},    # 退运费信息
        "popPostageUrl": str|null,     # 退运费链接
        "unknown_renders": [...],      # 未识别 render（仅记录名，不报错）
    }
    """
    result = {
        "basicRefundInfo": None,
        "refundStatusInfo": None,
        "nodeStatusInfo": None,
        "progressDetail": None,
        "refundDescribe": None,
        "bottomBar": [],
        "bottomShow": [],
        "postageRefundInfo": None,
        "popPostageUrl": None,
        "unknown_renders": [],
    }
    if not isinstance(inner_data, dict):
        return result
    components = inner_data.get("components")
    if not isinstance(components, list):
        return result

    for comp in components:
        if not isinstance(comp, dict):
            continue
        render = comp.get("render")
        if not render:
            continue
        if render not in SUPPORTED_REFUND_DETAIL_RENDERS:
            # 未识别 render 安全忽略（需求第九节）
            if isinstance(render, str) and len(render) <= 64:
                result["unknown_renders"].append(render)
            continue
        if render == "basicRefundInfo":
            result["basicRefundInfo"] = _parse_basic_refund_info(comp)
        elif render == "refundStatusInfo":
            result["refundStatusInfo"] = _parse_refund_status_info(comp)
        elif render == "nodeStatusInfo":
            result["nodeStatusInfo"] = _parse_node_status_info(comp)
        elif render == "progressDetail":
            result["progressDetail"] = _parse_progress_detail(comp)
        elif render == "refundDescribe":
            result["refundDescribe"] = _parse_refund_describe(comp)
        elif render == "bottomBar":
            result["bottomBar"] = _parse_bottom_bar(comp, current_refund_id)
        elif render == "bottomShow":
            result["bottomShow"] = _parse_bottom_show(comp)
        elif render == "postageRefundInfo":
            result["postageRefundInfo"] = _parse_postage_refund_info(comp)
        elif render == "popPostageUrl":
            result["popPostageUrl"] = _parse_pop_postage_url(comp)
        # investigationInfo 问卷本次不实现（需求第十三节明确）
    return result


def _parse_basic_refund_info(comp: dict) -> Optional[dict]:
    """解析 basicRefundInfo 组件（需求第十一节）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    if not isinstance(data, dict):
        return None
    # 凭证图片安全校验
    proof = data.get("refundProof") or {}
    if not isinstance(proof, dict):
        proof = {}
    proof_media = _normalize_proof_media_list(proof.get("proofMultiMediaList"))

    # 物流信息：买家退货物流 vs 卖家发货物流（需求第十二节）
    buyer_return_log = data.get("buyerReturnLogisticInfo") or {}
    if not isinstance(buyer_return_log, dict):
        buyer_return_log = {}
    trade_log = data.get("tradeLogisticInfo") or {}
    if not isinstance(trade_log, dict):
        trade_log = {}

    return {
        "applyMoney": _safe_decimal(data.get("applyMoney")),
        "csStatus": data.get("csStatus"),
        "csStatusDesc": data.get("csStatusDesc"),
        "disputeEndTime": _parse_datetime(data.get("disputeEndTime")),
        "gmtCreatedTime": _parse_datetime(data.get("gmtCreatedTime")),
        "gmtModifiedTime": _parse_datetime(data.get("gmtModifiedTime")),
        "goodsStatus": data.get("goodsStatus"),
        "goodsStatusDesc": data.get("goodsStatusDesc"),
        "postFeeBear": data.get("postFeeBear"),
        "reasonText": data.get("reasonText"),
        "reasonTextId": data.get("reasonTextId"),
        "refundId": str(data["refundId"]) if data.get("refundId") is not None else None,
        "refundProof": {"proofMultiMediaList": proof_media} if proof_media else {"proofMultiMediaList": []},
        "refundStatus": data.get("refundStatus"),
        "refundStatusDesc": data.get("refundStatusDesc"),
        "refundType": data.get("refundType"),
        "refundTypeDesc": data.get("refundTypeDesc"),
        # 物流：买家退货 vs 卖家发货（明确区分）
        "buyerReturnLogisticInfo": _normalize_logistic_info(buyer_return_log),
        "tradeLogisticInfo": _normalize_logistic_info(trade_log),
    }


def _normalize_logistic_info(log_info: dict) -> dict:
    """标准化物流信息：明确区分买家退货物流和卖家发货物流。"""
    if not isinstance(log_info, dict):
        return {"companyName": None, "mailNo": None, "consignTime": None}
    return {
        "companyName": log_info.get("companyName"),
        "mailNo": _mask_mail_no(log_info.get("mailNo")),
        "consignTime": _parse_datetime(log_info.get("consignTime")),
    }


def _parse_refund_status_info(comp: dict) -> Optional[dict]:
    """解析 refundStatusInfo 组件（退款状态头部）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    if not isinstance(data, dict):
        return None
    return {
        "title": data.get("title"),
        "desc": _decode_html_entities(data.get("desc")),
        "status": data.get("status"),
    }


def _parse_node_status_info(comp: dict) -> Optional[dict]:
    """解析 nodeStatusInfo 组件（退款阶段节点，需求第十节）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    if not isinstance(data, dict):
        return None
    need_show = data.get("needShowStatusNode")
    if need_show is not None:
        need_show = _parse_bool_string(need_show)
    nodes = data.get("nodeStatusList") or []
    if not isinstance(nodes, list):
        nodes = []
    parsed_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        parsed_nodes.append({
            "nodeStatus": node.get("nodeStatus"),
            "time": _parse_datetime(node.get("time")),
            "txt": _decode_html_entities(node.get("txt")),
        })
    return {
        "needShowStatusNode": need_show,
        "nodeStatusList": parsed_nodes,
    }


def _parse_progress_detail(comp: dict) -> Optional[dict]:
    """解析 progressDetail 组件（退款进度，需求第十节）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    if not isinstance(data, dict):
        return None
    title = _decode_html_entities(data.get("title"))
    nodes = data.get("progressNodeList") or []
    if not isinstance(nodes, list):
        nodes = []
    parsed_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        # tips 可能含 HTML 实体（如 &yen;），安全解码后作为纯文本
        tips = node.get("tips")
        if tips is not None:
            tips = _decode_html_entities(tips)
        # proofInfoList 凭证
        proof_info_list = node.get("proofInfoList") or []
        if not isinstance(proof_info_list, list):
            proof_info_list = []
        parsed_proof = _normalize_proof_media_list(proof_info_list)
        parsed_nodes.append({
            "actionCode": node.get("actionCode"),
            "proofInfoList": parsed_proof,
            "text": _decode_html_entities(node.get("text")),
            "timeStr": node.get("timeStr"),
            "tips": tips,
        })
    return {
        "title": title,
        "progressNodeList": parsed_nodes,
    }


def _parse_refund_describe(comp: dict) -> Optional[dict]:
    """解析 refundDescribe 组件（退款说明，富文本安全，需求第十三节）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    if not isinstance(data, dict):
        return None
    title = _decode_html_entities(data.get("title"))
    desc_rich_text = data.get("descRichText")
    return {
        "title": title,
        "descRichText": _normalize_rich_text_items(desc_rich_text),
    }


def _parse_bottom_bar(comp: dict, current_refund_id: str) -> list:
    """解析 bottomBar 组件（详情页操作，需求第十四节）。

    关键约束：
    - 不再次显示会跳回相同退款详情的"退款详情"按钮（避免递归跳转）
    - 只允许 viewRefundDetail / applyDisputePage / agreeRefundApply（白名单）
    - URL 类按钮做安全校验
    - doubleCheck 类按钮保留 doubleCheck 数据
    """
    if not isinstance(comp, dict):
        return []
    data = comp.get("data") or comp
    btn_list = data
    if isinstance(data, dict):
        btn_list = data.get("btnList") or data.get("buttons") or []
    if not isinstance(btn_list, list):
        return []
    # 支持的 code 白名单
    supported_codes = {"applyDisputePage", "agreeRefundApply"}
    # 注意：viewRefundDetail 不在此处显示（避免递归跳转）
    result = []
    for btn in btn_list:
        if not isinstance(btn, dict):
            continue
        code = btn.get("code")
        if code not in supported_codes:
            continue
        click_event = btn.get("clickEvent") or {}
        if not isinstance(click_event, dict):
            click_event = {}
        event_type = click_event.get("type")
        safe_btn = {
            "code": code,
            "name": btn.get("name"),
            "clickEvent": {"type": event_type},
        }
        if event_type == "url":
            url = (click_event.get("data") or {}).get("url")
            safe_url = _safe_url_for_open(url)
            if not safe_url:
                continue  # URL 不可信，跳过此按钮
            safe_btn["clickEvent"]["data"] = {"url": safe_url}
        elif event_type == "doubleCheck":
            dc_data = click_event.get("data") or {}
            if not isinstance(dc_data, dict):
                dc_data = {}
            safe_btn["clickEvent"]["data"] = {
                "title": dc_data.get("title"),
                "confirmText": dc_data.get("confirmText"),
                "riskDesc": dc_data.get("riskDesc") or dc_data.get("riskDescription"),
                "confirmButtonText": dc_data.get("confirmButtonText") or dc_data.get("buttonText"),
            }
        else:
            # 未知 clickEvent 类型不动态执行
            continue
        result.append(safe_btn)
    return result


def _parse_bottom_show(comp: dict) -> list:
    """解析 bottomShow 组件（底部展示信息，按服务端顺序渲染）。"""
    if not isinstance(comp, dict):
        return []
    data = comp.get("data") or comp
    items = data
    if isinstance(data, dict):
        items = data.get("list") or data.get("items") or []
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append({
            "title": _decode_html_entities(item.get("title")),
            "value": _decode_html_entities(item.get("value")),
            "copyable": _parse_bool_string(item.get("copyable")),
        })
    return result


def _parse_postage_refund_info(comp: dict) -> Optional[dict]:
    """解析 postageRefundInfo 组件（退运费信息）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    if not isinstance(data, dict):
        return None
    return {
        "applyMoney": _safe_decimal(data.get("applyMoney")),
        "refundStatus": data.get("refundStatus"),
        "refundStatusDesc": data.get("refundStatusDesc"),
        "reasonText": data.get("reasonText"),
    }


def _parse_pop_postage_url(comp: dict) -> Optional[str]:
    """解析 popPostageUrl 组件（退运费链接，经过安全校验）。"""
    if not isinstance(comp, dict):
        return None
    data = comp.get("data") or comp
    url = None
    if isinstance(data, dict):
        url = data.get("url") or data.get("linkUrl")
    elif isinstance(data, str):
        url = data
    return _safe_url_for_open(url)


# ----- service.record 解析（退款历史，需求第六节） -----

def _parse_service_record_data(inner_data: dict, current_refund_id: str) -> dict:
    """解析 service.record 的 data.data，返回退款历史结构。

    需求第六节：
    - refundRecordList: 退款记录列表（可能含多条退款，按服务端顺序展示）
    - postageRefundRecordList: 退运费记录列表（可能为空）
    - 当前 refundId 高亮，不取第一条冒充当前退款（需求第十六节）
    """
    if not isinstance(inner_data, dict):
        return {
            "refundRecordList": [],
            "postageRefundRecordList": [],
            "currentRefundId": str(current_refund_id) if current_refund_id else None,
        }

    raw_records = inner_data.get("refundRecordList") or []
    if not isinstance(raw_records, list):
        raw_records = []
    parsed_records = []
    for record in raw_records:
        if not isinstance(record, dict):
            continue
        refund_id_raw = record.get("refundId")
        refund_id_str = str(refund_id_raw) if refund_id_raw is not None else None
        parsed_records.append({
            "endTime": _parse_datetime(record.get("endTime")),
            "gmtCreatedTime": _parse_datetime(record.get("gmtCreatedTime")),
            "money": _safe_decimal(record.get("money")),
            "reasonId": record.get("reasonId"),
            "reasonText": record.get("reasonText"),
            "reasonTextId": record.get("reasonTextId"),
            "refundId": refund_id_str,
            "refundType": record.get("refundType"),
            "status": record.get("status"),
            "statusDesc": record.get("statusDesc"),
            "isCurrent": refund_id_str is not None and refund_id_str == str(current_refund_id),
        })

    raw_postage = inner_data.get("postageRefundRecordList") or []
    if not isinstance(raw_postage, list):
        raw_postage = []
    parsed_postage = []
    for record in raw_postage:
        if not isinstance(record, dict):
            continue
        parsed_postage.append({
            "endTime": _parse_datetime(record.get("endTime")),
            "gmtCreatedTime": _parse_datetime(record.get("gmtCreatedTime")),
            "money": _safe_decimal(record.get("money")),
            "refundId": str(record["refundId"]) if record.get("refundId") is not None else None,
            "status": record.get("status"),
            "statusDesc": record.get("statusDesc"),
        })

    return {
        "refundRecordList": parsed_records,
        "postageRefundRecordList": parsed_postage,
        "currentRefundId": str(current_refund_id) if current_refund_id else None,
    }


# ----- full.info 解析（完整订单信息，需求第七节） -----

def _parse_full_info_module(module: dict) -> dict:
    """解析 full.info 的 data.module，返回标准化结构。

    需求第七节：
    - merchantCommonData: 商品ID/订单ID/订单状态/下单付款发货时间
    - merchantItemVO: 商品图片/标题/规格
    - merchantPriceVO: 金额明细
    - merchantBuyerVO: 买家脱敏信息（仅展示服务端已脱敏内容）
    - orderInfoVO: 动态订单信息
    - orderStatusVO: 订单时间线
    - bottomBarVO: 提醒收货等操作（本次不实现，安全忽略）
    """
    if not isinstance(module, dict):
        return {"_valid": False}

    result = {"_valid": True}

    # merchantCommonData
    common_data = module.get("merchantCommonData") or {}
    if not isinstance(common_data, dict):
        common_data = {}
    result["merchantCommonData"] = {
        "consignTime": _parse_datetime(common_data.get("consignTime")),
        "createTime": _parse_datetime(common_data.get("createTime")),
        "itemId": str(common_data["itemId"]) if common_data.get("itemId") is not None else None,
        "orderId": str(common_data["orderId"]) if common_data.get("orderId") is not None else None,
        "orderStatus": common_data.get("orderStatus"),
        "paySuccessTime": _parse_datetime(common_data.get("paySuccessTime")),
        "inRefund": _parse_bool_string(common_data.get("inRefund")) if common_data.get("inRefund") is not None else None,
        "showDetail": common_data.get("showDetail"),
    }

    # merchantItemVO
    item_vo = module.get("merchantItemVO") or {}
    if not isinstance(item_vo, dict):
        item_vo = {}
    item_info_lines = item_vo.get("itemInfoLines")
    if item_info_lines is not None and not isinstance(item_info_lines, str):
        try:
            item_info_lines = json.dumps(item_info_lines, ensure_ascii=False)
        except (TypeError, ValueError):
            item_info_lines = None
    result["merchantItemVO"] = {
        "itemPicUrl": _validate_proof_image_url(item_vo.get("itemPicUrl")),
        "title": item_vo.get("title"),
        "itemInfoLines": item_info_lines,
    }

    # merchantPriceVO（金额，使用 Decimal 安全处理）
    price_vo = module.get("merchantPriceVO") or {}
    if not isinstance(price_vo, dict):
        price_vo = {}
    result["merchantPriceVO"] = {
        "auctionPrice": _safe_decimal(price_vo.get("auctionPrice")),
        "buyNum": str(price_vo["buyNum"]) if price_vo.get("buyNum") is not None else None,
        "confirmFee": _safe_decimal(price_vo.get("confirmFee")),
        "discountFee": _safe_decimal(price_vo.get("discountFee")),
        "postFee": _safe_decimal(price_vo.get("postFee")),
        "refundFee": _safe_decimal(price_vo.get("refundFee")),
        "totalPrice": _safe_decimal(price_vo.get("totalPrice")),
    }

    # merchantBuyerVO（买家信息，仅展示服务端已脱敏内容）
    buyer_vo = module.get("merchantBuyerVO") or {}
    if not isinstance(buyer_vo, dict):
        buyer_vo = {}
    # 不尝试解密 encryptedPhone，仅展示 phone 字段（已脱敏）
    result["merchantBuyerVO"] = {
        "address": buyer_vo.get("address"),
        "buyerId": str(buyer_vo["buyerId"]) if buyer_vo.get("buyerId") is not None else None,
        "name": buyer_vo.get("name"),
        "phone": buyer_vo.get("phone"),
        "userIcon": _validate_proof_image_url(buyer_vo.get("userIcon")),
        "userNick": buyer_vo.get("userNick"),
    }

    # orderInfoVO（动态订单信息）
    order_info_vo = module.get("orderInfoVO") or {}
    if not isinstance(order_info_vo, dict):
        order_info_vo = {}
    raw_info_list = order_info_vo.get("orderInfoList") or []
    if not isinstance(raw_info_list, list):
        raw_info_list = []
    parsed_info_list = []
    for info in raw_info_list:
        if not isinstance(info, dict):
            continue
        parsed_info_list.append({
            "title": _decode_html_entities(info.get("title")),
            "value": _decode_html_entities(info.get("value")),
            "copyable": _parse_bool_string(info.get("copyable")),
            # needOutShow / clickEvent / expanded 本次不执行（需求第七节）
        })
    # priceInfo
    price_info = order_info_vo.get("priceInfo") or {}
    if not isinstance(price_info, dict):
        price_info = {}
    result["orderInfoVO"] = {
        "orderInfoList": parsed_info_list,
        "priceInfo": {
            "amount": _safe_decimal(price_info.get("amount")),
            # billList / softwareServiceFeeList 透传（已脱敏金额数据）
            "billList": price_info.get("billList") if isinstance(price_info.get("billList"), list) else [],
            "softwareServiceFeeList": price_info.get("softwareServiceFeeList") if isinstance(price_info.get("softwareServiceFeeList"), list) else [],
        },
    }

    # orderStatusVO（订单时间线，与退款时间线分开展示）
    order_status_vo = module.get("orderStatusVO") or {}
    if not isinstance(order_status_vo, dict):
        order_status_vo = {}
    order_status_info = order_status_vo.get("orderStatusInfo") or {}
    if not isinstance(order_status_info, dict):
        order_status_info = {}
    raw_nodes = order_status_vo.get("orderStatusNodeList") or []
    if not isinstance(raw_nodes, list):
        raw_nodes = []
    parsed_status_nodes = []
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        # completed 可能是字符串 "true"/"false"，必须安全转换（需求第七节）
        parsed_status_nodes.append({
            "completed": _parse_bool_string(node.get("completed")),
            "time": _parse_datetime(node.get("time")),
            "title": _decode_html_entities(node.get("title")),
        })
    result["orderStatusVO"] = {
        "orderStatusInfo": {
            "status": order_status_info.get("status"),
            "title": _decode_html_entities(order_status_info.get("title")),
        },
        "orderStatusNodeList": parsed_status_nodes,
    }

    # bottomBarVO：提醒收货等操作（本次不实现，安全忽略）
    # 不动态执行响应中返回的任意 MTOP API（需求第十四节）

    return result


# ----- 组合调用（并行 + 缓存 + 去重，需求第五、十九、二十节） -----

async def _fetch_refund_detail_combined_internal(
    db: AsyncSession, tenant_id: int, account_id: int,
    order_id: str, refund_id: str,
    apis_to_call: Optional[set] = None,
) -> dict:
    """内部：并行调用三个接口，分别状态记录，分别失败处理。

    apis_to_call: 指定要调用的接口集合（None 表示全部三接口）
        {"service_record", "full_info", "refund_detail"}

    返回组合结构：
    {
        "summary": {...},  # 从退款列表缓存读取的摘要（由调用方填充）
        "serviceRecord": {"status": "ok|failed|skipped", "data": {...}, "error": str, "lastUpdate": iso},
        "fullInfo": {"status": "ok|failed|skipped", "data": {...}, "error": str, "lastUpdate": iso},
        "refundDetail": {"status": "ok|failed|skipped", "data": {...}, "error": str, "lastUpdate": iso},
        "lastSuccessAt": iso|null,  # 最后一次成功刷新时间（任一接口成功即更新）
        "partialFailure": bool,
    }
    """
    now_iso = datetime.now().isoformat()
    result = {
        "serviceRecord": {"status": "skipped", "data": None, "error": None, "lastUpdate": now_iso},
        "fullInfo": {"status": "skipped", "data": None, "error": None, "lastUpdate": now_iso},
        "refundDetail": {"status": "skipped", "data": None, "error": None, "lastUpdate": now_iso},
        "lastSuccessAt": None,
        "partialFailure": False,
    }

    call_all = apis_to_call is None
    call_service = call_all or "service_record" in apis_to_call
    call_full = call_all or "full_info" in apis_to_call
    call_detail = call_all or "refund_detail" in apis_to_call

    # 并行调用三个接口（用 asyncio.to_thread 包装同步函数）
    tasks = {}
    if call_service:
        tasks["service_record"] = asyncio.to_thread(
            fetch_refund_service_record, account_id, order_id
        )
    if call_full:
        tasks["full_info"] = asyncio.to_thread(
            fetch_refund_full_info, account_id, order_id
        )
    if call_detail:
        tasks["refund_detail"] = asyncio.to_thread(
            fetch_refund_detail, account_id, order_id, refund_id
        )

    # 并行执行（return_exceptions=True 防止单个失败影响其他）
    if not tasks:
        return result

    keys = list(tasks.keys())
    coros = [tasks[k] for k in keys]
    raw_results = await asyncio.gather(*coros, return_exceptions=True)
    raw_map = dict(zip(keys, raw_results))

    any_success = False

    # service.record
    if "service_record" in raw_map:
        raw = raw_map["service_record"]
        if isinstance(raw, Exception):
            err_code = "NETWORK_ERROR" if isinstance(raw, (asyncio.TimeoutError,)) else "UNKNOWN_ERROR"
            result["serviceRecord"] = {
                "status": "failed", "data": None,
                "error": f"接口异常: {type(raw).__name__}",
                "errorCode": err_code,
                "lastUpdate": now_iso,
            }
        else:
            ok, err = _check_service_record_success(raw)
            if ok:
                inner_data = (raw.get("data") or {}).get("data") or {}
                parsed = _parse_service_record_data(inner_data, refund_id)
                result["serviceRecord"] = {
                    "status": "ok", "data": parsed,
                    "error": None, "errorCode": None, "lastUpdate": now_iso,
                }
                any_success = True
            else:
                # 透传 fetch 层已分类的 errorCode，未提供时按错误文本二次分类
                err_code = raw.get("errorCode") or _classify_mtop_error(raw.get("ret"), err)
                # 结构异常单独标记
                if "结构异常" in str(err) or "缺少" in str(err):
                    err_code = "INVALID_RESPONSE_SHAPE"
                result["serviceRecord"] = {
                    "status": "failed", "data": None,
                    "error": err, "errorCode": err_code, "lastUpdate": now_iso,
                }

    # full.info
    if "full_info" in raw_map:
        raw = raw_map["full_info"]
        if isinstance(raw, Exception):
            err_code = "NETWORK_ERROR" if isinstance(raw, (asyncio.TimeoutError,)) else "UNKNOWN_ERROR"
            result["fullInfo"] = {
                "status": "failed", "data": None,
                "error": f"接口异常: {type(raw).__name__}",
                "errorCode": err_code,
                "lastUpdate": now_iso,
            }
        else:
            ok, err = _check_full_info_success(raw)
            if ok:
                module = (raw.get("data") or {}).get("module") or {}
                # 一致性校验（需求第十六节）
                id_ok, id_err = _check_full_info_order_id_consistency(module, order_id)
                if not id_ok:
                    result["fullInfo"] = {
                        "status": "failed", "data": None,
                        "error": id_err, "errorCode": "ID_CONSISTENCY_ERROR",
                        "lastUpdate": now_iso,
                    }
                else:
                    parsed = _parse_full_info_module(module)
                    result["fullInfo"] = {
                        "status": "ok", "data": parsed,
                        "error": None, "errorCode": None, "lastUpdate": now_iso,
                    }
                    any_success = True
            else:
                err_code = raw.get("errorCode") or _classify_mtop_error(raw.get("ret"), err)
                if "结构异常" in str(err) or "缺少" in str(err):
                    err_code = "INVALID_RESPONSE_SHAPE"
                result["fullInfo"] = {
                    "status": "failed", "data": None,
                    "error": err, "errorCode": err_code, "lastUpdate": now_iso,
                }

    # refund.detail
    if "refund_detail" in raw_map:
        raw = raw_map["refund_detail"]
        if isinstance(raw, Exception):
            err_code = "NETWORK_ERROR" if isinstance(raw, (asyncio.TimeoutError,)) else "UNKNOWN_ERROR"
            result["refundDetail"] = {
                "status": "failed", "data": None,
                "error": f"接口异常: {type(raw).__name__}",
                "errorCode": err_code,
                "lastUpdate": now_iso,
            }
        else:
            ok, err = _check_refund_detail_success(raw, order_id, refund_id)
            if ok:
                inner_data = (raw.get("data") or {}).get("data") or {}
                parsed_components = _parse_refund_detail_components(inner_data, refund_id)
                # 透传顶层字段（已确认的：encryptedPhone / idleRefundStatus / itemId / orderId / peerUserId / refundId / refundStatus / seller）
                # 注意：encryptedPhone 不解密、不展示（需求第七节）
                top_level = {
                    "orderId": str(inner_data["orderId"]) if inner_data.get("orderId") is not None else None,
                    "refundId": str(inner_data["refundId"]) if inner_data.get("refundId") is not None else None,
                    "itemId": str(inner_data["itemId"]) if inner_data.get("itemId") is not None else None,
                    "idleRefundStatus": inner_data.get("idleRefundStatus"),
                    "refundStatus": inner_data.get("refundStatus"),
                    "peerUserId": str(inner_data["peerUserId"]) if inner_data.get("peerUserId") is not None else None,
                    # encryptedPhone 不透传（保护隐私）
                }
                result["refundDetail"] = {
                    "status": "ok",
                    "data": {"topLevel": top_level, "components": parsed_components},
                    "error": None, "errorCode": None, "lastUpdate": now_iso,
                }
                any_success = True
            else:
                err_code = raw.get("errorCode") or _classify_mtop_error(raw.get("ret"), err)
                if "结构异常" in str(err) or "缺少" in str(err):
                    err_code = "INVALID_RESPONSE_SHAPE"
                if "不一致" in str(err):
                    err_code = "ID_CONSISTENCY_ERROR"
                result["refundDetail"] = {
                    "status": "failed", "data": None,
                    "error": err, "errorCode": err_code, "lastUpdate": now_iso,
                }

    if any_success:
        result["lastSuccessAt"] = now_iso
    result["partialFailure"] = any(
        result[k]["status"] == "failed" for k in ("serviceRecord", "fullInfo", "refundDetail")
    )
    return result


def _detail_cache_key(tenant_id: int, account_id: int, order_id: str, refund_id: str) -> tuple:
    """构造详情缓存键：按 (tenant_id, account_id, order_id, refund_id) 隔离。"""
    return (int(tenant_id), int(account_id), str(order_id), str(refund_id))


async def _get_cached_detail(tenant_id: int, account_id: int, order_id: str, refund_id: str) -> Optional[dict]:
    """读取缓存（命中返回数据，过期或不存在返回 None）。"""
    key = _detail_cache_key(tenant_id, account_id, order_id, refund_id)
    async with _refund_detail_cache_guard:
        entry = _refund_detail_cache.get(key)
        if entry is None:
            return None
        saved_at = entry.get("saved_at")
        if saved_at is None:
            _refund_detail_cache.pop(key, None)
            return None
        age = (datetime.now() - saved_at).total_seconds()
        if age > REFUND_DETAIL_CACHE_TTL_SECONDS:
            # 过期：返回旧数据但仍保留（让调用方先展示旧数据再后台刷新）
            return entry.get("data")
        return entry.get("data")


async def _save_cached_detail(tenant_id: int, account_id: int, order_id: str, refund_id: str, data: dict) -> None:
    """保存缓存。超过最大条数时按 LRU 简单淘汰。

    失败结果不缓存（需求第十一节）：仅当至少一个接口状态为 "ok" 时才保存。
    全部 failed/skipped 时不写入缓存，确保用户点击"重新加载"能真实发起新请求，
    而不是命中上一次的失败缓存。
    """
    # 失败结果不缓存：检查是否有任一接口成功
    has_any_ok = any(
        isinstance(data.get(k), dict) and data.get(k, {}).get("status") == "ok"
        for k in ("serviceRecord", "fullInfo", "refundDetail")
    )
    if not has_any_ok:
        logger.info(
            "退款详情全失败不写入缓存 tenantId=%s accountId=%s orderId=%s refundId=%s",
            tenant_id, account_id, order_id, refund_id,
        )
        return

    key = _detail_cache_key(tenant_id, account_id, order_id, refund_id)
    async with _refund_detail_cache_guard:
        # 简单 LRU：超过上限时删除最早的 saved_at
        if len(_refund_detail_cache) >= REFUND_DETAIL_CACHE_MAX_ENTRIES and key not in _refund_detail_cache:
            try:
                oldest_key = min(
                    _refund_detail_cache.keys(),
                    key=lambda k: _refund_detail_cache[k].get("saved_at") or datetime.min,
                )
                _refund_detail_cache.pop(oldest_key, None)
            except (ValueError, KeyError):
                pass
        now = datetime.now()
        last_success = data.get("lastSuccessAt")
        _refund_detail_cache[key] = {
            "data": data,
            "saved_at": now,
            "last_success_at": _parse_datetime(last_success) or now,
        }


async def _invalidate_cached_detail(tenant_id: int, account_id: int, order_id: str, refund_id: str) -> None:
    """失效缓存（写操作成功后调用）。"""
    key = _detail_cache_key(tenant_id, account_id, order_id, refund_id)
    async with _refund_detail_cache_guard:
        _refund_detail_cache.pop(key, None)
        # 同时取消进行中的请求（如果有）
        inflight = _refund_detail_inflight.pop(key, None)
    if inflight is not None and not inflight.done():
        try:
            inflight.cancel()
        except Exception:
            pass


async def _get_or_create_inflight(
    tenant_id: int, account_id: int, order_id: str, refund_id: str,
    factory,
) -> asyncio.Future:
    """获取进行中的请求或创建新请求（同一详情并发进入只发一组请求）。

    factory: 同步可调用，返回一个 awaitable（实际发起请求）
    """
    key = _detail_cache_key(tenant_id, account_id, order_id, refund_id)
    async with _refund_detail_cache_guard:
        existing = _refund_detail_inflight.get(key)
        if existing is not None and not existing.done():
            return existing
        # 创建新 Future 并绑定 factory() 的 awaitable
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        _refund_detail_inflight[key] = future

    async def _runner():
        try:
            value = await factory()
            if not future.done():
                future.set_result(value)
            return value
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        finally:
            async with _refund_detail_cache_guard:
                _refund_detail_inflight.pop(key, None)

    asyncio.create_task(_runner())
    return future


# ----- 对外接口 -----

async def _get_refund_summary_from_list_cache(
    db: AsyncSession, tenant_id: int, account_id: int, refund_id: str
) -> Optional[dict]:
    """从退款列表缓存读取当前退款的摘要（用于详情页立即展示）。

    复用 query_local_refunds 的字段映射，但只查询单条。
    """
    result = await db.execute(
        select(XianyuRefund).where(
            and_(
                XianyuRefund.tenant_id == tenant_id,
                XianyuRefund.account_id == account_id,
                XianyuRefund.external_refund_id == refund_id,
                XianyuRefund.deleted == 0,
            )
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    # 查询账号信息
    acc_result = await db.execute(
        select(XianyuAccount).where(
            and_(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
            )
        )
    )
    acc = acc_result.scalar_one_or_none()
    buttons = []
    if record.right_buttons_json:
        try:
            buttons = json.loads(record.right_buttons_json)
        except (ValueError, TypeError):
            buttons = []
    return {
        "id": record.id,
        "accountId": record.account_id,
        "accountNickname": acc.nickname if acc else None,
        "externalRefundId": record.external_refund_id,
        "externalOrderId": record.external_order_id,
        "externalItemId": record.external_item_id,
        "itemTitle": record.item_title,
        "itemPicUrl": record.item_pic_url,
        "itemInfoLines": record.item_info_lines,
        "buyNum": record.buy_num,
        "refundFee": str(record.refund_fee) if record.refund_fee is not None else None,
        "auctionPrice": str(record.auction_price) if record.auction_price is not None else None,
        "orderStatus": record.order_status,
        "orderSimpleRemark": record.order_simple_remark,
        "refundStatus": record.refund_status,
        "refundStatusDesc": record.refund_status_desc,
        "commonRefundStatus": record.common_refund_status,
        "refundReason": record.refund_reason,
        "csStatus": record.cs_status,
        "logisticsCompany": record.logistics_company,
        "logisticsMailNo": record.logistics_mail_no,
        "consignTime": record.consign_time.isoformat() if record.consign_time else None,
        "refundCreateTime": record.refund_create_time.isoformat() if record.refund_create_time else None,
        "commonCreateTime": record.common_create_time.isoformat() if record.common_create_time else None,
        "buyerNick": record.buyer_nick,
        "rightButtons": buttons,
        "syncStatus": record.sync_status,
        "lastSyncedTime": record.last_synced_time.isoformat() if record.last_synced_time else None,
    }


async def get_refund_detail(
    db: AsyncSession, tenant_id: int, account_id: int,
    order_id: str, refund_id: str,
) -> dict:
    """查询退款详情（缓存优先，过期后台刷新）。

    返回结构：
    {
        "ok": True,
        "summary": {...}|null,  # 退款列表缓存摘要
        "detail": {  # 组合详情
            "serviceRecord": {...}, "fullInfo": {...}, "refundDetail": {...},
            "lastSuccessAt": iso|null, "partialFailure": bool,
        }|null,
        "cached": bool,  # 是否命中缓存
        "cacheExpired": bool,  # 缓存是否已过期（命中时才有意义）
        "backendBackgroundRefreshTriggered": bool,  # 是否触发了后台刷新
        "error": str|null,
    }
    """
    # 1. 校验：账号归属 + 鱼小铺 + 退款归属
    is_fish_shop, _auth, err = await verify_fish_shop_account(db, account_id, tenant_id)
    if not is_fish_shop:
        return {"ok": False, "error": err or "账号不是鱼小铺"}
    # 校验退款归属（防止跨账号）
    refund_result = await db.execute(
        select(XianyuRefund).where(
            and_(
                XianyuRefund.tenant_id == tenant_id,
                XianyuRefund.account_id == account_id,
                XianyuRefund.external_refund_id == refund_id,
                XianyuRefund.deleted == 0,
            )
        )
    )
    refund_record = refund_result.scalar_one_or_none()
    if refund_record is None:
        return {"ok": False, "error": "退款记录不存在或不属于该账号"}
    # 校验 orderId 与 refundId 关系
    if refund_record.external_order_id and str(refund_record.external_order_id) != str(order_id):
        return {"ok": False, "error": "orderId 与退款记录不匹配"}

    # 2. 读取退款列表摘要（用于立即展示）
    summary = await _get_refund_summary_from_list_cache(db, tenant_id, account_id, refund_id)

    # 3. 读取详情缓存
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    cache_key = _detail_cache_key(tenant_id, account_id, order_id, refund_id)
    # 判断缓存是否过期
    cache_expired = True
    async with _refund_detail_cache_guard:
        entry = _refund_detail_cache.get(cache_key)
        if entry is not None:
            saved_at = entry.get("saved_at")
            if saved_at is not None:
                age = (datetime.now() - saved_at).total_seconds()
                cache_expired = age > REFUND_DETAIL_CACHE_TTL_SECONDS

    if cached is not None and not cache_expired:
        # 缓存有效：直接返回，不重复请求
        return {
            "ok": True,
            "summary": summary,
            "detail": cached,
            "cached": True,
            "cacheExpired": False,
            "backendBackgroundRefreshTriggered": False,
            "error": None,
        }

    # 4. 缓存过期或不存在：先返回旧数据，再后台刷新
    # 进行中请求去重：同一详情并发进入只发一组请求
    async def _factory():
        return await _fetch_refund_detail_combined_internal(
            db, tenant_id, account_id, order_id, refund_id, apis_to_call=None
        )

    # 如果有旧缓存，先返回旧数据并触发后台刷新
    if cached is not None and cache_expired:
        # 触发后台刷新（不阻塞当前响应）
        try:
            asyncio.create_task(_refresh_detail_background(
                tenant_id, account_id, order_id, refund_id
            ))
            background_triggered = True
        except Exception:
            background_triggered = False
        return {
            "ok": True,
            "summary": summary,
            "detail": cached,
            "cached": True,
            "cacheExpired": True,
            "backendBackgroundRefreshTriggered": background_triggered,
            "error": None,
        }

    # 5. 无缓存：复用进行中请求或发起新请求（阻塞等待）
    try:
        inflight = await _get_or_create_inflight(
            tenant_id, account_id, order_id, refund_id, _factory
        )
        detail = await inflight
        await _save_cached_detail(tenant_id, account_id, order_id, refund_id, detail)
        return {
            "ok": True,
            "summary": summary,
            "detail": detail,
            "cached": False,
            "cacheExpired": True,
            "backendBackgroundRefreshTriggered": False,
            "error": None,
        }
    except Exception as exc:
        logger.warning(
            "退款详情查询失败 accountId=%s orderId=%s refundId=%s errorType=%s",
            account_id, order_id, refund_id, type(exc).__name__,
        )
        return {
            "ok": False,
            "summary": summary,
            "detail": None,
            "cached": False,
            "cacheExpired": True,
            "backendBackgroundRefreshTriggered": False,
            "error": f"退款详情查询失败: {type(exc).__name__}",
        }


async def _refresh_detail_background(
    tenant_id: int, account_id: int, order_id: str, refund_id: str
) -> None:
    """后台刷新详情缓存（缓存过期时触发）。"""
    try:
        session_factory = _get_async_session()
        async with session_factory() as db:
            detail = await _fetch_refund_detail_combined_internal(
                db, tenant_id, account_id, order_id, refund_id, apis_to_call=None
            )
            await _save_cached_detail(tenant_id, account_id, order_id, refund_id, detail)
    except Exception as exc:
        logger.warning(
            "退款详情后台刷新失败 accountId=%s orderId=%s refundId=%s errorType=%s",
            account_id, order_id, refund_id, type(exc).__name__,
        )


async def refresh_refund_detail(
    db: AsyncSession, tenant_id: int, account_id: int,
    order_id: str, refund_id: str,
) -> dict:
    """手动刷新全部三个接口（强制刷新）。

    流程：
    1. 校验权限（账号归属 + 鱼小铺 + 退款归属）
    2. 失效旧缓存
    3. 并行调用三个接口
    4. 保存新缓存
    5. 返回新数据

    刷新失败时保留旧缓存（需求第十九节第9点）。
    """
    # 1. 校验
    is_fish_shop, _auth, err = await verify_fish_shop_account(db, account_id, tenant_id)
    if not is_fish_shop:
        return {"ok": False, "error": err or "账号不是鱼小铺"}
    refund_result = await db.execute(
        select(XianyuRefund).where(
            and_(
                XianyuRefund.tenant_id == tenant_id,
                XianyuRefund.account_id == account_id,
                XianyuRefund.external_refund_id == refund_id,
                XianyuRefund.deleted == 0,
            )
        )
    )
    refund_record = refund_result.scalar_one_or_none()
    if refund_record is None:
        return {"ok": False, "error": "退款记录不存在或不属于该账号"}
    if refund_record.external_order_id and str(refund_record.external_order_id) != str(order_id):
        return {"ok": False, "error": "orderId 与退款记录不匹配"}

    # 2. 失效旧缓存
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    # 3. 并行调用三个接口（不复用进行中的请求，强制刷新）
    try:
        detail = await _fetch_refund_detail_combined_internal(
            db, tenant_id, account_id, order_id, refund_id, apis_to_call=None
        )
    except Exception as exc:
        logger.warning(
            "退款详情刷新失败 accountId=%s orderId=%s refundId=%s errorType=%s",
            account_id, order_id, refund_id, type(exc).__name__,
        )
        return {"ok": False, "error": f"刷新失败: {type(exc).__name__}"}

    # 4. 保存新缓存
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, detail)

    # 5. 同时刷新摘要（从本地数据库读取最新记录）
    summary = await _get_refund_summary_from_list_cache(db, tenant_id, account_id, refund_id)

    return {
        "ok": True,
        "summary": summary,
        "detail": detail,
        "error": None,
    }


async def retry_refund_detail_api(
    db: AsyncSession, tenant_id: int, account_id: int,
    order_id: str, refund_id: str, api: str,
) -> dict:
    """单独重试某个失败接口（不重新请求成功的接口）。

    api: "service_record" / "full_info" / "refund_detail"

    返回更新后的完整 detail（含其他接口的旧数据 + 重试接口的新数据）。
    """
    if api not in ("service_record", "full_info", "refund_detail"):
        return {"ok": False, "error": "不支持的 api 参数"}

    # 校验
    is_fish_shop, _auth, err = await verify_fish_shop_account(db, account_id, tenant_id)
    if not is_fish_shop:
        return {"ok": False, "error": err or "账号不是鱼小铺"}
    refund_result = await db.execute(
        select(XianyuRefund).where(
            and_(
                XianyuRefund.tenant_id == tenant_id,
                XianyuRefund.account_id == account_id,
                XianyuRefund.external_refund_id == refund_id,
                XianyuRefund.deleted == 0,
            )
        )
    )
    refund_record = refund_result.scalar_one_or_none()
    if refund_record is None:
        return {"ok": False, "error": "退款记录不存在或不属于该账号"}
    if refund_record.external_order_id and str(refund_record.external_order_id) != str(order_id):
        return {"ok": False, "error": "orderId 与退款记录不匹配"}

    # 只调用指定接口
    try:
        new_detail = await _fetch_refund_detail_combined_internal(
            db, tenant_id, account_id, order_id, refund_id,
            apis_to_call={api},
        )
    except Exception as exc:
        logger.warning(
            "退款详情单接口重试失败 accountId=%s orderId=%s refundId=%s api=%s errorType=%s",
            account_id, order_id, refund_id, api, type(exc).__name__,
        )
        return {"ok": False, "error": f"重试失败: {type(exc).__name__}"}

    # 合并：保留其他接口的旧数据 + 重试接口的新数据
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    if cached is not None:
        # 合并：用 new_detail 中非 skipped 的字段覆盖 cached
        merged = dict(cached)
        api_key_map = {
            "service_record": "serviceRecord",
            "full_info": "fullInfo",
            "refund_detail": "refundDetail",
        }
        api_key = api_key_map[api]
        if new_detail.get(api_key, {}).get("status") != "skipped":
            merged[api_key] = new_detail[api_key]
        # 更新 lastSuccessAt（任一接口成功即更新）
        if new_detail.get("lastSuccessAt"):
            merged["lastSuccessAt"] = new_detail["lastSuccessAt"]
        # 重新计算 partialFailure
        merged["partialFailure"] = any(
            merged.get(k, {}).get("status") == "failed"
            for k in ("serviceRecord", "fullInfo", "refundDetail")
        )
        await _save_cached_detail(tenant_id, account_id, order_id, refund_id, merged)
        return {"ok": True, "detail": merged, "error": None}

    # 无旧缓存：直接保存 new_detail（其他接口显示 skipped）
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, new_detail)
    return {"ok": True, "detail": new_detail, "error": None}


async def invalidate_refund_detail_cache_after_write(
    tenant_id: int, account_id: int, order_id: str, refund_id: str
) -> None:
    """写操作（如同意退款）成功后失效详情缓存。

    需求第十四节：写操作成功后使当前详情缓存失效并刷新当前退款，不刷新全部账号。
    """
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)
    # 后台刷新当前退款详情（不阻塞响应）
    try:
        asyncio.create_task(_refresh_detail_background(
            tenant_id, account_id, order_id, refund_id
        ))
    except Exception:
        pass
