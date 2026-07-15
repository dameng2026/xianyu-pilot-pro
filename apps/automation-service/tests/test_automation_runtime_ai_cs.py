import pytest

from app.api.v1.routes.auto_reply_scope import _compute_effective
from app.services import automation_runtime
from app.services.automation_runtime import (
    _build_ai_cs_system_prompt,
    _build_goods_context_text,
    _compose_final_image_prompt,
    _compute_ai_cs_effective_enabled,
    _is_account_active_for_auto_reply,
    _match_image_prompt_category_with_ai,
    _match_image_prompt_category,
    _normalize_ai_cs_entries,
    _prepare_image_prompt_category_configs,
    _render_image_prompt_template,
    _resolve_account_chat_role,
    _resolve_image_prompt_for_item_with_ai,
    _resolve_image_prompt_for_item,
    process_incoming_message,
    _resolve_effective_buyer_id,
    _resolve_effective_buyer_id_from_sid,
)


def test_normalize_ai_cs_entries_uses_fallback_text():
    entries = _normalize_ai_cs_entries(None, fallback_text="仅按商品资料回复", prefix="知识库", source="user")

    assert entries == [{
        "name": "知识库 1",
        "content": "仅按商品资料回复",
        "source": "user",
    }]


def test_compute_ai_cs_effective_enabled_prefers_product_scope():
    assert _compute_ai_cs_effective_enabled(
        global_enabled=True,
        account_id=9,
        account_scopes={"accounts": {"9": True}},
        product_enabled=0,
    ) is False

    assert _compute_ai_cs_effective_enabled(
        global_enabled=True,
        account_id=9,
        account_scopes={"accounts": {"9": False}},
        product_enabled=1,
    ) is True

    assert _compute_ai_cs_effective_enabled(
        global_enabled=False,
        account_id=9,
        account_scopes={"accounts": {"9": True}},
        product_enabled=1,
    ) is False


def test_compute_ai_cs_effective_enabled_inherits_global_when_account_scope_missing():
    assert _compute_ai_cs_effective_enabled(
        global_enabled=True,
        account_id=9,
        account_scopes={"accounts": {}},
        product_enabled=None,
    ) is True

    assert _compute_ai_cs_effective_enabled(
        global_enabled=True,
        account_id=9,
        account_scopes={"accounts": {"9": False}},
        product_enabled=None,
    ) is False


def test_auto_reply_scope_effective_state_inherits_global_when_unscoped():
    assert _compute_effective(None, 9, {"accounts": {}}, True) is True
    assert _compute_effective(None, 9, {"accounts": {"9": False}}, True) is False
    assert _compute_effective(None, 9, {"accounts": {"9": True}}, True) is True
    assert _compute_effective(0, 9, {"accounts": {}}, True) is False


def test_build_goods_context_text_handles_missing_goods():
    text = _build_goods_context_text(None)

    assert "还没有查到" in text
    assert "等人工再帮他确认" in text


def test_build_ai_cs_system_prompt_prioritizes_user_entries():
    prompt = _build_ai_cs_system_prompt(
        {"systemPrompt": "你是店铺客服"},
        {
            "external_goods_id": "12345",
            "title": "华擎 RX5500XT 8G",
            "price": "5600",
            "sold_price": "5600",
            "quantity": 1,
            "category": "显卡",
            "status": 1,
            "description": "8G 挑战者 成色如图",
            "detail_url": "https://www.goofish.com/item?itemId=12345",
            "image_urls": ["https://img.example/1.jpg"],
        },
        [{"name": "用户知识库", "content": "优先说明当前商品成色。", "source": "user"}],
        [{"name": "用户规则", "content": "不要讨论平台规则。", "source": "user"}],
        [{"name": "默认知识库", "content": "补充默认售前口径。", "source": "default"}],
        [{"name": "默认规则", "content": "信息不足时转人工。", "source": "default"}],
    )

    user_kb_pos = prompt.find("优先说明当前商品成色。")
    default_kb_pos = prompt.find("补充默认售前口径。")

    assert "商品标题：华擎 RX5500XT 8G" in prompt
    assert "不要讨论平台规则。" in prompt
    assert user_kb_pos != -1
    assert default_kb_pos != -1
    assert user_kb_pos < default_kb_pos


def test_build_ai_cs_system_prompt_avoids_proactive_ai_identity():
    prompt = _build_ai_cs_system_prompt(
        {"systemPrompt": "你是店里负责接待买家的客服"},
        None,
        [],
        [],
        [],
        [],
    )

    assert "我是AI" not in prompt
    assert "我是 AI" not in prompt
    assert "当前店铺的商品客服" in prompt
    assert "像真人客服一样自然礼貌" in prompt


def test_build_goods_context_text_uses_human_fallback_tone():
    text = _build_goods_context_text(None)

    assert "暂时确认不了" in text
    assert "请买家查看商品页或等人工再帮他确认" in text


def test_resolve_effective_buyer_id_prefers_real_peer_when_buyer_is_seller():
    buyer_id = _resolve_effective_buyer_id(
        {
            "buyerId": "2211422464341@goofish",
            "peerUserId": "25945493@goofish",
            "sellerExternalUid": "2211422464341",
        }
    )

    assert buyer_id == "25945493@goofish"


def test_resolve_effective_buyer_id_rejects_seller_self_without_peer():
    buyer_id = _resolve_effective_buyer_id(
        {
            "buyerId": "2211422464341@goofish",
            "sellerExternalUid": "2211422464341",
        }
    )

    assert buyer_id == ""


def test_match_image_prompt_category_prefers_highest_keyword_score():
    matched = _match_image_prompt_category(
        "优酷 svip 会员 7天 周卡",
        "自动发货 支持手机电视",
        [
            {"categoryKey": "源码", "matchKeywords": "源码,程序,小程序", "promptTemplate": "A"},
            {"categoryKey": "会员卡", "matchKeywords": "会员,svip,周卡,自动发货", "promptTemplate": "B"},
        ],
    )

    assert matched["categoryKey"] == "会员卡"


def test_render_image_prompt_template_replaces_title_and_content():
    prompt = _render_image_prompt_template("TITLE={{TITLE}}|CONTENT={{CONTENT}}", "程序代做", "支持 Java Python")

    assert prompt == "TITLE=程序代做|CONTENT=支持 Java Python"


def test_compose_final_image_prompt_adds_context_for_short_template():
    prompt = _compose_final_image_prompt(
        "根据标题与正文生成合适的闲鱼商品主图",
        "Win10纯净版ISO镜像系统官方原版",
        "无广告无捆绑 多版本可选 自动发货",
    )

    assert "商品标题：Win10纯净版ISO镜像系统官方原版" in prompt
    assert "商品正文：无广告无捆绑 多版本可选 自动发货" in prompt
    assert "不要只生成背景底图" in prompt
    assert "不要底部红黄横条" in prompt


def test_compose_final_image_prompt_keeps_rendered_template_without_duplicate_context():
    prompt = _compose_final_image_prompt(
        "主图标题={{TITLE}}|主图内容={{CONTENT}}",
        "优酷SVIP周卡",
        "自动发货 支持手机电视电脑",
    )

    assert "主图标题=优酷SVIP周卡|主图内容=自动发货 支持手机电视电脑" in prompt
    assert "商品标题：" not in prompt
    assert "商品正文：" not in prompt


def test_resolve_image_prompt_for_item_uses_custom_prompt_mode():
    prompt, matched = _resolve_image_prompt_for_item(
        prompt_mode="custom",
        custom_prompt="CUSTOM {{TITLE}}",
        fallback_prompt="DEFAULT",
        title="Steam 激活码",
        description="自动发货",
        category_prompts=[
            {"categoryKey": "游戏", "matchKeywords": "steam,激活码", "promptTemplate": "GAME {{TITLE}}"}
        ],
    )

    assert prompt == "CUSTOM Steam 激活码"
    assert matched is None


def test_resolve_image_prompt_for_item_reclassifies_each_item_in_default_mode():
    prompt, matched = _resolve_image_prompt_for_item(
        prompt_mode="default",
        custom_prompt="",
        fallback_prompt="DEFAULT {{TITLE}}",
        title="优酷 svip 周卡",
        description="支持手机电视",
        category_prompts=[
            {"categoryKey": "会员卡", "matchKeywords": "会员,svip,周卡", "promptTemplate": "VIP {{TITLE}}"},
            {"categoryKey": "源码", "matchKeywords": "源码,程序", "promptTemplate": "CODE {{TITLE}}"},
        ],
    )

    assert prompt == "VIP 优酷 svip 周卡"
    assert matched["categoryKey"] == "会员卡"


def test_prepare_image_prompt_category_configs_filters_disabled_and_sorts():
    prepared = _prepare_image_prompt_category_configs([
        {"id": 9, "categoryKey": "generic_virtual", "sortOrder": 999, "enabled": True, "status": "正常"},
        {"id": 5, "categoryKey": "video_template", "sortOrder": 95, "enabled": True, "status": "正常"},
        {"id": 3, "categoryKey": "disabled_prompt", "sortOrder": 1, "enabled": False, "status": "正常"},
        {"id": 2, "categoryKey": "membership_vip", "sortOrder": 10, "enabled": True, "status": "正常"},
        {"id": 1, "categoryKey": "game_cdk", "sortOrder": 10, "enabled": True, "status": "正常"},
    ])

    assert [item["categoryKey"] for item in prepared] == ["game_cdk", "membership_vip", "video_template", "generic_virtual"]


@pytest.mark.anyio
async def test_match_image_prompt_category_with_ai_prefers_ai_selected_key(monkeypatch):
    async def allowed(_payload):
        return {"enough": True}

    async def charged(**kwargs):
        return {"deducted": True, "requestId": kwargs["request_id"]}

    async def fake_generate_text(scene, system_prompt, user_prompt, temperature, **kwargs):
        assert scene == "workflow_image_prompt_select"
        assert "game_cdk" in user_prompt
        return {"ok": True, "content": "{\"categoryKey\":\"game_cdk\"}", "requestId": kwargs["request_id"]}

    monkeypatch.setattr(automation_runtime, "precheck_ai_usage", allowed)
    monkeypatch.setattr(automation_runtime, "charge_text_usage", charged)

    matched = await _match_image_prompt_category_with_ai(
        "Steam 激活码 自动发货",
        "支持 DLC 入库",
        [
            {"categoryKey": "membership_vip", "name": "会员卡", "matchKeywords": "会员,周卡"},
            {"categoryKey": "game_cdk", "name": "游戏激活码", "matchKeywords": "Steam,CDK,DLC"},
        ],
        tenant_id=1,
        user_id=7,
        generate_text_func=fake_generate_text,
    )

    assert matched["categoryKey"] == "game_cdk"


@pytest.mark.anyio
async def test_resolve_image_prompt_for_item_with_ai_uses_ai_selected_template(monkeypatch):
    async def allowed(_payload):
        return {"enough": True}

    async def charged(**kwargs):
        return {"deducted": True, "requestId": kwargs["request_id"]}

    async def fake_generate_text(scene, system_prompt, user_prompt, temperature, **kwargs):
        return {"ok": True, "content": "{\"categoryKey\":\"dev_service\"}", "requestId": kwargs["request_id"]}

    monkeypatch.setattr(automation_runtime, "precheck_ai_usage", allowed)
    monkeypatch.setattr(automation_runtime, "charge_text_usage", charged)

    prompt, matched = await _resolve_image_prompt_for_item_with_ai(
        prompt_mode="default",
        custom_prompt="",
        fallback_prompt="DEFAULT {{TITLE}}",
        title="程序代做 Java Python",
        description="一对一沟通 急单可做",
        category_prompts=[
            {"categoryKey": "dev_service", "matchKeywords": "代做,接单", "promptTemplate": "SERVICE {{TITLE}}"},
            {"categoryKey": "source_code", "matchKeywords": "源码,程序", "promptTemplate": "CODE {{TITLE}}"},
        ],
        tenant_id=1,
        user_id=7,
        generate_text_func=fake_generate_text,
    )

    assert prompt == "SERVICE 程序代做 Java Python"
    assert matched["categoryKey"] == "dev_service"


class _FakeResult:
    def __init__(self, *, row=None):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row

    def scalar(self):
        if isinstance(self._row, dict):
            return next(iter(self._row.values()), None)
        return self._row


class _BuyerFallbackDB:
    def __init__(self):
        self.calls = 0

    async def execute(self, _statement, _params=None):
        self.calls += 1
        if self.calls == 1:
            return _FakeResult(row={
                "sender_user_id": "25945493@goofish",
                "peer_external_uid": "",
                "receiver_user_id": "2211422464341@goofish",
            })
        return _FakeResult(row=None)


class _DeletedAccountDB:
    def __init__(self):
        self.calls = []

    async def execute(self, _statement, _params=None):
        self.calls.append(str(_statement))
        if len(self.calls) == 1:
            return _FakeResult(row=None)
        raise AssertionError("deleted account should short-circuit before any further DB writes")


class _BuyerRoleSkipDB:
    def __init__(self):
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        if len(self.calls) == 1:
            return _FakeResult(row={"status": 1})
        raise AssertionError("buyer role should short-circuit before any write path")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_resolve_effective_buyer_id_from_sid_uses_recent_message_when_sender_missing():
    buyer_id = await _resolve_effective_buyer_id_from_sid(
        _BuyerFallbackDB(),
        tenant_id=1,
        account_id=9,
        payload={
            "sId": "63154410580",
            "buyerId": "",
            "senderUserId": "",
            "sellerExternalUid": "2211422464341",
        },
    )

    assert buyer_id == "25945493@goofish"


@pytest.mark.anyio
async def test_is_account_active_for_auto_reply_returns_false_when_account_missing():
    db = _DeletedAccountDB()

    active = await _is_account_active_for_auto_reply(db, tenant_id=1, account_id=9)

    assert active is False


@pytest.mark.anyio
async def test_process_incoming_message_skips_deleted_account_before_reply_flow():
    db = _DeletedAccountDB()

    result = await process_incoming_message(db, {
        "tenantId": 1,
        "accountId": 9,
        "content": "hello",
    })

    assert result["ok"] is True
    assert result["matched"] is False
    assert result["autoSent"] is False
    assert "deleted" in result["message"].lower() or "停用" in result["message"] or "删除" in result["message"]
    assert len(db.calls) == 1


@pytest.mark.anyio
async def test_resolve_account_chat_role_marks_seller_when_owner_matches_current_account():
    role = await _resolve_account_chat_role(
        _BuyerFallbackDB(),
        tenant_id=1,
        account_id=9,
        payload={
            "sellerExternalUid": "2211422464341",
            "ownerUserId": "2211422464341",
            "itemSellerId": "2211422464341",
            "goodsId": "1062282487203",
        },
    )

    assert role == "seller"


@pytest.mark.anyio
async def test_resolve_account_chat_role_marks_buyer_when_owner_differs_from_current_account():
    role = await _resolve_account_chat_role(
        _BuyerFallbackDB(),
        tenant_id=1,
        account_id=9,
        payload={
            "sellerExternalUid": "2211422464341",
            "ownerUserId": "1678242685",
            "itemSellerId": "1678242685",
            "groupOwnerId": "1678242685",
            "goodsId": "993739040368",
        },
    )

    assert role == "buyer"


@pytest.mark.anyio
async def test_process_incoming_message_skips_when_current_account_is_buyer():
    db = _BuyerRoleSkipDB()

    result = await process_incoming_message(db, {
        "tenantId": 1,
        "accountId": 9,
        "sellerExternalUid": "2211422464341",
        "ownerUserId": "1678242685",
        "itemSellerId": "1678242685",
        "groupOwnerId": "1678242685",
        "buyerId": "1678242685@goofish",
        "content": "buyer-side message",
        "sId": "63154410580",
    })

    assert result["ok"] is True
    assert result["matched"] is False
    assert result["autoSent"] is False
    assert "buyer" in result["message"].lower() or "买家" in result["message"]
    assert len(db.calls) == 1
