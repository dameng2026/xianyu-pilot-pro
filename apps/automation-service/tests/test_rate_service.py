"""评价管理服务测试。

覆盖需求第二十八节要求的核心场景：
- 字段映射（merchantBuyerVO / merchantCommonData / merchantItemVO / rateItemVOList）
- 字符串布尔值安全解析（"true"/"false" 不被当作 True）
- seller 字段区分买家评价与卖家评价
- 评价状态判断（rateItemVOList 中是否存在 seller=true 记录）
- orderId 大整数按字符串处理
- 分页字段（nextPage / totalCount / lastEndRow）字符串安全规范化
- 创建评价成功判断（successOrderIds / failOrderInfos）
- 评价等级白名单（仅好评 rate=1 已确认）
- MTOP API 白名单（仅允许 mtop.taobao.idle.merchant.rate.create）
- 脱敏（买家昵称、物流单号）
- 缓存过期判断
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.services import rate_service
from app.services.rate_service import (
    ALLOWED_MTOP_ACTION_APIS,
    ALL_ACCOUNTS_CACHE_TTL_SECONDS,
    CONFIRMED_RATE_LEVELS,
    DEFAULT_PAGE_SIZE,
    FULL_SYNC_INTERVAL_SECONDS,
    MAX_PAGES_PER_ACCOUNT,
    QUERY_CODE_ALL,
    QUERY_TYPE_ORDER,
    RATE_CREATE_API,
    RATE_FEEDBACK_MAX_LENGTH,
    RATE_LEVEL_GOOD,
    RATE_LIST_API,
    SINGLE_ACCOUNT_CACHE_TTL_SECONDS,
    SUPPORTED_CATEGORIES,
    _extract_rate_fields,
    _mask_buyer_nick,
    _mask_mail_no,
    _parse_bool_string,
    _safe_int,
    _to_str,
    is_all_accounts_cache_expired,
    is_single_account_cache_expired,
    judge_create_rate_success,
)


# ============================================================
# 样本数据构造（按需求第五节响应结构）
# ============================================================

def _build_sample_rate_item(
    *,
    has_seller_rate: bool = False,
    seller_rate_str: str = "true",
    buyer_rate_str: str = "false",
    order_id: int = 3313120441127005861,
    item_id: int = 1234567890123456789,
) -> dict:
    """构造符合需求第五节响应结构的样本评价记录。

    seller_rate_str / buyer_rate_str 用于验证字符串布尔值解析。
    """
    rate_list = []
    if has_seller_rate:
        rate_list.append({
            "feedBack": "很棒",
            "gmtCreate": "2026-07-27 10:30:00",
            "illegal": "false",
            "main": "卖家已评价",
            "pictCdnUrlList": [],
            "rate": "1",
            "rateId": "rate-001",
            "raterHeadImg": "//img.alicdn.com/seller.png",
            "seller": seller_rate_str,
        })
    rate_list.append({
        "feedBack": "不错",
        "gmtCreate": "2026-07-27 10:00:00",
        "illegal": "false",
        "main": "买家评价",
        "pictCdnUrlList": ["//img.alicdn.com/buyer1.jpg"],
        "rate": "1",
        "rateId": "rate-002",
        "raterHeadImg": "//img.alicdn.com/buyer.png",
        "seller": buyer_rate_str,
    })
    return {
        "merchantBuyerVO": {
            "buyerId": "buyer-123",
            "userIcon": "//img.alicdn.com/avatar.png",
            "userNick": "买家用",
        },
        "merchantCommonData": {
            "buyerApplyModifyAddress": "false",
            "consignTime": "2026-07-26 09:00:00",
            "createTime": "2026-07-25 10:00:00",
            "finishTime": "2026-07-27 10:00:00",
            "inRefund": "false",
            "itemId": item_id,
            "orderId": order_id,
            "orderStatus": "TRADE_SUCCESS",
            "paySuccessTime": "2026-07-25 10:05:00",
            "sellerRateStatus": "4",
            "showDetail": "true",
            "companyName": "顺丰速运",
            "mailNo": "SF1234567890123",
        },
        "merchantItemVO": {
            "itemPicUrl": "//img.alicdn.com/imgextra/test-item-pic.jpg",
            "title": "测试商品标题",
            "itemInfoLines": "颜色:红色;尺码:L",
        },
        "rateItemVOList": rate_list,
    }


# ============================================================
# 字段映射测试（需求第五节、第二十八节）
# ============================================================

def test_extract_rate_fields_maps_buyer_info():
    """验证 merchantBuyerVO 字段映射：buyerId / userIcon / userNick。"""
    raw = _build_sample_rate_item()
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["buyer_id"] == "buyer-123"
    assert result["buyer_icon"] == "//img.alicdn.com/avatar.png"
    # 昵称脱敏（首尾保留，中间用*）
    assert result["buyer_nick"] is not None
    assert result["buyer_nick"][0] == "买"
    assert "*" in result["buyer_nick"]


def test_extract_rate_fields_maps_common_data():
    """验证 merchantCommonData 字段映射。"""
    raw = _build_sample_rate_item()
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["order_status"] == "TRADE_SUCCESS"
    # sellerRateStatus 仅存储原始字符串，不作语义判定（需求第六节）
    assert result["seller_rate_status"] == "4"
    assert result["logistics_company"] == "顺丰速运"
    # 物流单号脱敏（前4后4，中间用*）
    assert result["logistics_mail_no"].startswith("SF12")
    assert result["logistics_mail_no"].endswith("0123")
    assert "*" in result["logistics_mail_no"]
    # 时间字段正确解析
    assert result["finish_time"] is not None
    assert result["order_create_time"] is not None
    assert result["pay_success_time"] is not None
    assert result["consign_time"] is not None


def test_extract_rate_fields_uses_string_for_order_and_item_id():
    """orderId 和 itemId 必须按字符串处理，避免大整数精度丢失（需求第十六节、第二十一节）。"""
    raw = _build_sample_rate_item()
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["external_order_id"] == "3313120441127005861"
    assert result["external_item_id"] == "1234567890123456789"
    # 验证未发生浮点精度丢失
    assert "e+" not in result["external_order_id"]
    assert "e+" not in result["external_item_id"]


def test_extract_rate_fields_maps_item_vo():
    """验证 merchantItemVO 字段映射：itemPicUrl / title / itemInfoLines。"""
    raw = _build_sample_rate_item()
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["item_title"] == "测试商品标题"
    assert result["item_pic_url"] == "//img.alicdn.com/imgextra/test-item-pic.jpg"
    assert "颜色:红色" in result["item_info_lines"]


def test_extract_rate_fields_returns_none_when_no_order_id():
    """没有 orderId 的记录应被跳过（用于唯一标识）。"""
    raw = _build_sample_rate_item()
    raw["merchantCommonData"]["orderId"] = None
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is None


# ============================================================
# seller 字段字符串布尔值解析（需求第五节、第二十八节）
# ============================================================

def test_string_false_not_treated_as_true():
    """字符串 "false" 不能被当作 True（需求第五节明确要求）。"""
    assert _parse_bool_string("false") is False
    assert _parse_bool_string("False") is False
    assert _parse_bool_string("FALSE") is False
    assert _parse_bool_string("0") is False
    assert _parse_bool_string("") is False
    assert _parse_bool_string(None) is False


def test_string_true_treated_as_true():
    """字符串 "true" 应被当作 True。"""
    assert _parse_bool_string("true") is True
    assert _parse_bool_string("True") is True
    assert _parse_bool_string("TRUE") is True
    assert _parse_bool_string("1") is True
    assert _parse_bool_string(1) is True
    assert _parse_bool_string(True) is True


def test_extract_rate_fields_distinguishes_seller_buyer_rate():
    """seller=true 为卖家评价，seller=false 为买家评价（需求第五节）。"""
    raw = _build_sample_rate_item(has_seller_rate=True, seller_rate_str="true", buyer_rate_str="false")
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    # 卖家评价（seller=true）
    assert result["has_seller_rate"] == 1
    assert result["seller_rate_content"] == "很棒"
    assert result["seller_rate_level"] == "1"
    assert result["seller_rate_id"] == "rate-001"
    # 买家评价（seller=false）
    assert result["buyer_rate_content"] == "不错"
    assert result["buyer_rate_level"] == "1"


def test_string_seller_false_does_not_become_seller_rate():
    """seller="false" 必须被识别为买家评价（而非卖家评价）。"""
    raw = _build_sample_rate_item(has_seller_rate=False)
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["has_seller_rate"] == 0
    # 卖家评价字段为空
    assert result["seller_rate_content"] is None
    assert result["seller_rate_level"] is None
    # 买家评价字段应有数据
    assert result["buyer_rate_content"] == "不错"


# ============================================================
# 评价状态判断（需求第六节、第二十八节）
# ============================================================

def test_has_seller_rate_zero_when_no_seller_rate():
    """不存在 seller=true 评价时 has_seller_rate=0 且 rate_reviewable=1。"""
    raw = _build_sample_rate_item(has_seller_rate=False)
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["has_seller_rate"] == 0
    assert result["rate_reviewable"] == 1


def test_has_seller_rate_one_when_seller_rate_exists():
    """存在 seller=true 评价时 has_seller_rate=1 且 rate_reviewable=0（不可重复评价）。"""
    raw = _build_sample_rate_item(has_seller_rate=True)
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["has_seller_rate"] == 1
    assert result["rate_reviewable"] == 0


def test_seller_rate_status_stored_as_raw_string():
    """sellerRateStatus 仅存储原始字符串，不作语义判定（需求第六节）。"""
    raw = _build_sample_rate_item()
    raw["merchantCommonData"]["sellerRateStatus"] = "5"
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["seller_rate_status"] == "5"
    # 不应将 4/5 等数字直接映射为可评价/不可评价


# ============================================================
# 分页字段解析（需求第七节、第二十八节）
# ============================================================

def test_safe_int_parses_string_numbers():
    """_safe_int 应正确解析字符串数字。"""
    assert _safe_int("27") == 27
    assert _safe_int("0") == 0
    assert _safe_int(20) == 20
    assert _safe_int(None) == 0
    assert _safe_int("") == 0
    assert _safe_int("abc") == 0


def test_to_str_handles_large_int():
    """_to_str 应将大整数转为字符串，避免精度丢失。"""
    assert _to_str(3313120441127005861) == "3313120441127005861"
    assert _to_str("123") == "123"
    assert _to_str(None) is None
    assert _to_str("") is None


# ============================================================
# 脱敏测试（需求第二十五节、第二十八节）
# ============================================================

def test_mask_buyer_nick_preserves_ends():
    """买家昵称脱敏：保留首尾字符，中间用 * 替换。"""
    assert _mask_buyer_nick("买家用") == "买*用"
    # "张三李四王五" 共 6 字符，保留首尾后中间 4 字符替换为 4 个 *
    assert _mask_buyer_nick("张三李四王五") == "张****五"
    assert _mask_buyer_nick("小") == "小"
    assert _mask_buyer_nick("") is None
    assert _mask_buyer_nick(None) is None


def test_mask_mail_no_preserves_head_tail():
    """物流单号脱敏：保留前4后4，中间用 * 替换。"""
    # "SF1234567890123" 共 15 字符，保留前4后4后中间 7 字符替换为 7 个 *
    assert _mask_mail_no("SF1234567890123") == "SF12*******0123"
    assert _mask_mail_no("ABC1234") == "ABC1234"  # <=8 不脱敏
    assert _mask_mail_no("") is None
    assert _mask_mail_no(None) is None


# ============================================================
# 评价等级白名单（需求第十七节、第二十八节）
# ============================================================

def test_confirmed_rate_levels_only_contains_good():
    """已确认的可提交等级仅包含好评（rate=1）。

    中评、差评未经真实接口样本确认，不得在白名单中。
    """
    assert RATE_LEVEL_GOOD == 1
    assert CONFIRMED_RATE_LEVELS == frozenset({1})
    # 明确禁止 0、-1 进入白名单
    assert 0 not in CONFIRMED_RATE_LEVELS
    assert -1 not in CONFIRMED_RATE_LEVELS


def test_rate_feedback_max_length_is_reasonable():
    """评价内容最大长度应是一个保守上限。"""
    assert RATE_FEEDBACK_MAX_LENGTH > 0
    assert RATE_FEEDBACK_MAX_LENGTH <= 1000  # 保守上限


# ============================================================
# MTOP API 白名单（需求第二十五节、第二十八节）
# ============================================================

def test_allowed_mtop_action_apis_only_contains_create():
    """允许执行的 MTOP 操作 API 仅包含 rate.create（rate.list 不在动作白名单中）。"""
    assert RATE_CREATE_API in ALLOWED_MTOP_ACTION_APIS
    assert RATE_LIST_API not in ALLOWED_MTOP_ACTION_APIS
    # 列表查询不算"动作"


def test_rate_list_api_name_matches_requirement():
    """评价列表 API 名称应与需求第四节一致。"""
    assert RATE_LIST_API == "mtop.taobao.idle.merchant.rate.list"


def test_rate_create_api_name_matches_requirement():
    """创建评价 API 名称应与需求第十六节一致。"""
    assert RATE_CREATE_API == "mtop.taobao.idle.merchant.rate.create"


# ============================================================
# 创建评价成功判断（需求第十八节、第二十八节）
# ============================================================

def test_judge_create_rate_success_returns_true_for_success():
    """module.success=true 且 successOrderIds 包含 orderId 时判定成功。"""
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": "true",
                "successOrderIds": ["3313120441127005861"],
                "failOrderInfos": [],
            }
        },
    }
    ok, msg, module = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is True
    assert "成功" in msg


def test_judge_create_rate_success_returns_false_when_module_success_false():
    """module.success=false 时判定失败。"""
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": "false",
                "successOrderIds": [],
                "failOrderInfos": [],
            }
        },
    }
    ok, msg, _ = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is False


def test_judge_create_rate_success_returns_false_when_order_not_in_success_ids():
    """当前 orderId 未出现在 successOrderIds 中时按部分失败处理（需求第十八节）。"""
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": "true",
                "successOrderIds": ["9999999999999999999"],  # 不包含当前订单
                "failOrderInfos": [],
            }
        },
    }
    ok, msg, _ = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is False
    assert "未出现" in msg or "未确认" in msg


def test_judge_create_rate_success_returns_false_when_order_in_fail_infos():
    """failOrderInfos 中存在当前订单失败信息时判定失败。"""
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": "true",
                "successOrderIds": ["3313120441127005861"],
                "failOrderInfos": [
                    {
                        "orderId": "3313120441127005861",
                        "failReason": "订单已评价",
                    }
                ],
            }
        },
    }
    ok, msg, _ = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is False
    assert "已评价" in msg or "失败" in msg


def test_judge_create_rate_success_handles_string_success_field():
    """module.success 可能是字符串 "true"/"false"，必须做类型转换。"""
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": "true",
                "successOrderIds": ["order-1"],
                "failOrderInfos": [],
            }
        },
    }
    ok, _, _ = judge_create_rate_success(api_result, "order-1")
    assert ok is True


# ============================================================
# 缓存过期判断（需求第九节、第二十八节）
# ============================================================

def test_is_single_account_cache_expired_when_no_sync_time():
    """无同步时间时缓存视为过期。"""
    assert is_single_account_cache_expired(None) is True


def test_is_single_account_cache_expired_when_within_window():
    """同步时间在新鲜窗口内时不过期。"""
    recent = datetime.now() - timedelta(seconds=SINGLE_ACCOUNT_CACHE_TTL_SECONDS // 2)
    assert is_single_account_cache_expired(recent) is False


def test_is_single_account_cache_expired_when_beyond_window():
    """同步时间超过新鲜窗口时过期。"""
    old = datetime.now() - timedelta(seconds=SINGLE_ACCOUNT_CACHE_TTL_SECONDS + 10)
    assert is_single_account_cache_expired(old) is True


def test_is_all_accounts_cache_expired_when_no_sync_time():
    assert is_all_accounts_cache_expired(None) is True


def test_is_all_accounts_cache_expired_within_window():
    recent = datetime.now() - timedelta(seconds=ALL_ACCOUNTS_CACHE_TTL_SECONDS // 2)
    assert is_all_accounts_cache_expired(recent) is False


def test_is_all_accounts_cache_expired_beyond_window():
    old = datetime.now() - timedelta(seconds=ALL_ACCOUNTS_CACHE_TTL_SECONDS + 10)
    assert is_all_accounts_cache_expired(old) is True


# ============================================================
# 常量与配置（需求第四节、第七节、第八节、第十节）
# ============================================================

def test_query_constants_match_requirement():
    """queryType/queryCode 应与需求第四节确认值一致。"""
    assert QUERY_TYPE_ORDER == "ORDER"
    assert QUERY_CODE_ALL == "ALL"


def test_pagination_constants_are_safe():
    """分页保护常量应设置合理上限。"""
    assert DEFAULT_PAGE_SIZE == 20  # 需求第四节确认
    assert MAX_PAGES_PER_ACCOUNT > 0
    assert MAX_PAGES_PER_ACCOUNT <= 100  # 合理上限


def test_sync_intervals_are_configurable():
    """缓存与完整同步间隔应为可调整的合理值。"""
    assert SINGLE_ACCOUNT_CACHE_TTL_SECONDS > 0
    assert ALL_ACCOUNTS_CACHE_TTL_SECONDS > SINGLE_ACCOUNT_CACHE_TTL_SECONDS  # 全部账号窗口更大
    assert FULL_SYNC_INTERVAL_SECONDS > ALL_ACCOUNTS_CACHE_TTL_SECONDS  # 完整校准更低频


def test_supported_categories_match_local_filter():
    """本地筛选分类应与需求第十二节一致：all / pending / done。"""
    assert set(SUPPORTED_CATEGORIES) == {"all", "pending", "done"}
