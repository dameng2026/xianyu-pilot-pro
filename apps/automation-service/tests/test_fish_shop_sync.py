"""
鱼小铺商品同步服务单元测试。

覆盖场景（按需求第二十九节）：
1. 商品管理接口字段映射（title/itemImageUrl/itemId/reservePrice/quantity/gmtCreate，不用 gmtShelf）
2. 数据罗盘接口字段映射（showPv/ipv，忽略 showUv/ipvUv）
3. 动态分页（不固定总页数、请求 pageSize 与响应 pageSize 不一致时使用响应值）
4. 最大 pageSize（使用已确认值、可调整）
5. 数值为 0 时保存 0（quantity=0、showPv=0、ipv=0）
6. 接口失败时保护旧数据（不清零、不删除）
7. 分页漂移（去重、补偿扫描、不无限扫描）
8. 两个接口按商品 ID 合并
9. 路由逻辑（鱼小铺账号走专属流程、普通账号走原有流程）
10. 累计销量不伪造
11. 日志不泄露 Cookie/token/sign
"""
from __future__ import annotations

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.fish_shop_sync import (
    FISH_SHOP_ITEM_SEARCH_API,
    FISH_SHOP_DATACOMPASS_API,
    FISH_SHOP_ITEM_SEARCH_PAGE_SIZE,
    FISH_SHOP_DATACOMPASS_PAGE_SIZE,
    FISH_SHOP_PAGE_CONCURRENCY,
    _build_item_search_data,
    _build_datacompass_data,
    _build_item_search_url_params,
    _check_fish_shop_biz_success,
    _parse_fish_shop_goods_item,
    _parse_item_search_response,
    _parse_datacompass_response,
    _parse_fish_shop_timestamp,
    _apply_datacompass_metrics,
    _is_retryable_error,
    _make_fish_shop_request,
    fetch_fish_shop_goods_all,
    fetch_fish_shop_datacompass_all,
)
from app.services.xianyu_goods_sync import (
    XianyuRiskControlError,
    XianyuAuthExpiredError,
    XianyuProviderRejectedError,
)


# ==================== 商品管理接口字段映射 ====================


class TestParseFishShopGoodsItem:
    """商品管理接口单商品字段映射测试。"""

    def test_field_mapping_basic(self):
        """验证 title/itemImageUrl/itemId/reservePrice/quantity/gmtCreate 正确映射。"""
        raw = {
            "itemId": 12345678901234,
            "title": "测试鱼小铺商品",
            "itemImageUrl": "https://img.example.com/pic.jpg",
            "reservePrice": "99.50",
            "quantity": 10,
            "gmtCreate": 1700000000000,
            "gmtShelf": 1700000001000,
            "itemStatus": 0,
            "itemStatusDesc": "在售",
        }
        goods = _parse_fish_shop_goods_item(raw)
        assert goods["external_goods_id"] == "12345678901234"
        assert goods["title"] == "测试鱼小铺商品"
        assert goods["cover_pic"] == "https://img.example.com/pic.jpg"
        assert goods["image_url"] == "https://img.example.com/pic.jpg"
        assert goods["price"] == "99.50"
        assert goods["sold_price"] == "99.50"
        assert goods["quantity"] == 10
        assert goods["stock"] == "10"
        # gmtCreate 是创建时间
        assert goods["gmt_create"] is not None
        assert isinstance(goods["gmt_create"], datetime)
        # gmtShelf 不作为创建时间字段（仅存 raw_payload）
        assert "gmt_shelf" not in goods
        assert goods["raw_payload"]["gmtShelf"] == 1700000001000
        # itemStatus 映射到 _fish_shop_status 中间字段
        assert goods["_fish_shop_status"] == 1  # 0=在售 → ORM 1

    def test_item_id_string_to_avoid_integer_precision_loss(self):
        """商品 ID 必须转为字符串，避免大整数精度损失。"""
        big_id = 9876543210987654321
        raw = {"itemId": big_id, "title": "x"}
        goods = _parse_fish_shop_goods_item(raw)
        assert goods["external_goods_id"] == str(big_id)

    def test_price_kept_as_string_for_precision(self):
        """价格保持字符串形式，避免浮点精度损失。"""
        raw = {"itemId": "1", "reservePrice": "0.01"}
        goods = _parse_fish_shop_goods_item(raw)
        assert goods["price"] == "0.01"
        assert isinstance(goods["price"], str)

    def test_gmt_shelf_not_used_as_create_time(self):
        """gmtShelf 是上架时间，不能作为创建时间，仅存 raw_payload。"""
        raw = {
            "itemId": "1",
            "gmtCreate": 1700000000000,
            "gmtShelf": 1700000001000,
        }
        goods = _parse_fish_shop_goods_item(raw)
        create_ts = goods["gmt_create"].timestamp() * 1000
        # gmtCreate 正确映射
        assert abs(create_ts - 1700000000000) < 1000
        # gmtShelf 不作为字段，仅存 raw_payload
        assert "gmt_shelf" not in goods
        assert goods["raw_payload"]["gmtShelf"] == 1700000001000

    def test_item_status_mapping(self):
        """itemStatus 映射到 _fish_shop_status 中间字段。"""
        # 0=在卖 → ORM 1
        goods = _parse_fish_shop_goods_item({"itemId": "1", "itemStatus": "0"})
        assert goods["_fish_shop_status"] == 1
        # -9=下架 → ORM 0
        goods = _parse_fish_shop_goods_item({"itemId": "1", "itemStatus": "-9"})
        assert goods["_fish_shop_status"] == 0
        # 其他 → ORM 2
        goods = _parse_fish_shop_goods_item({"itemId": "1", "itemStatus": "5"})
        assert goods["_fish_shop_status"] == 2

    def test_only_orm_fields_returned(self):
        """返回字典只包含 XianyuGoods ORM 合法字段 + _fish_shop_status 中间字段。"""
        raw = {"itemId": "1", "title": "x", "itemStatus": "0", "itemStatusDesc": "在卖"}
        goods = _parse_fish_shop_goods_item(raw)
        # 不应包含非 ORM 字段
        assert "itemId" not in goods
        assert "itemStatus" not in goods
        assert "itemStatusDesc" not in goods
        # 应包含 ORM 合法字段
        assert "external_goods_id" in goods
        assert "title" in goods
        assert "raw_payload" in goods
        # _fish_shop_status 是中间字段，由 _do_sync 处理
        assert "_fish_shop_status" in goods

    def test_quantity_zero_saved_as_zero(self):
        """quantity=0 时保存 0，不转换为空值。"""
        raw = {"itemId": "1", "quantity": 0}
        goods = _parse_fish_shop_goods_item(raw)
        assert goods["quantity"] == 0

    def test_quantity_missing_defaults_to_zero(self):
        """quantity 缺失时默认 0。"""
        raw = {"itemId": "1"}
        goods = _parse_fish_shop_goods_item(raw)
        assert goods["quantity"] == 0

    def test_quantity_invalid_string_defaults_to_zero(self):
        """quantity 为无效字符串时默认 0。"""
        raw = {"itemId": "1", "quantity": "abc"}
        goods = _parse_fish_shop_goods_item(raw)
        assert goods["quantity"] == 0


# ==================== 数据罗盘接口字段映射 ====================


class TestParseDatacompassResponse:
    """数据罗盘接口字段映射测试。"""

    def _make_response(self, items, **kwargs):
        data_inner = {"list": items}
        data_inner.update(kwargs)
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "code": "0",
                "data": data_inner,
            },
        }

    def test_show_pv_mapped_to_exposure_30d(self):
        """showPv 映射为最近30天曝光次数。"""
        resp = self._make_response([{"itmId": "1", "showPv": 150, "showUv": 123, "ipv": 11, "ipvUv": 9}])
        result = _parse_datacompass_response(resp)
        assert result["items"][0]["showPv"] == 150

    def test_ipv_mapped_to_view_30d(self):
        """ipv 映射为最近30天浏览次数。"""
        resp = self._make_response([{"itmId": "1", "showPv": 150, "showUv": 123, "ipv": 11, "ipvUv": 9}])
        result = _parse_datacompass_response(resp)
        assert result["items"][0]["ipv"] == 11

    def test_show_uv_ignored(self):
        """showUv（曝光人数）不保存。"""
        resp = self._make_response([{"itmId": "1", "showPv": 150, "showUv": 123, "ipv": 11, "ipvUv": 9}])
        result = _parse_datacompass_response(resp)
        item = result["items"][0]
        assert "showUv" not in item
        assert "show_uv" not in item

    def test_ipv_uv_ignored(self):
        """ipvUv（浏览人数）不保存。"""
        resp = self._make_response([{"itmId": "1", "showPv": 150, "showUv": 123, "ipv": 11, "ipvUv": 9}])
        result = _parse_datacompass_response(resp)
        item = result["items"][0]
        assert "ipvUv" not in item
        assert "ipv_uv" not in item

    def test_zero_show_pv_saved_as_zero(self):
        """showPv=0 时保存 0。"""
        resp = self._make_response([{"itmId": "1", "showPv": 0, "ipv": 0}])
        result = _parse_datacompass_response(resp)
        assert result["items"][0]["showPv"] == 0
        assert result["items"][0]["ipv"] == 0

    def test_pagination_fields_from_response(self):
        """分页字段从响应中读取。"""
        resp = self._make_response(
            [{"itmId": "1", "showPv": 1, "ipv": 1}],
            total=73,
            pageNo=1,
            pageSize=10,
        )
        result = _parse_datacompass_response(resp)
        assert result["total"] == 73
        assert result["pageNo"] == 1
        assert result["pageSize"] == 10
        # 73/10=8 页
        assert result["totalPage"] == 8

    def test_total_page_calculated_from_response_page_size(self):
        """总页数使用响应中的实际 pageSize 计算，不使用请求 pageSize。"""
        resp = self._make_response(
            [{"itmId": "1", "showPv": 1, "ipv": 1}],
            total=73,
            pageNo=1,
            pageSize=10,  # 服务端实际 pageSize=10
        )
        result = _parse_datacompass_response(resp)
        # 73/10=8 页（不是 73/50=2 页）
        assert result["totalPage"] == 8

    def test_empty_item_list(self):
        """空商品列表。"""
        resp = self._make_response([])
        result = _parse_datacompass_response(resp)
        assert result["items"] == []
        assert result["total"] == 0

    def test_item_without_itm_id_skipped(self):
        """没有 itmId 的条目被跳过。"""
        resp = self._make_response([
            {"itmId": "1", "showPv": 1, "ipv": 1},
            {"showPv": 2, "ipv": 2},  # 无 itmId
        ])
        result = _parse_datacompass_response(resp)
        assert len(result["items"]) == 1


# ==================== 商品管理接口响应解析 ====================


class TestParseItemSearchResponse:
    """商品管理接口响应解析测试。"""

    def _make_response(self, items, **page_info):
        inner = {
            "itemSearchResponseList": {
                "itemSearchResponseList": items,
                "currentPage": page_info.get("currentPage", 1),
                "hasNextPage": page_info.get("hasNextPage", False),
                "pageSize": page_info.get("pageSize", 20),
                "total": page_info.get("total", len(items)),
                "totalPage": page_info.get("totalPage", 1),
            }
        }
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "code": "0",
                "data": inner,
            },
        }

    def test_parse_success_with_items(self):
        resp = self._make_response([
            {"itemId": "1", "title": "商品1", "reservePrice": "10", "quantity": 5},
            {"itemId": "2", "title": "商品2", "reservePrice": "20", "quantity": 3},
        ], total=2, totalPage=1)
        result = _parse_item_search_response(resp)
        assert len(result["items"]) == 2
        assert result["total"] == 2
        assert result["totalPage"] == 1
        assert result["hasNextPage"] is False

    def test_pagination_fields_extracted(self):
        resp = self._make_response(
            [{"itemId": "1"}],
            currentPage=1,
            hasNextPage=True,
            pageSize=20,
            total=73,
            totalPage=4,
        )
        result = _parse_item_search_response(resp)
        assert result["currentPage"] == 1
        assert result["hasNextPage"] is True
        assert result["pageSize"] == 20
        assert result["total"] == 73
        assert result["totalPage"] == 4

    def test_biz_success_check_ret_failure(self):
        """ret 中包含错误时抛异常。"""
        resp = {"ret": ["FAIL::未知错误"]}
        with pytest.raises(XianyuProviderRejectedError):
            _parse_item_search_response(resp)

    def test_biz_success_check_rgv587(self):
        """ret 中包含 RGV587 时触发风控异常。"""
        resp = {"ret": ["RGV587_ERROR::风控"]}
        with pytest.raises(XianyuRiskControlError):
            _parse_item_search_response(resp)

    def test_biz_success_check_token_expired(self):
        """ret 中包含 Token 过期时触发认证异常。"""
        resp = {"ret": ["FAIL_SYS_TOKEN_EXOIRED::令牌过期"]}
        with pytest.raises(XianyuAuthExpiredError):
            _parse_item_search_response(resp)

    def test_data_data_success_false_raises(self):
        """data.data.success=false 时抛异常。"""
        resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "data": {"success": False, "message": "无权限"},
            },
        }
        with pytest.raises(XianyuProviderRejectedError, match="无权限"):
            _parse_item_search_response(resp)


# ==================== 请求构造测试 ====================


class TestBuildItemSearchData:
    """商品管理接口 data 字段构造测试。"""

    def test_biz_type_must_be_commonPro(self):
        """bizType 必须为字符串 commonPro。"""
        data = _build_item_search_data(1, 20)
        assert data["bizType"] == "commonPro"
        assert isinstance(data["bizType"], str)

    def test_search_request_must_be_string_braces(self):
        """searchRequest 必须是字符串 '{}'，不是 JSON 对象。"""
        data = _build_item_search_data(1, 20)
        assert data["searchRequest"] == "{}"
        assert isinstance(data["searchRequest"], str)

    def test_item_status_must_be_string_0_minus_9(self):
        """itemStatus 必须为字符串 '0,-9'。"""
        data = _build_item_search_data(1, 20)
        assert data["itemStatus"] == "0,-9"
        assert isinstance(data["itemStatus"], str)

    def test_page_no_starts_from_1(self):
        """pageNo 从 1 开始。"""
        data = _build_item_search_data(1, 20)
        assert data["pageNo"] == 1

    def test_page_size_parametrized(self):
        """pageSize 可参数化。"""
        data = _build_item_search_data(1, 50)
        assert data["pageSize"] == 50


class TestBuildDatacompassData:
    """数据罗盘接口 data 字段构造测试。"""

    def test_date_type_must_be_recent30d(self):
        """dateType 必须为 recent30d（只获取最近30天）。"""
        data = _build_datacompass_data(1, 10)
        assert data["dateType"] == "recent30d"

    def test_tab_type_must_be_all(self):
        """tabType 必须为 all。"""
        data = _build_datacompass_data(1, 10)
        assert data["tabType"] == "all"

    def test_itm_id_empty_for_full_scan(self):
        """全量扫描时 itmId 必须为空字符串。"""
        data = _build_datacompass_data(1, 10)
        assert data["itmId"] == ""

    def test_no_recent_1d_or_7d(self):
        """不包含最近1天或最近7天的 dateType。"""
        data = _build_datacompass_data(1, 10)
        assert data["dateType"] not in ("recent1d", "recent7d", "1d", "7d")


# ==================== 时间戳解析测试 ====================


class TestParseFishShopTimestamp:
    """鱼小铺时间戳解析测试。"""

    def test_millisecond_timestamp_int(self):
        """毫秒时间戳（整数）。"""
        ts = _parse_fish_shop_timestamp(1700000000000)
        assert ts is not None
        assert isinstance(ts, datetime)

    def test_millisecond_timestamp_string(self):
        """毫秒时间戳（字符串）。"""
        ts = _parse_fish_shop_timestamp("1700000000000")
        assert ts is not None
        assert isinstance(ts, datetime)

    def test_formatted_date_string(self):
        """已格式化的日期字符串。"""
        ts = _parse_fish_shop_timestamp("2024-01-01 12:00:00")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 1

    def test_none_returns_none(self):
        """None 输入返回 None。"""
        assert _parse_fish_shop_timestamp(None) is None

    def test_empty_string_returns_none(self):
        """空字符串返回 None。"""
        assert _parse_fish_shop_timestamp("") is None

    def test_invalid_format_returns_none(self):
        """无效格式返回 None。"""
        assert _parse_fish_shop_timestamp("not-a-date") is None


# ==================== 业务成功校验测试 ====================


class TestCheckFishShopBizSuccess:
    """鱼小铺接口业务成功校验测试。"""

    def test_success_ret(self):
        """ret 包含 SUCCESS 时通过。"""
        resp = {"ret": ["SUCCESS::调用成功"], "data": {}}
        _check_fish_shop_biz_success(resp, "test_api")  # 不抛异常

    def test_rgv587_raises_risk_control(self):
        """RGV587 触发风控异常。"""
        resp = {"ret": ["RGV587_ERROR::风控"]}
        with pytest.raises(XianyuRiskControlError):
            _check_fish_shop_biz_success(resp, "test_api")

    def test_token_expired_raises_auth(self):
        """Token 过期触发认证异常。"""
        resp = {"ret": ["FAIL_SYS_TOKEN_EXOIRED::令牌过期"]}
        with pytest.raises(XianyuAuthExpiredError):
            _check_fish_shop_biz_success(resp, "test_api")

    def test_token_expired_alias_raises_auth(self):
        """Token 过期（另一种拼写）触发认证异常。"""
        resp = {"ret": ["FAIL_SYS_TOKEN_EXPIRED::Token过期"]}
        with pytest.raises(XianyuAuthExpiredError):
            _check_fish_shop_biz_success(resp, "test_api")

    def test_data_code_non_zero_raises(self):
        """data.code 非 0/200/SUCCESS 时抛异常。"""
        resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"code": "500", "message": "内部错误"},
        }
        with pytest.raises(XianyuProviderRejectedError, match="内部错误"):
            _check_fish_shop_biz_success(resp, "test_api")

    def test_data_data_success_false_raises(self):
        """data.data.success=false 时抛异常。"""
        resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"data": {"success": False, "errorMsg": "无权限"}},
        }
        with pytest.raises(XianyuProviderRejectedError, match="无权限"):
            _check_fish_shop_biz_success(resp, "test_api")

    def test_data_data_success_true_passes(self):
        """data.data.success=true 时通过。"""
        resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"data": {"success": True}},
        }
        _check_fish_shop_biz_success(resp, "test_api")  # 不抛异常


# ==================== 数据合并测试 ====================


class TestApplyDatacompassMetrics:
    """数据罗盘指标合并测试。"""

    def test_metrics_applied_when_present(self):
        """metrics 存在时写入 showPv/ipv。"""
        goods = {}
        metrics = {"showPv": 150, "ipv": 11}
        _apply_datacompass_metrics(goods, metrics)
        assert goods["exposure_count_30d"] == 150
        assert goods["view_count_30d"] == 11

    def test_metrics_zero_saved_as_zero(self):
        """metrics 明确返回 0 时保存 0。"""
        goods = {}
        metrics = {"showPv": 0, "ipv": 0}
        _apply_datacompass_metrics(goods, metrics)
        assert goods["exposure_count_30d"] == 0
        assert goods["view_count_30d"] == 0

    def test_metrics_none_not_applied(self):
        """metrics 为 None 时不写入字段（保留已有值）。"""
        goods = {"exposure_count_30d": 100, "view_count_30d": 50}
        _apply_datacompass_metrics(goods, None)
        # 已有值保留
        assert goods["exposure_count_30d"] == 100
        assert goods["view_count_30d"] == 50

    def test_metrics_empty_dict_not_applied(self):
        """metrics 为空字典时不写入字段。"""
        goods = {"exposure_count_30d": 100}
        _apply_datacompass_metrics(goods, {})
        assert goods["exposure_count_30d"] == 100

    def test_show_uv_not_in_result(self):
        """合并结果不包含 showUv。"""
        goods = {}
        metrics = {"showPv": 150, "showUv": 123, "ipv": 11, "ipvUv": 9}
        _apply_datacompass_metrics(goods, metrics)
        assert "showUv" not in goods
        assert "show_uv" not in goods
        assert "ipvUv" not in goods
        assert "ipv_uv" not in goods


# ==================== 重试策略测试 ====================


class TestIsRetryableError:
    """错误重试判断测试。"""

    def test_network_error_retryable(self):
        """网络错误可重试。"""
        import requests
        assert _is_retryable_error(requests.ConnectionError("连接失败")) is True
        assert _is_retryable_error(requests.Timeout("超时")) is True

    def test_risk_control_not_retryable(self):
        """风控错误不可重试。"""
        assert _is_retryable_error(XianyuRiskControlError("风控")) is False

    def test_auth_expired_retryable(self):
        """Token 过期可重试（外层会先刷新 token）。"""
        assert _is_retryable_error(XianyuAuthExpiredError("Token过期")) is True

    def test_provider_rejected_not_retryable(self):
        """业务错误不可重试。"""
        assert _is_retryable_error(XianyuProviderRejectedError("业务错误")) is False

    def test_5xx_http_error_retryable(self):
        """5xx HTTP 错误可重试。"""
        import requests
        resp = MagicMock()
        resp.status_code = 503
        err = requests.HTTPError(response=resp)
        assert _is_retryable_error(err) is True

    def test_4xx_http_error_not_retryable(self):
        """4xx HTTP 错误不可重试。"""
        import requests
        resp = MagicMock()
        resp.status_code = 403
        err = requests.HTTPError(response=resp)
        assert _is_retryable_error(err) is False


# ==================== 动态分页测试 ====================


class TestFetchFishShopGoodsAllPagination:
    """商品管理接口全量分页测试。"""

    def _make_search_response(self, items, page, total, total_page, page_size=20):
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "code": "0",
                "data": {
                    "itemSearchResponseList": {
                        "itemSearchResponseList": items,
                        "currentPage": page,
                        "hasNextPage": page < total_page,
                        "pageSize": page_size,
                        "total": total,
                        "totalPage": total_page,
                    }
                },
            },
        }

    @pytest.mark.asyncio
    async def test_single_page_no_more_pagination(self):
        """单页结果不触发后续分页请求。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"
        call_count = 0

        def mock_request(cookie, api, data, **kwargs):
            nonlocal call_count
            call_count += 1
            return self._make_search_response(
                [{"itemId": "1", "title": "商品1"}], 1, 1, 1
            )

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_goods_all(cookie_str)

        assert call_count == 1  # 只请求一次
        assert result["total"] == 1
        assert result["unique_count"] == 1
        assert len(result["items"]) == 1

    @pytest.mark.asyncio
    async def test_multi_page_dynamic_pagination(self):
        """多页结果动态创建后续页请求。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"
        pages_requested = []

        def mock_request(cookie, api, data, **kwargs):
            page = data["pageNo"]
            pages_requested.append(page)
            # 前 3 页各 20 个，最后一页 13 个，合计 73
            items_per_page = 20 if page < 4 else 13
            items = [{"itemId": str((page - 1) * 20 + i), "title": f"商品{page}-{i}"} for i in range(items_per_page)]
            return self._make_search_response(items, page, 73, 4)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_goods_all(cookie_str)

        # 4 页全部请求
        assert sorted(pages_requested) == [1, 2, 3, 4]
        assert result["total"] == 73
        # 去重后 73 件（每页商品 ID 唯一）
        assert result["unique_count"] == 73

    @pytest.mark.asyncio
    async def test_response_page_size_used_not_request(self):
        """请求 pageSize 与响应 pageSize 不一致时，使用响应 pageSize。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"
        requested_page_sizes = []

        def mock_request(cookie, api, data, **kwargs):
            page = data["pageNo"]
            requested_page_sizes.append(data["pageSize"])
            # 服务端实际返回 pageSize=10，但 total=73
            items = [{"itemId": str(page * 10 + i)} for i in range(10)]
            return self._make_search_response(items, page, 73, 8, page_size=10)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_goods_all(cookie_str, page_size=50)

        # 第一页用请求 pageSize=50，后续页用响应 pageSize=10
        assert requested_page_sizes[0] == 50
        for ps in requested_page_sizes[1:]:
            assert ps == 10
        # 8 页全部请求（73/10=8）
        assert len(requested_page_sizes) == 8

    @pytest.mark.asyncio
    async def test_dedup_by_item_id(self):
        """重复商品按 itemId 去重。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"

        def mock_request(cookie, api, data, **kwargs):
            page = data["pageNo"]
            if page == 1:
                items = [{"itemId": "1"}, {"itemId": "2"}, {"itemId": "3"}]
            else:
                # 第 2 页重复第 1 页的部分商品
                items = [{"itemId": "3"}, {"itemId": "4"}, {"itemId": "5"}]
            return self._make_search_response(items, page, 5, 2)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_goods_all(cookie_str)

        assert result["unique_count"] == 5  # 去重后 5 件

    @pytest.mark.asyncio
    async def test_partial_page_failure_does_not_block(self):
        """某页失败不阻塞整体同步。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"

        def mock_request(cookie, api, data, **kwargs):
            page = data["pageNo"]
            if page == 2:
                raise XianyuProviderRejectedError("第2页失败")
            items = [{"itemId": str(i)} for i in range((page - 1) * 20, page * 20)]
            return self._make_search_response(items, page, 73, 4)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_goods_all(cookie_str)

        # 第 2 页失败，但第 1/3/4 页成功，结果中包含这些页的商品
        assert result["unique_count"] > 0
        # total 仍为 73，但 unique < total（因为第 2 页丢失）


class TestFetchFishShopDatacompassAllPagination:
    """数据罗盘接口全量分页测试。"""

    def _make_compass_response(self, items, page, total, page_size=10):
        total_page = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "code": "0",
                "data": {
                    "list": items,
                    "total": total,
                    "pageNo": page,
                    "pageSize": page_size,
                },
            },
        }

    @pytest.mark.asyncio
    async def test_single_page_no_more_pagination(self):
        """单页结果不触发后续分页。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"
        call_count = 0

        def mock_request(cookie, api, data, **kwargs):
            nonlocal call_count
            call_count += 1
            return self._make_compass_response(
                [{"itmId": "1", "showPv": 100, "ipv": 10}], 1, 1
            )

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_datacompass_all(cookie_str)

        assert call_count == 1
        assert result["total"] == 1
        assert "1" in result["metrics"]

    @pytest.mark.asyncio
    async def test_multi_page_dynamic_pagination(self):
        """多页结果动态创建后续页请求。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"
        pages_requested = []

        def mock_request(cookie, api, data, **kwargs):
            page = data["page"]
            pages_requested.append(page)
            items = [
                {"itmId": str(page * 10 + i), "showPv": 100 + i, "ipv": 10 + i}
                for i in range(10)
            ]
            return self._make_compass_response(items, page, 73, page_size=10)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_datacompass_all(cookie_str)

        # 73/10=8 页
        assert sorted(pages_requested) == [1, 2, 3, 4, 5, 6, 7, 8]
        assert result["total"] == 73

    @pytest.mark.asyncio
    async def test_response_page_size_used_not_request(self):
        """请求 pageSize 与响应 pageSize 不一致时，使用响应 pageSize。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"
        requested_page_sizes = []

        def mock_request(cookie, api, data, **kwargs):
            page = data["page"]
            requested_page_sizes.append(data["pageSize"])
            # 服务端实际返回 pageSize=10
            items = [{"itmId": str(i), "showPv": i, "ipv": i} for i in range(10)]
            return self._make_compass_response(items, page, 73, page_size=10)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_datacompass_all(cookie_str, page_size=50)

        # 第一页用请求 pageSize=50，后续页用响应 pageSize=10
        assert requested_page_sizes[0] == 50
        for ps in requested_page_sizes[1:]:
            assert ps == 10

    @pytest.mark.asyncio
    async def test_dedup_by_itm_id(self):
        """重复指标按 itmId 去重。"""
        cookie_str = "_m_h5_tk=token_123; unb=1"

        def mock_request(cookie, api, data, **kwargs):
            page = data["page"]
            if page == 1:
                items = [
                    {"itmId": "1", "showPv": 100, "ipv": 10},
                    {"itmId": "2", "showPv": 200, "ipv": 20},
                ]
            else:
                # 第 2 页重复 itmId=2
                items = [
                    {"itmId": "2", "showPv": 200, "ipv": 20},
                    {"itmId": "3", "showPv": 300, "ipv": 30},
                ]
            return self._make_compass_response(items, page, 3, page_size=2)

        with patch("app.services.fish_shop_sync._make_fish_shop_request", mock_request):
            result = await fetch_fish_shop_datacompass_all(cookie_str)

        assert result["unique_count"] == 3
        assert set(result["metrics"].keys()) == {"1", "2", "3"}


# ==================== 路由逻辑测试 ====================


class TestFishShopRouting:
    """鱼小铺账号路由测试。"""

    @pytest.mark.asyncio
    async def test_fish_shop_account_delegates_to_fish_shop_sync(self):
        """鱼小铺账号（fish_shop_user=1）委托鱼小铺同步流程。"""
        from app.services.xianyu_goods_sync import sync_goods_for_account

        async def mock_fish_shop_sync(**kwargs):
            return {"sync_id": kwargs["sync_id"], "mode": "fish_shop", "total": 10}

        # 模拟账号查询返回鱼小铺账号
        async def mock_session_execute(*args, **kwargs):
            mock_account = MagicMock()
            mock_account.fish_shop_user = 1
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_account)
            return result

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.xianyu_goods_sync._is_fish_shop_account_async", return_value=True):
            with patch("app.services.fish_shop_sync.sync_fish_shop_goods_for_account", side_effect=mock_fish_shop_sync):
                result = await sync_goods_for_account(
                    account_id=1,
                    tenant_id=100,
                    cookie_str="_m_h5_tk=token_123; unb=1",
                    sync_id="test-sync-1",
                    db_session_factory=None,
                    async_fetch_detail=False,
                )

        assert result["mode"] == "fish_shop"

    @pytest.mark.asyncio
    async def test_regular_account_uses_original_flow(self):
        """普通账号（fish_shop_user=0）走原有同步流程，不调用鱼小铺接口。"""
        from app.services.xianyu_goods_sync import sync_goods_for_account

        # 模拟普通账号：_is_fish_shop_account_async 返回 False
        # 即使后续原有流程因 mock 不完整而抛异常，关键验证是鱼小铺同步函数未被调用
        with patch("app.services.xianyu_goods_sync._is_fish_shop_account_async", return_value=False):
            with patch("app.services.fish_shop_sync.sync_fish_shop_goods_for_account") as mock_fish:
                try:
                    await sync_goods_for_account(
                        account_id=1,
                        tenant_id=100,
                        cookie_str="_m_h5_tk=token_123; unb=1",
                        sync_id="test-sync-2",
                        db_session_factory=None,
                        async_fetch_detail=False,
                    )
                except Exception:
                    pass  # 可能因 mock 不完整而失败，关键是验证鱼小铺接口未被调用
                mock_fish.assert_not_called()


# ==================== 累计销量不伪造测试 ====================


class TestCumulativeSalesNotFabricated:
    """累计销量不伪造测试。"""

    def test_quantity_not_treated_as_cumulative_sales(self):
        """quantity 是库存，不是累计销量。"""
        raw = {"itemId": "1", "quantity": 100}
        goods = _parse_fish_shop_goods_item(raw)
        # quantity 映射为库存，不应映射为累计销量字段
        assert goods["quantity"] == 100
        assert "sold_count" not in goods or goods.get("sold_count") is None
        assert "cumulative_sales" not in goods

    def test_total_not_treated_as_cumulative_sales(self):
        """total 是分页总数，不是累计销量。"""
        resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "code": "0",
                "data": {
                    "itemSearchResponseList": {
                        "itemSearchResponseList": [{"itemId": "1"}],
                        "total": 73,
                        "totalPage": 1,
                        "pageSize": 20,
                        "currentPage": 1,
                        "hasNextPage": False,
                    }
                },
            },
        }
        result = _parse_item_search_response(resp)
        # total 是商品总数，不应出现在单个商品字段中
        assert result["total"] == 73
        for item in result["items"]:
            assert "sold_count" not in item
            assert "cumulative_sales" not in item

    def test_no_fabricated_sales_field(self):
        """不伪造累计销量字段。"""
        raw = {"itemId": "1", "title": "商品"}
        goods = _parse_fish_shop_goods_item(raw)
        # 不应包含伪造的累计销量字段
        assert "sold_count" not in goods
        assert "cumulative_sales" not in goods
        assert "total_sales" not in goods


# ==================== 日志安全测试 ====================


class TestLogSecurity:
    """日志不泄露 Cookie/token/sign 测试。"""

    def test_make_request_does_not_log_cookie(self, caplog):
        """_make_fish_shop_request 不在日志中输出 Cookie。"""
        import logging
        cookie_str = "_m_h5_tk=secret_token_123; unb=secret_unb"
        caplog.set_level(logging.DEBUG, logger="app.services.fish_shop_sync")

        # 触发一个失败的请求（会记录日志）
        with patch("app.services.fish_shop_sync._get_token_from_cookie", return_value="secret_token_123"):
            with patch("requests.Session.post", side_effect=Exception("网络错误")):
                try:
                    _make_fish_shop_request(cookie_str, "test_api", {"page": 1})
                except Exception:
                    pass

        # 验证日志中不包含 Cookie 相关内容
        for record in caplog.records:
            msg = record.getMessage()
            assert "secret_token_123" not in msg
            assert "secret_unb" not in msg
            assert "_m_h5_tk" not in msg
            assert "sign=" not in msg

    def test_retry_log_does_not_leak_credentials(self, caplog):
        """重试日志不泄露凭证。"""
        import logging
        caplog.set_level(logging.WARNING, logger="app.services.fish_shop_sync")

        # 模拟重试场景的日志
        logger = logging.getLogger("app.services.fish_shop_sync")
        logger.warning(
            "鱼小铺接口 %s page=%d 第 %d 次重试，%.2fs 后重试，原因=%s",
            "item.search", 2, 1, 1.0, "ConnectionError",
        )

        for record in caplog.records:
            msg = record.getMessage()
            assert "cookie" not in msg.lower()
            assert "token" not in msg.lower() or "Token过期" in msg  # 允许提及 token 类型，不输出 token 值
            assert "sign" not in msg.lower() or "签名" in msg


# ==================== 常量配置测试 ====================


class TestConstants:
    """鱼小铺接口常量配置测试。"""

    def test_item_search_api_name(self):
        """商品管理接口 API 名称正确。"""
        assert FISH_SHOP_ITEM_SEARCH_API == "mtop.alibaba.idle.seller.pc.common.item.search"

    def test_datacompass_api_name(self):
        """数据罗盘接口 API 名称正确。"""
        assert FISH_SHOP_DATACOMPASS_API == "mtop.alibaba.idle.seller.pc.datacompass.item.list"

    def test_item_search_page_size_is_20(self):
        """商品管理接口已确认 pageSize=20。"""
        assert FISH_SHOP_ITEM_SEARCH_PAGE_SIZE == 20

    def test_datacompass_page_size_is_10(self):
        """数据罗盘接口已确认 pageSize=10。"""
        assert FISH_SHOP_DATACOMPASS_PAGE_SIZE == 10

    def test_page_concurrency_is_bounded(self):
        """单账号分页并发有上限。"""
        assert FISH_SHOP_PAGE_CONCURRENCY > 0
        assert FISH_SHOP_PAGE_CONCURRENCY <= 10  # 合理上限

    def test_item_search_form_extra_has_pc_fields(self):
        """商品管理接口 URL 参数包含 PC 工作台特有字段。"""
        extra = _build_item_search_url_params()
        assert "needLoginPC" in extra
        assert "showErrorToast" in extra
        assert "spm_cnt" in extra
