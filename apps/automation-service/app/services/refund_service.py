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
# 允许执行的 MTOP 操作 API 白名单（防止 rightVO 返回任意 API 被执行）
ALLOWED_MTOP_ACTION_APIS = frozenset({REFUND_AGREE_API})

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
