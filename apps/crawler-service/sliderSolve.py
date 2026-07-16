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

WINDOW_WIDTH = 1366
WINDOW_HEIGHT = 768
DEFAULT_TARGET_URL = "https://www.goofish.com/im"
DEFAULT_MAX_RETRIES = 5

# 人工在「自动化窗口」里拖也失败的根因：环境被标为机器人（非轨迹）。
# 反检测脚本覆盖常见 CDP / webdriver / 指纹探针。
STEALTH_INIT_SCRIPT = r"""
(() => {
  try {
    // webdriver: 删除属性比返回 undefined 更难被 'in' 检测识破
    try {
      delete Object.getPrototypeOf(navigator).webdriver;
    } catch (e) {}
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined,
      configurable: true,
    });

    // chrome 运行时
    window.chrome = window.chrome || {};
    window.chrome.runtime = window.chrome.runtime || {
      OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
      PlatformOs: { WIN: 'win', MAC: 'mac', LINUX: 'linux', ANDROID: 'android' },
      PlatformArch: { X86_64: 'x86-64', X86_32: 'x86-32', ARM: 'arm' },
    };
    window.chrome.csi = window.chrome.csi || (() => ({ startE: Date.now(), onloadT: Date.now(), pageT: Math.random() * 1000, tran: 15 }));
    window.chrome.loadTimes = window.chrome.loadTimes || (() => ({
      commitLoadTime: Date.now() / 1000 - 4,
      connectionInfo: 'h2',
      finishDocumentLoadTime: Date.now() / 1000 - 2,
      finishLoadTime: Date.now() / 1000 - 1.5,
      firstPaintAfterLoadTime: 0,
      firstPaintTime: Date.now() / 1000 - 3,
      navigationType: 'Other',
      npnNegotiatedProtocol: 'h2',
      requestTime: Date.now() / 1000 - 5,
      startLoadTime: Date.now() / 1000 - 5,
      wasAlternateProtocolAvailable: false,
      wasFetchedViaSpdy: true,
      wasNpnNegotiated: true,
    }));

    // plugins / mimeTypes 真实结构
    const mkPlugin = (name, filename, description) => {
      const p = { name, filename, description, length: 1 };
      p[0] = { type: 'application/pdf', suffixes: 'pdf', description };
      p.item = (i) => p[i] || null;
      p.namedItem = (n) => (n === name ? p : null);
      return p;
    };
    const pluginData = [
      mkPlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      mkPlugin('Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      mkPlugin('Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
    ];
    Object.defineProperty(navigator, 'plugins', {
      get: () => {
        const arr = pluginData.slice();
        arr.item = (i) => arr[i] || null;
        arr.namedItem = (n) => arr.find(x => x.name === n) || null;
        arr.refresh = () => {};
        return arr;
      },
      configurable: true,
    });

    Object.defineProperty(navigator, 'languages', {
      get: () => ['zh-CN', 'zh', 'en-US', 'en'],
      configurable: true,
    });
    Object.defineProperty(navigator, 'language', {
      get: () => 'zh-CN',
      configurable: true,
    });
    Object.defineProperty(navigator, 'platform', {
      get: () => 'Win32',
      configurable: true,
    });
    Object.defineProperty(navigator, 'hardwareConcurrency', {
      get: () => 8,
      configurable: true,
    });
    Object.defineProperty(navigator, 'deviceMemory', {
      get: () => 8,
      configurable: true,
    });
    Object.defineProperty(navigator, 'maxTouchPoints', {
      get: () => 0,
      configurable: true,
    });

    // permissions 与 Notification 一致性
    if (navigator.permissions && navigator.permissions.query) {
      const orig = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = (params) => {
        if (params && params.name === 'notifications') {
          const state = (typeof Notification !== 'undefined' && Notification.permission) || 'default';
          return Promise.resolve({ state, onchange: null });
        }
        return orig(params);
      };
    }

    // WebGL vendor（避免 SwiftShader）
    const patchWebGL = (proto) => {
      if (!proto || !proto.getParameter) return;
      const orig = proto.getParameter;
      proto.getParameter = function(param) {
        if (param === 37445) return 'Google Inc. (NVIDIA)';
        if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)';
        return orig.call(this, param);
      };
    };
    patchWebGL(WebGLRenderingContext && WebGLRenderingContext.prototype);
    if (typeof WebGL2RenderingContext !== 'undefined') {
      patchWebGL(WebGL2RenderingContext.prototype);
    }

    // 隐藏 cdc_ / $cdc_ / __playwright / __pw
    const kill = (obj) => {
      try {
        Object.keys(obj).forEach((k) => {
          if (/^cdc_|\$cdc_|__playwright|__pw_/.test(k)) {
            try { delete obj[k]; } catch (e) {}
          }
        });
      } catch (e) {}
    };
    kill(window);
    kill(document);

    // iframe 内容也尽量补 webdriver（同源）
    const desc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    if (desc) {
      Object.defineProperty(Navigator.prototype, 'webdriver', {
        get: () => undefined,
        configurable: true,
      });
    }
  } catch (e) {}
})();
"""


def get_chrome_user_agent(chrome_path: str) -> str:
    """UA 主版本尽量匹配本机 Chrome，避免 Client Hints 与 UA 不一致。"""
    ver = "131.0.0.0"
    try:
        # Windows: 从 chrome.exe 旁 Version 目录推断，或用 --version
        import re as _re
        out = subprocess.run(
            [chrome_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        m = _re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", (out.stdout or "") + (out.stderr or ""))
        if m:
            ver = m.group(0)
        else:
            # File version style 146.0.7680.76
            parent = os.path.dirname(chrome_path)
            for name in os.listdir(parent):
                if _re.match(r"^\d+\.\d+\.\d+\.\d+$", name):
                    ver = name
                    break
    except Exception:
        pass
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
    )

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


# ---------- 全自动：全局单飞锁（防止多账号同时开浏览器互相踩风控）----------
_SOLVE_LOCK_PATH = os.path.join(os.environ.get("TEMP") or "/tmp", "xya-slider-solve.lock")
_SEED_PROFILE_DIR = os.path.join(os.environ.get("TEMP") or "/tmp", "xya-slider-seed-v2")


class _FileLock:
    """跨进程文件锁，保证全自动滑块同一时刻只跑 1 个浏览器。"""

    def __init__(self, path: str, timeout: float = 300.0):
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        import msvcrt  # Windows

        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._fh = open(self.path, "a+b")
        start = time.time()
        while True:
            try:
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"等待滑块全局锁超时: {self.path}")
                time.sleep(0.5)

    def __exit__(self, *args):
        try:
            import msvcrt

            if self._fh:
                try:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                self._fh.close()
        except Exception:
            pass


def _ignore_chrome_lock_files(dirpath: str, names: list[str]) -> list[str]:
    ignore = set()
    for n in names:
        ln = n.lower()
        if ln in {
            "singletonlock",
            "singletoncookie",
            "singletonsocket",
            "lockfile",
            "runningchromeversion",
        } or ln.endswith(".lock"):
            ignore.add(n)
        # 体积大且无助于指纹的缓存可跳过
        if ln in {"cache", "code cache", "gpu cache", "service worker", "shadercache"}:
            ignore.add(n)
    return list(ignore)


def prepare_profile_dir(dest: str) -> str:
    """准备浏览器配置目录：优先克隆预热 seed，避免空 profile 被秒杀。"""
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)

    seed = _SEED_PROFILE_DIR
    seed_default = os.path.join(seed, "Default")
    if os.path.isdir(seed_default):
        try:
            shutil.copytree(seed, dest, dirs_exist_ok=True, ignore=_ignore_chrome_lock_files)
            log(f"已克隆预热 profile: {seed} -> {dest}")
            return dest
        except Exception as e:
            log(f"克隆 seed profile 失败，使用空目录: {e}")
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest, exist_ok=True)
    return dest


async def ensure_seed_profile(playwright, chrome_path: str, ua: str) -> None:
    """首次全自动运行时预热 seed：访问闲鱼首页生成真实 LocalStorage/站点数据。"""
    seed = _SEED_PROFILE_DIR
    marker = os.path.join(seed, ".xya_seed_ready")
    if os.path.isfile(marker):
        return
    log(f"=== 预热 seed Chrome 配置（全自动，仅首次）: {seed} ===")
    if os.path.exists(seed):
        shutil.rmtree(seed, ignore_errors=True)
    os.makedirs(seed, exist_ok=True)
    ctx = None
    try:
        ctx = await playwright.chromium.launch_persistent_context(
            seed,
            headless=False,
            executable_path=chrome_path,
            viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=ua,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                "--lang=zh-CN",
            ],
        )
        await ctx.add_init_script(STEALTH_INIT_SCRIPT)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2.5 + random.random() * 2)
        try:
            await page.mouse.wheel(0, 400)
        except Exception:
            pass
        await asyncio.sleep(1.5)
        await page.goto("https://www.goofish.com/im", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2.0)
        await ctx.close()
        ctx = None
        with open(marker, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
        log("seed profile 预热完成")
    except Exception as e:
        log(f"seed profile 预热失败（可继续）: {e}")
        try:
            if ctx:
                await ctx.close()
        except Exception:
            pass


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


def _win_dpi_scale() -> float:
    """CSS 像素 -> 物理像素比例（高 DPI 下 OS 鼠标坐标关键）。"""
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            dpi = int(ctypes.windll.user32.GetDpiForSystem())
            return max(1.0, dpi / 96.0)
        except Exception:
            return 1.0
    except Exception:
        return 1.0


def _win_send_input_move_click(actions: list[tuple[str, int, int, int]]) -> None:
    """Windows 系统级鼠标事件（SendInput），绕过部分 CDP 合成轨迹检测。

    actions: list of (type, x, y, delay_ms) type in move/down/up
    坐标为屏幕物理像素（已按 DPI 换算）。
    """
    if sys.platform != "win32":
        raise RuntimeError("SendInput only on Windows")

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_ABSOLUTE = 0x8000
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        _anonymous_ = ("i",)
        _fields_ = [("type", wintypes.DWORD), ("i", _I)]

    sw = user32.GetSystemMetrics(SM_CXSCREEN)
    sh = user32.GetSystemMetrics(SM_CYSCREEN)

    def to_abs(x: int, y: int) -> tuple[int, int]:
        ax = int(max(0, min(sw - 1, x)) * 65535 / max(1, sw - 1))
        ay = int(max(0, min(sh - 1, y)) * 65535 / max(1, sh - 1))
        return ax, ay

    def send_move(x: int, y: int) -> None:
        ax, ay = to_abs(x, y)
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi = MOUSEINPUT(ax, ay, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
        if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
            raise OSError("SendInput move failed")

    def send_btn(flags: int) -> None:
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
            raise OSError("SendInput button failed")

    for typ, x, y, delay_ms in actions:
        if typ == "move":
            send_move(x, y)
        elif typ == "down":
            send_move(x, y)
            send_btn(MOUSEEVENTF_LEFTDOWN)
        elif typ == "up":
            send_move(x, y)
            send_btn(MOUSEEVENTF_LEFTUP)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)


async def os_level_human_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> bool:
    """把页面坐标映射到屏幕，用系统鼠标拖动（更像真人硬件输入）。"""
    if sys.platform != "win32":
        return False
    try:
        pos = await page.evaluate(
            """([vx, vy]) => {
              const borderX = Math.max(0, (window.outerWidth - window.innerWidth) / 2);
              const borderY = Math.max(0, window.outerHeight - window.innerHeight - borderX);
              const dpr = window.devicePixelRatio || 1;
              const sx = window.screenX + borderX + vx;
              const sy = window.screenY + borderY + vy;
              return { sx, sy, borderX, borderY, dpr };
            }""",
            [start_x, start_y],
        )
        # CSS 像素 -> 物理像素（高 DPI）
        scale = _win_dpi_scale()
        # 优先用系统 DPI；若与页面 dpr 差很大，取较大值避免点偏
        page_dpr = float(pos.get("dpr") or 1)
        scale = max(scale, page_dpr if 0.9 < page_dpr < 4 else scale)

        base_x = int(round(float(pos["sx"]) * scale))
        base_y = int(round(float(pos["sy"]) * scale))
        dist_px = float(distance) * scale
        end_x = int(round(base_x + dist_px))
        log(
            f"  OS 坐标换算: page=({start_x:.1f},{start_y:.1f}) -> screen=({base_x},{base_y}) "
            f"scale={scale:.2f} border=({pos.get('borderX')},{pos.get('borderY')})"
        )

        steps = 48 + random.randint(0, 20)
        actions: list[tuple[str, int, int, int]] = []
        ax0 = base_x - int(40 * scale) - random.randint(0, int(30 * scale))
        ay0 = base_y + random.randint(int(-20 * scale), int(20 * scale))
        actions.append(("move", ax0, ay0, 100 + random.randint(0, 100)))
        actions.append(("move", base_x, base_y, 140 + random.randint(0, 120)))
        actions.append(("down", base_x, base_y, 110 + random.randint(0, 90)))
        for i in range(1, steps + 1):
            p = i / steps
            # 慢启动：前 25% 只完成约 12% 行程
            if p < 0.25:
                eased = 0.12 * (p / 0.25) ** 2.4
            elif p < 0.75:
                mid = (p - 0.25) / 0.5
                eased = 0.12 + 0.70 * (mid * mid * (3 - 2 * mid))
            else:
                tail = (p - 0.75) / 0.25
                eased = 0.82 + 0.18 * (1 - (1 - tail) ** 2)
            x = int(base_x + dist_px * eased)
            y = int(
                base_y
                + math.sin(math.pi * p) * (3 + random.random() * 6) * scale
                * (1 if random.random() > 0.4 else -1)
            )
            delay = int(22 + random.random() * 50)
            if p < 0.2 or p > 0.8:
                delay = int(delay * 1.8)
            actions.append(("move", x, y, delay))
        # 终点：几乎不超轨（过冲过大易判失败）
        actions.append(("move", end_x + random.randint(0, int(4 * scale)), base_y + random.randint(-2, 2), 80))
        actions.append(("move", end_x, base_y, 100))
        actions.append(("up", end_x, base_y, 60))
        log(f"  OS 级拖动: screen=({base_x},{base_y}) -> +{dist_px:.0f}px steps={steps} attempt={attempt}")
        await page.bring_to_front()
        await asyncio.sleep(0.3)
        try:
            await page.mouse.move(start_x - 15, start_y, steps=6)
        except Exception:
            pass
        await asyncio.to_thread(_win_send_input_move_click, actions)
        return True
    except Exception as e:
        log(f"  OS 级拖动失败，回退 page.mouse: {e}")
        return False


async def element_hover_drag(page, button, distance: float, attempt: int = 1) -> None:
    """基于元素 hover 的 page.mouse 拖动：先悬停按钮再按下，减少“点空”。"""
    box = await button.bounding_box()
    if not box:
        raise RuntimeError("button box gone")
    sx = box["x"] + box["width"] / 2
    sy = box["y"] + box["height"] / 2
    # attempt 调制终点：1 精确、2 略超、3 略欠再补
    if attempt == 1:
        dist = distance
    elif attempt == 2:
        dist = distance + 4 + random.random() * 6
    else:
        dist = max(180.0, distance - 3 + random.random() * 5)

    log(f"  元素悬停拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} attempt={attempt}")
    await button.hover(timeout=3000)
    await asyncio.sleep(0.15 + random.random() * 0.25)
    await page.mouse.move(sx, sy, steps=3)
    await asyncio.sleep(0.08 + random.random() * 0.12)
    await page.mouse.down()
    await asyncio.sleep(0.1 + random.random() * 0.15)

    steps = 36 + random.randint(0, 16)
    for i in range(1, steps + 1):
        p = i / steps
        if p < 0.22:
            eased = 0.1 * (p / 0.22) ** 2.2
        elif p < 0.78:
            mid = (p - 0.22) / 0.56
            eased = 0.1 + 0.75 * (mid * mid * (3 - 2 * mid))
        else:
            tail = (p - 0.78) / 0.22
            eased = 0.85 + 0.15 * math.sin(tail * math.pi / 2)
        x = sx + dist * eased
        y = sy + math.sin(math.pi * p) * (2 + random.random() * 4) * (1 if random.random() > 0.5 else -1)
        await page.mouse.move(x, y, steps=1)
        delay = 18 + random.random() * 42
        if p < 0.2 or p > 0.85:
            delay *= 1.7
        await page.wait_for_timeout(delay)

    await page.mouse.move(sx + dist, sy + random.uniform(-2, 2), steps=2)
    await page.wait_for_timeout(60 + random.random() * 80)
    await page.mouse.up()
    await page.wait_for_timeout(40 + random.random() * 60)


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
    """遍历所有 frame 找滑块按钮与可拖距离。

    距离优先用 JS 精测：轨道右缘 - 按钮右缘（更贴近 Baxia 判定的“到最右边”）。
    """
    for frame in page.frames:
        for sel in SLIDER_BUTTON_SELECTORS:
            try:
                button = await frame.query_selector(sel)
                if not button:
                    continue
                box = await button.bounding_box()
                if not box or box.get("width", 0) <= 0:
                    continue

                # JS 精测可拖距离
                dist_js = None
                try:
                    dist_js = await frame.evaluate(
                        """(btnSel) => {
                          const btn = document.querySelector(btnSel)
                            || document.querySelector('#nc_1_n1z')
                            || document.querySelector('.btn_slide');
                          if (!btn) return null;
                          const track = document.querySelector('.nc_scale')
                            || document.querySelector('#nc_1_n1t')
                            || document.querySelector('.scale_text')
                            || btn.parentElement;
                          if (!track) return null;
                          const br = btn.getBoundingClientRect();
                          const tr = track.getBoundingClientRect();
                          // 需要把按钮左边拖到轨道右边内侧
                          const d = (tr.right - br.right);
                          return d > 20 ? d : (tr.width - br.width);
                        }""",
                        sel,
                    )
                except Exception:
                    dist_js = None

                track_width = float(dist_js) if dist_js and float(dist_js) > 20 else None
                if track_width is None:
                    track_width = 260.0
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

                # 常见轨道可拖区间约 200~320
                track_width = max(200.0, min(float(track_width), 340.0))
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


async def navigate_fresh(page, target_url: str, *, hard: bool = False) -> None:
    """重置导航。

    hard=False（默认）：不清 localStorage/sessionStorage，避免把登录痕迹一并清掉加重风控。
    hard=True：清 storage 后回首页再进目标页（仅在加载失败连跪时使用）。
    """
    if hard:
        try:
            await page.evaluate(
                """() => {
                try { localStorage.clear(); } catch(e) {}
                try { sessionStorage.clear(); } catch(e) {}
            }"""
            )
            log("已清理 localStorage/sessionStorage（hard）")
        except Exception as e:
            log(f"清理存储失败(可忽略): {e}")

    home_wait = 1.5 + random.random() * 1.8
    try:
        await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=45000)
        log(f"已回到首页，等待 {home_wait:.1f}s 后重新导航到目标页")
        await asyncio.sleep(home_wait)
        # 拟人轻微滚动
        try:
            await page.mouse.wheel(0, 150 + random.randint(0, 200))
        except Exception:
            pass
        await asyncio.sleep(0.4 + random.random() * 0.6)
    except Exception as e:
        log(f"回首页失败: {e}")

    target_wait = 2.0 + random.random() * 1.8
    try:
        # 优先仍用拟人路径；失败再直开
        try:
            await human_warmup_and_enter_im(page, target_url or DEFAULT_TARGET_URL)
        except Exception:
            await page.goto(target_url or DEFAULT_TARGET_URL, wait_until="domcontentloaded", timeout=45000)
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


async def page_shows_load_failure(page) -> bool:
    """检测消息页/会话页「加载失败」风控态（人工拖也过不了的典型表现）。"""
    try:
        text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 800) : ''"
        )
        if not text:
            return False
        return bool(
            any(
                k in text
                for k in (
                    "加载失败",
                    "下载消息失败",
                    "网络异常",
                    "请刷新页面",
                    "连接中断",
                    "系统繁忙",
                )
            )
        )
    except Exception:
        return False


async def human_warmup_and_enter_im(page, target_url: str):
    """拟人路径进入消息页：首页闲逛 → 点击消息（优先），避免直接 goto /im 触发反爬。

    返回实际操作的 page（可能是 popup 消息窗）。
    """
    home = "https://www.goofish.com/"
    log(f"拟人导航：先打开首页 {home}")
    try:
        await page.goto(home, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"首页加载警告: {e}")

    # 首页随机鼠标移动 + 轻微滚动（制造真实浏览痕迹）
    for _ in range(3 + random.randint(0, 3)):
        x = 120 + random.random() * (WINDOW_WIDTH - 240)
        y = 100 + random.random() * (WINDOW_HEIGHT - 200)
        await page.mouse.move(x, y, steps=random.randint(5, 14))
        await asyncio.sleep(0.15 + random.random() * 0.35)
    try:
        await page.mouse.wheel(0, 200 + random.randint(0, 400))
    except Exception:
        pass
    await asyncio.sleep(1.2 + random.random() * 1.8)

    # 尝试点击「消息」入口（侧边栏）
    async def _click_msg_eval() -> bool:
        return bool(
            await page.evaluate(
                """() => {
                const wraps = Array.from(document.querySelectorAll('[class*="sidebar-item-wrap"], [class*="sidebar"] a, aside a, [class*="side"] a'));
                const t = wraps.find(w => ((w.textContent||'').trim().includes('消息')));
                if (!t) return false;
                t.scrollIntoView({block:'center'});
                t.click();
                return true;
            }"""
            )
        )

    async def _click_msg_locator() -> bool:
        loc = page.locator('[class*="sidebar-item-wrap"]').filter(has_text="消息").first
        if await loc.count() > 0:
            await loc.click(timeout=3000, force=True)
            return True
        return False

    for name, fn in (("eval-click", _click_msg_eval), ("locator-click", _click_msg_locator)):
        try:
            try:
                async with page.expect_popup(timeout=5000) as popup_info:
                    ok = await fn()
                    if not ok:
                        raise RuntimeError("no-msg-entry")
                popup = await popup_info.value
                await popup.wait_for_load_state("domcontentloaded", timeout=30000)
                log(f"消息页新窗口已打开 via {name}: {popup.url}")
                await asyncio.sleep(2.0 + random.random() * 1.5)
                return popup
            except Exception:
                # 可能同页跳转或未弹出
                ok = False
                try:
                    ok = await fn()
                except Exception:
                    ok = False
                await asyncio.sleep(2.0)
                if "/im" in (page.url or ""):
                    log(f"消息页同窗口打开 via {name}: {page.url}")
                    return page
                if not ok:
                    continue
        except Exception as e:
            log(f"点击消息失败 {name}: {e}")

    # 回退：直接访问 /im（风险更高）
    log("未点到消息入口，回退直接访问目标页（可能触发加载失败）")
    try:
        await page.goto(target_url or DEFAULT_TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"目标页加载警告: {e}")
    await asyncio.sleep(2.0 + random.random() * 1.5)
    return page


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

    # 拟人路径进入消息页（避免直接 /im）
    page = await human_warmup_and_enter_im(page, target_url or DEFAULT_TARGET_URL)
    log(f"当前操作页 URL: {page.url}")

    if await page_shows_load_failure(page):
        log("⚠ 进入消息页即出现「加载失败」——浏览器环境很可能已被风控标记")
        shot = os.path.join(screenshot_dir, f"load-fail-entry-{int(time.time())}.png")
        try:
            await page.screenshot(path=shot, full_page=False)
            result["screenshotPath"] = shot
        except Exception:
            pass
        # 仍继续尝试：有时滑块后刷新可恢复

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
    load_fail_streak = 0

    for attempt in range(1, max_retries + 1):
        result["attempts"] = attempt
        log("=" * 50)
        log(f"第 {attempt}/{max_retries} 次尝试")
        await diagnose_frames(page)

        # 风险探针：记录关键环境信号（用于分析为何人工也失败）
        try:
            probe = await page.evaluate(
                """() => ({
                  webdriver: navigator.webdriver,
                  languages: navigator.languages,
                  plugins: navigator.plugins ? navigator.plugins.length : -1,
                  chrome: !!window.chrome,
                  hw: navigator.hardwareConcurrency,
                  ua: navigator.userAgent.slice(0, 80),
                  hasCdc: Object.keys(window).some(k => k.startsWith('cdc_') || k.startsWith('$cdc_')),
                })"""
            )
            log(f"环境探针: {probe}")
        except Exception:
            pass

        if await page_shows_load_failure(page):
            load_fail_streak += 1
            last_error = "页面显示加载失败（环境/会话被风控）"
            log(f"⚠ {last_error} streak={load_fail_streak}")
            shot = os.path.join(screenshot_dir, f"load-fail-{attempt}-{int(time.time())}.png")
            try:
                await page.screenshot(path=shot, full_page=False)
                last_screenshot = shot
                result["screenshotPath"] = shot
            except Exception:
                pass
            # 加载失败：硬重置（清 storage）
            await navigate_fresh(page, target_url or DEFAULT_TARGET_URL, hard=True)
            page = await human_warmup_and_enter_im(page, target_url or DEFAULT_TARGET_URL)
            if load_fail_streak >= 3:
                result["error"] = (
                    "连续出现「加载失败」：自动化浏览器环境被闲鱼风控标记，"
                    "即使人工拖拽也难以通过。请换用本机日常 Chrome 配置/新 Cookie 后重试"
                )
                return result
            continue
        else:
            load_fail_streak = 0

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
            await navigate_fresh(page, target_url or DEFAULT_TARGET_URL)
            page = await human_warmup_and_enter_im(page, target_url or DEFAULT_TARGET_URL)
            continue

        result["captchaDetected"] = True
        button_el = slider_info.get("button")
        sx, sy, dist = slider_info["x"], slider_info["y"], float(slider_info["distance"])
        # 不再默认大幅过冲；终点微调交给各拖拽策略
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

        # 拖动前：先“看”弹窗 0.8~2s，模拟真人阅读
        await asyncio.sleep(0.8 + random.random() * 1.2)
        for _ in range(2 + random.randint(0, 2)):
            await page.mouse.move(
                sx + random.uniform(-40, 20),
                sy + random.uniform(-25, 25),
                steps=random.randint(4, 10),
            )
            await asyncio.sleep(0.06 + random.random() * 0.15)

        try:
            # 轮换：1 元素悬停拖  2 OS  3 容器内  4 出容器  5+ 再 OS
            if attempt == 1 and button_el is not None:
                log(f"  attempt={attempt} 使用【元素悬停】page.mouse 拖动")
                await element_hover_drag(page, button_el, dist, attempt)
            elif attempt in (2, 5) and sys.platform == "win32":
                log(f"  attempt={attempt} 使用【OS 系统鼠标 SendInput】拖动")
                ok_os = await os_level_human_drag(page, sx, sy, dist, attempt)
                if not ok_os:
                    if button_el is not None:
                        await element_hover_drag(page, button_el, dist, attempt)
                    else:
                        await human_like_drag(page, sx, sy, dist, attempt)
            elif attempt == 3:
                log(f"  attempt={attempt} 使用【容器内】page.mouse 拖动")
                await human_like_drag(page, sx, sy, dist, attempt)
            else:
                log(f"  attempt={attempt} 使用【超出容器】page.mouse 拖动")
                await human_like_drag_out_of_container(page, sx, sy, dist, attempt)
        except Exception as e:
            last_error = f"拖动异常: {e}"
            log(last_error)
            await navigate_fresh(page, target_url or DEFAULT_TARGET_URL, hard=False)
            continue

        result_wait = 2.6 + random.random() * 1.8
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
        log(f"× {last_error}")

        # 优先点「框体重试」并等待新滑块，而不是立刻清会话硬刷新
        clicked = await click_retry_if_needed(page)
        if clicked:
            log("已点击框体重试，等待新滑块就绪...")
            await asyncio.sleep(2.0 + random.random() * 1.5)
            new_info = await wait_for_slider_ready(page, max_wait_ms=8000)
            if new_info and not new_info.get("is_login_page") and not new_info.get("already_solved"):
                log("新滑块已就绪，下一轮直接拖")
                await asyncio.sleep(0.5 + random.random() * 0.8)
                continue

        # 连续失败：关弹窗 + 软重置（不清 storage）
        if attempt >= HUMAN_ACTION_THRESHOLD and human_action_count < MAX_HUMAN_ACTIONS:
            human_action_count += 1
            log(
                f"=== 连续 {attempt} 次失败，触发软重置 "
                f"({human_action_count}/{MAX_HUMAN_ACTIONS}) ==="
            )
            closed = await close_captcha_dialog(page)
            if closed:
                log("已关闭弹窗，等待页面变化...")
                await asyncio.sleep(1.5)
            await navigate_fresh(page, target_url or DEFAULT_TARGET_URL, hard=False)
            cooldown = 4.0 + random.random() * 4.0
            log(f"冷静期 {cooldown:.1f}s ...")
            await asyncio.sleep(cooldown)
        else:
            # 轻量等待后再试同页新滑块，降低连续 punish 刷新
            await asyncio.sleep(1.2 + random.random() * 1.5)

    # 全自动：不再等待人工拖拽，直接失败返回
    log("=== 全自动重试已用完，不再进入半自动人工等待 ===")
    result["error"] = last_error or f"滑块验证未通过，已全自动重试 {max_retries} 次"
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


async def _launch_solve_once(
    playwright,
    chrome_path: str,
    ua: str,
    cookie_str: str,
    target_url: str,
    max_retries: int,
    proxy: Optional[dict] = None,
) -> dict:
    """启动一次浏览器并求解（内部复用）。"""
    temp_root = os.environ.get("TEMP") or "/tmp"
    user_data_dir = os.path.join(
        temp_root, f"chrome-slider-warm-{int(time.time())}-{random.randint(1000, 9999)}"
    )
    prepare_profile_dir(user_data_dir)
    ctx = None
    try:
        log(
            "=== 启动真实 Chrome（seed 克隆 + 无 remote-debugging-port）"
            f" hasProxy={bool(proxy and proxy.get('server'))} ==="
        )
        launch_kwargs = dict(
            user_data_dir=user_data_dir,
            headless=False,
            executable_path=chrome_path,
            viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=ua,
            color_scheme="light",
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                "--disable-blink-features=AutomationControlled",
                "--lang=zh-CN",
            ],
        )
        if proxy and proxy.get("server"):
            launch_kwargs["proxy"] = {
                "server": str(proxy["server"]),
                **({"username": str(proxy["username"])} if proxy.get("username") else {}),
                **({"password": str(proxy["password"])} if proxy.get("password") else {}),
            }
        try:
            ctx = await playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            log(f"launch_persistent_context 失败，重试精简参数: {e}")
            launch_kwargs.pop("timezone_id", None)
            launch_kwargs["args"] = [
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
            ]
            ctx = await playwright.chromium.launch_persistent_context(**launch_kwargs)

        await ctx.add_init_script(STEALTH_INIT_SCRIPT)
        cookies = parse_cookie_string(cookie_str, ".goofish.com")
        if cookies:
            await ctx.add_cookies(cookies)
            log(f"注入 {len(cookies)} 条 cookies")

        page0 = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page0.goto("about:blank")
        except Exception:
            pass
        await asyncio.sleep(0.6 + random.random() * 0.9)

        solve_result = await solve_in_context(ctx, target_url, max_retries)
        if solve_result.get("solved"):
            fresh = await export_cookies(ctx)
            if fresh:
                solve_result["cookies"] = fresh
                solve_result["cookieCount"] = fresh.count("=")
                log(f"导出 {solve_result['cookieCount']} 个最新 cookies（{len(fresh)} 字符）")
        return solve_result
    finally:
        if ctx is not None:
            try:
                await ctx.close()
            except Exception:
                pass
        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass


async def main_async(args) -> dict:
    """全自动求解入口（无半自动人工介入）。

    策略：
    1) 全局文件锁：同时只允许 1 个求解浏览器
    2) seed profile 预热 + 克隆：降低空配置被秒杀概率
    3) 真实 Chrome + 去 enable-automation + stealth
    4) 拟人进消息页 + 多策略拖拽（OS 鼠标 / page.mouse）
    5) 首轮全失败后，换新 profile 再全自动重开一轮（仍无人工）
    """
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

    ua = get_chrome_user_agent(chrome_path)
    log(f"Chrome 路径: {chrome_path}")
    log(f"UA: {ua}")

    try:
        # 跨进程单飞：避免多账号同时求解把 IP/设备画像打爆
        with _FileLock(_SOLVE_LOCK_PATH, timeout=360.0):
            log("已获取全自动滑块全局锁")
            async with async_playwright() as p:
                await ensure_seed_profile(p, chrome_path, ua)

                proxy_cfg = None
                if getattr(args, "proxy_server", None):
                    proxy_cfg = {
                        "server": args.proxy_server,
                        "username": getattr(args, "proxy_username", None) or None,
                        "password": getattr(args, "proxy_password", None) or None,
                    }
                    log(f"使用绑定代理 server={args.proxy_server}")

                # 第一轮
                r1 = await _launch_solve_once(
                    p, chrome_path, ua, cookie_str, args.target_url, args.max_retries, proxy=proxy_cfg,
                )
                result.update(r1)
                total_attempts = int(r1.get("attempts") or 0)

                # 全自动第二轮：仅当检测到滑块且未通过时，换 profile 再来一次
                if (
                    not result.get("solved")
                    and result.get("captchaDetected")
                    and not result.get("isLoginPage")
                ):
                    log("=== 全自动第二轮：新 profile 重开浏览器再试 ===")
                    await asyncio.sleep(2.0 + random.random() * 2.5)
                    r2 = await _launch_solve_once(
                        p,
                        chrome_path,
                        ua,
                        cookie_str,
                        args.target_url,
                        max(2, min(3, int(args.max_retries or 3))),
                        proxy=proxy_cfg,
                    )
                    total_attempts += int(r2.get("attempts") or 0)
                    # 第二轮成功则覆盖；失败保留第一轮截图/错误
                    if r2.get("solved"):
                        result.update(r2)
                    else:
                        result["attempts"] = total_attempts
                        if r2.get("error"):
                            result["error"] = (
                                f"{result.get('error') or ''} | 第二轮: {r2.get('error')}"
                            ).strip(" |")
                        if r2.get("screenshotPath"):
                            result["screenshotPath"] = r2.get("screenshotPath")
                result["attempts"] = total_attempts or result.get("attempts") or 0

    except TimeoutError as e:
        result["error"] = str(e)
    except Exception as e:
        log(f"主流程异常: {e}")
        result["error"] = f"求解异常: {e}"

    result["durationMs"] = int((time.time() - start_time) * 1000)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="闲鱼滑块验证自动求解器")
    parser.add_argument("--cookie-file", required=True, help="Cookie 字符串文件路径")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL, help="目标页面 URL")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="最大拖动重试次数")
    parser.add_argument("--proxy-server", default="", help="账号绑定代理 server，如 http://host:port")
    parser.add_argument("--proxy-username", default="", help="代理用户名")
    parser.add_argument("--proxy-password", default="", help="代理密码")
    args = parser.parse_args()
    result = asyncio.run(main_async(args))
    output_result(result)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
