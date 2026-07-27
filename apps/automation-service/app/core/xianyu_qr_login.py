"""
闲鱼网页版扫码登录模块。
直接调用闲鱼官方 API，使用 requests.Session() 自动管理 Cookie。

扫码登录分三阶段采集 Cookie，最终合并保存：
阶段1 get_m_h5_tk()：请求 h5api.m.goofish.com，获取 _m_h5_tk、_m_h5_tk_enc 和其他 Cookie
阶段2 get_login_params()：访问 passport.goofish.com/mini_login.htm，继续采集 Set-Cookie
阶段3 poll_qr_status()：用户确认后，获取 unb 和其他会话 Cookie
合并规则：三阶段 Cookie 全部合并；同名 Cookie 后获取覆盖前值
"""

import hashlib
import io
import json
import logging
import random
import re
import secrets
import threading
import time
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

import qrcode
import requests

logger = logging.getLogger(__name__)

# ==================== 常量 ====================

APP_KEY = "34839810"
H5_API = "https://h5api.m.goofish.com/h5/mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get/1.0/"
LOGIN_PAGE = "https://passport.goofish.com/mini_login.htm"
QR_GENERATE = "https://passport.goofish.com/newlogin/qrcode/generate.do"
QR_QUERY = "https://passport.goofish.com/newlogin/qrcode/query.do"

H_COMMON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://passport.goofish.com/",
    "Origin": "https://passport.goofish.com",
}

H_PAGE = {
    **H_COMMON,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

H_API = {
    **H_COMMON,
    "Accept": "application/json, text/plain, */*",
}

POLL_INTERVAL = 0.8
SESSION_TIMEOUT = 300  # 5 分钟

# 上海时区 UTC+8
SHANGHAI_TZ = timezone(timedelta(hours=8))


def _shanghai_now() -> datetime:
    """返回当前上海时间"""
    return datetime.now(SHANGHAI_TZ)


def _json_or_raise(resp: requests.Response, stage: str) -> dict:
    """解析闲鱼接口 JSON；若返回 HTML/纯文本/风控提示，抛出明确错误，避免 Java 侧收到 Invalid... 非 JSON。"""
    text = resp.text or ""
    if resp.status_code >= 400:
        raise RuntimeError(f"{stage} HTTP {resp.status_code}")
    content_type = (resp.headers.get("content-type") or "").lower()
    stripped = text.strip()
    if "json" not in content_type and not (stripped.startswith("{") or stripped.startswith("[")):
        raise RuntimeError(f"{stage} 返回了无法识别的响应")
    try:
        return resp.json()
    except ValueError as exc:
        raise RuntimeError(f"{stage} 响应解析失败") from exc


# ==================== 会话管理 ====================

_sessions: dict[str, dict] = {}
_lock = threading.Lock()
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,64}$")
_MAX_SESSIONS = 10_000
_MAX_SESSIONS_PER_OWNER = 5


def _positive_id(value) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _valid_session_id(session_id: str) -> bool:
    return bool(_SESSION_ID_PATTERN.fullmatch(str(session_id or "")))


def _cleanup_expired():
    """清理过期会话。"""
    now = time.time()
    with _lock:
        expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > SESSION_TIMEOUT]
        for sid in expired:
            del _sessions[sid]


# ==================== 核心函数 ====================


def _get_m_h5_tk(session: requests.Session) -> str:
    """Step 1: 获取签名令牌 _m_h5_tk。

    闲鱼 API 的 _m_h5_tk cookie 获取流程比较特殊：
    - 第一次 GET 只返回 cookie2，不返回 _m_h5_tk
    - 需要做一次带签名的 POST（即使 token 为空），POST 响应会设置 _m_h5_tk
    - 提取 _m_h5_tk 中的真实 token 后，再用真实 token 做第二次 POST 刷新
    """
    # 第一次 GET — 获取初始 Cookie（cookie2）
    session.get(H5_API, headers=H_API, timeout=20)

    # 第一次 POST — 用空 token 触发 _m_h5_tk 下发
    # 此时服务器会返回 "令牌为空" 错误，但会在 Set-Cookie 中设置 _m_h5_tk
    t_ms = int(time.time() * 1000)
    data_str = '{"bizScene":"home"}'
    sign = hashlib.md5(f"&{t_ms}&{APP_KEY}&{data_str}".encode()).hexdigest()

    session.post(H5_API, headers=H_API, data={
        "jsv": "2.7.2", "appKey": APP_KEY, "t": str(t_ms), "sign": sign,
        "v": "1.0", "type": "originaljson", "dataType": "json",
        "timeout": "20000", "api": "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
        "data": data_str
    }, timeout=20)

    # 从响应 Cookie 中提取 _m_h5_tk
    m_h5_tk = session.cookies.get("_m_h5_tk")
    if not m_h5_tk:
        raise RuntimeError("无法获取 _m_h5_tk Cookie")

    token = m_h5_tk.split("_")[0]
    t_ms2 = int(time.time() * 1000)
    sign2 = hashlib.md5(f"{token}&{t_ms2}&{APP_KEY}&{data_str}".encode()).hexdigest()

    # 第二次 POST — 用真实 token 刷新，获取完整业务 Cookie
    session.post(H5_API, headers=H_API, data={
        "jsv": "2.7.2", "appKey": APP_KEY, "t": str(t_ms2), "sign": sign2,
        "v": "1.0", "type": "originaljson", "dataType": "json",
        "timeout": "20000", "api": "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
        "data": data_str
    }, timeout=20)

    return session.cookies.get("_m_h5_tk", "")


def _get_login_params(session: requests.Session) -> dict:
    """Step 2: 从登录页面提取 loginFormData。"""
    params = {
        "lang": "zh_cn", "appName": "xianyu", "appEntrance": "web",
        "styleType": "vertical", "bizParams": "", "notLoadSsoView": "false",
        "notKeepLogin": "false", "isMobile": "false", "qrCodeFirst": "false",
        "stie": "77", "rnd": str(random.random())
    }
    resp = session.get(LOGIN_PAGE, headers=H_PAGE, params=params, timeout=20)

    match = re.search(r"window\.viewData\s*=\s*(\{.*?\});", resp.text, re.DOTALL)
    if not match:
        match = re.search(r"var\s+viewData\s*=\s*(\{.*?\});", resp.text, re.DOTALL)
    if not match:
        raise RuntimeError("无法从登录页面提取 viewData")

    login_form = json.loads(match.group(1))["loginFormData"]
    login_form["umidTag"] = "SERVER"
    return login_form


def _generate_qrcode(session: requests.Session, login_form: dict) -> str:
    """Step 3: 生成二维码，返回 Base64 图片。"""
    resp = session.get(QR_GENERATE, headers=H_API, params=login_form, timeout=20)
    result = _json_or_raise(resp, "生成二维码")
    qr_data = result.get("content", {}).get("data") or {}

    code_content = qr_data.get("codeContent")
    if not code_content:
        raise RuntimeError(f"二维码内容为空，返回内容: {json.dumps(result, ensure_ascii=False)[:300]}")

    # 更新 login_form，补充 t 和 ck 用于后续轮询
    login_form["t"] = qr_data.get("t", "")
    login_form["ck"] = qr_data.get("ck", "")

    # 生成二维码图片
    img = qrcode.make(code_content)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _collect_session_cookies(session: requests.Session, resp: requests.Response) -> dict:
    """合并 session.cookies 与响应头 Set-Cookie，避免 requests 因 domain 不匹配而丢失登录态字段。

    问题背景：requests.Session 的 cookie jar 会根据 Set-Cookie 的 domain/path 属性保存 cookie，
    若闲鱼在 CONFIRMED 时下发的 Set-Cookie domain 是 .taobao.com/.alibaba.com 等，
    与请求 URL 的 host（passport.goofish.com）不匹配时，cookie 可能未被 session 收集。
    导致保存到数据库的 Cookie 缺少 havana_lgc2_77 / _hvn_lgc_ / havana_lgc_exp 等
    核心登录态字段，进而触发 hasLogin API 返回 SESSION_EXPIRED（虽然 _m_h5_tk 有效，
    但 hasLogin 严格要求 havana_lgc2_77 等字段）。

    修复方案：与 cookie_token_refresher._call_has_login 保持一致，同时从响应头解析
    Set-Cookie 合并到 cookies dict，确保不丢失任何字段。
    """
    cookies = {k: v for k, v in session.cookies.items()}

    # 从响应头解析所有 Set-Cookie（urllib3 HTTPHeaderDict.getlist 支持多值）
    set_cookie_values: list[str] = []
    try:
        if resp.raw is not None and hasattr(resp.raw, "headers"):
            set_cookie_values = resp.raw.headers.getlist("Set-Cookie") or []
    except Exception:
        set_cookie_values = []
    if not set_cookie_values:
        try:
            set_cookie_values = resp.headers.get_list("set-cookie") or []  # type: ignore[attr-defined]
        except Exception:
            set_cookie_values = []
    if not set_cookie_values:
        sc = resp.headers.get("set-cookie")
        if sc:
            set_cookie_values = [sc]

    new_keys: list[str] = []
    for sc in set_cookie_values:
        # 每个 Set-Cookie 形如 "key=value; Path=/; Domain=.taobao.com; ..."
        first = sc.split(";")[0].strip()
        if "=" in first:
            k, v = first.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                continue
            # 只在新值与 session 中已有值不同时记录（避免覆盖 session 中更完整的值）
            if cookies.get(k) != v:
                cookies[k] = v
                new_keys.append(k)

    if new_keys:
        logger.info(
            "扫码登录 CONFIRMED: 从 Set-Cookie 头补全 %d 个字段 keys=%s (session_cookies=%d, total=%d)",
            len(new_keys), new_keys, len({k: v for k, v in session.cookies.items()}), len(cookies),
        )
    else:
        logger.info(
            "扫码登录 CONFIRMED: Set-Cookie 头未补全新字段 (session_cookies=%d, total=%d)",
            len({k: v for k, v in session.cookies.items()}), len(cookies),
        )

    # 关键字段存在性检查（用于诊断登录态完整性）
    critical_keys = ("havana_lgc2_77", "_hvn_lgc_", "havana_lgc_exp", "unb", "_m_h5_tk")
    missing_critical = [k for k in critical_keys if k not in cookies]
    if missing_critical:
        logger.warning(
            "扫码登录 CONFIRMED: 仍缺少关键登录态字段 missing=%s (可能导致 hasLogin 返回 SESSION_EXPIRED)",
            missing_critical,
        )
    else:
        logger.info("扫码登录 CONFIRMED: 关键登录态字段全部就绪")

    return cookies


def _poll_status(session: requests.Session, login_form: dict, timeout: int = SESSION_TIMEOUT) -> dict:
    """Step 4: 轮询扫码状态，阻塞直到完成或超时。"""
    start = time.time()
    while time.time() - start < timeout:
        resp = session.post(QR_QUERY, headers=H_API, data=login_form, timeout=20)
        data = _json_or_raise(resp, "轮询二维码状态").get("content", {}).get("data") or {}
        status = data["qrCodeStatus"]

        if status == "CONFIRMED":
            if data.get("iframeRedirect"):
                return {"status": "verification_required", "iframe_redirect_url": data.get("iframeRedirectUrl")}
            # 收集 Cookie：同时从 session.cookies 和响应头 Set-Cookie 合并，避免丢失登录态字段
            cookies = _collect_session_cookies(session, resp)
            return {"status": "confirmed", "cookies": cookies}
        elif status == "EXPIRED":
            return {"status": "expired"}
        elif status == "SCANED":
            logger.info("已扫码，等待确认...")
        elif status != "NEW":
            return {"status": "cancelled"}

        time.sleep(POLL_INTERVAL)

    return {"status": "expired"}


def _poll_status_once(session: requests.Session, login_form: dict) -> dict:
    """单次轮询，非阻塞。"""
    try:
        resp = session.post(QR_QUERY, headers=H_API, data=login_form, timeout=20)
        data = _json_or_raise(resp, "轮询二维码状态").get("content", {}).get("data") or {}
        status = data["qrCodeStatus"]

        if status == "CONFIRMED":
            if data.get("iframeRedirect"):
                return {"status": "verification_required", "iframe_redirect_url": data.get("iframeRedirectUrl")}
            # 收集 Cookie：同时从 session.cookies 和响应头 Set-Cookie 合并，避免丢失登录态字段
            cookies = _collect_session_cookies(session, resp)
            return {"status": "confirmed", "cookies": cookies}
        return {"status": status.lower()}
    except Exception as e:
        logger.error("轮询异常 errorType=%s", type(e).__name__)
        return {"status": "error", "message": "登录状态查询失败，请稍后重试"}


# ==================== 公开 API ====================


def generate_qrcode(user_id: int = None, tenant_id: int = None) -> dict:
    """
    创建新的扫码登录会话，返回 sessionId 和 Base64 二维码图片。
    user_id/tenant_id: 当前登录用户的上下文，扫码成功后用于归属账号。
    返回: {"sessionId": str, "qrImage": str (base64 data URI)}
    """
    owner_user_id = _positive_id(user_id)
    owner_tenant_id = _positive_id(tenant_id)
    if owner_user_id is None or owner_tenant_id is None:
        raise ValueError("扫码登录必须绑定有效的用户和租户")

    _cleanup_expired()

    session_id = secrets.token_urlsafe(32)
    s = requests.Session()
    login_form = {}

    # Reserve capacity before contacting the upstream provider.  Without a
    # bound, an authenticated caller could accumulate sessions faster than
    # the timeout cleanup and exhaust process memory.
    with _lock:
        owner_session_count = sum(
            1
            for session in _sessions.values()
            if session.get("user_id") == owner_user_id
            and session.get("tenant_id") == owner_tenant_id
        )
        if owner_session_count >= _MAX_SESSIONS_PER_OWNER:
            raise RuntimeError("too many active QR login sessions for this owner")
        if len(_sessions) >= _MAX_SESSIONS:
            raise RuntimeError("QR login session capacity is temporarily exhausted")
        _sessions[session_id] = {
            "session": s,
            "login_form": login_form,
            "qr_image": "",
            "status": "initializing",
            "created_at": time.time(),
            "user_id": owner_user_id,
            "tenant_id": owner_tenant_id,
        }

    try:
        _get_m_h5_tk(s)
        login_form = _get_login_params(s)
        qr_image = _generate_qrcode(s, login_form)
    except Exception as e:
        with _lock:
            _sessions.pop(session_id, None)
        logger.error("生成二维码失败 errorType=%s", type(e).__name__)
        raise RuntimeError("生成闲鱼登录二维码失败，请稍后重试") from e

    with _lock:
        reserved = _sessions.get(session_id)
        if reserved is None:
            raise RuntimeError("QR login session reservation expired")
        reserved.update({
            "login_form": login_form,
            "qr_image": qr_image,
            "status": "new",
        })

    logger.info("闲鱼扫码登录会话已创建 tenantId=%s", owner_tenant_id)
    return {"sessionId": session_id, "qrImage": qr_image}


def get_session_status(session_id: str) -> dict:
    """
    获取会话状态（单次轮询）。
    确认登录成功后不再返回原始 Cookie，仅返回安全的摘要信息。
    返回: {"status": "new"|"scaned"|"confirmed"|"expired"|"cancelled"|"verification_required", ...}
    """
    if not _valid_session_id(session_id):
        return {"status": "expired", "message": "会话不存在或已过期"}
    _cleanup_expired()

    with _lock:
        sdata = _sessions.get(session_id)
    if not sdata:
        return {"status": "expired", "message": "会话不存在或已过期"}

    # 检查超时
    if time.time() - sdata["created_at"] > SESSION_TIMEOUT:
        with _lock:
            _sessions.pop(session_id, None)
        return {"status": "expired", "message": "登录超时"}

    result = _poll_status_once(sdata["session"], sdata["login_form"])

    with _lock:
        if session_id in _sessions:
            _sessions[session_id]["status"] = result["status"]

    # 如果是 confirmed，保存 cookies 到会话数据，只返回安全摘要
    if result.get("status") == "confirmed":
        cookies = result.pop("cookies", None)
        if cookies:
            # 保存 cookies 到会话，供 get_session_cookies 读取
            with _lock:
                if session_id in _sessions:
                    _sessions[session_id]["saved_cookies"] = cookies
            # 提取 unb 用于前端显示，cookie 数据不返回
            unb = cookies.get("unb", "")
            result["unb"] = unb
            result["externalUid"] = unb
        else:
            result["unb"] = ""
            result["externalUid"] = ""

    return result


def get_session_cookies(session_id: str) -> Optional[dict]:
    """
    内部使用：获取登录成功后的完整 Cookie 数据和用户上下文。
    仅在 status 为 confirmed 时返回有效数据。
    返回: {"cookies": dict, "user_id": int, "tenant_id": int, "cookie_text": str, "unb": str, "m_h5_tk": str}
    """
    if not _valid_session_id(session_id):
        return None
    with _lock:
        sdata = _sessions.get(session_id)
    if not sdata:
        return None

    # 优先使用 get_session_status 已保存的 cookies，避免重复轮询（QR 只能确认一次）
    saved_cookies = sdata.get("saved_cookies", {})
    if saved_cookies:
        cookie_text = _format_cookies(saved_cookies)
        unb = saved_cookies.get("unb", "")
        m_h5_tk = saved_cookies.get("_m_h5_tk", "")

        with _lock:
            user_id = sdata.get("user_id")
            tenant_id = sdata.get("tenant_id")

        return {
            "cookies": saved_cookies,
            "cookie_text": cookie_text,
            "unb": unb,
            "m_h5_tk": m_h5_tk,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

    # 兜底：若无保存的 cookies，尝试轮询一次
    result = _poll_status_once(sdata["session"], sdata["login_form"])
    if result["status"] == "confirmed":
        cookies = result.get("cookies", {})
        cookie_text = _format_cookies(cookies)
        unb = cookies.get("unb", "")
        m_h5_tk = cookies.get("_m_h5_tk", "")

        with _lock:
            user_id = sdata.get("user_id")
            tenant_id = sdata.get("tenant_id")

        return {
            "cookies": cookies,
            "cookie_text": cookie_text,
            "unb": unb,
            "m_h5_tk": m_h5_tk,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }
    return None


def get_session_context(session_id: str) -> Optional[dict]:
    """获取会话的用户上下文，不执行轮询。"""
    if not _valid_session_id(session_id):
        return None
    with _lock:
        sdata = _sessions.get(session_id)
    if not sdata:
        return None
    return {
        "user_id": sdata.get("user_id"),
        "tenant_id": sdata.get("tenant_id"),
        "status": sdata.get("status"),
    }


def cleanup_session(session_id: str) -> bool:
    """清理指定会话。"""
    if not _valid_session_id(session_id):
        return False
    with _lock:
        return _sessions.pop(session_id, None) is not None


def cleanup_session_for_owner(session_id: str, user_id: int, tenant_id: int) -> bool:
    """仅当会话属于给定用户和租户时清理。"""
    owner_user_id = _positive_id(user_id)
    owner_tenant_id = _positive_id(tenant_id)
    if not _valid_session_id(session_id) or owner_user_id is None or owner_tenant_id is None:
        return False
    with _lock:
        session = _sessions.get(session_id)
        if not session:
            return False
        if session.get("user_id") != owner_user_id or session.get("tenant_id") != owner_tenant_id:
            return False
        _sessions.pop(session_id, None)
        return True


def cleanup_sessions_for_owner(user_id: int, tenant_id: int) -> int:
    """只清理指定用户在指定租户下创建的扫码会话。"""
    owner_user_id = _positive_id(user_id)
    owner_tenant_id = _positive_id(tenant_id)
    if owner_user_id is None or owner_tenant_id is None:
        return 0
    with _lock:
        owned = [
            sid
            for sid, session in _sessions.items()
            if session.get("user_id") == owner_user_id
            and session.get("tenant_id") == owner_tenant_id
        ]
        for sid in owned:
            _sessions.pop(sid, None)
        return len(owned)


# ==================== 完整流程（独立运行） ====================


def xianyu_qr_login(blocking: bool = True, timeout: int = SESSION_TIMEOUT) -> dict:
    """
    完整扫码登录流程。
    - blocking=True: 阻塞等待扫码完成
    - blocking=False: 只生成二维码，返回 sessionId 和图片
    """
    s = requests.Session()
    _get_m_h5_tk(s)
    login_form = _get_login_params(s)
    qr_image = _generate_qrcode(s, login_form)

    if not blocking:
        return {"qr_image": qr_image, "session": s, "login_form": login_form}

    result = _poll_status(s, login_form, timeout)
    result["qr_image"] = qr_image
    return result


# ==================== Cookie 工具函数 ====================


def _format_cookies(cookies: dict) -> str:
    """
    将 dict 格式的 Cookie 合并为完整的 Cookie 字符串。
    格式: "key1=value1; key2=value2; ..."
    """
    if not cookies:
        return ""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _extract_unb(cookies: dict) -> str:
    """从 Cookie dict 中提取 unb"""
    if not cookies:
        return ""
    return cookies.get("unb", "")


def _extract_m_h5_tk(cookies: dict) -> str:
    """从 Cookie dict 中提取 _m_h5_tk"""
    if not cookies:
        return ""
    return cookies.get("_m_h5_tk", "")
