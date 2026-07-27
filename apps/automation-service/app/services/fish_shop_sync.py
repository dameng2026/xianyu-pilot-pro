"""
鱼小铺账号商品同步服务。

仅在账号被判定为鱼小铺账号（XianyuAccount.fish_shop_user=1）时调用：
1. 调用鱼小铺商品管理接口（mtop.alibaba.idle.seller.pc.common.item.search）获取商品基础信息；
2. 调用鱼小铺数据罗盘接口（mtop.alibaba.idle.seller.pc.datacompass.item.list）获取最近30天曝光/浏览；
3. 两个接口并行执行，按商品ID（itemId / itmId）合并数据；
4. 复用 xianyu_goods_sync 的入库逻辑批量写入。

普通闲鱼账号不走本模块，仍由 xianyu_goods_sync.sync_goods_for_account 处理。

复用项：
- MTOP 签名（_build_sign）、Cookie 解析（_parse_cookie）、Token 提取（_get_token_from_cookie）；
- Token 刷新（_refresh_m_h5_tk）、风控异常类型（XianyuRiskControlError 等）；
- 入库工具（_build_goods_insert_values / _build_goods_update_values / upsert_goods_record）；
- 同步任务状态（_sync_tasks / _sync_lock / _persist_sync_task）；
- 详情同步后台任务（_async_fetch_details）。
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import random
import time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from .xianyu_goods_sync import (
    APP_KEY,
    H5_API_BASE,
    HEADERS,
    GOODS_SYNC_FAILURE_MESSAGE,
    XianyuRiskControlError,
    XianyuAuthExpiredError,
    XianyuProviderRejectedError,
    _build_sign,
    _parse_cookie,
    _get_token_from_cookie,
    _refresh_m_h5_tk,
    _build_goods_insert_values,
    _build_goods_update_values,
)

logger = logging.getLogger(__name__)

# 鱼小铺 PC 工作台接口（与普通 mtop.idle.idleitem.* 不同）
FISH_SHOP_ITEM_SEARCH_API = "mtop.alibaba.idle.seller.pc.common.item.search"
FISH_SHOP_ITEM_SEARCH_VERSION = "1.0"
FISH_SHOP_DATACOMPASS_API = "mtop.alibaba.idle.seller.pc.datacompass.item.list"
FISH_SHOP_DATACOMPASS_VERSION = "1.0"

# 已确认的请求 pageSize
FISH_SHOP_ITEM_SEARCH_PAGE_SIZE = 20
FISH_SHOP_DATACOMPASS_PAGE_SIZE = 10

# 单账号分页并发上限
# - 提高到 8：73 件商品 + pageSize=10 → 8 页数据罗盘可一次性并发完成
# - 闲鱼对单账号同一接口的并发容忍度足够（PC 工作台正常使用时也会并发请求）
FISH_SHOP_PAGE_CONCURRENCY = 8

# 风控/Token 过期关键字
RGV587 = "RGV587"
TOKEN_EXPIRED = "FAIL_SYS_TOKEN_EXOIRED"
TOKEN_EXPIRED_ALIAS = "FAIL_SYS_TOKEN_EXPIRED"

# 业务成功标志
BIZ_SUCCESS = "SUCCESS"


def _build_fish_shop_headers(cookie_str: str) -> dict:
    """构建鱼小铺 PC 工作台请求头。

    与 XianyuItemOperator._get_headers(is_seller=True) 对齐：
    - Origin/Referer 指向 seller.goofish.com
    - 携带 idle_site_biz_code: COMMONPRO（鱼小铺业务码）
    """
    return {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://seller.goofish.com",
        "Referer": "https://seller.goofish.com/",
        "idle_site_biz_code": "COMMONPRO",
        "idle_user_group_member_id": "",
    }


def _make_fish_shop_request(
    cookie_str: str,
    api_name: str,
    data: dict,
    *,
    version: str = FISH_SHOP_ITEM_SEARCH_VERSION,
    session: Optional[requests.Session] = None,
    extra_url_params: Optional[dict] = None,
    timeout: int = 30,
) -> dict:
    """
    调用鱼小铺 mtop API（PC 工作台专用）。

    与 XianyuItemOperator._call_api 一致的请求结构：
    - URL 查询参数包含 jsv/appKey/t/sign/v/type/dataType/accountSite/timeout/api/sessionOption/spm_cnt
    - 表单 body 仅包含 data 字段
    - 请求头携带 seller.goofish.com 来源与 idle_site_biz_code

    每次调用独立生成 t / sign / data_json，不复用固定签名。
    session 由调用方传入以便复用 TCP/TLS 连接；不传则新建。
    """
    token = _get_token_from_cookie(cookie_str)
    if not token:
        raise XianyuAuthExpiredError("Cookie 中缺少 _m_h5_tk，无法签名")

    t_ms = str(int(time.time() * 1000))
    data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    sign = _build_sign(token, t_ms, data_json)

    # URL 查询参数（与 XianyuItemOperator._build_url 对齐）
    url_params = {
        "jsv": "2.7.2",
        "appKey": APP_KEY,
        "t": t_ms,
        "sign": sign,
        "v": version,
        "type": "json",
        "dataType": "json",
        "accountSite": "xianyu",
        "timeout": str(timeout * 1000),
        "api": api_name,
        "sessionOption": "AutoLoginOnly",
        "spm_cnt": "a21ybx.item.0.0",
        "spm_pre": "",
    }
    if extra_url_params:
        url_params.update(extra_url_params)

    url = f"{H5_API_BASE}/{api_name}/{version}/?{urlencode(url_params)}"

    own_session = session or requests.Session()
    if session is None:
        for part in cookie_str.split(";"):
            if "=" not in part:
                continue
            key, _, value = part.partition("=")
            key = key.strip()
            value = value.strip()
            if key and value:
                own_session.cookies.set(key, value, domain=".goofish.com")

    headers = _build_fish_shop_headers(cookie_str)
    # 表单 body 仅包含 data 字段
    form_data = {"data": data_json}

    try:
        resp = own_session.post(url, headers=headers, data=form_data, timeout=timeout + 10)
        resp.raise_for_status()
        return resp.json()
    except ValueError:
        raise XianyuProviderRejectedError(f"鱼小铺接口 {api_name} 返回非 JSON 响应")
    except requests.RequestException as e:
        raise XianyuProviderRejectedError(f"鱼小铺接口 {api_name} 网络异常: {type(e).__name__}")


def _build_item_search_url_params() -> dict:
    """鱼小铺商品管理接口 PC 工作台特有 URL 查询参数。

    与抓包记录对齐：
    - needLoginPC=true：PC 工作台登录态校验
    - showErrorToast=false：服务端错误不弹前端 toast
    - spm_cnt=a21yho.home.item.search：商品管理页面埋点
    """
    return {
        "needLoginPC": "true",
        "showErrorToast": "false",
        "spm_cnt": "a21yho.home.item.search",
    }


def _build_item_search_data(page_no: int, page_size: int) -> dict:
    """
    构造商品管理接口 data 字段。

    注意：searchRequest 当前确认值是字符串 "{}"，不是 JSON 对象。
    bizType 必须保持字符串 "commonPro"。itemStatus 当前确认值是字符串 "0,-9"。
    """
    return {
        "bizType": "commonPro",
        "searchRequest": "{}",
        "itemStatus": "0,-9",
        "pageNo": page_no,
        "pageSize": page_size,
    }


def _check_fish_shop_biz_success(response: dict, api_name: str) -> None:
    """
    业务成功校验：不能只看 HTTP 200。
    至少检查：外层 ret、data.code、data.data.success。

    实测响应结构：
    - ret: ["SUCCESS::调用成功"]
    - data.code: "success"（小写字符串，与 ret 中的 "SUCCESS" 大小写不同）
    - data.msg: "成功"
    - data.data.success: "true"（字符串）或不存在
    """
    ret = response.get("ret") or []
    if isinstance(ret, str):
        ret = [ret]
    ret_msg = " ".join(str(r) for r in ret)

    if RGV587 in ret_msg:
        raise XianyuRiskControlError("鱼小铺接口触发平台风控验证")
    if TOKEN_EXPIRED in ret_msg or TOKEN_EXPIRED_ALIAS in ret_msg:
        raise XianyuAuthExpiredError("账号 Token 已过期")

    # ret 中包含 SUCCESS（大小写敏感）即认为外层调用成功
    if ret and not any(BIZ_SUCCESS in str(r) for r in ret):
        raise XianyuProviderRejectedError(f"鱼小铺接口 {api_name} 返回错误：" + ret_msg)

    data = response.get("data")
    if not isinstance(data, dict):
        raise XianyuProviderRejectedError(f"鱼小铺接口 {api_name} data 字段非对象")

    # code 实测为小写 "success"；兼容大小写与数字形式
    code = data.get("code")
    if code is not None:
        code_lower = str(code).strip().lower()
        if code_lower not in ("0", "200", "success"):
            msg = data.get("message") or data.get("msg") or f" data.code={code}"
            raise XianyuProviderRejectedError(f"鱼小铺接口 {api_name} 返回错误： message={msg}")

    inner = data.get("data")
    if isinstance(inner, dict):
        # success 实测为字符串 "true"/"false"；兼容布尔与字符串
        success = inner.get("success")
        if success is not None:
            success_str = str(success).strip().lower()
            if success_str in ("false", "0"):
                msg = inner.get("errorMsg") or inner.get("message") or inner.get("msg") or ""
                raise XianyuProviderRejectedError(
                    f"鱼小铺接口 {api_name} data.data.success=false message={msg}"
                )


def _str_to_bool(value: Any) -> bool:
    """将字符串/任意类型安全转为布尔值。

    实测响应中 hasNextPage/success 字段为字符串 "true"/"false"，
    直接 bool("false") 会错误返回 True，必须按字符串内容判断。
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes")


def _parse_item_search_response(response: dict) -> dict:
    """
    解析商品管理接口响应，返回：
    {
      "items": [...],         # 商品列表
      "currentPage": int,
      "hasNextPage": bool,
      "pageSize": int,        # 服务端实际 pageSize
      "total": int,
      "totalPage": int,
    }

    兼容两种响应结构：
    1. 包装形式（PC 工作台）：itemSearchResponseList 是对象，内含 list 与分页元数据
       {
         "data": {
           "data": {
             "itemSearchResponseList": {
               "itemSearchResponseList": [...],  # 实际商品列表
               "currentPage": "1", "hasNextPage": "true",
               "pageSize": "20", "total": "X", "totalPage": "Y"
             }
           }
         }
       }
    2. 扁平形式（兜底）：itemSearchResponseList 直接是商品列表，分页字段在外层
    """
    _check_fish_shop_biz_success(response, FISH_SHOP_ITEM_SEARCH_API)
    data = response.get("data") or {}
    inner = data.get("data") or {}
    # 兼容两种结构：包装形式（dict）或扁平形式（list）
    raw_wrapper = inner.get("itemSearchResponseList")
    if isinstance(raw_wrapper, dict):
        # 包装形式：分页字段在 wrapper 内
        page_holder = raw_wrapper
        raw_items = raw_wrapper.get("itemSearchResponseList") or []
    else:
        # 扁平形式：分页字段在 inner 内
        page_holder = inner
        raw_items = raw_wrapper or []
    if not isinstance(raw_items, list):
        raw_items = []
    items = [_parse_fish_shop_goods_item(it) for it in raw_items if isinstance(it, dict)]
    return {
        "items": items,
        "currentPage": int(page_holder.get("currentPage") or 1),
        "hasNextPage": _str_to_bool(page_holder.get("hasNextPage")),
        "pageSize": int(page_holder.get("pageSize") or FISH_SHOP_ITEM_SEARCH_PAGE_SIZE),
        "total": int(page_holder.get("total") or len(items)),
        "totalPage": int(page_holder.get("totalPage") or 1),
    }


def _parse_fish_shop_goods_item(item: dict) -> dict:
    """
    将商品管理接口返回的单个商品对象解析为统一字典。

    字段映射（来自需求第五、六节）：
    - title           → 商品标题
    - itemImageUrl    → 商品封面图
    - itemId          → 闲鱼商品ID（字符串，避免整数精度损失）
    - reservePrice    → 商品价格（字符串，保留精度）
    - quantity        → 商品库存
    - gmtCreate       → 商品创建时间（毫秒时间戳）
    - gmtShelf        → 上架时间（不作创建时间）
    - itemStatus      → 商品状态（用于映射 ORM status 字段：0=在售→1，其他→下架）
    - itemStatusDesc  → 状态描述（仅存 raw_payload，不入库单独字段）

    返回字典只包含 XianyuGoods ORM 模型的合法字段，避免 TypeError。
    原始完整数据存入 raw_payload，便于后续诊断与详情同步。
    """
    item_id = item.get("itemId")
    if item_id is None:
        return {}
    item_id = str(item_id)

    title = item.get("title") or ""
    cover_pic = item.get("itemImageUrl") or ""
    price = item.get("reservePrice")
    if price is None:
        price = ""
    price = str(price)

    quantity_raw = item.get("quantity")
    try:
        quantity = int(quantity_raw)
    except (ValueError, TypeError):
        quantity = 0

    gmt_create = _parse_fish_shop_timestamp(item.get("gmtCreate"))

    # itemStatus 映射到 ORM status 字段：
    # 鱼小铺 "0" 表示"在卖"→ ORM 1；"-9" 表示已下架 → ORM 0；其他 → ORM 2（已售）
    # 注意：不直接设置 "status" 字段，因为 _build_goods_insert_values / _build_goods_update_values
    #       会翻转 status 值（0→1, 1→0），导致语义错乱。
    #       改为设置 "_fish_shop_status" 中间字段，由 _do_sync 在构建完 insert/update values 后
    #       直接覆盖 ORM status 字段。
    # 注意：itemStatus 可能是整数 0（falsy）或字符串 "0"/"-9"，必须用 is None 检查
    item_status_value = item.get("itemStatus")
    item_status_raw = str(item_status_value).strip() if item_status_value is not None else ""
    if item_status_raw == "0":
        fish_shop_status = 1  # 在售
    elif item_status_raw == "-9":
        fish_shop_status = 0  # 下架
    else:
        fish_shop_status = 2  # 其他状态归为已售/异常

    # 解析商品编辑能力（itemExtendList / itemOperationInfo）
    # 用于前端编辑按钮显示与后端权限校验
    edit_capability = _parse_item_edit_capability(item)

    # 只返回 XianyuGoods ORM 模型的合法字段 + _fish_shop_status 中间字段
    # _fish_shop_status 会在 _do_sync 中被读取并删除，不会传给 ORM
    return {
        "external_goods_id": item_id,
        "title": title,
        "cover_pic": cover_pic,
        "image_url": cover_pic,
        "price": price,
        "sold_price": price,
        "quantity": quantity,
        "stock": str(quantity),
        "gmt_create": gmt_create,
        "_fish_shop_status": fish_shop_status,
        # 编辑能力信息持久化到 ORM 字段（V1.21），供前端列表"编辑"按钮直接判断
        "can_edit": 1 if edit_capability["can_edit"] else 0,
        "edit_note": edit_capability["note"],
        # 原始完整数据存入 raw_payload，便于后续诊断与详情同步
        # 包含 itemExtendList / itemOperationInfo 原始结构，供后端二次校验使用
        "raw_payload": {
            "itemId": item_id,
            "title": title,
            "itemImageUrl": cover_pic,
            "reservePrice": price,
            "quantity": quantity_raw,
            "gmtCreate": item.get("gmtCreate"),
            "gmtShelf": item.get("gmtShelf"),
            "itemStatus": item.get("itemStatus"),
            "itemStatusDesc": item.get("itemStatusDesc"),
            "itemType": item.get("itemType"),
            "itemExtendList": item.get("itemExtendList"),
            "itemOperationInfo": item.get("itemOperationInfo"),
        },
    }


def _parse_item_edit_capability(item: dict) -> dict:
    """
    解析商品编辑能力。

    闲鱼商品管理列表响应中可能包含以下编辑能力信息：
    1. itemExtendList: [{key: "itemEdit", value: "true"/"false", note: "..."}]
    2. itemOperationInfo.operateItemList: [{operateType: "itemEdit", note: "..."}]

    返回:
        {"can_edit": bool, "note": str}
        - can_edit: 是否支持编辑（默认 True，仅明确为 false 时才为 False）
        - note: 不支持编辑时的提示文案
    """
    can_edit = True
    note = ""

    # 方式1: itemExtendList 中 key=itemEdit
    extend_list = item.get("itemExtendList")
    if isinstance(extend_list, list):
        for ext in extend_list:
            if not isinstance(ext, dict):
                continue
            if str(ext.get("key", "")).strip() == "itemEdit":
                value = ext.get("value")
                # value 可能是 "true"/"false" 字符串或布尔值
                if value is not None:
                    can_edit = _str_to_bool(value)
                note = str(ext.get("note", "") or "").strip()
                break

    # 方式2: itemOperationInfo.operateItemList 中 operateType=itemEdit
    # 如果方式1未找到，尝试方式2
    if can_edit and not note:
        op_info = item.get("itemOperationInfo")
        if isinstance(op_info, dict):
            op_list = op_info.get("operateItemList")
            if isinstance(op_list, list):
                for op in op_list:
                    if not isinstance(op, dict):
                        continue
                    if str(op.get("operateType", "")).strip() == "itemEdit":
                        # 存在 itemEdit 操作项表示可编辑
                        can_edit = True
                        note = str(op.get("note", "") or "").strip()
                        break
                else:
                    # operateItemList 存在但不包含 itemEdit，表示不支持编辑
                    if op_list:
                        can_edit = False

    return {"can_edit": can_edit, "note": note}


def _parse_fish_shop_timestamp(value: Any) -> Optional[datetime]:
    """
    解析鱼小铺接口的时间戳字段。
    兼容毫秒时间戳（数字或字符串）与已格式化的日期字符串。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # 毫秒时间戳
        try:
            return datetime.fromtimestamp(value / 1000.0)
        except (OSError, ValueError, OverflowError):
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # 尝试作为数字解析（毫秒时间戳字符串）
        try:
            return datetime.fromtimestamp(float(s) / 1000.0)
        except (ValueError, OSError, OverflowError):
            pass
        # 尝试常见格式
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


def _build_datacompass_data(page_no: int, page_size: int) -> dict:
    """构造数据罗盘最近30天请求 data 字段。"""
    return {
        "tabType": "all",
        "dateType": "recent30d",
        "itmId": "",
        "page": page_no,
        "pageSize": page_size,
    }


def _parse_datacompass_response(response: dict) -> dict:
    """
    解析数据罗盘响应，返回：
    {
      "items": [{"itmId": str, "showPv": int, "ipv": int}, ...],
      "total": int,
      "pageNo": int,
      "pageSize": int,         # 服务端实际 pageSize
      "totalPage": int,        # 由 total/pageSize 计算
    }

    注意：只提取 showPv（曝光次数）和 ipv（浏览次数），
    showUv（曝光人数）/ ipvUv（浏览人数）不保存。
    """
    _check_fish_shop_biz_success(response, FISH_SHOP_DATACOMPASS_API)
    data = response.get("data") or {}
    inner = data.get("data") or {}
    raw_items = inner.get("list") or inner.get("itemList") or []

    items: list[dict] = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        itm_id = it.get("itmId")
        if itm_id is None:
            continue
        itm_id = str(itm_id)
        try:
            show_pv = int(it.get("showPv") or 0)
        except (ValueError, TypeError):
            show_pv = 0
        try:
            ipv = int(it.get("ipv") or 0)
        except (ValueError, TypeError):
            ipv = 0
        items.append({"itmId": itm_id, "showPv": show_pv, "ipv": ipv})

    total = int(inner.get("total") or len(items))
    page_no = int(inner.get("pageNo") or inner.get("page") or 1)
    page_size = int(inner.get("pageSize") or FISH_SHOP_DATACOMPASS_PAGE_SIZE)
    total_page = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "pageNo": page_no,
        "pageSize": page_size,
        "totalPage": total_page,
    }


def _is_retryable_error(exc: Exception) -> bool:
    """判断是否为可重试的临时错误（网络/限流/可恢复 token 过期）。"""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, XianyuRiskControlError):
        return False
    if isinstance(exc, XianyuAuthExpiredError):
        return True
    if isinstance(exc, XianyuProviderRejectedError):
        return False
    if isinstance(exc, requests.HTTPError):
        resp = getattr(exc, "response", None)
        code = getattr(resp, "status_code", None)
        if code is None:
            return False
        return 500 <= int(code) < 600
    return False


async def _fetch_page_with_retry(
    cookie_str: str,
    api_name: str,
    data_builder,
    parser,
    page_no: int,
    page_size: int,
    *,
    version: str = FISH_SHOP_ITEM_SEARCH_VERSION,
    session: Optional[requests.Session] = None,
    extra_url_params: Optional[dict] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
    label: str = "",
) -> dict:
    """
    受信号量约束的单页请求 + 有限重试。
    重试仅针对失败页，不影响已成功页面。
    """
    last_exc: Exception | None = None
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        if semaphore is not None:
            await semaphore.acquire()
        try:
            data = data_builder(page_no, page_size)
            # 关键：用 asyncio.to_thread 包装同步 HTTP 请求，让事件循环可以真正并发执行多个分页
            # 每次调用创建独立 session（session=None），避免多线程共享 requests.Session 引发竞态
            # 使用 functools.partial 正确传递关键字参数（_make_fish_shop_request 的 version/session/extra_url_params 是 kw-only）
            request_fn = functools.partial(
                _make_fish_shop_request,
                cookie_str, api_name, data,
                version=version, session=None, extra_url_params=extra_url_params,
            )
            response = await asyncio.to_thread(request_fn)
            return parser(response)
        except Exception as e:
            last_exc = e
            if not _is_retryable_error(e) or attempt >= max_attempts:
                logger.warning(
                    "鱼小铺接口 %s page=%d 重试耗尽 label=%s err=%s",
                    api_name, page_no, label, str(e)[:200],
                )
                raise
            backoff = 0.3 * attempt + random.uniform(0, 0.3)
            logger.warning(
                "鱼小铺接口 %s page=%d 第 %d 次重试，%.2fs 后重试，原因=%s",
                api_name, page_no, attempt, backoff, type(e).__name__,
            )
            await asyncio.sleep(backoff)
        finally:
            if semaphore is not None:
                semaphore.release()

    if last_exc is not None:
        raise last_exc
    raise XianyuProviderRejectedError(f"鱼小铺接口 {api_name} page={page_no} 重试耗尽")


async def fetch_fish_shop_goods_all(
    cookie_str: str,
    page_size: int = FISH_SHOP_ITEM_SEARCH_PAGE_SIZE,
) -> dict:
    """
    全量获取鱼小铺商品管理接口数据。

    流程：
    1. 请求第一页；
    2. 检查业务是否成功；
    3. 读取 currentPage/hasNextPage/pageSize/total/totalPage；
    4. 若 totalPage<=1 直接完成；
    5. 多页时动态创建 2..N 页任务，受控并发；
    6. 合并 itemSearchResponseList；
    7. 按 itemId 去重；
    8. 校验唯一数量与 total；
    9. 不一致时执行一次有限补偿扫描。

    返回：{"items": [...], "total": int, "unique_count": int}
    """
    session = requests.Session()
    for part in cookie_str.split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            session.cookies.set(key, value, domain=".goofish.com")

    extra_url_params = _build_item_search_url_params()

    first = await _fetch_page_with_retry(
        cookie_str, FISH_SHOP_ITEM_SEARCH_API, _build_item_search_data,
        _parse_item_search_response, 1, page_size,
        version=FISH_SHOP_ITEM_SEARCH_VERSION,
        session=session, extra_url_params=extra_url_params, label="item.search",
    )

    items_by_id: dict[str, dict] = {}
    for it in first["items"]:
        iid = it.get("external_goods_id") or it.get("itemId")
        if iid:
            items_by_id[str(iid)] = it

    total = first["total"]
    total_page = first["totalPage"]
    server_page_size = first["pageSize"]

    if total_page <= 1:
        return {
            "items": list(items_by_id.values()),
            "total": total,
            "unique_count": len(items_by_id),
        }

    sem = asyncio.Semaphore(FISH_SHOP_PAGE_CONCURRENCY)
    tasks = [
        _fetch_page_with_retry(
            cookie_str, FISH_SHOP_ITEM_SEARCH_API, _build_item_search_data,
            _parse_item_search_response, p, server_page_size,
            version=FISH_SHOP_ITEM_SEARCH_VERSION,
            session=session, extra_url_params=extra_url_params, semaphore=sem,
            label="item.search",
        )
        for p in range(2, total_page + 1)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed_pages = []
    for r in results:
        if isinstance(r, Exception):
            failed_pages.append(r)
            continue
        for it in r.get("items", []):
            iid = it.get("external_goods_id") or it.get("itemId")
            if iid:
                items_by_id[str(iid)] = it

    if failed_pages:
        logger.warning("鱼小铺 item.search 部分页面失败：%s", str(failed_pages)[:200])

    unique_count = len(items_by_id)
    # item.search 补偿扫描优化：
    # - 商品管理接口的 total 与实际返回商品数偶尔会因分页边界差异略有不一致，
    #   缺失 1-3 件通常是正常的分页边界现象，无需补偿扫描。
    # - 仅当缺失比例 > 10% 时才触发补偿扫描，避免少量缺失导致额外请求拖慢同步。
    missing_ratio = (total - unique_count) / total if total > 0 else 0
    if unique_count < total and missing_ratio > 0.1:
        logger.warning(
            "鱼小铺 item.search 去重后数量 %d 小于 total %d（缺失 %.1f%%），执行一次补偿扫描",
            unique_count, total, missing_ratio * 100,
        )
        # 补偿扫描：在已收集 ID 之外扫描几页
        comp_tasks = []
        for p in range(total_page + 1, total_page + 3):
            comp_tasks.append(
                _fetch_page_with_retry(
                    cookie_str, FISH_SHOP_ITEM_SEARCH_API, _build_item_search_data,
                    _parse_item_search_response, p, server_page_size,
                    version=FISH_SHOP_ITEM_SEARCH_VERSION,
                    session=session, extra_url_params=extra_url_params, semaphore=sem,
                    label="item.search-comp",
                )
            )
        comp_results = await asyncio.gather(*comp_tasks, return_exceptions=True)
        for r in comp_results:
            if isinstance(r, Exception):
                continue
            for it in r.get("items", []):
                iid = it.get("external_goods_id") or it.get("itemId")
                if iid:
                    items_by_id.setdefault(str(iid), it)
        new_unique = len(items_by_id)
        if new_unique < total:
            logger.warning(
                "鱼小铺 item.search 补偿后仍缺少 %d 件商品（账号数据可能在同步期间变化），保留已获得数据",
                total - new_unique,
            )
    elif unique_count < total:
        logger.info(
            "鱼小铺 item.search 去重后数量 %d 小于 total %d（缺失 %.1f%%，未达 10%% 阈值，跳过补偿扫描）",
            unique_count, total, missing_ratio * 100,
        )

    return {
        "items": list(items_by_id.values()),
        "total": total,
        "unique_count": len(items_by_id),
    }


async def fetch_fish_shop_datacompass_all(
    cookie_str: str,
    page_size: int = FISH_SHOP_DATACOMPASS_PAGE_SIZE,
) -> dict:
    """
    全量获取鱼小铺数据罗盘最近30天指标。

    流程：
    1. 请求第一页；
    2. 检查业务是否成功；
    3. 读取响应中的 total / pageNo / 实际 pageSize；
    4. 用服务端实际 pageSize 计算总页数；
    5. 动态创建剩余页任务；
    6. 合并所有指标；
    7. 按 itmId 去重；
    8. 校验唯一数量与 total；
    9. 不一致时执行一次有限补偿扫描。

    返回：{"metrics": {itmId: {"showPv": int, "ipv": int}}, "total": int, "unique_count": int}
    """
    session = requests.Session()
    for part in cookie_str.split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            session.cookies.set(key, value, domain=".goofish.com")

    first = await _fetch_page_with_retry(
        cookie_str, FISH_SHOP_DATACOMPASS_API, _build_datacompass_data,
        _parse_datacompass_response, 1, page_size,
        session=session, label="datacompass",
    )

    metrics: dict[str, dict] = {}
    for it in first["items"]:
        iid = it.get("itmId")
        if iid:
            metrics[str(iid)] = {"showPv": it["showPv"], "ipv": it["ipv"]}

    total = first["total"]
    server_page_size = first["pageSize"]
    total_page = first["totalPage"]

    if total_page <= 1:
        return {
            "metrics": metrics,
            "total": total,
            "unique_count": len(metrics),
        }

    sem = asyncio.Semaphore(FISH_SHOP_PAGE_CONCURRENCY)
    tasks = [
        _fetch_page_with_retry(
            cookie_str, FISH_SHOP_DATACOMPASS_API, _build_datacompass_data,
            _parse_datacompass_response, p, server_page_size,
            session=session, semaphore=sem, label="datacompass",
        )
        for p in range(2, total_page + 1)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed = []
    for r in results:
        if isinstance(r, Exception):
            failed.append(r)
            continue
        for it in r.get("items", []):
            iid = it.get("itmId")
            if iid:
                metrics.setdefault(str(iid), {"showPv": it["showPv"], "ipv": it["ipv"]})

    if failed:
        logger.warning("鱼小铺 datacompass 部分页面失败：%s", str(failed)[:200])

    unique_count = len(metrics)
    # 数据罗盘补偿扫描优化：
    # - datacompass 接口对部分商品（如新发布、无曝光）天然不返回指标数据，
    #   导致 unique_count < total 是正常现象，补偿扫描通常也无法获得缺失数据。
    # - 仅当缺失比例 > 20% 时才触发补偿扫描（避免个别商品缺失导致额外请求），
    #   且补偿扫描页数限制为 2 页，避免拖慢同步。
    missing_ratio = (total - unique_count) / total if total > 0 else 0
    if unique_count < total and missing_ratio > 0.2:
        logger.warning(
            "鱼小铺 datacompass 去重后数量 %d 小于 total %d（缺失 %.1f%%），执行一次补偿扫描",
            unique_count, total, missing_ratio * 100,
        )
        comp_tasks = []
        for p in range(total_page + 1, total_page + 3):
            comp_tasks.append(
                _fetch_page_with_retry(
                    cookie_str, FISH_SHOP_DATACOMPASS_API, _build_datacompass_data,
                    _parse_datacompass_response, p, server_page_size,
                    session=session, semaphore=sem, label="datacompass-comp",
                )
            )
        comp_results = await asyncio.gather(*comp_tasks, return_exceptions=True)
        for r in comp_results:
            if isinstance(r, Exception):
                continue
            for it in r.get("items", []):
                iid = it.get("itmId")
                if iid:
                    metrics.setdefault(str(iid), {"showPv": it["showPv"], "ipv": it["ipv"]})
    elif unique_count < total:
        logger.info(
            "鱼小铺 datacompass 去重后数量 %d 小于 total %d（缺失 %.1f%%，未达 20%% 阈值，跳过补偿扫描）",
            unique_count, total, missing_ratio * 100,
        )

    return {
        "metrics": metrics,
        "total": total,
        "unique_count": len(metrics),
    }


def _apply_datacompass_metrics(goods_dict: dict, metrics: Optional[dict]) -> None:
    """
    将数据罗盘的最近30天指标合并到商品字典。

    规则：
    - 只有 metrics 存在且明确返回 0 时，才写入 0；
    - metrics 中没有该商品时，不写入字段（保留已有值，不清零）。
    """
    if not metrics:
        return
    if "showPv" in metrics:
        goods_dict["exposure_count_30d"] = metrics["showPv"]
    if "ipv" in metrics:
        goods_dict["view_count_30d"] = metrics["ipv"]


async def sync_fish_shop_goods_for_account(
    account_id: int,
    tenant_id: int,
    cookie_str: str,
    sync_id: str,
    db_session_factory,
    async_fetch_detail: bool = True,
) -> dict:
    """
    鱼小铺账号商品同步主流程。

    流程：
    1. 复用 token 刷新（_refresh_m_h5_tk）；
    2. 并行调用两个鱼小铺接口（item.search + datacompass.item.list）；
       两个接口各自发现分页数量后受控并发拉取剩余页；
    3. 按 itemId / itmId 关联，将 showPv / ipv 合并到商品字典；
    4. 复用 _build_goods_insert_values / _build_goods_update_values 批量写入；
    5. 标记本地多余商品为下架；
    6. 持久化同步任务状态；
    7. 触发详情同步后台任务（可选）。
    """
    from .xianyu_goods_sync import (
        _persist_sync_task,
        _sync_tasks,
        _sync_lock,
        _async_fetch_details,
        _detail_sync_tasks,
        upsert_goods_record,
    )
    from ..core.database import async_session
    from ..models.entities import XianyuGoods
    from sqlalchemy import select, update, and_, func

    start_time = time.time()

    with _sync_lock:
        _sync_tasks[sync_id] = {
            "status": "running",
            "progress": 0,
            "total": 0,
            "new": 0,
            "updated": 0,
            "skipped": 0,
            "off_shelf": 0,
            "detail_synced": 0,
            "mode": "fish_shop",
        }

    await _persist_sync_task(
        sync_id, status="running", progress=0,
        account_id=account_id, tenant_id=tenant_id,
    )
    logger.info("鱼小铺同步开始: account_id=%d", account_id)
    # Token 刷新优化：
    # _refresh_m_h5_tk 需要 3 个串行 HTTP 请求（约 1.5-2 秒），
    # 而同步前通常 Cookie 中已包含有效的 _m_h5_tk（由 Cookie/Token 刷新调度器维护）。
    # 策略：
    # 1. 若 Cookie 中已有 _m_h5_tk，直接使用，跳过刷新（节省 ~2 秒）
    # 2. 若 API 调用触发 token 过期错误，_fetch_page_with_retry 会重试，
    #    届时再触发刷新（lazy refresh）
    existing_token = _get_token_from_cookie(cookie_str)
    if not existing_token:
        logger.info("账号 %d Cookie 中无 _m_h5_tk，执行刷新令牌流程", account_id)
        cookie_str = await asyncio.to_thread(_refresh_m_h5_tk, cookie_str)
    else:
        logger.info("账号 %d Cookie 中已包含 _m_h5_tk，跳过刷新（节省 ~2 秒）", account_id)

    async def _do_sync():
        goods_task = asyncio.create_task(
            fetch_fish_shop_goods_all(cookie_str), name="fish_shop_item_search"
        )
        compass_task = asyncio.create_task(
            fetch_fish_shop_datacompass_all(cookie_str), name="fish_shop_datacompass"
        )

        goods_result = await goods_task
        try:
            compass_result = await compass_task
            compass_ok = True
        except Exception as exc:
            logger.warning("鱼小铺数据罗盘接口失败，仅更新商品基础信息，保留已有 30 天指标 err=%s", str(exc)[:200])
            compass_result = {"metrics": {}, "total": 0, "unique_count": 0}
            compass_ok = False

        items = goods_result.get("items", [])
        metrics_map = compass_result.get("metrics", {})

        logger.info(
            "鱼小铺商品管理接口完成: unique=%d, total=%d; 数据罗盘完成: metrics=%d",
            len(items), goods_result.get("total", 0), len(metrics_map),
        )

        synced_ids: set[str] = set()
        updated_count = 0
        new_count = 0

        # 预处理：提取所有 external_goods_id，用于一次性批量查询现有商品
        all_ext_ids: list[str] = []
        items_by_ext_id: dict[str, dict] = {}
        for item_dict in items:
            ext_id = item_dict.get("external_goods_id")
            if not ext_id:
                continue
            ext_id_str = str(ext_id)
            synced_ids.add(ext_id_str)
            all_ext_ids.append(ext_id_str)
            items_by_ext_id[ext_id_str] = item_dict

        async with async_session() as db:
            # 批量查询现有商品（一次查询替代 N 次单独查询，大幅减少数据库往返）
            existing_map: dict[str, XianyuGoods] = {}
            if all_ext_ids:
                existing_result = await db.execute(
                    select(XianyuGoods).where(
                        and_(
                            XianyuGoods.tenant_id == tenant_id,
                            XianyuGoods.account_id == account_id,
                            XianyuGoods.external_goods_id.in_(all_ext_ids),
                        )
                    )
                )
                for g in existing_result.scalars():
                    if g.external_goods_id:
                        existing_map[str(g.external_goods_id)] = g

            # 用于对比的关键字段：仅当这些字段有变化时才执行 UPDATE，避免无变化的 73 次全量更新
            _compare_fields = (
                "title", "price", "sold_price", "cover_pic", "image_url",
                "quantity", "stock", "status",
                "exposure_count_30d", "view_count_30d",
                "gmt_create", "can_edit", "edit_note",
            )

            def _normalize_compare(value: Any) -> Any:
                """规范化比较值，避免类型差异（int vs str）造成误判。"""
                if value is None:
                    return None
                if isinstance(value, str):
                    s = value.strip()
                    # 尝试数字字符串转 int（"007" → 7, "0" → 0）
                    if s.lstrip("-").isdigit():
                        try:
                            return int(s)
                        except ValueError:
                            return s
                    return s
                return value

            def _has_changes(existing_row: XianyuGoods, update_values: dict) -> bool:
                """检查 update_values 中的关键字段是否与现有记录不同。"""
                for field in _compare_fields:
                    if field not in update_values:
                        continue
                    new_val = _normalize_compare(update_values.get(field))
                    old_val = _normalize_compare(getattr(existing_row, field, None))
                    if new_val != old_val:
                        return True
                return False

            # 收集待新增的商品（用于批量插入）
            new_items_to_insert: list[dict] = []

            for ext_id_str, item_dict in items_by_ext_id.items():
                metrics = metrics_map.get(ext_id_str)
                _apply_datacompass_metrics(item_dict, metrics)

                item_dict["account_id"] = account_id
                item_dict["tenant_id"] = tenant_id

                # 读取 _fish_shop_status 中间字段（由 _parse_fish_shop_goods_item 设置）
                # 不直接传给 ORM，避免 TypeError；在 insert/update values 构建后单独设置 status
                fish_shop_status = item_dict.pop("_fish_shop_status", None)

                existing = existing_map.get(ext_id_str)

                if existing:
                    update_values = _build_goods_update_values(
                        existing, item_dict, partial=False
                    )
                    # 删除可能的中间字段（_clean_goods_update_values 会复制所有键）
                    update_values.pop("_fish_shop_status", None)
                    # 覆盖 status 为鱼小铺接口返回的真实状态
                    if fish_shop_status is not None:
                        update_values["status"] = fish_shop_status
                    # 性能优化：跳过无变化的 UPDATE（实测 73 件商品中通常大部分数据无变化）
                    if update_values and _has_changes(existing, update_values):
                        await db.execute(
                            update(XianyuGoods)
                            .where(XianyuGoods.id == existing.id)
                            .values(**update_values)
                        )
                        updated_count += 1
                    # 无变化的商品静默跳过，不计入 updated_count
                else:
                    insert_values = _build_goods_insert_values(item_dict)
                    # 删除可能的中间字段
                    insert_values.pop("_fish_shop_status", None)
                    # 覆盖 status 为鱼小铺接口返回的真实状态
                    if fish_shop_status is not None:
                        insert_values["status"] = fish_shop_status
                    new_items_to_insert.append(insert_values)
                    new_count += 1

            # 批量插入新增商品（一次 INSERT 替代 N 次 add+commit，大幅减少数据库往返）
            if new_items_to_insert:
                await db.run_sync(lambda sync_db: sync_db.bulk_insert_mappings(
                    XianyuGoods, new_items_to_insert,
                ))

            await db.commit()

            # 标记本地多余商品为下架（单条 UPDATE 替代 SELECT + 循环 UPDATE）
            # 仅当 synced_ids 非空时执行：将不在本次同步结果中的本地商品 status 置为 0
            off_shelf_count = 0
            if synced_ids:
                # 先查询需要标记下架的商品数量（用于日志统计）
                count_stmt = select(func.count()).select_from(XianyuGoods).where(
                    and_(
                        XianyuGoods.tenant_id == tenant_id,
                        XianyuGoods.account_id == account_id,
                        XianyuGoods.deleted == 0,
                        XianyuGoods.status != 0,
                        XianyuGoods.external_goods_id.notin_(list(synced_ids)),
                    )
                )
                off_shelf_count = (await db.execute(count_stmt)).scalar() or 0
                # 单条 UPDATE 一次性标记所有不在 synced_ids 中的商品为下架
                if off_shelf_count > 0:
                    await db.execute(
                        update(XianyuGoods)
                        .where(
                            and_(
                                XianyuGoods.tenant_id == tenant_id,
                                XianyuGoods.account_id == account_id,
                                XianyuGoods.deleted == 0,
                                XianyuGoods.status != 0,
                                XianyuGoods.external_goods_id.notin_(list(synced_ids)),
                            )
                        )
                        .values(status=0)
                    )
                    await db.commit()

        duration = time.time() - start_time
        total_changed = new_count + updated_count

        sync_result = {
            "total": len(items),
            "unique_count": len(synced_ids),
            "new": new_count,
            "updated": updated_count,
            "off_shelf": off_shelf_count,
            "detail_synced": 0,
            "duration_seconds": duration,
            "compass_ok": compass_ok,
            "mode": "fish_shop",
        }

        logger.info(
            "鱼小铺同步完成: account_id=%d, total=%d, new=%d, updated=%d, off_shelf=%d, duration=%.1fs",
            account_id, sync_result["total"], new_count, updated_count,
            off_shelf_count, duration,
        )

        await _persist_sync_task(
            sync_id,
            status="completed",
            progress=100,
            total=sync_result["total"],
            new=new_count,
            updated=updated_count,
            off_shelf=off_shelf_count,
            detail_synced=0,
            duration_seconds=duration,
            account_id=account_id,
            tenant_id=tenant_id,
        )

        with _sync_lock:
            _sync_tasks[sync_id].update({
                "status": "completed",
                "progress": 100,
                "total": sync_result["total"],
                "new": new_count,
                "updated": updated_count,
                "off_shelf": off_shelf_count,
                "duration_seconds": duration,
            })

        return sync_result, items

    try:
        sync_result, detail_items = await _do_sync()

        # 触发详情同步后台任务
        if async_fetch_detail and detail_items:
            task = asyncio.create_task(
                _async_fetch_details(
                    cookie_str, detail_items, account_id, tenant_id, sync_id,
                ),
                name="fish_shop_detail_sync",
            )
            _detail_sync_tasks.add(task)
            task.add_done_callback(_detail_sync_tasks.discard)
            logger.info(
                "鱼小铺同步创建详情同步任务: account_id=%d, items_count=%d",
                account_id, len(detail_items),
            )

        return sync_result
    except Exception as exc:
        duration = time.time() - start_time
        logger.warning(
            "鱼小铺同步失败: account_id=%d, duration=%.1fs, err=%s",
            account_id, duration, str(exc)[:200],
        )
        await _persist_sync_task(
            sync_id, status="failed", progress=100,
            duration_seconds=duration,
            account_id=account_id, tenant_id=tenant_id,
        )
        with _sync_lock:
            _sync_tasks[sync_id].update({
                "status": "failed",
                "duration_seconds": duration,
            })
        raise
