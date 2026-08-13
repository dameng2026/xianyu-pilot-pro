"""
鱼小铺卖家数据概览服务（数据罗盘 singleuser.seller.summary）。

仅在账号被判定为鱼小铺账号（XianyuAccount.fish_shop_user=1）时调用：
- 接口：mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary
- 用途：获取卖家维度的成交、曝光、浏览、访问、咨询等汇总指标与趋势

复用项（与 fish_shop_sync.py 保持一致）：
- MTOP 签名（_build_sign）、Token 提取（_get_token_from_cookie）、Token 刷新（_refresh_m_h5_tk）
- 鱼小铺 PC 工作台请求构造（_make_fish_shop_request、_build_fish_shop_headers）
- 业务成功校验（_check_fish_shop_biz_success）
- Cookie 解密（decrypt_cookie_if_needed）
- 风控/Token 异常类型（XianyuRiskControlError 等）

安全约束（与项目既有约定一致）：
- 日志不得输出 Cookie / _m_h5_tk / _m_h5_tk_enc / sign / 完整原始响应
- 不得将 Cookie 返回前端
- 每个账号使用自己的 Cookie，禁止跨账号复用

聚合规则：
- 金额、计数类指标：按账号求和
- 客单价 aov：总成交金额 / 总订单数（不直接平均各账号 aov）
- 比例/百分位指标（ratio / showPvCmpPctl / payOrdCntCmpPctl 等）：不平均，全部账号模式返回 null
- 人数类指标（showUv/ipvUv/vstUv/payByrCnt/chatUv）：求和（注明各账号之和，非跨店去重）
- 趋势：按 ds 聚合，仅保留 realDateRange 范围
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cookie_crypto import decrypt_cookie_if_needed
from ..models.entities import XianyuAccount, XianyuAccountAuth
from .fish_shop_sync import (
    FISH_SHOP_DATACOMPASS_VERSION,
    _build_fish_shop_headers,
    _check_fish_shop_biz_success,
    _make_fish_shop_request,
)
from .xianyu_goods_sync import (
    XianyuAuthExpiredError,
    XianyuProviderRejectedError,
    XianyuRiskControlError,
    _get_token_from_cookie,
    _refresh_m_h5_tk,
)

logger = logging.getLogger(__name__)

# 鱼小铺卖家数据概览接口（PC 工作台数据罗盘 - 单卖家汇总）
FISH_SHOP_SELLER_SUMMARY_API = "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary"
FISH_SHOP_SELLER_SUMMARY_VERSION = "1.0"

# dateType 白名单（按需求固化，禁止自由传值）
ALLOWED_DATE_TYPES = ("recent1d", "recent7d", "recent30d")
DEFAULT_DATE_TYPE = "recent7d"

# 全部账号模式下的并发上限（与 fish_shop_sync.py 的 FISH_SHOP_PAGE_CONCURRENCY 对齐）
SELLER_SUMMARY_CONCURRENCY = 16

# 单账号请求超时（秒）—— 闲鱼 MTOP 平均 2-5s，10s 足够，避免单账号拖垮聚合
SELLER_SUMMARY_TIMEOUT = 10

# 短期内存缓存 TTL（秒）：5 分钟内重复访问直接命中缓存
CACHE_TTL_SECONDS = 300

# 请求去重：相同 (tenant_id, account_id, dateType) 的并发请求复用同一 Future
_inflight_requests: dict[tuple[int, Optional[int], str], asyncio.Future] = {}
# 缓存：(tenant_id, account_id, dateType) -> (timestamp, payload)
_response_cache: dict[tuple[int, Optional[int], str], tuple[float, dict]] = {}

# 可相加指标（金额/计数/人数类），全部账号模式按账号求和
ADDITIVE_METRICS = (
    "payAmt", "fstByrPayAmt", "rptByrPayAmt", "rfdAmt",
    "payOrdCnt", "payByrCnt", "rfdOrdCnt",
    "showPv", "showUv", "ipv", "ipvUv", "vstPv", "vstUv",
    "showItmCnt", "ipvItmCnt", "stItmCnt", "onlCnt",
    "favCnt", "newItmCnt", "chatUv", "cmtItmCnt",
    "rptOrdCnt", "rptByrCnt",
)

# 比例/百分位指标：不可相加、不可平均，全部账号模式返回 null
NON_ADDITIVE_METRICS = (
    "rep3minUvRate", "showPvCmpPctl", "payOrdCntCmpPctl", "uctr", "rpr",
)

# 核心展示指标顺序（用于前端卡片分组，与需求第十五节一致）
CORE_METRIC_KEYS = (
    "payAmt", "payOrdCnt", "payByrCnt", "aov",
    "showPv", "showUv", "ipv", "ipvUv",
    "vstPv", "vstUv", "chatUv", "onlCnt",
)

# 趋势图可选指标（与需求第十七节一致）
TREND_METRIC_KEYS = (
    "payAmt", "payOrdCnt", "showPv", "showUv",
    "ipv", "ipvUv", "vstPv", "vstUv", "chatUv",
)


def _build_seller_summary_data(date_type: str) -> dict:
    """构造 singleuser.seller.summary 接口的 data 字段。

    按需求第八节，固定结构：
      {"dateRange": "", "dateType": "<date_type>", "ms": "", "selectedSellerId": "undefined"}

    注意：
    - dateRange / ms 固定为空字符串
    - selectedSellerId 是字符串 "undefined"，不是 JavaScript 的 undefined
    - 不得在序列化时删除该字段
    - 不得将项目内部账号 ID 或系统用户 ID 写入 selectedSellerId
    """
    return {
        "dateRange": "",
        "dateType": date_type,
        "ms": "",
        "selectedSellerId": "undefined",
    }


def _build_seller_summary_url_params() -> dict:
    """singleuser.seller.summary 接口 PC 工作台特有 URL 查询参数。

    与抓包记录对齐：showErrorToast=false（服务端错误不弹前端 toast）。
    """
    return {
        "showErrorToast": "false",
        "spm_cnt": "a21ybx.datacompass.0.0",
    }


async def _resolve_fish_shop_accounts(
    db: AsyncSession,
    tenant_id: int,
    user_id: Optional[int] = None,
) -> list[dict]:
    """查询当前租户下所有可用的鱼小铺账号。

    仅返回 fish_shop_user=1 且未删除的账号，普通闲鱼账号不进入列表。
    """
    query = select(
        XianyuAccount.id,
        XianyuAccount.nickname,
        XianyuAccount.external_uid,
        XianyuAccount.remark,
    ).where(
        XianyuAccount.tenant_id == tenant_id,
        XianyuAccount.deleted == 0,
        XianyuAccount.fish_shop_user == 1,
    ).order_by(XianyuAccount.created_time.desc())

    if user_id is not None:
        try:
            scoped_user_id = int(user_id)
        except (TypeError, ValueError):
            scoped_user_id = 0
        if scoped_user_id > 0:
            from sqlalchemy import or_
            query = query.where(
                or_(XianyuAccount.user_id == scoped_user_id, XianyuAccount.user_id.is_(None))
            )

    result = await db.execute(query)
    rows = result.all()
    return [
        {
            "id": row[0],
            "nickname": row[1],
            "externalUid": row[2],
            "remark": row[3],
        }
        for row in rows
    ]


async def _resolve_account_cookie_str(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> tuple[Optional[str], Optional[str]]:
    """读取单个鱼小铺账号的明文 Cookie。

    返回 (cookie_str, error_msg)。error_msg 非空时表示账号不可用。
    """
    try:
        result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
        )
        auth = result.scalar_one_or_none()
        if not auth or not auth.encrypted_cookie:
            return None, "账号未登录或 Cookie 已失效，请到「账号管理」扫码登录闲鱼账号"

        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
        token = _get_token_from_cookie(cookie_str)
        if not token:
            # 尝试刷新 _m_h5_tk
            try:
                cookie_str = await asyncio.to_thread(_refresh_m_h5_tk, cookie_str)
                token = _get_token_from_cookie(cookie_str)
            except Exception as e:
                logger.warning("刷新 _m_h5_tk 失败 account_id=%s errorType=%s", account_id, type(e).__name__)
            if not token:
                return None, "Cookie 中缺少 _m_h5_tk，请重新登录闲鱼账号"
        return cookie_str, None
    except Exception as e:
        logger.warning("读取账号 Cookie 失败 account_id=%s errorType=%s", account_id, type(e).__name__)
        return None, "读取账号登录状态失败，请稍后重试"


def _parse_seller_summary_response(response: dict) -> dict:
    """解析 singleuser.seller.summary 响应。

    主要路径：
      data.data.graphBannerBenchData.bannerDataList[]
      data.data.graphBannerBenchData.graphDataList[]
      data.extendInfo.realDateRange

    返回结构化 payload：
      {
        "realDateRange": ["20260720", "20260726"],
        "banners": { "<metricKey>": { name, data, dataFormat, dataStr, lastData, lastDataFormat, lastDataStr, ratio, ratioFormat, decimal, cycle, extendInfo }, ... },
        "graph": [ { "ds": "20260720", "timeCycle": ..., "<metric>": value, ... }, ... ]
      }
    """
    data = response.get("data") or {}
    inner = data.get("data") or {}
    extend_info = data.get("extendInfo") or {}

    real_date_range = extend_info.get("realDateRange") or []
    if not isinstance(real_date_range, list):
        real_date_range = []

    graph_banner = inner.get("graphBannerBenchData") or {}
    if not isinstance(graph_banner, dict):
        graph_banner = {}

    banner_list = graph_banner.get("bannerDataList") or []
    if not isinstance(banner_list, list):
        banner_list = []

    graph_list = graph_banner.get("graphDataList") or []
    if not isinstance(graph_list, list):
        graph_list = []

    banners: dict[str, dict] = {}
    for item in banner_list:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name or not isinstance(name, str):
            continue
        banners[name] = {
            "name": name,
            "cycle": item.get("cycle") or "",
            "data": item.get("data"),
            "dataFormat": item.get("dataFormat") or "",
            "dataStr": item.get("dataStr") or "",
            "lastData": item.get("lastData"),
            "lastDataFormat": item.get("lastDataFormat") or "",
            "lastDataStr": item.get("lastDataStr") or "",
            "ratio": item.get("ratio"),
            "ratioFormat": item.get("ratioFormat") or "",
            "decimal": item.get("decimal"),
            "extendInfo": item.get("extendInfo") or {},
        }

    graph: list[dict] = []
    for item in graph_list:
        if not isinstance(item, dict):
            continue
        ds = item.get("ds")
        if ds is None or ds == "":
            continue
        graph.append(dict(item))

    return {
        "realDateRange": real_date_range,
        "banners": banners,
        "graph": graph,
    }


def _to_number(value: Any) -> Optional[float]:
    """安全转 float，失败返回 None。用于聚合计算。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _aggregate_banners(per_account: list[dict]) -> dict:
    """聚合多账号 banner 数据。

    规则：
    - 金额/计数/人数类（ADDITIVE_METRICS）：当前值与上期值分别求和
    - aov：用总成交金额 / 总订单数 重新计算（不直接平均）
    - 比例/百分位类（NON_ADDITIVE_METRICS）：返回 null
    - ratio：用聚合后的当前值与上期值重新计算（不平均各账号 ratio）
    - 上期为 0 或缺失：避免除零，ratio 返回 null
    """
    if not per_account:
        return {}

    # 收集每个指标的所有账号取值
    metric_current: dict[str, list[float]] = {}
    metric_last: dict[str, list[float]] = {}
    for entry in per_account:
        banners = entry.get("banners") or {}
        for key, item in banners.items():
            cur = _to_number(item.get("data"))
            last = _to_number(item.get("lastData"))
            if cur is not None:
                metric_current.setdefault(key, []).append(cur)
            if last is not None:
                metric_last.setdefault(key, []).append(last)

    aggregated: dict[str, dict] = {}
    all_keys = set(metric_current.keys()) | set(metric_last.keys())
    for key in all_keys:
        cur_sum = sum(metric_current.get(key, [])) if metric_current.get(key) else None
        last_sum = sum(metric_last.get(key, [])) if metric_last.get(key) else None

        if key in NON_ADDITIVE_METRICS:
            # 比例/百分位类：不平均，全部账号模式返回 null
            aggregated[key] = {
                "name": key,
                "data": None,
                "dataFormat": "",
                "dataStr": "",
                "lastData": None,
                "lastDataFormat": "",
                "lastDataStr": "",
                "ratio": None,
                "ratioFormat": "",
                "decimal": None,
                "cycle": "",
                "extendInfo": {},
                "aggregated": True,
            }
            continue

        if key == "aov":
            # 客单价：总成交金额 / 总订单数（不直接平均各账号 aov）
            pay_amt_sum = sum(metric_current.get("payAmt", [])) if metric_current.get("payAmt") else 0.0
            pay_ord_sum = sum(metric_current.get("payOrdCnt", [])) if metric_current.get("payOrdCnt") else 0.0
            last_pay_amt_sum = sum(metric_last.get("payAmt", [])) if metric_last.get("payAmt") else 0.0
            last_pay_ord_sum = sum(metric_last.get("payOrdCnt", [])) if metric_last.get("payOrdCnt") else 0.0
            cur_aov = (pay_amt_sum / pay_ord_sum) if pay_ord_sum > 0 else None
            last_aov = (last_pay_amt_sum / last_pay_ord_sum) if last_pay_ord_sum > 0 else None
            ratio = _compute_ratio(cur_aov, last_aov)
            aggregated[key] = {
                "name": key,
                "data": cur_aov,
                "dataFormat": "",
                "dataStr": "",
                "lastData": last_aov,
                "lastDataFormat": "",
                "lastDataStr": "",
                "ratio": ratio,
                "ratioFormat": "",
                "decimal": None,
                "cycle": "",
                "extendInfo": {},
                "aggregated": True,
            }
            continue

        # 可相加指标：直接求和
        ratio = _compute_ratio(cur_sum, last_sum)
        aggregated[key] = {
            "name": key,
            "data": cur_sum,
            "dataFormat": "",
            "dataStr": "",
            "lastData": last_sum,
            "lastDataFormat": "",
            "lastDataStr": "",
            "ratio": ratio,
            "ratioFormat": "",
            "decimal": None,
            "cycle": "",
            "extendInfo": {},
            "aggregated": True,
        }

    return aggregated


def _compute_ratio(current: Optional[float], last: Optional[float]) -> Optional[float]:
    """计算变化比例。

    - current 或 last 为 None：返回 None（无对比值，不显示虚假百分比）
    - last == 0：避免除零，返回 None
    - last != 0：(current - last) / |last|
    - 注意：返回的是小数（如 0.12 表示 12%），前端格式化时按项目统一百分比格式
    """
    if current is None or last is None:
        return None
    try:
        last_abs = abs(last)
        if last_abs == 0:
            return None
        return (current - last) / last_abs
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _aggregate_graph(per_account: list[dict]) -> list[dict]:
    """聚合多账号趋势数据。

    规则：
    - 仅保留 realDateRange 范围内的数据
    - 按 ds 建立日期映射
    - 可相加指标按日期求和
    - 比例/百分位类指标不平均，置为 None
    - 缺失日期按"该账号当天未返回"处理，不补 0
    - 失败账号不整段补 0
    - 按 ds 升序排序
    """
    if not per_account:
        return []

    # 取所有账号 realDateRange 的交集（按需求：使用 realDateRange 过滤当前周期）
    # 各账号 realDateRange 应该一致（同一 dateType），取第一个非空即可
    real_range: list[str] = []
    for entry in per_account:
        r = entry.get("realDateRange") or []
        if r:
            real_range = r
            break

    real_range_set = set(real_range)

    # 按 ds 聚合
    daily: dict[str, dict[str, float]] = {}
    for entry in per_account:
        graph = entry.get("graph") or []
        for point in graph:
            ds = point.get("ds")
            if not ds or (real_range_set and str(ds) not in real_range_set):
                continue
            bucket = daily.setdefault(str(ds), {})
            for key, value in point.items():
                if key in ("ds", "timeCycle", "slrId"):
                    continue
                if key in NON_ADDITIVE_METRICS:
                    # 比例类不平均，置为 None
                    bucket[key] = None
                    continue
                num = _to_number(value)
                if num is None:
                    continue
                bucket[key] = bucket.get(key, 0.0) + num

    # 按 ds 排序输出
    result: list[dict] = []
    for ds in sorted(daily.keys()):
        bucket = daily[ds]
        point: dict[str, Any] = {"ds": ds}
        for key, value in bucket.items():
            point[key] = value
        result.append(point)
    return result


async def _fetch_single_account_summary(
    cookie_str: str,
    date_type: str,
) -> dict:
    """调用 singleuser.seller.summary 接口获取单账号数据。

    每次调用独立生成 t / sign / data_json，不复用固定签名。
    签名使用的 data 字符串与 POST 提交的 data 字符串完全一致（由 _make_fish_shop_request 内部保证）。
    """
    data = _build_seller_summary_data(date_type)
    extra_params = _build_seller_summary_url_params()
    response = await asyncio.to_thread(
        _make_fish_shop_request,
        cookie_str,
        FISH_SHOP_SELLER_SUMMARY_API,
        data,
        version=FISH_SHOP_SELLER_SUMMARY_VERSION,
        extra_url_params=extra_params,
        timeout=SELLER_SUMMARY_TIMEOUT,
    )
    _check_fish_shop_biz_success(response, FISH_SHOP_SELLER_SUMMARY_API)
    return _parse_seller_summary_response(response)


async def _fetch_account_summary_with_cache(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    date_type: str,
) -> dict:
    """单账号请求 + 缓存 + 请求去重。

    缓存维度：(tenant_id, account_id, dateType)
    去重：相同 key 的并发请求复用同一 Future
    """
    cache_key = (tenant_id, account_id, date_type)

    # 命中未过期缓存
    cached = _response_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        logger.info(
            "fish_shop_datacompass cache_hit tenant_id=%s account_id=%s dateType=%s",
            tenant_id, account_id, date_type,
        )
        return cached[1]

    # 请求去重：相同 key 的并发请求复用 Future
    inflight = _inflight_requests.get(cache_key)
    if inflight is not None:
        logger.info(
            "fish_shop_datacompass dedup_hit tenant_id=%s account_id=%s dateType=%s",
            tenant_id, account_id, date_type,
        )
        return await inflight

    future: asyncio.Future = asyncio.get_event_loop().create_future()
    _inflight_requests[cache_key] = future

    started = time.time()
    try:
        cookie_str, err = await _resolve_account_cookie_str(db, tenant_id, account_id)
        if err:
            raise XianyuAuthExpiredError(err)

        payload = await _fetch_single_account_summary(cookie_str, date_type)
        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            "fish_shop_datacompass single_ok tenant_id=%s account_id=%s dateType=%s elapsed_ms=%s",
            tenant_id, account_id, date_type, elapsed_ms,
        )
        _response_cache[cache_key] = (time.time(), payload)
        future.set_result(payload)
        return payload
    except Exception as e:
        # 不缓存失败结果
        err_type = type(e).__name__
        # 标记为已知业务异常类型时使用更清晰的日志
        if isinstance(e, (XianyuAuthExpiredError, XianyuRiskControlError, XianyuProviderRejectedError)):
            logger.warning(
                "fish_shop_datacompass single_biz_fail tenant_id=%s account_id=%s dateType=%s errorType=%s",
                tenant_id, account_id, date_type, err_type,
            )
        else:
            logger.warning(
                "fish_shop_datacompass single_fail tenant_id=%s account_id=%s dateType=%s errorType=%s",
                tenant_id, account_id, date_type, err_type,
            )
        if not future.done():
            future.set_exception(e)
        raise
    finally:
        _inflight_requests.pop(cache_key, None)


async def fetch_seller_summary(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int],
    date_type: str,
    user_id: Optional[int] = None,
) -> dict:
    """卖家数据概览主入口。

    - account_id=None：全部鱼小铺账号模式，逐账号请求并聚合
    - account_id=<id>：单账号模式，仅请求该账号

    返回结构：
      {
        "mode": "single" | "all",
        "dateType": "recent7d",
        "realDateRange": ["20260720", "20260726"],
        "banners": { "<metricKey>": {...}, ... },
        "graph": [ { "ds": "20260720", ... }, ... ],
        "accounts": {
          "total": <int>,           # 鱼小铺账号总数
          "success": <int>,         # 成功账号数
          "failed": <int>,          # 失败账号数
          "failedAccountIds": [...],# 失败账号 ID（非敏感）
          "isPartial": <bool>,      # 是否部分成功
          "allFailed": <bool>       # 是否全部失败
        },
        "aovNote": "..."            # 全部账号模式下的客单价/人数说明（可选）
      }
    """
    safe_date_type = date_type if date_type in ALLOWED_DATE_TYPES else DEFAULT_DATE_TYPE

    # 查询当前租户可用的鱼小铺账号
    fish_shop_accounts = await _resolve_fish_shop_accounts(db, tenant_id, user_id)

    if not fish_shop_accounts:
        # 没有鱼小铺账号：不调用接口，返回空状态
        return {
            "mode": "all",
            "dateType": safe_date_type,
            "realDateRange": [],
            "banners": {},
            "graph": [],
            "accounts": {
                "total": 0,
                "success": 0,
                "failed": 0,
                "failedAccountIds": [],
                "isPartial": False,
                "allFailed": False,
            },
            "noFishShopAccount": True,
        }

    if account_id is not None:
        # 单账号模式：校验该账号是否属于鱼小铺账号
        target = next((a for a in fish_shop_accounts if a["id"] == account_id), None)
        if target is None:
            # 选中的账号不是鱼小铺账号或不存在：不调用接口
            return {
                "mode": "single",
                "dateType": safe_date_type,
                "realDateRange": [],
                "banners": {},
                "graph": [],
                "accounts": {
                    "total": len(fish_shop_accounts),
                    "success": 0,
                    "failed": 0,
                    "failedAccountIds": [],
                    "isPartial": False,
                    "allFailed": False,
                },
                "invalidAccount": True,
            }

        try:
            payload = await _fetch_account_summary_with_cache(db, tenant_id, account_id, safe_date_type)
            return {
                "mode": "single",
                "dateType": safe_date_type,
                "realDateRange": payload.get("realDateRange") or [],
                "banners": payload.get("banners") or {},
                "graph": payload.get("graph") or [],
                "accounts": {
                    "total": 1,
                    "success": 1,
                    "failed": 0,
                    "failedAccountIds": [],
                    "isPartial": False,
                    "allFailed": False,
                },
            }
        except Exception:
            # 单账号失败：返回整体失败状态
            return {
                "mode": "single",
                "dateType": safe_date_type,
                "realDateRange": [],
                "banners": {},
                "graph": [],
                "accounts": {
                    "total": 1,
                    "success": 0,
                    "failed": 1,
                    "failedAccountIds": [account_id],
                    "isPartial": False,
                    "allFailed": True,
                },
                "loadFailed": True,
            }

    # 全部账号模式
    # 只有一个鱼小铺账号：等价于单账号请求（不重复请求两次）
    if len(fish_shop_accounts) == 1:
        only_id = fish_shop_accounts[0]["id"]
        try:
            payload = await _fetch_account_summary_with_cache(db, tenant_id, only_id, safe_date_type)
            return {
                "mode": "all",
                "dateType": safe_date_type,
                "realDateRange": payload.get("realDateRange") or [],
                "banners": payload.get("banners") or {},
                "graph": payload.get("graph") or [],
                "accounts": {
                    "total": 1,
                    "success": 1,
                    "failed": 0,
                    "failedAccountIds": [],
                    "isPartial": False,
                    "allFailed": False,
                },
                "aovNote": "全部账号仅 1 个鱼小铺账号，数据即该账号数据。",
            }
        except Exception:
            return {
                "mode": "all",
                "dateType": safe_date_type,
                "realDateRange": [],
                "banners": {},
                "graph": [],
                "accounts": {
                    "total": 1,
                    "success": 0,
                    "failed": 1,
                    "failedAccountIds": [only_id],
                    "isPartial": False,
                    "allFailed": True,
                },
                "loadFailed": True,
            }

    # 多账号：受控并发请求
    sem = asyncio.Semaphore(SELLER_SUMMARY_CONCURRENCY)

    async def _fetch_one(account: dict) -> tuple[int, Optional[dict], Optional[Exception]]:
        async with sem:
            try:
                payload = await _fetch_account_summary_with_cache(db, tenant_id, account["id"], safe_date_type)
                return account["id"], payload, None
            except Exception as e:
                return account["id"], None, e

    tasks = [_fetch_one(a) for a in fish_shop_accounts]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    success_payloads: list[dict] = []
    failed_ids: list[int] = []
    for account_id_, payload, err in results:
        if payload is not None and err is None:
            success_payloads.append(payload)
        else:
            failed_ids.append(account_id_)

    total = len(fish_shop_accounts)
    success_count = len(success_payloads)
    failed_count = len(failed_ids)

    if success_count == 0:
        # 全部失败
        return {
            "mode": "all",
            "dateType": safe_date_type,
            "realDateRange": [],
            "banners": {},
            "graph": [],
            "accounts": {
                "total": total,
                "success": success_count,
                "failed": failed_count,
                "failedAccountIds": failed_ids,
                "isPartial": False,
                "allFailed": True,
            },
            "loadFailed": True,
        }

    # 聚合成功账号
    aggregated_banners = _aggregate_banners(success_payloads)
    aggregated_graph = _aggregate_graph(success_payloads)

    # realDateRange 取第一个成功账号的
    real_date_range: list[str] = []
    for entry in success_payloads:
        r = entry.get("realDateRange") or []
        if r:
            real_date_range = r
            break

    is_partial = failed_count > 0

    return {
        "mode": "all",
        "dateType": safe_date_type,
        "realDateRange": real_date_range,
        "banners": aggregated_banners,
        "graph": aggregated_graph,
        "accounts": {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "failedAccountIds": failed_ids,
            "isPartial": is_partial,
            "allFailed": False,
        },
        "aovNote": (
            "全部账号数据为各鱼小铺账号之和：客单价 = 总成交金额 / 总订单数；"
            "人数类指标（曝光人数、浏览人数、访客人数、支付买家数、咨询人数）"
            "为各账号去重人数之和，非跨店铺全局唯一去重。"
        ),
    }


def invalidate_cache(tenant_id: Optional[int] = None, account_id: Optional[int] = None) -> None:
    """清除缓存。

    账号删除、Cookie 更新、权限变化时调用，避免返回错误的旧聚合结果。
    - tenant_id=None：清空所有缓存
    - 仅 tenant_id：清空该租户所有缓存
    - tenant_id + account_id：清空该账号所有 dateType 缓存
    """
    if tenant_id is None:
        _response_cache.clear()
        return

    keys_to_remove = []
    for key in _response_cache.keys():
        t_id, a_id, _ = key
        if t_id != tenant_id:
            continue
        if account_id is not None and a_id != account_id:
            continue
        keys_to_remove.append(key)
    for key in keys_to_remove:
        _response_cache.pop(key, None)


# ==================== 流量分布（浏览分布）====================
FISH_SHOP_BROWSE_SUMMARY_API = "mtop.alibaba.idle.seller.pc.datacompass.singleuser.browse.summary"
FISH_SHOP_BROWSE_SUMMARY_VERSION = "1.0"
BROWSE_ALLOWED_DATE_TYPES = (*ALLOWED_DATE_TYPES, "customDate")
BROWSE_TIMEOUT = 10
BROWSE_CACHE_TTL_SECONDS = 60

# 缓存：(tenant_id, account_id, dateType, dateRange) -> (timestamp, payload)
_browse_cache: dict[tuple, tuple[float, dict]] = {}
_browse_inflight: dict[tuple, asyncio.Future] = {}


def _build_browse_summary_data(date_type: str, date_range: str = "") -> dict:
    """构建流量分布接口请求体。"""
    data: dict[str, str] = {"dateType": date_type}
    if date_type == "customDate" and date_range:
        data["dateRange"] = date_range
    return data


def _parse_browse_summary_response(response: dict) -> dict:
    """流量分布接口直接返回 data 原始结构（sceneSourceList/itemCateList/...）。"""
    data = response.get("data") or {}
    return data if isinstance(data, dict) else {}


async def _fetch_single_account_browse(
    cookie_str: str,
    date_type: str,
    date_range: str = "",
) -> dict:
    """调用 singleuser.browse.summary 接口获取单个账号流量分布。"""
    data = _build_browse_summary_data(date_type, date_range)
    response = await asyncio.to_thread(
        _make_fish_shop_request,
        cookie_str,
        FISH_SHOP_BROWSE_SUMMARY_API,
        data,
        version=FISH_SHOP_BROWSE_SUMMARY_VERSION,
        extra_url_params=_build_seller_summary_url_params(),
        timeout=BROWSE_TIMEOUT,
    )
    _check_fish_shop_biz_success(response, FISH_SHOP_BROWSE_SUMMARY_API)
    return _parse_browse_summary_response(response)


async def _fetch_account_browse_with_cache(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    date_type: str,
    date_range: str = "",
) -> dict:
    """单账号流量分布请求 + 短缓存 + 请求去重。"""
    cache_key = (tenant_id, account_id, date_type, date_range)
    cached = _browse_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < BROWSE_CACHE_TTL_SECONDS:
        return cached[1]

    inflight = _browse_inflight.get(cache_key)
    if inflight is not None:
        return await inflight

    future: asyncio.Future = asyncio.get_event_loop().create_future()
    _browse_inflight[cache_key] = future
    try:
        cookie_str, err = await _resolve_account_cookie_str(db, tenant_id, account_id)
        if err:
            raise XianyuAuthExpiredError(err)
        payload = await _fetch_single_account_browse(cookie_str, date_type, date_range)
        _browse_cache[cache_key] = (time.time(), payload)
        future.set_result(payload)
        return payload
    except Exception as e:
        if not future.done():
            future.set_exception(e)
        raise
    finally:
        _browse_inflight.pop(cache_key, None)


async def fetch_browse_summary(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int] = None,
    date_type: str = DEFAULT_DATE_TYPE,
    user_id: Optional[int] = None,
    date_range: str = "",
) -> dict:
    """流量分布主入口。

    - account_id=None：全部鱼小铺账号模式，逐账号请求并返回列表
    - account_id=<id>：单账号模式
    """
    safe_date_type = date_type if date_type in BROWSE_ALLOWED_DATE_TYPES else DEFAULT_DATE_TYPE
    fish_shop_accounts = await _resolve_fish_shop_accounts(db, tenant_id, user_id)

    if not fish_shop_accounts:
        return {
            "mode": "all",
            "dateType": safe_date_type,
            "noFishShopAccount": True,
            "accounts": [],
        }

    if account_id is not None:
        target = next((a for a in fish_shop_accounts if a["id"] == account_id), None)
        if target is None:
            return {
                "mode": "single",
                "dateType": safe_date_type,
                "invalidAccount": True,
                "data": {},
            }
        payload = await _fetch_account_browse_with_cache(
            db, tenant_id, account_id, safe_date_type, date_range,
        )
        return {
            "mode": "single",
            "dateType": safe_date_type,
            "accountId": account_id,
            "accountName": target.get("nickname") or "",
            "data": payload,
        }

    results: list[dict] = []
    for acc in fish_shop_accounts:
        try:
            payload = await _fetch_account_browse_with_cache(
                db, tenant_id, acc["id"], safe_date_type, date_range,
            )
            results.append({
                "accountId": acc["id"],
                "accountName": acc.get("nickname") or "",
                "data": payload,
                "success": True,
            })
        except Exception as exc:
            results.append({
                "accountId": acc["id"],
                "accountName": acc.get("nickname") or "",
                "data": {},
                "success": False,
                "error": type(exc).__name__,
            })
    return {"mode": "all", "dateType": safe_date_type, "accounts": results}
