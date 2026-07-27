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
"""
from __future__ import annotations

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
    REFUND_LIST_API,
    SUPPORTED_CATEGORIES,
    TRUSTED_EXTERNAL_HOSTS,
    _extract_refund_fields,
    _mask_buyer_nick,
    _mask_mail_no,
    _parse_bool_string,
    _safe_decimal,
    _safe_int,
    _safe_url_for_open,
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
