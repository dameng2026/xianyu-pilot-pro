import pytest
from types import SimpleNamespace
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.v1.routes import (
    account,
    ai_transaction_engine,
    auto_category,
    auto_reply,
    captcha,
    dashboard,
    feishu,
    internal,
    items,
    messages,
    misc,
    opportunity,
    order,
    restful,
    system,
    workflow,
)
from app.schemas.account import RefreshAccountProfileReqDTO
from app.schemas.common import AiProviderReqDTO
from app.schemas.common import GetSettingReqDTO, SaveSettingReqDTO
from app.schemas.order import ConfirmShipmentReqDTO


class _SingleRowResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row

    def scalars(self):
        return self

    def all(self):
        return [self._row]


class _SingleRowDb:
    def __init__(self, row):
        self._row = row

    async def execute(self, _query):
        return _SingleRowResult(self._row)


class _FailingDb:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("database unavailable")


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _SequenceScalarDb:
    def __init__(self, values):
        self._values = iter(values)

    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(next(self._values))


class _EmptyRowsResult:
    def scalars(self):
        return self

    def all(self):
        return []


class _CapturingDb:
    def __init__(self):
        self.query = None

    async def execute(self, query, *_args, **_kwargs):
        self.query = query
        return _EmptyRowsResult()


@pytest.mark.asyncio
async def test_unimplemented_audio_capability_is_fail_closed():
    result = await messages.audio_url(
        "message-1",
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "暂不可用" in result.msg


@pytest.mark.asyncio
async def test_unimplemented_auto_reply_batch_import_does_not_claim_success():
    result = await auto_reply.batch_import_auto_reply_rules(
        {"rules": [{"ruleName": "test"}]},
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "未导入" in result.msg


@pytest.mark.asyncio
async def test_legacy_publish_endpoint_does_not_claim_item_went_online():
    result = await restful.publish_item(
        {"goodsId": 10, "title": "test", "price": "9.90"},
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "未发布" in result.msg


@pytest.mark.asyncio
async def test_legacy_sync_state_endpoints_do_not_fabricate_completion():
    user = {"tenant_id": 1, "user_id": 1}

    progress = await restful.restful_goods_sync_progress("sync-1", current_user=user)
    syncing = await restful.restful_goods_syncing(10, current_user=user)

    assert progress.code == 503
    assert syncing.code == 503
    assert "不可用" in progress.msg
    assert "不可用" in syncing.msg


@pytest.mark.asyncio
async def test_legacy_profile_refresh_endpoints_do_not_claim_remote_refresh():
    existing_account = SimpleNamespace(
        id=10,
        external_uid="uid-10",
        nickname="cached nickname",
        avatar_url=None,
        remark=None,
        province=None,
        city=None,
        account_level="0",
        status=1,
        created_time=None,
    )
    db = _SingleRowDb(existing_account)
    user = {"tenant_id": 1, "user_id": 1}

    post_style = await account.refresh_account_profile(
        RefreshAccountProfileReqDTO(account_id=10),
        db=db,
        current_user=user,
    )
    restful_style = await restful.restful_refresh_account_profile(
        10,
        db=db,
        current_user=user,
    )

    assert post_style.code == 503
    assert restful_style.code == 503
    assert "未刷新" in post_style.msg
    assert "未刷新" in restful_style.msg


@pytest.mark.asyncio
async def test_legacy_ai_provider_listing_is_fail_closed_without_tenant_isolation():
    provider = SimpleNamespace(
        id=7,
        provider_name="provider",
        api_key="super-secret-provider-key",
        base_url="https://provider.invalid/v1",
        model_name="model",
        status=1,
    )

    result = await system.list_ai_providers(
        db=_SingleRowDb(provider),
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "super-secret-provider-key" not in result.model_dump_json()
    assert "租户隔离" in result.msg


@pytest.mark.asyncio
async def test_legacy_ai_provider_management_is_fail_closed():
    user = {"tenant_id": 1, "user_id": 1}
    request = AiProviderReqDTO(
        provider_name="provider",
        api_key="secret",
        base_url="https://provider.invalid/v1",
        model_name="model",
    )

    results = [
        await system.save_ai_provider(request, db=None, current_user=user),
        await system.list_ai_providers_by_type({"type": "text"}, db=None, current_user=user),
        await system.delete_ai_provider({"id": 7}, db=None, current_user=user),
        await system.activate_ai_provider({"id": 7}, db=None, current_user=user),
        await system.test_ai_provider({"id": 7}, db=None, current_user=user),
        await system.get_ai_provider_models({"id": 7}, db=None, current_user=user),
    ]

    assert all(result.code == 503 for result in results)
    assert all(result.data is None for result in results)
    assert all("配置中心" in result.msg for result in results)


@pytest.mark.asyncio
async def test_workflow_image_generation_never_returns_placeholder_images_as_generated():
    result = await workflow.ai_generate_images(
        {"title": "test product", "imageCount": 2},
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "未生成" in result.msg


@pytest.mark.asyncio
async def test_dashboard_database_failures_are_not_reported_as_zero_metrics():
    user = {"tenant_id": 1, "user_id": 1}
    db = _FailingDb()

    stats = await dashboard.get_dashboard_stats(db=db, current_user=user)
    summary = await dashboard.get_dashboard_summary(db=db, current_user=user)
    trend = await dashboard.get_dashboard_sales_trend(days=7, db=db, current_user=user)

    assert stats.code == 503
    assert summary.code == 503
    assert trend.code == 503
    assert all(result.data is None for result in (stats, summary, trend))
    assert all("暂不可用" in result.msg for result in (stats, summary, trend))


@pytest.mark.asyncio
async def test_workflow_query_failures_are_not_reported_as_empty_business_data():
    user = {"tenant_id": 1, "user_id": 1}
    db = _FailingDb()

    results = [
        await workflow.workflow_overview(db=db, current_user=user),
        await workflow.list_workflows(
            keyword="", status="", current=1, size=20, db=db, current_user=user
        ),
        await workflow.list_executions(
            workflow_id=None,
            status="",
            keyword="",
            current=1,
            size=20,
            db=db,
            current_user=user,
        ),
        await workflow.recent_runs(limit=10, db=db, current_user=user),
        await workflow.get_execution_logs(
            1, node_type="", status="", db=db, current_user=user
        ),
    ]

    assert all(result.code == 503 for result in results)
    assert all(result.data is None for result in results)
    assert all("暂不可用" in result.msg for result in results)


@pytest.mark.asyncio
async def test_opportunity_history_failure_is_not_reported_as_empty_history():
    result = await opportunity.opportunity_history(
        keyword="",
        current=1,
        size=20,
        db=_FailingDb(),
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "暂不可用" in result.msg


@pytest.mark.asyncio
async def test_opportunity_rewrite_is_fail_closed_when_ai_is_unavailable(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        return {"ok": False, "error": "provider unavailable", "requestId": "request-1"}

    monkeypatch.setattr(opportunity, "generate_text", unavailable)
    monkeypatch.setattr(opportunity, "get_polish_keywords_restriction", unavailable)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code == 503
    assert result.data is None
    assert "AI" in result.msg


@pytest.mark.asyncio
async def test_opportunity_rewrite_handles_unicode_punctuation_and_reports_real_ai_success(monkeypatch):
    async def no_restriction():
        return ""

    async def generated(*_args, **_kwargs):
        return {
            "ok": True,
            "content": "全新标题！\n这是一段完全改写、可人工复核的商品描述。",
            "provider": "test-provider",
            "model": "test-model",
            "requestId": "request-2",
            "usage": {},
        }

    async def unchanged(title, content):
        return title, content, []

    async def no_charge(**_kwargs):
        return {"deducted": True, "requestId": _kwargs["request_id"]}

    async def billing_allowed(_payload):
        return {"enough": True}

    monkeypatch.setattr(opportunity, "get_polish_keywords_restriction", no_restriction)
    monkeypatch.setattr(opportunity, "generate_text", generated)
    monkeypatch.setattr(opportunity, "enforce_polish_restriction", unchanged)
    monkeypatch.setattr(opportunity, "precheck_ai_usage", billing_allowed)
    monkeypatch.setattr(opportunity, "charge_text_usage", no_charge)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code == 200
    assert result.data["ok"] is True
    assert result.data["fallback"] is False
    assert result.data["provider"] == "test-provider"


@pytest.mark.asyncio
async def test_legacy_confirm_shipment_never_marks_local_order_as_platform_shipped():
    result = await order.confirm_shipment(
        ConfirmShipmentReqDTO(xianyu_account_id=9, order_id="order-1"),
        db=_FailingDb(),
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code != 200
    assert result.data is None


@pytest.mark.asyncio
async def test_category_tree_load_failure_is_not_reported_as_an_empty_tree(monkeypatch):
    def fail_load():
        raise RuntimeError("category source unavailable")

    monkeypatch.setattr(auto_category, "load_categories", fail_load)

    result = await auto_category.get_categories()

    assert result.code == 503
    assert result.data is None
    assert "暂不可用" in result.msg


@pytest.mark.asyncio
async def test_internal_tenant_scoped_routes_reject_missing_tenant_id(monkeypatch):
    async def must_not_run(*_args, **_kwargs):
        pytest.fail("tenant-scoped operation must not run without tenantId")

    monkeypatch.setattr(internal, "list_due_tasks", must_not_run)
    monkeypatch.setattr(internal, "execute_scheduled_task", must_not_run)
    monkeypatch.setattr(internal, "local_business_search", must_not_run)
    monkeypatch.setattr(internal, "list_workflow_timeline", must_not_run, raising=False)
    monkeypatch.setattr(internal, "list_workflow_state_variables", must_not_run, raising=False)

    def reject_background_task(coro):
        coro.close()
        pytest.fail("background task must not start without tenantId")

    monkeypatch.setattr(internal._asyncio, "create_task", reject_background_task)

    results = [
        await internal.internal_due_tasks(tenantId=None, limit=20, db=None, _=None),
        await internal.internal_run_task(1, body={}, db=None, _=None),
        await internal.internal_business_search(q="test", tenantId=None, limit=20, db=None, _=None),
        await internal.internal_execute_workflow(1, body={}, _=None),
        await internal.internal_continue_workflow(1, body={}, _=None),
        await internal.internal_workflow_timeline(1, tenantId=None, db=None, _=None),
        await internal.internal_workflow_state_variables(1, tenantId=None, db=None, _=None),
        await internal.internal_item_timing_stats(tenantId=None, db=None, _=None),
    ]

    assert all(result.code == 400 for result in results)
    assert all(result.data is None for result in results)
    assert all("tenantId" in result.msg for result in results)


@pytest.mark.asyncio
async def test_internal_timing_database_failure_is_not_reported_as_zero_samples():
    result = await internal.internal_item_timing_stats(
        tenantId=1,
        db=_FailingDb(),
        _=None,
    )

    assert result.code == 503
    assert result.data is None
    assert "暂不可用" in result.msg


@pytest.mark.asyncio
async def test_restful_dashboard_uses_persisted_today_order_count():
    result = await restful.restful_get_dashboard(
        db=_SequenceScalarDb([2, 5, 7, 3]),
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 200
    assert result.data == {
        "accountCount": 2,
        "orderCount": 5,
        "goodsCount": 7,
        "todayOrderCount": 3,
    }


@pytest.mark.asyncio
async def test_account_summary_uses_persisted_runtime_and_cookie_health_counts():
    result = await restful.restful_get_accounts_summary(
        db=_SequenceScalarDb([10, 7, 3, 6, 4]),
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 200
    assert result.data == {
        "total": 10,
        "normal": 7,
        "verify": 3,
        "wsOnline": 6,
        "cookieWarn": 4,
    }


@pytest.mark.asyncio
async def test_notification_listing_is_tenant_scoped_and_excludes_deleted_rows():
    db = _CapturingDb()

    result = await system.list_notifications(
        db=db,
        current_user={"tenant_id": 42, "user_id": 9},
    )

    query = str(db.query)
    assert result.code == 200
    assert "WHERE notification.tenant_id" in query
    assert "notification.deleted =" in query


@pytest.mark.asyncio
async def test_skeleton_transaction_engine_does_not_claim_strategy_execution():
    result = await ai_transaction_engine.run_engine(
        {"message": "可以便宜吗", "sales_card": {"aiSummary": "summary"}},
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 503
    assert result.data is None
    assert "未执行" in result.msg


@pytest.mark.asyncio
async def test_quick_reply_templates_require_authentication():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/quickReplyTemplate/list")

    assert response.status_code == 401
    assert response.json()["code"] == 401


@pytest.mark.asyncio
async def test_legacy_python_content_management_route_is_retired():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        read_response = await client.get("/api/content/carousels")

    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_internal_public_content_upload_requires_authentication():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/internal/content/public-images/upload",
            files={"file": ("banner.png", b"not-an-image", "image/png")},
            data={"purpose": "carousel"},
            headers={"X-Internal-Tenant-Id": "1"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_category_management_requires_authentication():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/xianyu/categories")

    assert response.status_code == 401
    assert response.json()["code"] == 401


@pytest.mark.asyncio
async def test_captcha_routes_only_use_authenticated_tenant(monkeypatch):
    captured = []

    async def compute_priority(tenant_id, trigger_scene="manual"):
        captured.append({"tenant_id": tenant_id, "_source": "compute_priority"})
        return ("normal", 0)

    async def enqueue(account_id, tenant_id, **kwargs):
        captured.append({"tenant_id": tenant_id, "_source": "enqueue", "account_id": account_id})
        return 42

    async def enqueue_with_pos(account_id, tenant_id, **kwargs):
        captured.append({"tenant_id": tenant_id, "_source": "enqueue", "account_id": account_id})
        return (42, 1, 1)

    async def get_pos(record_id):
        return (1, 1)

    async def handle(**kwargs):
        captured.append({"tenant_id": kwargs.get("tenant_id"), "_source": "handle"})
        return {"detected": False}

    # auto_solve_captcha 内部从 captcha_precheck / captcha_queue 模块导入函数，
    # 需要在源模块上 monkeypatch 才能生效
    from app.services import captcha_precheck, captcha_queue
    monkeypatch.setattr(captcha_precheck, "compute_solve_priority", compute_priority)
    # auto_solve_captcha / handle_captcha 使用 enqueue_solve_with_position 获取入队瞬间位置，
    # 不再二次调用 get_queue_position（避免 worker 已取出任务返回 (0, 0) 的竞态）
    monkeypatch.setattr(captcha_queue, "enqueue_solve_with_position", enqueue_with_pos)
    monkeypatch.setattr(captcha_queue, "enqueue_solve", enqueue)
    monkeypatch.setattr(captcha_queue, "get_queue_position", get_pos)
    # handle_captcha 在 autoSolve=False 时仍直接调用 handle_captcha_for_account
    monkeypatch.setattr(captcha, "handle_captcha_for_account", handle)
    user = {"tenant_id": 1, "user_id": 7}

    auto_result = await captcha.auto_solve_captcha(
        {"accountId": 10, "tenantId": 999},
        current_user=user,
    )
    await captcha.handle_captcha(
        {"accountId": 10, "tenantId": 999},
        current_user=user,
    )

    # auto_solve_captcha 应使用 current_user 的 tenant_id=1，而非 body 中的 tenantId=999
    assert captured[0]["tenant_id"] == 1
    assert captured[1]["tenant_id"] == 1
    # handle_captcha（autoSolve=False）也应使用 current_user 的 tenant_id=1
    assert captured[2]["tenant_id"] == 1
    # auto_solve_captcha 入队成功后返回 200 + 排队信息
    assert auto_result.code == 200
    assert auto_result.data["recordId"] == 42
    assert auto_result.data["status"] == "queued"


@pytest.mark.asyncio
async def test_feishu_transient_handler_failure_requests_provider_retry(monkeypatch):
    def fail_resolution(*_args, **_kwargs):
        raise RuntimeError("temporary database failure")

    monkeypatch.setattr(feishu, "_resolve_tenant_id_from_tenant_key", fail_resolution)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feishu/webhook",
            json={"header": {"tenant_key": "tenant-key"}},
        )

    assert response.status_code == 500
    assert response.json() == {"code": 1, "msg": "temporary failure"}


def test_feishu_event_is_deduplicated_only_after_successful_processing(monkeypatch):
    monkeypatch.setattr(feishu, "_EVENT_DEDUP", {})

    assert feishu._is_duplicate_event(11, "event-1") is False
    assert feishu._is_duplicate_event(11, "event-1") is False

    feishu._mark_event_processed(11, "event-1")

    assert feishu._is_duplicate_event(11, "event-1") is True
    assert feishu._is_duplicate_event(22, "event-1") is False


@pytest.mark.asyncio
async def test_legacy_global_system_settings_are_fail_closed_without_tenant_isolation():
    user = {"tenant_id": 1, "user_id": 7}
    results = [
        await system.get_setting(GetSettingReqDTO(setting_key="key"), db=None, current_user=user),
        await system.save_setting(
            SaveSettingReqDTO(setting_key="key", setting_value="value"),
            db=None,
            current_user=user,
        ),
        await system.list_settings(db=None, current_user=user),
        await system.delete_setting({"setting_key": "key"}, db=None, current_user=user),
    ]

    assert all(result.code == 503 for result in results)
    assert all(result.data is None for result in results)
    assert all("配置中心" in result.msg for result in results)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/image.png",
        "https://127.0.0.1/image.png",
        "https://169.254.169.254/latest/meta-data",
        "https://user:password@example.com/image.png",
    ],
)
def test_auto_category_rejects_unsafe_remote_image_urls(url):
    with pytest.raises(ValueError):
        auto_category._validate_remote_image_url(url)


@pytest.mark.parametrize(
    "path",
    [
        "/../../.env",
        "/uploads/images/../secret.txt",
        "/etc/passwd",
        "/uploads/other/file.png",
    ],
)
def test_auto_category_rejects_unsafe_relative_image_paths(path):
    with pytest.raises(ValueError):
        auto_category._validate_relative_image_path(path)


def test_auto_category_local_images_are_bound_to_authenticated_tenant():
    assert auto_category._validate_relative_image_path(
        "/uploads/images/tenant-7/image.png", tenant_id=7
    ) == "/uploads/images/tenant-7/image.png"

    for path in (
        "/uploads/images/tenant-8/image.png",
        "/uploads/images/legacy-flat.png",
        "/uploads/cache/tenant-8/image.png",
        "/uploads/images/tenant-7/%2e%2e/tenant-8/image.png",
    ):
        with pytest.raises(ValueError):
            auto_category._validate_relative_image_path(path, tenant_id=7)


@pytest.mark.asyncio
async def test_internal_scheduled_task_failure_is_not_wrapped_as_success(monkeypatch):
    async def unsupported(*_args, **_kwargs):
        return {
            "ok": False,
            "error": "UNSUPPORTED_TASK_TYPE",
            "message": "不支持的定时任务类型: unknown",
        }

    monkeypatch.setattr(internal, "execute_scheduled_task", unsupported)

    result = await internal.internal_run_task(
        77,
        body={"tenantId": 1},
        db=None,
        _=None,
    )

    assert result.code == 422
    assert result.data is None
    assert "不支持" in result.msg


@pytest.mark.asyncio
async def test_unimplemented_republish_capability_is_fail_closed():
    result = await items.republish_item(
        {"goodsId": "goods-1"},
        db=None,
        _=None,
    )

    assert result.code == 503
    assert result.data is None
    assert "未重新发布" in result.msg


@pytest.mark.asyncio
async def test_syncing_status_requires_tenant_before_using_runtime_evidence(monkeypatch):
    from app.services import xianyu_goods_sync

    monkeypatch.setattr(xianyu_goods_sync, "is_account_syncing", lambda _account_id: True)

    missing_tenant = await items.is_syncing(
        8,
        tenantId=None,
        tenant_id=None,
        db=None,
        _=None,
    )
    known_tenant = await items.is_syncing(
        8,
        tenantId=1,
        tenant_id=None,
        db=None,
        _=None,
    )

    assert missing_tenant.code == 400
    assert known_tenant.code == 200
    assert known_tenant.data is True


@pytest.mark.asyncio
async def test_media_list_io_failure_is_not_reported_as_empty(monkeypatch):
    monkeypatch.setattr(misc.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(misc.os, "listdir", lambda _path: (_ for _ in ()).throw(OSError("disk unavailable")))

    result = await misc.media_list(
        {},
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code != 200
    assert result.data is None


@pytest.mark.asyncio
async def test_global_media_library_is_truthfully_unavailable_without_tenant_storage(monkeypatch):
    monkeypatch.setattr(misc.os.path, "exists", lambda _path: False)

    result = await misc.media_list(
        {},
        db=None,
        current_user={"tenant_id": 1, "user_id": 1},
    )

    assert result.code == 410
    assert result.data is None
    assert "租户隔离" in result.msg
