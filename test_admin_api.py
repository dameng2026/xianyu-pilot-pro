#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后台 API 全面联动测试 - 使用正确路径"""
import json
import urllib.request
import urllib.error
import ssl

BASE = "http://localhost:18080"
TOKEN = None
results = []

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def req(method, path, body=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body:
        data = json.dumps(body).encode("utf-8")
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(r, timeout=10, context=ctx)
        content = resp.read().decode("utf-8")
        return json.loads(content), resp.status
    except urllib.error.HTTPError as e:
        try:
            content = e.read().decode("utf-8")
            return json.loads(content), e.code
        except:
            return {"code": -1, "msg": str(e), "data": None}, e.code
    except Exception as e:
        return {"code": -1, "msg": str(e)[:60], "data": None}, -1


def test(module, method, path, desc, body=None, token=None, expect_data=True):
    j, http = req(method, path, body, token)
    code = j.get("code", -1)
    msg = j.get("msg", "")
    data = j.get("data")
    cnt = 0
    if isinstance(data, list):
        cnt = len(data)
    elif isinstance(data, dict):
        if "total" in data:
            cnt = data.get("total", 0)
        elif "totalCount" in data:
            cnt = data.get("totalCount", 0)
        elif "records" in data:
            cnt = data.get("total", 0)
        elif "list" in data:
            cnt = len(data.get("list", []))
        else:
            cnt = 1 if data else 0
    elif data is not None:
        cnt = 1
    status = "OK" if code == 200 else "FAIL"
    results.append((module, method, path, desc, status, code, cnt, msg[:40]))
    return j


# ======== 1. 登录 ========
print("=" * 90)
print("1. 登录获取 Token")
print("=" * 90)
j, _ = req("POST", "/admin-api/auth/login", {"userName": "admin", "password": "123456"})
if j.get("code") == 200 and j.get("data", {}).get("token"):
    TOKEN = j["data"]["token"]
    print("[OK] 登录成功\n")
else:
    print("[FAIL] 登录失败:", j.get("msg"))
    exit(1)

tests = [
    # ======== Auth / User Info ========
    ("auth", "GET", "/admin-api/health", "健康检查"),
    ("auth", "GET", "/admin-api/user/info", "当前用户信息"),

    # ======== AdminModule Controller (通用模块CRUD) ========
    ("admin", "GET", "/admin-api/admin/menus", "后台菜单列表"),
    ("admin", "GET", "/admin-api/admin/users", "后台用户列表"),
    ("admin", "GET", "/admin-api/admin/dashboard/summary", "管理员仪表盘摘要"),
    ("admin", "GET", "/admin-api/admin/dashboard/trend", "管理员趋势数据"),
    ("admin", "GET", "/admin-api/admin/dashboard/recent-events", "最近事件"),

    # ======== 模块 Meta/Stats/Page (通用模块框架) ========
    ("module", "GET", "/admin-api/admin/modules/dashboard/meta", "dashboard 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/dashboard/page?current=1&size=10", "dashboard 模块分页"),
    ("module", "GET", "/admin-api/admin/modules/xianyu-accounts/meta", "xianyu-accounts 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/xianyu-accounts/page?current=1&size=10", "xianyu-accounts 分页"),
    ("module", "GET", "/admin-api/admin/modules/goods/meta", "goods 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/goods/page?current=1&size=10", "goods 分页"),
    ("module", "GET", "/admin-api/admin/modules/orders/meta", "orders 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/orders/page?current=1&size=10", "orders 分页"),
    ("module", "GET", "/admin-api/admin/modules/messages/meta", "messages 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/messages/page?current=1&size=10", "messages 分页"),
    ("module", "GET", "/admin-api/admin/modules/delivery/meta", "delivery 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/delivery/page?current=1&size=10", "delivery 分页"),
    ("module", "GET", "/admin-api/admin/modules/auto-reply/meta", "auto-reply 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/auto-reply/page?current=1&size=10", "auto-reply 分页"),
    ("module", "GET", "/admin-api/admin/modules/kami/meta", "kami 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/kami/page?current=1&size=10", "kami 分页"),
    ("module", "GET", "/admin-api/admin/modules/plans/meta", "plans 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/plans/page?current=1&size=10", "plans 分页"),
    ("module", "GET", "/admin-api/admin/modules/licenses/meta", "licenses 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/licenses/page?current=1&size=10", "licenses 分页"),
    ("module", "GET", "/admin-api/admin/modules/notify-channels/meta", "notify-channels 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/notify-channels/page?current=1&size=10", "notify-channels 分页"),
    ("module", "GET", "/admin-api/admin/modules/risk-events/meta", "risk-events 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/risk-events/page?current=1&size=10", "risk-events 分页"),
    ("module", "GET", "/admin-api/admin/modules/alerts/meta", "alerts 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/alerts/page?current=1&size=10", "alerts 分页"),
    ("module", "GET", "/admin-api/admin/modules/hot-goods/meta", "hot-goods 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/hot-goods/page?current=1&size=10", "hot-goods 分页"),
    ("module", "GET", "/admin-api/admin/modules/rag/meta", "rag 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/rag/page?current=1&size=10", "rag 分页"),
    ("module", "GET", "/admin-api/admin/modules/sensitive-words/meta", "sensitive-words 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/sensitive-words/page?current=1&size=10", "sensitive-words 分页"),
    ("module", "GET", "/admin-api/admin/modules/runtime/meta", "runtime 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/runtime/page?current=1&size=10", "runtime 分页"),
    ("module", "GET", "/admin-api/admin/modules/backups/meta", "backups 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/backups/page?current=1&size=10", "backups 分页"),
    ("module", "GET", "/admin-api/admin/modules/files/meta", "files 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/files/page?current=1&size=10", "files 分页"),
    ("module", "GET", "/admin-api/admin/modules/versions/meta", "versions 模块元数据"),
    ("module", "GET", "/admin-api/admin/modules/versions/page?current=1&size=10", "versions 分页"),

    # ======== 系统配置 ========
    ("sysconfig", "GET", "/admin-api/system/config", "系统配置"),
    ("sysconfig", "GET", "/admin-api/system/sms-config", "短信配置"),
    ("sysconfig", "GET", "/admin-api/system/email-config", "邮件配置"),
    ("sysconfig", "GET", "/admin-api/system/user/page?current=1&size=10", "系统用户分页"),

    # ======== 后台监控 ========
    ("monitor", "GET", "/admin-api/monitor/ai", "AI 监控"),
    ("monitor", "GET", "/admin-api/monitor/ai/token-stats", "AI Token 统计"),
    ("monitor", "GET", "/admin-api/monitor/ai/cost-stats", "AI 成本统计"),
    ("monitor", "GET", "/admin-api/monitor/ai/user-stats", "AI 用户统计"),
    ("monitor", "GET", "/admin-api/monitor/ai/usage", "AI 用量"),
    ("monitor", "GET", "/admin-api/monitor/auto-reply", "自动回复监控"),
    ("monitor", "GET", "/admin-api/monitor/workflow", "工作流监控"),

    # ======== AI 计费 ========
    ("aibilling", "GET", "/admin-api/ai-billing/summary", "AI 计费摘要"),
    ("aibilling", "GET", "/admin-api/ai-billing/usage/page?current=1&size=10", "AI 用量分页"),
    ("aibilling", "GET", "/admin-api/ai-billing/ledger/page?current=1&size=10", "AI 账本分页"),
    ("aibilling", "GET", "/admin-api/ai-billing/model-prices/page?current=1&size=10", "模型定价分页"),

    # ======== 套餐管理 ========
    ("billing", "GET", "/admin-api/billing/plans/page?current=1&size=10", "套餐分页"),
    ("billing", "GET", "/admin-api/billing/plans", "套餐列表(前端)"),

    # ======== 支付 ========
    ("payment", "GET", "/admin-api/payment/configs", "支付配置"),
    ("payment", "GET", "/admin-api/payment/orders/page?current=1&size=10", "支付订单分页"),
    ("payment", "GET", "/admin-api/payment/token-plans/page?current=1&size=10", "Token套餐分页"),

    # ======== 操作日志 ========
    ("ops", "GET", "/admin-api/operation-logs?current=1&size=10", "操作日志分页"),
    ("ops", "GET", "/admin-api/client-errors/page?current=1&size=10", "客户端错误日志"),
    ("ops", "GET", "/admin-api/notifications/delivery-logs?current=1&size=10", "通知发送记录"),

    # ======== 系统运维 ========
    ("ops", "GET", "/admin-api/ops/liveness", "存活检查"),
    ("ops", "GET", "/admin-api/ops/readiness", "就绪检查"),
    ("ops", "GET", "/admin-api/ops/prometheus", "Prometheus 指标"),

    # ======== AI 供应商 ========
    ("ai", "GET", "/admin-api/ai-provider/status", "AI 供应商状态"),

    # ======== 热销商品统计 ========
    ("hotgoods", "GET", "/admin-api/api/hot-goods/dates", "热销商品日期列表"),
    ("hotgoods", "POST", "/admin-api/api/hot-goods/refresh", "刷新热销统计", {"minSales": 5}),
]

# ======== 2. 后台 API 批量测试 ========
print("=" * 90)
print("2. 后台 API 批量测试")
print("=" * 90)
print(f"{'模块':<12} {'路径':<48} {'状态':<6} {'Code':<5} {'数据量':<6} 消息")
print("-" * 110)

for mod, m, p, *rest in tests:
    body = rest[0] if rest else None
    test(mod, m, p, "", body=body, token=TOKEN)

for r in results:
    print(f"{r[0]:<12} {r[2][:47]:<48} {r[4]:<6} {r[5]:<5} {r[6]:<6} {r[7]}")

ok = sum(1 for r in results if r[4] == "OK")
fail = sum(1 for r in results if r[4] == "FAIL")
print(f"\n===== 统计 =====")
print(f"OK: {ok}  FAIL: {fail}  Total: {len(results)}")

# ======== 3. 前台 API 联动测试 ========
print(f"\n{'=' * 90}")
print("3. 前台 User-web API 联动测试")
print("=" * 90)

j, _ = req("POST", "/api/login/login", {"userName": "user", "password": "123456"})
if j.get("code") == 200 and j.get("data") is not None:
    user_token = j["data"]
    print("[OK] 前台用户登录成功\n")
    user_tests = [
        ("GET", "/api/dashboard/summary", "前台仪表盘摘要"),
        ("GET", "/api/dashboard/sales-trend", "销售趋势"),
        ("GET", "/api/dashboard/order-message-trend", "订单消息趋势"),
        ("GET", "/api/dashboard/category-sales", "分类销售"),
        ("GET", "/api/dashboard/account-health", "账号健康"),
        ("GET", "/api/dashboard/recent-logs", "最近日志"),
        ("GET", "/api/xianyu/accounts?current=1&size=10", "闲鱼账号列表"),
        ("GET", "/api/xianyu/accounts/summary", "闲鱼账号摘要"),
        ("GET", "/api/goods?current=1&size=10", "商品列表"),
        ("GET", "/api/orders?current=1&size=10", "订单列表"),
        ("GET", "/api/auto-reply/rules", "自动回复规则"),
        ("GET", "/api/auto-reply/rules/logs", "自动回复日志"),
        ("GET", "/api/conversations?current=1&size=10", "消息会话列表"),
        ("GET", "/api/auto-delivery/rules", "自动发货规则"),
        ("GET", "/api/auto-delivery/global-config", "自动发货全局配置"),
        ("GET", "/api/auto-delivery/stats", "自动发货统计"),
        ("GET", "/api/scheduled-tasks?current=1&size=10", "定时任务列表"),
        ("GET", "/api/cards", "卡密管理"),
        ("GET", "/api/operation-logs?current=1&size=10", "前台操作日志"),
        ("GET", "/api/notification-settings", "通知设置"),
        ("GET", "/api/profile/overview", "用户概览"),
        ("GET", "/api/navigation/overview", "导航概览"),
        ("GET", "/api/navigation/notifications", "导航通知"),
        ("GET", "/api/navigation/system-status", "系统状态"),
        ("GET", "/api/health", "前台健康检查"),
    ]
    print(f"{'路径':<48} {'状态':<6} {'Code':<5} 消息")
    print("-" * 80)
    for m, p, d in user_tests:
        j, _ = req(m, p, token=user_token)
        code = j.get("code", -1)
        msg = j.get("msg", "")[:35]
        st = "OK" if code == 200 else "FAIL"
        print(f"{p[:47]:<48} {st:<6} {code:<5} {msg}")
else:
    print(f"[SKIP] 前台用户登录失败: {j.get('msg', j.get('message', 'unknown'))}")

# ======== 4. 冗余功能与问题分析 ========
print(f"\n{'=' * 90}")
print("4. 综合分析")
print("=" * 90)

empty_modules = [(r[0], r[2], r[3]) for r in results if r[4] == "OK" and r[6] == 0]
fail_modules = [(r[0], r[2], r[3], r[7]) for r in results if r[4] == "FAIL"]

if empty_modules:
    print(f"\n[A] 以下 API 返回空数据 ({len(empty_modules)} 个)：")
    for r in empty_modules:
        print(f"  - [{r[0]}] {r[1]}")

if fail_modules:
    print(f"\n[B] 以下 API 返回错误/404 ({len(fail_modules)} 个)：")
    for r in fail_modules:
        print(f"  - [{r[0]}] {r[1]} => {r[3]}")
