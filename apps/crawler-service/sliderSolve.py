#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
闲鱼滑块验证自动求解器（Python · Playwright page.mouse，不控制用户硬件鼠标）

核心策略（基于实测与历史失败截图分析）：
1. 同页连续失败会累积 Baxia 惩罚态；每次失败后必须彻底重置（清 storage + 回首页 + 再进消息页）
2. 使用真实 Chrome + CDP，配合 page.mouse 生成 isTrusted 鼠标事件
3. 拖动：接近轨迹、起点偏移、钟形速度、Y 弧线、过冲回退；奇偶次交替容器内/出容器拖动
4. 每轮 pre/post 截图，便于视觉复盘
5. 成功后导出最新 Cookie（含 _m_h5_tk 等）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from typing import Any, Optional

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright is not installed. Run: pip install playwright", file=sys.stderr)
    sys.exit(2)

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
DEFAULT_TARGET_URL = "https://www.goofish.com/im"
DEFAULT_MAX_RETRIES = 5

BAXIA_CONTAINER_SELECTORS = [
    "#nc_1",
    ".nc_wrapper",
    "#baxia-dialog",
    'iframe[src*="baxia"]',
    ".J_MIDDLEWARE_FRAME",
    'iframe[id*="baxia"]',
    ".slide-verify",
    "#nc_1_n1z",
    ".btn_slide",
]

SLIDER_BUTTON_SELECTORS = [
    "#nc_1_n1z",
    ".btn_slide",
    ".nc_iconfont",
    ".slide-btn",
    "#nc_1_n1t",
    ".nc-lang-cnt",
    '[data-role="slider"]',
]

SLIDER_TRACK_SELECTORS = [
    ".nc_scale",
    ".scale_text",
    ".slide-track",
    "#nc_1__scale",
    ".nc-lang",
]

SUCCESS_SELECTORS = [".nc_ok", ".success", "#nc_1_n1z.success", ".icon-success"]
FAIL_SELECTORS = [".nc_error", ".errloading", ".fail", "#nc_1_refresh1"]


def log(msg: str) -> None:
    print(f"[sliderSolve] {msg}", flush=True)


def output_result(result: dict) -> None:
    """最后一行 JSON 供 TypeScript 解析。"""
    print(json.dumps(result, ensure_ascii=False), flush=True)


def find_chrome_path() -> Optional[str]:
    local = os.environ.get("LOCALAPPDATA") or ""
    candidates = [
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def parse_cookie_string(cookie_str: str, domain: str = ".goofish.com") -> list[dict]:
    """解析 Cookie；设置 30 天过期，便于持久化。"""
    expires_future = int(time.time()) + 30 * 24 * 3600
    cookies: list[dict] = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part:
            continue
        eq = part.find("=")
        if eq <= 0:
            continue
        name = part[:eq].strip()
        value = part[eq + 1 :].strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "expires": expires_future,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            }
        )
    return cookies


def close_proc_gracefully(proc: Optional[subprocess.Popen], timeout: float = 5.0) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        else:
            proc.terminate()
            proc.wait(timeout=timeout)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


async def get_slider_info(page) -> Optional[dict]:
    """遍历所有 frame 找滑块按钮与轨道宽度。"""
    for frame in page.frames:
        for sel in SLIDER_BUTTON_SELECTORS:
            try:
                button = await frame.query_selector(sel)
                if not button:
                    continue
                box = await button.bounding_box()
                if not box or box.get("width", 0) <= 0:
                    continue
                track_width = 300.0
                for tsel in SLIDER_TRACK_SELECTORS:
                    try:
                        track = await frame.query_selector(tsel)
                        if not track:
                            continue
                        track_box = await track.bounding_box()
                        if track_box and track_box.get("width", 0) > 0:
                            track_width = float(track_box["width"] - box["width"])
                            break
                    except Exception:
                        pass
                # 距离过短/过长都不合理，钳制到常见区间
                track_width = max(180.0, min(track_width, 360.0))
                return {
                    "button": button,
                    "frame": frame,
                    "x": float(box["x"] + box["width"] / 2),
                    "y": float(box["y"] + box["height"] / 2),
                    "distance": track_width,
                    "width": float(box["width"]),
                    "height": float(box["height"]),
                }
            except Exception:
                continue
    return None


async def detect_captcha_container(page) -> tuple[bool, Optional[str]]:
    for selector in BAXIA_CONTAINER_SELECTORS:
        try:
            elem = await page.query_selector(selector)
            if elem and await elem.is_visible():
                return True, selector
        except Exception:
            pass
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        for selector in BAXIA_CONTAINER_SELECTORS:
            try:
                elem = await frame.query_selector(selector)
                if elem and await elem.is_visible():
                    return True, selector
            except Exception:
                pass
    return False, None


async def check_solved(page) -> bool:
    for sel in SUCCESS_SELECTORS:
        for frame in page.frames:
            try:
                elem = await frame.query_selector(sel)
                if elem and await elem.is_visible():
                    return True
            except Exception:
                pass
    for sel in FAIL_SELECTORS:
        for frame in page.frames:
            try:
                elem = await frame.query_selector(sel)
                if elem and await elem.is_visible():
                    return False
            except Exception:
                pass
    detected, _ = await detect_captcha_container(page)
    return not detected


async def human_like_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """容器内拖动：接近轨迹 + 起点偏移 + 三阶段速度 + Y 弧线 + 过冲回退。"""
    if attempt == 1:
        steps_base, step_delay_min, step_delay_max = 38, 28, 65
        pause_points = [0.35 + random.random() * 0.2]
    elif attempt == 2:
        steps_base, step_delay_min, step_delay_max = 42, 35, 80
        pause_points = []
    elif attempt == 3:
        steps_base, step_delay_min, step_delay_max = 32, 20, 50
        pause_points = []
    elif attempt == 4:
        steps_base, step_delay_min, step_delay_max = 48, 45, 95
        pause_points = [0.4 + random.random() * 0.2]
    else:
        steps_base = 36 + random.randint(0, 12)
        step_delay_min = 25 + random.randint(0, 20)
        step_delay_max = step_delay_min + 30 + random.randint(0, 30)
        pause_points = []

    steps = steps_base + random.randint(0, 10)
    pause_duration_ms = 220 + random.randint(0, 180)
    log(
        f"拖动策略: attempt={attempt}, steps={steps}, "
        f"delay={step_delay_min}-{step_delay_max}ms, pauses={len(pause_points)}"
    )

    # 起点在按钮中心附近随机偏移（±4px），避免永远点死中心
    actual_start_x = start_x + random.uniform(-4, 4)
    actual_start_y = start_y + random.uniform(-3, 3)

    # 接近轨迹：从按钮附近随机点移入，而非瞬移
    approach_angle = random.uniform(0, 2 * math.pi)
    approach_dist = 40 + random.random() * 80
    approach_x = max(5, min(WINDOW_WIDTH - 5, actual_start_x + math.cos(approach_angle) * approach_dist))
    approach_y = max(5, min(WINDOW_HEIGHT - 5, actual_start_y + math.sin(approach_angle) * approach_dist))
    approach_steps = 8 + random.randint(0, 8)
    await page.mouse.move(approach_x, approach_y)
    await page.wait_for_timeout(80 + random.randint(0, 120))
    for i in range(1, approach_steps + 1):
        t = i / approach_steps
        eased = t * t * (3 - 2 * t)
        mx = approach_x + (actual_start_x - approach_x) * eased
        my = approach_y + (actual_start_y - approach_y) * eased
        await page.mouse.move(mx, my)
        await page.wait_for_timeout(12 + random.random() * 25)

    await page.wait_for_timeout(100 + random.random() * 180)
    await page.mouse.down()
    await page.wait_for_timeout(90 + random.random() * 120)
    # 按下后微漂移
    await page.mouse.move(
        actual_start_x + random.uniform(-2, 2),
        actual_start_y + random.uniform(-2, 2),
    )
    await page.wait_for_timeout(40 + random.random() * 60)

    arc_direction = -1 if random.random() < 0.5 else 1
    arc_amplitude = 3 + random.random() * 6
    last_x = actual_start_x
    last_y = actual_start_y
    pause_idx = 0

    for i in range(1, steps + 1):
        progress = i / steps
        if progress < 0.18:
            speed_weight = 1.0 - 0.65 * (progress / 0.18)
        elif progress < 0.72:
            speed_weight = 0.22 + 0.12 * math.sin(progress * math.pi * 5)
        else:
            speed_weight = 0.35 + 0.65 * ((progress - 0.72) / 0.28)

        # ease-in-out 变体
        eased = (progress ** 2.3) / ((progress ** 2.3) + ((1 - progress) ** 2.3) + 1e-9)
        target_x = actual_start_x + distance * eased

        # 中段偶发回退
        if random.random() < 0.06 and 3 < i < steps - 4:
            target_x = last_x - (2 + random.random() * 4)

        arc_offset = arc_direction * arc_amplitude * math.sin(math.pi * progress)
        y_drift = (random.random() - 0.5) * 5
        target_y = actual_start_y + arc_offset
        current_y = last_y * 0.55 + target_y * 0.45 + y_drift

        await page.mouse.move(target_x, current_y)

        median_delay = step_delay_min + (step_delay_max - step_delay_min) * 0.4
        # Box-Muller 对数正态间隔
        u1 = max(1e-10, random.random())
        u2 = random.random()
        normal = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        log_delay = median_delay * math.exp(0.45 * normal)
        delay = max(step_delay_min, min(step_delay_max * 2.2, log_delay)) * speed_weight
        await page.wait_for_timeout(delay)

        last_x, last_y = target_x, current_y
        if pause_idx < len(pause_points) and progress >= pause_points[pause_idx]:
            log(f"  在 progress={progress:.2f} 处停顿 {pause_duration_ms}ms")
            await page.wait_for_timeout(pause_duration_ms)
            pause_idx += 1

    # 过冲 + 回退 + 微调释放
    await page.wait_for_timeout(40 + random.random() * 80)
    overshoot = 6 + random.random() * 10
    await page.mouse.move(
        actual_start_x + distance + overshoot,
        actual_start_y + random.uniform(-6, 6),
        steps=2,
    )
    await page.wait_for_timeout(60 + random.random() * 90)
    await page.mouse.move(
        actual_start_x + distance + random.uniform(-1.5, 1.5),
        actual_start_y + random.uniform(-3, 3),
        steps=2,
    )
    for _ in range(1 if random.random() < 0.65 else 2):
        await page.wait_for_timeout(45 + random.random() * 70)
        await page.mouse.move(
            actual_start_x + distance + random.uniform(-2, 2),
            actual_start_y + random.uniform(-2, 2),
        )
    await page.wait_for_timeout(60 + random.random() * 90)
    await page.mouse.up()


async def human_like_drag_out_of_container(
    page, start_x: float, start_y: float, distance: float, attempt: int = 1
) -> None:
    """出容器拖动：Y 大幅偏出弹窗（±50~120px），模拟真人不拘束手部路径。"""
    if attempt <= 2:
        steps_base, step_delay_min, step_delay_max = 40, 28, 70
    elif attempt == 3:
        steps_base, step_delay_min, step_delay_max = 34, 22, 55
    else:
        steps_base = 38 + random.randint(0, 12)
        step_delay_min = 25 + random.randint(0, 25)
        step_delay_max = step_delay_min + 30 + random.randint(0, 40)

    steps = steps_base + random.randint(0, 10)
    log(f"  超出容器拖动策略: attempt={attempt}, steps={steps}, delay={step_delay_min}-{step_delay_max}ms")

    actual_start_x = start_x + random.uniform(-3, 3)
    actual_start_y = start_y + random.uniform(-2, 2)

    await page.mouse.move(actual_start_x - 30 - random.random() * 40, actual_start_y + random.uniform(-20, 20))
    await page.wait_for_timeout(80 + random.random() * 120)
    await page.mouse.move(actual_start_x, actual_start_y, steps=6)
    await page.wait_for_timeout(100 + random.random() * 150)
    await page.mouse.down()
    await page.wait_for_timeout(90 + random.random() * 110)

    num_out_points = 2 + random.randint(0, 1)
    out_points = []
    for i in range(num_out_points):
        prog = 0.2 + (0.6 * (i + 1) / (num_out_points + 1)) + random.uniform(-0.05, 0.05)
        direction = -1 if i % 2 == 0 else 1
        magnitude = 55 + random.random() * 70
        out_points.append({"progress": max(0.15, min(0.85, prog)), "y_offset": direction * magnitude})
    log(
        "  出容器拐点: "
        + " | ".join(f"p={p['progress']:.2f},y={p['y_offset']:.0f}px" for p in out_points)
    )

    last_x = actual_start_x
    for i in range(1, steps + 1):
        progress = i / steps
        eased = progress * progress * (3 - 2 * progress)
        target_x = actual_start_x + distance * eased
        if random.random() < 0.05 and 3 < i < steps - 3:
            target_x = last_x - (2 + random.random() * 3)

        base_arc = math.sin(math.pi * progress) * 5
        y_offset = 0.0
        for op in out_points:
            dist = abs(progress - op["progress"])
            if dist < 0.18:
                influence = math.exp(-(dist * dist) / (2 * 0.055 * 0.055))
                y_offset += op["y_offset"] * influence
        current_y = actual_start_y + base_arc + y_offset + random.uniform(-5, 5)
        await page.mouse.move(target_x, current_y)

        bell = math.sin(math.pi * progress)
        delay_weight = 1 - bell * 0.45
        delay = (step_delay_min + random.random() * (step_delay_max - step_delay_min)) * delay_weight
        await page.wait_for_timeout(delay)
        last_x = target_x

    await page.wait_for_timeout(40 + random.random() * 80)
    overshoot = 5 + random.random() * 12
    await page.mouse.move(
        actual_start_x + distance + overshoot,
        actual_start_y + random.uniform(-25, 25),
        steps=2,
    )
    await page.wait_for_timeout(50 + random.random() * 90)
    await page.mouse.move(
        actual_start_x + distance,
        actual_start_y + random.uniform(-18, 18),
        steps=2,
    )
    await page.wait_for_timeout(60 + random.random() * 90)
    await page.mouse.up()


async def wait_for_slider_ready(page, max_wait_ms: int = 10000) -> Optional[dict]:
    start = time.time()
    last_log = 0.0
    while (time.time() - start) * 1000 < max_wait_ms:
        # 登录页
        url = (page.url or "").lower()
        if "login.taobao.com" in url or "login.goofish.com" in url or "/login" in url:
            return {"is_login_page": True}

        if await check_solved(page):
            # 可能用户手动完成，或本就无需验证
            detected, _ = await detect_captcha_container(page)
            if not detected:
                return {"already_solved": True}

        info = await get_slider_info(page)
        if info:
            return info

        now = time.time()
        if now - last_log > 2.0:
            elapsed = int((now - start) * 1000)
            log(f"  等待滑块... ({elapsed}ms/{max_wait_ms}ms)")
            last_log = now
        await asyncio.sleep(0.4)
    return None


async def diagnose_frames(page) -> None:
    log(f"页面 URL: {page.url}")
    for i, frame in enumerate(page.frames):
        try:
            furl = frame.url or ""
            tag = "[PUNISH]" if ("punish" in furl or "_____tmd_____" in furl) else "[OK]"
            log(f"  Frame {i}: {tag} {furl[:180]}")
        except Exception:
            pass


async def close_captcha_dialog(page) -> bool:
    close_selectors = [
        ".nc_close",
        ".nc-icon-close",
        ".baxia-close",
        ".dialog-close",
        ".modal-close",
        ".popup-close",
        ".close-btn",
        ".btn-close",
        ".ant-modal-close",
        ".next-dialog-close",
        'button[aria-label*="close"]',
        'button[aria-label*="关闭"]',
    ]
    search_frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
    for f in search_frames:
        for sel in close_selectors:
            try:
                elem = await f.query_selector(sel)
                if elem and await elem.is_visible():
                    log(f"找到弹窗关闭按钮: {sel}")
                    await elem.click(timeout=2000)
                    await asyncio.sleep(0.8)
                    return True
            except Exception:
                pass
        try:
            closed = await f.evaluate(
                """() => {
                const candidates = [];
                const allElems = document.querySelectorAll('button, [role="button"], a, span, div, i');
                for (const el of Array.from(allElems)) {
                  const text = (el.textContent || '').trim();
                  const aria = el.getAttribute('aria-label') || '';
                  const cls = typeof el.className === 'string' ? el.className : '';
                  if (/^[×✕✗xX]$/.test(text) || /关闭|close/i.test(aria) || /close|关闭/i.test(cls)) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.width < 60 && rect.height > 0 && rect.height < 60) {
                      candidates.push(el);
                    }
                  }
                }
                candidates.sort((a, b) => {
                  const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
                  return (rb.right - ra.right) || (ra.top - rb.top);
                });
                if (candidates.length) { candidates[0].click(); return true; }
                return false;
            }"""
            )
            if closed:
                log("通过文本特征点击了弹窗关闭按钮")
                await asyncio.sleep(0.8)
                return True
        except Exception:
            pass
    log("未找到弹窗关闭按钮")
    return False


async def navigate_fresh(page, target_url: str) -> None:
    """彻底重置：清 storage → 回首页 → 再进目标页（避免同会话惩罚累积）。"""
    try:
        await page.evaluate(
            """() => {
            try { localStorage.clear(); } catch(e) {}
            try { sessionStorage.clear(); } catch(e) {}
        }"""
        )
        log("已清理 localStorage/sessionStorage")
    except Exception as e:
        log(f"清理存储失败(可忽略): {e}")

    home_wait = 1.2 + random.random() * 1.5
    try:
        await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=45000)
        log(f"已回到首页，等待 {home_wait:.1f}s 后重新导航到目标页")
        await asyncio.sleep(home_wait)
    except Exception as e:
        log(f"回首页失败: {e}")

    target_wait = 1.8 + random.random() * 1.8
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        log(f"已导航到目标页，等待 {target_wait:.1f}s 让页面加载")
        await asyncio.sleep(target_wait)
    except Exception as e:
        log(f"导航到目标页失败: {e}")


async def click_retry_if_needed(page) -> bool:
    """验证失败后点击框体重试。"""
    for frame in page.frames:
        try:
            text = await frame.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
            if not text:
                continue
            if not any(
                k in text
                for k in (
                    "验证失败",
                    "点击框体重试",
                    "点击重试",
                    "滑块加载失败",
                    "滑动失败",
                    "验证未通过",
                )
            ):
                continue
            for sel in ("#nc_1", ".nc_wrapper", "#baxia-dialog", ".nc-lang-cnt", ".errloading", "#nc_1_refresh1"):
                try:
                    elem = await frame.query_selector(sel)
                    if elem and await elem.is_visible():
                        await elem.click(timeout=2000)
                        log(f"已点击重试区域: {sel}")
                        await asyncio.sleep(2.2)
                        return True
                except Exception:
                    pass
            # 点击弹窗中心
            try:
                box = await frame.evaluate(
                    """() => {
                    const el = document.querySelector('#nc_1, .nc_wrapper, #baxia-dialog, .slide-verify');
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }"""
                )
                if box:
                    await page.mouse.click(box["x"], box["y"])
                    log("已点击弹窗中心触发重试")
                    await asyncio.sleep(2.2)
                    return True
            except Exception:
                pass
        except Exception:
            continue
    return False


async def solve_in_context(ctx, target_url: str, max_retries: int) -> dict:
    """在已注入 Cookie 的 context 中求解。失败后刷新重置 Baxia。"""
    result: dict[str, Any] = {
        "ok": False,
        "solved": False,
        "captchaDetected": False,
        "attempts": 0,
    }
    pages = ctx.pages
    page = pages[0] if pages else await ctx.new_page()
    screenshot_dir = os.path.join(os.getcwd(), "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        log(f"访问目标页面: {target_url}")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"页面加载警告: {e}")

    init_wait = 2.0 + random.random() * 1.5
    log(f"等待 {init_wait:.1f} 秒让页面加载完成...")
    await asyncio.sleep(init_wait)
    log(f"当前页面 URL: {page.url}")

    url_l = (page.url or "").lower()
    if any(x in url_l for x in ("login.taobao.com", "login.goofish.com", "/login", "/uilogin")):
        result["error"] = "Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie"
        result["isLoginPage"] = True
        return result

    human_action_count = 0
    HUMAN_ACTION_THRESHOLD = 3
    MAX_HUMAN_ACTIONS = 2
    last_error = ""
    last_screenshot = None

    for attempt in range(1, max_retries + 1):
        result["attempts"] = attempt
        log("=" * 50)
        log(f"第 {attempt}/{max_retries} 次尝试")
        await diagnose_frames(page)

        url_l = (page.url or "").lower()
        if any(x in url_l for x in ("login.taobao.com", "login.goofish.com", "/login", "/uilogin")):
            result["error"] = "Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie"
            return result

        detected, detected_selector = await detect_captcha_container(page)
        has_punish = any(
            "punish" in ((f.url or "").lower()) or "_____tmd_____" in ((f.url or "").lower())
            for f in page.frames
        )
        log(f"滑块容器检测: detected={detected}, selector={detected_selector}, has_punish_frame={has_punish}")

        if not detected and not has_punish:
            if await check_solved(page):
                log("✓ 未检测到滑块，验证通过！")
                result.update({"ok": True, "solved": True, "captchaDetected": False})
                return result
            # 可能还在加载
            await asyncio.sleep(2.0)
            detected, detected_selector = await detect_captcha_container(page)

        log("等待滑块按钮加载...")
        slider_info = await wait_for_slider_ready(page, max_wait_ms=10000)
        if slider_info and slider_info.get("is_login_page"):
            result["error"] = "Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie"
            return result
        if slider_info and slider_info.get("already_solved"):
            log("✓ 用户已手动完成滑块验证 / 无需验证")
            result.update({"ok": True, "solved": True, "captchaDetected": True})
            return result

        if not slider_info:
            last_error = "未找到滑块按钮"
            log(last_error)
            shot = os.path.join(screenshot_dir, f"slider-not-found-{int(time.time())}.png")
            try:
                await page.screenshot(path=shot, full_page=False)
                last_screenshot = shot
                result["screenshotPath"] = shot
            except Exception:
                pass
            log("刷新页面重试（彻底重置）...")
            await navigate_fresh(page, target_url)
            continue

        result["captchaDetected"] = True
        sx, sy, dist = slider_info["x"], slider_info["y"], slider_info["distance"]
        log(f"找到滑块: x={sx:.1f}, y={sy:.1f}, distance={dist:.1f}")

        # 拖动前再次确认是否已通过
        if await check_solved(page):
            detected2, _ = await detect_captcha_container(page)
            if not detected2:
                result.update({"ok": True, "solved": True, "captchaDetected": True})
                return result

        pre_path = os.path.join(screenshot_dir, f"slider-pre-{attempt}-{int(time.time())}.png")
        try:
            await page.screenshot(path=pre_path, full_page=False)
            last_screenshot = pre_path
        except Exception:
            pass

        # 拖动前短暂停顿（阅读弹窗）
        await asyncio.sleep(0.4 + random.random() * 0.7)

        try:
            if attempt % 2 == 0:
                log(f"  attempt={attempt} 使用【超出容器】拖动方法")
                await human_like_drag_out_of_container(page, sx, sy, dist, attempt)
            else:
                log(f"  attempt={attempt} 使用【容器内】拖动方法")
                await human_like_drag(page, sx, sy, dist, attempt)
        except Exception as e:
            last_error = f"拖动异常: {e}"
            log(last_error)
            await navigate_fresh(page, target_url)
            continue

        result_wait = 2.0 + random.random() * 1.2
        log(f"等待 {result_wait:.1f} 秒验证结果...")
        await asyncio.sleep(result_wait)

        post_path = os.path.join(screenshot_dir, f"slider-post-{attempt}-{int(time.time())}.png")
        try:
            await page.screenshot(path=post_path, full_page=False)
            last_screenshot = post_path
            result["screenshotPath"] = post_path
        except Exception:
            pass

        solved = await check_solved(page)
        if solved:
            # 检查是否“下载消息失败”假阳性
            try:
                body = await page.evaluate(
                    "() => document.body ? document.body.innerText.substring(0, 400) : ''"
                )
                if body and ("下载消息失败" in body or "加载失败" in body):
                    log("滑块通过但页面显示加载失败/下载消息失败，刷新重试")
                    await navigate_fresh(page, target_url)
                    continue
            except Exception:
                pass
            log("✓✓✓ 滑块验证通过！")
            result.update({"ok": True, "solved": True, "captchaDetected": True})
            return result

        last_error = f"第 {attempt} 次拖动未通过"
        log(f"× {last_error}，将刷新页面重置 Baxia 状态后重试")

        # 先点框体重试，再决定是否整页重置
        await click_retry_if_needed(page)
        await asyncio.sleep(1.0)

        # 连续失败触发“真人行动”：关弹窗 → 重置
        if attempt >= HUMAN_ACTION_THRESHOLD and human_action_count < MAX_HUMAN_ACTIONS:
            human_action_count += 1
            log(
                f"=== 连续 {attempt} 次失败，触发真人行动 "
                f"({human_action_count}/{MAX_HUMAN_ACTIONS}) ==="
            )
            closed = await close_captcha_dialog(page)
            if closed:
                log("已关闭弹窗，等待页面变化...")
                await asyncio.sleep(1.5)
            else:
                log("未找到关闭按钮，直接刷新页面")
            await navigate_fresh(page, target_url)
            cooldown = 3.5 + random.random() * 3.5
            log(f"冷静期 {cooldown:.1f}s ...")
            await asyncio.sleep(cooldown)
        else:
            # 关键：每次失败后彻底重置，避免同会话惩罚累积
            await navigate_fresh(page, target_url)
            await asyncio.sleep(1.0 + random.random() * 1.5)

    # 末尾给用户短窗口手动拖
    log("=== 所有自动重试已用完，等待 12 秒让用户手动拖动滑块 ===")
    for _ in range(6):
        await asyncio.sleep(2)
        if await check_solved(page):
            detected, _ = await detect_captcha_container(page)
            if not detected:
                result.update({"ok": True, "solved": True, "captchaDetected": True})
                return result

    result["error"] = last_error or f"滑块验证未通过，已重试 {max_retries} 次（含手动等待）"
    if last_screenshot:
        result["screenshotPath"] = last_screenshot
    return result


async def export_cookies(ctx) -> str:
    try:
        cookies = await ctx.cookies()
        # 优先 goofish / taobao 相关
        parts = []
        for c in cookies:
            name = c.get("name") or ""
            value = c.get("value") or ""
            if name and value is not None:
                parts.append(f"{name}={value}")
        return "; ".join(parts)
    except Exception as e:
        log(f"导出 cookies 失败: {e}")
        return ""


async def main_async(args) -> dict:
    start_time = time.time()
    result: dict[str, Any] = {
        "ok": False,
        "solved": False,
        "captchaDetected": False,
        "attempts": 0,
        "durationMs": 0,
    }

    try:
        with open(args.cookie_file, "r", encoding="utf-8") as f:
            cookie_str = f.read().strip()
    except Exception as e:
        result["error"] = f"读取 Cookie 文件失败: {e}"
        result["durationMs"] = int((time.time() - start_time) * 1000)
        return result

    if not cookie_str:
        result["error"] = "Cookie 字符串为空"
        result["durationMs"] = int((time.time() - start_time) * 1000)
        return result

    chrome_path = find_chrome_path()
    if not chrome_path:
        result["error"] = "未找到 Chrome 可执行文件"
        result["durationMs"] = int((time.time() - start_time) * 1000)
        return result

    log(f"Chrome 路径: {chrome_path}")
    temp_root = os.environ.get("TEMP") or "/tmp"
    user_data_dir = os.path.join(temp_root, f"chrome-slider-solve-{int(time.time())}")
    chrome_proc = None
    browser = None

    try:
        if os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)
        os.makedirs(user_data_dir, exist_ok=True)

        async with async_playwright() as p:
            # === 阶段1：持久化注入 Cookie ===
            log("=== 阶段1：注入 Cookie 到持久化目录 ===")
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                executable_path=chrome_path,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-popup-blocking",
                    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            # 仅写入 goofish 域，避免把登录 Cookie 复制到无关域
            cookies = parse_cookie_string(cookie_str, ".goofish.com")
            if cookies:
                await ctx.add_cookies(cookies)
                log(f"注入 {len(cookies)} 条 cookies")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=45000)
                log(f"首页加载完成: {page.url}")
            except Exception as e:
                log(f"首页加载警告: {e}")
            await asyncio.sleep(1.5)
            log("关闭上下文（持久化 Cookie）...")
            await ctx.close()

            # 清理 SingletonLock 以免二次启动失败
            lock_file = os.path.join(user_data_dir, "SingletonLock")
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except Exception:
                pass

            # === 阶段2：subprocess 启动干净 Chrome ===
            log("=== 阶段2：用 subprocess 启动干净的 Chrome ===")
            debug_port = 9222 + random.randint(0, 200)
            chrome_args = [
                chrome_path,
                f"--user-data-dir={user_data_dir}",
                f"--remote-debugging-port={debug_port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                "--disable-blink-features=AutomationControlled",
            ]
            log(f"Chrome 启动参数: port={debug_port}")
            chrome_proc = subprocess.Popen(
                chrome_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log("等待 8 秒让 Chrome 启动和页面加载...")
            await asyncio.sleep(8)

            # === 阶段3：CDP 连接 ===
            log(f"=== 阶段3：CDP 连接到 Chrome（端口 {debug_port}）===")
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
            log("CDP 连接成功")
            contexts = browser.contexts
            if not contexts:
                result["error"] = "CDP 连接成功但无 browser context"
                return result
            ctx2 = contexts[0]

            solve_result = await solve_in_context(ctx2, args.target_url, args.max_retries)
            result.update(solve_result)

            if result.get("solved"):
                fresh = await export_cookies(ctx2)
                if fresh:
                    result["cookies"] = fresh
                    result["cookieCount"] = fresh.count("=")
                    log(f"导出 {result['cookieCount']} 个最新 cookies（{len(fresh)} 字符）")

    except Exception as e:
        log(f"主流程异常: {e}")
        result["error"] = f"求解异常: {e}"
    finally:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        close_proc_gracefully(chrome_proc)
        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass

    result["durationMs"] = int((time.time() - start_time) * 1000)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="闲鱼滑块验证自动求解器")
    parser.add_argument("--cookie-file", required=True, help="Cookie 字符串文件路径")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL, help="目标页面 URL")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="最大拖动重试次数")
    args = parser.parse_args()
    result = asyncio.run(main_async(args))
    output_result(result)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
