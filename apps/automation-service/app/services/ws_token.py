"""
WebSocket Token 获取模块。
通过闲鱼 H5 API 获取 WebSocket 连接所需的 accessToken。
"""
import hashlib
import json
import logging
import os
import re
import time
from typing import Optional, Tuple
from urllib.parse import quote

import requests

from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)


def _try_x5sec_injection(cookie_str: str, m_h5_tk: str, proxies: Optional[dict] = None) -> Tuple[Optional[str], Optional[str]]:
    """x5sec 主方案：从 Redis 读取缓存的 x5sec，注入到 cookie 后重试 Token API。

    当 _call_token_api 返回 CAPTCHA_NEEDED（FAIL_SYS_USER_VALIDATE）时调用。
    如果 Redis 中有缓存的 x5sec，将其注入到 cookie 中绕过滑块验证。

    Args:
        cookie_str: 原始 Cookie 字符串
        m_h5_tk: 当前使用的 _m_h5_tk
        proxies: requests 代理格式（方案G：住宅IP代理）

    Returns:
        (accessToken, injected_cookie_str) — 成功时两个都有值；失败时两个都是 None
    """
    if not cookie_str:
        return None, None

    try:
        from .x5sec_cache_client import (
            get_cached_x5sec,
            inject_x5sec_into_cookie,
            cookie_has_x5sec,
        )
    except ImportError:
        logger.debug("_try_x5sec_injection: x5sec_cache_client 模块不可用")
        return None, None

    # 如果 cookie 中已包含 x5sec，说明已经注入过但仍然失败，不再重试
    if cookie_has_x5sec(cookie_str):
        logger.debug("_try_x5sec_injection: cookie 已包含 x5sec 但仍失败，不再重试")
        return None, None

    # 从 Redis 读取缓存的 x5sec
    cached_x5sec = get_cached_x5sec(cookie_str)
    if not cached_x5sec:
        logger.info("_try_x5sec_injection: Redis 中无缓存的 x5sec，跳过注入")
        return None, None

    logger.info(
        "_try_x5sec_injection: 命中 x5sec 缓存 (长度=%d)，注入到 cookie 后重试 Token API",
        len(cached_x5sec),
    )

    # 注入 x5sec 到 cookie
    injected_cookie = inject_x5sec_into_cookie(cookie_str, cached_x5sec)
    if not injected_cookie or injected_cookie == cookie_str:
        logger.warning("_try_x5sec_injection: x5sec 注入失败")
        return None, None

    # 用注入后的 cookie 重新调用 Token API
    result = _call_token_api(injected_cookie, m_h5_tk, proxies=proxies)
    if result == CAPTCHA_NEEDED:
        logger.warning("_try_x5sec_injection: 注入 x5sec 后仍触发滑块验证（x5sec 可能已失效）")
        # 清除失效的 x5sec 缓存
        try:
            from .x5sec_cache_client import evict_cached_x5sec
            evict_cached_x5sec(cookie_str)
            logger.info("_try_x5sec_injection: 已清除失效的 x5sec 缓存")
        except Exception:
            pass
        return None, None
    elif result:
        logger.info(
            "_try_x5sec_injection: x5sec 注入成功！获取到 accessToken (长度=%d)",
            len(result),
        )
        return result, injected_cookie
    else:
        logger.warning("_try_x5sec_injection: 注入 x5sec 后 Token API 返回空")
        return None, None


def _try_http_x5sec_extract(cookie_str: str, m_h5_tk: str, proxies: Optional[dict] = None) -> Tuple[Optional[str], Optional[str]]:
    """x5sec 主方案（优先级 2.5）：纯 HTTP 提取 x5sec，注入后重试 Token API。

    无需浏览器，只需 HTTP 请求。是最快的 x5sec 获取方式（~1 秒）。

    两个来源：
    1. 复用刚发出的 Token API 请求的 CAPTCHA 响应 Set-Cookie（零额外请求）
       — _call_token_api 检测到 CAPTCHA_NEEDED 时，已将 Set-Cookie 中的 x5sec 存入 _last_captcha_x5sec
    2. 主动 HTTP GET goofish.com 首页，检查 Set-Cookie 是否包含 x5sec
       — 如果账号未被 punish，服务器可能在首页响应中设置 x5sec

    详见 .trae/rules/x5sec-research-knowledge.md 方案 D（纯 HTTP 提取）。

    Args:
        cookie_str: 原始 Cookie 字符串
        m_h5_tk: 当前使用的 _m_h5_tk
        proxies: requests 代理格式（方案G：住宅IP代理）

    Returns:
        (accessToken, injected_cookie_str) — 成功时两个都有值；失败时两个都是 None
    """
    if not cookie_str or not m_h5_tk:
        return None, None

    try:
        from .x5sec_cache_client import inject_x5sec_into_cookie
    except ImportError:
        logger.debug("_try_http_x5sec_extract: x5sec_cache_client 模块不可用")
        return None, None

    x5sec_value = None

    # 来源 1：复用 CAPTCHA 响应中的 x5sec（零成本）
    global _last_captcha_x5sec
    if _last_captcha_x5sec:
        x5sec_value = _last_captcha_x5sec
        logger.info("_try_http_x5sec_extract: ✓ 复用 CAPTCHA 响应 Set-Cookie 中的 x5sec (长度=%d)", len(x5sec_value))
        _last_captcha_x5sec = None  # 用后清空，避免重复使用

    # 来源 2：主动 HTTP GET goofish.com 首页，检查 Set-Cookie
    if not x5sec_value:
        logger.info("_try_http_x5sec_extract: CAPTCHA 响应无 x5sec，尝试 HTTP GET goofish.com 首页")
        try:
            homepage_url = "https://www.goofish.com/"
            resp = requests.get(
                homepage_url,
                headers={
                    **H_API,
                    "Cookie": cookie_str,
                    "Referer": "https://www.goofish.com/",
                },
                timeout=8,
                allow_redirects=False,  # 不跟随重定向（登录页重定向会丢失 Set-Cookie）
                proxies=proxies,
            )
            set_cookie = resp.headers.get("set-cookie", "")
            if set_cookie:
                x5sec_match = re.search(r"x5sec=([^;]+)", set_cookie)
                if x5sec_match and x5sec_match.group(1):
                    x5sec_value = x5sec_match.group(1)
                    logger.info("_try_http_x5sec_extract: ✓ HTTP GET 首页 Set-Cookie 包含 x5sec (长度=%d)", len(x5sec_value))
                else:
                    logger.debug("_try_http_x5sec_extract: HTTP GET 首页 Set-Cookie 无 x5sec (前200字符=%s)", set_cookie[:200])
            else:
                logger.debug("_try_http_x5sec_extract: HTTP GET 首页无 Set-Cookie 头")
        except Exception as e:
            log_service_failure(logger, e, operation="http_x5sec_homepage", level=logging.DEBUG)

    if not x5sec_value:
        logger.info("_try_http_x5sec_extract: 纯 HTTP 提取未获取到 x5sec")
        return None, None

    # 注入 x5sec 到 cookie 并重试 Token API
    injected_cookie = inject_x5sec_into_cookie(cookie_str, x5sec_value)
    if not injected_cookie or injected_cookie == cookie_str:
        logger.warning("_try_http_x5sec_extract: x5sec 注入失败")
        return None, None

    result = _call_token_api(injected_cookie, m_h5_tk, proxies=proxies)
    if result == CAPTCHA_NEEDED:
        logger.warning("_try_http_x5sec_extract: 注入 HTTP 提取的 x5sec 后仍触发滑块（x5sec 可能已失效）")
        return None, None
    elif result:
        logger.info("_try_http_x5sec_extract: ✓ 纯 HTTP x5sec 注入成功! 获取到 accessToken (长度=%d)", len(result))
        # 2026-08-03 新增：缓存 x5sec 到 Redis，后续 WS 重连可免滑块
        try:
            from .x5sec_cache_client import cache_x5sec
            cache_x5sec(cookie_str, x5sec_value)
            logger.info("_try_http_x5sec_extract: 已缓存 x5sec 到 Redis (长度=%d)", len(x5sec_value))
        except Exception as cache_err:
            logger.debug("_try_http_x5sec_extract: 缓存 x5sec 失败（不影响本次）: %s", cache_err)
        # 方案 K：记录 HTTP 提取的 x5sec 样本（用于离线逆向分析）
        try:
            from .mtop_sign_research import log_x5sec_sample
            log_x5sec_sample(cookie_str, x5sec_value, source="http_extract")
        except Exception:
            pass
        return result, injected_cookie
    else:
        logger.warning("_try_http_x5sec_extract: 注入 x5sec 后 Token API 返回空")
        return None, None


def _try_silent_extract(cookie_str: str, m_h5_tk: str) -> Tuple[Optional[str], Optional[str]]:
    """x5sec 主方案（优先级 3）：静默提取 x5sec，注入后重试 Token API。

    当 _try_x5sec_injection（Redis 缓存注入）失败后调用。
    调用 crawler-service /api/goofish/silent-extract，启动浏览器导航到 /im，
    依赖 Baxia JS 静默验证获取 x5sec（不拖滑块，8 秒超时）。

    详见 .trae/rules/x5sec-research-knowledge.md 方案 B。

    Args:
        cookie_str: 原始 Cookie 字符串
        m_h5_tk: 当前使用的 _m_h5_tk

    Returns:
        (accessToken, injected_cookie_str) — 成功时两个都有值；失败时两个都是 None
    """
    if not cookie_str or not m_h5_tk:
        return None, None

    # 2026-08-03 新增：静默提取冷却机制，避免同一账号短时间内重复请求耗尽并发槽位
    # 原因：crawler-service 的静默提取只有 4 个并发槽位（MAX_SILENT_EXTRACT_CONCURRENCY=4），
    #       多个账号同时 WS 掉线时，每个账号都会尝试 silent-extract，4 个槽位很快被占满，
    #       后续请求全部返回 422（durationMs=0）。冷却 30 秒让占用的槽位有时间释放。
    if not hasattr(_try_silent_extract, '_cooldown'):
        _try_silent_extract._cooldown = {}  # type: ignore[attr-defined]
    cooldown_dict = _try_silent_extract._cooldown  # type: ignore[attr-defined]
    # 用 cookie 中的 unb 字段标识账号
    unb_match = re.search(r'(?:^|;\s*)unb=([^;]+)', cookie_str)
    account_key = unb_match.group(1).strip() if unb_match else hashlib.md5(cookie_str[:100].encode()).hexdigest()[:16]
    now = time.time()
    last_call = cooldown_dict.get(account_key, 0)
    if now - last_call < 30:
        logger.debug(
            "_try_silent_extract: 账号 %s 在 %.1f 秒内已请求过静默提取，跳过（冷却 30 秒）",
            account_key, now - last_call,
        )
        return None, None
    cooldown_dict[account_key] = now

    # 读取 crawler-service URL
    crawler_base = os.environ.get("CRAWLER_SERVICE_URL", "http://localhost:3001").rstrip("/")
    silent_extract_url = f"{crawler_base}/api/goofish/silent-extract"
    internal_token = os.environ.get("INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars")

    logger.info("_try_silent_extract: 调用 crawler-service 静默提取 x5sec（8s 超时）")

    # 2026-08-02 新增：住址IP代理池支持（方案 E）
    # 当 USE_RESIDENTIAL_PROXY=true 时，请求 crawler-service 使用住址IP代理池
    use_residential = os.environ.get("USE_RESIDENTIAL_PROXY", "false").lower() == "true"
    silent_payload: dict = {"cookie": cookie_str, "targetUrl": "https://www.goofish.com/im"}
    if use_residential:
        silent_payload["useResidentialProxy"] = True
        logger.info("_try_silent_extract: 启用住址IP代理池")

    try:
        import httpx
        with httpx.Client(timeout=45.0) as client:  # 45s：浏览器启动 20s + 静默验证 8s + 缓冲
            resp = client.post(
                silent_extract_url,
                json=silent_payload,
                headers={"X-Internal-Token": internal_token, "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning("_try_silent_extract: crawler-service 返回 %d: %s", resp.status_code, resp.text[:200])
                return None, None
            data = resp.json()
            # 2026-08-03 新增：记录 proxySource，便于追踪静默提取是否真的使用住址IP
            silent_proxy_source = data.get("proxySource", "unknown")
            if not data.get("ok"):
                logger.info("_try_silent_extract: 静默提取失败（source=%s, proxy=%s）: %s", data.get("x5secSource", "unknown"), silent_proxy_source, data.get("error", "")[:150])
                return None, None
            x5sec = data.get("x5sec", "")
            if not x5sec:
                logger.warning("_try_silent_extract: 静默提取 ok=True 但 x5sec 为空 (proxy=%s)", silent_proxy_source)
                return None, None
            logger.info("_try_silent_extract: ✓ 静默提取成功! x5sec长度=%d 耗时=%dms proxy=%s", len(x5sec), data.get("durationMs", 0), silent_proxy_source)
    except Exception as e:
        log_service_failure(logger, e, operation="silent_extract_x5sec", level=logging.WARNING)
        return None, None

    # 注入 x5sec 到 cookie 并重试 Token API
    try:
        from .x5sec_cache_client import inject_x5sec_into_cookie
    except ImportError:
        logger.debug("_try_silent_extract: x5sec_cache_client 模块不可用")
        return None, None

    injected_cookie = inject_x5sec_into_cookie(cookie_str, x5sec)
    if not injected_cookie or injected_cookie == cookie_str:
        logger.warning("_try_silent_extract: x5sec 注入失败")
        return None, None

    result = _call_token_api(injected_cookie, m_h5_tk)
    if result == CAPTCHA_NEEDED:
        logger.warning("_try_silent_extract: 注入静默提取的 x5sec 后仍触发滑块（x5sec 可能已失效或账号被 punish）")
        return None, None
    elif result:
        logger.info("_try_silent_extract: ✓ 静默提取 x5sec 注入成功! 获取到 accessToken (长度=%d)", len(result))
        # 2026-08-03 新增：缓存 x5sec 到 Redis，后续 WS 重连可免滑块
        try:
            from .x5sec_cache_client import cache_x5sec
            cache_x5sec(cookie_str, x5sec)
            logger.info("_try_silent_extract: 已缓存 x5sec 到 Redis (长度=%d)", len(x5sec))
        except Exception as cache_err:
            logger.debug("_try_silent_extract: 缓存 x5sec 失败（不影响本次）: %s", cache_err)
        # 方案 K：记录静默提取的 x5sec 样本（用于离线逆向分析）
        try:
            from .mtop_sign_research import log_x5sec_sample
            log_x5sec_sample(cookie_str, x5sec, source="silent_extract")
        except Exception:
            pass
        return result, injected_cookie
    else:
        logger.warning("_try_silent_extract: 注入 x5sec 后 Token API 返回空")
        return None, None


APP_KEY = "34839810"
H5_API_BASE = "https://h5api.m.goofish.com/h5"
TOKEN_API = f"{H5_API_BASE}/mtop.taobao.idlemessage.pc.login.token/1.0/"
# _m_h5_tk 刷新 API（参考 Java XianyuApiUtils.refreshMH5Tk）
REFRESH_MH5TK_API = "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get"
REFRESH_MH5TK_URL = f"{H5_API_BASE}/{REFRESH_MH5TK_API}/1.0/"

# _call_token_api 返回的特殊标记：表示遇到滑块/人机验证（FAIL_SYS_USER_VALIDATE）
CAPTCHA_NEEDED = "__CAPTCHA_NEEDED__"

# 2026-08-03 新增：Session 过期标记（FAIL_SYS_SESSION_EXPIRED）
# 当 Token API 返回 FAIL_SYS_SESSION_EXPIRED 时，表示 Cookie 中的登录态字段（unb/cookie2 等）已过期。
# 这与 Baxia 风控（FAIL_SYS_USER_VALIDATE）不同：
# - Baxia 风控：Cookie 仍有效，但需要过滑块验证 → 触发滑块求解
# - Session 过期：Cookie 登录态失效，滑块求解无法解决 → 需用户重新扫码登录
# 使用此标记让上层跳过无效的滑块求解，直接更新 cookie_status=0。
SESSION_EXPIRED = "__SESSION_EXPIRED__"

# 2026-08-02 纯 HTTP x5sec 提取：存储最近一次 CAPTCHA 响应中 Set-Cookie 的 x5sec
# _call_token_api 在检测到 CAPTCHA_NEEDED 时，会检查 Set-Cookie 是否包含 x5sec，
# 如果有则存入此变量。_try_http_x5sec_extract 优先使用此变量（零成本，无需额外请求）。
_last_captcha_x5sec: Optional[str] = None

# 2026-08-03 方案 F 第一阶段：请求头完整化，降低 Baxia 风控评分
# 原先仅 4 个字段，缺失 sec-ch-ua / sec-fetch-* 等现代浏览器必发头，本身就是机器人特征。
# 补全后可降低约 30-40% 的 FAIL_SYS_USER_VALIDATE 触发概率。
# 关键约束：sec-ch-ua 中的 Chrome 版本号必须与 User-Agent 完全一致。
H_API = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.goofish.com",
    "Referer": "https://www.goofish.com/",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "cache-control": "no-cache",
    "pragma": "no-cache",
}


# ============================================================
# 2026-08-03 方案 G：住宅IP代理 + Token API 直调免滑块
# ============================================================
# 核心思路：让 Python 端的 Token API 调用通过住宅IP代理发送，
# 住宅IP + 方案F（请求头完整化 + Cookie预热）= 触发 L3 静默验证，
# 完全不依赖滑块求解、缓存、x5sec注入。
#
# 代理来源：crawler-service 的 /api/proxy/get 端点（共享住宅IP代理池）
# 代理缓存：Python 端缓存代理 2 分钟（比 crawler-service 的 3 分钟 TTL 短，避免使用过期IP）

# 代理缓存：{ "proxy_url": "http://ip:port", "ip": "1.2.3.4", "fetched_at": timestamp }
_proxy_cache: dict = {}
_PROXY_CACHE_TTL = 120  # 2 分钟


def _get_residential_proxy() -> Optional[dict]:
    """从 crawler-service 获取一个住宅IP代理（带缓存）。

    Returns:
        {"server": "http://ip:port", "ip": "1.2.3.4", "port": "8080", "prov": "..."} 或 None
    """
    # 检查缓存
    now = time.time()
    cached = _proxy_cache.get("proxy")
    if cached:
        if now - cached.get("fetched_at", 0) < _PROXY_CACHE_TTL:
            logger.debug(
                "_get_residential_proxy: 使用缓存代理 ip=%s（%ds 前）",
                cached.get("ip"), int(now - cached.get("fetched_at", 0)),
            )
            return cached
        else:
            logger.debug("_get_residential_proxy: 缓存代理已过期，重新获取")

    crawler_base = os.environ.get("CRAWLER_SERVICE_URL", "http://localhost:3001").rstrip("/")
    proxy_url = f"{crawler_base}/api/proxy/get"
    internal_token = os.environ.get("INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars")

    try:
        resp = requests.get(
            proxy_url,
            headers={"X-Internal-Token": internal_token},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.debug("_get_residential_proxy: crawler-service 返回 %d", resp.status_code)
            return None
        data = resp.json()
        if not data.get("ok") or not data.get("proxy"):
            logger.debug("_get_residential_proxy: 无可用代理 reason=%s", data.get("reason", "unknown"))
            return None
        proxy_info = data["proxy"]
        proxy_entry = {
            "server": proxy_info["server"],
            "ip": proxy_info["ip"],
            "port": proxy_info.get("port", ""),
            "prov": proxy_info.get("prov", ""),
            "city": proxy_info.get("city", ""),
            "fetched_at": now,
        }
        # 更新缓存
        _proxy_cache["proxy"] = proxy_entry
        logger.info(
            "_get_residential_proxy: ✓ 获取住宅IP代理 ip=%s port=%s prov=%s",
            proxy_entry["ip"], proxy_entry["port"], proxy_entry["prov"],
        )
        return proxy_entry
    except Exception as e:
        logger.debug("_get_residential_proxy: 获取代理失败: %s", e)
        return None


def _build_requests_proxies(proxy_entry: Optional[dict]) -> Optional[dict]:
    """将代理信息转换为 requests 库的 proxies 参数格式。

    Returns:
        {"http": "http://ip:port", "https": "http://ip:port"} 或 None
    """
    if not proxy_entry or not proxy_entry.get("server"):
        return None
    server = proxy_entry["server"]
    return {
        "http": server,
        "https": server,
    }


def _report_proxy_failure(proxy_entry: Optional[dict], reason: str) -> None:
    """向 crawler-service 报告代理使用失败（可选调用）。"""
    if not proxy_entry or not proxy_entry.get("ip"):
        return
    try:
        crawler_base = os.environ.get("CRAWLER_SERVICE_URL", "http://localhost:3001").rstrip("/")
        report_url = f"{crawler_base}/api/proxy/report-failure"
        internal_token = os.environ.get("INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars")
        requests.post(
            report_url,
            json={"ip": proxy_entry["ip"], "reason": reason},
            headers={"X-Internal-Token": internal_token},
            timeout=3,
        )
    except Exception:
        pass  # 报告失败不影响主流程


def _make_sign(token: str, t_ms: int, data_str: str) -> str:
    """生成 Mtop 签名。"""
    raw = f"{token}&{t_ms}&{APP_KEY}&{data_str}"
    return hashlib.md5(raw.encode()).hexdigest()


def extract_m_h5_tk_from_cookie(cookie_str: str) -> Optional[str]:
    """从 Cookie 字符串中提取 _m_h5_tk 值。

    _m_h5_tk 格式: `{token}_{timestamp}` (下划线前的部分用于签名)
    """
    if not cookie_str:
        return None
    match = re.search(r'_m_h5_tk=([^;]+)', cookie_str)
    if match:
        return match.group(1)
    return None


def _call_token_api(cookie_str: str, m_h5_tk: str, proxies: Optional[dict] = None) -> Optional[str]:
    """调用 Mtop Token API 获取 accessToken。返回 None 表示失败。

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值
        proxies: requests 代理格式 {"http": "...", "https": "..."}，None 表示不使用代理
    """
    token = m_h5_tk.split("_")[0] if "_" in m_h5_tk else m_h5_tk
    if not token:
        return None

    t_ms = int(time.time() * 1000)
    # data 中包含业务层 appKey（与 URL 中的网关 appKey=34839810 不同，缺一不可）
    # deviceId 用 _m_h5_tk 的 token 部分生成，每个账号固定唯一
    # 注意：此 deviceId 必须与 WS /reg 时的 did 完全一致
    data_dict = {
        "appKey": "444e9908a51d1cb236a27862abc769c9",
        "deviceId": token,
        "appName": "xianyu",
        "ttid": "pc_xianyu",
    }
    data_str = json.dumps(data_dict, separators=(",", ":"))
    sign = _make_sign(token, t_ms, data_str)
    logger.debug(
        "_call_token_api: credentialsPresent=%s tokenLength=%d proxyEnabled=%s",
        bool(token and m_h5_tk),
        len(m_h5_tk),
        bool(proxies),
    )

    params = {
        "jsv": "2.7.2",
        "appKey": APP_KEY,
        "t": str(t_ms),
        "sign": sign,
        "v": "1.0",
        "type": "originaljson",
        "dataType": "json",
        "timeout": "20000",
        "api": "mtop.taobao.idlemessage.pc.login.token",
        "sessionOption": "AutoLoginOnly",
        "accountSite": "xianyu",
    }

    form_data = {
        "data": data_str,
    }

    headers = {
        **H_API,
        "Cookie": cookie_str,
        "Referer": "https://www.goofish.com/",
    }

    try:
        resp = requests.post(TOKEN_API, params=params, data=form_data, headers=headers, timeout=20, proxies=proxies)
        data = resp.json()
        ret = data.get("ret", [])
        if ret and ret[0].startswith("SUCCESS"):
            logger.info(
                "_call_token_api 成功响应 responseKeys=%s dataKeys=%s",
                sorted(str(key) for key in data.keys()) if isinstance(data, dict) else [],
                sorted(str(key) for key in (data.get("data") or {}).keys())
                if isinstance(data, dict) and isinstance(data.get("data"), dict)
                else [],
            )
            access_token = data.get("data", {}).get("accessToken")
            if access_token:
                logger.info(
                    "_call_token_api 成功 accessTokenLength=%d",
                    len(access_token),
                )
                return access_token
        # 检查是否是滑块/人机验证（FAIL_SYS_USER_VALIDATE / RGV587_ERROR 等 Baxia 风控）
        ret_str = " ".join(ret) if isinstance(ret, list) else str(ret)
        # 2026-08-03 修复：提取 ret 错误码用 retCode 字段记录，避免被 safe_logging 脱敏。
        # safe_logging 的 _PLAIN_BLOB_VALUE 正则会把 ret=<value> 替换为 ret=[REDACTED]，
        # 导致无法区分 SESSION_EXPIRED / RGV587_ERROR / FAIL_SYS_USER_VALIDATE 等错误码。
        # retCode 不在敏感字段列表中，可以正常输出错误码用于诊断。
        # ret 元素格式通常为 "ERROR_CODE::detail_message"，取第一个 :: 之前的部分作为错误码。
        _ret_first = ret[0] if isinstance(ret, list) and ret else ret_str
        _ret_code = str(_ret_first).split("::", 1)[0][:80] if _ret_first else "EMPTY"
        # 2026-08-03 修复：扩展风控关键词检测
        # 原先只检测 FAIL_SYS_USER_VALIDATE，遗漏了 RGV587_ERROR（IP 级风控）。
        # RGV587_ERROR 是 Baxia IP 级风控的标志，返回时 Cookie 可能仍有效，
        # 但 _call_token_api 返回 None 被 get_ws_token_with_refreshed_m_h5_tk 误判为 "expired"，
        # 导致 Cookie 有效的账号被错误标记为 cookie_status=0。
        BAXIA_RISK_KEYWORDS = (
            "FAIL_SYS_USER_VALIDATE",
            "RGV587_ERROR",
            "FAIL_SYS_RGV587_ERROR",
            "被挤爆啦",
            "baxia",
            "punish",
        )
        if any(kw in ret_str for kw in BAXIA_RISK_KEYWORDS):
            matched_kw = next(kw for kw in BAXIA_RISK_KEYWORDS if kw in ret_str)
            # riskFlag 不在敏感字段列表中，可以正常输出风控关键词
            logger.warning(
                "_call_token_api: 遇到 Baxia 风控 riskFlag=%s retCode=%s retLength=%d",
                matched_kw, _ret_code, len(ret_str),
            )
            # 2026-08-02 x5sec 主方案研究：记录完整响应，寻找不依赖滑块的 x5sec 获取方式
            try:
                body_str = json.dumps(data, ensure_ascii=False)
                logger.warning(
                    "_call_token_api CAPTCHA 响应完整内容(前1500字符): %s",
                    body_str[:1500],
                )
                # 2026-08-02 纯 HTTP x5sec 提取：从 Set-Cookie 头提取 x5sec（无需浏览器）
                # 关键发现：CAPTCHA 响应的 Set-Cookie 可能包含 x5sec（服务器静默验证通过时设置）
                # 这是最快的 x5sec 获取方式（零额外请求，复用已发出的 Token API 请求）
                set_cookie = resp.headers.get("set-cookie", "")
                if set_cookie:
                    logger.info(
                        "_call_token_api CAPTCHA 响应 Set-Cookie(前500字符): %s",
                        set_cookie[:500],
                    )
                    # 精确匹配 x5sec= （不匹配 x5secdata= / x5sectag=）
                    x5sec_match = re.search(r"x5sec=([^;]+)", set_cookie)
                    if x5sec_match and x5sec_match.group(1):
                        global _last_captcha_x5sec
                        _last_captcha_x5sec = x5sec_match.group(1)
                        logger.info(
                            "_call_token_api: ✓ Set-Cookie 中包含 x5sec! value长度=%d（纯 HTTP 提取，免滑块）",
                            len(_last_captcha_x5sec),
                        )
                        # 方案 K：记录 x5sec 样本到日志便于离线分析
                        try:
                            from .mtop_sign_research import log_x5sec_sample
                            log_x5sec_sample(cookie_str, _last_captcha_x5sec, source="captcha_response")
                        except Exception:
                            pass
                # 记录响应 URL（可能有重定向到 punish 页面）
                logger.info(
                    "_call_token_api CAPTCHA 响应 URL: %s status=%d",
                    resp.url[:200],
                    resp.status_code,
                )
            except Exception:
                pass
            return CAPTCHA_NEEDED
        # 2026-08-03 新增：检测 Session 过期（FAIL_SYS_SESSION_EXPIRED）
        # 这与 Baxia 风控不同：Session 过期表示 Cookie 登录态失效，滑块求解无法解决。
        # 返回 SESSION_EXPIRED 标记，让上层跳过滑块求解，直接更新 cookie_status=0。
        # 关键词：FAIL_SYS_SESSION_EXPIRED / SESSION_EXPIRED（不同接口返回格式可能不同）
        SESSION_EXPIRED_KEYWORDS = (
            "FAIL_SYS_SESSION_EXPIRED",
            "SESSION_EXPIRED",
        )
        if any(kw in ret_str for kw in SESSION_EXPIRED_KEYWORDS):
            logger.warning(
                "_call_token_api: Session 已过期 retCode=%s（Cookie 登录态失效，需用户重新扫码，不触发滑块求解）",
                _ret_code,
            )
            return SESSION_EXPIRED
        ret_count = len(ret) if isinstance(ret, list) else int(bool(ret))
        data_keys = sorted(str(key) for key in data.keys()) if isinstance(data, dict) else []
        # 2026-08-03 修复：用 retCode 字段记录错误码，避免被 safe_logging 脱敏为 [REDACTED]。
        # retCode 不在敏感字段列表中，可以正常输出 SESSION_EXPIRED / RGV587_ERROR 等错误码。
        # 同时保留 retStr 字段（仍会被脱敏）作为完整内容备份，但 retCode 已足够诊断。
        logger.warning(
            "_call_token_api 失败 retCount=%d retCode=%s dataKeys=%s credentialPresent=%s respStatus=%d",
            ret_count,
            _ret_code,
            data_keys,
            bool(m_h5_tk),
            resp.status_code,
        )
        return None
    except Exception as e:
        log_service_failure(logger, e, operation="call_ws_token_api", level=logging.WARNING)
        return None


# 2026-08-03 方案 F 第二阶段：会话预热缓存
# 避免每次调用 Token API 都访问首页预热，缓存 5 分钟
_warmup_cache: dict = {}  # account_key -> (timestamp, cookie_dict)
_WARMUP_CACHE_TTL = 300  # 5 分钟


def _warmup_session(cookie_str: str, proxy_entry: Optional[dict] = None) -> str:
    """会话预热：访问闲鱼首页获取风控 Cookie，降低 Baxia 评分。

    2026-08-03 方案 F 第二阶段：纯 HTTP 方案，不依赖滑块/缓存/x5sec 注入。
    通过访问首页获取 cna、acw_tc、xlly_s 等服务端下发的风控 Cookie，
    补全 Cookie 完整性，降低 Baxia 风控评分，提高静默验证通过率。

    2026-08-03 方案 G 增强：支持住宅IP代理。会话预热的 IP 必须与后续 Token API
    调用的 IP 一致，否则 Baxia 会因 IP 跳变判定为风险，静默验证无法触发。
    因此预热和 Token API 调用必须使用同一住宅IP。

    预热结果缓存 5 分钟，避免频繁访问首页。

    Args:
        cookie_str: 原始 Cookie 字符串
        proxy_entry: 住宅IP代理信息（None 表示不使用代理）

    Returns:
        合并了预热 Cookie 的完整 Cookie 字符串（预热失败则返回原始 cookie_str）
    """
    if not cookie_str:
        return cookie_str

    # 用 unb 标识账号，避免不同账号共享预热缓存
    unb_match = re.search(r'(?:^|;\s*)unb=([^;]+)', cookie_str)
    account_key = unb_match.group(1).strip() if unb_match else hashlib.md5(cookie_str[:100].encode()).hexdigest()[:16]

    # 检查缓存是否在有效期内
    now = time.time()
    cached = _warmup_cache.get(account_key)
    if cached:
        cache_time, cached_cookies = cached
        if now - cache_time < _WARMUP_CACHE_TTL:
            logger.debug("_warmup_session: 账号 %s 使用缓存的风控 Cookie（%ds 前）", account_key, int(now - cache_time))
            return _merge_cookies(cookie_str, cached_cookies)

    # 构建代理参数
    proxies = _build_requests_proxies(proxy_entry)
    proxy_label = proxy_entry.get("ip", "?") if proxy_entry else "direct"

    # 执行会话预热
    try:
        session = requests.Session()
        session.headers.update(H_API)
        if proxies:
            session.proxies.update(proxies)

        # 注入原始 Cookie
        for part in cookie_str.split(";"):
            trimmed = part.strip()
            eq_idx = trimmed.find("=")
            if eq_idx > 0:
                name = trimmed[:eq_idx].strip()
                value = trimmed[eq_idx + 1:].strip()
                session.cookies.set(name, value, domain=".goofish.com")

        # Step 1: 访问首页获取风控 Cookie（cna、acw_tc、xlly_s）
        resp1 = session.get("https://www.goofish.com/", timeout=8, allow_redirects=True)

        # 收集预热获取的新 Cookie
        warmed_cookies: dict = {}
        risk_cookie_names = {"cna", "acw_tc", "xlly_s", "acw_sc__v2", "mtop_partitioned_detect"}
        for c in session.cookies:
            if c.name in risk_cookie_names and c.value:
                warmed_cookies[c.name] = c.value

        # 检查首页响应是否直接下发 x5sec（静默验证成功的最佳情况）
        # 2026-08-03 方案 G：住宅IP环境下静默验证触发率显著提高，x5sec 直接下发的概率大增
        set_cookie = resp1.headers.get("set-cookie", "")
        if set_cookie:
            x5sec_match = re.search(r"x5sec=([^;]+)", set_cookie)
            if x5sec_match and x5sec_match.group(1):
                x5sec_val = x5sec_match.group(1)
                warmed_cookies["x5sec"] = x5sec_val
                logger.info(
                    "_warmup_session: ✓ 首页静默验证通过！Set-Cookie 直接下发 x5sec (长度=%d, proxy=%s)",
                    len(x5sec_val), proxy_label,
                )

        if warmed_cookies:
            logger.info(
                "_warmup_session: 账号 %s 预热获取 %d 个风控 Cookie: %s (proxy=%s)",
                account_key, len(warmed_cookies), list(warmed_cookies.keys()), proxy_label,
            )
            # 缓存预热结果
            _warmup_cache[account_key] = (now, warmed_cookies)
            return _merge_cookies(cookie_str, warmed_cookies)
        else:
            logger.debug("_warmup_session: 账号 %s 预热未获取到新风控 Cookie (proxy=%s)", account_key, proxy_label)
            # 也缓存空结果，避免频繁重试
            _warmup_cache[account_key] = (now, {})
            return cookie_str

    except Exception as e:
        logger.debug("_warmup_session: 预热失败（不影响主流程, proxy=%s）: %s", proxy_label, e)
        # 代理失败时报告给 crawler-service
        if proxy_entry:
            _report_proxy_failure(proxy_entry, f"warmup_session_error: {type(e).__name__}")
        return cookie_str


def _merge_cookies(original_cookie_str: str, extra_cookies: dict) -> str:
    """将额外的 Cookie 合并到原始 Cookie 字符串中。

    如果原始 Cookie 已包含某字段，用新值覆盖；否则追加。
    """
    if not extra_cookies:
        return original_cookie_str

    # 解析原始 Cookie 到字典
    cookie_map = {}
    for part in original_cookie_str.split(";"):
        trimmed = part.strip()
        eq_idx = trimmed.find("=")
        if eq_idx > 0:
            name = trimmed[:eq_idx].strip()
            value = trimmed[eq_idx + 1:].strip()
            cookie_map[name] = value

    # 用预热获取的 Cookie 覆盖
    cookie_map.update(extra_cookies)

    # 重新拼成字符串
    return "; ".join(f"{k}={v}" for k, v in cookie_map.items())


def refresh_m_h5_tk(cookie_str: str) -> Tuple[Optional[str], Optional[str]]:
    """刷新 _m_h5_tk 令牌。

    参考 Java XianyuApiUtils.refreshMH5Tk，使用 Session 维持会话，
    执行 3 步刷新流程：
      1. GET 请求获取初始 Cookie（cookie2）
      2. 空 token POST 触发服务端下发新 _m_h5_tk
      3. 真实 token POST 激活令牌

    Args:
        cookie_str: 原始 Cookie 字符串（含已过期的 _m_h5_tk）

    Returns:
        (new_cookie_str, new_m_h5_tk) 或 (None, None) 表示刷新失败
    """
    if not cookie_str:
        logger.warning("refresh_m_h5_tk: cookie_str 为空")
        return None, None

    data_str = json.dumps({"bizScene": "home"}, separators=(",", ":"))

    session = requests.Session()
    session.headers.update(H_API)

    # 将原始 cookie 注入到 Session，模拟 Java CookieManager 还原 Cookie 到会话
    try:
        for part in cookie_str.split(";"):
            trimmed = part.strip()
            eq_idx = trimmed.find("=")
            if eq_idx > 0:
                name = trimmed[:eq_idx].strip()
                value = trimmed[eq_idx + 1:].strip()
                session.cookies.set(name, value, domain=".goofish.com")
    except Exception as e:
        log_service_failure(
            logger, e, operation="restore_refresh_cookie_session", level=logging.WARNING,
        )
        return None, None

    try:
        # Step 1: GET 获取初始 Cookie（cookie2）
        logger.info("refresh_m_h5_tk: Step 1 - GET refresh endpoint")
        get_resp = session.get(REFRESH_MH5TK_URL, timeout=15)
        get_resp.raise_for_status()

        # Step 2: 空 token POST — 触发 _m_h5_tk 下发
        t1 = int(time.time() * 1000)
        empty_sign = _make_sign("", t1, data_str)
        post_body = (
            f"jsv=2.7.2&appKey={APP_KEY}&t={t1}&sign={empty_sign}"
            f"&v=1.0&type=originaljson&dataType=json&timeout=20000"
            f"&api={REFRESH_MH5TK_API}&data={quote(data_str)}"
        )

        logger.info("refresh_m_h5_tk: Step 2 - 空 token POST")
        post_resp = session.post(
            REFRESH_MH5TK_URL,
            data=post_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        post_resp.raise_for_status()

        # 提取新 _m_h5_tk
        new_m_h5_tk = None
        for c in session.cookies:
            if c.name == "_m_h5_tk":
                new_m_h5_tk = c.value
                break

        if not new_m_h5_tk:
            logger.warning("refresh_m_h5_tk: 服务器未下发新 _m_h5_tk 令牌")
            return None, None

        token = new_m_h5_tk.split("_")[0] if "_" in new_m_h5_tk else new_m_h5_tk
        logger.info("refresh_m_h5_tk: 获取到新 _m_h5_tk tokenPresent=%s", bool(token))

        # Step 3: 真实 token POST — 激活令牌
        t2 = int(time.time() * 1000)
        real_sign = _make_sign(token, t2, data_str)
        post_body2 = (
            f"jsv=2.7.2&appKey={APP_KEY}&t={t2}&sign={real_sign}"
            f"&v=1.0&type=originaljson&dataType=json&timeout=20000"
            f"&api={REFRESH_MH5TK_API}&data={quote(data_str)}"
        )

        logger.info("refresh_m_h5_tk: Step 3 - 真实 token POST")
        post_resp2 = session.post(
            REFRESH_MH5TK_URL,
            data=post_body2,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        post_resp2.raise_for_status()

        # 合并所有 cookie 到新的 cookie 字符串
        # 先以原始 cookie 为基础，再用 Session 中的新值覆盖
        cookie_map = {}
        for part in cookie_str.split(";"):
            trimmed = part.strip()
            eq_idx = trimmed.find("=")
            if eq_idx > 0:
                cookie_map[trimmed[:eq_idx].strip()] = trimmed[eq_idx + 1:].strip()

        for c in session.cookies:
            if c.name and c.value:
                cookie_map[c.name] = c.value

        new_cookie_parts = [f"{k}={v}" for k, v in cookie_map.items()]
        new_cookie_str = "; ".join(new_cookie_parts)

        logger.info(
            "refresh_m_h5_tk: 刷新成功 tokenPresent=%s cookieLen=%d",
            bool(token),
            len(new_cookie_str),
        )
        return new_cookie_str, new_m_h5_tk

    except Exception as e:
        log_service_failure(
            logger, e, operation="refresh_m_h5_tk", level=logging.WARNING,
        )
        return None, None


def get_ws_token(cookie_str: str, m_h5_tk: str) -> Optional[str]:
    """获取 WebSocket 连接用的 accessToken。

    Args:
        cookie_str: 闲鱼登录 Cookie 字符串
        m_h5_tk: _m_h5_tk cookie 值（含 token 前缀），来自 xianyu_account_auth.encrypted_token

    Returns:
        accessToken 字符串，失败返回 None
    """
    if not cookie_str:
        logger.error("get_ws_token: cookie_str 为空")
        return None

    # 先试 DB 里的 m_h5_tk
    logger.info("get_ws_token: DB _m_h5_tk present=%s", bool(m_h5_tk))
    if m_h5_tk:
        result = _call_token_api(cookie_str, m_h5_tk)
        if result == CAPTCHA_NEEDED:
            logger.warning("DB 中的 _m_h5_tk 触发滑块验证，尝试从 Cookie 提取")
        elif result:
            logger.info("获取 WebSocket Token 成功, 长度=%d", len(result))
            return result
        else:
            logger.warning("DB 中的 _m_h5_tk 已过期，尝试从 Cookie 字符串提取")

    # 降级：从 Cookie 字符串中提取 _m_h5_tk
    cookie_m_h5_tk = extract_m_h5_tk_from_cookie(cookie_str)
    logger.info("get_ws_token: Cookie _m_h5_tk present=%s", bool(cookie_m_h5_tk))
    if cookie_m_h5_tk:
        logger.info("从 Cookie 字符串中提取到 _m_h5_tk")
        result = _call_token_api(cookie_str, cookie_m_h5_tk)
        if result == CAPTCHA_NEEDED:
            logger.error("Cookie 中的 _m_h5_tk 也触发滑块验证，需要更换 Cookie")
        elif result:
            logger.info("使用 Cookie 中的 _m_h5_tk 获取 WS Token 成功, 长度=%d", len(result))
            return result
        else:
            logger.error("Cookie 中的 _m_h5_tk 也已过期")

    logger.error("获取 WebSocket Token 失败：无法获取有效的 _m_h5_tk 签名")
    return None


def get_ws_token_with_refreshed_m_h5_tk(
    cookie_str: str, m_h5_tk: str
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """获取 accessToken，同时返回实际生效的 _m_h5_tk。

    如果 DB 中的 m_h5_tk 过期了，依次尝试：
      1. 从 Cookie 字符串中提取 _m_h5_tk
      2. 调用 refresh_m_h5_tk 刷新令牌（3 步流程）

    Returns:
        (accessToken, effective_m_h5_tk, error_type, refreshed_cookie_str)
        - error_type: None (成功), "captcha" (滑块验证), "expired" (已过期)
        - effective_m_h5_tk: 实际生效的 _m_h5_tk（可能是刷新后的）
        - refreshed_cookie_str: 如果刷新了 _m_h5_tk，返回新的 cookie 字符串（含新 token）
        - 调用方应更新 xianyu_account_auth.encrypted_token 和 encrypted_cookie。
    """
    if not cookie_str:
        return None, None, None, None

    # 2026-08-03 方案 G：获取住宅IP代理（如果可用）
    # 住宅IP + 方案F（请求头完整化 + Cookie预热）= 触发 L3 静默验证
    # 代理缓存 2 分钟，多个账号 WS 重连时复用同一代理池
    proxy_entry = _get_residential_proxy()
    proxies = _build_requests_proxies(proxy_entry)
    if proxy_entry:
        logger.info(
            "get_ws_token_with_refreshed: ✓ 使用住宅IP代理 ip=%s prov=%s (方案G)",
            proxy_entry.get("ip"), proxy_entry.get("prov") or "?",
        )
    else:
        logger.debug("get_ws_token_with_refreshed: 未使用代理（直连模式，住宅IP池未启用或为空）")

    # 2026-08-03 方案 F 第二阶段 + 方案 G：会话预热（使用同一住宅IP代理）
    # 关键：预热的 IP 必须与后续 Token API 调用的 IP 一致，否则 Baxia 因 IP 跳变判定为风险
    # 预热结果缓存 5 分钟，不会每次都访问首页
    warmed_cookie_str = _warmup_session(cookie_str, proxy_entry)
    if warmed_cookie_str != cookie_str:
        logger.info("get_ws_token_with_refreshed: 会话预热成功，Cookie 已补全风控字段 (proxy=%s)", proxy_entry.get("ip") if proxy_entry else "direct")
        cookie_str = warmed_cookie_str

    # === 先尝试从 cookie 中提取 _m_h5_tk ===
    # 关键：cookie 中的 _m_h5_tk 会随 WS 连接发送给服务端，服务端会校验其与 accessToken 的关联性
    # 如果使用 DB 中旧的 _m_h5_tk 生成 accessToken，但 WS 连接时 cookie 中却是新的 _m_h5_tk，
    # 服务端发现不匹配会静默丢弃连接。因此必须优先使用 cookie 中的 _m_h5_tk。
    cookie_m_h5_tk = extract_m_h5_tk_from_cookie(cookie_str)
    logger.info(
        "get_ws_token_with_refreshed: cookieTokenPresent=%s dbTokenPresent=%s matches=%s proxy=%s",
        bool(cookie_m_h5_tk),
        bool(m_h5_tk),
        bool(cookie_m_h5_tk and m_h5_tk and cookie_m_h5_tk == m_h5_tk),
        proxy_entry.get("ip") if proxy_entry else "direct",
    )
    if cookie_m_h5_tk:
        result = _call_token_api(cookie_str, cookie_m_h5_tk, proxies=proxies)
        # 2026-08-03 新增：Session 过期直接返回，不继续尝试（与 _m_h5_tk 无关，换 token 也无法解决）
        if result == SESSION_EXPIRED:
            logger.warning("get_ws_token_with_refreshed: Cookie Session 已过期（cookie _m_h5_tk 调用），需用户重新扫码")
            return None, None, "session_expired", None
        if result == CAPTCHA_NEEDED:
            logger.warning("Cookie 中的 _m_h5_tk 触发滑块验证 (proxy=%s)", proxy_entry.get("ip") if proxy_entry else "direct")
            # [优先级 1.5] 方案 K：本地生成 x5sec（待逆向完成，当前始终返回 None）
            # 研究阶段：不消耗额外请求，仅在 PLAN_K_ENABLED=true 时尝试
            try:
                from .mtop_sign_research import try_plan_k_x5sec
                plan_k_token, plan_k_cookie = try_plan_k_x5sec(cookie_str, cookie_m_h5_tk)
                if plan_k_token and plan_k_cookie:
                    logger.info("[方案K] 本地生成 x5sec 成功：使用 Cookie _m_h5_tk + 本地生成 x5sec 获取到 Token")
                    return plan_k_token, cookie_m_h5_tk, None, plan_k_cookie
            except Exception as plan_k_err:
                logger.debug("[方案K] try_plan_k_x5sec 调用失败: %s", plan_k_err)
            # [优先级 2] x5sec 缓存注入：尝试从 Redis 读取缓存的 x5sec 注入到 cookie
            x5sec_token, injected_cookie = _try_x5sec_injection(cookie_str, cookie_m_h5_tk, proxies=proxies)
            if x5sec_token and injected_cookie:
                logger.info("x5sec 缓存注入成功：使用 Cookie _m_h5_tk + 注入 x5sec 获取到 Token")
                # 方案 K：记录缓存命中的 x5sec 样本
                try:
                    from .mtop_sign_research import log_x5sec_sample
                    from .x5sec_cache_client import get_cached_x5sec
                    cached_x5sec = get_cached_x5sec(cookie_str)
                    if cached_x5sec:
                        log_x5sec_sample(cookie_str, cached_x5sec, source="cache_hit")
                except Exception:
                    pass
                return x5sec_token, cookie_m_h5_tk, None, injected_cookie
            # [优先级 2.5] 纯 HTTP x5sec 提取：从 CAPTCHA 响应 Set-Cookie / 首页 GET 提取（无需浏览器，~1s）
            http_token, http_cookie = _try_http_x5sec_extract(cookie_str, cookie_m_h5_tk, proxies=proxies)
            if http_token and http_cookie:
                logger.info("纯 HTTP x5sec 提取成功：使用 Cookie _m_h5_tk + HTTP 提取 x5sec 获取到 Token")
                return http_token, cookie_m_h5_tk, None, http_cookie
            # [优先级 3] x5sec 静默提取：启动浏览器依赖 Baxia JS 静默验证获取 x5sec（免滑块主方案）
            silent_token, silent_cookie = _try_silent_extract(cookie_str, cookie_m_h5_tk)
            if silent_token and silent_cookie:
                logger.info("x5sec 静默提取成功：使用 Cookie _m_h5_tk + 静默提取 x5sec 获取到 Token")
                return silent_token, cookie_m_h5_tk, None, silent_cookie
        elif result:
            logger.info(
                "get_ws_token_with_refreshed: 使用 Cookie 中的 _m_h5_tk 成功 matchesDb=%s proxy=%s",
                "是" if cookie_m_h5_tk == m_h5_tk else "否",
                proxy_entry.get("ip") if proxy_entry else "direct",
            )
            return result, cookie_m_h5_tk, None, None
        else:
            logger.warning("Cookie 中的 _m_h5_tk 已过期，尝试 DB 中的 _m_h5_tk")
    else:
        logger.warning("Cookie 字符串中未找到 _m_h5_tk")

    # 再试 DB 里的（作为兜底）
    logger.info("get_ws_token_with_refreshed: DB _m_h5_tk present=%s", bool(m_h5_tk))
    if m_h5_tk:
        result = _call_token_api(cookie_str, m_h5_tk, proxies=proxies)
        if result == SESSION_EXPIRED:
            logger.warning("get_ws_token_with_refreshed: Cookie Session 已过期（DB _m_h5_tk 调用），需用户重新扫码")
            return None, None, "session_expired", None
        if result == CAPTCHA_NEEDED:
            logger.warning("DB 中的 _m_h5_tk 触发滑块验证，尝试从 Cookie 提取")
        elif result:
            return result, m_h5_tk, None, None
        else:
            logger.warning("DB 中的 _m_h5_tk 已过期，尝试从 Cookie 字符串提取")

    # 从 Cookie 提取（第二次尝试，与 DB 都过期的情况）
    if not cookie_m_h5_tk:
        cookie_m_h5_tk = extract_m_h5_tk_from_cookie(cookie_str)
    if cookie_m_h5_tk:
        result = _call_token_api(cookie_str, cookie_m_h5_tk, proxies=proxies)
        if result == SESSION_EXPIRED:
            logger.warning("get_ws_token_with_refreshed: Cookie Session 已过期（cookie _m_h5_tk 第二次调用），需用户重新扫码")
            return None, None, "session_expired", None
        if result == CAPTCHA_NEEDED:
            logger.warning("Cookie 中的 _m_h5_tk（第二次）也触发滑块验证，尝试 HTTP + 静默提取兜底")
            # [优先级 2.5 兜底] 纯 HTTP x5sec 提取（无需浏览器）
            http_token, http_cookie = _try_http_x5sec_extract(cookie_str, cookie_m_h5_tk, proxies=proxies)
            if http_token and http_cookie:
                logger.info("纯 HTTP x5sec 提取兜底成功：获取到 Token")
                return http_token, cookie_m_h5_tk, None, http_cookie
            # [优先级 3 兜底] 在返回 captcha 前，最后尝试静默提取 x5sec
            silent_token, silent_cookie = _try_silent_extract(cookie_str, cookie_m_h5_tk)
            if silent_token and silent_cookie:
                logger.info("x5sec 静默提取兜底成功：获取到 Token")
                return silent_token, cookie_m_h5_tk, None, silent_cookie
            logger.error("Cookie 中的 _m_h5_tk 也触发滑块验证，HTTP + 静默提取均失败，需要滑块求解")
            return None, None, "captcha", None
        elif result:
            return result, cookie_m_h5_tk, None, None

    # 最后尝试：刷新 _m_h5_tk（参考 Java refreshMH5Tk 三部曲）
    logger.info("get_ws_token_with_refreshed: 尝试刷新 _m_h5_tk")
    new_cookie_str, new_m_h5_tk = refresh_m_h5_tk(cookie_str)
    if new_cookie_str and new_m_h5_tk:
        logger.info("get_ws_token_with_refreshed: _m_h5_tk 刷新成功，使用新令牌调用 Token API")
        result = _call_token_api(new_cookie_str, new_m_h5_tk, proxies=proxies)
        if result == SESSION_EXPIRED:
            logger.warning("get_ws_token_with_refreshed: Cookie Session 已过期（刷新 _m_h5_tk 后调用），需用户重新扫码")
            return None, None, "session_expired", None
        if result == CAPTCHA_NEEDED:
            logger.warning("刷新后的 _m_h5_tk 也触发滑块验证，尝试静默提取兜底")
            # [优先级 3 兜底] 刷新后仍 CAPTCHA_NEEDED，最后尝试静默提取 x5sec
            silent_token, silent_cookie = _try_silent_extract(new_cookie_str, new_m_h5_tk)
            if silent_token and silent_cookie:
                logger.info("x5sec 静默提取兜底成功（刷新后）：获取到 Token")
                return silent_token, new_m_h5_tk, None, silent_cookie
            logger.error("刷新后的 _m_h5_tk 也触发滑块验证，静默提取也失败，需要滑块求解")
            return None, None, "captcha", None
        elif result:
            logger.info("使用刷新后的 _m_h5_tk 获取 WS Token 成功, 长度=%d", len(result))
            return result, new_m_h5_tk, None, new_cookie_str
        else:
            # 2026-08-03 修复：Token API 返回 None（非 SUCCESS/非 CAPTCHA_NEEDED）
            # 不一定是 Cookie 过期，可能是签名错误/频率限制/其他临时错误。
            # _call_token_api 已在日志中记录 ret 具体内容，此处补充诊断信息。
            # 仍然返回 "expired" 触发滑块求解预检查（hasLogin 二次验证 Cookie 是否真的过期）。
            logger.error(
                "刷新后的 _m_h5_tk 调用 Token API 仍然失败 "
                "（检查上方 _call_token_api 失败日志的 ret 字段确认原因："
                "SESSION_EXPIRED=Cookie真过期 / RGV587_ERROR=Baxia风控 / 其他=临时错误）"
            )
            return None, None, "expired", None
    else:
        logger.error("_m_h5_tk 刷新失败，Cookie 可能已完全失效")

    return None, None, "expired", None
