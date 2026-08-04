#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloakBrowser 滑块求解器（方案 K 7.11 实施产物）

CloakBrowser 是 C++ 源码级反指纹 Chromium（71 个源码 patch：canvas/WebGL/audio/GPU/
WebRTC/自动化信号/CDP 输入行为等），与 patchright（JS 注入式反检测）本质不同。
本脚本复用 sliderSolve.py 的滑块检测/拖动函数，仅替换浏览器启动为 CloakBrowser，
用于验证"源码级反指纹能否通过 Baxia FireyeJS 检测、让 NoCaptcha 生成 token"。

启用方式（server.ts 的 Python fallback 调用）：
    python cloakbrowser_solve.py --cookie <cookie_str> [--headless] [--timeout 170]

对比基准（patchright 失败根因，见 x5sec-research-knowledge.md 6.9/6.10 节）：
- patchright 下 plugins=0（机器人特征）、WebGL 软件渲染、window.chrome=undefined
- CloakBrowser 下 plugins=5、真实 GPU 透传（RTX 4060 Ti）、window.chrome=object
- 本脚本若滑块通过 → 证明源码级反指纹优于 JS 注入，可纳入生产

注意：
- CloakBrowser 免费版 v146 无需 license key（本项目使用）
- 生产 Linux 容器需安装 cloakbrowser + 下载二进制（首次运行自动下载 ~200MB）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from typing import Any, Optional

# 复用 sliderSolve.py 的滑块检测/拖动函数（已确认有 __main__ 保护，可安全 import）
sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])
from sliderSolve import (  # noqa: E402
    get_slider_info,
    human_like_drag,
    check_solved,
    detect_captcha_container,
    strip_risk_cookies,
    output_result,
    log,
    _is_punish_url,
)

CAPTURE_X5SEC_JS = """
() => {
  const out = {x5sec: '', x5secdata: '', cookies: []};
  try {
    const m = document.cookie.match(/x5sec=([^;]+)/);
    if (m) out.x5sec = m[1];
  } catch (e) {}
  try {
    const m = document.cookie.match(/x5secdata=([^;]+)/);
    if (m) out.x5secdata = m[1];
  } catch (e) {}
  out.cookies = document.cookie.split(';').map(c => c.trim().split('=')[0]).filter(n => /x5sec|nc_|umt/i.test(n));
  return out;
}
"""


async def solve_with_cloakbrowser(
    cookie_str: str,
    headless: bool = False,
    target_url: str = "https://www.goofish.com/im",
    max_attempts: int = 3,
    proxy: Optional[dict] = None,
) -> dict:
    """用 CloakBrowser 求解滑块，复用 sliderSolve 的检测/拖动逻辑。"""
    start = time.time()
    result: dict[str, Any] = {
        "ok": False,
        "solved": False,
        "captchaDetected": False,
        "attempts": 0,
        "durationMs": 0,
        "browserBackend": "cloakbrowser",
    }

    try:
        from cloakbrowser import launch_persistent_context_async
    except ImportError:
        result["error"] = "cloakbrowser 未安装（pip install cloakbrowser）"
        result["durationMs"] = int((time.time() - start) * 1000)
        return result

    # 临时 profile 目录
    import tempfile
    user_data_dir = tempfile.mkdtemp(prefix="cloak-solve-")
    ctx = None
    try:
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": user_data_dir,
            "headless": headless,
            "viewport": {"width": 1280, "height": 800},
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "humanize": True,  # 拟人鼠标/键盘/滚动
        }
        if proxy and proxy.get("server"):
            launch_kwargs["proxy"] = str(proxy["server"])
        log("[CloakBrowser] 启动浏览器（源码级反指纹 + humanize）...")
        ctx = await launch_persistent_context_async(**launch_kwargs)

        # 注入 cookie（清除 risk cookies）
        clean_cookie = strip_risk_cookies(cookie_str)
        cookies = []
        for part in clean_cookie.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.append({"name": name.strip(), "value": value.strip(),
                            "domain": ".goofish.com", "path": "/"})
        if cookies:
            await ctx.add_cookies(cookies)
            log(f"[CloakBrowser] 注入 {len(cookies)} 个 cookie（已清除 risk cookies）")

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # 捕获 Set-Cookie 中的 x5sec
        captured_x5sec = {"value": ""}

        async def on_response(resp):
            try:
                sc = resp.headers.get("set-cookie", "")
                if sc:
                    m = re.search(r"(?<![a-z])x5sec=([^;]+)", sc)
                    if m and m.group(1) and not captured_x5sec["value"]:
                        captured_x5sec["value"] = m.group(1)
                        log(f"[CloakBrowser] ✓ Set-Cookie 下发 x5sec（来源 {resp.url[:60]}）")
            except Exception:
                pass

        page.on("response", on_response)

        log(f"[CloakBrowser] 导航到 {target_url}")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log(f"[CloakBrowser] 导航异常（继续）: {e}")
        await asyncio.sleep(3.0)

        # 检查页面是否渲染（CloakBrowser 关键验证点：patchright 下 body 为空）
        page_state = await page.evaluate(
            """() => ({
                bodyLen: document.body ? document.body.innerText.length : 0,
                hasBaxiaCommon: typeof window.baxiaCommon,
                hasBaxia: typeof window.__baxia__,
                hasAwsc: typeof window.AWSC,
                hasNcWrapper: !!document.querySelector('.nc_wrapper'),
            })"""
        )
        log(f"[CloakBrowser] 页面状态: {json.dumps(page_state)}")
        if page_state.get("bodyLen", 0) == 0:
            log("[CloakBrowser] ⚠ 页面 body 为空（前端 JS 未渲染）")

        # 多策略拖动
        for attempt in range(1, max_attempts + 1):
            result["attempts"] = attempt
            detected, sel = await detect_captcha_container(page)
            result["captchaDetected"] = detected
            log(f"[CloakBrowser] attempt {attempt}: captcha容器={detected} ({sel})")

            if not detected:
                # 检查是否已通过（无滑块）
                if await check_solved(page):
                    result["solved"] = True
                    result["ok"] = True
                    break
                # 等待滑块出现
                for _ in range(10):
                    await asyncio.sleep(2)
                    detected, sel = await detect_captcha_container(page)
                    if detected:
                        break
                if not detected:
                    log("[CloakBrowser] 滑块未出现，等待超时")
                    break

            # 检测 punish URL
            if _is_punish_url(page.url):
                log("[CloakBrowser] 检测到 punish URL，仍尝试拖动（脱离 punish 唯一途径）")

            slider = await get_slider_info(page)
            if not slider:
                log("[CloakBrowser] 未找到滑块元素")
                await asyncio.sleep(2)
                continue

            # 拟人拖动（human_like_drag 内部已处理多种轨迹）
            start_x = float(slider.get("x", 0))
            start_y = float(slider.get("y", 0))
            distance = float(slider.get("distance", 260))
            log(f"[CloakBrowser] 拖动滑块 x={start_x:.0f} y={start_y:.0f} dist={distance:.0f}")
            try:
                await human_like_drag(page, start_x, start_y, distance, attempt)
            except Exception as e:
                log(f"[CloakBrowser] 拖动异常: {e}")

            await asyncio.sleep(2.5)
            if await check_solved(page):
                result["solved"] = True
                result["ok"] = True
                log("[CloakBrowser] ✓✓ 滑块通过！")
                break
            else:
                log(f"[CloakBrowser] attempt {attempt} 未通过")

            # 失败后重置：清 storage + 回首页
            try:
                await page.evaluate("localStorage.clear(); sessionStorage.clear();")
                await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
            except Exception:
                pass

        # 提取 x5sec
        try:
            x5sec_state = await page.evaluate(CAPTURE_X5SEC_JS)
            if captured_x5sec["value"]:
                result["x5sec"] = captured_x5sec["value"]
                result["x5secSource"] = "set_cookie"
            elif x5sec_state.get("x5sec"):
                result["x5sec"] = x5sec_state["x5sec"]
                result["x5secSource"] = "browser_cookie"
            if x5sec_state.get("x5secdata"):
                result["x5secdata"] = x5sec_state["x5secdata"]
        except Exception as e:
            log(f"[CloakBrowser] x5sec 提取异常: {e}")

        # 收集 cookies
        try:
            all_cookies = await ctx.cookies()
            result["cookies"] = "; ".join(
                f"{c['name']}={c['value']}" for c in all_cookies
                if c.get("domain") and ("goofish" in c["domain"] or "aliyun" in c["domain"] or "aliapp" in c["domain"])
            )
        except Exception:
            pass

        result["durationMs"] = int((time.time() - start) * 1000)
        result["ok"] = result["solved"]
        return result
    except Exception as e:
        result["error"] = str(e)
        result["durationMs"] = int((time.time() - start) * 1000)
        return result
    finally:
        try:
            if ctx:
                await ctx.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="CloakBrowser 滑块求解器")
    parser.add_argument("--cookie", default="", help="cookie 字符串")
    parser.add_argument("--cookie-file", default="", help="cookie 文件路径")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--target-url", default="https://www.goofish.com/im")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--proxy-server", default="", help="HTTP 代理服务器，如 http://ip:port")
    args = parser.parse_args()

    cookie = args.cookie
    if args.cookie_file:
        with open(args.cookie_file, "r", encoding="utf-8") as f:
            cookie = f.read().strip()

    if not cookie:
        print(json.dumps({"ok": False, "error": "cookie 为空"}))
        sys.exit(1)

    proxy = None
    if args.proxy_server:
        proxy = {"server": args.proxy_server}

    result = asyncio.run(solve_with_cloakbrowser(
        cookie_str=cookie,
        headless=args.headless,
        target_url=args.target_url,
        max_attempts=args.max_attempts,
        proxy=proxy,
    ))
    output_result(result)


if __name__ == "__main__":
    main()
