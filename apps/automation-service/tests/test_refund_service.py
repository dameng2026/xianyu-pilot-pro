"""退款管理服务测试。

覆盖需求第三十节要求的核心场景：
- 字段映射（itemVO/priceVO/commonData/refundInfoVO/rightVO）
- 分页字符串安全规范化（"true"/"27"/"0"）
- URL 安全校验（仅允许闲鱼/阿里官方域名）
- 金额处理（字符串十进制，避免浮点误差）
- 脱敏（买家昵称、物流单号）
- 分类映射（orderStatus 精确匹配）
- MTOP API 白名单（仅允许 agree.refund）
- 退运费分类无可靠映射时不返回数据
- 退款详情三接口并行调用、缓存、去重、局部失败、components 按 render 解析
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest

from app.services import refund_service
from app.services.refund_service import (
    ALLOWED_MTOP_ACTION_APIS,
    CATEGORY_ORDER_STATUS_MAP,
    DEFAULT_PAGE_SIZE,
    DANGEROUS_PROTOCOLS,
    MAX_PAGES_PER_ACCOUNT,
    QUERY_CODE_ALL,
    REFUND_AGREE_API,
    REFUND_DETAIL_API,
    REFUND_DETAIL_CACHE_TTL_SECONDS,
    REFUND_FULL_INFO_API,
    REFUND_LIST_API,
    REFUND_SERVICE_RECORD_API,
    SUPPORTED_CATEGORIES,
    SUPPORTED_REFUND_DETAIL_RENDERS,
    TRUSTED_EXTERNAL_HOSTS,
    _check_full_info_order_id_consistency,
    _check_full_info_success,
    _check_refund_detail_success,
    _check_service_record_success,
    _decode_html_entities,
    _detail_cache_key,
    _extract_refund_fields,
    _find_component_by_render,
    _get_cached_detail,
    _get_or_create_inflight,
    _invalidate_cached_detail,
    _is_mtop_success,
    _mask_buyer_nick,
    _mask_mail_no,
    _normalize_logistic_info,
    _normalize_proof_media_list,
    _normalize_rich_text_items,
    _parse_basic_refund_info,
    _parse_bottom_bar,
    _parse_full_info_module,
    _parse_progress_detail,
    _parse_refund_detail_components,
    _parse_service_record_data,
    _parse_bool_string,
    _safe_decimal,
    _safe_int,
    _safe_style_dict,
    _safe_url_for_open,
    _validate_proof_image_url,
    _validate_rich_text_link,
    fetch_refund_detail,
    fetch_refund_full_info,
    fetch_refund_service_record,
)


# ============================================================
# 字段映射测试（需求第九节、第三十节）
# ============================================================

def _build_sample_refund_item():
    """构造一个符合需求第八节响应结构的样本退款记录。"""
    return {
        "itemVO": {
            "itemPicUrl": "//img.alicdn.com/imgextra/test-item-pic.jpg",
            "title": "测试商品标题",
            "itemInfoLines": "颜色:红色;尺码:L",
        },
        "priceVO": {
            "buyNum": "2",
            "refundFee": "12.50",
            "auctionPrice": "6.25",
        },
        "commonData": {
            "itemId": 1234567890123456789,  # 大整数，验证字符串处理
            "orderId": 9876543210987654321,
            "orderStatus": "未发货退款",
            "orderSimpleRemark": "买家申请退款",
            "refundStatus": "REFUND_APPLYING",
            "createTime": "2026-07-27 10:00:00",
            "companyName": "顺丰速运",
            "mailNo": "SF1234567890123",
            "consignTime": "2026-07-27 09:00:00",
        },
        "refundInfoVO": {
            "refundId": 123456789,
            "refundStatus": "等待卖家处理",
            "refundStatusDesc": "还剩 23 小时 59 分",
            "reason": "商品与描述不符",
            "csStatus": "no",
            "gmtCreate": "2026-07-27 10:30:00",
        },
        "buyerInfoVO": {
            "buyerId": "buyer-123",
            "userNick": "买家用",
            "userIcon": "//img.alicdn.com/avatar.png",
        },
        "rightVO": {
            "btnList": [
                {
                    "code": "viewRefundDetail",
                    "name": "退款详情",
                    "clickEvent": {
                        "type": "url",
                        "data": {"url": "https://www.goofish.com/refund/detail?refundId=123456789"},
                    },
                },
                {
                    "code": "applyDisputePage",
                    "name": "我要维权",
                    "clickEvent": {
                        "type": "url",
                        "data": {"url": "https://www.goofish.com/refund/dispute?refundId=123456789"},
                    },
                },
                {
                    "code": "agreeRefundApply",
                    "name": "同意退款",
                    "clickEvent": {
                        "type": "doubleCheck",
                        "data": {
                            "title": "确认同意退款",
                            "confirmText": "同意后将立即退款给买家",
                            "riskDesc": "此操作不可撤销",
                        },
                    },
                },
                # 未支持的操作（应被过滤掉）
                {
                    "code": "contactBuyer",
                    "name": "联系买家",
                    "clickEvent": {"type": "url", "data": {"url": "https://www.goofish.com/chat"}},
                },
            ],
        },
    }


def test_extract_refund_fields_maps_item_vo_fields():
    """验证 itemVO 字段映射：itemPicUrl / title / itemInfoLines。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result is not None
    assert result["item_title"] == "测试商品标题"
    assert result["item_pic_url"] == "//img.alicdn.com/imgextra/test-item-pic.jpg"
    assert "颜色:红色;尺码:L" in result["item_info_lines"]


def test_extract_refund_fields_maps_price_vo_fields():
    """验证 priceVO 字段映射：buyNum / refundFee / auctionPrice。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result["buy_num"] == "2"
    assert result["refund_fee"] == Decimal("12.50")
    assert result["auction_price"] == Decimal("6.25")


def test_extract_refund_fields_uses_string_for_item_and_order_id():
    """商品ID和订单ID必须按字符串处理，避免大整数精度丢失。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result["external_item_id"] == "1234567890123456789"
    assert result["external_order_id"] == "9876543210987654321"
    # 验证字符串与原始值一致（未发生浮点精度丢失）
    assert result["external_item_id"] != "1.2345678901234568e+18"


def test_extract_refund_fields_maps_common_data_fields():
    """验证 commonData 字段映射：orderStatus / orderSimpleRemark / companyName / mailNo / consignTime。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result["order_status"] == "未发货退款"
    assert result["order_simple_remark"] == "买家申请退款"
    assert result["logistics_company"] == "顺丰速运"
    assert result["consign_time"] is not None


def test_extract_refund_fields_maps_refund_info_vo_fields():
    """验证 refundInfoVO 字段映射：refundStatus / refundStatusDesc / reason / csStatus / gmtCreate。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result["refund_status"] == "等待卖家处理"
    assert result["refund_status_desc"] == "还剩 23 小时 59 分"
    assert result["refund_reason"] == "商品与描述不符"
    assert result["cs_status"] == "no"
    assert result["refund_create_time"] is not None


def test_extract_refund_fields_refund_id_as_string():
    """refundId 必须按字符串存储。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result["external_refund_id"] == "123456789"


def test_extract_refund_fields_skips_record_without_refund_id():
    """没有 refundId 的记录应被跳过（返回 None）。"""
    raw = _build_sample_refund_item()
    raw["refundInfoVO"]["refundId"] = None
    raw.pop("refundId", None)
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    assert result is None


def test_extract_refund_fields_falls_back_to_common_create_time():
    """退款申请时间缺失时回退到 commonData.createTime。"""
    raw = _build_sample_refund_item()
    raw["refundInfoVO"]["gmtCreate"] = None
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    # refund_create_time 应该来自 common_create_time
    assert result["refund_create_time"] is not None
    assert result["common_create_time"] is not None


def test_extract_refund_fields_filters_unsupported_buttons():
    """rightVO.btnList 中仅保留本项目支持的操作（viewRefundDetail/applyDisputePage/agreeRefundApply）。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    buttons = json.loads(result["right_buttons_json"])
    codes = [b["code"] for b in buttons]
    assert "viewRefundDetail" in codes
    assert "applyDisputePage" in codes
    assert "agreeRefundApply" in codes
    # 不支持的按钮应被过滤掉
    assert "contactBuyer" not in codes


def test_extract_refund_fields_masks_buyer_nick_and_mail_no():
    """买家昵称和物流单号必须脱敏存储。"""
    raw = _build_sample_refund_item()
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    # 买家用 -> 买*用
    assert result["buyer_nick"] == "买*用"
    # 物流单号 SF1234567890123 -> SF12********0123
    assert result["logistics_mail_no"] is not None
    assert "*" in result["logistics_mail_no"]
    assert result["logistics_mail_no"] != "SF1234567890123"


def test_extract_refund_fields_filters_untrusted_url_buttons():
    """URL 类按钮的 URL 不可信时应被过滤掉。"""
    raw = _build_sample_refund_item()
    # 将 viewRefundDetail 的 URL 改为不可信域名
    raw["rightVO"]["btnList"][0]["clickEvent"]["data"]["url"] = "https://evil.example.com/refund"
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    buttons = json.loads(result["right_buttons_json"])
    codes = [b["code"] for b in buttons]
    assert "viewRefundDetail" not in codes  # URL 不可信，被过滤
    assert "applyDisputePage" in codes  # 其他按钮不受影响


def test_extract_refund_fields_rejects_dangerous_url_protocol():
    """javascript: 等危险协议的 URL 应被过滤。"""
    raw = _build_sample_refund_item()
    raw["rightVO"]["btnList"][0]["clickEvent"]["data"]["url"] = "javascript:alert('xss')"
    result = _extract_refund_fields(raw, account_id=1, tenant_id=1)
    buttons = json.loads(result["right_buttons_json"])
    codes = [b["code"] for b in buttons]
    assert "viewRefundDetail" not in codes


# ============================================================
# 分页字符串安全规范化测试（需求第十三节、第三十节）
# ============================================================

def test_parse_bool_string_handles_string_true():
    """字符串 'true' 应被解析为 True。"""
    assert _parse_bool_string("true") is True
    assert _parse_bool_string("True") is True
    assert _parse_bool_string("TRUE") is True


def test_parse_bool_string_handles_string_false():
    """字符串 'false' 应被解析为 False（不能依赖 JS 字符串真值）。"""
    assert _parse_bool_string("false") is False
    assert _parse_bool_string("False") is False


def test_parse_bool_string_handles_numeric():
    assert _parse_bool_string(1) is True
    assert _parse_bool_string(0) is False
    assert _parse_bool_string(True) is True
    assert _parse_bool_string(False) is False
    assert _parse_bool_string(None) is False


def test_safe_int_handles_string_numbers():
    """分页字段可能是字符串形式（'27'/'0'），需安全解析。"""
    assert _safe_int("27") == 27
    assert _safe_int("0") == 0
    assert _safe_int(27) == 27
    assert _safe_int(None) == 0
    assert _safe_int("") == 0
    assert _safe_int("invalid") == 0


# ============================================================
# 金额处理测试（需求第二十八节、第三十节）
# ============================================================

def test_safe_decimal_handles_string_amount():
    """金额字符串应安全解析为 Decimal，避免浮点误差。"""
    assert _safe_decimal("12.50") == Decimal("12.50")
    assert _safe_decimal("0.01") == Decimal("0.01")
    assert _safe_decimal(12.5) == Decimal("12.5")


def test_safe_decimal_returns_none_for_invalid():
    assert _safe_decimal(None) is None
    assert _safe_decimal("") is None
    assert _safe_decimal("invalid") is None


def test_safe_decimal_preserves_precision():
    """验证大金额不会因为浮点转换而精度丢失。"""
    # 这是一个会因浮点而丢失精度的例子
    float_value = 0.1 + 0.2  # 0.30000000000000004
    decimal_value = _safe_decimal("0.3")
    assert decimal_value == Decimal("0.3")
    assert decimal_value != Decimal(str(float_value))


# ============================================================
# URL 安全校验测试（需求第二十四节、第三十节）
# ============================================================

def test_safe_url_accepts_goofish_official_domain():
    """闲鱼官方域名应通过校验。"""
    assert _safe_url_for_open("https://www.goofish.com/refund/detail?id=123") is not None
    assert _safe_url_for_open("https://seller.goofish.com/refund/list") is not None


def test_safe_url_accepts_taobao_official_domain():
    """淘宝/阿里官方域名应通过校验。"""
    assert _safe_url_for_open("https://trade.taobao.com/refund/detail") is not None
    assert _safe_url_for_open("https://www.alipay.com/refund") is not None


def test_safe_url_accepts_subdomain_of_trusted():
    """可信域名的子域名应通过校验。"""
    assert _safe_url_for_open("https://refund.goofish.com/detail/123") is not None


def test_safe_url_rejects_untrusted_domain():
    """非可信域名应被拒绝。"""
    assert _safe_url_for_open("https://evil.example.com/refund") is None
    assert _safe_url_for_open("https://phishing.com/goofish.com") is None


def test_safe_url_rejects_javascript_protocol():
    """javascript: 协议应被拒绝。"""
    assert _safe_url_for_open("javascript:alert('xss')") is None


def test_safe_url_rejects_data_protocol():
    """data: 协议应被拒绝。"""
    assert _safe_url_for_open("data:text/html,<script>alert(1)</script>") is None


def test_safe_url_rejects_file_protocol():
    """file: 协议应被拒绝。"""
    assert _safe_url_for_open("file:///etc/passwd") is None


def test_safe_url_rejects_empty_or_none():
    assert _safe_url_for_open(None) is None
    assert _safe_url_for_open("") is None
    assert _safe_url_for_open("   ") is None


def test_dangerous_protocols_contains_expected_values():
    """DANGEROUS_PROTOCOLS 应包含 javascript/data/file/vbscript。"""
    assert "javascript:" in DANGEROUS_PROTOCOLS
    assert "data:" in DANGEROUS_PROTOCOLS
    assert "file:" in DANGEROUS_PROTOCOLS
    assert "vbscript:" in DANGEROUS_PROTOCOLS


def test_trusted_external_hosts_contains_goofish():
    """TRUSTED_EXTERNAL_HOSTS 应包含闲鱼/阿里官方域名。"""
    assert "goofish.com" in TRUSTED_EXTERNAL_HOSTS
    assert "taobao.com" in TRUSTED_EXTERNAL_HOSTS
    assert "alipay.com" in TRUSTED_EXTERNAL_HOSTS


# ============================================================
# 脱敏测试
# ============================================================

def test_mask_buyer_nick_long_name():
    """长昵称应保留首尾，中间用 * 替换。"""
    assert _mask_buyer_nick("买家用") == "买*用"
    assert _mask_buyer_nick("买家用户名") == "买***名"


def test_mask_buyer_nick_short_name():
    """两字符昵称应保留首字符，第二字符替换为 *。"""
    assert _mask_buyer_nick("买家") == "买*"


def test_mask_buyer_nick_single_char():
    """单字符昵称应原样返回。"""
    assert _mask_buyer_nick("买") == "买"


def test_mask_buyer_nick_none():
    assert _mask_buyer_nick(None) is None
    assert _mask_buyer_nick("") is None


def test_mask_mail_no_long():
    """长物流单号应保留前4后4，中间用 * 替换。"""
    masked = _mask_mail_no("SF1234567890123")
    assert masked.startswith("SF12")
    assert masked.endswith("0123")
    assert "*" in masked
    assert masked != "SF1234567890123"


def test_mask_mail_no_short():
    """短物流单号（<=8字符）应原样返回。"""
    assert _mask_mail_no("SF1234") == "SF1234"


def test_mask_mail_no_none():
    assert _mask_mail_no(None) is None
    assert _mask_mail_no("") is None


# ============================================================
# 分类映射测试（需求第五节、第三十节）
# ============================================================

def test_category_order_status_map_has_unshipped():
    """未发货退款应映射到 '未发货退款' orderStatus。"""
    assert "未发货退款" in CATEGORY_ORDER_STATUS_MAP["unshipped"]


def test_category_order_status_map_has_shipped():
    """已发货退款应映射到 '已发货退款' orderStatus。"""
    assert "已发货退款" in CATEGORY_ORDER_STATUS_MAP["shipped"]


def test_category_order_status_map_has_return():
    """退货退款应映射到 '退货退款' orderStatus。"""
    assert "退货退款" in CATEGORY_ORDER_STATUS_MAP["return"]


def test_category_order_status_map_no_freight():
    """退运费分类不应有猜测的 orderStatus 映射。"""
    assert "freight" not in CATEGORY_ORDER_STATUS_MAP


def test_supported_categories_has_five_tabs():
    """应支持五个分类标签。"""
    assert SUPPORTED_CATEGORIES == ["all", "unshipped", "shipped", "return", "freight"]


def test_category_map_uses_exact_match():
    """分类映射应使用精确匹配，不含模糊值。"""
    for status_list in CATEGORY_ORDER_STATUS_MAP.values():
        for status in status_list:
            # 必须是已确认的 orderStatus 值
            assert status in ("未发货退款", "已发货退款", "退货退款")


# ============================================================
# MTOP API 白名单测试（需求第十一节、第二十三节、第三十节）
# ============================================================

def test_allowed_mtop_action_apis_only_contains_agree_refund():
    """仅允许 agree.refund API，防止 rightVO 返回任意 API 被执行。"""
    assert REFUND_AGREE_API in ALLOWED_MTOP_ACTION_APIS
    assert len(ALLOWED_MTOP_ACTION_APIS) == 1


def test_refund_list_api_name_matches_demand():
    """退款列表 API 名称必须与需求第六节确认一致。"""
    assert REFUND_LIST_API == "mtop.taobao.idle.merchant.refund.list"


def test_refund_agree_api_name_matches_demand():
    """同意退款 API 名称必须与需求第十一节确认一致。"""
    assert REFUND_AGREE_API == "mtop.taobao.idle.merchant.refund.agree.refund"


def test_query_code_all_matches_demand():
    """全部订单的 queryCode 必须为 'ALL'。"""
    assert QUERY_CODE_ALL == "ALL"


# ============================================================
# 分页保护常量测试（需求第十三节、第三十节）
# ============================================================

def test_default_page_size_is_20():
    """默认每页大小应为 20（需求第十三节确认）。"""
    assert DEFAULT_PAGE_SIZE == 20


def test_max_pages_per_account_has_protection():
    """应设置最大页数保护，防止无限循环。"""
    assert MAX_PAGES_PER_ACCOUNT > 0
    assert MAX_PAGES_PER_ACCOUNT >= 50  # 至少支持 50 页（1000 条）


# ============================================================
# fetch_refund_list_page 接口调用测试（mock MTOP）
# ============================================================

class _FakeMtopResult:
    def __init__(self, payload):
        self._payload = payload

    def get(self, key, default=None):
        return self._payload.get(key, default)


def test_fetch_refund_list_page_calls_mtop_with_correct_data_structure(monkeypatch):
    """验证 fetch_refund_list_page 发送的 data 结构与需求第六节一致。"""
    captured = {}

    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout):
        captured["account_id"] = account_id
        captured["api"] = api
        captured["data_str"] = data_str
        captured["timeout"] = timeout
        return {
            "success": True,
            "data": {
                "data": {
                    "items": [],
                    "nextPage": "false",
                    "totalCount": "0",
                    "lastEndRow": "0",
                    "ext": {},
                }
            },
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "unb=123; _m_h5_tk=token_123" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = refund_service.fetch_refund_list_page(account_id=1, page_number=1, page_size=20)

    # 验证 data 结构
    import json as _json
    data_obj = _json.loads(captured["data_str"])
    assert data_obj["pageNumber"] == 1
    assert data_obj["rowsPerPage"] == 20
    assert data_obj["queryType"] == "refund"
    assert data_obj["refundSearchParam"] == {"queryCode": "ALL"}

    # 验证 API 名称
    assert captured["api"] == "mtop.taobao.idle.merchant.refund.list"

    # 验证返回结果
    assert result["success"] is True
    assert result["data"]["items"] == []
    assert result["data"]["nextPage"] is False  # 字符串 "false" 应被解析为 False
    assert result["data"]["totalCount"] == 0


def test_fetch_refund_list_page_normalizes_string_pagination_fields(monkeypatch):
    """验证 nextPage/totalCount 字符串字段被安全规范化。"""
    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout):
        return {
            "success": True,
            "data": {
                "data": {
                    "items": [{"refundInfoVO": {"refundId": "1"}}],
                    "nextPage": "true",  # 字符串 "true"
                    "totalCount": "27",  # 字符串 "27"
                    "lastEndRow": "0",
                    "ext": {"totalRefundFee": "150.00"},
                }
            },
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = refund_service.fetch_refund_list_page(account_id=1, page_number=1)

    assert result["success"] is True
    assert result["data"]["nextPage"] is True  # "true" -> True
    assert result["data"]["totalCount"] == 27  # "27" -> 27
    assert result["data"]["ext"]["totalRefundFee"] == "150.00"


def test_fetch_refund_list_page_returns_failure_when_no_auth(monkeypatch):
    """账号无认证信息时应返回失败。"""
    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: None)
    result = refund_service.fetch_refund_list_page(account_id=1)
    assert result["success"] is False
    assert "认证" in result["error"] or "auth" in result["error"].lower()


def test_fetch_refund_list_page_returns_failure_when_cookie_empty(monkeypatch):
    """Cookie 为空时应返回失败。"""
    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "" if value == "enc" else "")
    result = refund_service.fetch_refund_list_page(account_id=1)
    assert result["success"] is False
    assert "Cookie" in result["error"] or "cookie" in result["error"].lower()


def test_fetch_refund_list_page_returns_failure_on_mtop_failure(monkeypatch):
    """MTOP 业务返回失败时不应当作成功。"""
    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout):
        return {
            "success": False,
            "error": "FAIL_SYS_USER_VALIDATE",
            "ret": ["FAIL_SYS_USER_VALIDATE::Baxia验证"],
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = refund_service.fetch_refund_list_page(account_id=1)
    assert result["success"] is False
    assert "FAIL_SYS_USER_VALIDATE" in result["error"]


def test_fetch_refund_list_page_returns_failure_when_data_missing(monkeypatch):
    """HTTP 200 但 data.data 不存在时应返回失败。"""
    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout):
        return {
            "success": True,
            "data": {},  # 缺少 data.data
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = refund_service.fetch_refund_list_page(account_id=1)
    assert result["success"] is False
    assert "结构异常" in result["error"] or "structure" in result["error"].lower()


def test_fetch_refund_list_page_handles_non_list_items(monkeypatch):
    """items 不是合法数组时应返回空列表。"""
    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout):
        return {
            "success": True,
            "data": {
                "data": {
                    "items": "not-a-list",  # 非法 items
                    "nextPage": "false",
                    "totalCount": "0",
                }
            },
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = refund_service.fetch_refund_list_page(account_id=1)
    assert result["success"] is True
    assert result["data"]["items"] == []  # 非法 items 被规范化为空列表


# ============================================================
# 退款详情 - 三接口 API 常量测试（需求第六、七、八节）
# ============================================================

def test_refund_service_record_api_name_matches_demand():
    """退款服务记录 API 名称必须与需求第六节一致。"""
    assert REFUND_SERVICE_RECORD_API == "mtop.taobao.idle.merchant.refund.service.record"


def test_refund_full_info_api_name_matches_demand():
    """完整订单信息 API 名称必须与需求第七节一致。"""
    assert REFUND_FULL_INFO_API == "mtop.taobao.idle.trade.merchant.full.info"


def test_refund_detail_api_name_matches_demand():
    """退款核心详情 API 名称必须与需求第八节一致。"""
    assert REFUND_DETAIL_API == "mtop.taobao.idle.merchant.refund.detail"


def test_detail_query_apis_whitelist_only_contains_query_apis():
    """详情接口白名单仅含查询类接口，禁止执行类接口（如 agree.refund）。"""
    from app.services.refund_service import DETAIL_QUERY_APIS
    assert REFUND_SERVICE_RECORD_API in DETAIL_QUERY_APIS
    assert REFUND_FULL_INFO_API in DETAIL_QUERY_APIS
    assert REFUND_DETAIL_API in DETAIL_QUERY_APIS
    # 同意退款 API 不得出现在详情查询白名单中
    assert REFUND_AGREE_API not in DETAIL_QUERY_APIS


def test_refund_detail_cache_ttl_is_short():
    """退款详情缓存时长必须为短时（60秒），不得缓存数小时。"""
    assert REFUND_DETAIL_CACHE_TTL_SECONDS == 60
    assert REFUND_DETAIL_CACHE_TTL_SECONDS <= 300  # 不超过 5 分钟


# ============================================================
# fetch_refund_service_record 接口测试（需求第六节）
# ============================================================

def test_fetch_refund_service_record_sends_correct_data_structure(monkeypatch):
    """验证 fetch_refund_service_record 发送的 data 仅含 orderId，API 名称正确。

    需求第六节：type=originaljson，不带 valueType=string。
    """
    captured = {}

    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout, **kwargs):
        captured["api"] = api
        captured["data_str"] = data_str
        captured["kwargs"] = kwargs
        return {
            "success": True,
            "ret": ["SUCCESS::调用成功"],
            "data": {"data": {"refundRecordList": [], "postageRefundRecordList": []}},
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = fetch_refund_service_record(account_id=1, order_id="123456789")

    assert captured["api"] == REFUND_SERVICE_RECORD_API
    data_obj = json.loads(captured["data_str"])
    assert data_obj == {"orderId": "123456789"}
    # 需求第六节：type=originaljson，不带 valueType
    assert captured["kwargs"].get("query_type") == "originaljson"
    assert captured["kwargs"].get("include_value_type") is False
    assert result["success"] is True


def test_fetch_refund_service_record_rejects_empty_order_id():
    """orderId 为空时应返回失败。"""
    result = fetch_refund_service_record(account_id=1, order_id="")
    assert result["success"] is False
    assert "orderId" in result["error"]


def test_fetch_refund_service_record_returns_failure_when_no_auth(monkeypatch):
    """无账号认证信息时返回失败。"""
    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: None)
    result = fetch_refund_service_record(account_id=1, order_id="123")
    assert result["success"] is False


# ============================================================
# fetch_refund_full_info 接口测试（需求第七节）
# ============================================================

def test_fetch_refund_full_info_uses_tid_not_orderId(monkeypatch):
    """验证 fetch_refund_full_info 使用 tid 参数名，不是 orderId/refundId/itemId。

    需求第七节：type=json，带 valueType=string。
    """
    captured = {}

    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout, **kwargs):
        captured["api"] = api
        captured["data_str"] = data_str
        captured["kwargs"] = kwargs
        return {
            "success": True,
            "ret": ["SUCCESS::调用成功"],
            "data": {"module": {"merchantCommonData": {}}},
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = fetch_refund_full_info(account_id=1, order_id="987654321")

    assert captured["api"] == REFUND_FULL_INFO_API
    data_obj = json.loads(captured["data_str"])
    # 严格按需求第七节：参数名是 tid
    assert data_obj == {"tid": "987654321"}
    assert "orderId" not in data_obj
    assert "refundId" not in data_obj
    assert "itemId" not in data_obj
    # 需求第七节：type=json，带 valueType=string
    assert captured["kwargs"].get("query_type") == "json"
    assert captured["kwargs"].get("include_value_type") is True
    assert result["success"] is True


# ============================================================
# fetch_refund_detail 接口测试（需求第八节）
# ============================================================

def test_fetch_refund_detail_sends_orderId_and_refundId(monkeypatch):
    """验证 fetch_refund_detail 发送 orderId 和 refundId 两个参数，API 名称正确。

    需求第八节：type=originaljson，不带 valueType=string。
    """
    captured = {}

    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout, **kwargs):
        captured["api"] = api
        captured["data_str"] = data_str
        captured["kwargs"] = kwargs
        return {
            "success": True,
            "ret": ["SUCCESS::调用成功"],
            "data": {"data": {"orderId": "123", "refundId": "456", "components": []}},
        }

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    result = fetch_refund_detail(account_id=1, order_id="123", refund_id="456")

    assert captured["api"] == REFUND_DETAIL_API
    data_obj = json.loads(captured["data_str"])
    assert data_obj == {"orderId": "123", "refundId": "456"}
    # 需求第八节：type=originaljson，不带 valueType
    assert captured["kwargs"].get("query_type") == "originaljson"
    assert captured["kwargs"].get("include_value_type") is False
    assert result["success"] is True


def test_fetch_refund_detail_rejects_empty_refund_id():
    """refundId 为空时应返回失败。"""
    result = fetch_refund_detail(account_id=1, order_id="123", refund_id="")
    assert result["success"] is False
    assert "refundId" in result["error"]


# ============================================================
# 三接口分别签名验证（需求第十八节）
# ============================================================

def test_three_apis_use_distinct_data_strings(monkeypatch):
    """三个接口必须分别构造 data 和 sign，不得共用。

    验证：三次调用 _post_mtop_with_token_retry 收到的 data_str 各不相同。
    同时验证三个接口的 query_type 和 include_value_type 参数差异化传递。
    """
    captured = []

    def fake_post_mtop(account_id, cookie_str, api, data_str, timeout, **kwargs):
        captured.append({
            "api": api,
            "data_str": data_str,
            "query_type": kwargs.get("query_type"),
            "include_value_type": kwargs.get("include_value_type"),
        })
        if api == REFUND_SERVICE_RECORD_API:
            return {"success": True, "ret": ["SUCCESS"], "data": {"data": {}}}
        if api == REFUND_FULL_INFO_API:
            return {"success": True, "ret": ["SUCCESS"], "data": {"module": {}}}
        if api == REFUND_DETAIL_API:
            return {"success": True, "ret": ["SUCCESS"], "data": {"data": {"components": []}}}
        return {"success": False, "error": "unknown api"}

    monkeypatch.setattr(refund_service, "_get_account_auth", lambda account_id: {"encrypted_cookie": "enc"})
    monkeypatch.setattr(refund_service, "_decrypt_value", lambda value: "cookie" if value == "enc" else "")
    monkeypatch.setattr(refund_service, "_post_mtop_with_token_retry", fake_post_mtop)

    fetch_refund_service_record(account_id=1, order_id="order-1")
    fetch_refund_full_info(account_id=1, order_id="order-1")
    fetch_refund_detail(account_id=1, order_id="order-1", refund_id="refund-1")

    assert len(captured) == 3
    apis = [c["api"] for c in captured]
    data_strs = [c["data_str"] for c in captured]
    # 三个 API 名称各不相同
    assert len(set(apis)) == 3
    # 三个 data 字符串各不相同
    assert len(set(data_strs)) == 3

    # 需求第六/七/八节：三个接口的 query_type 和 include_value_type 必须差异化
    by_api = {c["api"]: c for c in captured}
    # service.record：type=originaljson，不带 valueType
    assert by_api[REFUND_SERVICE_RECORD_API]["query_type"] == "originaljson"
    assert by_api[REFUND_SERVICE_RECORD_API]["include_value_type"] is False
    # full.info：type=json，带 valueType=string
    assert by_api[REFUND_FULL_INFO_API]["query_type"] == "json"
    assert by_api[REFUND_FULL_INFO_API]["include_value_type"] is True
    # refund.detail：type=originaljson，不带 valueType
    assert by_api[REFUND_DETAIL_API]["query_type"] == "originaljson"
    assert by_api[REFUND_DETAIL_API]["include_value_type"] is False


# ============================================================
# 成功判定测试（需求第十七节）
# ============================================================

def test_is_mtop_success_handles_list_with_success_prefix():
    assert _is_mtop_success(["SUCCESS::调用成功"]) is True
    assert _is_mtop_success(["SUCCESS"]) is True


def test_is_mtop_success_handles_failure_ret():
    assert _is_mtop_success(["FAIL_SYS_USER_VALIDATE::Baxia验证"]) is False
    assert _is_mtop_success([]) is False
    assert _is_mtop_success(None) is False


def test_is_mtop_success_handles_string():
    assert _is_mtop_success("SUCCESS::ok") is True
    assert _is_mtop_success("FAIL::x") is False


def test_check_service_record_success_requires_data_data():
    """service.record 成功判定：data.data 必须存在。"""
    ok, _ = _check_service_record_success({
        "success": True, "ret": ["SUCCESS"],
        "data": {"data": {"refundRecordList": []}},
    })
    assert ok is True


def test_check_service_record_success_fails_when_data_data_missing():
    ok, err = _check_service_record_success({
        "success": True, "ret": ["SUCCESS"], "data": {},
    })
    assert ok is False
    assert "data.data" in err or "结构异常" in err


def test_check_service_record_success_fails_on_mtop_failure():
    ok, _ = _check_service_record_success({
        "success": True, "ret": ["FAIL_SYS_USER_VALIDATE"], "data": {"data": {}},
    })
    assert ok is False


def test_check_full_info_success_requires_module():
    """full.info 成功判定：data.module 必须存在。"""
    ok, _ = _check_full_info_success({
        "success": True, "ret": ["SUCCESS"], "data": {"module": {"merchantCommonData": {}}},
    })
    assert ok is True


def test_check_full_info_success_fails_when_module_missing():
    ok, err = _check_full_info_success({
        "success": True, "ret": ["SUCCESS"], "data": {},
    })
    assert ok is False
    assert "module" in err


def test_check_refund_detail_success_validates_id_consistency():
    """refund.detail 成功判定：响应 orderId/refundId 必须与请求一致。"""
    ok, _ = _check_refund_detail_success({
        "success": True, "ret": ["SUCCESS"],
        "data": {"data": {"orderId": "123", "refundId": "456", "components": []}},
    }, expected_order_id="123", expected_refund_id="456")
    assert ok is True


def test_check_refund_detail_success_rejects_mismatched_order_id():
    """响应 orderId 与请求不一致时拒绝合并。"""
    ok, err = _check_refund_detail_success({
        "success": True, "ret": ["SUCCESS"],
        "data": {"data": {"orderId": "999", "refundId": "456", "components": []}},
    }, expected_order_id="123", expected_refund_id="456")
    assert ok is False
    assert "orderId" in err and "不一致" in err


def test_check_refund_detail_success_rejects_mismatched_refund_id():
    ok, err = _check_refund_detail_success({
        "success": True, "ret": ["SUCCESS"],
        "data": {"data": {"orderId": "123", "refundId": "999", "components": []}},
    }, expected_order_id="123", expected_refund_id="456")
    assert ok is False
    assert "refundId" in err and "不一致" in err


def test_check_refund_detail_success_requires_components_as_list():
    """components 必须是数组（或 None）。"""
    ok, err = _check_refund_detail_success({
        "success": True, "ret": ["SUCCESS"],
        "data": {"data": {"components": "not-a-list"}},
    }, expected_order_id="123", expected_refund_id="456")
    assert ok is False
    assert "components" in err


def test_check_full_info_order_id_consistency_passes_when_match():
    """merchantCommonData.orderId 与请求一致时通过。"""
    ok, _ = _check_full_info_order_id_consistency(
        {"merchantCommonData": {"orderId": "123"}}, "123"
    )
    assert ok is True


def test_check_full_info_order_id_consistency_fails_when_mismatch():
    ok, err = _check_full_info_order_id_consistency(
        {"merchantCommonData": {"orderId": "999"}}, "123"
    )
    assert ok is False
    assert "orderId" in err and "不一致" in err


def test_check_full_info_order_id_consistency_passes_when_missing():
    """merchantCommonData 缺失时不视为不一致（前置校验已拦截）。"""
    ok, _ = _check_full_info_order_id_consistency({}, "123")
    assert ok is True


# ============================================================
# components 按 render 解析测试（需求第九节）
# ============================================================

def test_find_component_by_render_finds_matching_component():
    """按 render 字段查找组件，不按固定下标。"""
    components = [
        {"render": "basicRefundInfo", "data": {"refundId": "1"}},
        {"render": "nodeStatusInfo", "data": {}},
    ]
    found = _find_component_by_render(components, "nodeStatusInfo")
    assert found is not None
    assert found["render"] == "nodeStatusInfo"


def test_find_component_by_render_returns_none_when_not_found():
    components = [{"render": "basicRefundInfo"}]
    assert _find_component_by_render(components, "nodeStatusInfo") is None


def test_find_component_by_render_handles_non_list():
    """components 不是 list 时安全返回 None。"""
    assert _find_component_by_render(None, "basicRefundInfo") is None
    assert _find_component_by_render("not-a-list", "basicRefundInfo") is None


def test_supported_renders_contains_all_confirmed_renders():
    """已确认的 render 值必须全部支持。"""
    expected = {
        "nodeStatusInfo", "refundStatusInfo", "investigationInfo",
        "refundDescribe", "progressDetail", "bottomBar", "bottomShow",
        "popPostageUrl", "basicRefundInfo", "postageRefundInfo",
    }
    assert expected.issubset(SUPPORTED_REFUND_DETAIL_RENDERS)


def test_parse_refund_detail_components_handles_empty_components():
    """空 components 数组应返回所有区域为 None / 空。"""
    result = _parse_refund_detail_components({}, "refund-1")
    assert result["basicRefundInfo"] is None
    assert result["nodeStatusInfo"] is None
    assert result["bottomBar"] == []
    assert result["unknown_renders"] == []


def test_parse_refund_detail_components_ignores_unknown_render():
    """未识别 render 应安全忽略，不报错。"""
    inner_data = {"components": [{"render": "unknownFutureRender", "data": {}}]}
    result = _parse_refund_detail_components(inner_data, "refund-1")
    assert "unknownFutureRender" in result["unknown_renders"]
    # 已识别组件仍为空
    assert result["basicRefundInfo"] is None


def test_parse_refund_detail_components_order_change_does_not_affect_parsing():
    """顺序变化不影响解析结果。"""
    components_a = [
        {"render": "basicRefundInfo", "data": {"refundId": "1"}},
        {"render": "nodeStatusInfo", "data": {}},
    ]
    components_b = list(reversed(components_a))
    result_a = _parse_refund_detail_components({"components": components_a}, "1")
    result_b = _parse_refund_detail_components({"components": components_b}, "1")
    assert result_a["basicRefundInfo"] is not None
    assert result_b["basicRefundInfo"] is not None
    assert result_a["nodeStatusInfo"] is not None
    assert result_b["nodeStatusInfo"] is not None


def test_parse_refund_detail_components_handles_non_dict_components():
    """components 中含非 dict 项时应安全跳过。"""
    inner_data = {"components": ["not-a-dict", None, 123, {"render": "basicRefundInfo", "data": {"refundId": "1"}}]}
    result = _parse_refund_detail_components(inner_data, "1")
    assert result["basicRefundInfo"] is not None


# ============================================================
# basicRefundInfo 解析测试（需求第十一节）
# ============================================================

def test_parse_basic_refund_info_maps_confirmed_fields():
    """basicRefundInfo 字段映射：applyMoney / refundTypeDesc / reasonText / 等。"""
    comp = {
        "render": "basicRefundInfo",
        "data": {
            "applyMoney": "12.50",
            "refundTypeDesc": "我要退款",
            "refundType": "REFUND_TYPE_1",
            "reasonText": "商品与描述不符",
            "goodsStatusDesc": "已发货",
            "refundStatusDesc": "等待卖家处理",
            "csStatusDesc": "客服未介入",
            "postFeeBear": "买家承担",
            "gmtCreatedTime": "2026-07-27 10:00:00",
            "gmtModifiedTime": "2026-07-27 11:00:00",
            "disputeEndTime": None,
            "refundId": "123456",
            "refundStatus": "APPLYING",
            "goodsStatus": "SHIPPED",
            "csStatus": "no",
        },
    }
    result = _parse_basic_refund_info(comp)
    assert result is not None
    assert result["applyMoney"] == Decimal("12.50")
    assert result["refundTypeDesc"] == "我要退款"
    assert result["reasonText"] == "商品与描述不符"
    assert result["goodsStatusDesc"] == "已发货"
    assert result["refundStatusDesc"] == "等待卖家处理"
    assert result["csStatusDesc"] == "客服未介入"
    assert result["postFeeBear"] == "买家承担"
    assert result["refundId"] == "123456"


def test_parse_basic_refund_info_normalizes_logistic_info():
    """basicRefundInfo 物流信息：买家退货 vs 卖家发货明确区分。"""
    comp = {
        "render": "basicRefundInfo",
        "data": {
            "refundId": "1",
            "buyerReturnLogisticInfo": {"companyName": "圆通", "mailNo": "YT1234567890", "consignTime": "2026-07-28 10:00:00"},
            "tradeLogisticInfo": {"companyName": "顺丰", "mailNo": "SF1234567890", "consignTime": "2026-07-27 09:00:00"},
        },
    }
    result = _parse_basic_refund_info(comp)
    # 买家退货物流
    assert result["buyerReturnLogisticInfo"]["companyName"] == "圆通"
    # 卖家发货物流
    assert result["tradeLogisticInfo"]["companyName"] == "顺丰"
    # 物流单号必须脱敏
    assert result["buyerReturnLogisticInfo"]["mailNo"] != "YT1234567890"
    assert "*" in result["buyerReturnLogisticInfo"]["mailNo"]


def test_normalize_logistic_info_handles_non_dict():
    """物流信息非 dict 时返回空结构。"""
    result = _normalize_logistic_info(None)
    assert result == {"companyName": None, "mailNo": None, "consignTime": None}


def test_normalize_logistic_info_masks_mail_no():
    """物流单号必须脱敏。"""
    result = _normalize_logistic_info({"companyName": "顺丰", "mailNo": "SF1234567890123"})
    assert result["companyName"] == "顺丰"
    assert "*" in result["mailNo"]
    assert result["mailNo"] != "SF1234567890123"


# ============================================================
# bottomBar 解析测试（需求第十四节：避免递归跳转）
# ============================================================

def test_parse_bottom_bar_excludes_view_refund_detail_button():
    """bottomBar 必须过滤掉 viewRefundDetail 按钮，避免递归跳转。"""
    comp = {
        "render": "bottomBar",
        "data": {
            "btnList": [
                {"code": "viewRefundDetail", "name": "退款详情", "clickEvent": {"type": "url", "data": {"url": "https://www.goofish.com/r/1"}}},
                {"code": "applyDisputePage", "name": "我要维权", "clickEvent": {"type": "url", "data": {"url": "https://www.goofish.com/dispute/1"}}},
                {"code": "agreeRefundApply", "name": "同意退款", "clickEvent": {"type": "doubleCheck", "data": {"title": "确认", "riskDesc": "不可撤销"}}},
            ]
        },
    }
    result = _parse_bottom_bar(comp, current_refund_id="1")
    codes = [b["code"] for b in result]
    # viewRefundDetail 被过滤（递归跳转）
    assert "viewRefundDetail" not in codes
    # 仅保留 applyDisputePage / agreeRefundApply
    assert "applyDisputePage" in codes
    assert "agreeRefundApply" in codes


def test_parse_bottom_bar_filters_unsafe_url_buttons():
    """URL 不可信的按钮应被过滤。"""
    comp = {
        "render": "bottomBar",
        "data": {
            "btnList": [
                {"code": "applyDisputePage", "name": "维权", "clickEvent": {"type": "url", "data": {"url": "javascript:alert(1)"}}},
                {"code": "agreeRefundApply", "name": "同意", "clickEvent": {"type": "doubleCheck", "data": {}}},
            ]
        },
    }
    result = _parse_bottom_bar(comp, current_refund_id="1")
    codes = [b["code"] for b in result]
    # javascript: URL 被过滤
    assert "applyDisputePage" not in codes
    # doubleCheck 类按钮不受 URL 校验影响
    assert "agreeRefundApply" in codes


def test_parse_bottom_bar_ignores_unknown_click_event_type():
    """未知 clickEvent 类型不动态执行。"""
    comp = {
        "render": "bottomBar",
        "data": {
            "btnList": [
                {"code": "agreeRefundApply", "name": "同意", "clickEvent": {"type": "unknownMtopApi", "data": {"api": "mtop.evil.execute"}}},
            ]
        },
    }
    result = _parse_bottom_bar(comp, current_refund_id="1")
    assert result == []  # 未知类型被过滤


# ============================================================
# service.record 解析测试（需求第六节、第十六节）
# ============================================================

def test_parse_service_record_data_highlights_current_refund_id():
    """当前 refundId 必须高亮，不取第一条冒充当前退款。"""
    inner_data = {
        "refundRecordList": [
            {"refundId": "111", "money": "10.00", "statusDesc": "退款成功"},
            {"refundId": "222", "money": "20.00", "statusDesc": "退款中"},  # 当前
            {"refundId": "333", "money": "30.00", "statusDesc": "退款关闭"},
        ],
        "postageRefundRecordList": [],
    }
    result = _parse_service_record_data(inner_data, current_refund_id="222")
    records = result["refundRecordList"]
    # 当前 refundId 高亮
    current_records = [r for r in records if r["isCurrent"]]
    assert len(current_records) == 1
    assert current_records[0]["refundId"] == "222"
    # 不取第一条冒充当前退款
    assert records[0]["refundId"] == "111"
    assert records[0]["isCurrent"] is False


def test_parse_service_record_data_handles_missing_current_refund():
    """当前 refundId 不在历史列表中时，仍正常展示其他记录。"""
    inner_data = {
        "refundRecordList": [{"refundId": "111", "money": "10.00"}],
        "postageRefundRecordList": [],
    }
    result = _parse_service_record_data(inner_data, current_refund_id="999")
    records = result["refundRecordList"]
    assert len(records) == 1
    assert all(r["isCurrent"] is False for r in records)
    # currentRefundId 仍记录请求的 refundId
    assert result["currentRefundId"] == "999"


def test_parse_service_record_data_handles_empty_postage_list():
    """postageRefundRecordList 为空时正常展示，不报错。"""
    inner_data = {"refundRecordList": [], "postageRefundRecordList": []}
    result = _parse_service_record_data(inner_data, current_refund_id="1")
    assert result["postageRefundRecordList"] == []
    assert result["refundRecordList"] == []


def test_parse_service_record_data_handles_non_list_records():
    """非 list 记录应安全回退为空数组。"""
    inner_data = {"refundRecordList": "not-a-list", "postageRefundRecordList": None}
    result = _parse_service_record_data(inner_data, current_refund_id="1")
    assert result["refundRecordList"] == []
    assert result["postageRefundRecordList"] == []


def test_parse_service_record_data_handles_non_dict_inner():
    """inner_data 非 dict 时安全返回空结构。"""
    result = _parse_service_record_data(None, current_refund_id="1")
    assert result["refundRecordList"] == []
    assert result["postageRefundRecordList"] == []
    assert result["currentRefundId"] == "1"


# ============================================================
# full.info 解析测试（需求第七节）
# ============================================================

def test_parse_full_info_module_completed_string_safety():
    """orderStatusNodeList[].completed 字符串 'true'/'false' 必须安全转换。"""
    module = {
        "merchantCommonData": {"orderId": "123", "itemId": "456", "orderStatus": "已发货"},
        "orderStatusVO": {
            "orderStatusInfo": {"title": "已发货"},
            "orderStatusNodeList": [
                {"completed": "true", "title": "下单", "time": "2026-07-27 10:00:00"},
                {"completed": "false", "title": "付款", "time": "2026-07-27 11:00:00"},
                {"completed": True, "title": "发货", "time": "2026-07-27 12:00:00"},
            ],
        },
    }
    result = _parse_full_info_module(module)
    nodes = result["orderStatusVO"]["orderStatusNodeList"]
    # 字符串 "true" 应被转为 True
    assert nodes[0]["completed"] is True
    # 字符串 "false" 应被转为 False
    assert nodes[1]["completed"] is False
    # 布尔 True 应保持 True
    assert nodes[2]["completed"] is True


def test_parse_full_info_module_item_id_as_string():
    """商品ID/订单ID 必须按字符串处理，避免大整数精度丢失。"""
    module = {
        "merchantCommonData": {
            "itemId": 1234567890123456789,
            "orderId": 9876543210987654321,
        },
    }
    result = _parse_full_info_module(module)
    assert result["merchantCommonData"]["itemId"] == "1234567890123456789"
    assert result["merchantCommonData"]["orderId"] == "9876543210987654321"


def test_parse_full_info_module_buyer_id_as_string():
    """buyerId 必须按字符串处理。"""
    module = {
        "merchantBuyerVO": {"buyerId": 1234567890123456789, "userNick": "买家"},
    }
    result = _parse_full_info_module(module)
    assert result["merchantBuyerVO"]["buyerId"] == "1234567890123456789"


def test_parse_full_info_module_does_not_decrypt_encrypted_phone():
    """encryptedPhone 不应出现在解析结果中（不解密、不展示）。"""
    module = {
        "merchantBuyerVO": {"buyerId": "1", "phone": "138****1234", "encryptedPhone": "encrypted-data"},
    }
    result = _parse_full_info_module(module)
    # phone 字段保留（已脱敏）
    assert result["merchantBuyerVO"]["phone"] == "138****1234"
    # encryptedPhone 不应透传
    assert "encryptedPhone" not in result["merchantBuyerVO"]


def test_parse_full_info_module_handles_non_dict():
    """module 非 dict 时返回 _valid=False。"""
    result = _parse_full_info_module(None)
    assert result["_valid"] is False


def test_parse_full_info_module_refund_fee_not_overriding_apply_money():
    """merchantPriceVO.refundFee 不应覆盖当前退款申请金额（需求第十五节）。

    本测试验证解析层将 refundFee 单独存储，不与 applyMoney 混合。
    """
    module = {
        "merchantPriceVO": {"refundFee": "0", "totalPrice": "100.00"},
    }
    result = _parse_full_info_module(module)
    # refundFee 字段单独存在
    assert result["merchantPriceVO"]["refundFee"] == Decimal("0")
    # 解析结果中不出现 applyMoney（applyMoney 仅来自 refund.detail.basicRefundInfo）
    assert "applyMoney" not in result["merchantPriceVO"]


# ============================================================
# HTML 实体解码测试（需求第十三节）
# ============================================================

def test_decode_html_entities_decodes_yen_symbol():
    """&yen; 应被解码为 ¥（人民币符号）。"""
    assert _decode_html_entities("&yen;10.00") == "¥10.00"


def test_decode_html_entities_decodes_common_entities():
    assert _decode_html_entities("&amp;") == "&"
    assert _decode_html_entities("&lt;") == "<"
    assert _decode_html_entities("&gt;") == ">"
    assert _decode_html_entities("&quot;") == '"'


def test_decode_html_entities_handles_none_and_empty():
    assert _decode_html_entities(None) == ""
    assert _decode_html_entities("") == ""


# ============================================================
# 富文本安全测试（需求第十三节）
# ============================================================

def test_validate_rich_text_link_accepts_goofish_https():
    """富文本链接仅允许 https + 官方域名。"""
    assert _validate_rich_text_link("https://www.goofish.com/help/refund") is not None
    assert _validate_rich_text_link("https://seller.goofish.com/dispute") is not None


def test_validate_rich_text_link_rejects_javascript_protocol():
    assert _validate_rich_text_link("javascript:alert('xss')") is None


def test_validate_rich_text_link_rejects_data_protocol():
    assert _validate_rich_text_link("data:text/html,<script>alert(1)</script>") is None


def test_validate_rich_text_link_rejects_file_protocol():
    assert _validate_rich_text_link("file:///etc/passwd") is None


def test_validate_rich_text_link_rejects_http_protocol():
    """仅允许 https，http 应被拒绝。"""
    assert _validate_rich_text_link("http://www.goofish.com/help") is None


def test_validate_rich_text_link_rejects_untrusted_domain():
    assert _validate_rich_text_link("https://evil.example.com/") is None


def test_safe_style_dict_only_allows_safe_properties():
    """仅允许有限安全样式，未识别样式忽略。"""
    style = "color:red;font-size:14px;background:url(javascript:alert(1));position:fixed;"
    result = _safe_style_dict(style)
    assert "color" in result
    assert "font-size" in result
    # background / position 等不安全样式被忽略
    assert "background" not in result
    assert "position" not in result


def test_safe_style_dict_handles_non_string():
    assert _safe_style_dict(None) == {}
    assert _safe_style_dict(123) == {}


def test_normalize_rich_text_items_decodes_html_entities_in_content():
    """富文本 content 必须解码 HTML 实体后作为纯文本。"""
    items = [{"content": "&yen;10.00 退款", "type": "text"}]
    result = _normalize_rich_text_items(items)
    assert len(result) == 1
    assert result[0]["content"] == "¥10.00 退款"
    assert result[0]["type"] == "text"


def test_normalize_rich_text_items_validates_link_url():
    """富文本 linkUrl 经过协议和官方域名白名单校验。"""
    items = [
        {"content": "官方指南", "type": "link", "linkUrl": "https://www.goofish.com/help/refund"},
        {"content": "恶意链接", "type": "link", "linkUrl": "javascript:alert(1)"},
    ]
    result = _normalize_rich_text_items(items)
    assert len(result) == 2
    assert result[0]["linkUrl"] is not None
    assert result[1]["linkUrl"] is None  # 危险协议被拒绝


def test_normalize_rich_text_items_handles_non_list():
    assert _normalize_rich_text_items(None) == []
    assert _normalize_rich_text_items("not-a-list") == []


# ============================================================
# 凭证图片 URL 校验测试（需求第十二节）
# ============================================================

def test_validate_proof_image_url_accepts_alicdn_https():
    """凭证图片仅允许 https + 官方 CDN 域名。"""
    assert _validate_proof_image_url("https://img.alicdn.com/test.jpg") is not None
    assert _validate_proof_image_url("https://gw.alicdn.com/test.jpg") is not None


def test_validate_proof_image_url_handles_protocol_relative():
    """//cdn.example.com/x.jpg 协议相对 URL 应升级为 https。"""
    result = _validate_proof_image_url("//img.alicdn.com/test.jpg")
    assert result == "https://img.alicdn.com/test.jpg"


def test_validate_proof_image_url_rejects_javascript_protocol():
    assert _validate_proof_image_url("javascript:alert(1)") is None


def test_validate_proof_image_url_rejects_data_protocol():
    assert _validate_proof_image_url("data:image/png;base64,abc") is None


def test_validate_proof_image_url_rejects_http_protocol():
    """仅允许 https，http 应被拒绝。"""
    assert _validate_proof_image_url("http://img.alicdn.com/test.jpg") is None


def test_validate_proof_image_url_rejects_untrusted_domain():
    assert _validate_proof_image_url("https://evil.example.com/test.jpg") is None


def test_normalize_proof_media_list_filters_invalid_urls():
    """非法 URL 直接跳过，不返回 None 项。"""
    items = [
        {"url": "https://img.alicdn.com/1.jpg", "type": "image"},
        {"url": "javascript:alert(1)", "type": "image"},
        {"url": "https://evil.example.com/2.jpg", "type": "image"},
        "not-a-dict",
        None,
    ]
    result = _normalize_proof_media_list(items)
    assert len(result) == 1
    assert result[0]["url"] == "https://img.alicdn.com/1.jpg"


def test_normalize_proof_media_list_handles_non_list():
    assert _normalize_proof_media_list(None) == []
    assert _normalize_proof_media_list("not-a-list") == []


# ============================================================
# progressDetail 解析测试（需求第十节）
# ============================================================

def test_parse_progress_detail_decodes_html_entities_in_tips():
    """progressNodeList[].tips 含 HTML 实体时应安全解码后作为纯文本。"""
    comp = {
        "render": "progressDetail",
        "data": {
            "title": "退款进度",
            "progressNodeList": [
                {
                    "text": "买家申请退款",
                    "timeStr": "2026-07-27 10:00:00",
                    "tips": "退款金额 &yen;10.00",
                    "proofInfoList": [{"url": "https://img.alicdn.com/proof.jpg"}],
                },
            ],
        },
    }
    result = _parse_progress_detail(comp)
    assert result is not None
    assert result["title"] == "退款进度"
    assert result["progressNodeList"][0]["tips"] == "退款金额 ¥10.00"
    # 凭证图片 URL 安全校验
    assert result["progressNodeList"][0]["proofInfoList"][0]["url"] == "https://img.alicdn.com/proof.jpg"


def test_parse_progress_detail_handles_empty_node_list():
    comp = {"render": "progressDetail", "data": {"title": "退款进度"}}
    result = _parse_progress_detail(comp)
    assert result is not None
    assert result["progressNodeList"] == []


# ============================================================
# 缓存键隔离测试（需求第十九节）
# ============================================================

def test_detail_cache_key_isolates_by_account():
    """不同账号不得共享同一订单缓存。"""
    key_a = _detail_cache_key(tenant_id=1, account_id=100, order_id="order-1", refund_id="refund-1")
    key_b = _detail_cache_key(tenant_id=1, account_id=200, order_id="order-1", refund_id="refund-1")
    assert key_a != key_b


def test_detail_cache_key_isolates_by_refund_id():
    """同一订单不同 refundId 必须有不同缓存键。"""
    key_a = _detail_cache_key(tenant_id=1, account_id=100, order_id="order-1", refund_id="refund-1")
    key_b = _detail_cache_key(tenant_id=1, account_id=100, order_id="order-1", refund_id="refund-2")
    assert key_a != key_b


def test_detail_cache_key_isolates_by_tenant():
    """不同租户的相同账号/订单不得共享缓存。"""
    key_a = _detail_cache_key(tenant_id=1, account_id=100, order_id="order-1", refund_id="refund-1")
    key_b = _detail_cache_key(tenant_id=2, account_id=100, order_id="order-1", refund_id="refund-1")
    assert key_a != key_b


# ============================================================
# 缓存读写测试（需求第十九节）
# ============================================================

@pytest.mark.asyncio
async def test_save_and_get_cached_detail_roundtrip():
    """缓存写入后应能读取到。"""
    tenant_id, account_id, order_id, refund_id = 99, 991, "order-cache-1", "refund-cache-1"
    # 先清理可能存在的旧缓存
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    from app.services.refund_service import _save_cached_detail
    data = {
        "serviceRecord": {"status": "ok", "data": {"test": True}},
        "fullInfo": {"status": "ok"},
        "refundDetail": {"status": "ok"},
        "lastSuccessAt": "2026-07-27T10:00:00",
        "partialFailure": False,
    }
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, data)
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    assert cached is not None
    assert cached["serviceRecord"]["data"]["test"] is True

    # 清理
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)


@pytest.mark.asyncio
async def test_invalidate_cached_detail_removes_entry():
    """失效缓存后应读取不到。"""
    tenant_id, account_id, order_id, refund_id = 99, 992, "order-cache-2", "refund-cache-2"
    from app.services.refund_service import _save_cached_detail
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, {"lastSuccessAt": None})
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    assert cached is None


# ============================================================
# 进行中请求去重测试（需求第十九节）
# ============================================================

@pytest.mark.asyncio
async def test_get_or_create_inflight_deduplicates_concurrent_requests():
    """同一详情并发进入只发一组请求。"""
    tenant_id, account_id, order_id, refund_id = 99, 993, "order-inflight-1", "refund-inflight-1"
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    call_count = {"value": 0}

    async def factory():
        call_count["value"] += 1
        await asyncio.sleep(0.05)  # 模拟网络延迟
        return {"value": "result"}

    # 并发发起 5 个相同 key 的请求
    futures = await asyncio.gather(
        _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, factory),
        _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, factory),
        _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, factory),
        _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, factory),
        _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, factory),
    )
    results = await asyncio.gather(*futures)
    # 所有调用应得到相同结果
    for r in results:
        assert r == {"value": "result"}
    # factory 应只被调用 1 次（去重）
    assert call_count["value"] == 1


# ============================================================
# 并行调用 + 局部失败测试（需求第五、二十节）
# ============================================================

@pytest.mark.asyncio
async def test_combined_internal_handles_partial_failure(monkeypatch):
    """某个接口失败时其他区域继续展示。"""
    tenant_id, account_id, order_id, refund_id = 99, 994, "order-partial-1", "refund-partial-1"

    def fake_service_record(account_id, order_id, timeout=20):
        return {"success": True, "ret": ["SUCCESS"], "data": {"data": {"refundRecordList": []}}}

    def fake_full_info(account_id, order_id, timeout=20):
        return {"success": False, "error": "接口超时", "ret": ["FAIL_TIMEOUT"]}

    def fake_refund_detail(account_id, order_id, refund_id, timeout=20):
        return {
            "success": True, "ret": ["SUCCESS"],
            "data": {"data": {"orderId": order_id, "refundId": refund_id, "components": []}},
        }

    monkeypatch.setattr(refund_service, "fetch_refund_service_record", fake_service_record)
    monkeypatch.setattr(refund_service, "fetch_refund_full_info", fake_full_info)
    monkeypatch.setattr(refund_service, "fetch_refund_detail", fake_refund_detail)

    from app.services.refund_service import _fetch_refund_detail_combined_internal
    detail = await _fetch_refund_detail_combined_internal(
        db=None, tenant_id=tenant_id, account_id=account_id,
        order_id=order_id, refund_id=refund_id,
    )

    # serviceRecord 成功
    assert detail["serviceRecord"]["status"] == "ok"
    # fullInfo 失败
    assert detail["fullInfo"]["status"] == "failed"
    # refundDetail 成功
    assert detail["refundDetail"]["status"] == "ok"
    # 部分失败标志为 True
    assert detail["partialFailure"] is True
    # lastSuccessAt 应被设置（任一接口成功即更新）
    assert detail["lastSuccessAt"] is not None


@pytest.mark.asyncio
async def test_combined_internal_handles_all_failure(monkeypatch):
    """三个接口全部失败时，partialFailure=True 且 lastSuccessAt=None。"""
    def fake_failure(*args, **kwargs):
        return {"success": False, "error": "网络错误", "ret": ["FAIL_NETWORK"]}

    monkeypatch.setattr(refund_service, "fetch_refund_service_record", fake_failure)
    monkeypatch.setattr(refund_service, "fetch_refund_full_info", fake_failure)
    monkeypatch.setattr(refund_service, "fetch_refund_detail", fake_failure)

    from app.services.refund_service import _fetch_refund_detail_combined_internal
    detail = await _fetch_refund_detail_combined_internal(
        db=None, tenant_id=99, account_id=995,
        order_id="order-all-fail", refund_id="refund-all-fail",
    )
    assert detail["serviceRecord"]["status"] == "failed"
    assert detail["fullInfo"]["status"] == "failed"
    assert detail["refundDetail"]["status"] == "failed"
    assert detail["partialFailure"] is True
    assert detail["lastSuccessAt"] is None


@pytest.mark.asyncio
async def test_combined_internal_handles_exception_as_failure(monkeypatch):
    """接口抛异常时该接口标记为 failed，不影响其他接口。"""
    def fake_service_raises(*args, **kwargs):
        raise RuntimeError("network error")

    def fake_full_info(account_id, order_id, timeout=20):
        return {"success": True, "ret": ["SUCCESS"], "data": {"module": {}}}

    def fake_refund_detail(account_id, order_id, refund_id, timeout=20):
        return {
            "success": True, "ret": ["SUCCESS"],
            "data": {"data": {"orderId": order_id, "refundId": refund_id, "components": []}},
        }

    monkeypatch.setattr(refund_service, "fetch_refund_service_record", fake_service_raises)
    monkeypatch.setattr(refund_service, "fetch_refund_full_info", fake_full_info)
    monkeypatch.setattr(refund_service, "fetch_refund_detail", fake_refund_detail)

    from app.services.refund_service import _fetch_refund_detail_combined_internal
    detail = await _fetch_refund_detail_combined_internal(
        db=None, tenant_id=99, account_id=996,
        order_id="order-exc", refund_id="refund-exc",
    )
    # 抛异常的接口被标记为 failed
    assert detail["serviceRecord"]["status"] == "failed"
    assert "RuntimeError" in detail["serviceRecord"]["error"]
    # 其他接口正常
    assert detail["fullInfo"]["status"] == "ok"
    assert detail["refundDetail"]["status"] == "ok"


# ============================================================
# 单接口重试测试（需求第二十节）
# ============================================================

@pytest.mark.asyncio
async def test_combined_internal_only_calls_specified_api(monkeypatch):
    """retry_refund_detail_api 只调用指定失败接口，不重新请求成功接口。"""
    called_apis = []

    def fake_service_record(*args, **kwargs):
        called_apis.append("service_record")
        return {"success": True, "ret": ["SUCCESS"], "data": {"data": {}}}

    def fake_full_info(*args, **kwargs):
        called_apis.append("full_info")
        return {"success": True, "ret": ["SUCCESS"], "data": {"module": {}}}

    def fake_refund_detail(*args, **kwargs):
        called_apis.append("refund_detail")
        return {"success": True, "ret": ["SUCCESS"], "data": {"data": {"orderId": "x", "refundId": "y", "components": []}}}

    monkeypatch.setattr(refund_service, "fetch_refund_service_record", fake_service_record)
    monkeypatch.setattr(refund_service, "fetch_refund_full_info", fake_full_info)
    monkeypatch.setattr(refund_service, "fetch_refund_detail", fake_refund_detail)

    from app.services.refund_service import _fetch_refund_detail_combined_internal
    # 仅重试 full_info
    detail = await _fetch_refund_detail_combined_internal(
        db=None, tenant_id=99, account_id=997,
        order_id="x", refund_id="y",
        apis_to_call={"full_info"},
    )
    # 只调用了 full_info，其他接口被 skipped
    assert called_apis == ["full_info"]
    assert detail["serviceRecord"]["status"] == "skipped"
    assert detail["fullInfo"]["status"] == "ok"
    assert detail["refundDetail"]["status"] == "skipped"


# ============================================================
# 错误分类测试（需求第二节、第十三节）
# ============================================================

def test_classify_mtop_error_auth_expired_for_token_expired():
    """FAIL_SYS_TOKEN_EXOIRED 应分类为 AUTH_EXPIRED。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error(["FAIL_SYS_TOKEN_EXOIRED::令牌过期"]) == "AUTH_EXPIRED"


def test_classify_mtop_error_auth_expired_for_token_empty():
    """FAIL_SYS_TOKEN_EMPTY 应分类为 AUTH_EXPIRED。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error(["FAIL_SYS_TOKEN_EMPTY::令牌为空"]) == "AUTH_EXPIRED"


def test_classify_mtop_error_network_timeout():
    """请求超时应分类为 NETWORK_TIMEOUT。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error([], "请求超时") == "NETWORK_TIMEOUT"


def test_classify_mtop_error_network_error_for_unavailable():
    """闲鱼接口请求失败应分类为 NETWORK_ERROR。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error([], "闲鱼接口请求失败，请稍后重试") == "NETWORK_ERROR"


def test_classify_mtop_error_mtop_ret_failure():
    """ret 含 FAIL_ 但非 token 过期应分类为 MTOP_RET_FAILURE。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error(["FAIL_SYS_USER_VALIDATE::Baxia验证"]) == "MTOP_RET_FAILURE"


def test_classify_mtop_error_unknown_when_no_info():
    """无 ret 无 error 应分类为 UNKNOWN_ERROR。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error(None, None) == "UNKNOWN_ERROR"


def test_classify_mtop_error_handles_string_ret():
    """ret 为字符串（非列表）时也应能正确分类。"""
    from app.services.refund_service import _classify_mtop_error
    assert _classify_mtop_error("FAIL_SYS_USER_VALIDATE::Baxia验证") == "MTOP_RET_FAILURE"


# ============================================================
# 失败结果不缓存测试（需求第十一节）
# ============================================================

@pytest.mark.asyncio
async def test_save_cached_detail_skips_all_failed_result():
    """全部接口 failed 的 detail 不应被缓存。"""
    from app.services.refund_service import _save_cached_detail, _get_cached_detail, _invalidate_cached_detail
    tenant_id, account_id, order_id, refund_id = 99, 980, "order-no-cache-1", "refund-no-cache-1"
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    all_failed_detail = {
        "serviceRecord": {"status": "failed", "data": None, "error": "失败1"},
        "fullInfo": {"status": "failed", "data": None, "error": "失败2"},
        "refundDetail": {"status": "failed", "data": None, "error": "失败3"},
        "lastSuccessAt": None,
        "partialFailure": True,
    }
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, all_failed_detail)
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    assert cached is None, "全失败结果不应被缓存"


@pytest.mark.asyncio
async def test_save_cached_detail_skips_all_skipped_result():
    """全部接口 skipped 的 detail 不应被缓存。"""
    from app.services.refund_service import _save_cached_detail, _get_cached_detail, _invalidate_cached_detail
    tenant_id, account_id, order_id, refund_id = 99, 981, "order-no-cache-2", "refund-no-cache-2"
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    all_skipped_detail = {
        "serviceRecord": {"status": "skipped", "data": None, "error": None},
        "fullInfo": {"status": "skipped", "data": None, "error": None},
        "refundDetail": {"status": "skipped", "data": None, "error": None},
        "lastSuccessAt": None,
        "partialFailure": False,
    }
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, all_skipped_detail)
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    assert cached is None, "全 skipped 结果不应被缓存"


@pytest.mark.asyncio
async def test_save_cached_detail_saves_partial_success():
    """部分接口成功的 detail 应被缓存。"""
    from app.services.refund_service import _save_cached_detail, _get_cached_detail, _invalidate_cached_detail
    tenant_id, account_id, order_id, refund_id = 99, 982, "order-cache-partial", "refund-cache-partial"
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    partial_detail = {
        "serviceRecord": {"status": "ok", "data": {"x": 1}},
        "fullInfo": {"status": "failed", "data": None, "error": "超时"},
        "refundDetail": {"status": "ok", "data": {"y": 2}},
        "lastSuccessAt": "2026-07-28T10:00:00",
        "partialFailure": True,
    }
    await _save_cached_detail(tenant_id, account_id, order_id, refund_id, partial_detail)
    cached = await _get_cached_detail(tenant_id, account_id, order_id, refund_id)
    assert cached is not None, "部分成功结果应被缓存"
    assert cached["serviceRecord"]["status"] == "ok"


# ============================================================
# errorCode 透传测试（需求第十三节）
# ============================================================

@pytest.mark.asyncio
async def test_combined_internal_propagates_error_code_on_failure(monkeypatch):
    """接口失败时 detail 块应包含 errorCode 字段供前端展示。"""
    def fake_service_record(*args, **kwargs):
        return {
            "success": False, "error": "FAIL_SYS_TOKEN_EXOIRED",
            "ret": ["FAIL_SYS_TOKEN_EXOIRED::令牌过期"],
            "errorCode": "AUTH_EXPIRED",
        }

    def fake_full_info(*args, **kwargs):
        return {"success": False, "error": "请求超时", "ret": [], "errorCode": "NETWORK_TIMEOUT"}

    def fake_refund_detail(*args, **kwargs):
        return {"success": False, "error": "Baxia", "ret": ["FAIL_SYS_USER_VALIDATE::Baxia"], "errorCode": "MTOP_RET_FAILURE"}

    monkeypatch.setattr(refund_service, "fetch_refund_service_record", fake_service_record)
    monkeypatch.setattr(refund_service, "fetch_refund_full_info", fake_full_info)
    monkeypatch.setattr(refund_service, "fetch_refund_detail", fake_refund_detail)

    from app.services.refund_service import _fetch_refund_detail_combined_internal
    detail = await _fetch_refund_detail_combined_internal(
        db=None, tenant_id=99, account_id=990,
        order_id="order-err-code", refund_id="refund-err-code",
    )
    # 三个接口都失败，且各自透传 errorCode
    assert detail["serviceRecord"]["status"] == "failed"
    assert detail["serviceRecord"]["errorCode"] == "AUTH_EXPIRED"
    assert detail["fullInfo"]["status"] == "failed"
    assert detail["fullInfo"]["errorCode"] == "NETWORK_TIMEOUT"
    assert detail["refundDetail"]["status"] == "failed"
    assert detail["refundDetail"]["errorCode"] == "MTOP_RET_FAILURE"


@pytest.mark.asyncio
async def test_combined_internal_marks_id_consistency_error(monkeypatch):
    """响应 orderId/refundId 与请求不一致时应标记 ID_CONSISTENCY_ERROR。"""
    def fake_service_record(*args, **kwargs):
        return {"success": True, "ret": ["SUCCESS"], "data": {"data": {}}}

    def fake_full_info(*args, **kwargs):
        # module.merchantCommonData.orderId 与请求不一致
        return {
            "success": True, "ret": ["SUCCESS"],
            "data": {"module": {"merchantCommonData": {"orderId": "WRONG_ORDER_ID"}}},
        }

    def fake_refund_detail(*args, **kwargs):
        return {
            "success": True, "ret": ["SUCCESS"],
            "data": {"data": {"orderId": "WRONG", "refundId": "WRONG_R", "components": []}},
        }

    monkeypatch.setattr(refund_service, "fetch_refund_service_record", fake_service_record)
    monkeypatch.setattr(refund_service, "fetch_refund_full_info", fake_full_info)
    monkeypatch.setattr(refund_service, "fetch_refund_detail", fake_refund_detail)

    from app.services.refund_service import _fetch_refund_detail_combined_internal
    detail = await _fetch_refund_detail_combined_internal(
        db=None, tenant_id=99, account_id=991,
        order_id="EXPECTED_ORDER", refund_id="EXPECTED_REFUND",
    )
    # fullInfo 一致性校验失败
    assert detail["fullInfo"]["status"] == "failed"
    assert detail["fullInfo"]["errorCode"] == "ID_CONSISTENCY_ERROR"
    # refundDetail 一致性校验失败
    assert detail["refundDetail"]["status"] == "failed"
    assert detail["refundDetail"]["errorCode"] == "ID_CONSISTENCY_ERROR"


# ============================================================
# 进行中请求失败后清理测试（需求第十一节）
# ============================================================

@pytest.mark.asyncio
async def test_inflight_cleared_after_failure():
    """请求失败后进行中映射应被清理，下次请求能发起新请求。"""
    from app.services.refund_service import (
        _get_or_create_inflight,
        _invalidate_cached_detail,
        _refund_detail_inflight,
    )
    tenant_id, account_id, order_id, refund_id = 99, 983, "order-inflight-fail", "refund-inflight-fail"
    await _invalidate_cached_detail(tenant_id, account_id, order_id, refund_id)

    call_count = {"value": 0}

    async def failing_factory():
        call_count["value"] += 1
        raise RuntimeError("network error")

    # 第一次请求：失败
    fut1 = await _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, failing_factory)
    with pytest.raises(RuntimeError):
        await fut1

    # 进行中映射应已清理
    key = _detail_cache_key(tenant_id, account_id, order_id, refund_id)
    assert key not in _refund_detail_inflight, "失败后进行中映射应被清理"

    # 第二次请求：应能发起新请求（不被旧失败 future 阻塞）
    async def success_factory():
        call_count["value"] += 1
        return {"value": "ok"}

    fut2 = await _get_or_create_inflight(tenant_id, account_id, order_id, refund_id, success_factory)
    result = await fut2
    assert result == {"value": "ok"}
    # factory 应被调用 2 次（第一次失败 + 第二次成功）
    assert call_count["value"] == 2
