"""为使用手册页面截取 26 张功能页面截图。

视口 2560x1440（27 寸 QHD），full_page 截图。
用法：python scripts/capture_manual_shots.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

USER_WEB = "http://localhost:5174"
CORE_API = "http://127.0.0.1:18080"
OUT_DIR = Path(__file__).resolve().parent.parent / "apps" / "user-web" / "public" / "xya" / "manual"

# 截图清单：文件名 -> 路由 key
SHOTS = {
    "dashboard.png": "dashboard",
    "data.png": "data",
    "accounts.png": "accounts",
    "connections.png": "connections",
    "products.png": "products",
    "orders.png": "orders",
    "product-publish.png": "product-publish",
    "opportunities.png": "opportunities",
    "messages.png": "messages",
    "workflow.png": "workflow",
    "workflow-tasks.png": "workflow-tasks",
    "card-warehouse.png": "card-warehouse",
    "auto-delivery.png": "auto-delivery",
    "delivery-source-library.png": "delivery-source-library",
    "delivery-statement.png": "delivery-statement",
    "delivery-templates.png": "delivery-templates",
    "delivery-records.png": "delivery-records",
    "scheduled-tasks.png": "scheduled-tasks",
    "auto-reply.png": "auto-reply",
    "logs.png": "logs",
    "slider-solve-records.png": "slider-solve-records",
    "feedback.png": "feedback",
    "notify-settings.png": "settings-notify",
    "ai-cs-settings.png": "settings-ai-cs",
    "vip.png": "vip",
    "profile.png": "profile",
}


def fetch_token():
    """调用 core-api 登录获取 token。"""
    payload = json.dumps({"username": "demo", "password": "123456"}).encode("utf-8")
    req = urllib.request.Request(
        f"{CORE_API}/api/login/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    token = body.get("data", {}).get("token", "")
    username = body.get("data", {}).get("username", "demo")
    if not token:
        raise RuntimeError("登录失败：未获取到 token")
    return token, username


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[info] 输出目录: {OUT_DIR}")

    token, username = fetch_token()
    print(f"[info] 登录成功: {username}, token 长度={len(token)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 2560, "height": 1440},
            device_scale_factor=1,
            locale="zh-CN",
        )
        page = context.new_page()

        # 先访问站点以初始化 localStorage
        page.goto(f"{USER_WEB}/#/login", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        # 注入 token 到 localStorage
        page.evaluate(
            """([token, username]) => {
                localStorage.setItem('xianyu_auth_token', token);
                localStorage.setItem('xianyu_username', username);
            }""",
            [token, username],
        )
        # 刷新以应用认证态
        page.goto(f"{USER_WEB}/#/dashboard", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        # 等待应用初始化完成
        try:
            page.wait_for_selector("body", timeout=5000)
        except Exception:
            pass
        time.sleep(2)
        current_hash = page.evaluate("location.hash")
        print(f"[info] 当前 hash: {current_hash}")
        if "login" in current_hash:
            print("[warn] 仍在登录页，认证注入可能失败")
            # 截一张登录页作为诊断
            page.screenshot(path=str(OUT_DIR / "_login_debug.png"), full_page=False)
            # 继续尝试

        total = len(SHOTS)
        success = 0
        failed = []
        for idx, (filename, route_key) in enumerate(SHOTS.items(), 1):
            out_path = OUT_DIR / filename
            print(f"[{idx}/{total}] 截图 {filename}  (route={route_key})", flush=True)
            try:
                page.goto(f"{USER_WEB}/#/{route_key}", wait_until="domcontentloaded")
                # 等待网络空闲
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                # 额外等待动画/渲染
                time.sleep(1.5)
                # 关闭可能存在的模态框/抽屉（按 Esc）
                try:
                    page.keyboard.press("Escape")
                    time.sleep(0.2)
                except Exception:
                    pass
                page.screenshot(path=str(out_path), full_page=True)
                size = out_path.stat().st_size
                print(f"    -> OK ({size} bytes)")
                success += 1
            except Exception as e:
                print(f"    -> FAIL: {e}")
                failed.append(filename)

        browser.close()

    print()
    print(f"=== 完成: 成功 {success}/{total} ===")
    if failed:
        print(f"失败列表: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
