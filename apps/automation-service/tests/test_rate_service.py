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
    RATE_LEVEL_BAD,
    RATE_LEVEL_GOOD,
    RATE_LEVEL_NEUTRAL,
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
    seller_rate_value: str = "1",
    buyer_rate_value: str = "1",
    buyer_feedback: str = "不错",
    order_id: int = 3313120441127005861,
    item_id: int = 1234567890123456789,
) -> dict:
    """构造符合需求第五节响应结构的样本评价记录。

    seller_rate_str / buyer_rate_str 用于验证字符串布尔值解析。
    seller_rate_value / buyer_rate_value 用于验证不同评价等级（"1"/"-1"/"0"）。
    buyer_feedback 用于构造买家占位记录（如"ta在交易成功后未做出评价内容"）。
    """
    rate_list = []
    if has_seller_rate:
        rate_list.append({
            "feedBack": "很棒",
            "gmtCreate": "2026-07-27 10:30:00",
            "illegal": "false",
            "main": "卖家已评价",
            "pictCdnUrlList": [],
            "rate": seller_rate_value,
            "rateId": "rate-001",
            "raterHeadImg": "//img.alicdn.com/seller.png",
            "seller": seller_rate_str,
        })
    rate_list.append({
        "feedBack": buyer_feedback,
        "gmtCreate": "2026-07-27 10:00:00",
        "illegal": "false",
        "main": "买家评价",
        "pictCdnUrlList": ["//img.alicdn.com/buyer1.jpg"],
        "rate": buyer_rate_value,
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
# 评价等级映射与白名单（需求第一节、第二节、第三节、第五节、第十八节）
# ============================================================

def test_confirmed_rate_levels_contains_all_three():
    """已确认的可提交等级包含好评(1)、中评(-1)、差评(0)。

    需求第一节、第二节、第三节已通过真实接口样本确认：
    - 好评 rate=1
    - 中评 rate=-1（真实请求样本：data.module.success=true，successOrderIds 包含 orderId）
    - 差评 rate=0（真实请求样本：data.module.success=true，successOrderIds 包含 orderId）
    """
    assert RATE_LEVEL_GOOD == 1
    assert RATE_LEVEL_NEUTRAL == -1
    assert RATE_LEVEL_BAD == 0
    assert CONFIRMED_RATE_LEVELS == frozenset({1, -1, 0})
    # 三个等级均在白名单中
    assert 1 in CONFIRMED_RATE_LEVELS
    assert -1 in CONFIRMED_RATE_LEVELS
    assert 0 in CONFIRMED_RATE_LEVELS
    # 不得交换中评和差评的数值
    assert RATE_LEVEL_NEUTRAL != 0
    assert RATE_LEVEL_BAD != -1


def test_rate_zero_is_valid_bad_review():
    """差评 rate=0 是合法业务值，不得因真假判断被拦截（需求第六节）。

    0 不可被当作：未选择 / 空值 / undefined / 无效评价 / 未映射。
    """
    assert RATE_LEVEL_BAD == 0
    assert 0 in CONFIRMED_RATE_LEVELS
    # 0 是合法值，bool(0) 为 False 但 0 仍是有效评价等级
    assert bool(RATE_LEVEL_BAD) is False  # Python 中 bool(0) is False
    # 但 0 仍在白名单中，不应被 if not rate 拦截
    assert RATE_LEVEL_BAD in CONFIRMED_RATE_LEVELS


def test_rate_negative_one_is_valid_neutral_review():
    """中评 rate=-1 是合法业务值，不得被当作非法值（需求第六节）。

    -1 不可被当作：未选择 / 非法 / 未映射。
    """
    assert RATE_LEVEL_NEUTRAL == -1
    assert -1 in CONFIRMED_RATE_LEVELS


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
    """本地筛选分类应包含状态筛选与等级筛选（需求第十二节）。

    - 状态：all / pending / done
    - 等级：good / neutral / bad（仅匹配 seller=true 的卖家评价）
    """
    assert set(SUPPORTED_CATEGORIES) == {"all", "pending", "done", "good", "neutral", "bad"}


# ============================================================
# 卖家评价等级识别（需求第八节、第十节、第十八节）
# ============================================================

def test_seller_rate_negative_one_is_neutral():
    """seller=true 且 rate=-1 应识别为卖家中评（需求第一节、第十节）。

    不得把 seller=true 的 rate=-1 当作差评或未映射。
    """
    raw = _build_sample_rate_item(
        has_seller_rate=True,
        seller_rate_str="true",
        seller_rate_value="-1",
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["has_seller_rate"] == 1
    assert result["seller_rate_level"] == "-1"
    assert result["seller_rate_content"] == "很棒"


def test_seller_rate_zero_is_bad():
    """seller=true 且 rate=0 应识别为卖家差评（需求第一节、第十节）。

    0 是合法业务值，不得因真假判断被当成空值或未选择（需求第六节）。
    """
    raw = _build_sample_rate_item(
        has_seller_rate=True,
        seller_rate_str="true",
        seller_rate_value="0",
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["has_seller_rate"] == 1
    assert result["seller_rate_level"] == "0"
    assert result["seller_rate_content"] == "很棒"


def test_seller_rate_one_is_good():
    """seller=true 且 rate=1 应识别为卖家好评（需求第一节、第十节）。"""
    raw = _build_sample_rate_item(
        has_seller_rate=True,
        seller_rate_str="true",
        seller_rate_value="1",
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["has_seller_rate"] == 1
    assert result["seller_rate_level"] == "1"


def test_seller_rate_supports_integer_value():
    """seller 评价等级也兼容整数形式（1/-1/0 而非字符串，需求第七节）。"""
    raw = _build_sample_rate_item(
        has_seller_rate=True,
        seller_rate_str="true",
        seller_rate_value=-1,  # 整数而非字符串
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["has_seller_rate"] == 1
    assert result["seller_rate_level"] == "-1"


# ============================================================
# 买家占位记录与中评冲突（需求第八节、第十一节、第十八节）
# ============================================================

def test_buyer_placeholder_rate_negative_one_not_seller_rate():
    """seller=false、rate=-1、feedback='ta在交易成功后未做出评价内容' 不得当作卖家评价（需求第八节）。

    关键约束：
    - 不得因 rate=-1 就把卖家状态显示为中评
    - 不得把订单标记为卖家已评价
    - 不得计入卖家中评统计
    """
    raw = _build_sample_rate_item(
        has_seller_rate=False,
        buyer_rate_str="false",
        buyer_rate_value="-1",
        buyer_feedback="ta在交易成功后未做出评价内容",
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    # 不得标记为卖家已评价
    assert result["has_seller_rate"] == 0
    # 卖家评价字段应为空
    assert result["seller_rate_content"] is None
    assert result["seller_rate_level"] is None
    # 买家评价字段应有占位内容
    assert result["buyer_rate_content"] == "ta在交易成功后未做出评价内容"
    assert result["buyer_rate_level"] == "-1"
    # 仍可评价
    assert result["rate_reviewable"] == 1


def test_buyer_placeholder_does_not_affect_seller_status():
    """即使买家侧 rate=-1 存在占位记录，卖家状态仍由 seller=true 记录决定（需求第八节）。

    构造同时包含：
    - seller=false, rate=-1, feedback='ta在交易成功后未做出评价内容'（买家占位）
    - seller=true, rate=1（卖家好评）
    验证卖家等级只取 seller=true 记录。
    """
    raw = _build_sample_rate_item(
        has_seller_rate=True,
        seller_rate_str="true",
        seller_rate_value="1",
        buyer_rate_str="false",
        buyer_rate_value="-1",
        buyer_feedback="ta在交易成功后未做出评价内容",
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    # 卖家评价取 seller=true 记录
    assert result["has_seller_rate"] == 1
    assert result["seller_rate_level"] == "1"  # 卖家好评，而非 -1
    assert result["seller_rate_content"] == "很棒"
    # 买家评价取 seller=false 记录
    assert result["buyer_rate_level"] == "-1"
    assert "未做出评价" in result["buyer_rate_content"]


def test_multiple_rate_records_do_not_overwrite():
    """同一订单同时存在买家与卖家评价时不应互相覆盖（需求第十八节）。"""
    raw = _build_sample_rate_item(
        has_seller_rate=True,
        seller_rate_str="true",
        seller_rate_value="-1",  # 卖家中评
        buyer_rate_str="false",
        buyer_rate_value="0",  # 买家差评
        buyer_feedback="买家差评内容",
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    # 卖家与买家各自独立
    assert result["seller_rate_level"] == "-1"
    assert result["buyer_rate_level"] == "0"
    assert result["seller_rate_content"] == "很棒"
    assert result["buyer_rate_content"] == "买家差评内容"
    assert result["has_seller_rate"] == 1


# ============================================================
# 创建评价成功判断（中评 / 差评，需求第二节、第三节、第十五节、第十八节）
# ============================================================

def test_judge_create_rate_success_for_neutral():
    """中评 rate=-1 提交成功响应应判定为成功（需求第二节、第十五节）。

    真实请求依据：
    - ret 包含 SUCCESS
    - data.module.success 为 true
    - failOrderInfos 为空
    - successOrderIds 包含目标订单ID
    """
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
    ok, msg, _ = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is True
    assert "成功" in msg


def test_judge_create_rate_success_for_bad():
    """差评 rate=0 提交成功响应应判定为成功（需求第三节、第十五节）。

    真实请求依据：
    - ret 包含 SUCCESS
    - data.module.success 为 true
    - failOrderInfos 为空
    - successOrderIds 包含目标订单ID
    不得因 rate=0 提前拒绝。
    """
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
    ok, msg, _ = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is True
    assert "成功" in msg


def test_judge_create_rate_success_for_neutral_with_integer_success():
    """中评成功响应中 module.success 为布尔 true 时也应判定成功。"""
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": True,  # 布尔而非字符串
                "successOrderIds": ["order-neutral"],
                "failOrderInfos": [],
            }
        },
    }
    ok, _, _ = judge_create_rate_success(api_result, "order-neutral")
    assert ok is True


def test_judge_create_rate_failure_does_not_change_local_level():
    """中评/差评提交失败时不应改变本地等级（需求第十八节）。

    此测试验证 judge_create_rate_success 在失败时返回 False，
    上层 create_rate 会据此保留本地状态（不标记为已评价）。
    """
    # module.success=false 表示提交失败
    api_result = {
        "success": True,
        "data": {
            "module": {
                "success": "false",
                "successOrderIds": [],
                "failOrderInfos": [
                    {"orderId": "3313120441127005861", "failReason": "订单已评价"}
                ],
            }
        },
    }
    ok, msg, _ = judge_create_rate_success(api_result, "3313120441127005861")
    assert ok is False
    # 失败原因应包含具体信息
    assert "已评价" in msg or "失败" in msg


# ============================================================
# 创建评价等级校验（需求第五节、第六节）
# ============================================================

def test_invalid_rate_values_not_in_confirmed_levels():
    """非法评价值不应通过白名单校验（需求第五节）。

    允许的创建评价值只能是 1、-1、0。
    """
    invalid_values = [2, -2, 3, -3, 100, -100]
    for v in invalid_values:
        assert v not in CONFIRMED_RATE_LEVELS, f"{v} 不应在白名单中"


def test_create_rate_rejects_invalid_level_early():
    """create_rate 应在数据库访问前拒绝非法评价等级（需求第五节、第六节）。

    通过 asyncio.run 调用，传入 None 作为 db（因非法等级会提前返回，
    不会触及数据库访问）。
    """
    import asyncio

    async def _run():
        # 非法等级 2 应被拒绝（不触及 db）
        result = await rate_service.create_rate(
            db=None, account_id=1, order_id="order-1",
            rate=2, feedback="测试", anonymous=False, tenant_id=1,
        )
        return result

    result = asyncio.run(_run())
    assert result["ok"] is False
    assert "不合法" in result["error"] or "仅支持" in result["error"]


def test_create_rate_accepts_all_three_levels_early_validation(monkeypatch):
    """create_rate 对 1/-1/0 均通过等级校验（需求第五节、第六节）。

    使用 monkeypatch 替换 verify_fish_shop_account，使其返回"非鱼小铺账号"，
    这样函数会在等级校验之后、数据库访问之前被拦截，从而能区分
    "等级校验失败"与"数据库访问失败"。
    """
    import asyncio

    async def _fake_verify(db, account_id, tenant_id):
        # 返回 (is_fish_shop=False, auth=None, err_msg) 以阻断后续 db 访问
        return False, None, "测试桩：账号不是鱼小铺"

    monkeypatch.setattr(rate_service, "verify_fish_shop_account", _fake_verify)

    async def _run(rate):
        result = await rate_service.create_rate(
            db=None, account_id=1, order_id="order-1",
            rate=rate, feedback="测试", anonymous=False, tenant_id=1,
        )
        return result

    for rate in [1, -1, 0]:
        result = asyncio.run(_run(rate))
        # 应该被鱼小铺校验拦截，而不是被等级校验拦截
        assert result["ok"] is False
        assert "不合法" not in result["error"], f"rate={rate} 不应被等级校验拒绝"
        assert "仅支持" not in result["error"], f"rate={rate} 不应被等级校验拒绝"
        assert "鱼小铺" in result["error"], f"rate={rate} 应被鱼小铺校验拦截"


# ============================================================
# 提交参数构造（需求第五节）
# ============================================================

def test_call_create_rate_builds_correct_payload_for_good():
    """好评提交参数应为 rate=1（需求第五节）。

    构造请求体（需求第二节确认）：
        {
          "tradeIdList": ["orderId"],
          "imageUrls": [],
          "rate": 1,
          "feedback": "...",
          "anonymous": false
        }
    不得使用字符串标签（如 "good"）直接提交。
    """
    captured = {}

    def _fake_post(account_id, cookie_str, api, data_str, timeout):
        import json as _json
        captured["api"] = api
        captured["data"] = _json.loads(data_str)
        return {"success": True, "data": {"module": {"success": "true"}}}

    monkeypatch_target = "app.services.rate_service._post_mtop_with_token_retry"
    import app.services.rate_service as _svc

    original = _svc._post_mtop_with_token_retry
    _svc._post_mtop_with_token_retry = _fake_post
    original_get_auth = _svc._get_account_auth
    original_decrypt = _svc._decrypt_value
    _svc._get_account_auth = lambda aid: {"encrypted_cookie": "enc"}
    _svc._decrypt_value = lambda v: "cookie-str"
    try:
        result = rate_service.call_create_rate(
            account_id=1, order_id="order-1", rate=1,
            feedback="好评内容", anonymous=False,
        )
    finally:
        _svc._post_mtop_with_token_retry = original
        _svc._get_account_auth = original_get_auth
        _svc._decrypt_value = original_decrypt

    assert result["success"] is True
    assert captured["api"] == RATE_CREATE_API
    assert captured["data"]["rate"] == 1
    assert captured["data"]["rate"] != "good"
    assert captured["data"]["tradeIdList"] == ["order-1"]
    assert captured["data"]["imageUrls"] == []
    assert captured["data"]["feedback"] == "好评内容"
    assert captured["data"]["anonymous"] is False


def test_call_create_rate_builds_correct_payload_for_neutral():
    """中评提交参数应为 rate=-1（需求第二节、第五节）。

    真实请求依据（需求第二节）：
        {
          "tradeIdList": ["目标订单ID"],
          "imageUrls": [],
          "rate": -1,
          "feedback": "用户输入的评价内容",
          "anonymous": false
        }
    不得使用 "normal" 等字符串标签直接提交。
    """
    captured = {}

    def _fake_post(account_id, cookie_str, api, data_str, timeout):
        import json as _json
        captured["data"] = _json.loads(data_str)
        return {"success": True, "data": {"module": {"success": "true"}}}

    import app.services.rate_service as _svc
    original = _svc._post_mtop_with_token_retry
    original_get_auth = _svc._get_account_auth
    original_decrypt = _svc._decrypt_value
    _svc._post_mtop_with_token_retry = _fake_post
    _svc._get_account_auth = lambda aid: {"encrypted_cookie": "enc"}
    _svc._decrypt_value = lambda v: "cookie-str"
    try:
        result = rate_service.call_create_rate(
            account_id=1, order_id="order-neutral", rate=-1,
            feedback="中评内容", anonymous=False,
        )
    finally:
        _svc._post_mtop_with_token_retry = original
        _svc._get_account_auth = original_get_auth
        _svc._decrypt_value = original_decrypt

    assert result["success"] is True
    assert captured["data"]["rate"] == -1
    assert captured["data"]["rate"] != "normal"
    assert captured["data"]["tradeIdList"] == ["order-neutral"]


def test_call_create_rate_builds_correct_payload_for_bad():
    """差评提交参数应为 rate=0（需求第三节、第五节）。

    真实请求依据（需求第三节）：
        {
          "tradeIdList": ["目标订单ID"],
          "imageUrls": [],
          "rate": 0,
          "feedback": "用户输入的评价内容",
          "anonymous": false
        }
    不得使用 "bad" 等字符串标签直接提交。
    不得因 rate=0 被替换为 null/未选择。
    """
    captured = {}

    def _fake_post(account_id, cookie_str, api, data_str, timeout):
        import json as _json
        captured["data"] = _json.loads(data_str)
        return {"success": True, "data": {"module": {"success": "true"}}}

    import app.services.rate_service as _svc
    original = _svc._post_mtop_with_token_retry
    original_get_auth = _svc._get_account_auth
    original_decrypt = _svc._decrypt_value
    _svc._post_mtop_with_token_retry = _fake_post
    _svc._get_account_auth = lambda aid: {"encrypted_cookie": "enc"}
    _svc._decrypt_value = lambda v: "cookie-str"
    try:
        result = rate_service.call_create_rate(
            account_id=1, order_id="order-bad", rate=0,
            feedback="差评内容", anonymous=False,
        )
    finally:
        _svc._post_mtop_with_token_retry = original
        _svc._get_account_auth = original_get_auth
        _svc._decrypt_value = original_decrypt

    assert result["success"] is True
    # 关键：rate=0 必须原样出现在请求体中，不能被替换为 null/未选择
    assert captured["data"]["rate"] == 0
    assert captured["data"]["rate"] is not None
    assert captured["data"]["rate"] != "bad"
    assert captured["data"]["tradeIdList"] == ["order-bad"]


def test_call_create_rate_preserves_anonymous_flag():
    """anonymous 字段必须使用真实布尔值（需求第五节）。"""
    captured = {}

    def _fake_post(account_id, cookie_str, api, data_str, timeout):
        import json as _json
        captured["data"] = _json.loads(data_str)
        return {"success": True, "data": {"module": {"success": "true"}}}

    import app.services.rate_service as _svc
    original = _svc._post_mtop_with_token_retry
    original_get_auth = _svc._get_account_auth
    original_decrypt = _svc._decrypt_value
    _svc._post_mtop_with_token_retry = _fake_post
    _svc._get_account_auth = lambda aid: {"encrypted_cookie": "enc"}
    _svc._decrypt_value = lambda v: "cookie-str"
    try:
        # 匿名
        rate_service.call_create_rate(
            account_id=1, order_id="o1", rate=1,
            feedback="x", anonymous=True,
        )
        anon_true = captured["data"]["anonymous"]
        # 不匿名
        rate_service.call_create_rate(
            account_id=1, order_id="o1", rate=1,
            feedback="x", anonymous=False,
        )
        anon_false = captured["data"]["anonymous"]
    finally:
        _svc._post_mtop_with_token_retry = original
        _svc._get_account_auth = original_get_auth
        _svc._decrypt_value = original_decrypt

    assert anon_true is True
    assert anon_false is False


# ============================================================
# 数据库存储类型验证（需求第十六节）
# ============================================================

def test_seller_rate_level_stored_as_string():
    """seller_rate_level 字段存储为字符串，可无损保存 1/-1/0（需求第十六节）。

    通过 _extract_rate_fields 提取后，seller_rate_level 始终是字符串：
    - rate=1  → "1"
    - rate=-1 → "-1"
    - rate=0  → "0"

    不得将 0 转换为空、-1 转换为未映射、rate 保存为布尔值。
    """
    # 好评
    raw_good = _build_sample_rate_item(
        has_seller_rate=True, seller_rate_str="true", seller_rate_value="1"
    )
    result_good = _extract_rate_fields(raw_good, account_id=1, tenant_id=1)
    assert result_good["seller_rate_level"] == "1"
    assert isinstance(result_good["seller_rate_level"], str)

    # 中评
    raw_neutral = _build_sample_rate_item(
        has_seller_rate=True, seller_rate_str="true", seller_rate_value="-1"
    )
    result_neutral = _extract_rate_fields(raw_neutral, account_id=1, tenant_id=1)
    assert result_neutral["seller_rate_level"] == "-1"
    assert isinstance(result_neutral["seller_rate_level"], str)

    # 差评
    raw_bad = _build_sample_rate_item(
        has_seller_rate=True, seller_rate_str="true", seller_rate_value="0"
    )
    result_bad = _extract_rate_fields(raw_bad, account_id=1, tenant_id=1)
    assert result_bad["seller_rate_level"] == "0"
    assert isinstance(result_bad["seller_rate_level"], str)
    # 关键：0 不得被转换为 None/空
    assert result_bad["seller_rate_level"] is not None
    assert result_bad["seller_rate_level"] != ""


def test_seller_rate_level_preserves_integer_input():
    """整数形式的 rate 也能正确转为字符串存储（需求第七节、第十六节）。"""
    # 整数 1
    raw = _build_sample_rate_item(
        has_seller_rate=True, seller_rate_str="true", seller_rate_value=1
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["seller_rate_level"] == "1"

    # 整数 -1
    raw = _build_sample_rate_item(
        has_seller_rate=True, seller_rate_str="true", seller_rate_value=-1
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["seller_rate_level"] == "-1"

    # 整数 0
    raw = _build_sample_rate_item(
        has_seller_rate=True, seller_rate_str="true", seller_rate_value=0
    )
    result = _extract_rate_fields(raw, account_id=1, tenant_id=1)
    assert result["seller_rate_level"] == "0"
    # 关键：0 不得丢失
    assert result["seller_rate_level"] is not None
