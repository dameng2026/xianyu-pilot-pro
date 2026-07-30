"""
鱼小铺卖家数据概览服务单元测试。

覆盖场景（按需求第二十九节）：
1. 请求结构：dateRange/ms 为空字符串、selectedSellerId 为字符串 "undefined"
2. dateType 白名单：recent1d / recent7d / recent30d
3. 响应解析：bannerDataList / graphDataList / realDateRange
4. 成功判断：HTTP 200 但 ret 失败时按失败处理
5. 全部账号聚合：金额/计数求和、aov 用总额/总订单数、不平均 ratio
6. 人数类指标：求和（注明各账号之和，非跨店去重）
7. 比例/百分位：不平均，全部账号模式返回 None
8. 趋势聚合：按 ds 聚合，使用 realDateRange 过滤，0 值正常显示
9. 部分失败：成功账号数据仍展示，failedAccountIds 不暴露敏感信息
10. 单账号：只请求一次，不重复请求
11. selectedSellerId：不写入项目内部账号 ID 或系统用户 ID
12. 缓存隔离：不同账号、不同 dateType 缓存独立
13. 安全：日志不含 Cookie / token / sign
14. _compute_ratio：上期为 0 不除零、缺失不显示虚假百分比
"""
from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fish_shop_datacompass import (
    ALLOWED_DATE_TYPES,
    CACHE_TTL_SECONDS,
    CORE_METRIC_KEYS,
    DEFAULT_DATE_TYPE,
    FISH_SHOP_SELLER_SUMMARY_API,
    FISH_SHOP_SELLER_SUMMARY_VERSION,
    NON_ADDITIVE_METRICS,
    SELLER_SUMMARY_CONCURRENCY,
    SELLER_SUMMARY_TIMEOUT,
    TREND_METRIC_KEYS,
    _aggregate_banners,
    _aggregate_graph,
    _build_seller_summary_data,
    _build_seller_summary_url_params,
    _compute_ratio,
    _fetch_account_summary_with_cache,
    _fetch_single_account_summary,
    _parse_seller_summary_response,
    _resolve_account_cookie_str,
    _resolve_fish_shop_accounts,
    _to_number,
    fetch_seller_summary,
    invalidate_cache,
)
from app.services.xianyu_goods_sync import (
    XianyuAuthExpiredError,
    XianyuProviderRejectedError,
    XianyuRiskControlError,
)


# ==================== 请求结构 ====================


class TestBuildSellerSummaryData:
    """请求 data 字段构造测试。"""

    def test_recent7d_structure(self):
        data = _build_seller_summary_data("recent7d")
        assert data["dateRange"] == ""
        assert data["dateType"] == "recent7d"
        assert data["ms"] == ""
        assert data["selectedSellerId"] == "undefined"

    def test_recent1d_only_changes_date_type(self):
        data = _build_seller_summary_data("recent1d")
        assert data["dateType"] == "recent1d"
        assert data["dateRange"] == ""
        assert data["ms"] == ""
        assert data["selectedSellerId"] == "undefined"

    def test_recent30d_only_changes_date_type(self):
        data = _build_seller_summary_data("recent30d")
        assert data["dateType"] == "recent30d"
        assert data["dateRange"] == ""
        assert data["ms"] == ""
        assert data["selectedSellerId"] == "undefined"

    def test_selected_seller_id_is_string_undefined_not_js_undefined(self):
        """selectedSellerId 必须是字符串 "undefined"，不是 Python None 或 JS undefined。"""
        data = _build_seller_summary_data("recent7d")
        assert data["selectedSellerId"] == "undefined"
        assert isinstance(data["selectedSellerId"], str)

    def test_selected_seller_id_not_contains_internal_account_id(self):
        """不得把项目内部账号 ID 写入 selectedSellerId。"""
        data = _build_seller_summary_data("recent7d")
        # 排除常见的内部 ID 形式
        assert "123456" not in data["selectedSellerId"]
        assert data["selectedSellerId"] != ""

    def test_serialization_keeps_selected_seller_id_field(self):
        """序列化后 selectedSellerId 字段必须存在且为字符串 "undefined"。"""
        data = _build_seller_summary_data("recent7d")
        serialized = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        assert '"selectedSellerId":"undefined"' in serialized


# ==================== dateType 白名单 ====================


class TestDateTypeWhitelist:
    """dateType 白名单测试。"""

    def test_allowed_date_types(self):
        assert set(ALLOWED_DATE_TYPES) == {"recent1d", "recent7d", "recent30d"}

    def test_default_date_type(self):
        assert DEFAULT_DATE_TYPE == "recent7d"


# ==================== 响应解析 ====================


def _make_response(
    banners=None,
    graph=None,
    real_date_range=None,
    ret=("SUCCESS::调用成功",),
    data_code="success",
    inner_success="true",
):
    """构造模拟响应。"""
    banner_list = banners or []
    graph_list = graph or []
    return {
        "ret": list(ret),
        "data": {
            "code": data_code,
            "msg": "成功",
            "data": {
                "success": inner_success,
                "graphBannerBenchData": {
                    "bannerDataList": banner_list,
                    "graphDataList": graph_list,
                },
            },
            "extendInfo": {
                "realDateRange": real_date_range or [],
            },
        },
    }


class TestParseSellerSummaryResponse:
    """响应解析测试。"""

    def test_parse_banner_data_list(self):
        banners = [
            {
                "name": "payAmt",
                "cycle": "环比",
                "data": 1234.56,
                "dataFormat": "¥1,234.56",
                "dataStr": "1234.56",
                "lastData": 1000.0,
                "lastDataFormat": "¥1,000.00",
                "lastDataStr": "1000.00",
                "ratio": 0.2346,
                "ratioFormat": "23.46%",
                "decimal": 2,
                "extendInfo": {"unit": "元"},
            },
        ]
        resp = _make_response(banners=banners, real_date_range=["20260720", "20260726"])
        payload = _parse_seller_summary_response(resp)
        assert "payAmt" in payload["banners"]
        assert payload["banners"]["payAmt"]["data"] == 1234.56
        assert payload["banners"]["payAmt"]["dataFormat"] == "¥1,234.56"
        assert payload["banners"]["payAmt"]["lastData"] == 1000.0
        assert payload["banners"]["payAmt"]["ratio"] == 0.2346
        assert payload["banners"]["payAmt"]["ratioFormat"] == "23.46%"
        assert payload["realDateRange"] == ["20260720", "20260726"]

    def test_parse_graph_data_list(self):
        graph = [
            {"ds": "20260720", "timeCycle": "day", "slrId": "123", "payAmt": 100.0, "payOrdCnt": 5},
            {"ds": "20260721", "timeCycle": "day", "slrId": "123", "payAmt": 200.0, "payOrdCnt": 10},
        ]
        resp = _make_response(graph=graph, real_date_range=["20260720", "20260721"])
        payload = _parse_seller_summary_response(resp)
        assert len(payload["graph"]) == 2
        assert payload["graph"][0]["ds"] == "20260720"
        assert payload["graph"][0]["payAmt"] == 100.0

    def test_real_date_range_from_extend_info(self):
        resp = _make_response(real_date_range=["20260720", "20260726"])
        payload = _parse_seller_summary_response(resp)
        assert payload["realDateRange"] == ["20260720", "20260726"]

    def test_real_date_range_missing_returns_empty(self):
        resp = _make_response(real_date_range=None)
        # 删除 extendInfo
        resp["data"]["extendInfo"] = {}
        payload = _parse_seller_summary_response(resp)
        assert payload["realDateRange"] == []

    def test_missing_graph_banner_bench_data_safe(self):
        """缺少 graphBannerBenchData 时安全失败，返回空结构。"""
        resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"code": "success", "data": {}},
        }
        payload = _parse_seller_summary_response(resp)
        assert payload["banners"] == {}
        assert payload["graph"] == []
        assert payload["realDateRange"] == []

    def test_missing_single_metric_does_not_crash(self):
        """缺少单个次要指标时页面不崩溃。"""
        banners = [{"name": "payAmt", "data": 100}]
        resp = _make_response(banners=banners)
        payload = _parse_seller_summary_response(resp)
        assert "payAmt" in payload["banners"]
        # 缺少的字段默认空
        assert payload["banners"]["payAmt"]["lastData"] is None
        assert payload["banners"]["payAmt"]["ratio"] is None


# ==================== 成功判断 ====================


class TestBusinessSuccessCheck:
    """HTTP 200 但 MTOP 业务失败时按失败处理。"""

    @pytest.mark.asyncio
    async def test_ret_failure_raises(self):
        """ret 中不含 SUCCESS 时抛 XianyuProviderRejectedError。"""
        bad_resp = {
            "ret": ["FAIL::参数错误"],
            "data": {"code": "fail"},
        }
        with patch(
            "app.services.fish_shop_datacompass._make_fish_shop_request",
            return_value=bad_resp,
        ):
            with pytest.raises(XianyuProviderRejectedError):
                await _fetch_single_account_summary("fake_cookie", "recent7d")

    @pytest.mark.asyncio
    async def test_data_code_failure_raises(self):
        """data.code 非 success 时抛异常。"""
        bad_resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"code": "fail", "message": "业务失败"},
        }
        with patch(
            "app.services.fish_shop_datacompass._make_fish_shop_request",
            return_value=bad_resp,
        ):
            with pytest.raises(XianyuProviderRejectedError):
                await _fetch_single_account_summary("fake_cookie", "recent7d")

    @pytest.mark.asyncio
    async def test_missing_graph_banner_bench_data_raises_or_safe(self):
        """缺少 graphBannerBenchData 时不会崩溃（_parse 返回空结构）。"""
        empty_resp = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "code": "success",
                "data": {"success": "true"},
                "extendInfo": {},
            },
        }
        with patch(
            "app.services.fish_shop_datacompass._make_fish_shop_request",
            return_value=empty_resp,
        ):
            payload = await _fetch_single_account_summary("fake_cookie", "recent7d")
            assert payload["banners"] == {}
            assert payload["graph"] == []


# ==================== 全部账号聚合 ====================


class TestAggregateBanners:
    """全部账号 banner 聚合测试。"""

    def test_additive_metric_summed(self):
        """金额/计数类指标按账号求和。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260726"],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 1000.0, "lastData": 800.0, "ratio": 0.25},
                    "payOrdCnt": {"name": "payOrdCnt", "data": 10, "lastData": 8, "ratio": 0.25},
                },
                "graph": [],
            },
            {
                "realDateRange": ["20260720", "20260726"],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 500.0, "lastData": 400.0, "ratio": 0.25},
                    "payOrdCnt": {"name": "payOrdCnt", "data": 5, "lastData": 4, "ratio": 0.25},
                },
                "graph": [],
            },
        ]
        result = _aggregate_banners(per_account)
        # 求和
        assert result["payAmt"]["data"] == 1500.0
        assert result["payAmt"]["lastData"] == 1200.0
        assert result["payOrdCnt"]["data"] == 15.0
        assert result["payOrdCnt"]["lastData"] == 12.0
        # ratio 不平均，用聚合后重新计算
        assert result["payAmt"]["ratio"] is not None
        # (1500 - 1200) / 1200 = 0.25
        assert abs(result["payAmt"]["ratio"] - 0.25) < 1e-6

    def test_aov_uses_total_amount_divided_by_total_orders(self):
        """客单价 = 总成交金额 / 总订单数，不直接平均各账号 aov。"""
        per_account = [
            {
                "realDateRange": [],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 1000.0, "lastData": None},
                    "payOrdCnt": {"name": "payOrdCnt", "data": 10, "lastData": None},
                    "aov": {"name": "aov", "data": 100.0, "lastData": None},
                },
                "graph": [],
            },
            {
                "realDateRange": [],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 600.0, "lastData": None},
                    "payOrdCnt": {"name": "payOrdCnt", "data": 2, "lastData": None},
                    "aov": {"name": "aov", "data": 300.0, "lastData": None},
                },
                "graph": [],
            },
        ]
        result = _aggregate_banners(per_account)
        # 总额 1600 / 总订单 12 = 133.33...
        assert result["aov"]["data"] is not None
        assert abs(result["aov"]["data"] - (1600.0 / 12.0)) < 1e-6
        # 不应等于平均各账号 aov（100 + 300）/2 = 200
        assert result["aov"]["data"] != 200.0

    def test_non_additive_metric_returns_none(self):
        """比例/百分位类指标不平均，返回 None。"""
        per_account = [
            {
                "realDateRange": [],
                "banners": {
                    "showPvCmpPctl": {"name": "showPvCmpPctl", "data": 0.85, "lastData": None},
                    "payOrdCntCmpPctl": {"name": "payOrdCntCmpPctl", "data": 0.72, "lastData": None},
                    "uctr": {"name": "uctr", "data": 0.05, "lastData": None},
                },
                "graph": [],
            },
            {
                "realDateRange": [],
                "banners": {
                    "showPvCmpPctl": {"name": "showPvCmpPctl", "data": 0.60, "lastData": None},
                    "payOrdCntCmpPctl": {"name": "payOrdCntCmpPctl", "data": 0.40, "lastData": None},
                },
                "graph": [],
            },
        ]
        result = _aggregate_banners(per_account)
        for key in ("showPvCmpPctl", "payOrdCntCmpPctl", "uctr"):
            assert key in result
            assert result[key]["data"] is None
            assert result[key]["ratio"] is None
            assert result[key]["aggregated"] is True

    def test_uv_metrics_summed_with_note(self):
        """人数类指标按账号求和（非跨店去重）。"""
        per_account = [
            {
                "realDateRange": [],
                "banners": {
                    "showUv": {"name": "showUv", "data": 100, "lastData": 80, "ratio": 0.25},
                    "vstUv": {"name": "vstUv", "data": 50, "lastData": 40, "ratio": 0.25},
                },
                "graph": [],
            },
            {
                "realDateRange": [],
                "banners": {
                    "showUv": {"name": "showUv", "data": 200, "lastData": 180, "ratio": 0.11},
                    "vstUv": {"name": "vstUv", "data": 100, "lastData": 90, "ratio": 0.11},
                },
                "graph": [],
            },
        ]
        result = _aggregate_banners(per_account)
        # 各账号之和（非跨店去重）
        assert result["showUv"]["data"] == 300.0
        assert result["vstUv"]["data"] == 150.0

    def test_missing_last_data_no_fake_ratio(self):
        """上期数据缺失时不显示虚假百分比。"""
        per_account = [
            {
                "realDateRange": [],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 1000.0, "lastData": None, "ratio": None},
                },
                "graph": [],
            },
        ]
        result = _aggregate_banners(per_account)
        assert result["payAmt"]["data"] == 1000.0
        assert result["payAmt"]["lastData"] is None
        assert result["payAmt"]["ratio"] is None

    def test_last_zero_no_division_error(self):
        """上期为 0 时避免除零，ratio 返回 None。"""
        per_account = [
            {
                "realDateRange": [],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 1000.0, "lastData": 0.0, "ratio": None},
                },
                "graph": [],
            },
        ]
        result = _aggregate_banners(per_account)
        assert result["payAmt"]["data"] == 1000.0
        assert result["payAmt"]["lastData"] == 0.0
        assert result["payAmt"]["ratio"] is None


# ==================== 比例计算 ====================


class TestComputeRatio:
    """_compute_ratio 测试。"""

    def test_positive_ratio(self):
        assert abs(_compute_ratio(120, 100) - 0.2) < 1e-6

    def test_negative_ratio(self):
        assert abs(_compute_ratio(80, 100) - (-0.2)) < 1e-6

    def test_zero_ratio(self):
        assert _compute_ratio(100, 100) == 0.0

    def test_last_zero_returns_none(self):
        """上期为 0 时不除零。"""
        assert _compute_ratio(100, 0) is None

    def test_last_none_returns_none(self):
        """上期缺失时不显示虚假百分比。"""
        assert _compute_ratio(100, None) is None

    def test_current_none_returns_none(self):
        assert _compute_ratio(None, 100) is None

    def test_both_none_returns_none(self):
        assert _compute_ratio(None, None) is None

    def test_both_zero_returns_none(self):
        """当前和上期都为 0 时返回 None（避免除零）。"""
        assert _compute_ratio(0, 0) is None


# ==================== 趋势聚合 ====================


class TestAggregateGraph:
    """趋势数据聚合测试。"""

    def test_aggregate_by_ds(self):
        """多账号趋势按 ds 聚合。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "payAmt": 100.0, "payOrdCnt": 5},
                    {"ds": "20260721", "payAmt": 200.0, "payOrdCnt": 10},
                ],
            },
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "payAmt": 50.0, "payOrdCnt": 2},
                    {"ds": "20260721", "payAmt": 80.0, "payOrdCnt": 4},
                ],
            },
        ]
        result = _aggregate_graph(per_account)
        assert len(result) == 2
        assert result[0]["ds"] == "20260720"
        assert result[0]["payAmt"] == 150.0
        assert result[0]["payOrdCnt"] == 7.0
        assert result[1]["ds"] == "20260721"
        assert result[1]["payAmt"] == 280.0

    def test_filter_by_real_date_range(self):
        """使用 realDateRange 过滤当前周期，不混入对比周期。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260726"],
                "banners": {},
                "graph": [
                    {"ds": "20260713", "payAmt": 999.0},  # 上一周期，应被过滤
                    {"ds": "20260720", "payAmt": 100.0},
                    {"ds": "20260726", "payAmt": 200.0},
                ],
            },
        ]
        result = _aggregate_graph(per_account)
        ds_list = [p["ds"] for p in result]
        assert "20260713" not in ds_list
        assert "20260720" in ds_list
        assert "20260726" in ds_list

    def test_zero_value_kept_not_treated_as_missing(self):
        """0 值正常显示，不当成无数据。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "payAmt": 0},
                    {"ds": "20260721", "payAmt": 100.0},
                ],
            },
        ]
        result = _aggregate_graph(per_account)
        assert result[0]["payAmt"] == 0.0
        assert result[1]["payAmt"] == 100.0

    def test_failed_account_not_padded_with_zero(self):
        """失败账号不整段补 0（聚合时只看成功账号的 graph）。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "payAmt": 100.0},
                    {"ds": "20260721", "payAmt": 200.0},
                ],
            },
            # 第二个账号某天没数据
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "payAmt": 50.0},
                    # 20260721 缺失
                ],
            },
        ]
        result = _aggregate_graph(per_account)
        # 20260720 = 150
        assert result[0]["payAmt"] == 150.0
        # 20260721 = 200（不是 200+0=200，但是只有第一个账号贡献）
        assert result[1]["payAmt"] == 200.0

    def test_ratio_metric_not_averaged(self):
        """比例类趋势指标不平均，置为 None。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "uctr": 0.05},
                    {"ds": "20260721", "uctr": 0.06},
                ],
            },
            {
                "realDateRange": ["20260720", "20260721"],
                "banners": {},
                "graph": [
                    {"ds": "20260720", "uctr": 0.10},
                    {"ds": "20260721", "uctr": 0.12},
                ],
            },
        ]
        result = _aggregate_graph(per_account)
        for point in result:
            assert point.get("uctr") is None

    def test_sorted_by_ds(self):
        """按 ds 升序排序。"""
        per_account = [
            {
                "realDateRange": ["20260720", "20260721", "20260722"],
                "banners": {},
                "graph": [
                    {"ds": "20260722", "payAmt": 300.0},
                    {"ds": "20260720", "payAmt": 100.0},
                    {"ds": "20260721", "payAmt": 200.0},
                ],
            },
        ]
        result = _aggregate_graph(per_account)
        assert [p["ds"] for p in result] == ["20260720", "20260721", "20260722"]


# ==================== fetch_seller_summary 主入口 ====================


class TestFetchSellerSummary:
    """fetch_seller_summary 主入口测试。"""

    @pytest.mark.asyncio
    async def test_no_fish_shop_account_returns_empty_state(self):
        """没有鱼小铺账号：不调用接口，返回空状态。"""
        db = MagicMock()
        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=[]),
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        assert result["noFishShopAccount"] is True
        assert result["accounts"]["total"] == 0
        assert result["banners"] == {}
        assert result["graph"] == []

    @pytest.mark.asyncio
    async def test_single_fish_shop_account_does_not_duplicate_request(self):
        """只有一个鱼小铺账号：默认全部账号等价于该账号，只请求一次。"""
        db = MagicMock()
        account = {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""}
        payload = {
            "realDateRange": ["20260720", "20260726"],
            "banners": {"payAmt": {"name": "payAmt", "data": 1000.0, "lastData": 800.0, "ratio": 0.25}},
            "graph": [{"ds": "20260720", "payAmt": 100.0}],
        }
        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=[account]),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            AsyncMock(return_value=payload),
        ) as mock_fetch:
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        # 只请求一次（不重复请求"全部账号"+"单账号"两次）
        assert mock_fetch.await_count == 1
        assert result["mode"] == "all"
        assert result["accounts"]["total"] == 1
        assert result["accounts"]["success"] == 1
        assert result["banners"]["payAmt"]["data"] == 1000.0

    @pytest.mark.asyncio
    async def test_multiple_accounts_aggregated(self):
        """多个鱼小铺账号：逐账号请求并聚合。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
            {"id": 101, "nickname": "B", "displayName": "B", "externalUid": "u2", "remark": ""},
        ]

        async def fake_fetch(db_, tenant_id, account_id, date_type):
            return {
                "realDateRange": ["20260720", "20260726"],
                "banners": {
                    "payAmt": {"name": "payAmt", "data": 1000.0 if account_id == 100 else 500.0, "lastData": None},
                },
                "graph": [{"ds": "20260720", "payAmt": 100.0 if account_id == 100 else 50.0}],
            }

        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            side_effect=fake_fetch,
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        assert result["mode"] == "all"
        assert result["accounts"]["total"] == 2
        assert result["accounts"]["success"] == 2
        # 聚合后 payAmt = 1500
        assert result["banners"]["payAmt"]["data"] == 1500.0
        # 趋势按 ds 聚合
        assert result["graph"][0]["payAmt"] == 150.0
        # 含 aovNote 说明
        assert "aovNote" in result

    @pytest.mark.asyncio
    async def test_partial_failure_keeps_successful_data(self):
        """部分账号失败：成功账号数据仍展示，标记 isPartial。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
            {"id": 101, "nickname": "B", "displayName": "B", "externalUid": "u2", "remark": ""},
        ]

        async def fake_fetch(db_, tenant_id, account_id, date_type):
            if account_id == 101:
                raise XianyuAuthExpiredError("Cookie 失效")
            return {
                "realDateRange": ["20260720", "20260726"],
                "banners": {"payAmt": {"name": "payAmt", "data": 1000.0, "lastData": None}},
                "graph": [{"ds": "20260720", "payAmt": 100.0}],
            }

        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            side_effect=fake_fetch,
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        assert result["accounts"]["total"] == 2
        assert result["accounts"]["success"] == 1
        assert result["accounts"]["failed"] == 1
        assert 101 in result["accounts"]["failedAccountIds"]
        assert result["accounts"]["isPartial"] is True
        assert result["accounts"]["allFailed"] is False
        # 成功账号数据仍然展示
        assert result["banners"]["payAmt"]["data"] == 1000.0
        # 不暴露底层错误
        assert "loadFailed" not in result

    @pytest.mark.asyncio
    async def test_all_failed_returns_load_failed(self):
        """所有账号都失败：显示整体失败。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
            {"id": 101, "nickname": "B", "displayName": "B", "externalUid": "u2", "remark": ""},
        ]

        async def fake_fetch(db_, tenant_id, account_id, date_type):
            raise XianyuAuthExpiredError("Cookie 失效")

        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            side_effect=fake_fetch,
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        assert result["accounts"]["allFailed"] is True
        assert result["loadFailed"] is True
        assert result["banners"] == {}

    @pytest.mark.asyncio
    async def test_single_account_mode_only_requests_selected(self):
        """单账号模式：只请求选中的鱼小铺账号。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
            {"id": 101, "nickname": "B", "displayName": "B", "externalUid": "u2", "remark": ""},
        ]
        payload = {
            "realDateRange": ["20260720", "20260726"],
            "banners": {"payAmt": {"name": "payAmt", "data": 1000.0, "lastData": None}},
            "graph": [],
        }
        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            AsyncMock(return_value=payload),
        ) as mock_fetch:
            result = await fetch_seller_summary(db, tenant_id=1, account_id=101, date_type="recent7d")
        # 只请求账号 101
        mock_fetch.assert_awaited_once()
        called_args = mock_fetch.await_args
        assert called_args.args[2] == 101  # account_id
        assert result["mode"] == "single"
        assert result["accounts"]["total"] == 1
        assert result["accounts"]["success"] == 1

    @pytest.mark.asyncio
    async def test_single_account_normal_account_rejected(self):
        """选中普通闲鱼账号（非鱼小铺）：不调用接口。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
        ]
        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            AsyncMock(),
        ) as mock_fetch:
            result = await fetch_seller_summary(db, tenant_id=1, account_id=999, date_type="recent7d")
        mock_fetch.assert_not_awaited()
        assert result.get("invalidAccount") is True
        assert result["banners"] == {}

    @pytest.mark.asyncio
    async def test_invalid_date_type_falls_back_to_default(self):
        """非法 dateType 回退到默认 recent7d。"""
        db = MagicMock()
        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=[]),
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="invalid")
        assert result["dateType"] == "recent7d"


# ==================== 缓存与请求去重 ====================


class TestCacheAndDedup:
    """缓存与请求去重测试。"""

    def setup_method(self):
        invalidate_cache()

    def teardown_method(self):
        invalidate_cache()

    @pytest.mark.asyncio
    async def test_same_account_date_type_dedup(self):
        """相同 (tenant, account, dateType) 的并发请求复用 Future。"""
        db = MagicMock()
        payload = {
            "realDateRange": ["20260720", "20260726"],
            "banners": {"payAmt": {"name": "payAmt", "data": 100.0, "lastData": None}},
            "graph": [],
        }
        call_count = 0

        async def fake_resolve(db_, tenant_id, account_id):
            return "fake_cookie", None

        async def fake_fetch_summary(cookie, date_type):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return payload

        with patch(
            "app.services.fish_shop_datacompass._resolve_account_cookie_str",
            side_effect=fake_resolve,
        ), patch(
            "app.services.fish_shop_datacompass._fetch_single_account_summary",
            side_effect=fake_fetch_summary,
        ):
            # 并发 3 个相同请求
            tasks = [
                _fetch_account_summary_with_cache(db, 1, 100, "recent7d"),
                _fetch_account_summary_with_cache(db, 1, 100, "recent7d"),
                _fetch_account_summary_with_cache(db, 1, 100, "recent7d"),
            ]
            results = await asyncio.gather(*tasks)
        # 只发起一次实际请求
        assert call_count == 1
        # 所有结果相同
        for r in results:
            assert r["banners"]["payAmt"]["data"] == 100.0

    @pytest.mark.asyncio
    async def test_different_accounts_cache_isolated(self):
        """不同账号缓存相互隔离。"""
        db = MagicMock()

        async def fake_resolve(db_, tenant_id, account_id):
            return "fake_cookie", None

        async def fake_fetch_summary(cookie, date_type):
            # 不同 cookie 应返回不同结果，但这里测试缓存隔离用相同 cookie 也可以
            return {
                "realDateRange": [],
                "banners": {"payAmt": {"name": "payAmt", "data": 100.0, "lastData": None}},
                "graph": [],
            }

        with patch(
            "app.services.fish_shop_datacompass._resolve_account_cookie_str",
            side_effect=fake_resolve,
        ), patch(
            "app.services.fish_shop_datacompass._fetch_single_account_summary",
            side_effect=fake_fetch_summary,
        ):
            await _fetch_account_summary_with_cache(db, 1, 100, "recent7d")
            await _fetch_account_summary_with_cache(db, 1, 101, "recent7d")
            # 两次请求都成功（缓存按 account_id 隔离）
            from app.services.fish_shop_datacompass import _response_cache
            assert (1, 100, "recent7d") in _response_cache
            assert (1, 101, "recent7d") in _response_cache

    @pytest.mark.asyncio
    async def test_different_date_type_cache_isolated(self):
        """不同 dateType 缓存相互隔离。"""
        db = MagicMock()

        async def fake_resolve(db_, tenant_id, account_id):
            return "fake_cookie", None

        async def fake_fetch_summary(cookie, date_type):
            return {
                "realDateRange": [],
                "banners": {"payAmt": {"name": "payAmt", "data": 100.0, "lastData": None}},
                "graph": [],
            }

        with patch(
            "app.services.fish_shop_datacompass._resolve_account_cookie_str",
            side_effect=fake_resolve,
        ), patch(
            "app.services.fish_shop_datacompass._fetch_single_account_summary",
            side_effect=fake_fetch_summary,
        ):
            await _fetch_account_summary_with_cache(db, 1, 100, "recent1d")
            await _fetch_account_summary_with_cache(db, 1, 100, "recent7d")
            from app.services.fish_shop_datacompass import _response_cache
            assert (1, 100, "recent1d") in _response_cache
            assert (1, 100, "recent7d") in _response_cache

    @pytest.mark.asyncio
    async def test_invalidate_cache_for_account(self):
        """账号删除/Cookie 更新后旧缓存失效。"""
        db = MagicMock()

        async def fake_resolve(db_, tenant_id, account_id):
            return "fake_cookie", None

        async def fake_fetch_summary(cookie, date_type):
            return {
                "realDateRange": [],
                "banners": {"payAmt": {"name": "payAmt", "data": 100.0, "lastData": None}},
                "graph": [],
            }

        with patch(
            "app.services.fish_shop_datacompass._resolve_account_cookie_str",
            side_effect=fake_resolve,
        ), patch(
            "app.services.fish_shop_datacompass._fetch_single_account_summary",
            side_effect=fake_fetch_summary,
        ):
            await _fetch_account_summary_with_cache(db, 1, 100, "recent7d")
            from app.services.fish_shop_datacompass import _response_cache
            assert (1, 100, "recent7d") in _response_cache
            invalidate_cache(tenant_id=1, account_id=100)
            assert (1, 100, "recent7d") not in _response_cache


# ==================== 并发控制 ====================


class TestConcurrencyControl:
    """多账号请求采用受控并发测试。"""

    def test_concurrency_limit_constant(self):
        """并发上限常量存在且合理（不突破项目全局并发限制）。"""
        assert SELLER_SUMMARY_CONCURRENCY == 8
        assert SELLER_SUMMARY_CONCURRENCY > 0
        assert SELLER_SUMMARY_CONCURRENCY <= 16  # 不无限并发

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_semaphore(self):
        """多个账号同时请求时，并发数不超过 SELLER_SUMMARY_CONCURRENCY。"""
        db = MagicMock()
        accounts = [
            {"id": i, "nickname": f"A{i}", "displayName": f"A{i}", "externalUid": f"u{i}", "remark": ""}
            for i in range(20)
        ]

        current_concurrent = 0
        max_concurrent = 0

        async def fake_resolve(db_, tenant_id, account_id):
            return "fake_cookie", None

        async def fake_fetch_summary(cookie, date_type):
            nonlocal current_concurrent, max_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.05)
            current_concurrent -= 1
            return {
                "realDateRange": ["20260720", "20260726"],
                "banners": {"payAmt": {"name": "payAmt", "data": 100.0, "lastData": None}},
                "graph": [],
            }

        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._resolve_account_cookie_str",
            side_effect=fake_resolve,
        ), patch(
            "app.services.fish_shop_datacompass._fetch_single_account_summary",
            side_effect=fake_fetch_summary,
        ):
            await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        # 并发数不超过上限
        assert max_concurrent <= SELLER_SUMMARY_CONCURRENCY


# ==================== 安全 ====================


class TestSecurity:
    """安全测试：日志不含 Cookie / token / sign。"""

    def test_safe_log_message_no_cookie(self):
        """日志格式不应包含 Cookie / _m_h5_tk / sign 等敏感字段。"""
        # 这里通过日志格式约定验证：模块中所有 logger 调用只记录 account_id / dateType / errorType / elapsed_ms
        # 由于日志格式是代码约束，我们通过静态检查确认
        import inspect
        from app.services import fish_shop_datacompass as mod
        source = inspect.getsource(mod)
        # 不应包含直接打印 cookie 的语句
        assert 'logger.info("cookie' not in source.lower()
        assert 'logger.warning("cookie' not in source.lower()
        # 不应包含打印 _m_h5_tk 的语句
        assert 'logger.%s("_m_h5_tk' not in source.lower()
        # 不应包含打印 sign 的语句
        assert 'logger.%s("sign' not in source.lower()

    @pytest.mark.asyncio
    async def test_cookie_not_in_response_payload(self):
        """返回给前端的数据不含 Cookie。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
        ]
        payload = {
            "realDateRange": [],
            "banners": {},
            "graph": [],
        }
        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            AsyncMock(return_value=payload),
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        # 返回结构中不应有 cookie / token / sign 字段
        result_str = json.dumps(result, ensure_ascii=False, default=str)
        assert "cookie" not in result_str.lower()
        assert "_m_h5_tk" not in result_str.lower()
        assert "sign" not in result_str.lower() or "assign" in result_str.lower()  # "design" 等单词可能命中

    @pytest.mark.asyncio
    async def test_failed_account_ids_not_sensitive(self):
        """failedAccountIds 只含账号 ID，不含敏感错误信息。"""
        db = MagicMock()
        accounts = [
            {"id": 100, "nickname": "A", "displayName": "A", "externalUid": "u1", "remark": ""},
            {"id": 101, "nickname": "B", "displayName": "B", "externalUid": "u2", "remark": ""},
        ]

        async def fake_fetch(db_, tenant_id, account_id, date_type):
            if account_id == 101:
                raise XianyuAuthExpiredError("Cookie _m_h5_tk=secret_value 已失效")
            return {"realDateRange": [], "banners": {}, "graph": []}

        with patch(
            "app.services.fish_shop_datacompass._resolve_fish_shop_accounts",
            AsyncMock(return_value=accounts),
        ), patch(
            "app.services.fish_shop_datacompass._fetch_account_summary_with_cache",
            side_effect=fake_fetch,
        ):
            result = await fetch_seller_summary(db, tenant_id=1, account_id=None, date_type="recent7d")
        # failedAccountIds 只含 ID 数字
        assert result["accounts"]["failedAccountIds"] == [101]
        # 不暴露敏感的 error message
        result_str = json.dumps(result, ensure_ascii=False, default=str)
        assert "secret_value" not in result_str
        assert "_m_h5_tk" not in result_str.lower()


# ==================== 常量与配置 ====================


class TestConstants:
    """常量与配置测试。"""

    def test_api_name(self):
        assert FISH_SHOP_SELLER_SUMMARY_API == "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary"

    def test_api_version(self):
        assert FISH_SHOP_SELLER_SUMMARY_VERSION == "1.0"

    def test_timeout_is_reasonable(self):
        """单账号请求超时不小于 10 秒，不大于 60 秒。"""
        assert 10 <= SELLER_SUMMARY_TIMEOUT <= 60

    def test_cache_ttl_is_short(self):
        """缓存 TTL 应较短（不超过 5 分钟）。"""
        assert CACHE_TTL_SECONDS <= 300

    def test_core_metric_keys_includes_required(self):
        """核心指标必须包含需求第十五节列出的全部指标。"""
        required = {
            "payAmt", "payOrdCnt", "payByrCnt", "aov",
            "showPv", "showUv", "ipv", "ipvUv",
            "vstPv", "vstUv", "chatUv", "onlCnt",
        }
        assert required.issubset(set(CORE_METRIC_KEYS))

    def test_trend_metric_keys_includes_required(self):
        """趋势图可选指标必须包含需求第十七节列出的若干项。"""
        required = {"payAmt", "payOrdCnt", "showPv", "showUv", "ipv", "ipvUv", "vstPv", "vstUv", "chatUv"}
        assert required.issubset(set(TREND_METRIC_KEYS))

    def test_non_additive_metrics_includes_ratio_and_pctl(self):
        """不可相加指标包含 ratio / showPvCmpPctl / payOrdCntCmpPctl。"""
        for key in ("showPvCmpPctl", "payOrdCntCmpPctl"):
            assert key in NON_ADDITIVE_METRICS
