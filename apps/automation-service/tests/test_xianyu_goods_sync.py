"""
商品同步服务单元测试。
测试签名、数据解析、增量比较等核心逻辑。
"""
import hashlib
import pytest
import json
from unittest.mock import patch, MagicMock

from app.services.xianyu_goods_sync import (
    _build_sign,
    _parse_cookie,
    _get_token_from_cookie,
    _parse_item_list_response,
    _parse_item_detail_response,
    _parse_card_to_goods,
    _is_goods_changed,
    _merge_detail_info,
    _build_goods_insert_values,
    _build_goods_update_values,
    APP_KEY,
)


class TestBuildSign:
    """签名算法测试"""

    def test_build_sign_basic(self):
        token = "abc123"
        timestamp = 1700000000000
        data_json = '{"pageNum":1}'
        sign = _build_sign(token, timestamp, data_json)
        expected_raw = f"{token}&{timestamp}&{APP_KEY}&{data_json}"
        expected = hashlib.md5(expected_raw.encode()).hexdigest()
        assert sign == expected

    def test_build_sign_consistent(self):
        """相同输入产生相同签名"""
        token = "test_token"
        ts = 1234567890
        data = '{"key":"value"}'
        sign1 = _build_sign(token, ts, data)
        sign2 = _build_sign(token, ts, data)
        assert sign1 == sign2

    def test_build_sign_different_data(self):
        """不同数据产生不同签名"""
        token = "test_token"
        ts = 1234567890
        sign1 = _build_sign(token, ts, '{"a":1}')
        sign2 = _build_sign(token, ts, '{"a":2}')
        assert sign1 != sign2


class TestParseCookie:
    """Cookie 解析测试"""

    def test_parse_cookie_basic(self):
        cookie_str = "unb=12345; _m_h5_tk=abc_123; session=xyz"
        result = _parse_cookie(cookie_str)
        assert result["unb"] == "12345"
        assert result["_m_h5_tk"] == "abc_123"
        assert result["session"] == "xyz"

    def test_parse_cookie_empty(self):
        assert _parse_cookie("") == {}
        assert _parse_cookie(None) == {}

    def test_parse_cookie_with_spaces(self):
        cookie_str = "  unb=12345  ;  _m_h5_tk=abc_123  "
        result = _parse_cookie(cookie_str)
        assert result["unb"] == "12345"
        assert result["_m_h5_tk"] == "abc_123"

    def test_get_token_from_cookie(self):
        cookie_str = "_m_h5_tk=token_1234567890; unb=user1"
        token = _get_token_from_cookie(cookie_str)
        assert token == "token"

    def test_get_token_from_cookie_missing(self):
        cookie_str = "unb=user1; session=xyz"
        token = _get_token_from_cookie(cookie_str)
        assert token is None


class TestParseItemListResponse:
    """商品列表响应解析测试"""

    def test_parse_success_response(self):
        response = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "cardList": [
                    {
                        "cardData": {
                            "itemId": "12345",
                            "title": "测试商品",
                            "price": "99.00",
                            "itemStatus": 1,
                        }
                    },
                    {
                        "cardData": {
                            "itemId": "67890",
                            "title": "测试商品2",
                            "price": "199.00",
                            "itemStatus": 3,
                        }
                    },
                ]
            },
        }
        items = _parse_item_list_response(response)
        assert len(items) == 2
        assert items[0]["itemId"] == "12345"
        assert items[0]["title"] == "测试商品"
        assert items[1]["itemId"] == "67890"

    def test_parse_empty_response(self):
        response = {"ret": ["SUCCESS::调用成功"], "data": {"cardList": []}}
        items = _parse_item_list_response(response)
        assert items == []

    def test_parse_rgv587_error(self):
        response = {"ret": ["RGV587::风控"]}
        with pytest.raises(RuntimeError, match="风控"):
            _parse_item_list_response(response)

    def test_parse_token_expired_error(self):
        response = {"ret": ["FAIL_SYS_TOKEN_EXOIRED::令牌过期"]}
        with pytest.raises(RuntimeError, match="Token"):
            _parse_item_list_response(response)

    def test_parse_token_expired_alias_error(self):
        response = {"ret": ["FAIL_SYS_TOKEN_EXPIRED::Token过期"]}
        with pytest.raises(RuntimeError, match="Token"):
            _parse_item_list_response(response)

    def test_parse_other_error(self):
        response = {"ret": ["FAIL::未知错误"]}
        with pytest.raises(RuntimeError, match="闲鱼接口返回错误"):
            _parse_item_list_response(response)

    def test_parse_ret_as_string(self):
        response = {"ret": "SUCCESS::调用成功", "data": {"cardList": [{"cardData": {"itemId": "1"}}]}}
        items = _parse_item_list_response(response)
        assert len(items) == 1


class TestParseItemDetailResponse:
    """商品详情响应解析测试"""

    def test_parse_detail_success(self):
        response = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"item": {"desc": "这是商品详情描述", "itemId": "12345"}},
        }
        result = _parse_item_detail_response(response)
        assert result["item"]["desc"] == "这是商品详情描述"

    def test_parse_detail_failed(self):
        response = {"ret": ["FAIL::错误"]}
        result = _parse_item_detail_response(response)
        assert result == {}


class TestParseCardToGoods:
    """CardData 解析为商品字典测试"""

    def test_parse_basic_goods(self):
        card_data = {
            "itemId": "12345",
            "title": "测试商品",
            "soldPrice": "99.00",
            "coverPic": "https://img.example.com/pic.jpg",
            "quantity": 10,
            "exposureCount": 100,
            "viewCount": 50,
            "wantCount": 5,
            "detailUrl": "https://goofish.com/item/12345",
            "itemStatus": 1,
        }
        goods = _parse_card_to_goods(card_data, account_id=1, tenant_id=100)
        assert goods["external_goods_id"] == "12345"
        assert goods["title"] == "测试商品"
        assert goods["sold_price"] == "99.00"
        assert goods["cover_pic"] == "https://img.example.com/pic.jpg"
        assert goods["quantity"] == 10
        assert goods["exposure_count"] == 100
        assert goods["view_count"] == 50
        assert goods["want_count"] == 5
        assert goods["detail_url"] == "https://goofish.com/item/12345"
        assert goods["status"] == 0  # 在售
        assert goods["account_id"] == 1
        assert goods["tenant_id"] == 100

    def test_parse_sold_goods(self):
        card_data = {"itemId": "67890", "title": "已售商品", "itemStatus": 3}
        goods = _parse_card_to_goods(card_data, account_id=1, tenant_id=100)
        assert goods["status"] == 2  # 已售

    def test_parse_off_shelf_goods(self):
        card_data = {"itemId": "11111", "itemStatus": 2}
        goods = _parse_card_to_goods(card_data, account_id=1, tenant_id=100)
        assert goods["status"] == 1  # 下架


class TestIsGoodsChanged:
    """商品变化检测测试"""

    def test_no_change(self):
        existing = {
            "title": "商品A",
            "sold_price": "99",
            "cover_pic": "pic.jpg",
            "status": 0,
            "quantity": 10,
            "exposure_count": 100,
            "view_count": 50,
            "want_count": 5,
            "detail_info": "描述",
        }
        new_data = dict(existing)
        assert _is_goods_changed(existing, new_data) is False

    def test_title_changed(self):
        existing = {"title": "商品A", "sold_price": "99", "cover_pic": "", "status": 0, "quantity": 0, "exposure_count": 0, "view_count": 0, "want_count": 0, "detail_info": ""}
        new_data = dict(existing)
        new_data["title"] = "商品B"
        assert _is_goods_changed(existing, new_data) is True

    def test_price_changed(self):
        existing = {"title": "", "sold_price": "99", "cover_pic": "", "status": 0, "quantity": 0, "exposure_count": 0, "view_count": 0, "want_count": 0, "detail_info": ""}
        new_data = dict(existing)
        new_data["sold_price"] = "199"
        assert _is_goods_changed(existing, new_data) is True

    def test_status_changed(self):
        existing = {"title": "", "sold_price": "", "cover_pic": "", "status": 0, "quantity": 0, "exposure_count": 0, "view_count": 0, "want_count": 0, "detail_info": ""}
        new_data = dict(existing)
        new_data["status"] = 2
        assert _is_goods_changed(existing, new_data) is True

    def test_quantity_changed(self):
        existing = {"title": "", "sold_price": "", "cover_pic": "", "status": 0, "quantity": 10, "exposure_count": 0, "view_count": 0, "want_count": 0, "detail_info": ""}
        new_data = dict(existing)
        new_data["quantity"] = 20
        assert _is_goods_changed(existing, new_data) is True


class TestMergeDetailInfo:
    """详情合并测试"""

    def test_merge_detail(self):
        goods = {"detail_info": "", "description": "", "detail_url": ""}
        detail_data = {
            "item": {
                "desc": "详细的商品描述文本",
                "detailUrl": "https://example.com/detail/123",
            }
        }
        _merge_detail_info(goods, detail_data)
        assert goods["detail_info"] == "详细的商品描述文本"
        assert goods["description"] == "详细的商品描述文本"
        assert goods["detail_url"] == "https://example.com/detail/123"

    def test_merge_empty_detail(self):
        goods = {"detail_info": "", "description": ""}
        _merge_detail_info(goods, {})
        assert goods["detail_info"] == ""
        assert goods["description"] == ""

    def test_merge_detail_no_desc(self):
        goods = {"detail_info": "old", "description": "old"}
        detail_data = {"item": {"otherField": "value"}}
        _merge_detail_info(goods, detail_data)
        assert goods["detail_info"] == "old"  # 未变化


class TestFetchGoodsList:
    """商品列表获取测试（mock API）"""

    @patch("app.services.xianyu_goods_sync._make_api_request")
    def test_fetch_single_page(self, mock_request):
        from app.services.xianyu_goods_sync import fetch_goods_list

        mock_request.return_value = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "cardList": [
                    {"cardData": {"itemId": "1", "title": "商品1", "itemStatus": 1}},
                    {"cardData": {"itemId": "2", "title": "商品2", "itemStatus": 1}},
                ]
            },
        }

        items = fetch_goods_list("unb=user123; other=c", page_size=20)
        assert len(items) == 2
        assert items[0]["itemId"] == "1"

    @patch("app.services.xianyu_goods_sync._make_api_request")
    def test_fetch_multiple_pages(self, mock_request):
        from app.services.xianyu_goods_sync import fetch_goods_list

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "ret": ["SUCCESS::调用成功"],
                    "data": {"cardList": [{"cardData": {"itemId": str(i), "itemStatus": 1}} for i in range(20)]},
                }
            else:
                return {
                    "ret": ["SUCCESS::调用成功"],
                    "data": {"cardList": [{"cardData": {"itemId": "21", "itemStatus": 1}}]},
                }

        mock_request.side_effect = side_effect
        items = fetch_goods_list("unb=user123; other=c", page_size=20)
        assert len(items) == 21

    @patch("app.services.xianyu_goods_sync._make_api_request")
    def test_fetch_empty(self, mock_request):
        from app.services.xianyu_goods_sync import fetch_goods_list

        mock_request.return_value = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"cardList": []},
        }
        items = fetch_goods_list("unb=user123; other=c")
        assert items == []
class TestGoodsPersistenceHelpers:
    def test_build_goods_insert_values_maps_status_and_context(self):
        values = _build_goods_insert_values(
            {
                "tenant_id": 1,
                "account_id": 2,
                "external_goods_id": "abc",
                "title": "测试商品",
                "status": 0,
                "quantity": "5",
                "stock": "5",
                "image_urls": ["https://img.example.com/a.jpg"],
                "detail_info": "详情",
            }
        )
        assert values["tenant_id"] == 1
        assert values["account_id"] == 2
        assert values["goods_id"] == "abc"
        assert values["status"] == 1
        assert values["quantity"] == 5
        assert values["stock"] == 5
        assert values["cover_pic"] == "https://img.example.com/a.jpg"
        assert values["description"] == "详情"

    def test_build_goods_update_values_partial_does_not_overwrite_empty_text(self):
        existing = type(
            "Goods",
            (),
            {
                "cover_pic": "https://img.example.com/existing.jpg",
                "image_url": "https://img.example.com/existing.jpg",
            },
        )()
        values = _build_goods_update_values(
            existing,
            {
                "external_goods_id": "abc",
                "title": "新标题",
                "detail_info": "",
                "description": "",
                "quantity": 0,
                "stock": 0,
            },
            partial=True,
        )
        assert values["title"] == "新标题"
        assert "detail_info" not in values
        assert "description" not in values

    def test_merge_detail_info_extracts_images_and_quantity(self):
        goods = {"cover_pic": "", "image_url": ""}
        detail_data = {
            "item": {
                "desc": "详细描述",
                "quantity": 6,
                "imageList": [
                    {"url": "https://img.example.com/1.jpg"},
                    {"url": "https://img.example.com/2.jpg"},
                ],
            }
        }
        _merge_detail_info(goods, detail_data)
        assert goods["quantity"] == 6
        assert goods["stock"] == 6
        assert goods["image_urls"] == [
            "https://img.example.com/1.jpg",
            "https://img.example.com/2.jpg",
        ]
        assert goods["cover_pic"] == "https://img.example.com/1.jpg"
