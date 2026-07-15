from __future__ import annotations

import json
import ast
from pathlib import Path

import httpx
import pytest

from app.api.v1.routes import opportunity, workflow
from app.services import ai_billing, automation_runtime


SERVICE_ROOT = Path(__file__).parents[1]
SCOPED_AI_FILES = [
    SERVICE_ROOT / "app/api/v1/routes/opportunity.py",
    SERVICE_ROOT / "app/api/v1/routes/workflow.py",
    SERVICE_ROOT / "app/services/automation_runtime.py",
    SERVICE_ROOT / "app/services/feishu_chat.py",
]


@pytest.mark.asyncio
async def test_opportunity_rewrite_does_not_call_provider_when_billing_precheck_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls = 0

    async def java_billing_boundary(path: str, _payload: dict) -> dict:
        if path.endswith("/precheck"):
            return {"enough": False, "message": "Token 余额不足，请先充值"}
        return {"deducted": True, "requestId": "unexpected-charge"}

    async def generated(*_args, **_kwargs) -> dict:
        nonlocal provider_calls
        provider_calls += 1
        return {
            "ok": True,
            "content": "不应生成",
            "provider": "test-provider",
            "model": "test-model",
            "requestId": "provider-request",
            "usage": {},
        }

    async def no_restriction() -> str:
        return ""

    monkeypatch.setattr(ai_billing, "_post_java", java_billing_boundary)
    monkeypatch.setattr(opportunity, "generate_text", generated)
    monkeypatch.setattr(opportunity, "get_polish_keywords_restriction", no_restriction)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code == 402
    assert result.data is None
    assert "余额不足" in result.msg
    assert provider_calls == 0


@pytest.mark.asyncio
async def test_opportunity_rewrite_does_not_return_generated_content_when_charge_is_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def java_billing_boundary(path: str, _payload: dict) -> dict:
        if path.endswith("/precheck"):
            return {"enough": True}
        return {}

    async def generated(*_args, **_kwargs) -> dict:
        return {
            "ok": True,
            "content": "已生成标题\n已生成且尚未扣费的正文",
            "provider": "test-provider",
            "model": "test-model",
            "requestId": "provider-request",
            "usage": {},
        }

    async def no_restriction() -> str:
        return ""

    async def unchanged(title: str, content: str) -> tuple[str, str, list[str]]:
        return title, content, []

    monkeypatch.setattr(ai_billing, "_post_java", java_billing_boundary)
    monkeypatch.setattr(opportunity, "generate_text", generated)
    monkeypatch.setattr(opportunity, "get_polish_keywords_restriction", no_restriction)
    monkeypatch.setattr(opportunity, "enforce_polish_restriction", unchanged)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code == 503
    assert result.data is None
    assert "计费" in result.msg


@pytest.mark.asyncio
async def test_opportunity_rewrite_uses_one_request_id_for_precheck_provider_and_charge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    billing_payloads: list[tuple[str, dict]] = []
    provider_request_ids: list[str | None] = []

    async def java_billing_boundary(path: str, payload: dict) -> dict:
        billing_payloads.append((path, dict(payload)))
        if path.endswith("/precheck"):
            return {"enough": True}
        return {"deducted": True, "requestId": payload["requestId"]}

    async def generated(
        _scene: str,
        _system_prompt: str,
        _user_prompt: str,
        _temperature: float,
        *,
        request_id: str | None = None,
    ) -> dict:
        provider_request_ids.append(request_id)
        return {
            "ok": True,
            "content": "全新标题\n经过模型生成并完成计费的正文",
            "provider": "test-provider",
            "model": "test-model",
            "requestId": request_id,
            "usage": {"prompt_tokens": 4, "completion_tokens": 5},
        }

    async def no_restriction() -> str:
        return ""

    async def unchanged(title: str, content: str) -> tuple[str, str, list[str]]:
        return title, content, []

    monkeypatch.setattr(ai_billing, "_post_java", java_billing_boundary)
    monkeypatch.setattr(opportunity, "generate_text", generated)
    monkeypatch.setattr(opportunity, "get_polish_keywords_restriction", no_restriction)
    monkeypatch.setattr(opportunity, "enforce_polish_restriction", unchanged)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code == 200
    request_ids = [payload["requestId"] for _, payload in billing_payloads]
    assert len(request_ids) == 2
    assert len(set(request_ids)) == 1
    assert provider_request_ids == request_ids[:1]
    assert result.data["requestId"] == request_ids[0]


@pytest.mark.asyncio
async def test_opportunity_rewrite_requires_positive_user_binding_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls = 0

    async def generated(*_args, **_kwargs) -> dict:
        nonlocal provider_calls
        provider_calls += 1
        return {"ok": True, "content": "不应生成"}

    monkeypatch.setattr(opportunity, "generate_text", generated)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1},
    )

    assert result.code == 400
    assert result.data is None
    assert "用户" in result.msg
    assert provider_calls == 0


@pytest.mark.asyncio
async def test_opportunity_charges_successful_provider_call_before_semantic_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    charged_request_ids: list[str] = []

    async def allowed(_payload: dict) -> dict:
        return {"enough": True}

    async def generated(*_args, **kwargs) -> dict:
        return {
            "ok": True,
            "content": "旧标题\n旧正文",
            "provider": "test",
            "model": "test",
            "requestId": kwargs["request_id"],
            "usage": {},
        }

    async def no_restriction() -> str:
        return ""

    async def unchanged(title: str, content: str) -> tuple[str, str, list[str]]:
        return title, content, []

    async def charged(**kwargs) -> dict:
        charged_request_ids.append(kwargs["request_id"])
        return {"deducted": True, "requestId": kwargs["request_id"]}

    monkeypatch.setattr(opportunity, "precheck_ai_usage", allowed)
    monkeypatch.setattr(opportunity, "generate_text", generated)
    monkeypatch.setattr(opportunity, "get_polish_keywords_restriction", no_restriction)
    monkeypatch.setattr(opportunity, "enforce_polish_restriction", unchanged)
    monkeypatch.setattr(opportunity, "charge_text_usage", charged)

    result = await opportunity.rewrite_opportunity_item(
        {"item": {"title": "旧标题", "description": "旧正文"}},
        current_user={"tenant_id": 1, "user_id": 7},
    )

    assert result.code == 502
    assert len(charged_request_ids) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "body", "generated_content"),
    [
        (workflow.ai_screen_goods, {"screenPrompt": "只要数码", "title": "手机"}, '{"passed":true,"reason":"符合","score":90}'),
        (workflow.ai_rewrite_goods, {"title": "旧标题", "description": "旧正文"}, '{"title":"新标题","description":"新正文","highlights":[]}'),
        (workflow.ai_extract_keywords, {"text": "软件安装包 PSD源文件"}, '["软件安装包","PSD源文件"]'),
    ],
)
async def test_workflow_ai_routes_fail_closed_before_provider_when_precheck_rejects(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    body: dict,
    generated_content: str,
) -> None:
    provider_calls = 0

    async def java_billing_boundary(path: str, payload: dict) -> dict:
        if path.endswith("/precheck"):
            return {"enough": False}
        return {"deducted": True, "requestId": payload["requestId"]}

    async def generated(*_args, **_kwargs) -> dict:
        nonlocal provider_calls
        provider_calls += 1
        return {
            "ok": True,
            "content": generated_content,
            "provider": "test-provider",
            "model": "test-model",
            "requestId": "provider-request",
            "usage": {},
        }

    monkeypatch.setattr(ai_billing, "_post_java", java_billing_boundary)
    monkeypatch.setattr(workflow, "generate_text", generated)

    result = await handler(body=body, db=None, current_user={"tenant_id": 1, "user_id": 7})

    assert result.code == 402
    assert result.data is None
    assert provider_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "body", "generated_content"),
    [
        (workflow.ai_screen_goods, {"screenPrompt": "只要数码", "title": "手机"}, '{"passed":true,"reason":"符合","score":90}'),
        (workflow.ai_rewrite_goods, {"title": "旧标题", "description": "旧正文"}, '{"title":"新标题","description":"新正文","highlights":[]}'),
        (workflow.ai_extract_keywords, {"text": "软件安装包 PSD源文件"}, '["软件安装包","PSD源文件"]'),
    ],
)
async def test_workflow_ai_routes_do_not_return_generated_data_when_charge_fails(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    body: dict,
    generated_content: str,
) -> None:
    async def allowed(_payload: dict) -> dict:
        return {"enough": True}

    async def generated(*_args, **kwargs) -> dict:
        return {
            "ok": True,
            "content": generated_content,
            "provider": "test-provider",
            "model": "test-model",
            "requestId": kwargs["request_id"],
            "usage": {},
        }

    async def failed_charge(**_kwargs) -> dict:
        raise ai_billing.AiBillingUnavailable("billing unavailable")

    monkeypatch.setattr(workflow, "precheck_ai_usage", allowed)
    monkeypatch.setattr(workflow, "generate_text", generated)
    monkeypatch.setattr(workflow, "charge_text_usage", failed_charge)

    result = await handler(body=body, db=None, current_user={"tenant_id": 1, "user_id": 7})

    assert result.code == 503
    assert result.data is None


@pytest.mark.asyncio
async def test_runtime_product_filter_stops_when_billing_precheck_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls = 0

    async def resolve_user(*_args, **_kwargs) -> int:
        return 7

    async def rejected(_payload: dict) -> dict:
        raise ai_billing.AiBillingPaymentRequired("insufficient")

    async def generated(*_args, **_kwargs) -> dict:
        nonlocal provider_calls
        provider_calls += 1
        return {"ok": True, "content": "符合"}

    monkeypatch.setattr(automation_runtime, "_resolve_account_user_id", resolve_user)
    monkeypatch.setattr(automation_runtime, "precheck_ai_usage", rejected)
    monkeypatch.setattr(automation_runtime, "generate_text", generated)

    result = await automation_runtime._execute_workflow_node(
        db=None,
        tenant_id=1,
        typ="PRODUCT_FILTER",
        config={"userPrompt": "只要数码"},
        context={"__execution_id__": 99},
        state={
            "selected_account_ids": [12],
            "selected_products": [{"id": "goods-1", "title": "手机", "price": 100}],
            "target_count": 1,
        },
    )

    assert result["ok"] is False
    assert result["errorCode"] == "AI_BALANCE_INSUFFICIENT"
    assert provider_calls == 0


@pytest.mark.asyncio
async def test_runtime_product_filter_does_not_advance_when_charge_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve_user(*_args, **_kwargs) -> int:
        return 7

    async def allowed(_payload: dict) -> dict:
        return {"enough": True}

    async def generated(*_args, **_kwargs) -> dict:
        return {"ok": True, "content": "符合", "provider": "test", "model": "test", "usage": {}}

    async def charge_failed(**_kwargs) -> dict:
        raise ai_billing.AiBillingUnavailable("down")

    monkeypatch.setattr(automation_runtime, "_resolve_account_user_id", resolve_user)
    monkeypatch.setattr(automation_runtime, "precheck_ai_usage", allowed)
    monkeypatch.setattr(automation_runtime, "generate_text", generated)
    monkeypatch.setattr(automation_runtime, "charge_text_usage", charge_failed)

    result = await automation_runtime._execute_workflow_node(
        db=None,
        tenant_id=1,
        typ="PRODUCT_FILTER",
        config={"userPrompt": "只要数码"},
        context={"__execution_id__": 99},
        state={
            "selected_account_ids": [12],
            "selected_products": [{"id": "goods-1", "title": "手机", "price": 100}],
            "target_count": 1,
        },
    )

    assert result["ok"] is False
    assert result["errorCode"] == "AI_BILLING_UNAVAILABLE"
    assert result["items"] == []


@pytest.mark.asyncio
async def test_runtime_product_polish_stops_before_provider_when_precheck_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls = 0

    class EmptyProviderResult:
        def scalar_one_or_none(self):
            return None

    class FakeDb:
        async def execute(self, _statement):
            return EmptyProviderResult()

    async def resolve_user(*_args, **_kwargs) -> int:
        return 7

    async def empty_restriction():
        return ""

    async def no_forbidden():
        return []

    async def rejected(_payload: dict) -> dict:
        raise ai_billing.AiBillingPaymentRequired("insufficient")

    async def generated(*_args, **_kwargs) -> dict:
        nonlocal provider_calls
        provider_calls += 1
        return {"ok": True, "content": '{"title":"新标题","body":"新正文"}'}

    monkeypatch.setattr(automation_runtime, "_resolve_account_user_id", resolve_user)
    monkeypatch.setattr(automation_runtime, "get_polish_keywords_restriction", empty_restriction)
    monkeypatch.setattr(automation_runtime, "get_polish_forbidden_keywords", no_forbidden)
    monkeypatch.setattr(automation_runtime, "precheck_ai_usage", rejected)
    monkeypatch.setattr(automation_runtime, "generate_text", generated)

    result = await automation_runtime._execute_workflow_node(
        db=FakeDb(),
        tenant_id=1,
        typ="PRODUCT_POLISH",
        config={"tone": "简洁"},
        context={"__execution_id__": 99},
        state={
            "selected_account_ids": [12],
            "selected_products": [{"id": "goods-1", "title": "旧标题", "description": "旧正文"}],
        },
    )

    assert result["ok"] is False
    assert result["errorCode"] == "AI_BALANCE_INSUFFICIENT"
    assert provider_calls == 0


@pytest.mark.asyncio
async def test_runtime_product_polish_never_uses_generated_content_after_unexpected_charge_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyProviderResult:
        def scalar_one_or_none(self):
            return None

    class FakeDb:
        async def execute(self, _statement):
            return EmptyProviderResult()

    async def resolve_user(*_args, **_kwargs) -> int:
        return 7

    async def empty_restriction():
        return ""

    async def no_forbidden():
        return []

    async def allowed(_payload: dict) -> dict:
        return {"enough": True}

    async def generated(*_args, **_kwargs) -> dict:
        return {
            "ok": True,
            "content": '{"title":"未扣费标题","body":"未扣费正文"}',
            "provider": "test",
            "model": "test",
            "usage": {},
        }

    async def broken_charge(**_kwargs) -> dict:
        raise ValueError("unexpected usage payload")

    monkeypatch.setattr(automation_runtime, "_resolve_account_user_id", resolve_user)
    monkeypatch.setattr(automation_runtime, "get_polish_keywords_restriction", empty_restriction)
    monkeypatch.setattr(automation_runtime, "get_polish_forbidden_keywords", no_forbidden)
    monkeypatch.setattr(automation_runtime, "precheck_ai_usage", allowed)
    monkeypatch.setattr(automation_runtime, "generate_text", generated)
    monkeypatch.setattr(automation_runtime, "charge_text_usage", broken_charge)

    result = await automation_runtime._execute_workflow_node(
        db=FakeDb(),
        tenant_id=1,
        typ="PRODUCT_POLISH",
        config={"tone": "简洁"},
        context={"__execution_id__": 99},
        state={
            "selected_account_ids": [12],
            "selected_products": [{"id": "goods-1", "title": "旧标题", "description": "旧正文"}],
        },
    )

    assert result["ok"] is False
    assert result["errorCode"] == "AI_MODEL_UNAVAILABLE"
    assert result["polished"] == []


@pytest.mark.asyncio
async def test_billing_transport_retries_keep_the_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    seen_request_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen_request_ids.append(payload["requestId"])
        if len(seen_request_ids) < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            json={"code": 0, "data": {"deducted": True, "requestId": payload["requestId"]}},
            request=request,
        )

    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_billing.settings, "core_api_base_url", "https://billing.example")
    monkeypatch.setattr(ai_billing.httpx, "AsyncClient", client_factory)

    result = await ai_billing.charge_ai_usage({
        "tenantId": 1,
        "userId": 7,
        "scene": "test",
        "requestId": "stable-request-id",
    })

    assert result["deducted"] is True
    assert seen_request_ids == ["stable-request-id"] * 3


@pytest.mark.asyncio
async def test_billing_maps_upstream_payment_required_to_safe_402(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            402,
            json={"code": 402, "msg": "internal balance detail"},
            request=request,
        )
    )

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_billing.settings, "core_api_base_url", "https://billing.example")
    monkeypatch.setattr(ai_billing.httpx, "AsyncClient", client_factory)

    with pytest.raises(ai_billing.AiBillingPaymentRequired) as exc_info:
        await ai_billing.precheck_ai_usage({
            "tenantId": 1,
            "userId": 7,
            "scene": "test",
            "requestId": "request-id",
        })

    assert exc_info.value.status_code == 402
    assert "internal balance detail" not in exc_info.value.user_message


@pytest.mark.asyncio
async def test_billing_rejects_oversized_upstream_response_without_buffering_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"x" * (ai_billing.MAX_BILLING_RESPONSE_BYTES + 1),
            request=request,
        )
    )

    def client_factory(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_billing.settings, "core_api_base_url", "https://billing.example")
    monkeypatch.setattr(ai_billing.httpx, "AsyncClient", client_factory)

    with pytest.raises(ai_billing.AiBillingUnavailable):
        await ai_billing.precheck_ai_usage({
            "tenantId": 1,
            "userId": 7,
            "scene": "test",
            "requestId": "request-id",
        })


@pytest.mark.parametrize("path", SCOPED_AI_FILES, ids=lambda path: path.name)
def test_all_scoped_generate_text_calls_supply_a_stable_request_id(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else ""
        if name not in {"generate_text", "generate_text_func"}:
            continue
        if not any(keyword.arg == "request_id" for keyword in node.keywords):
            missing.append(node.lineno)
    assert missing == [], f"generate_text calls without request_id in {path.name}: {missing}"


@pytest.mark.parametrize("path", SCOPED_AI_FILES, ids=lambda path: path.name)
def test_scoped_ai_paths_do_not_document_or_implement_non_blocking_charge(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert "扣费（失败不阻断" not in source
    assert 'request_id=""' not in source


@pytest.mark.parametrize(
    ("relative_path", "scene"),
    [
        ("app/api/v1/routes/opportunity.py", "opportunity_rewrite"),
        ("app/api/v1/routes/workflow.py", "workflow_screen"),
        ("app/api/v1/routes/workflow.py", "workflow_rewrite"),
        ("app/api/v1/routes/workflow.py", "workflow_extract_keywords"),
        ("app/services/automation_runtime.py", "workflow_category_suggest"),
        ("app/services/automation_runtime.py", "auto_reply"),
        ("app/services/automation_runtime.py", "product_filter"),
        ("app/services/automation_runtime.py", "product_polish"),
        ("app/services/feishu_chat.py", "feishu_chat_intent"),
    ],
)
def test_expected_billable_text_scenes_remain_in_the_audited_inventory(
    relative_path: str,
    scene: str,
) -> None:
    source = (SERVICE_ROOT / relative_path).read_text(encoding="utf-8")
    assert f'"{scene}"' in source
    assert "precheck_ai_usage" in source
    assert "charge_text_usage" in source
