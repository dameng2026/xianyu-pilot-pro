"""小梦客服 (xiaomeng-assistant) 运行时与工具调用回归测试。

覆盖场景：
1. build_fallback_summary 在 generate_summary AI 调用失败时的兜底自然语言摘要
2. list_refunds / import_cards 工具元信息正确注册到 TOOL_REGISTRY / QUERY_TOOLS
3. create_card_group 支持 cards 数组参数（元信息层校验）
4. build_system_prompt 包含「绝不返回代码/JSON」硬性约束

这些测试不连接数据库，仅做纯函数级校验，避免引入外部依赖。
数据库相关的端到端验证由 _verify_xiaomeng_fix.py 临时脚本承担（已删除）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保 app 包可被导入
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_cs_runtime import build_fallback_summary, _fmt_dt  # noqa: E402
from app.services.ai_cs_tools import (  # noqa: E402
    TOOL_REGISTRY,
    TOOL_DEFINITIONS,
    QUERY_TOOLS,
    is_query_tool,
)


# ============================================================
# 工具注册表完整性
# ============================================================

def test_list_refunds_registered_as_query_tool():
    """list_refunds 应注册为查询类工具，可在 stream_chat 中自动执行。"""
    assert "list_refunds" in TOOL_REGISTRY
    assert "list_refunds" in QUERY_TOOLS
    assert is_query_tool("list_refunds") is True


def test_import_cards_registered_as_write_tool():
    """import_cards 是写操作类工具，不应在 QUERY_TOOLS 中（需用户确认）。"""
    assert "import_cards" in TOOL_REGISTRY
    assert "import_cards" not in QUERY_TOOLS
    assert is_query_tool("import_cards") is False


def test_tool_definitions_include_new_tools():
    """TOOL_DEFINITIONS 应包含 list_refunds / import_cards 的元信息。"""
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert "list_refunds" in names
    assert "import_cards" in names


def test_create_card_group_definition_has_cards_param():
    """create_card_group 元信息应包含 cards 数组参数（支持批量导入卡密）。"""
    defs = {t["name"]: t for t in TOOL_DEFINITIONS}
    assert "cards" in defs["create_card_group"]["parameters"]


def test_tool_registry_and_definitions_in_sync():
    """TOOL_REGISTRY 与 TOOL_DEFINITIONS 的工具名应完全一致。"""
    registry_names = set(TOOL_REGISTRY.keys())
    definition_names = {t["name"] for t in TOOL_DEFINITIONS}
    assert registry_names == definition_names, (
        f"差异：仅注册表有 {registry_names - definition_names}，"
        f"仅定义有 {definition_names - registry_names}"
    )


# ============================================================
# build_fallback_summary 各工具场景
# ============================================================

def test_fallback_summary_list_accounts_with_deleted():
    """list_accounts 兜底摘要应展示账号列表，标注软删除账号。"""
    summary = build_fallback_summary(
        user_message="我的账号",
        tool_name="list_accounts",
        tool_result={
            "success": True,
            "data": {
                "accounts": [
                    {
                        "id": 1, "nickname": "小龙菜菜",
                        "accountStatus": "正常", "onlineStatus": "在线",
                        "cookieStatus": "正常", "healthScore": 95, "healthLevel": "优秀",
                    },
                    {
                        "id": 2, "nickname": "大梦服务",
                        "accountStatus": "已禁用（已删除）", "onlineStatus": "离线",
                        "cookieStatus": "已过期", "healthScore": 50, "healthLevel": "一般",
                    },
                ],
                "total": 2, "activeCount": 1, "deletedCount": 1,
            },
        },
    )
    assert "小龙菜菜" in summary
    assert "大梦服务" in summary
    assert "已禁用" in summary
    assert "1 个正常、1 个已禁用" in summary
    # 绝不能出现 JSON / 字段名等技术细节
    assert "accounts" not in summary
    assert "nickname" not in summary
    assert "{" not in summary


def test_fallback_summary_list_accounts_empty():
    """list_accounts 空结果应引导用户绑定新账号。"""
    summary = build_fallback_summary(
        user_message="我的账号",
        tool_name="list_accounts",
        tool_result={"success": True, "data": {"accounts": [], "total": 0}},
    )
    assert "暂无闲鱼账号" in summary
    assert "扫码登录" in summary or "绑定" in summary


def test_fallback_summary_list_refunds_with_data():
    """list_refunds 兜底摘要应展示退款列表，包含金额/状态/时间。"""
    summary = build_fallback_summary(
        user_message="最近有没有退款",
        tool_name="list_refunds",
        tool_result={
            "success": True,
            "data": {
                "refunds": [
                    {
                        "itemTitle": "二手手机",
                        "refundFee": "100.00",
                        "refundStatusDesc": "退款成功",
                        "buyerNick": "张三",
                        "refundCreateTime": "2026-07-25T15:21:43",
                    },
                ],
                "total": 1,
            },
        },
    )
    assert "1 条退款记录" in summary
    assert "二手手机" in summary
    assert "100.00" in summary
    assert "退款成功" in summary
    assert "张三" in summary
    assert "2026-07-25 15:21" in summary
    # 绝不能出现 JSON
    assert "{" not in summary
    assert "refundFee" not in summary


def test_fallback_summary_list_refunds_empty():
    """list_refunds 空结果应让用户放心。"""
    summary = build_fallback_summary(
        user_message="最近有没有退款",
        tool_name="list_refunds",
        tool_result={"success": True, "data": {"refunds": [], "total": 0}},
    )
    assert "没有查询到退款记录" in summary


def test_fallback_summary_create_card_group_with_import():
    """create_card_group 兜底摘要应展示分组名+导入条数。"""
    summary = build_fallback_summary(
        user_message="帮我建卡密仓库",
        tool_name="create_card_group",
        tool_result={
            "success": True,
            "data": {
                "groupId": 99, "groupName": "我的卡密库", "importedCount": 3,
            },
        },
    )
    assert "我的卡密库" in summary
    assert "99" in summary
    assert "3 条卡密" in summary


def test_fallback_summary_import_cards():
    """import_cards 兜底摘要应展示导入条数。"""
    summary = build_fallback_summary(
        user_message="加卡密",
        tool_name="import_cards",
        tool_result={
            "success": True,
            "data": {"groupId": 99, "importedCount": 5},
        },
    )
    assert "99" in summary
    assert "5 条卡密" in summary


def test_fallback_summary_failure_case():
    """工具失败时兜底摘要应友好提示重试。"""
    summary = build_fallback_summary(
        user_message="查询",
        tool_name="list_accounts",
        tool_result={"success": False, "error": "数据库连接失败", "data": None},
    )
    assert "数据库连接失败" in summary
    assert "重试" in summary or "换种方式" in summary


def test_fallback_summary_unknown_tool_uses_generic_template():
    """未知工具应走通用兜底模板，不崩溃。"""
    summary = build_fallback_summary(
        user_message="测试",
        tool_name="some_unknown_tool",
        tool_result={"success": True, "data": {"foo": "bar", "items": [1, 2, 3]}},
    )
    assert "已为您处理完毕" in summary
    # 通用模板会列出关键字段摘要
    assert "items" in summary or "foo" in summary


def test_fallback_summary_never_returns_code_or_json():
    """所有工具的兜底摘要都不能包含 JSON 代码块或字段名等技术细节。"""
    cases = [
        ("list_accounts", {"success": True, "data": {"accounts": [{"id": 1, "nickname": "测试"}], "total": 1}}),
        ("list_refunds", {"success": True, "data": {"refunds": [], "total": 0}}),
        ("list_orders", {"success": True, "data": {"orders": [], "total": 0}}),
        ("list_card_groups", {"success": True, "data": {"groups": [], "total": 0}}),
        ("create_card_group", {"success": True, "data": {"groupId": 1, "groupName": "x", "importedCount": 0}}),
        ("import_cards", {"success": True, "data": {"groupId": 1, "importedCount": 1}}),
        ("get_token_balance", {"success": True, "data": {"balance": 100}}),
    ]
    for tool_name, result in cases:
        summary = build_fallback_summary(
            user_message="test", tool_name=tool_name, tool_result=result,
        )
        # 绝不能出现 ``` 代码块、JSON 大括号、字段名等技术细节
        assert "```" not in summary, f"工具 {tool_name} 兜底摘要出现代码块：{summary}"
        assert "{" not in summary, f"工具 {tool_name} 兜底摘要出现 JSON 大括号：{summary}"
        assert "success" not in summary, f"工具 {tool_name} 兜底摘要出现 success 字段名：{summary}"
        assert "data" not in summary, f"工具 {tool_name} 兜底摘要出现 data 字段名：{summary}"


# ============================================================
# _fmt_dt 时间格式化
# ============================================================

def test_fmt_dt_iso_string_to_yyyy_mm_dd_hh_mm():
    assert _fmt_dt("2026-07-25T15:21:43") == "2026-07-25 15:21"


def test_fmt_dt_empty_returns_empty():
    assert _fmt_dt("") == ""
    assert _fmt_dt(None) == ""


# ============================================================
# build_system_prompt 硬性约束
# ============================================================

def test_build_system_prompt_contains_no_code_constraint():
    """系统提示词应明确要求小梦不返回代码/JSON。

    这个测试需要数据库连接，此处仅校验常量片段是否存在。
    实际的 build_system_prompt 集成测试由 e2e 脚本承担。
    """
    # 直接读取源码文件，校验关键约束字符串存在
    src_path = ROOT / "app" / "services" / "ai_cs_runtime.py"
    src = src_path.read_text(encoding="utf-8")
    # 硬性约束：必须自然语言回复
    assert "必须用自然语言回复用户" in src
    assert "绝不能返回代码" in src
    # 工具调用规则：绝不向用户展示 tool_call 代码块
    assert "绝不向用户展示" in src
    # 新增能力：退款查询 + 批量建卡密仓库
    assert "list_refunds" in src
    assert "import_cards" in src
    assert "create_card_group" in src
    assert "cards" in src


# ============================================================
# 新增工具注册与摘要测试（v2 扩展：商品管理/消息/数据分析/配置更新/发布）
# ============================================================

# 新增工具应当全部注册到 TOOL_REGISTRY 与 TOOL_DEFINITIONS
_NEW_TOOLS_V2 = [
    # 商品管理增强类
    "get_product_summary",       # 查询
    "delete_product",             # 写
    "toggle_product_status",      # 写
    "search_goods_online",        # 查询
    # 消息类
    "list_recent_conversations",  # 查询
    "reply_buyer_message",        # 写
    # 鱼小铺数据分析类
    "get_fish_shop_data",         # 查询
    "get_sales_comparison",       # 查询
    # 配置更新类
    "update_delivery_statement",  # 写
    "update_workflow",            # 写
    "update_scheduled_task",      # 写
    "update_auto_reply_rule",     # 写
    # 商品发布类
    "prepare_product_publish",    # 写
]

# 新增工具中应当作为查询类（无需用户确认）自动执行
_NEW_QUERY_TOOLS_V2 = {
    "get_product_summary",
    "search_goods_online",
    "list_recent_conversations",
    "get_fish_shop_data",
    "get_sales_comparison",
}

# 新增工具中应当作为写操作类（需用户确认）
_NEW_WRITE_TOOLS_V2 = {
    "delete_product",
    "toggle_product_status",
    "reply_buyer_message",
    "update_delivery_statement",
    "update_workflow",
    "update_scheduled_task",
    "update_auto_reply_rule",
    "prepare_product_publish",
}


def test_all_new_v2_tools_registered():
    """v2 扩展的 13 个新工具应当全部注册到 TOOL_REGISTRY。"""
    for name in _NEW_TOOLS_V2:
        assert name in TOOL_REGISTRY, f"工具 {name} 未注册到 TOOL_REGISTRY"


def test_all_new_v2_tools_have_definitions():
    """v2 扩展的 13 个新工具应当全部有元信息定义。"""
    names = {t["name"] for t in TOOL_DEFINITIONS}
    for name in _NEW_TOOLS_V2:
        assert name in names, f"工具 {name} 缺少元信息定义"


def test_new_v2_query_tools_in_query_set():
    """v2 查询类工具应当在 QUERY_TOOLS 集合中（自动执行无需确认）。"""
    for name in _NEW_QUERY_TOOLS_V2:
        assert name in QUERY_TOOLS, f"查询工具 {name} 未加入 QUERY_TOOLS"
        assert is_query_tool(name) is True


def test_new_v2_write_tools_not_in_query_set():
    """v2 写操作类工具不应当在 QUERY_TOOLS 集合中（需用户确认）。"""
    for name in _NEW_WRITE_TOOLS_V2:
        assert name not in QUERY_TOOLS, f"写工具 {name} 不应在 QUERY_TOOLS 中"
        assert is_query_tool(name) is False


def test_v2_tool_registry_and_definitions_in_sync():
    """v2 扩展后 TOOL_REGISTRY 与 TOOL_DEFINITIONS 应保持完全一致。"""
    registry_names = set(TOOL_REGISTRY.keys())
    definition_names = {t["name"] for t in TOOL_DEFINITIONS}
    assert registry_names == definition_names


# ============================================================
# v2 工具 build_fallback_summary 中文摘要测试
# ============================================================

def test_fallback_summary_get_product_summary():
    """get_product_summary 摘要应展示商品总数/在售/下架/曝光/浏览/想要。"""
    summary = build_fallback_summary(
        user_message="我有多少商品",
        tool_name="get_product_summary",
        tool_result={
            "success": True,
            "data": {
                "total": 50, "onShelf": 40, "offShelf": 5, "soldOut": 5,
                "totalExposure": 1000, "totalView": 800, "totalWant": 100,
            },
        },
    )
    assert "50 个" in summary
    assert "在售 40" in summary
    assert "下架 5" in summary
    assert "已售 5" in summary
    assert "1000" in summary
    assert "{" not in summary


def test_fallback_summary_delete_product():
    """delete_product 摘要应展示商品名+提醒同步下架。"""
    summary = build_fallback_summary(
        user_message="删除商品",
        tool_name="delete_product",
        tool_result={
            "success": True,
            "data": {"goodsId": 1, "title": "二手手机", "message": "..."},
        },
    )
    assert "二手手机" in summary
    assert "本地记录已删除" in summary or "需要在前端同步下架" in summary
    assert "{" not in summary


def test_fallback_summary_toggle_product_status():
    """toggle_product_status 摘要应展示商品名+动作+同步提示。"""
    summary = build_fallback_summary(
        user_message="下架商品",
        tool_name="toggle_product_status",
        tool_result={
            "success": True,
            "data": {"goodsId": 1, "title": "二手手机", "status": 0, "message": "..."},
        },
    )
    assert "二手手机" in summary
    assert "下架" in summary
    assert "{" not in summary


def test_fallback_summary_search_goods_online_with_data():
    """search_goods_online 摘要应展示商品列表（标题/价格/卖家/地区）。"""
    summary = build_fallback_summary(
        user_message="搜iPhone",
        tool_name="search_goods_online",
        tool_result={
            "success": True,
            "data": {
                "keyword": "iPhone",
                "searchMode": "fast",
                "total": 2,
                "items": [
                    {"title": "iPhone 13", "price": "3999", "seller": "张三", "area": "北京"},
                    {"title": "iPhone 14", "price": "4999", "seller": "李四", "area": "上海"},
                ],
            },
        },
    )
    assert "iPhone" in summary
    assert "iPhone 13" in summary
    assert "3999" in summary
    assert "张三" in summary
    assert "{" not in summary


def test_fallback_summary_search_goods_online_empty():
    """search_goods_online 空结果应友好提示。"""
    summary = build_fallback_summary(
        user_message="搜iPhone",
        tool_name="search_goods_online",
        tool_result={
            "success": True,
            "data": {"keyword": "iPhone", "searchMode": "fast", "total": 0, "items": []},
        },
    )
    assert "没有找到" in summary or "0" in summary
    assert "{" not in summary


def test_fallback_summary_list_recent_conversations_with_unread():
    """list_recent_conversations 摘要应展示未读数与会话列表。"""
    summary = build_fallback_summary(
        user_message="在线消息",
        tool_name="list_recent_conversations",
        tool_result={
            "success": True,
            "data": {
                "conversations": [
                    {"buyerName": "张三", "goodsTitle": "二手手机", "unreadCount": 3,
                     "lastMessageContent": "老板，还在吗"},
                ],
                "total": 1, "totalUnread": 3,
            },
        },
    )
    assert "张三" in summary
    assert "3 条未读" in summary or "未读 3" in summary
    assert "{" not in summary


def test_fallback_summary_reply_buyer_message():
    """reply_buyer_message 摘要应展示发送成功+暂停自动回复提示。"""
    summary = build_fallback_summary(
        user_message="回复买家",
        tool_name="reply_buyer_message",
        tool_result={
            "success": True,
            "data": {
                "accountId": 1, "conversationId": 2, "buyerId": "123",
                "content": "好的，已发货", "message": "...",
            },
        },
    )
    assert "已发送给买家" in summary or "消息已发送" in summary
    assert "暂停" in summary
    assert "好的，已发货" in summary
    assert "{" not in summary


def test_fallback_summary_get_fish_shop_data():
    """get_fish_shop_data 摘要应展示关键指标。"""
    summary = build_fallback_summary(
        user_message="鱼小铺数据",
        tool_name="get_fish_shop_data",
        tool_result={
            "success": True,
            "data": {
                "mode": "all", "dateType": "recent7d",
                "realDateRange": ["20260720", "20260726"],
                "metrics": {
                    "payAmt": {"label": "成交金额", "current": "5000", "ratio": "+10%"},
                    "payOrdCnt": {"label": "支付订单数", "current": "50"},
                },
                "accounts": {"success": 3, "failed": 0},
            },
        },
    )
    assert "鱼小铺" in summary
    assert "成交金额" in summary
    assert "5000" in summary
    assert "支付订单数" in summary
    assert "{" not in summary


def test_fallback_summary_get_sales_comparison_increase():
    """get_sales_comparison 摘要应展示今日/昨日对比+增长率。"""
    summary = build_fallback_summary(
        user_message="今天比昨天多卖多少",
        tool_name="get_sales_comparison",
        tool_result={
            "success": True,
            "data": {
                "today": {"orders": 10, "amount": 500.0, "pendingShip": 3},
                "yesterday": {"orders": 8, "amount": 400.0, "pendingShip": 2},
                "amountDiff": 100.0,
                "amountGrowthPct": 25.0,
                "orderDiff": 2,
                "message": "今日成交 500.00 元",
            },
        },
    )
    assert "10 单" in summary
    assert "8 单" in summary
    assert "增加" in summary
    assert "100.00" in summary
    assert "{" not in summary


def test_fallback_summary_get_sales_comparison_decrease():
    """get_sales_comparison 摘要在销售额下降时应显示「减少」。"""
    summary = build_fallback_summary(
        user_message="今天比昨天多卖多少",
        tool_name="get_sales_comparison",
        tool_result={
            "success": True,
            "data": {
                "today": {"orders": 5, "amount": 300.0, "pendingShip": 1},
                "yesterday": {"orders": 8, "amount": 400.0, "pendingShip": 2},
                "amountDiff": -100.0,
                "amountGrowthPct": -25.0,
                "orderDiff": -3,
                "message": "今日成交 300.00 元",
            },
        },
    )
    assert "减少" in summary
    assert "{" not in summary


def test_fallback_summary_update_delivery_statement():
    """update_delivery_statement 摘要应展示启用状态+文案预览。"""
    summary = build_fallback_summary(
        user_message="配置发货声明",
        tool_name="update_delivery_statement",
        tool_result={
            "success": True,
            "data": {
                "enabled": True,
                "content": "亲，付款后请回复「确认发货」，否则不予发货哦",
                "message": "...",
            },
        },
    )
    assert "已启用" in summary
    assert "付款后请回复" in summary
    assert "{" not in summary


def test_fallback_summary_update_workflow():
    """update_workflow 摘要应展示更新字段。"""
    summary = build_fallback_summary(
        user_message="更新工作流",
        tool_name="update_workflow",
        tool_result={
            "success": True,
            "data": {
                "workflowId": 5,
                "updatedFields": ["name", "status"],
                "message": "...",
            },
        },
    )
    assert "#5" in summary
    assert "name" in summary and "status" in summary
    assert "{" not in summary


def test_fallback_summary_update_scheduled_task():
    """update_scheduled_task 摘要应展示更新字段。"""
    summary = build_fallback_summary(
        user_message="更新定时任务",
        tool_name="update_scheduled_task",
        tool_result={
            "success": True,
            "data": {
                "taskId": 3,
                "updatedFields": ["cron_expr"],
                "message": "...",
            },
        },
    )
    assert "#3" in summary
    assert "cron_expr" in summary
    assert "{" not in summary


def test_fallback_summary_update_auto_reply_rule():
    """update_auto_reply_rule 摘要应展示更新字段。"""
    summary = build_fallback_summary(
        user_message="更新自动回复",
        tool_name="update_auto_reply_rule",
        tool_result={
            "success": True,
            "data": {
                "ruleId": 7,
                "updatedFields": ["reply_content"],
                "message": "...",
            },
        },
    )
    assert "#7" in summary
    assert "reply_content" in summary
    assert "{" not in summary


def test_fallback_summary_prepare_product_publish():
    """prepare_product_publish 摘要应展示发布参数+引导提示。"""
    summary = build_fallback_summary(
        user_message="发布商品",
        tool_name="prepare_product_publish",
        tool_result={
            "success": True,
            "data": {
                "accountId": 1, "accountName": "小龙菜菜", "isFishShop": True,
                "title": "二手手机", "price": "999", "imageUrls": ["url1", "url2"],
                "publishUrl": "/publish", "message": "...",
            },
        },
    )
    assert "二手手机" in summary
    assert "999" in summary
    assert "小龙菜菜" in summary
    assert "鱼小铺" in summary
    assert "2 张" in summary
    assert "商品发布" in summary
    assert "{" not in summary


def test_all_v2_tool_fallback_summaries_have_no_tech_details():
    """v2 所有新工具的兜底摘要绝不能出现 JSON/代码块/字段名。"""
    cases = [
        ("get_product_summary", {"success": True, "data": {"total": 1, "onShelf": 1, "offShelf": 0, "soldOut": 0}}),
        ("delete_product", {"success": True, "data": {"goodsId": 1, "title": "x", "message": "y"}}),
        ("toggle_product_status", {"success": True, "data": {"goodsId": 1, "title": "x", "status": 1, "message": "y"}}),
        ("search_goods_online", {"success": True, "data": {"keyword": "x", "items": [], "total": 0}}),
        ("list_recent_conversations", {"success": True, "data": {"conversations": [], "total": 0, "totalUnread": 0}}),
        ("reply_buyer_message", {"success": True, "data": {"content": "hi", "buyerId": "1", "message": "ok"}}),
        ("get_fish_shop_data", {"success": True, "data": {"metrics": {}, "realDateRange": []}}),
        ("get_sales_comparison", {"success": True, "data": {"today": {"orders": 0, "amount": 0.0, "pendingShip": 0}, "yesterday": {"orders": 0, "amount": 0.0, "pendingShip": 0}, "amountDiff": 0.0, "message": "x"}}),
        ("update_delivery_statement", {"success": True, "data": {"enabled": True, "content": "x", "message": "y"}}),
        ("update_workflow", {"success": True, "data": {"workflowId": 1, "updatedFields": [], "message": "x"}}),
        ("update_scheduled_task", {"success": True, "data": {"taskId": 1, "updatedFields": [], "message": "x"}}),
        ("update_auto_reply_rule", {"success": True, "data": {"ruleId": 1, "updatedFields": [], "message": "x"}}),
        ("prepare_product_publish", {"success": True, "data": {"title": "x", "price": "1", "imageUrls": ["u"], "isFishShop": True, "accountName": "y", "message": "z"}}),
    ]
    for tool_name, result in cases:
        summary = build_fallback_summary(
            user_message="test", tool_name=tool_name, tool_result=result,
        )
        # 绝不能出现 ``` 代码块、JSON 大括号、字段名等技术细节
        assert "```" not in summary, f"工具 {tool_name} 兜底摘要出现代码块：{summary}"
        assert "{" not in summary, f"工具 {tool_name} 兜底摘要出现 JSON 大括号：{summary}"
        assert "success" not in summary, f"工具 {tool_name} 兜底摘要出现 success 字段名：{summary}"
        assert "data" not in summary, f"工具 {tool_name} 兜底摘要出现 data 字段名：{summary}"


def test_build_system_prompt_contains_v2_capabilities():
    """系统提示词应包含 v2 新增能力的描述。"""
    src_path = ROOT / "app" / "services" / "ai_cs_runtime.py"
    src = src_path.read_text(encoding="utf-8")
    # v2 新增能力关键词
    assert "get_product_summary" in src
    assert "search_goods_online" in src
    assert "list_recent_conversations" in src
    assert "reply_buyer_message" in src
    assert "get_fish_shop_data" in src
    assert "get_sales_comparison" in src
    assert "update_delivery_statement" in src
    assert "prepare_product_publish" in src
    # 能力描述
    assert "鱼小铺数据罗盘" in src
    assert "今日与昨日销售对比" in src
    assert "发货声明" in src
    assert "商品发布" in src


def test_v2_total_tool_count_at_least_38():
    """v2 扩展后工具总数应至少为 38（25 原有 + 13 新增）。"""
    assert len(TOOL_REGISTRY) >= 38, f"工具总数 {len(TOOL_REGISTRY)} < 38"
    assert len(QUERY_TOOLS) >= 19, f"查询类工具数 {len(QUERY_TOOLS)} < 19"
