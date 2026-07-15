#!/usr/bin/env python3
"""快速 API 验证脚本"""
import json, urllib.request, urllib.error, ssl, sys, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
BASE = "http://localhost:18080"


def req(method, path, body=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    d = json.dumps(body).encode() if body else None
    r = urllib.request.Request(BASE + path, d, h, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=10, context=ctx)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except:
            return {"code": -1, "msg": str(e)[:40], "data": None}
    except Exception as e:
        return {"code": -1, "msg": str(e)[:40], "data": None}


# 登录
j = req("POST", "/admin-api/auth/login", {"userName": "admin", "password": "123456"})
token = j.get("data", {}).get("token", "")
if not token:
    print("FAIL: 登录失败", j.get("msg"))
    sys.exit(1)
print("登录成功")

tests = [
    # Core auth/health
    ("auth", "GET", "/admin-api/health", "健康检查"),
    ("auth", "GET", "/admin-api/user/info", "当前用户信息"),
    # Admin dashboard & menus
    ("admin", "GET", "/admin-api/admin/menus", "后台菜单列表"),
    ("admin", "GET", "/admin-api/admin/users", "后台用户列表"),
    ("admin", "GET", "/admin-api/admin/dashboard/summary", "管理员仪表盘摘要"),
    ("admin", "GET", "/admin-api/admin/dashboard/trend", "管理员趋势"),
    ("admin", "GET", "/admin-api/admin/dashboard/recent-events", "最近事件"),
    # System config
    ("sysconfig", "GET", "/admin-api/system/config", "系统配置"),
    ("sysconfig", "GET", "/admin-api/system/sms-config", "短信配置"),
    ("sysconfig", "GET", "/admin-api/system/email-config", "邮件配置"),
    ("sysconfig", "GET", "/admin-api/system/user/page?current=1&size=10", "系统用户分页"),
    # Monitor
    ("monitor", "GET", "/admin-api/monitor/ai", "AI监控"),
    ("monitor", "GET", "/admin-api/monitor/ai/token-stats", "AI Token统计"),
    ("monitor", "GET", "/admin-api/monitor/ai/cost-stats", "AI成本统计"),
    ("monitor", "GET", "/admin-api/monitor/ai/usage", "AI用量"),
    ("monitor", "GET", "/admin-api/monitor/auto-reply", "自动回复监控"),
    ("monitor", "GET", "/admin-api/monitor/workflow", "工作流监控"),
    # AI Billing
    ("aibilling", "GET", "/admin-api/ai-billing/summary", "AI计费摘要"),
    ("aibilling", "GET", "/admin-api/ai-billing/usage/page?current=1&size=10", "AI用量分页"),
    ("aibilling", "GET", "/admin-api/ai-billing/ledger/page?current=1&size=10", "AI账本分页"),
    ("aibilling", "GET", "/admin-api/ai-billing/model-prices/page?current=1&size=10", "模型定价"),
    # Billing/Plans
    ("billing", "GET", "/admin-api/billing/plans/page?current=1&size=10", "套餐分页"),
    ("billing", "GET", "/admin-api/billing/plans", "套餐列表(前端)"),
    # Payment
    ("payment", "GET", "/admin-api/payment/configs", "支付配置"),
    ("payment", "GET", "/admin-api/payment/orders/page?current=1&size=10", "支付订单分页"),
    ("payment", "GET", "/admin-api/payment/token-plans/page?current=1&size=10", "Token套餐"),
    # Ops/Logs
    ("ops", "GET", "/admin-api/operation-logs?current=1&size=10", "操作日志"),
    ("ops", "GET", "/admin-api/client-errors/page?current=1&size=10", "客户端错误日志"),
    ("ops", "GET", "/admin-api/notifications/delivery-logs?current=1&size=10", "通知发送记录"),
    ("ops", "GET", "/admin-api/ops/liveness", "存活检查"),
    ("ops", "GET", "/admin-api/ops/readiness", "就绪检查"),
    ("ops", "GET", "/admin-api/ops/prometheus", "Prometheus指标"),
    # AI Provider
    ("ai", "GET", "/admin-api/ai-provider/status", "AI供应商状态"),
    # Hot Goods
    ("hotgoods", "GET", "/admin-api/api/hot-goods/dates", "热销商品日期"),
    # Admin Xianyu Accounts
    ("admin-xy", "GET", "/admin-api/admin/xianyu/accounts?current=1&size=10", "后台闲鱼账号"),
]

# 内置模块 key 列表
module_keys = [
    "dashboard", "xianyu-accounts", "goods", "orders", "messages",
    "delivery", "auto-reply", "kami", "plans", "licenses",
    "notify-channels", "risk-events", "alerts", "hot-goods",
    "rag", "sensitive-words", "runtime", "backups", "files", "versions",
]

ok, fail, result_lines = 0, 0, []

print(f"{'模块':<12} {'路径':<50} {'状态':<5} {'Code':<5} 数据 消息")
print("-" * 110)

for mod, method, path, desc in tests:
    body = None
    if isinstance(desc, tuple):
        body = desc[1]
        desc = desc[0]
    j = req(method, path, body=body, token=token)
    code = j.get("code", -1)
    msg = j.get("msg", "")[:30]
    data = j.get("data")
    cnt = ""
    if isinstance(data, list):
        cnt = str(len(data))
    elif isinstance(data, dict):
        if "total" in data:
            cnt = f"t={data['total']}"
        elif "records" in data:
            cnt = f"r={len(data['records'])}"
        elif data:
            cnt = "1"
    status = "OK" if code == 200 else "FAIL"
    if code == 200:
        ok += 1
    else:
        fail += 1
    print(f"  [{status}] {mod:<10} {path:<48} {code:<5} {cnt or '':<5} {msg}")

# 模块 Meta + Page
for k in module_keys:
    for suffix in ["meta", "page?current=1&size=10"]:
        path = f"/admin-api/admin/modules/{k}/{suffix}"
        j = req("GET", path, token=token)
        code = j.get("code", -1)
        msg = j.get("msg", "")[:25]
        if code == 200:
            ok += 1
            print(f"  [OK] module     /modules/{k:<24}/{suffix:<22} {code:<5} {msg}")
        else:
            fail += 1
            print(f"  [FAIL] module   /modules/{k:<24}/{suffix:<22} {code:<5} {msg}")

print(f"\n=== 结果统计 ===")
print(f"OK: {ok}  FAIL: {fail}  Total: {ok + fail}")
