"""
WebSocket Token 获取模块。
通过闲鱼 H5 API 获取 WebSocket 连接所需的 accessToken。
"""
import hashlib
import json
import logging
import re
import time
from typing import Optional, Tuple
from urllib.parse import quote

import requests

from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

APP_KEY = "34839810"
H5_API_BASE = "https://h5api.m.goofish.com/h5"
TOKEN_API = f"{H5_API_BASE}/mtop.taobao.idlemessage.pc.login.token/1.0/"
# _m_h5_tk 刷新 API（参考 Java XianyuApiUtils.refreshMH5Tk）
REFRESH_MH5TK_API = "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get"
REFRESH_MH5TK_URL = f"{H5_API_BASE}/{REFRESH_MH5TK_API}/1.0/"

# _call_token_api 返回的特殊标记：表示遇到滑块/人机验证（FAIL_SYS_USER_VALIDATE）
CAPTCHA_NEEDED = "__CAPTCHA_NEEDED__"

H_API = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
}


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


def _call_token_api(cookie_str: str, m_h5_tk: str) -> Optional[str]:
    """调用 Mtop Token API 获取 accessToken。返回 None 表示失败。"""
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
        "_call_token_api: credentialsPresent=%s tokenLength=%d",
        bool(token and m_h5_tk),
        len(m_h5_tk),
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
        resp = requests.post(TOKEN_API, params=params, data=form_data, headers=headers, timeout=20)
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
        # 检查是否是滑块/人机验证（FAIL_SYS_USER_VALIDATE）
        ret_str = " ".join(ret) if isinstance(ret, list) else str(ret)
        if "FAIL_SYS_USER_VALIDATE" in ret_str:
            logger.warning("_call_token_api: 遇到滑块/人机验证")
            return CAPTCHA_NEEDED
        ret_count = len(ret) if isinstance(ret, list) else int(bool(ret))
        data_keys = sorted(str(key) for key in data.keys()) if isinstance(data, dict) else []
        logger.warning(
            "_call_token_api 失败 retCount=%d dataKeys=%s credentialPresent=%s",
            ret_count,
            data_keys,
            bool(m_h5_tk),
        )
        return None
    except Exception as e:
        log_service_failure(logger, e, operation="call_ws_token_api", level=logging.WARNING)
        return None


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

    # === 先尝试从 cookie 中提取 _m_h5_tk ===
    # 关键：cookie 中的 _m_h5_tk 会随 WS 连接发送给服务端，服务端会校验其与 accessToken 的关联性
    # 如果使用 DB 中旧的 _m_h5_tk 生成 accessToken，但 WS 连接时 cookie 中却是新的 _m_h5_tk，
    # 服务端发现不匹配会静默丢弃连接。因此必须优先使用 cookie 中的 _m_h5_tk。
    cookie_m_h5_tk = extract_m_h5_tk_from_cookie(cookie_str)
    logger.info(
        "get_ws_token_with_refreshed: cookieTokenPresent=%s dbTokenPresent=%s matches=%s",
        bool(cookie_m_h5_tk),
        bool(m_h5_tk),
        bool(cookie_m_h5_tk and m_h5_tk and cookie_m_h5_tk == m_h5_tk),
    )
    if cookie_m_h5_tk:
        result = _call_token_api(cookie_str, cookie_m_h5_tk)
        if result == CAPTCHA_NEEDED:
            logger.warning("Cookie 中的 _m_h5_tk 触发滑块验证")
        elif result:
            logger.info(
                "get_ws_token_with_refreshed: 使用 Cookie 中的 _m_h5_tk 成功 matchesDb=%s",
                "是" if cookie_m_h5_tk == m_h5_tk else "否",
            )
            return result, cookie_m_h5_tk, None, None
        else:
            logger.warning("Cookie 中的 _m_h5_tk 已过期，尝试 DB 中的 _m_h5_tk")
    else:
        logger.warning("Cookie 字符串中未找到 _m_h5_tk")

    # 再试 DB 里的（作为兜底）
    logger.info("get_ws_token_with_refreshed: DB _m_h5_tk present=%s", bool(m_h5_tk))
    if m_h5_tk:
        result = _call_token_api(cookie_str, m_h5_tk)
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
        result = _call_token_api(cookie_str, cookie_m_h5_tk)
        if result == CAPTCHA_NEEDED:
            logger.error("Cookie 中的 _m_h5_tk 也触发滑块验证，需要更换 Cookie")
            return None, None, "captcha", None
        elif result:
            return result, cookie_m_h5_tk, None, None

    # 最后尝试：刷新 _m_h5_tk（参考 Java refreshMH5Tk 三部曲）
    logger.info("get_ws_token_with_refreshed: 尝试刷新 _m_h5_tk")
    new_cookie_str, new_m_h5_tk = refresh_m_h5_tk(cookie_str)
    if new_cookie_str and new_m_h5_tk:
        logger.info("get_ws_token_with_refreshed: _m_h5_tk 刷新成功，使用新令牌调用 Token API")
        result = _call_token_api(new_cookie_str, new_m_h5_tk)
        if result == CAPTCHA_NEEDED:
            logger.error("刷新后的 _m_h5_tk 也触发滑块验证，需要更换 Cookie")
            return None, None, "captcha", None
        elif result:
            logger.info("使用刷新后的 _m_h5_tk 获取 WS Token 成功, 长度=%d", len(result))
            return result, new_m_h5_tk, None, new_cookie_str
        else:
            logger.error("刷新后的 _m_h5_tk 调用 Token API 仍然失败")
            return None, None, "expired", None
    else:
        logger.error("_m_h5_tk 刷新失败，Cookie 可能已完全失效")

    return None, None, "expired", None
