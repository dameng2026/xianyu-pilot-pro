"""
鱼小铺商品编辑详情接口（mtop.idle.pc.backend.idleitem.editdetail）单元测试。

覆盖需求第四至十七节中可独立于真实闲鱼接口验证的逻辑：
- 请求 data 构造（单层 JSON {"itemId":"..."}，不包裹 inputJson）
- 签名使用与提交完全一致的 data 字符串
- itemId 按字符串处理（避免整数精度损失）
- 业务成功判断（不能只判断 HTTP 200）
- 响应 itemId 与请求 itemId 一致性校验
- 字段解析（标题/正文/图片/价格/库存/分类/地址/运费/服务协议/多规格）
- 字符串布尔值安全转换（"false" 不能被识别为 true）
- wlDescription 不覆盖 desc（避免标题正文重复）
- 库存 0 是合法值（不能被当成空值）
- 金额保持分单位（避免浮点精度问题）
- 简单商品无 itemProperties/itemSkuList 时不报错
- 多规格商品 itemProperties/itemSkuList 正确回显
- 请求去重（同一账号+itemId 同时只发一个请求）
- 不同账号不能共享详情缓存
- 编辑成功后缓存失效
- 日志不泄露 Cookie/token/sign/完整正文/完整地址

不依赖真实闲鱼接口与数据库，全部使用纯函数与 mock。
"""
from __future__ import annotations

import json
import threading
import time
import pytest
from unittest.mock import patch, MagicMock

from app.services.fish_shop_publish import (
    FISH_SHOP_EDIT_DETAIL_API,
    FISH_SHOP_EDIT_DETAIL_VERSION,
    FISH_SHOP_DETAIL_API,
    FISH_SHOP_DETAIL_VERSION,
    _safe_str_to_bool,
    _safe_int,
    _safe_str,
    _build_edit_detail_data,
    _build_edit_detail_request_url,
    _extract_edit_detail_data,
    _parse_image_info_list,
    _parse_item_text_dto,
    _parse_item_price_dto,
    _parse_quantity,
    _parse_item_cat_dto,
    _parse_item_label_ext_list,
    _parse_item_addr_dto,
    _parse_item_post_fee_dto,
    _parse_user_rights_protocols,
    _parse_item_properties,
    _parse_property_image_list,
    _parse_item_sku_list,
    parse_edit_detail_response,
    call_fish_shop_edit_detail,
    fetch_fish_shop_edit_detail,
    invalidate_edit_detail_cache,
    clear_all_edit_detail_cache,
)


# ============================================================
# API 常量测试
# ============================================================


class TestEditDetailApiConstants:
    """editdetail 接口常量测试。"""

    def test_edit_detail_api_name(self):
        """API 名称必须是 mtop.idle.pc.backend.idleitem.editdetail（注意是 editdetail 不是 detail）。"""
        assert FISH_SHOP_EDIT_DETAIL_API == "mtop.idle.pc.backend.idleitem.editdetail"

    def test_edit_detail_version_is_1_0(self):
        assert FISH_SHOP_EDIT_DETAIL_VERSION == "1.0"

    def test_legacy_alias_constants(self):
        """旧别名常量仍指向正确 API，便于已有代码平滑过渡。"""
        assert FISH_SHOP_DETAIL_API == FISH_SHOP_EDIT_DETAIL_API
        assert FISH_SHOP_DETAIL_VERSION == FISH_SHOP_EDIT_DETAIL_VERSION


# ============================================================
# 请求 data 构造（单层 JSON，不包裹 inputJson）
# ============================================================


class TestEditDetailDataConstruction:
    """editdetail 请求 data 字符串构造测试。

    关键约束：
    - 单层 JSON：{"itemId":"<item_id>"}
    - 不包裹 inputJson（与发布/编辑接口的双层结构不同）
    - itemId 必须按字符串处理（避免整数精度损失）
    - 签名使用的 data 字符串必须与提交的 data 字符串完全一致
    """

    def test_data_is_single_layer_json(self):
        """data 是单层 JSON 字符串，不是双层 inputJson 结构。"""
        data_str = _build_edit_detail_data("123456789")
        parsed = json.loads(data_str)
        assert parsed == {"itemId": "123456789"}
        # 确认没有 inputJson 字段
        assert "inputJson" not in parsed

    def test_item_id_treated_as_string(self):
        """itemId 必须按字符串处理，避免整数精度损失。"""
        # 大整数 itemId（超过 JS Number.MAX_SAFE_INTEGER）
        big_id = "9007199254740993"
        data_str = _build_edit_detail_data(big_id)
        parsed = json.loads(data_str)
        assert parsed["itemId"] == big_id
        assert isinstance(parsed["itemId"], str)

    def test_item_id_numeric_input_converted_to_string(self):
        """即使是数字类型输入，也要强制按字符串处理。"""
        data_str = _build_edit_detail_data(123456)
        parsed = json.loads(data_str)
        assert parsed["itemId"] == "123456"
        assert isinstance(parsed["itemId"], str)

    def test_empty_item_id_raises(self):
        """空 itemId 必须抛出异常。"""
        with pytest.raises(ValueError):
            _build_edit_detail_data("")
        with pytest.raises(ValueError):
            _build_edit_detail_data(None)

    def test_data_uses_compact_separators(self):
        """data 字符串使用紧凑分隔符（与签名字符串完全一致）。"""
        data_str = _build_edit_detail_data("123")
        # 不应包含空格
        assert " " not in data_str
        # 应为紧凑格式：{"itemId":"123"}
        assert data_str == '{"itemId":"123"}'

    def test_data_string_stable_for_signing(self):
        """同一 itemId 多次构造的 data 字符串完全一致（签名稳定性）。"""
        s1 = _build_edit_detail_data("123456")
        s2 = _build_edit_detail_data("123456")
        assert s1 == s2


# ============================================================
# 业务成功判断（不能只判断 HTTP 200）
# ============================================================


class TestEditDetailSuccessJudgment:
    """editdetail 接口业务成功判断测试。

    关键约束：
    - 不能只判断 HTTP 200
    - ret 中必须包含 SUCCESS
    - data 必须存在
    - data.itemId 必须存在
    - 返回的 itemId 必须与请求 itemId 一致
    """

    def test_http_200_but_ret_failed_raises(self, monkeypatch):
        """HTTP 200 但 ret 表示失败时必须按失败处理。"""
        def mock_post(url, headers, data, timeout):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "ret": ["FAIL_SYS_USER_VALIDATE::用户未登录"],
                "data": {},
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr("requests.post", mock_post)
        monkeypatch.setattr(
            "app.services.fish_shop_publish._refresh_m_h5_tk",
            lambda c: c,
        )
        monkeypatch.setattr(
            "app.services.fish_shop_publish.extract_token_from_cookie",
            lambda c: "fake_token",
        )

        with pytest.raises(RuntimeError) as exc_info:
            call_fish_shop_edit_detail("cookie_str", "123456")
        assert "FAIL_SYS_USER_VALIDATE" in str(exc_info.value)

    def test_missing_data_raises(self, monkeypatch):
        """响应缺少 data 字段时必须失败。"""
        def mock_post(url, headers, data, timeout):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "ret": ["SUCCESS::调用成功"],
                # 没有 data 字段
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr("requests.post", mock_post)
        monkeypatch.setattr(
            "app.services.fish_shop_publish._refresh_m_h5_tk",
            lambda c: c,
        )
        monkeypatch.setattr(
            "app.services.fish_shop_publish.extract_token_from_cookie",
            lambda c: "fake_token",
        )

        with pytest.raises(RuntimeError) as exc_info:
            call_fish_shop_edit_detail("cookie_str", "123456")
        assert "itemId" in str(exc_info.value) or "格式异常" in str(exc_info.value)

    def test_missing_item_id_raises(self, monkeypatch):
        """响应缺少 itemId 时必须失败。"""
        def mock_post(url, headers, data, timeout):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"title": "test"}},  # 没有 itemId
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr("requests.post", mock_post)
        monkeypatch.setattr(
            "app.services.fish_shop_publish._refresh_m_h5_tk",
            lambda c: c,
        )
        monkeypatch.setattr(
            "app.services.fish_shop_publish.extract_token_from_cookie",
            lambda c: "fake_token",
        )

        with pytest.raises(RuntimeError) as exc_info:
            call_fish_shop_edit_detail("cookie_str", "123456")
        assert "itemId" in str(exc_info.value)

    def test_item_id_mismatch_raises(self, monkeypatch):
        """响应 itemId 与请求 itemId 不一致时必须失败。"""
        def mock_post(url, headers, data, timeout):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"itemId": "999999"}},  # 不一致
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr("requests.post", mock_post)
        monkeypatch.setattr(
            "app.services.fish_shop_publish._refresh_m_h5_tk",
            lambda c: c,
        )
        monkeypatch.setattr(
            "app.services.fish_shop_publish.extract_token_from_cookie",
            lambda c: "fake_token",
        )

        with pytest.raises(RuntimeError) as exc_info:
            call_fish_shop_edit_detail("cookie_str", "123456")
        assert "不一致" in str(exc_info.value)

    def test_successful_response_returns_result(self, monkeypatch):
        """成功的响应返回完整结果。"""
        def mock_post(url, headers, data, timeout):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "ret": ["SUCCESS::调用成功"],
                "data": {
                    "data": {
                        "itemId": "123456",
                        "itemTextDTO": {"title": "测试商品", "desc": "测试描述"},
                    }
                },
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr("requests.post", mock_post)
        monkeypatch.setattr(
            "app.services.fish_shop_publish._refresh_m_h5_tk",
            lambda c: c,
        )
        monkeypatch.setattr(
            "app.services.fish_shop_publish.extract_token_from_cookie",
            lambda c: "fake_token",
        )

        result = call_fish_shop_edit_detail("cookie_str", "123456")
        assert "data" in result


# ============================================================
# 字段解析：标题与正文
# ============================================================


class TestItemTextParsing:
    """标题与正文解析测试。

    关键约束：
    - 标题使用 itemTextDTO.title
    - 正文优先使用 itemTextDTO.desc
    - 不使用 wlDescription 覆盖 desc（避免标题正文重复）
    """

    def test_title_from_item_text_dto(self):
        """标题使用 itemTextDTO.title。"""
        parsed = _parse_item_text_dto({"title": "我的商品", "desc": "描述", "wlDescription": "组合文本"})
        assert parsed["title"] == "我的商品"

    def test_description_prefers_desc(self):
        """正文优先使用 desc，不使用 wlDescription 覆盖。"""
        parsed = _parse_item_text_dto({
            "title": "我的商品",
            "desc": "这是描述",
            "wlDescription": "我的商品\n这是描述",  # wlDescription 包含标题+描述
        })
        assert parsed["desc"] == "这是描述"
        # wlDescription 仅作为补充字段保留，不覆盖 desc
        assert parsed["wlDescription"] == "我的商品\n这是描述"

    def test_empty_desc_keeps_empty(self):
        """desc 为空时保持空，不用 wlDescription 覆盖。"""
        parsed = _parse_item_text_dto({
            "title": "我的商品",
            "desc": "",
            "wlDescription": "我的商品\n描述内容",
        })
        assert parsed["desc"] == ""
        # wlDescription 仍保留原始值
        assert parsed["wlDescription"] == "我的商品\n描述内容"

    def test_none_item_text_dto_returns_empty(self):
        """itemTextDTO 为 None 时返回空值。"""
        parsed = _parse_item_text_dto(None)
        assert parsed["title"] == ""
        assert parsed["desc"] == ""
        assert parsed["wlDescription"] == ""

    def test_wl_description_does_not_cause_title_duplication(self):
        """wlDescription 包含标题时，不会导致标题在正文中重复。"""
        title = "iPhone 15 Pro"
        desc = "99新 iPhone 15 Pro 256GB"
        wl_desc = f"{title}\n{desc}"  # wlDescription 是标题+描述组合
        parsed = _parse_item_text_dto({
            "title": title,
            "desc": desc,
            "wlDescription": wl_desc,
        })
        # 正文应该是 desc，不是 wlDescription
        assert parsed["desc"] == desc
        assert parsed["desc"] != wl_desc


# ============================================================
# 字段解析：图片
# ============================================================


class TestImageListParsing:
    """图片列表解析测试。

    关键约束：
    - imageInfoDOList 完整回显
    - major 正确识别（字符串 "false" 不能被识别为 true）
    - 顺序保持服务器返回顺序
    - 只有一张主图
    """

    def test_string_false_not_treated_as_true(self):
        """字符串 "false" 必须被识别为 False，不能直接使用 bool()。"""
        # 验证 _safe_str_to_bool 正确处理字符串布尔值
        assert _safe_str_to_bool("false") is False
        assert _safe_str_to_bool("true") is True
        assert _safe_str_to_bool("False") is False
        assert _safe_str_to_bool("True") is True
        assert _safe_str_to_bool(False) is False
        assert _safe_str_to_bool(True) is True
        assert _safe_str_to_bool(None) is False
        assert _safe_str_to_bool("") is False

    def test_image_list_preserves_order(self):
        """图片顺序保持服务器返回顺序。"""
        images = [
            {"url": "img1.jpg", "major": "true"},
            {"url": "img2.jpg", "major": "false"},
            {"url": "img3.jpg", "major": "false"},
        ]
        parsed = _parse_image_info_list(images)
        assert len(parsed) == 3
        assert parsed[0]["url"] == "img1.jpg"
        assert parsed[1]["url"] == "img2.jpg"
        assert parsed[2]["url"] == "img3.jpg"

    def test_major_correctly_identified(self):
        """major=true 的图片被正确识别为主图。"""
        images = [
            {"url": "img1.jpg", "major": "true"},
            {"url": "img2.jpg", "major": "false"},
        ]
        parsed = _parse_image_info_list(images)
        assert parsed[0]["major"] is True
        assert parsed[1]["major"] is False

    def test_string_false_not_treated_as_major(self):
        """字符串 'false' 不能被识别为 major=true（关键 bug 防护）。"""
        images = [
            {"url": "img1.jpg", "major": "false"},  # 字符串 "false"
            {"url": "img2.jpg", "major": "false"},
        ]
        parsed = _parse_image_info_list(images)
        # 两张都不是主图
        assert parsed[0]["major"] is False
        assert parsed[1]["major"] is False

    def test_empty_url_skipped(self):
        """空 URL 的图片被跳过。"""
        images = [
            {"url": "", "major": "true"},
            {"url": "img1.jpg", "major": "false"},
        ]
        parsed = _parse_image_info_list(images)
        assert len(parsed) == 1
        assert parsed[0]["url"] == "img1.jpg"

    def test_complete_image_list_returned(self):
        """完整图片列表被回显，不只用列表封面。"""
        images = [
            {"url": f"img{i}.jpg", "major": "true" if i == 0 else "false"}
            for i in range(5)
        ]
        parsed = _parse_image_info_list(images)
        assert len(parsed) == 5
        major_count = sum(1 for img in parsed if img["major"])
        assert major_count == 1  # 只有一张主图


# ============================================================
# 字段解析：价格与库存
# ============================================================


class TestPriceAndStockParsing:
    """价格与库存解析测试。

    关键约束：
    - priceInCent 正确转换（保持分单位，避免浮点精度）
    - quantity 正确转换（0 是合法库存，不能被当成空值）
    """

    def test_price_in_cent_as_integer(self):
        """价格保持分单位的整数。"""
        parsed = _parse_item_price_dto({"priceInCent": 9999})
        assert parsed["priceInCent"] == 9999
        assert isinstance(parsed["priceInCent"], int)

    def test_price_in_cent_string_converted(self):
        """字符串分单位被转换为整数。"""
        parsed = _parse_item_price_dto({"priceInCent": "9999"})
        assert parsed["priceInCent"] == 9999

    def test_price_in_cent_zero(self):
        """价格为 0 时返回 0。"""
        parsed = _parse_item_price_dto({"priceInCent": 0})
        assert parsed["priceInCent"] == 0

    def test_price_in_cent_negative_clamped_to_zero(self):
        """负数价格被限制为 0。"""
        parsed = _parse_item_price_dto({"priceInCent": -100})
        assert parsed["priceInCent"] == 0

    def test_quantity_zero_is_valid(self):
        """库存 0 是合法值，不能被当成空值。"""
        assert _parse_quantity(0) == 0
        assert _parse_quantity("0") == 0

    def test_quantity_string_converted(self):
        """字符串库存被转换为整数。"""
        assert _parse_quantity("100") == 100

    def test_quantity_negative_clamped_to_zero(self):
        """负数库存被限制为 0。"""
        assert _parse_quantity(-5) == 0

    def test_quantity_none_returns_zero(self):
        """None 库存返回 0。"""
        assert _parse_quantity(None) == 0

    def test_quantity_float_truncated(self):
        """浮点库存被截断为整数。"""
        assert _parse_quantity(10.9) == 10

    def test_no_float_precision_loss_for_price(self):
        """价格不进行浮点运算，避免精度损失。"""
        # 19.99 元 = 1999 分
        parsed = _parse_item_price_dto({"priceInCent": 1999})
        assert parsed["priceInCent"] == 1999
        # 不应有浮点转换


# ============================================================
# 字段解析：分类
# ============================================================


class TestCategoryParsing:
    """分类解析测试。"""

    def test_complete_category_parsed(self):
        """完整分类信息被解析。"""
        cat_dto = {
            "catId": "50025461",
            "catName": "软件安装包",
            "tbCatId": "50003316",
            "channelCatId": "201449620",
            "sugShow": "true",
        }
        parsed = _parse_item_cat_dto(cat_dto)
        assert parsed["catId"] == "50025461"
        assert parsed["catName"] == "软件安装包"
        assert parsed["tbCatId"] == "50003316"
        assert parsed["channelCatId"] == "201449620"

    def test_empty_category_returns_defaults(self):
        """空分类返回默认空值。"""
        parsed = _parse_item_cat_dto(None)
        assert parsed["catId"] == ""
        assert parsed["catName"] == ""

    def test_label_ext_list_empty_properties_safe(self):
        """itemLabelExtList 中空 properties 不会报错。"""
        labels = [
            {"cardId": "1", "value": "标签1", "properties": {}},
            {"cardId": "2", "value": "", "properties": None},  # 空 properties
            {"cardId": "3", "value": "标签3"},  # 缺失 properties
        ]
        parsed = _parse_item_label_ext_list(labels)
        assert len(parsed) == 3
        assert parsed[0]["value"] == "标签1"
        assert parsed[1]["properties"] == {}
        assert parsed[2]["properties"] == {}


# ============================================================
# 字段解析：地址
# ============================================================


class TestAddressParsing:
    """地址解析测试。

    关键约束：
    - 正确回显地址
    - 不得硬编码抓包中的地址
    - divisionId 兼容字符串与数字形式
    - 不得因 divisionId 形式不同报错
    """

    def test_complete_address_parsed(self):
        """完整地址被解析。"""
        addr = {
            "prov": "浙江省",
            "city": "杭州市",
            "area": "西湖区",
            "poiName": "某地",
            "divisionId": "330106",
            "gps": "30.2741,120.1551",
            "poiId": "B00123",
        }
        parsed = _parse_item_addr_dto(addr)
        assert parsed["prov"] == "浙江省"
        assert parsed["city"] == "杭州市"
        assert parsed["area"] == "西湖区"
        assert parsed["divisionId"] == "330106"

    def test_division_id_numeric_form(self):
        """divisionId 为数字形式时也正确处理（保持字符串）。"""
        addr = {"prov": "浙江省", "city": "杭州市", "divisionId": 330106}
        parsed = _parse_item_addr_dto(addr)
        assert parsed["divisionId"] == "330106"

    def test_division_id_string_form(self):
        """divisionId 为字符串形式时正确处理。"""
        addr = {"prov": "浙江省", "city": "杭州市", "divisionId": "330106"}
        parsed = _parse_item_addr_dto(addr)
        assert parsed["divisionId"] == "330106"

    def test_empty_address_returns_defaults(self):
        """空地址返回默认空值。"""
        parsed = _parse_item_addr_dto(None)
        assert parsed["prov"] == ""
        assert parsed["city"] == ""


# ============================================================
# 字段解析：运费（字符串布尔值）
# ============================================================


class TestPostFeeParsing:
    """运费解析测试。

    关键约束：
    - 字符串布尔值安全转换（"true"/"false"）
    - 不得使用 Boolean("false") 这种产生错误结果的转换
    """

    def test_string_boolean_can_free_shipping(self):
        """canFreeShipping='true' 字符串正确转换为 True。"""
        parsed = _parse_item_post_fee_dto({"canFreeShipping": "true"})
        assert parsed["canFreeShipping"] is True

    def test_string_false_can_free_shipping(self):
        """canFreeShipping='false' 字符串正确转换为 False（关键 bug 防护）。"""
        parsed = _parse_item_post_fee_dto({"canFreeShipping": "false"})
        assert parsed["canFreeShipping"] is False

    def test_string_boolean_support_freight(self):
        """supportFreight 字符串布尔值正确转换。"""
        assert _parse_item_post_fee_dto({"supportFreight": "true"})["supportFreight"] is True
        assert _parse_item_post_fee_dto({"supportFreight": "false"})["supportFreight"] is False

    def test_string_boolean_only_take_self(self):
        """onlyTakeSelf 字符串布尔值正确转换。"""
        assert _parse_item_post_fee_dto({"onlyTakeSelf": "true"})["onlyTakeSelf"] is True
        assert _parse_item_post_fee_dto({"onlyTakeSelf": "false"})["onlyTakeSelf"] is False

    def test_post_price_in_cent_as_int(self):
        """postPriceInCent 保持分单位整数。"""
        parsed = _parse_item_post_fee_dto({"postPriceInCent": "1000"})
        assert parsed["postPriceInCent"] == 1000
        assert isinstance(parsed["postPriceInCent"], int)

    def test_empty_post_fee_returns_defaults(self):
        """空运费返回默认值。"""
        parsed = _parse_item_post_fee_dto(None)
        assert parsed["canFreeShipping"] is False
        assert parsed["supportFreight"] is False
        assert parsed["postPriceInCent"] == 0


# ============================================================
# 字段解析：服务协议
# ============================================================


class TestUserRightsProtocolsParsing:
    """服务协议解析测试。"""

    def test_protocols_parsed(self):
        """服务协议正确解析。"""
        protocols = [
            {"serviceCode": "FAST_DELIVERY_48_HOUR", "enable": "true"},
            {"serviceCode": "FAST_DELIVERY_24_HOUR", "enable": "false"},
        ]
        parsed = _parse_user_rights_protocols(protocols)
        assert len(parsed) == 2
        assert parsed[0]["serviceCode"] == "FAST_DELIVERY_48_HOUR"
        assert parsed[0]["enable"] is True
        assert parsed[1]["enable"] is False

    def test_empty_protocols_returns_empty_list(self):
        """空协议列表返回空列表。"""
        assert _parse_user_rights_protocols(None) == []
        assert _parse_user_rights_protocols([]) == []


# ============================================================
# 字段解析：多规格
# ============================================================


class TestMultiSpecParsing:
    """多规格解析测试。

    关键约束：
    - 简单商品无 itemProperties/itemSkuList 时不报错，返回空列表
    - 多规格商品 itemProperties/itemSkuList 正确回显
    - 规格类型、规格值、SKU 价格/库存、skuId/inventoryId 正确解析
    """

    def test_simple_item_no_properties(self):
        """简单商品无 itemProperties 时返回空列表，不报错。"""
        parsed = _parse_item_properties(None)
        assert parsed == []

    def test_simple_item_no_sku_list(self):
        """简单商品无 itemSkuList 时返回空列表，不报错。"""
        parsed = _parse_item_sku_list(None)
        assert parsed == []

    def test_simple_item_no_property_image_list(self):
        """简单商品无 propertyImageList 时返回空列表。"""
        assert _parse_property_image_list(None) == []

    def test_multi_spec_properties_parsed(self):
        """多规格商品的 itemProperties 正确解析。"""
        properties = [
            {
                "propertyName": "颜色",
                "supportImage": "true",
                "propertyValues": [
                    {"propertyValue": "红色", "propertyValueImg": "img1.jpg"},
                    {"propertyValue": "蓝色", "propertyValueImg": ""},
                ],
            },
            {
                "propertyName": "尺码",
                "supportImage": "false",
                "propertyValues": [
                    {"propertyValue": "S"},
                    {"propertyValue": "M"},
                ],
            },
        ]
        parsed = _parse_item_properties(properties)
        assert len(parsed) == 2
        assert parsed[0]["propertyName"] == "颜色"
        assert parsed[0]["supportImage"] is True
        assert len(parsed[0]["propertyValues"]) == 2
        assert parsed[0]["propertyValues"][0]["propertyValue"] == "红色"
        assert parsed[0]["propertyValues"][0]["propertyValueImg"] == "img1.jpg"
        assert parsed[1]["supportImage"] is False

    def test_multi_spec_sku_list_parsed(self):
        """多规格商品的 itemSkuList 正确解析。"""
        skus = [
            {
                "priceInCent": "1000",
                "quantity": "5",
                "propertyList": [
                    {"propertyText": "颜色", "valueText": "红色"},
                    {"propertyText": "尺码", "valueText": "S"},
                ],
                "skuId": "sku1",
                "inventoryId": "inv1",
            },
            {
                "priceInCent": "2000",
                "quantity": "10",
                "propertyList": [
                    {"propertyText": "颜色", "valueText": "蓝色"},
                    {"propertyText": "尺码", "valueText": "M"},
                ],
                "skuId": "sku2",
                "inventoryId": "inv2",
            },
        ]
        parsed = _parse_item_sku_list(skus)
        assert len(parsed) == 2
        assert parsed[0]["priceInCent"] == 1000
        assert parsed[0]["quantity"] == 5
        assert parsed[0]["skuId"] == "sku1"
        assert parsed[0]["inventoryId"] == "inv1"
        assert len(parsed[0]["propertyList"]) == 2

    def test_property_image_list_parsed(self):
        """propertyImageList 正确解析。"""
        images = [
            {"propertyText": "颜色", "valueText": "红色", "propertyValueImg": "img1.jpg"},
            {"propertyText": "颜色", "valueText": "蓝色", "propertyValueImg": "img2.jpg"},
        ]
        parsed = _parse_property_image_list(images)
        assert len(parsed) == 2
        assert parsed[0]["propertyText"] == "颜色"
        assert parsed[0]["valueText"] == "红色"
        assert parsed[0]["propertyValueImg"] == "img1.jpg"

    def test_sku_with_zero_quantity_valid(self):
        """SKU 库存为 0 时是合法值。"""
        skus = [
            {
                "priceInCent": "1000",
                "quantity": "0",
                "propertyList": [{"propertyText": "颜色", "valueText": "红色"}],
                "skuId": "sku1",
                "inventoryId": "inv1",
            },
        ]
        parsed = _parse_item_sku_list(skus)
        assert parsed[0]["quantity"] == 0  # 0 是合法库存

    def test_empty_property_name_skipped(self):
        """空规格名被跳过。"""
        properties = [
            {"propertyName": "", "propertyValues": [{"propertyValue": "红色"}]},
            {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}]},
        ]
        parsed = _parse_item_properties(properties)
        assert len(parsed) == 1
        assert parsed[0]["propertyName"] == "颜色"

    def test_empty_property_value_skipped(self):
        """空规格值被跳过。"""
        properties = [
            {
                "propertyName": "颜色",
                "propertyValues": [
                    {"propertyValue": ""},
                    {"propertyValue": "红色"},
                ],
            },
        ]
        parsed = _parse_item_properties(properties)
        assert len(parsed) == 1
        assert len(parsed[0]["propertyValues"]) == 1


# ============================================================
# 完整响应解析：parse_edit_detail_response
# ============================================================


class TestParseEditDetailResponse:
    """完整 editdetail 响应解析测试。"""

    def test_simple_item_response_parsed(self):
        """简单商品响应正确解析（无多规格字段）。"""
        result = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "data": {
                    "itemId": "123456",
                    "itemStatus": "0",
                    "itemTextDTO": {
                        "title": "简单商品",
                        "desc": "这是一个简单商品",
                        "wlDescription": "简单商品\n这是一个简单商品",
                    },
                    "imageInfoDOList": [
                        {"url": "img1.jpg", "major": "true"},
                        {"url": "img2.jpg", "major": "false"},
                    ],
                    "itemPriceDTO": {"priceInCent": 9999},
                    "quantity": 10,
                    "itemCatDTO": {"catId": "50025461", "catName": "软件"},
                    "itemAddrDTO": {"prov": "浙江省", "city": "杭州市"},
                    "itemPostFeeDTO": {"canFreeShipping": "true"},
                    "userRightsProtocols": [],
                }
            },
        }
        parsed = parse_edit_detail_response(result)
        assert parsed["itemId"] == "123456"
        assert parsed["title"] == "简单商品"
        assert parsed["description"] == "这是一个简单商品"
        # wlDescription 不覆盖 desc
        assert parsed["wlDescription"] == "简单商品\n这是一个简单商品"
        assert len(parsed["imageUrls"]) == 2
        assert parsed["majorImageUrl"] == "img1.jpg"
        assert parsed["priceInCent"] == 9999
        assert parsed["quantity"] == 10
        assert parsed["catName"] == "软件"
        assert parsed["prov"] == "浙江省"
        assert parsed["canFreeShipping"] is True
        # 简单商品无多规格
        assert parsed["itemProperties"] == []
        assert parsed["itemSkuList"] == []
        assert parsed["isMultiSpec"] is False

    def test_multi_spec_item_response_parsed(self):
        """多规格商品响应正确解析。"""
        result = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "data": {
                    "itemId": "789",
                    "itemTextDTO": {"title": "多规格商品", "desc": "描述"},
                    "imageInfoDOList": [{"url": "img1.jpg", "major": "true"}],
                    "itemPriceDTO": {"priceInCent": 1000},
                    "quantity": 15,
                    "itemProperties": [
                        {
                            "propertyName": "颜色",
                            "supportImage": "true",
                            "propertyValues": [
                                {"propertyValue": "红色", "propertyValueImg": "r.jpg"},
                                {"propertyValue": "蓝色", "propertyValueImg": "b.jpg"},
                            ],
                        },
                    ],
                    "itemSkuList": [
                        {
                            "priceInCent": "1000",
                            "quantity": "5",
                            "propertyList": [{"propertyText": "颜色", "valueText": "红色"}],
                            "skuId": "s1",
                            "inventoryId": "i1",
                        },
                        {
                            "priceInCent": "2000",
                            "quantity": "10",
                            "propertyList": [{"propertyText": "颜色", "valueText": "蓝色"}],
                            "skuId": "s2",
                            "inventoryId": "i2",
                        },
                    ],
                    "propertyImageList": [
                        {"propertyText": "颜色", "valueText": "红色", "propertyValueImg": "r.jpg"},
                    ],
                }
            },
        }
        parsed = parse_edit_detail_response(result)
        assert parsed["isMultiSpec"] is True
        assert len(parsed["itemProperties"]) == 1
        assert parsed["itemProperties"][0]["propertyName"] == "颜色"
        assert len(parsed["itemSkuList"]) == 2
        assert parsed["itemSkuList"][0]["skuId"] == "s1"
        assert parsed["itemSkuList"][0]["quantity"] == 5
        assert parsed["itemSkuList"][1]["quantity"] == 10

    def test_response_item_id_mismatch_in_parse(self):
        """parse 函数不抛异常（一致性校验在 call 函数中完成）。"""
        result = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"data": {"itemId": "different_id"}},
        }
        # parse 函数只负责映射，不抛异常
        parsed = parse_edit_detail_response(result)
        assert parsed["itemId"] == "different_id"


# ============================================================
# 请求去重与缓存
# ============================================================


class TestEditDetailCacheAndDedup:
    """请求去重与缓存测试。

    关键约束：
    - 同一账号同一 itemId 同时读取只发送一次请求
    - 不同账号同一 itemId 不能共享请求
    - 编辑成功后缓存失效
    - 不会长期展示旧数据
    """

    def setup_method(self):
        """每个测试前清空缓存。"""
        clear_all_edit_detail_cache()

    def teardown_method(self):
        """每个测试后清空缓存。"""
        clear_all_edit_detail_cache()

    def test_cache_hit_avoids_repeat_request(self, monkeypatch):
        """命中缓存时不重复请求。"""
        call_count = 0

        def mock_call(cookie_str, item_id):
            nonlocal call_count
            call_count += 1
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"itemId": item_id}},
            }

        monkeypatch.setattr(
            "app.services.fish_shop_publish.call_fish_shop_edit_detail",
            mock_call,
        )

        # 第一次请求：发起真实调用
        result1 = fetch_fish_shop_edit_detail("cookie", 1, "123")
        assert call_count == 1

        # 第二次请求：命中缓存，不再调用
        result2 = fetch_fish_shop_edit_detail("cookie", 1, "123")
        assert call_count == 1  # 没有增加

        # 两次返回结果相同
        assert result1["itemId"] == result2["itemId"]

    def test_different_accounts_not_shared(self, monkeypatch):
        """不同账号同一 itemId 不能共享缓存。"""
        call_count = 0
        called_accounts = []

        def mock_call(cookie_str, item_id):
            nonlocal call_count
            call_count += 1
            called_accounts.append(cookie_str)
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"itemId": item_id}},
            }

        monkeypatch.setattr(
            "app.services.fish_shop_publish.call_fish_shop_edit_detail",
            mock_call,
        )

        # 账号 A 请求
        fetch_fish_shop_edit_detail("cookieA", 1, "123")
        # 账号 B 请求同一 itemId
        fetch_fish_shop_edit_detail("cookieB", 2, "123")

        # 两次调用都发生（不同账号不共享缓存）
        assert call_count == 2
        assert len(called_accounts) == 2

    def test_different_item_ids_not_shared(self, monkeypatch):
        """同一账号不同 itemId 不能共享缓存。"""
        call_count = 0

        def mock_call(cookie_str, item_id):
            nonlocal call_count
            call_count += 1
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"itemId": item_id}},
            }

        monkeypatch.setattr(
            "app.services.fish_shop_publish.call_fish_shop_edit_detail",
            mock_call,
        )

        fetch_fish_shop_edit_detail("cookie", 1, "123")
        fetch_fish_shop_edit_detail("cookie", 1, "456")
        assert call_count == 2

    def test_invalidate_cache_forces_refresh(self, monkeypatch):
        """失效缓存后下一次请求重新发起。"""
        call_count = 0

        def mock_call(cookie_str, item_id):
            nonlocal call_count
            call_count += 1
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"itemId": item_id}},
            }

        monkeypatch.setattr(
            "app.services.fish_shop_publish.call_fish_shop_edit_detail",
            mock_call,
        )

        # 第一次请求
        fetch_fish_shop_edit_detail("cookie", 1, "123")
        assert call_count == 1

        # 失效缓存
        invalidate_edit_detail_cache(1, "123")

        # 第二次请求：缓存已失效，重新调用
        fetch_fish_shop_edit_detail("cookie", 1, "123")
        assert call_count == 2

    def test_bypass_cache_forces_refresh(self, monkeypatch):
        """bypass_cache=True 时强制刷新。"""
        call_count = 0

        def mock_call(cookie_str, item_id):
            nonlocal call_count
            call_count += 1
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {"data": {"itemId": item_id}},
            }

        monkeypatch.setattr(
            "app.services.fish_shop_publish.call_fish_shop_edit_detail",
            mock_call,
        )

        fetch_fish_shop_edit_detail("cookie", 1, "123")
        assert call_count == 1

        # bypass_cache=True 强制刷新
        fetch_fish_shop_edit_detail("cookie", 1, "123", bypass_cache=True)
        assert call_count == 2

    def test_empty_item_id_raises(self):
        """空 itemId 抛出异常。"""
        with pytest.raises(ValueError):
            fetch_fish_shop_edit_detail("cookie", 1, "")

    def test_empty_account_id_raises(self):
        """空 account_id 抛出异常。"""
        with pytest.raises(ValueError):
            fetch_fish_shop_edit_detail("cookie", 0, "123")


# ============================================================
# 安全：日志不泄露敏感信息
# ============================================================


class TestEditDetailLogSecurity:
    """日志安全测试。

    关键约束：
    - 不得记录 Cookie、_m_h5_tk、sign、Authorization
    - 不得记录完整商品正文、完整地址
    - 异常消息只暴露脱敏信息
    """

    def test_safe_str_truncates_in_log(self):
        """_safe_str 不改变原值（日志截断由调用方处理）。"""
        s = _safe_str("test_value")
        assert s == "test_value"

    def test_exception_message_does_not_contain_cookie(self, monkeypatch):
        """异常消息中不包含 Cookie。"""
        cookie_value = "super_secret_cookie_value_12345"

        def mock_post(url, headers, data, timeout):
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = Exception("Server Error")
            return mock_resp

        monkeypatch.setattr("requests.post", mock_post)
        monkeypatch.setattr(
            "app.services.fish_shop_publish._refresh_m_h5_tk",
            lambda c: c,
        )
        monkeypatch.setattr(
            "app.services.fish_shop_publish.extract_token_from_cookie",
            lambda c: "fake_token",
        )

        with pytest.raises(Exception) as exc_info:
            call_fish_shop_edit_detail(cookie_value, "123456")
        # 异常消息中不应包含完整 cookie
        assert cookie_value not in str(exc_info.value)


# ============================================================
# 工具函数：_safe_str_to_bool / _safe_int / _safe_str
# ============================================================


class TestSafeConversionFunctions:
    """安全转换函数测试。"""

    def test_safe_str_to_bool_various_inputs(self):
        """_safe_str_to_bool 处理各种输入。"""
        assert _safe_str_to_bool(True) is True
        assert _safe_str_to_bool(False) is False
        assert _safe_str_to_bool("true") is True
        assert _safe_str_to_bool("false") is False
        assert _safe_str_to_bool("TRUE") is True
        assert _safe_str_to_bool("FALSE") is False
        assert _safe_str_to_bool("1") is True
        assert _safe_str_to_bool("0") is False
        assert _safe_str_to_bool("yes") is True
        assert _safe_str_to_bool(None) is False
        assert _safe_str_to_bool("") is False

    def test_safe_int_various_inputs(self):
        """_safe_int 处理各种输入。"""
        assert _safe_int(100) == 100
        assert _safe_int("100") == 100
        assert _safe_int("100.9") == 100  # 截断
        assert _safe_int(100.9) == 100
        assert _safe_int(None) == 0
        assert _safe_int("") == 0
        assert _safe_int("abc") == 0
        assert _safe_int(True) == 1
        assert _safe_int(False) == 0

    def test_safe_int_with_minimum(self):
        """_safe_int 的 minimum 参数。"""
        assert _safe_int(-5, minimum=0) == 0
        assert _safe_int(10, minimum=0) == 10
        assert _safe_int("-5", minimum=0) == 0

    def test_safe_str_various_inputs(self):
        """_safe_str 处理各种输入。"""
        assert _safe_str(None) == ""
        assert _safe_str("test") == "test"
        assert _safe_str(123) == "123"
        assert _safe_str(True) == "True"
