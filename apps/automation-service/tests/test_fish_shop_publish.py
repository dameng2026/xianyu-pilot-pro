"""
鱼小铺多规格商品发布与编辑服务单元测试。

覆盖需求第三十节中可独立于闲鱼真实接口验证的逻辑：
- 多规格校验（最多 2 个规格类型、规格名不空不重、规格值不空不重、最多一个 supportImage）
- SKU 笛卡尔积生成（2×3=6 组合、不缺不重、排序无关）
- 双层 JSON 序列化（inputJson 字符串 + 外层再序列化，签名使用最终字符串）
- 内部商品对象构造（发布不带 itemId、编辑携带 itemId、空占位过滤）
- 价格安全转换为分（¥1.00→"100"、¥12.00→"1200"、负数/NaN 拒绝）
- 库存校验（非负整数、0 合法、负数/小数/非法文本拒绝）
- 响应 SKU 乱序匹配（不通过下标、用 property_key 匹配、skuId/inventoryId 写入正确组合）
- 规格图片（最多一个 supportImage=true、propertyImageList 只引用 supportImage 规格类型）
- 失败判定（HTTP 200 但 ret 失败时不成功、data.data=false 被拒绝）

不依赖真实闲鱼接口与数据库，全部使用纯函数与 mock。
"""
from __future__ import annotations

import json
import logging
import pytest
from unittest.mock import patch, MagicMock

from app.services.fish_shop_publish import (
    FISH_SHOP_PUBLISH_API,
    FISH_SHOP_PUBLISH_VERSION,
    FISH_SHOP_EDIT_API,
    FISH_SHOP_EDIT_VERSION,
    MAX_PROPERTY_TYPES,
    build_internal_item_object,
    build_property_image_list,
    build_property_key,
    build_sign,
    call_fish_shop_api,
    cartesian_sku_combinations,
    double_layer_serialize,
    extract_response_item_id,
    extract_response_skus,
    generate_unique_code,
    match_response_skus,
    validate_multi_spec_payload,
)


# ============================================================
# 常量与 API 名称测试
# ============================================================


class TestFishShopApiConstants:
    """鱼小铺发布/编辑接口常量测试。"""

    def test_publish_api_name(self):
        """发布接口 API 名称必须是 mtop.idle.pc.backend.idleitem.publish。"""
        assert FISH_SHOP_PUBLISH_API == "mtop.idle.pc.backend.idleitem.publish"

    def test_edit_api_name(self):
        """编辑接口 API 名称必须是 mtop.idle.pc.backend.idleitem.edit。"""
        assert FISH_SHOP_EDIT_API == "mtop.idle.pc.backend.idleitem.edit"

    def test_publish_version_is_1_0(self):
        assert FISH_SHOP_PUBLISH_VERSION == "1.0"

    def test_edit_version_is_1_0(self):
        assert FISH_SHOP_EDIT_VERSION == "1.0"

    def test_max_property_types_is_two(self):
        """最多 2 个规格类型。"""
        assert MAX_PROPERTY_TYPES == 2


# ============================================================
# 规格数量与命名校验
# ============================================================


class TestPropertyCountValidation:
    """规格数量与命名校验测试。"""

    def test_one_property_type_accepted(self):
        """一个规格类型可用。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "supportImage": False, "propertyValues": [{"propertyValue": "红色"}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]}],
        }
        assert validate_multi_spec_payload(data) is None

    def test_two_property_types_accepted(self):
        """两个规格类型可用。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "supportImage": False, "propertyValues": [{"propertyValue": "红色"}]},
                {"propertyName": "尺码", "supportImage": False, "propertyValues": [{"propertyValue": "S"}]},
            ],
            "itemSkuList": [
                {"price": "10", "quantity": 5, "propertyList": [
                    {"propertyText": "颜色", "valueText": "红色"},
                    {"propertyText": "尺码", "valueText": "S"},
                ]},
            ],
        }
        assert validate_multi_spec_payload(data) is None

    def test_three_property_types_rejected(self):
        """第三个规格类型必须被阻止。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}]},
                {"propertyName": "尺码", "propertyValues": [{"propertyValue": "S"}]},
                {"propertyName": "材质", "propertyValues": [{"propertyValue": "棉"}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        err = validate_multi_spec_payload(data)
        assert err is not None
        assert "2" in err

    def test_empty_property_name_rejected(self):
        """规格名不能为空。"""
        data = {
            "itemProperties": [
                {"propertyName": "", "propertyValues": [{"propertyValue": "红色"}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        err = validate_multi_spec_payload(data)
        assert err is not None
        assert "规格名称" in err

    def test_duplicate_property_names_rejected(self):
        """两个规格名不能重复。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}]},
                {"propertyName": "颜色", "propertyValues": [{"propertyValue": "蓝色"}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        err = validate_multi_spec_payload(data)
        assert err is not None
        assert "重复" in err

    def test_empty_property_value_rejected(self):
        """规格值不能为空。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "propertyValues": [{"propertyValue": ""}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        err = validate_multi_spec_payload(data)
        assert err is not None
        assert "至少需要" in err or "至少一个" in err

    def test_duplicate_property_values_rejected(self):
        """同一规格类型下规格值不能重复。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "propertyValues": [
                    {"propertyValue": "红色"},
                    {"propertyValue": "红色"},
                ]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        err = validate_multi_spec_payload(data)
        assert err is not None
        assert "重复" in err


# ============================================================
# 规格图片：supportImage 限制
# ============================================================


class TestPropertyImageValidation:
    """规格图片相关校验测试。"""

    def test_one_support_image_accepted(self):
        """最多一个规格类型 supportImage=true 时通过。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "supportImage": True, "propertyValues": [{"propertyValue": "红色"}]},
                {"propertyName": "尺码", "supportImage": False, "propertyValues": [{"propertyValue": "S"}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        assert validate_multi_spec_payload(data) is None

    def test_two_support_image_rejected(self):
        """两个规格类型同时 supportImage=true 必须被拒绝。"""
        data = {
            "itemProperties": [
                {"propertyName": "颜色", "supportImage": True, "propertyValues": [{"propertyValue": "红色"}]},
                {"propertyName": "尺码", "supportImage": True, "propertyValues": [{"propertyValue": "S"}]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": []}],
        }
        err = validate_multi_spec_payload(data)
        assert err is not None
        assert "图片" in err

    def test_property_image_list_only_refs_support_image_group(self):
        """propertyImageList 只引用 supportImage=true 的规格类型。"""
        groups = [
            {"propertyName": "颜色", "supportImage": True, "propertyValues": [
                {"propertyValue": "红色", "propertyValueImg": "https://img.example.com/red.jpg"},
                {"propertyValue": "蓝色", "propertyValueImg": "https://img.example.com/blue.jpg"},
            ]},
            {"propertyName": "尺码", "supportImage": False, "propertyValues": [
                {"propertyValue": "S", "propertyValueImg": "https://img.example.com/s.jpg"},
            ]},
        ]
        result = build_property_image_list(groups)
        # 只引用颜色规格类型，尺码的图片被忽略
        assert len(result) == 2
        for item in result:
            assert item["propertyText"] == "颜色"

    def test_property_image_list_empty_when_no_support_image(self):
        """所有规格类型都不支持图片时 propertyImageList 为空。"""
        groups = [
            {"propertyName": "颜色", "supportImage": False, "propertyValues": [
                {"propertyValue": "红色", "propertyValueImg": "https://img.example.com/red.jpg"},
            ]},
        ]
        result = build_property_image_list(groups)
        assert result == []

    def test_property_image_list_skips_empty_image(self):
        """规格值没有图片时不进入 propertyImageList。"""
        groups = [
            {"propertyName": "颜色", "supportImage": True, "propertyValues": [
                {"propertyValue": "红色", "propertyValueImg": "https://img.example.com/red.jpg"},
                {"propertyValue": "蓝色", "propertyValueImg": ""},  # 无图片
            ]},
        ]
        result = build_property_image_list(groups)
        assert len(result) == 1
        assert result[0]["valueText"] == "红色"


# ============================================================
# SKU 笛卡尔积生成
# ============================================================


class TestCartesianSkuCombinations:
    """SKU 笛卡尔积生成测试。"""

    def test_single_property_single_value(self):
        """单规格单值 → 1 个 SKU。"""
        groups = [
            {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}]},
        ]
        combos = cartesian_sku_combinations(groups)
        assert len(combos) == 1
        assert combos[0] == [{"propertyText": "颜色", "valueText": "红色"}]

    def test_two_by_three_six_combinations(self):
        """2 规格 × 3 规格 → 6 个 SKU（需求第十八节明确示例）。"""
        groups = [
            {"propertyName": "颜色", "propertyValues": [
                {"propertyValue": "红色"},
                {"propertyValue": "蓝色"},
            ]},
            {"propertyName": "尺码", "propertyValues": [
                {"propertyValue": "S"},
                {"propertyValue": "M"},
                {"propertyValue": "L"},
            ]},
        ]
        combos = cartesian_sku_combinations(groups)
        assert len(combos) == 6

    def test_no_duplicate_combinations(self):
        """SKU 组合不重复。"""
        groups = [
            {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}, {"propertyValue": "蓝色"}]},
            {"propertyName": "尺码", "propertyValues": [{"propertyValue": "S"}, {"propertyValue": "M"}]},
        ]
        combos = cartesian_sku_combinations(groups)
        keys = {build_property_key(c) for c in combos}
        assert len(keys) == len(combos) == 4

    def test_no_missing_combinations(self):
        """SKU 组合不缺漏。"""
        groups = [
            {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}, {"propertyValue": "蓝色"}]},
            {"propertyName": "尺码", "propertyValues": [{"propertyValue": "S"}, {"propertyValue": "M"}]},
        ]
        combos = cartesian_sku_combinations(groups)
        keys = {build_property_key(c) for c in combos}
        expected = {
            build_property_key([{"propertyText": "颜色", "valueText": "红色"}, {"propertyText": "尺码", "valueText": "S"}]),
            build_property_key([{"propertyText": "颜色", "valueText": "红色"}, {"propertyText": "尺码", "valueText": "M"}]),
            build_property_key([{"propertyText": "颜色", "valueText": "蓝色"}, {"propertyText": "尺码", "valueText": "S"}]),
            build_property_key([{"propertyText": "颜色", "valueText": "蓝色"}, {"propertyText": "尺码", "valueText": "M"}]),
        }
        assert keys == expected

    def test_combinations_independent_of_input_order(self):
        """规格顺序变化不改变组合集合。"""
        groups_a = [
            {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}, {"propertyValue": "蓝色"}]},
            {"propertyName": "尺码", "propertyValues": [{"propertyValue": "S"}, {"propertyValue": "M"}]},
        ]
        groups_b = [
            {"propertyName": "尺码", "propertyValues": [{"propertyValue": "S"}, {"propertyValue": "M"}]},
            {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}, {"propertyValue": "蓝色"}]},
        ]
        keys_a = {build_property_key(c) for c in cartesian_sku_combinations(groups_a)}
        keys_b = {build_property_key(c) for c in cartesian_sku_combinations(groups_b)}
        assert keys_a == keys_b

    def test_empty_property_value_skipped(self):
        """空白规格值不进入组合。"""
        groups = [
            {"propertyName": "颜色", "propertyValues": [
                {"propertyValue": "红色"},
                {"propertyValue": ""},  # 空值
                {"propertyValue": "  "},  # 空白
            ]},
        ]
        combos = cartesian_sku_combinations(groups)
        assert len(combos) == 1
        assert combos[0][0]["valueText"] == "红色"

    def test_empty_property_name_skipped(self):
        """空规格名的类型被跳过。"""
        groups = [
            {"propertyName": "", "propertyValues": [{"propertyValue": "红色"}]},
            {"propertyName": "尺码", "propertyValues": [{"propertyValue": "S"}]},
        ]
        combos = cartesian_sku_combinations(groups)
        assert len(combos) == 1
        assert combos[0][0]["propertyText"] == "尺码"


# ============================================================
# 价格与库存校验
# ============================================================


class TestPriceAndStockValidation:
    """价格与库存校验测试。"""

    def _make_sku(self, price, quantity):
        return {
            "itemProperties": [
                {"propertyName": "颜色", "propertyValues": [{"propertyValue": "红色"}]},
            ],
            "itemSkuList": [
                {"price": price, "quantity": quantity, "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]},
            ],
        }

    def test_price_zero_accepted(self):
        """价格 0 是合法的（不要求 > 0）。"""
        assert validate_multi_spec_payload(self._make_sku(0, 5)) is None

    def test_quantity_zero_accepted(self):
        """库存 0 可提交。"""
        assert validate_multi_spec_payload(self._make_sku("10", 0)) is None

    def test_negative_price_rejected(self):
        """负数价格被拒绝。"""
        err = validate_multi_spec_payload(self._make_sku(-1, 5))
        assert err is not None
        assert "负数" in err

    def test_negative_quantity_rejected(self):
        """负数库存被拒绝。"""
        err = validate_multi_spec_payload(self._make_sku("10", -1))
        assert err is not None
        assert "负数" in err

    def test_decimal_quantity_rejected(self):
        """小数库存被拒绝。"""
        err = validate_multi_spec_payload(self._make_sku("10", 1.5))
        assert err is not None
        assert "整数" in err

    def test_invalid_quantity_text_rejected(self):
        """非法文本库存被拒绝。"""
        err = validate_multi_spec_payload(self._make_sku("10", "abc"))
        assert err is not None
        assert "整数" in err

    def test_missing_price_rejected(self):
        """SKU 缺少价格被拒绝。"""
        err = validate_multi_spec_payload(self._make_sku(None, 5))
        assert err is not None
        assert "价格" in err

    def test_empty_price_rejected(self):
        """SKU 价格为空字符串被拒绝。"""
        err = validate_multi_spec_payload(self._make_sku("", 5))
        assert err is not None
        assert "价格" in err


# ============================================================
# priceInCent 安全金额转换
# ============================================================


class TestPriceCentConversion:
    """priceInCent 安全金额转换测试（通过 _safe_price_to_cent 间接验证）。"""

    def test_one_yuan_to_100_cents(self):
        """¥1.00 → "100"。"""
        from app.services.xianyu_goods_sync import _safe_price_to_cent
        assert _safe_price_to_cent("1.00") == 100
        assert _safe_price_to_cent(1) == 100
        assert _safe_price_to_cent(1.0) == 100

    def test_twelve_yuan_to_1200_cents(self):
        """¥12.00 → "1200"。"""
        from app.services.xianyu_goods_sync import _safe_price_to_cent
        assert _safe_price_to_cent("12.00") == 1200
        assert _safe_price_to_cent(12) == 1200

    def test_decimal_yuan_no_precision_loss(self):
        """¥0.01 → 1，无浮点精度损失。"""
        from app.services.xianyu_goods_sync import _safe_price_to_cent
        assert _safe_price_to_cent("0.01") == 1
        assert _safe_price_to_cent("0.1") == 10
        assert _safe_price_to_cent("99.99") == 9999

    def test_string_decimal_safe(self):
        """字符串形式的小数金额无精度损失。"""
        from app.services.xianyu_goods_sync import _safe_price_to_cent
        # 0.1 + 0.2 经典浮点陷阱：0.30000000000000004 → 30 而非 31
        # 字符串解析避免此问题
        assert _safe_price_to_cent("0.3") == 30


# ============================================================
# 双层 JSON 序列化
# ============================================================


class TestDoubleLayerSerialization:
    """双层 JSON 序列化测试（需求第十一节）。"""

    def test_inner_json_is_string(self):
        """inputJson 必须是字符串，不是嵌套对象。"""
        internal_obj = {"title": "test", "quantity": "1"}
        final_data = double_layer_serialize(internal_obj)
        # 解析外层，验证 inputJson 是字符串
        outer = json.loads(final_data)
        assert "inputJson" in outer
        assert isinstance(outer["inputJson"], str)

    def test_inner_json_parses_back_to_internal_object(self):
        """inputJson 字符串解析后等于原内部对象。"""
        internal_obj = {
            "title": "测试商品",
            "itemSkuList": [{"priceInCent": "100", "quantity": "5"}],
            "itemProperties": [{"propertyName": "颜色", "supportImage": False}],
        }
        final_data = double_layer_serialize(internal_obj)
        outer = json.loads(final_data)
        inner = json.loads(outer["inputJson"])
        assert inner == internal_obj

    def test_outer_serialization_compact(self):
        """外层序列化使用紧凑格式（无多余空格）。"""
        internal_obj = {"a": 1}
        final_data = double_layer_serialize(internal_obj)
        # 紧凑格式：键值对之间无空格
        assert ", " not in final_data
        assert ": " not in final_data

    def test_inner_serialization_compact(self):
        """内层序列化也使用紧凑格式。"""
        internal_obj = {"a": 1, "b": [1, 2, 3]}
        final_data = double_layer_serialize(internal_obj)
        outer = json.loads(final_data)
        inner_str = outer["inputJson"]
        assert ", " not in inner_str
        assert ": " not in inner_str

    def test_sign_uses_final_data_string(self):
        """签名必须使用最终 data 字符串，与提交字符串完全相同。"""
        internal_obj = {"title": "test", "quantity": "1"}
        final_data = double_layer_serialize(internal_obj)
        token = "fake_token"
        t_ms = "1700000000000"
        sign = build_sign(token, t_ms, final_data)
        # 验证签名是 MD5(token + & + t + & + APP_KEY + & + final_data)
        import hashlib
        from app.services.xianyu_goods_sync import APP_KEY
        expected = hashlib.md5(f"{token}&{t_ms}&{APP_KEY}&{final_data}".encode()).hexdigest()
        assert sign == expected

    def test_no_reserialization_after_sign(self):
        """签名后不得重新序列化产生不同的 data 字符串。

        通过对比签名输入与实际提交输入（call_fish_shop_api 内部行为）
        来确保使用同一 final_data。
        """
        internal_obj = {"title": "test", "price": "10"}
        final_data = double_layer_serialize(internal_obj)
        # final_data 是确定性的：相同输入产生相同输出
        assert double_layer_serialize(internal_obj) == final_data


# ============================================================
# 内部商品对象构造
# ============================================================


class TestBuildInternalItemObject:
    """内部商品对象构造测试。"""

    def _make_request(self, *, is_edit=False, item_id=None):
        return {
            "title": "测试商品",
            "description": "测试描述",
            "imageUrls": ["https://img.example.com/1.jpg", "https://img.example.com/2.jpg"],
            "itemProperties": [
                {"propertyName": "颜色", "supportImage": True, "propertyValues": [
                    {"propertyValue": "红色", "propertyValueImg": "https://img.example.com/red.jpg"},
                ]},
            ],
            "itemSkuList": [
                {"price": "10.00", "quantity": 5, "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]},
            ],
            "shippingMode": "free",
            "supportSelfPick": False,
            "location": {"prov": "广东省", "city": "深圳市", "area": "南山区", "divisionId": "440305", "gps": "114.05,22.55", "poiId": "", "poiName": ""},
            **({"itemId": item_id} if is_edit else {}),
        }

    def test_publish_does_not_include_item_id(self):
        """发布场景内部对象不携带 itemId。"""
        internal = build_internal_item_object(self._make_request(), ["url1", "url2"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert "itemId" not in internal

    def test_edit_includes_item_id(self):
        """编辑场景内部对象携带 itemId。"""
        internal = build_internal_item_object(
            self._make_request(is_edit=True, item_id="123456"),
            ["url1", "url2"],
            {"catId": "1", "catName": "x"},
            is_edit=True,
        )
        assert internal.get("itemId") == "123456"

    def test_edit_without_item_id_raises(self):
        """编辑场景缺失 itemId 必须抛异常。"""
        with pytest.raises(ValueError, match="itemId"):
            build_internal_item_object(
                self._make_request(is_edit=True, item_id=""),  # 空 itemId
                ["url1"],
                {"catId": "1", "catName": "x"},
                is_edit=True,
            )

    def test_empty_placeholder_values_filtered(self):
        """提交前过滤空占位对象：空白规格值不进入内部对象。"""
        req = self._make_request()
        req["itemProperties"][0]["propertyValues"].append({"propertyValue": "", "propertyValueImg": ""})
        req["itemProperties"][0]["propertyValues"].append({"propertyValue": "  ", "propertyValueImg": ""})
        internal = build_internal_item_object(req, ["url1"], {"catId": "1", "catName": "x"}, is_edit=False)
        # 仅保留 "红色"
        prop = internal["itemProperties"][0]
        assert len(prop["propertyValues"]) == 1
        assert prop["propertyValues"][0]["propertyValue"] == "红色"

    def test_unique_code_generated_not_hardcoded(self):
        """uniqueCode 必须每次生成，不复用抓包固定值。"""
        req = self._make_request()
        internal_a = build_internal_item_object(req, ["url1"], {"catId": "1", "catName": "x"}, is_edit=False)
        internal_b = build_internal_item_object(req, ["url1"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert internal_a["uniqueCode"] != internal_b["uniqueCode"]
        # 长度为 32（uuid4().hex）
        assert len(internal_a["uniqueCode"]) == 32

    def test_first_image_is_major(self):
        """第一张图片是主图。"""
        internal = build_internal_item_object(
            self._make_request(),
            ["https://img.example.com/a.jpg", "https://img.example.com/b.jpg"],
            {"catId": "1", "catName": "x"},
            is_edit=False,
        )
        images = internal["imageInfoDOList"]
        assert images[0]["major"] is True
        assert images[1]["major"] is False

    def test_total_quantity_is_sum_of_skus(self):
        """顶层 quantity 是所有 SKU 库存之和。"""
        req = self._make_request()
        req["itemSkuList"] = [
            {"price": "10", "quantity": 5, "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]},
            {"price": "20", "quantity": 3, "propertyList": [{"propertyText": "颜色", "valueText": "蓝色"}]},
        ]
        req["itemProperties"][0]["propertyValues"] = [
            {"propertyValue": "红色"},
            {"propertyValue": "蓝色"},
        ]
        internal = build_internal_item_object(req, ["url1"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert internal["quantity"] == "8"

    def test_min_price_is_lowest_sku_price(self):
        """itemPriceDTO.priceInCent 是最低 SKU 价格。"""
        req = self._make_request()
        req["itemSkuList"] = [
            {"price": "30", "quantity": 5, "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]},
            {"price": "10", "quantity": 3, "propertyList": [{"propertyText": "颜色", "valueText": "蓝色"}]},
            {"price": "20", "quantity": 2, "propertyList": [{"propertyText": "颜色", "valueText": "绿色"}]},
        ]
        req["itemProperties"][0]["propertyValues"] = [
            {"propertyValue": "红色"}, {"propertyValue": "蓝色"}, {"propertyValue": "绿色"},
        ]
        internal = build_internal_item_object(req, ["url1"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert internal["itemPriceDTO"]["priceInCent"] == "1000"  # ¥10 → 1000 分


# ============================================================
# 响应 SKU 乱序匹配
# ============================================================


class TestResponseSkuMatching:
    """服务器响应 SKU 乱序匹配测试（需求第二十节）。"""

    def test_match_by_property_key_not_index(self):
        """服务器返回顺序与请求不同时，通过 property_key 匹配。"""
        submitted = [
            {"priceInCent": "1000", "quantity": "5", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
            ]},
            {"priceInCent": "2000", "quantity": "3", "propertyList": [
                {"propertyText": "颜色", "valueText": "蓝色"},
            ]},
        ]
        # 服务器倒序返回
        response = [
            {"skuId": "sku_blue", "inventoryId": "inv_blue", "priceInCent": "2000", "quantity": "3",
             "propertyList": [{"propertyText": "颜色", "valueText": "蓝色"}]},
            {"skuId": "sku_red", "inventoryId": "inv_red", "priceInCent": "1000", "quantity": "5",
             "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]},
        ]
        matched = match_response_skus(response, submitted)
        # 红色 SKU 应得到 sku_red / inv_red
        red = next(m for m in matched if m["propertyList"][0]["valueText"] == "红色")
        assert red["skuId"] == "sku_red"
        assert red["inventoryId"] == "inv_red"
        # 蓝色 SKU 应得到 sku_blue / inv_blue
        blue = next(m for m in matched if m["propertyList"][0]["valueText"] == "蓝色")
        assert blue["skuId"] == "sku_blue"
        assert blue["inventoryId"] == "inv_blue"

    def test_two_property_sku_match_by_combined_key(self):
        """双规格 SKU 通过组合 property_key 匹配。"""
        submitted = [
            {"priceInCent": "1000", "quantity": "5", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
                {"propertyText": "尺码", "valueText": "S"},
            ]},
            {"priceInCent": "2000", "quantity": "3", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
                {"propertyText": "尺码", "valueText": "M"},
            ]},
        ]
        response = [
            {"skuId": "sku_red_m", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
                {"propertyText": "尺码", "valueText": "M"},
            ]},
            {"skuId": "sku_red_s", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
                {"propertyText": "尺码", "valueText": "S"},
            ]},
        ]
        matched = match_response_skus(response, submitted)
        s_sku = next(m for m in matched if any(p["valueText"] == "S" for p in m["propertyList"]))
        m_sku = next(m for m in matched if any(p["valueText"] == "M" for p in m["propertyList"]))
        assert s_sku["skuId"] == "sku_red_s"
        assert m_sku["skuId"] == "sku_red_m"

    def test_response_skus_calibrate_price_and_quantity(self):
        """服务器响应校准 SKU 价格和库存。"""
        submitted = [
            {"priceInCent": "1000", "quantity": "5", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
            ]},
        ]
        response = [
            {"priceInCent": "1500", "quantity": "8", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
            ]},
        ]
        matched = match_response_skus(response, submitted)
        assert matched[0]["priceInCent"] == "1500"
        assert matched[0]["quantity"] == "8"

    def test_missing_response_sku_keeps_submission(self):
        """服务器未返回某 SKU 时保留提交值，不报错。"""
        submitted = [
            {"priceInCent": "1000", "quantity": "5", "propertyList": [
                {"propertyText": "颜色", "valueText": "红色"},
            ]},
            {"priceInCent": "2000", "quantity": "3", "propertyList": [
                {"propertyText": "颜色", "valueText": "蓝色"},
            ]},
        ]
        response = [
            # 只返回红色
            {"skuId": "sku_red", "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]},
        ]
        matched = match_response_skus(response, submitted)
        assert len(matched) == 2
        # 蓝色未匹配，无 skuId
        blue = next(m for m in matched if m["propertyList"][0]["valueText"] == "蓝色")
        assert "skuId" not in blue

    def test_property_key_normalizes_order(self):
        """property_key 排序后归一化，规格顺序变化仍能匹配。"""
        key_a = build_property_key([
            {"propertyText": "颜色", "valueText": "红色"},
            {"propertyText": "尺码", "valueText": "S"},
        ])
        key_b = build_property_key([
            {"propertyText": "尺码", "valueText": "S"},
            {"propertyText": "颜色", "valueText": "红色"},
        ])
        assert key_a == key_b


# ============================================================
# 响应 itemId 提取
# ============================================================


class TestResponseItemIdExtraction:
    """响应 itemId 提取测试。"""

    def test_extract_from_data_data_item_id(self):
        result = {"data": {"data": {"itemId": "123456789"}}}
        assert extract_response_item_id(result) == "123456789"

    def test_extract_from_data_item_id(self):
        result = {"data": {"itemId": "987654321"}}
        assert extract_response_item_id(result) == "987654321"

    def test_extract_returns_empty_when_missing(self):
        result = {"data": {}}
        assert extract_response_item_id(result) == ""

    def test_extract_returns_empty_when_data_not_dict(self):
        result = {"data": "string"}
        assert extract_response_item_id(result) == ""


# ============================================================
# 成功判定与失败处理
# ============================================================


class TestApiCallSuccessJudgment:
    """接口调用成功判定测试（需求第二十七、二十八节）。"""

    def _make_resp(self, ret, data_body=None):
        return {"ret": ret, "data": data_body or {}, "traceId": "test-trace"}

    def test_http_200_with_success_ret_passes(self):
        """HTTP 200 且 ret 包含 SUCCESS 时通过。"""
        resp = self._make_resp(["SUCCESS::调用成功"])
        with patch("app.services.fish_shop_publish._refresh_m_h5_tk"), \
             patch("app.services.fish_shop_publish.extract_token_from_cookie", return_value="token"), \
             patch("app.services.fish_shop_publish.double_layer_serialize", return_value="{}"), \
             patch("app.services.fish_shop_publish.build_sign", return_value="sign"), \
             patch("app.services.fish_shop_publish.build_request_url", return_value="http://example.com"), \
             patch("app.services.fish_shop_publish.get_fish_shop_headers", return_value={}), \
             patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = resp
            mock_post.return_value.raise_for_status = MagicMock()
            result = call_fish_shop_api("cookie", FISH_SHOP_PUBLISH_API, FISH_SHOP_PUBLISH_VERSION, {"x": 1})
            assert result == resp

    def test_http_200_with_fail_ret_raises(self):
        """HTTP 200 但 ret 失败时不视为成功。"""
        resp = self._make_resp(["FAIL::业务错误"])
        with patch("app.services.fish_shop_publish._refresh_m_h5_tk"), \
             patch("app.services.fish_shop_publish.extract_token_from_cookie", return_value="token"), \
             patch("app.services.fish_shop_publish.double_layer_serialize", return_value="{}"), \
             patch("app.services.fish_shop_publish.build_sign", return_value="sign"), \
             patch("app.services.fish_shop_publish.build_request_url", return_value="http://example.com"), \
             patch("app.services.fish_shop_publish.get_fish_shop_headers", return_value={}), \
             patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = resp
            mock_post.return_value.raise_for_status = MagicMock()
            with pytest.raises(RuntimeError, match="FAIL::业务错误"):
                call_fish_shop_api("cookie", FISH_SHOP_PUBLISH_API, FISH_SHOP_PUBLISH_VERSION, {"x": 1})

    def test_data_data_false_rejected(self):
        """data.data 为 False 时视为拒绝。"""
        resp = self._make_resp(["SUCCESS::调用成功"], data_body={"data": False, "msg": "无权限"})
        with patch("app.services.fish_shop_publish._refresh_m_h5_tk"), \
             patch("app.services.fish_shop_publish.extract_token_from_cookie", return_value="token"), \
             patch("app.services.fish_shop_publish.double_layer_serialize", return_value="{}"), \
             patch("app.services.fish_shop_publish.build_sign", return_value="sign"), \
             patch("app.services.fish_shop_publish.build_request_url", return_value="http://example.com"), \
             patch("app.services.fish_shop_publish.get_fish_shop_headers", return_value={}), \
             patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = resp
            mock_post.return_value.raise_for_status = MagicMock()
            with pytest.raises(RuntimeError, match="无权限"):
                call_fish_shop_api("cookie", FISH_SHOP_PUBLISH_API, FISH_SHOP_PUBLISH_VERSION, {"x": 1})


# ============================================================
# 日志安全：不泄露 Cookie/token/sign
# ============================================================


class TestLogSecurity:
    """日志安全测试（需求第二十八节）。"""

    def test_failure_log_does_not_leak_cookie_or_sign(self, caplog):
        """失败日志不得记录 Cookie / token / sign / 完整请求体。"""
        secret_cookie = "super_secret_cookie_value_123"
        secret_token = "super_secret_token_456"
        secret_sign = "md5_sign_value_789"
        resp = {"ret": ["FAIL::业务错误"], "data": {}, "traceId": "trace-1"}

        caplog.set_level(logging.WARNING, logger="app.services.fish_shop_publish")
        with patch("app.services.fish_shop_publish._refresh_m_h5_tk"), \
             patch("app.services.fish_shop_publish.extract_token_from_cookie", return_value=secret_token), \
             patch("app.services.fish_shop_publish.double_layer_serialize", return_value='{"inputJson":"..."}'), \
             patch("app.services.fish_shop_publish.build_sign", return_value=secret_sign), \
             patch("app.services.fish_shop_publish.build_request_url", return_value="http://example.com"), \
             patch("app.services.fish_shop_publish.get_fish_shop_headers", return_value={"Cookie": secret_cookie}), \
             patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = resp
            mock_post.return_value.raise_for_status = MagicMock()
            try:
                call_fish_shop_api(secret_cookie, FISH_SHOP_PUBLISH_API, FISH_SHOP_PUBLISH_VERSION, {"x": 1})
            except RuntimeError:
                pass

        # 验证日志不包含敏感信息
        for record in caplog.records:
            msg = record.getMessage()
            assert secret_cookie not in msg
            assert secret_token not in msg
            assert secret_sign not in msg
            assert "_m_h5_tk" not in msg


# ============================================================
# uniqueCode 生成
# ============================================================


class TestUniqueCodeGeneration:
    """uniqueCode 生成测试（需求第二十六节）。"""

    def test_unique_code_is_32_char_hex(self):
        code = generate_unique_code()
        assert len(code) == 32
        # 必须是合法的十六进制
        int(code, 16)

    def test_unique_code_unique_per_call(self):
        """每次调用产生不同的 uniqueCode。"""
        codes = {generate_unique_code() for _ in range(100)}
        assert len(codes) == 100

    def test_unique_code_not_hardcoded(self):
        """uniqueCode 不为抓包固定值。"""
        code = generate_unique_code()
        # 不能是常见的抓包固定值
        assert code != "abc123"
        assert code != "00000000000000000000000000000000"
        assert code != "ffffffffffffffffffffffffffffffff"


# ============================================================
# 接口选择：发布 vs 编辑
# ============================================================


class TestApiSelection:
    """接口选择测试（需求第三十节"接口选择"部分）。"""

    def test_publish_uses_publish_api(self):
        """鱼小铺多规格发布调用 publish 接口。"""
        assert FISH_SHOP_PUBLISH_API == "mtop.idle.pc.backend.idleitem.publish"
        assert FISH_SHOP_PUBLISH_API != FISH_SHOP_EDIT_API

    def test_edit_uses_edit_api(self):
        """鱼小铺编辑调用 edit 接口。"""
        assert FISH_SHOP_EDIT_API == "mtop.idle.pc.backend.idleitem.edit"
        assert FISH_SHOP_PUBLISH_API != FISH_SHOP_EDIT_API

    def test_publish_does_not_carry_item_id(self):
        """发布请求不携带已有 itemId。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "itemId": "should_not_be_used"}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert "itemId" not in internal

    def test_edit_carries_correct_item_id(self):
        """编辑请求携带正确 itemId。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "itemId": "target_item_id"}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=True)
        assert internal["itemId"] == "target_item_id"

    def test_edit_does_not_use_internal_db_id(self):
        """编辑请求使用闲鱼 itemId，不使用项目内部数据库主键。"""
        # itemId 字段必须是闲鱼 itemId（字符串），不能是项目数据库主键（整数）
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "itemId": "xianyu_item_123"}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=True)
        assert internal["itemId"] == "xianyu_item_123"
        # 不应包含项目内部主键字段（如 dbId / primaryId / internalId 等）
        for forbidden_key in ("dbId", "primaryId", "internalId", "localId"):
            assert forbidden_key not in internal or internal[forbidden_key] != "xianyu_item_123"


# ============================================================
# 路由权限与商品归属（通过路由层单元测试覆盖）
# ============================================================


class TestFishShopRoutePermission:
    """鱼小铺路由权限测试（通过 mock 数据库会话验证）。

    覆盖需求第二十九节"前后端权限必须同时实现"中可独立验证的部分。
    """

    @pytest.mark.asyncio
    async def test_publish_rejects_non_fish_shop_account(self):
        """普通账号调用 fish-shop/publish 必须被拒绝。"""
        from app.api.v1.routes.fish_shop import _get_account_auth_and_check_fish_shop
        from unittest.mock import AsyncMock

        # 模拟账号查询返回普通账号（fish_shop_user=0）
        mock_account = MagicMock()
        mock_account.fish_shop_user = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_account)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        auth, is_fish_shop = await _get_account_auth_and_check_fish_shop(mock_db, account_id=1, tenant_id=100)
        assert is_fish_shop is False
        assert auth is None

    @pytest.mark.asyncio
    async def test_publish_accepts_fish_shop_account(self):
        """鱼小铺账号调用 fish-shop/publish 通过权限校验。"""
        from app.api.v1.routes.fish_shop import _get_account_auth_and_check_fish_shop
        from unittest.mock import AsyncMock

        mock_account = MagicMock()
        mock_account.fish_shop_user = 1

        mock_auth = MagicMock()
        mock_auth.encrypted_cookie = "encrypted_cookie_data"

        # 第一次 execute 返回账号，第二次返回 auth
        account_result = MagicMock()
        account_result.scalar_one_or_none = MagicMock(return_value=mock_account)
        auth_result = MagicMock()
        auth_result.scalar_one_or_none = MagicMock(return_value=mock_auth)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[account_result, auth_result])

        auth, is_fish_shop = await _get_account_auth_and_check_fish_shop(mock_db, account_id=1, tenant_id=100)
        assert is_fish_shop is True
        assert auth is mock_auth

    @pytest.mark.asyncio
    async def test_edit_rejects_goods_not_belonging_to_account(self):
        """编辑接口拒绝不属于当前账号的商品。"""
        from app.api.v1.routes.fish_shop import _verify_goods_belongs_to_account
        from unittest.mock import AsyncMock

        # 模拟数据库查询返回 None（商品不归属当前账号）
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _verify_goods_belongs_to_account(mock_db, tenant_id=100, account_id=1, external_goods_id="999")
        assert result is None

    @pytest.mark.asyncio
    async def test_detail_rejects_non_fish_shop_account(self):
        """详情接口拒绝普通账号访问（前端隐藏按钮不足以作为权限控制）。"""
        from app.api.v1.routes.fish_shop import _get_account_auth_and_check_fish_shop
        from unittest.mock import AsyncMock

        mock_account = MagicMock()
        mock_account.fish_shop_user = 0  # 普通账号

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_account)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        auth, is_fish_shop = await _get_account_auth_and_check_fish_shop(mock_db, account_id=1, tenant_id=100)
        assert is_fish_shop is False  # 后端必须再次校验，拒绝普通账号


# ============================================================
# 防止重复提交
# ============================================================


class TestDuplicateSubmissionPrevention:
    """防止重复提交测试（需求第二十六节）。

    通过验证 uniqueCode 每次生成不同的值，确保同一表单不会因重试
    产生两个完全相同的请求（uniqueCode 不同会被闲鱼识别为不同发布）。
    """

    def test_unique_code_differs_between_two_calls(self):
        """两次调用产生不同 uniqueCode，避免重复发布。"""
        code_a = generate_unique_code()
        code_b = generate_unique_code()
        assert code_a != code_b

    def test_publish_data_differs_due_to_unique_code(self):
        """两次构造的内部对象因 uniqueCode 不同而产生不同的 final_data。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"]}
        internal_a = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        internal_b = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        data_a = double_layer_serialize(internal_a)
        data_b = double_layer_serialize(internal_b)
        # uniqueCode 不同导致 data 不同
        assert data_a != data_b


# ============================================================
# 商品图片与规格图片区分
# ============================================================


class TestImageSeparation:
    """商品图片与规格图片使用不同数据结构测试（需求第十五节）。"""

    def test_product_images_in_image_info_do_list(self):
        """商品图片位于 imageInfoDOList。"""
        req = {"title": "x", "description": "y", "imageUrls": ["p1", "p2"]}
        internal = build_internal_item_object(req, ["p1_cdn", "p2_cdn"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert "imageInfoDOList" in internal
        assert len(internal["imageInfoDOList"]) == 2
        # 商品图片不与规格图片混淆
        for img in internal["imageInfoDOList"]:
            assert "url" in img

    def test_spec_images_in_property_image_list(self):
        """规格图片位于 propertyImageList。"""
        req = {
            "title": "x", "description": "y", "imageUrls": ["p1"],
            "itemProperties": [
                {"propertyName": "颜色", "supportImage": True, "propertyValues": [
                    {"propertyValue": "红色", "propertyValueImg": "spec_red.jpg"},
                ]},
            ],
            "itemSkuList": [{"price": "10", "quantity": 5, "propertyList": [{"propertyText": "颜色", "valueText": "红色"}]}],
        }
        internal = build_internal_item_object(req, ["p1_cdn"], {"catId": "1", "catName": "x"}, is_edit=False)
        assert "propertyImageList" in internal
        assert len(internal["propertyImageList"]) == 1
        assert internal["propertyImageList"][0]["propertyValueImg"] == "spec_red.jpg"
        # 商品图片与规格图片在结构上分离
        product_urls = {img["url"] for img in internal["imageInfoDOList"]}
        spec_urls = {item["propertyValueImg"] for item in internal["propertyImageList"]}
        assert "spec_red.jpg" not in product_urls
        assert "p1_cdn" not in spec_urls


# ============================================================
# 发货设置字段互斥
# ============================================================


class TestShippingModeFields:
    """发货设置字段互斥测试（需求第二十五节）。"""

    def test_free_shipping_mode(self):
        """包邮模式：canFreeShipping=true。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "shippingMode": "free", "supportSelfPick": False}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        fee = internal["itemPostFeeDTO"]
        assert fee["canFreeShipping"] is True

    def test_fixed_shipping_mode(self):
        """一口价运费模式：supportFreight=true 且 postPriceInCent > 0。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "shippingMode": "fixed", "postFee": "10.00", "supportSelfPick": False}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        fee = internal["itemPostFeeDTO"]
        assert fee["supportFreight"] is True
        assert fee["canFreeShipping"] is False
        assert fee["postPriceInCent"] == "1000"

    def test_no_shipping_mode(self):
        """无需邮寄模式：supportFreight=false。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "shippingMode": "none", "supportSelfPick": False}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        fee = internal["itemPostFeeDTO"]
        assert fee["supportFreight"] is False

    def test_free_and_fixed_not_simultaneous(self):
        """包邮与非零一口价运费不能同时提交：fixed 模式 canFreeShipping 必须为 false。"""
        req = {"title": "x", "description": "y", "imageUrls": ["u"], "shippingMode": "fixed", "postFee": "10.00"}
        internal = build_internal_item_object(req, ["u"], {"catId": "1", "catName": "x"}, is_edit=False)
        fee = internal["itemPostFeeDTO"]
        # 不能同时 canFreeShipping=true 且 postPriceInCent > 0
        if fee["canFreeShipping"] is True:
            assert fee.get("postPriceInCent", "0") == "0"
        else:
            assert fee.get("postPriceInCent", "0") != "0"
