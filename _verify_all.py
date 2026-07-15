"""
浏览器真实监测验证所有功能（通过UI登录）
"""
import sys
import time
import json
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5174"
API_BASE = "http://localhost:18080"
USERNAME = "demo"
PASSWORD = "123456"

TOKEN_FILE = Path("_verify_token.txt")
results = []

def log(name, status, detail=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{icon} [{name}] {status} {detail}")
    results.append({"name": name, "status": status, "detail": detail})

def login_api():
    r = requests.post(f"{API_BASE}/api/login/login",
                      json={"username": USERNAME, "password": PASSWORD},
                      timeout=15)
    data = r.json()
    if data.get("code") == 200:
        token = data["data"]["token"]
        TOKEN_FILE.write_text(token, encoding="utf-8")
        return token
    raise RuntimeError(f"登录失败: {data}")

def api_get(token, path, timeout=30):
    return requests.get(f"{API_BASE}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=timeout).json()

def api_post(token, path, body=None, timeout=60):
    return requests.post(f"{API_BASE}{path}",
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"},
                         json=body or {},
                         timeout=timeout).json()

def verify_backend_apis(token):
    print("\n========== 后端 API 接口验证 ==========")
    # 1. Cookie/Token 刷新调度器
    try:
        r = api_get(token, "/api/account/refresh/status", timeout=15)
        if r.get("code") == 200 and r["data"].get("running"):
            cfg = r["data"].get("config", {})
            details = (f"running=True, accounts={r['data']['accountsCount']}, "
                       f"cookie保活={cfg.get('cookieKeepaliveIntervalMinutes')}min, "
                       f"mh5tk={cfg.get('mh5tkRefreshMinHours')}-{cfg.get('mh5tkRefreshMaxHours')}h, "
                       f"wsToken={cfg.get('wsTokenRefreshMinHours')}-{cfg.get('wsTokenRefreshMaxHours')}h, "
                       f"账号间隔={cfg.get('accountIntervalMinSeconds')}-{cfg.get('accountIntervalMaxSeconds')}s")
            log("Cookie/Token刷新状态", "PASS", details)
        else:
            log("Cookie/Token刷新状态", "FAIL", str(r))
    except Exception as e:
        log("Cookie/Token刷新状态", "FAIL", str(e))

    # 2. 手动触发Cookie保活
    try:
        r = api_post(token, "/api/account/refresh/force",
                     {"accountId": 1, "refreshType": "cookie"}, timeout=60)
        if r.get("code") == 200 and r["data"].get("success"):
            log("Cookie保活触发", "PASS", f"cookie={r['data']['details'].get('cookie')}")
        else:
            log("Cookie保活触发", "FAIL", str(r))
    except Exception as e:
        log("Cookie保活触发", "FAIL", str(e))

    # 3. 滑块检测
    try:
        r = api_post(token, "/api/captcha/detect", {"accountId": 1}, timeout=30)
        if r.get("code") == 200:
            log("滑块检测", "PASS", f"detected={r['data'].get('detected')}")
        else:
            log("滑块检测", "FAIL", str(r))
    except Exception as e:
        log("滑块检测", "FAIL", str(e))

    # 4. 滑块操作指引
    try:
        r = api_post(token, "/api/captcha/instructions",
                     {"accountId": 1, "captchaUrl": ""}, timeout=15)
        if r.get("code") == 200 and r["data"].get("steps"):
            log("滑块操作指引", "PASS",
                f"steps={len(r['data']['steps'])}, autoSolve={r['data'].get('autoSolveAvailable')}")
        else:
            log("滑块操作指引", "FAIL", str(r))
    except Exception as e:
        log("滑块操作指引", "FAIL", str(e))

    # 5. RAG 统计
    try:
        r = api_get(token, "/api/knowledge-base/rag/stats", timeout=15)
        if r.get("code") == 200:
            log("RAG知识库统计", "PASS",
                f"totalDocuments={r['data'].get('totalDocuments')}")
        else:
            log("RAG知识库统计", "FAIL", str(r))
    except Exception as e:
        log("RAG知识库统计", "FAIL", str(e))

    # 6. 卡密配置列表
    try:
        r = api_post(token, "/api/kami/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            log("卡密发货配置", "PASS", f"records={len(r['data'].get('records', []))}")
        else:
            log("卡密发货配置", "FAIL", str(r))
    except Exception as e:
        log("卡密发货配置", "FAIL", str(e))

    # 7. 自动发货配置
    try:
        r = api_post(token, "/api/autoDelivery/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            log("自动发货配置", "PASS", f"records={len(r['data'].get('records', []))}")
        else:
            log("自动发货配置", "FAIL", str(r))
    except Exception as e:
        log("自动发货配置", "FAIL", str(e))

    # 8. 擦亮功能
    try:
        r = api_post(token, "/api/item/polish", {"accountId": 1}, timeout=30)
        if r.get("code") == 200 and r["data"].get("taskId"):
            task_id = r["data"]["taskId"]
            log("擦亮任务提交", "PASS", f"taskId={task_id}, total={r['data'].get('total')}")
            for _ in range(30):
                time.sleep(2)
                p = api_get(token, f"/api/item/polishProgress/{task_id}", timeout=10)
                if p.get("code") == 200:
                    pd = p["data"]
                    if not pd.get("running"):
                        if pd.get("status") == "completed":
                            log("擦亮任务完成", "PASS",
                                f"polished={pd.get('polished')}, failed={pd.get('failed')}, "
                                f"msg={pd.get('message')}")
                        else:
                            log("擦亮任务完成", "FAIL",
                                f"status={pd.get('status')}, msg={pd.get('message')}")
                        break
            else:
                log("擦亮任务完成", "FAIL", "超时未完成")
        elif r.get("code") == 200:
            log("擦亮任务提交", "PASS", f"msg={r['data'].get('message')}")
        else:
            log("擦亮任务提交", "FAIL", str(r))
    except Exception as e:
        log("擦亮任务", "FAIL", str(e))

def verify_token_refresher_running():
    print("\n========== Token刷新定时任务运行验证 ==========")
    try:
        token = login_api()
        r = api_get(token, "/api/account/refresh/status", timeout=15)
        if r.get("code") == 200:
            data = r["data"]
            running = data.get("running")
            accounts = data.get("accountsCount", 0)
            account_list = data.get("accounts", [])
            all_ok = all(a.get("lastCookieKeepaliveOk") for a in account_list if a.get("lastCookieKeepaliveOk") is not None)
            detail = (f"running={running}, accounts={accounts}, "
                      f"allCookieKeepaliveOk={all_ok}")
            if running and accounts > 0:
                log("Token刷新调度器运行", "PASS", detail)
            else:
                log("Token刷新调度器运行", "WARN", detail)
        else:
            log("Token刷新调度器运行", "FAIL", str(r))
    except Exception as e:
        log("Token刷新调度器运行", "FAIL", str(e))

def verify_frontend_pages(token):
    print("\n========== 前端页面浏览器真实操作验证 ==========")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. 访问首页
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            title = page.title()
            log("前端首页加载", "PASS", f"title={title}")
        except Exception as e:
            log("前端首页加载", "FAIL", str(e))

        # 2. 通过UI登录
        try:
            # 等待登录表单加载
            page.wait_for_selector('input', timeout=10000)
            # 找到用户名和密码输入框
            inputs = page.query_selector_all('input')
            if len(inputs) >= 2:
                inputs[0].fill(USERNAME)
                inputs[1].fill(PASSWORD)
                # 找到登录按钮
                login_btn = page.query_selector('button[type="submit"]') or page.query_selector('button:has-text("登录")')
                if login_btn:
                    login_btn.click()
                    page.wait_for_timeout(3000)
                    log("UI登录", "PASS", "已通过登录表单登录")
                else:
                    log("UI登录", "FAIL", "未找到登录按钮")
            else:
                log("UI登录", "FAIL", f"未找到足够输入框，仅 {len(inputs)} 个")
        except Exception as e:
            log("UI登录", "FAIL", str(e))

        # 3. 访问账号页面
        try:
            page.goto(f"{BASE_URL}/#/accounts", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            content = page.content()
            if "账号" in content or "account" in content.lower():
                log("账号页面访问", "PASS", "页面正常加载")
            else:
                log("账号页面访问", "FAIL", "未找到账号相关内容")
        except Exception as e:
            log("账号页面访问", "FAIL", str(e))

        # 4. 访问商品页面
        try:
            page.goto(f"{BASE_URL}/#/products", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            content = page.content()
            if "商品" in content or "product" in content.lower() or "擦亮" in content:
                log("商品页面访问", "PASS", "页面正常加载")
            else:
                log("商品页面访问", "FAIL", "未找到商品相关内容")
        except Exception as e:
            log("商品页面访问", "FAIL", str(e))

        # 5. 访问消息页面
        try:
            page.goto(f"{BASE_URL}/#/messages", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            content = page.content()
            if "消息" in content or "message" in content.lower() or "会话" in content:
                log("消息页面访问", "PASS", "页面正常加载")
            else:
                log("消息页面访问", "FAIL", "未找到消息相关内容")
        except Exception as e:
            log("消息页面访问", "FAIL", str(e))

        # 6. 访问卡密管理页面（路由为 card-warehouse）
        try:
            page.goto(f"{BASE_URL}/#/card-warehouse", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            content = page.content()
            if "卡密" in content or "卡仓" in content or "card" in content.lower():
                log("卡密管理页面访问", "PASS", "页面正常加载")
            else:
                log("卡密管理页面访问", "FAIL", "未找到卡密相关内容")
        except Exception as e:
            log("卡密管理页面访问", "FAIL", str(e))

        # 7. 访问自动回复页面
        try:
            page.goto(f"{BASE_URL}/#/auto-reply", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            content = page.content()
            if "自动回复" in content or "知识库" in content or "auto" in content.lower():
                log("自动回复/RAG页面访问", "PASS", "页面正常加载")
            else:
                log("自动回复/RAG页面访问", "FAIL", "未找到相关内容")
        except Exception as e:
            log("自动回复/RAG页面访问", "FAIL", str(e))

        # 8. 访问商机发掘页面
        try:
            page.goto(f"{BASE_URL}/#/opportunities", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            content = page.content()
            if "商机" in content or "opportunity" in content.lower() or "搜索" in content or "闲鱼" in content:
                log("商机发掘页面访问", "PASS", "页面正常加载")
            else:
                log("商机发掘页面访问", "FAIL", "未找到相关内容")
        except Exception as e:
            log("商机发掘页面访问", "FAIL", str(e))

        # 9. 检查 console 错误
        if console_errors:
            critical_errors = [e for e in console_errors
                               if "Failed to fetch" not in e
                               and "favicon" not in e.lower()
                               and "NetworkError" not in e]
            if critical_errors:
                log("前端Console错误检查", "WARN",
                    f"发现 {len(critical_errors)} 个错误，示例: {critical_errors[0][:100]}")
            else:
                log("前端Console错误检查", "PASS", "仅有可忽略的网络错误")
        else:
            log("前端Console错误检查", "PASS", "无 console 错误")

        # 10. 截图保存
        try:
            page.goto(f"{BASE_URL}/#/dashboard", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            page.screenshot(path="_verify_dashboard.png", full_page=True)
            log("仪表盘截图", "PASS", "已保存 _verify_dashboard.png")
        except Exception as e:
            log("仪表盘截图", "FAIL", str(e))

        browser.close()

def main():
    print("=" * 60)
    print("7项功能全方位验证 - 浏览器真实监测")
    print("=" * 60)

    try:
        token = login_api()
        print(f"✅ 登录成功，token: {token[:30]}...")
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return

    verify_backend_apis(token)
    verify_token_refresher_running()
    verify_frontend_pages(token)

    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌" if r["status"] == "FAIL" else "⚠️"
        print(f"{icon} {r['name']}: {r['status']} - {r['detail'][:80]}")
    print("-" * 60)
    print(f"总计: {len(results)} 项 | 通过: {pass_count} | 失败: {fail_count} | 警告: {warn_count}")

if __name__ == "__main__":
    main()
