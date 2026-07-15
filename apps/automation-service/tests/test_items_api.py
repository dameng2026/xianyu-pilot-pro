"""
商品同步 API 集成测试。
使用 FastAPI TestClient 测试 refresh/list/detail 端点。
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import ASGITransport, AsyncClient
from types import SimpleNamespace

from app.main import app
from app.core.config import settings
from app.core.response import ResultObject
from app.services.xianyu_goods_sync import XianyuItemOperator
from app.api.v1.routes import items as items_route
from app.api.v1.routes import workflow as workflow_route


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestItemList:
    """商品列表接口测试"""

    @pytest.mark.anyio
    async def test_list_requires_auth(self, async_client):
        """未认证时返回 401"""
        response = await async_client.post("/api/item/list", json={})
        data = response.json()
        assert data["code"] == 401

    @pytest.mark.anyio
    async def test_list_with_auth(self, async_client):
        """需要有效的认证令牌"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.post("/api/item/list", json={}, headers=headers)
        data = response.json()
        assert data["code"] == 401


class TestWorkflowAiGenerateImages:
    """工作流测试生图接口在未接入真实图片提供方时应失败关闭。"""

    @pytest.mark.anyio
    async def test_generate_images_does_not_return_or_charge_for_placeholders(self):
        current_user = {"tenant_id": 1, "user_id": 2}
        captured = {}

        class DummyResult:
            def __init__(self, rows):
                self._rows = rows

            def mappings(self):
                return self

            def all(self):
                return self._rows

        class DummyDb:
            async def execute(self, *args, **kwargs):
                return DummyResult([
                    {
                        "json_text": {
                            "categoryKey": "game_cdk",
                            "matchKeywords": "Steam,CDK,激活码,DLC",
                            "promptTemplate": "游戏主图 {{TITLE}} / {{CONTENT}}",
                            "enabled": True,
                            "status": "正常",
                        }
                    }
                ])

        async def fake_generate_text(scene, system_prompt, user_prompt, temperature):
            captured.setdefault("scenes", []).append(scene)
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            if scene == "workflow_image_prompt_select":
                return {"ok": True, "content": "{\"categoryKey\":\"game_cdk\"}", "requestId": "req-0", "usage": {}}
            return {"ok": True, "content": "mock", "requestId": "req-1", "usage": {}}

        previous_ai_provider_enabled = settings.ai_provider_enabled
        settings.ai_provider_enabled = True
        with patch.object(workflow_route, "generate_text", new=AsyncMock(side_effect=fake_generate_text)):
            with patch.object(workflow_route, "precheck_ai_usage", new=AsyncMock(return_value={"ok": True})):
                with patch.object(workflow_route, "charge_image_usage", new=AsyncMock(return_value=None)):
                    result = await workflow_route.ai_generate_images(
                        body={
                            "title": "Steam激活码 自动发货",
                            "description": "支持DLC入库与游戏激活",
                            "prompt": "通用兜底 {{TITLE}}",
                            "promptMode": "default",
                            "customPrompt": "",
                            "imageCount": 1,
                            "modelKey": "model-config-image",
                        },
                        db=DummyDb(),
                        current_user=current_user,
                    )
        settings.ai_provider_enabled = previous_ai_provider_enabled

        assert result.code == 503
        assert result.data is None
        assert "未生成" in result.msg
        assert captured == {}
        


class TestItemRefresh:
    """商品刷新接口测试"""

    @pytest.mark.anyio
    async def test_refresh_requires_auth(self, async_client):
        """未认证时返回 401"""
        response = await async_client.post("/api/item/refresh", json={})
        data = response.json()
        assert data["code"] == 401

    @pytest.mark.anyio
    async def test_refresh_missing_account_id(self, async_client):
        """缺少 account_id 参数"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.post("/api/item/refresh", json={}, headers=headers)
        data = response.json()
        assert data["code"] == 401  # 先被认证拦截


class TestItemPolish:
    """一键擦亮接口测试"""

    @pytest.mark.anyio
    async def test_polish_submits_background_task_for_on_sale_items(self):
        from app.models.entities import XianyuGoods

        class DummyScalarResult:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        class DummyExecuteResult:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                return DummyScalarResult(self._rows)

        class DummyDb:
            async def execute(self, query):
                sql = str(query.compile(compile_kwargs={"literal_binds": True}))
                if "xianyu_goods.status = 1" in sql:
                    return DummyExecuteResult([
                        XianyuGoods(
                            id=1,
                            tenant_id=9,
                            account_id=7,
                            external_goods_id="xy-1",
                            title="测试在售商品",
                            status=1,
                            deleted=0,
                        )
                    ])
                return DummyExecuteResult([])

        operator = MagicMock()
        created_coroutines = []

        class DummyTask:
            def add_done_callback(self, callback):
                self._callback = callback

        def fake_create_task(coro):
            created_coroutines.append(coro)
            return DummyTask()

        try:
            with patch.object(
                items_route,
                "_get_account_auth",
                new=AsyncMock(return_value=SimpleNamespace(encrypted_cookie="encrypted-cookie")),
            ):
                with patch.object(items_route, "_is_fish_shop_account", new=AsyncMock(return_value=False)):
                    with patch.object(items_route, "decrypt_cookie_if_needed", return_value="_m_h5_tk=test_123; unb=demo"):
                        with patch("app.services.xianyu_goods_sync.extract_token_from_cookie", return_value="test_123"):
                            with patch.object(items_route, "XianyuItemOperator", return_value=operator):
                                with patch.object(items_route.asyncio, "create_task", side_effect=fake_create_task):
                                    result = await items_route.polish_account_items(
                                        req={"xianyuAccountId": 7, "tenantId": 9},
                                        db=DummyDb(),
                                        _=None,
                                    )

            assert result.code == 200
            assert result.data["status"] in {"queued", "running"}
            assert result.data["running"] is True
            assert result.data["total"] == 1
            assert result.data["processed"] == 0
            assert result.data["polished"] == 0
            assert result.data["failed"] == 0
            assert result.data["taskId"]
            assert "已提交" in result.data["message"]
            assert len(created_coroutines) == 1
            operator.polish_batch.assert_not_called()
        finally:
            for coro in created_coroutines:
                coro.close()
            if hasattr(items_route, "_polish_tasks"):
                items_route._polish_tasks.clear()
            if hasattr(items_route, "_polish_account_tasks"):
                items_route._polish_account_tasks.clear()

    def test_polish_treats_already_polished_as_success(self):
        """当闲鱼返回 FAIL_BIZ_IDLEITEM_POLISH_AGAIN（宝贝已擦亮过）时应视为成功"""
        operator = XianyuItemOperator("_m_h5_tk=test_123; unb=demo")

        with patch.object(
            operator,
            "_call_polish_api",
            side_effect=RuntimeError("闲鱼 API 调用失败: ['FAIL_BIZ_IDLEITEM_POLISH_AGAIN::宝贝已经擦亮过了，请刷新一下~']"),
        ) as call_api:
            result = operator.polish("xy-1")

        assert result["success"] is True
        assert result["already_done"] is True
        assert result["need_manual"] is False
        assert result["error"] is None
        assert call_api.call_count == 1

    def test_polish_real_failure_returns_failure(self):
        """当闲鱼返回其他业务错误时应返回失败"""
        operator = XianyuItemOperator("_m_h5_tk=test_123; unb=demo")

        with patch.object(
            operator,
            "_call_polish_api",
            side_effect=RuntimeError("闲鱼 API 调用失败: ['FAIL_BIZ_ITEM_NOT_FOUND::商品不存在']"),
        ) as call_api:
            result = operator.polish("xy-1")

        assert result["success"] is False
        assert result["already_done"] is False
        assert result["need_manual"] is False
        assert result["error"] == "商品擦亮失败，请稍后重试"
        assert result["errorCode"] == "POLISH_FAILED"
        assert "FAIL_BIZ_ITEM_NOT_FOUND" not in result["error"]
        assert call_api.call_count == 1

    def test_polish_captcha_triggers_need_manual(self):
        """触发风控时 need_manual 应为 True"""
        operator = XianyuItemOperator("_m_h5_tk=test_123; unb=demo")

        with patch.object(
            operator,
            "_call_polish_api",
            side_effect=RuntimeError("闲鱼 API 调用失败: ['FAIL_SYS_USER_VALIDATE::请完成验证']"),
        ) as call_api:
            result = operator.polish("xy-1")

        assert result["success"] is False
        assert result["need_manual"] is True
        assert result["already_done"] is False
        assert call_api.call_count == 1

    @pytest.mark.anyio
    async def test_polish_progress_returns_current_task_snapshot(self):
        with patch.dict(
            items_route._polish_tasks,
            {
                "task-1": {
                    "taskId": "task-1",
                    "accountId": 7,
                    "tenantId": 9,
                    "status": "running",
                    "running": True,
                    "total": 3,
                    "processed": 1,
                    "polished": 1,
                    "failed": 0,
                    "progress": 33,
                    "needManual": False,
                    "message": "擦亮任务执行中",
                    "error": None,
                    "_updatedTs": 1,
                }
            },
            clear=True,
        ):
            result = await items_route.get_polish_progress("task-1", _=None)

        assert result.code == 200
        assert result.data == {
            "taskId": "task-1",
            "accountId": 7,
            "tenantId": 9,
            "status": "running",
            "running": True,
            "total": 3,
            "processed": 1,
            "polished": 1,
            "failed": 0,
            "progress": 33,
            "needManual": False,
            "message": "擦亮任务执行中",
            "error": None,
        }


class TestItemDetail:
    """商品详情接口测试"""

    @pytest.mark.anyio
    async def test_detail_requires_auth(self, async_client):
        response = await async_client.post("/api/item/detail", json={})
        data = response.json()
        assert data["code"] == 401


class TestSyncProgress:
    """同步进度接口测试"""

    @pytest.mark.anyio
    async def test_sync_progress_requires_auth(self, async_client):
        """获取同步进度需要认证"""
        response = await async_client.get("/api/item/syncProgress/nonexistent_id")
        data = response.json()
        assert data["code"] == 401

    @pytest.mark.anyio
    async def test_syncing_requires_auth(self, async_client):
        """检查同步状态需要认证"""
        response = await async_client.get("/api/item/syncing/999")
        data = response.json()
        assert data["code"] == 401


class TestGoodsSyncService:
    """商品同步服务模块测试（mock requests）"""

    @patch("app.services.xianyu_goods_sync.requests.Session")
    def test_make_api_request(self, mock_session_class):
        from app.services.xianyu_goods_sync import _make_api_request

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"cardList": []},
        }
        mock_session.post.return_value = mock_response

        cookie_str = "_m_h5_tk=abc123_456; unb=testuser"
        result = _make_api_request(cookie_str, "mtop.idle.web.xyh.item.list", {"pageNum": 1})

        assert result["ret"][0] == "SUCCESS::调用成功"
        mock_session.post.assert_called_once()

    def test_make_api_request_missing_token(self):
        from app.services.xianyu_goods_sync import _make_api_request
        import pytest as pt

        cookie_str = "unb=testuser"  # 缺少 _m_h5_tk
        with pt.raises(RuntimeError, match="缺少 _m_h5_tk"):
            _make_api_request(cookie_str, "test.api", {})


class TestGoodsDTOMapping:
    """商品 DTO 映射测试"""

    def test_goods_to_dto_all_fields(self):
        from app.models.entities import XianyuGoods
        from app.api.v1.routes.items import goods_to_dto
        from datetime import datetime

        goods = XianyuGoods(
            id=1,
            tenant_id=100,
            account_id=10,
            external_goods_id="12345",
            title="测试商品",
            price="99.00",
            sold_price="89.00",
            cover_pic="https://img.example.com/pic.jpg",
            image_url="https://img.example.com/pic.jpg",
            stock="10",
            quantity=10,
            exposure_count=100,
            view_count=50,
            want_count=5,
            detail_url="https://goofish.com/item/12345",
            detail_info="详情描述",
            description="详情描述",
            category="数码",
            sort_order=1,
            status=0,
            created_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        dto = goods_to_dto(goods)

        assert dto.id == 1
        assert dto.xianyu_account_id == 10
        assert dto.xy_goods_id == "12345"
        assert dto.goods_title == "测试商品"
        assert dto.goods_price == "89.00"  # 优先取 sold_price
        assert dto.goods_stock == "10"
        assert dto.goods_image == "https://img.example.com/pic.jpg"
        assert dto.cover_pic == "https://img.example.com/pic.jpg"
        assert dto.sold_price == "89.00"
        assert dto.quantity == 10
        assert dto.exposure_count == 100
        assert dto.view_count == 50
        assert dto.want_count == 5
        assert dto.detail_url == "https://goofish.com/item/12345"
        assert dto.detail_info == "详情描述"
        assert dto.sort_order == 1
        assert dto.status == 1
        assert dto.created_time is not None

    def test_goods_to_dto_fallback_price(self):
        from app.models.entities import XianyuGoods
        from app.api.v1.routes.items import goods_to_dto

        goods = XianyuGoods(
            id=1,
            price="99.00",
            sold_price=None,  # sold_price 为空时，回退到 price
        )

        dto = goods_to_dto(goods)
        assert dto.goods_price == "99.00"


class TestNormalizePrice:
    """价格标准化函数测试"""

    def test_normalize_price_valid(self):
        from app.api.v1.routes.items import normalize_price
        assert normalize_price("99.99") == "99.99"
        assert normalize_price("100") == "100"
        assert normalize_price("0.01") == "0.01"
        assert normalize_price("100.00") == "100"
        assert normalize_price("  50.50  ") == "50.5"

    def test_normalize_price_invalid(self):
        from app.api.v1.routes.items import normalize_price
        import pytest as pt

        with pt.raises(ValueError, match="价格不能为空"):
            normalize_price("")
        with pt.raises(ValueError, match="价格不能为空"):
            normalize_price("  ")
        with pt.raises(ValueError, match="价格必须大于0"):
            normalize_price("0")
        with pt.raises(ValueError, match="价格必须大于0"):
            normalize_price("-1")
        with pt.raises(ValueError, match="价格最多保留2位小数"):
            normalize_price("99.999")
        with pt.raises(ValueError, match="价格格式无效"):
            normalize_price("abc")


class TestSellerSearchPayload:
    """卖家工作台搜索 payload 构建测试"""

    def test_seller_search_payload_no_status(self):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        payload = XianyuItemOperator._seller_search_payload("12345", None)
        assert payload["pageNo"] == 1
        assert payload["pageSize"] == 20
        assert payload["bizType"] == "commonPro"
        assert '"itemId":"12345"' in payload["searchRequest"]
        assert "itemStatus" not in payload

    def test_seller_search_payload_with_status(self):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        payload = XianyuItemOperator._seller_search_payload("12345", "0,-9")
        assert payload["itemStatus"] == "0,-9"


class TestBuildPriceUpdatePayload:
    """改价请求 payload 构建测试"""

    def _make_operator(self):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        return XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)

    def test_build_payload_no_sku(self):
        operator = self._make_operator()
        seller_item = {"itemId": "12345", "quantity": 10}
        payload = operator._build_seller_price_update_payload(seller_item, "99.99")
        assert payload["itemId"] == "12345"
        assert payload["quantity"] == 10
        assert payload["price"] == "99.99"
        assert "itemSkuListStr" not in payload

    def test_build_payload_with_sku(self):
        operator = self._make_operator()
        seller_item = {
            "itemId": "12345",
            "idleItemSkuList": [
                {"skuId": "sku1", "quantity": 5},
                {"skuId": "sku2", "quantity": 3},
            ]
        }
        payload = operator._build_seller_price_update_payload(seller_item, "88.00")
        assert payload["itemId"] == "12345"
        assert "itemSkuListStr" in payload
        import json
        sku_list = json.loads(payload["itemSkuListStr"])
        assert len(sku_list) == 2
        assert sku_list[0]["skuId"] == "sku1"
        assert sku_list[0]["price"] == "88.00"
        assert sku_list[0]["quantity"] == 5
        assert sku_list[1]["skuId"] == "sku2"
        assert sku_list[1]["price"] == "88.00"
        assert sku_list[1]["quantity"] == 3

    def test_build_payload_empty_sku_list(self):
        operator = self._make_operator()
        seller_item = {"itemId": "12345", "idleItemSkuList": [], "quantity": 8}
        payload = operator._build_seller_price_update_payload(seller_item, "75.50")
        assert payload["itemId"] == "12345"
        assert payload["quantity"] == 8
        assert payload["price"] == "75.50"
        assert "itemSkuListStr" not in payload

    def test_build_payload_missing_item_id(self):
        operator = self._make_operator()
        import pytest as pt
        with pt.raises(RuntimeError, match="缺少 itemId"):
            operator._build_seller_price_update_payload({}, "99.99")


class TestSafeQuantity:
    """安全读取库存测试"""

    def test_safe_quantity_normal(self):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        assert XianyuItemOperator._safe_quantity({"quantity": 10}) == 10
        assert XianyuItemOperator._safe_quantity({"quantity": "5"}) == 5
        assert XianyuItemOperator._safe_quantity({"quantity": 0}) == 0
        assert XianyuItemOperator._safe_quantity({"quantity": None}) == 0
        assert XianyuItemOperator._safe_quantity({}) == 0


class TestXianyuItemOperatorUpdatePrice:
    """XianyuItemOperator 改价方法测试（mock API）"""

    @patch.object(XianyuItemOperator, '_call_api')
    @patch.object(XianyuItemOperator, '_find_seller_item')
    def test_update_price_success(self, mock_find, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_find.return_value = {"itemId": "12345", "quantity": 10}
        mock_call_api.return_value = {"ret": ["SUCCESS::调用成功"]}

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        result = operator.update_price("12345", "99.99")

        assert result is True
        mock_find.assert_called_once_with("12345")
        mock_call_api.assert_called_once()

    def test_update_price_not_fish_shop(self):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        import pytest as pt
        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=False)
        with pt.raises(RuntimeError, match="不是鱼小铺"):
            operator.update_price("12345", "99.99")

    @patch.object(XianyuItemOperator, '_find_seller_item')
    def test_update_price_find_fails(self, mock_find):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_find.side_effect = RuntimeError("未找到商品")

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        import pytest as pt
        with pt.raises(RuntimeError, match="未找到商品"):
            operator.update_price("12345", "99.99")


class TestFindSellerItem:
    """卖家工作台商品搜索测试（mock API）"""

    @patch.object(XianyuItemOperator, '_call_api')
    def test_find_seller_item_found(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_call_api.return_value = {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "data": {
                    "itemSearchResponseList": [
                        {"itemId": "12345", "title": "测试商品", "quantity": 10}
                    ]
                }
            }
        }

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        result = operator._find_seller_item("12345")
        assert result["itemId"] == "12345"
        assert result["title"] == "测试商品"

    @patch.object(XianyuItemOperator, '_call_api')
    def test_find_seller_item_not_found(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_call_api.return_value = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"data": {"itemSearchResponseList": []}}
        }

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        import pytest as pt
        with pt.raises(RuntimeError, match="未找到"):
            operator._find_seller_item("99999")


class TestUpdatePriceAPI:
    """改价 API 端点测试"""

    @pytest.mark.anyio
    async def test_update_price_requires_auth(self, async_client):
        """未认证时返回 401"""
        response = await async_client.post("/api/item/updatePrice", json={})
        data = response.json()
        assert data["code"] == 401

    @pytest.mark.anyio
    async def test_update_price_invalid_token(self, async_client):
        """无效 token 返回 401"""
        headers = {"Authorization": "Bearer invalid"}
        response = await async_client.post("/api/item/updatePrice", json={}, headers=headers)
        data = response.json()
        assert data["code"] == 401


class TestRemoteDeleteAPI:
    """远程删除 API 端点测试"""

    @pytest.mark.anyio
    async def test_remote_delete_requires_auth(self, async_client):
        """未认证时返回 401"""
        response = await async_client.post("/api/item/remoteDelete", json={})
        data = response.json()
        assert data["code"] == 401

    @pytest.mark.anyio
    async def test_remote_delete_invalid_token(self, async_client):
        """无效 token 返回 401"""
        headers = {"Authorization": "Bearer invalid"}
        response = await async_client.post("/api/item/remoteDelete", json={}, headers=headers)
        data = response.json()
        assert data["code"] == 401

    @pytest.mark.anyio
    async def test_remote_delete_missing_params(self, async_client):
        """缺少参数时返回错误"""
        # 使用无效 token，预期返回 403 认证错误
        headers = {"Authorization": "Bearer invalid"}
        response = await async_client.post(
            "/api/item/remoteDelete",
            json={"tenant_id": 1},
            headers=headers,
        )
        data = response.json()
        assert data["code"] == 401


class TestXianyuItemOperatorDelete:
    """XianyuItemOperator 删除方法测试"""

    @patch.object(XianyuItemOperator, '_call_api')
    def test_delete_seller(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_call_api.return_value = {"ret": ["SUCCESS::调用成功"]}

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        result = operator.delete("12345")
        assert result is True
        # 鱼小铺删除应包含 draftId=None
        call_kwargs = mock_call_api.call_args
        assert call_kwargs[0][0] == XianyuItemOperator.SELLER_DELETE_API

    @patch.object(XianyuItemOperator, '_call_api')
    def test_delete_normal(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_call_api.return_value = {"ret": ["SUCCESS::调用成功"]}

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=False)
        result = operator.delete("12345")
        assert result is True
        call_kwargs = mock_call_api.call_args
        assert call_kwargs[0][0] == XianyuItemOperator.NORMAL_DELETE_API


class TestUpdatePriceBatch:
    """批量改价测试"""

    @patch.object(XianyuItemOperator, 'update_price')
    def test_update_price_batch(self, mock_update):
        from app.services.xianyu_goods_sync import XianyuItemOperator

        mock_update.side_effect = [True, True, RuntimeError("失败")]
        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        results = operator.update_price_batch(["id1", "id2", "id3"], "99.99")

        assert results["id1"] is True
        assert results["id2"] is True
        assert results["id3"] is False
        assert mock_update.call_count == 3


class TestNormalizePriceEdgeCases:
    """价格标准化函数的边界情况测试"""

    def test_normalize_large_price(self):
        from app.api.v1.routes.items import normalize_price
        # 大数值
        assert normalize_price("999999.99") == "999999.99"
        assert normalize_price("1000000") == "1000000"

    def test_normalize_price_max_decimal(self):
        from app.api.v1.routes.items import normalize_price
        # 小数点后恰好2位
        assert normalize_price("0.10") == "0.1"
        assert normalize_price("10.00") == "10"
        assert normalize_price("10.01") == "10.01"
        assert normalize_price("0.99") == "0.99"

    def test_normalize_price_trailing_zeros(self):
        from app.api.v1.routes.items import normalize_price
        assert normalize_price("10.10") == "10.1"
        assert normalize_price("10.00") == "10"

    def test_normalize_price_invalid_chars(self):
        from app.api.v1.routes.items import normalize_price
        import pytest as pt
        with pt.raises(ValueError):
            normalize_price("12a.00")
        with pt.raises(ValueError):
            normalize_price("1.2.3")
        with pt.raises(ValueError):
            normalize_price("0x10")


class TestXianyuItemOperatorOffShelf:
    """XianyuItemOperator 下架方法测试"""

    @patch.object(XianyuItemOperator, '_call_api')
    def test_off_shelf_seller(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_call_api.return_value = {"ret": ["SUCCESS::调用成功"]}

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        result = operator.off_shelf("12345")
        assert result is True
        call_args = mock_call_api.call_args
        assert call_args[0][0] == XianyuItemOperator.SELLER_OFF_SHELF_API

    @patch.object(XianyuItemOperator, '_call_api')
    def test_off_shelf_normal(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_call_api.return_value = {"ret": ["SUCCESS::调用成功"]}

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=False)
        result = operator.off_shelf("12345")
        assert result is True
        call_args = mock_call_api.call_args
        assert call_args[0][0] == XianyuItemOperator.NORMAL_OFF_SHELF_API

    @patch.object(XianyuItemOperator, '_call_api')
    def test_off_shelf_api_failure(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        import pytest as pt
        mock_call_api.side_effect = RuntimeError("RGV587::触发风控")

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=False)
        with pt.raises(RuntimeError, match="触发风控"):
            operator.off_shelf("12345")


class TestXianyuItemOperatorDeleteFailures:
    """XianyuItemOperator 删除失败场景测试"""

    @patch.object(XianyuItemOperator, '_call_api')
    def test_delete_api_failure_rgv587(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        import pytest as pt
        mock_call_api.side_effect = RuntimeError("RGV587::触发风控")

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=False)
        with pt.raises(RuntimeError, match="触发风控"):
            operator.delete("12345")

    @patch.object(XianyuItemOperator, '_call_api')
    def test_delete_api_token_expired(self, mock_call_api):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        import pytest as pt
        mock_call_api.side_effect = RuntimeError("FAIL_SYS_TOKEN_EXPIRED::token expired")

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        with pt.raises(RuntimeError, match="token expired"):
            operator.delete("12345")

    def test_delete_missing_token(self):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        import pytest as pt
        with pt.raises(RuntimeError, match="缺少 _m_h5_tk"):
            XianyuItemOperator("unb=testuser", is_fish_shop=False)


class TestDeleteBatch:
    """批量删除测试"""

    @patch.object(XianyuItemOperator, 'delete')
    def test_delete_batch_mixed_results(self, mock_delete):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_delete.side_effect = [True, RuntimeError("失败"), True]

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        results = operator.delete_batch(["id1", "id2", "id3"])

        assert results["id1"] is True
        assert results["id2"] is False
        assert results["id3"] is True
        assert mock_delete.call_count == 3

    @patch.object(XianyuItemOperator, 'delete')
    def test_delete_batch_all_success(self, mock_delete):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_delete.return_value = True

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        results = operator.delete_batch(["id1", "id2"])

        assert all(results.values())
        assert mock_delete.call_count == 2

    @patch.object(XianyuItemOperator, 'delete')
    def test_delete_batch_all_fail(self, mock_delete):
        from app.services.xianyu_goods_sync import XianyuItemOperator
        mock_delete.side_effect = RuntimeError("API错误")

        operator = XianyuItemOperator("_m_h5_tk=abc123_456", is_fish_shop=True)
        results = operator.delete_batch(["id1", "id2"])

        assert not any(results.values())
        assert mock_delete.call_count == 2
