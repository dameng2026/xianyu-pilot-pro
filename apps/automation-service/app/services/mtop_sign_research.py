"""方案 K：MTOP H5 API 签名算法逆向（高难度）—— 研究模块

> **背景**：当前所有免滑块方案（缓存注入 / HTTP 提取 / 静默提取 / 滑块求解）都依赖
> 服务端或浏览器在 Baxia 验证通过后下发 x5sec。方案 K 的目标是逆向 _m_h5_tk 签名
> 算法与 x5sec 生成逻辑，直接在客户端生成有效 x5sec，完全跳过 Baxia 验证流程。
>
> **难度评估**：极高。Baxia 服务端校验涉及多维信号（IP 信誉 / Cookie 完整性 /
> 请求频率 / 设备指纹 / 行为序列），x5sec 由服务端签发并加密，客户端无法直接伪造。
>
> **本模块定位**：长期研究方向的基础框架，提供：
>   1. x5sec 结构分析器：解码 base64、解析字段、记录样本便于离线分析
>   2. _m_h5_tk 签名算法实现（已知算法，复用 ws_token._make_sign）
>   3. x5sec 生成器抽象接口：待逆向完成后填充具体算法
>   4. 方案 K 调用入口：在优先级链中作为优先级 1.5 尝试
>
> **当前状态**：2026-08-05 迭代。`generate_x5sec_locally` 已实现三条路线：
>   - Route 1（模板替换）：从缓存 x5sec 替换时间戳刷新（无网络请求）
>   - Route 3（MTOP API 触发）：调用轻量 MTOP API 触发服务端下发 x5sec
>   - Route I（FireyeJS 浏览器）：调用 crawler-service NC 链（useProxy=true）
>   Route 2（完整逆向）因研究结论"x5sec 服务端生成"而搁置。
>   各路线成功时返回有效 x5sec，由 try_plan_k_x5sec 注入后调用 Token API 验证。
>   不影响现有方案 F/G/缓存/HTTP/静默/滑块（PLAN_K_ENABLED=false 时本模块仅记录样本）。
>
> **相关文件**：
>   - 本模块：apps/automation-service/app/services/mtop_sign_research.py
>   - 集成点：apps/automation-service/app/services/ws_token.py（get_ws_token_with_refreshed_m_h5_tk）
>   - 文档：.trae/rules/x5sec-research-knowledge.md 第九章 方案 K
>
> **研究路线**（待持续推进）：
>   1. 收集大量 x5sec 样本（不同账号 / IP / 时间段）
>   2. 分析 x5sec 结构（base64 解码 → 字段拆分 → 加密算法识别）
>   3. 对比成功/失败样本，识别关键字段
>   4. 逆向 Baxia JS（FireyeJS / NoCaptcha）的 x5sec 生成逻辑
>   5. 实现客户端 x5sec 生成器，验证服务端接受度
"""
import base64
import hashlib
import json
import logging
import os
import re
import time
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)

# ============================================================
# 常量（与 ws_token.py / xianyu_goods_sync.py 保持一致）
# ============================================================
APP_KEY = "34839810"
H5_API_BASE = "https://h5api.m.goofish.com/h5"

# 方案 K 启用开关（默认关闭，仅研究阶段使用）
# 启用方式：环境变量 PLAN_K_ENABLED=true
PLAN_K_ENABLED = os.environ.get("PLAN_K_ENABLED", "false").lower() == "true"

# x5sec 样本记录开关：即使方案 K 未启用，也可以记录 x5sec 样本到日志便于离线分析
PLAN_K_SAMPLE_LOGGING = os.environ.get("PLAN_K_SAMPLE_LOGGING", "true").lower() == "true"

# x5sec 样本持久化开关：将样本写入 JSONL 文件，便于离线多样本对比分析
# 默认 false（生产环境可能产生大量样本文件，需显式开启）
PLAN_K_PERSIST_SAMPLES = os.environ.get("PLAN_K_PERSIST_SAMPLES", "false").lower() == "true"

# 已知 x5sec 字段名（基于公开资料与样本观察，待逆向验证）
# x5sec 格式可能是：base64(json({uid, ts, sign, ...})) 或 base64(encrypted_payload)
X5SEC_KNOWN_FIELDS = ["uid", "ts", "sign", "exp", "v", "data"]

# ============================================================
# 1. _m_h5_tk 签名算法（已知，复用 ws_token._make_sign）
# ============================================================

def make_mtop_sign(token: str, t_ms: int, data_str: str) -> str:
    """生成 MTOP H5 API 签名。

    算法：MD5(token + "&" + timestamp + "&" + APP_KEY + "&" + dataJson)

    这是 MTOP 网关的公开签名算法（非加密保护），用于请求完整性校验。
    真正的逆向难点在于 x5sec（Baxia 风控令牌），而非 _m_h5_tk 签名本身。

    Args:
        token: _m_h5_tk 的 token 部分（下划线前）
        t_ms: 毫秒时间戳
        data_str: JSON 序列化后的请求数据

    Returns:
        32 位小写 MD5 签名
    """
    raw = f"{token}&{t_ms}&{APP_KEY}&{data_str}"
    return hashlib.md5(raw.encode()).hexdigest()


def extract_token_from_m_h5_tk(m_h5_tk: str) -> Optional[str]:
    """从 _m_h5_tk 提取 token 部分。

    _m_h5_tk 格式：{token}_{timestamp}，token 部分用于签名。

    Args:
        m_h5_tk: _m_h5_tk 完整值

    Returns:
        token 部分，或 None
    """
    if not m_h5_tk:
        return None
    if "_" in m_h5_tk:
        return m_h5_tk.split("_")[0]
    return m_h5_tk


# ============================================================
# 2. x5sec 结构分析器（研究工具）
# ============================================================

def analyze_x5sec_structure(x5sec: str) -> Dict[str, Any]:
    """分析 x5sec 结构，返回字段信息便于离线研究。

    x5sec 通常以 base64 编码，可能包含：
    - 用户标识（uid / unb）
    - 时间戳（签发时间 / 过期时间）
    - 签名（HMAC / 自定义算法）
    - 风控状态标记
    - 加密 payload

    本函数仅做结构分析，不尝试伪造。研究结果用于填充 generate_x5sec_locally。

    Args:
        x5sec: x5sec 值（从 Set-Cookie 或缓存获取）

    Returns:
        分析结果 dict：
        {
            "length": int,
            "is_base64": bool,
            "decoded_length": int,
            "decoded_prefix_hex": str,
            "decoded_printable": str,
            "has_json_structure": bool,
            "json_fields": list,
            "looks_like_encrypted": bool,
            "sample_timestamp": int,
        }
    """
    result: Dict[str, Any] = {
        "length": len(x5sec) if x5sec else 0,
        "is_base64": False,
        "decoded_length": 0,
        "decoded_prefix_hex": "",
        "decoded_printable": "",
        "has_json_structure": False,
        "json_fields": [],
        "looks_like_encrypted": False,
        "sample_timestamp": int(time.time()),
    }

    if not x5sec:
        return result

    # 尝试 base64 解码
    try:
        # x5sec 可能是 url-safe base64
        cleaned = x5sec.replace("-", "+").replace("_", "/")
        # 补齐 padding
        padding = 4 - (len(cleaned) % 4)
        if padding != 4:
            cleaned = cleaned + "=" * padding
        decoded = base64.b64decode(cleaned, validate=False)
        result["is_base64"] = True
        result["decoded_length"] = len(decoded)
        result["decoded_prefix_hex"] = decoded[:32].hex()

        # 检查是否可打印
        try:
            decoded_str = decoded.decode("utf-8", errors="replace")
            result["decoded_printable"] = decoded_str[:200]

            # 检查是否是 JSON
            stripped = decoded_str.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                result["has_json_structure"] = True
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict):
                        result["json_fields"] = list(parsed.keys())
                except Exception:
                    pass
        except Exception:
            pass

        # 启发式判断：解码后无可见 ASCII，可能是加密 payload
        printable_ratio = sum(1 for b in decoded[:64] if 32 <= b < 127) / max(1, min(64, len(decoded)))
        if printable_ratio < 0.3 and len(decoded) > 16:
            result["looks_like_encrypted"] = True

    except Exception as e:
        logger.debug("[方案K] analyze_x5sec_structure: base64 解码失败: %s", e)

    return result


def log_x5sec_sample(cookie_str: str, x5sec: str, source: str = "unknown") -> None:
    """记录 x5sec 样本到日志，便于离线分析。

    即使方案 K 未启用，也可以通过 PLAN_K_SAMPLE_LOGGING=true 收集样本。
    样本日志格式：[方案K-SAMPLE] source=xxx length=xxx analysis=xxx

    同时持久化到 JSONL 文件（PLAN_K_PERSIST_SAMPLES=true 时），便于离线对比分析。
    文件路径：{PLAN_K_SAMPLE_DIR}/x5sec_samples_{date}.jsonl

    Args:
        cookie_str: Cookie 字符串（用于提取 unb 标识账号）
        x5sec: x5sec 值
        source: 样本来源（captcha_response / cache_hit / silent_extract / slider_solve / http_extract）
    """
    if not PLAN_K_SAMPLE_LOGGING:
        return
    if not x5sec:
        return

    try:
        unb_match = re.search(r"(?:^|;\s*)unb=([^;]+)", cookie_str or "")
        unb = unb_match.group(1).strip() if unb_match else "unknown"

        analysis = analyze_x5sec_structure(x5sec)
        logger.info(
            "[方案K-SAMPLE] source=%s unb=%s length=%d is_base64=%s decoded_len=%d "
            "has_json=%s json_fields=%s encrypted=%s prefix_hex=%s",
            source,
            unb,
            analysis["length"],
            analysis["is_base64"],
            analysis["decoded_length"],
            analysis["has_json_structure"],
            analysis["json_fields"],
            analysis["looks_like_encrypted"],
            analysis["decoded_prefix_hex"][:32],
        )

        # 持久化到 JSONL 文件（便于离线多样本对比）
        if PLAN_K_PERSIST_SAMPLES:
            _persist_x5sec_sample(cookie_str, x5sec, source, unb, analysis)
    except Exception as e:
        logger.debug("[方案K-SAMPLE] 记录样本失败: %s", e)


def _persist_x5sec_sample(
    cookie_str: str,
    x5sec: str,
    source: str,
    unb: str,
    analysis: Dict[str, Any],
) -> None:
    """将 x5sec 样本持久化到 JSONL 文件。

    文件格式（每行一个 JSON）：
    {"ts": 1700000000, "source": "captcha_response", "unb": "12345",
     "length": 128, "analysis": {...}, "x5sec": "...", "cookie_prefix_hash": "abc123"}

    同一账号同一天的样本写入同一文件，便于按账号+时间维度分析。

    Args:
        cookie_str: Cookie 字符串
        x5sec: x5sec 值
        source: 样本来源
        unb: 账号 unb
        analysis: analyze_x5sec_structure 返回的分析结果
    """
    try:
        sample_dir = os.environ.get("PLAN_K_SAMPLE_DIR", "/tmp/x5sec_samples")
        os.makedirs(sample_dir, exist_ok=True)

        # 按日期分文件，便于按天分析
        date_str = time.strftime("%Y%m%d", time.localtime())
        sample_file = os.path.join(sample_dir, f"x5sec_samples_{date_str}.jsonl")

        # cookie 前缀 hash 用于跨样本关联（不存储完整 cookie 避免泄露）
        cookie_prefix_hash = hashlib.md5((cookie_str or "")[:100].encode()).hexdigest()[:16]

        sample_record = {
            "ts": int(time.time()),
            "source": source,
            "unb": unb,
            "cookie_prefix_hash": cookie_prefix_hash,
            "length": len(x5sec),
            "x5sec": x5sec,
            "analysis": analysis,
        }

        # 原子追加写入
        with open(sample_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample_record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("[方案K] _persist_x5sec_sample: 持久化失败: %s", e)


# ============================================================
# 3. x5sec 生成器（方案 K 多路线实现）
# ============================================================

# 已知可能触发 x5sec 下发的轻量 MTOP API 端点
# 这些端点风控等级较低，调用时服务端可能在 Set-Cookie 中附带 x5sec
# 顺序：从最可能下发 x5sec（会话/用户类）到次可能（配置/通知类）
_X5SEC_TRIGGER_MTOP_APIS = [
    "mtop.taobao.idle.user.get",
    "mtop.taobao.idle.session.check",
    "mtop.taobao.idle.config.get",
    "mtop.taobao.idle.message.list.get",
    "mtop.taobao.idle.profile.get",
    "mtop.taobao.idle.notice.get",
]

# MTOP 风控信号关键词（响应体含这些说明触发 Baxia 风控）
_BAXIA_RISK_SIGNALS = [
    "FAIL_SYS_USER_VALIDATE",
    "RGV587_ERROR",
    "x5secdata",
    "baxia",
    "punish",
]


def _extract_x5sec_from_response(resp: Any) -> Tuple[Optional[str], str, bool]:
    """从 MTOP/HTTP 响应中提取 x5sec，并检测风控信号。

    优先用 resp.cookies（requests 自动解析所有 Set-Cookie，最可靠），
    回退到 resp.raw.headers.getlist（多个 Set-Cookie 头），再回退到合并的 headers。

    Args:
        resp: requests.Response 对象

    Returns:
        (x5sec, source, risk_triggered):
        - x5sec: 提取的 x5sec 值，或 None
        - source: 提取来源（cookies / set_cookie_header / raw_headers）
        - risk_triggered: 响应是否含 Baxia 风控信号
    """
    x5sec = None
    source = "none"

    # 优先用 resp.cookies（requests 自动解析所有 Set-Cookie）
    if hasattr(resp, "cookies") and resp.cookies:
        for ck in resp.cookies:
            if ck.name == "x5sec" and ck.value and len(ck.value) > 5:
                x5sec = ck.value
                source = "cookies"
                break

    # 回退 1：resp.raw.headers.getlist（多个 Set-Cookie 头，未合并）
    if not x5sec and hasattr(resp, "raw") and hasattr(resp.raw, "headers"):
        try:
            set_cookies = resp.raw.headers.getlist("Set-Cookie")
        except Exception:
            set_cookies = []
        for sc in set_cookies:
            extracted = extract_x5sec_from_response_headers(sc)
            if extracted:
                x5sec = extracted
                source = "raw_headers"
                break

    # 回退 2：合并的 headers（最不可靠，但兜底）
    if not x5sec:
        set_cookie = resp.headers.get("Set-Cookie") or resp.headers.get("set-cookie") or ""
        if set_cookie:
            x5sec = extract_x5sec_from_response_headers(set_cookie)
            if x5sec:
                source = "set_cookie_header"

    # 检测风控信号（响应体）
    risk_triggered = False
    try:
        body_text = resp.text[:2000] if hasattr(resp, "text") else ""
        if body_text:
            for signal in _BAXIA_RISK_SIGNALS:
                if signal in body_text:
                    risk_triggered = True
                    break
    except Exception:
        pass

    return x5sec, source, risk_triggered


def _refresh_x5sec_via_template(cookie_str: str, m_h5_tk: str) -> Optional[str]:
    """Route 1：基于缓存 x5sec 模板替换时间戳，尝试刷新过期 x5sec。

    原理：如果 x5sec 包含明文时间戳字段（ASCII 秒级/毫秒级），且服务端
    仅校验时间戳时效性（不校验签名或签名不覆盖时间戳字段），则替换时间戳
    后可能恢复有效性。这是"尽力尝试"——若 x5sec 含签名校验则会失败，
    失败后由 generate_x5sec_locally 的后续 Route 接管。

    步骤：
    1. 从 Redis/本地缓存获取已缓存的 x5sec 样本
    2. 用 find_timestamp_in_x5sec 定位时间戳位置
    3. 替换为当前时间戳（保持相同长度）
    4. 重新 base64 编码返回

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值（未使用，保持接口一致）

    Returns:
        刷新后的 x5sec 值，或 None（无缓存样本/无时间戳/替换失败）
    """
    try:
        from .x5sec_cache_client import get_cached_x5sec
    except ImportError:
        logger.debug("[方案K-Route1] x5sec_cache_client 模块不可用")
        return None

    cached_x5sec = get_cached_x5sec(cookie_str)
    if not cached_x5sec:
        logger.debug("[方案K-Route1] 无缓存 x5sec 样本，跳过模板替换")
        return None

    ts_analysis = find_timestamp_in_x5sec(cached_x5sec)
    if not ts_analysis.get("found"):
        logger.debug("[方案K-Route1] 缓存 x5sec 中未找到时间戳模式，跳过")
        return None

    current_ts = int(time.time())

    best_match = None
    for match in ts_analysis.get("matches", []):
        if not match.get("plausible"):
            continue
        enc = match.get("encoding", "")
        if enc == "ascii_seconds":
            best_match = match
            break
        if enc == "ascii_millis" and not best_match:
            best_match = match

    if not best_match:
        logger.debug("[方案K-Route1] 未找到合理的时间戳匹配，跳过")
        return None

    try:
        cleaned = cached_x5sec.replace("-", "+").replace("_", "/")
        padding = 4 - (len(cleaned) % 4)
        if padding != 4:
            cleaned = cleaned + "=" * padding
        decoded = bytearray(base64.b64decode(cleaned, validate=False))
    except Exception as e:
        logger.debug("[方案K-Route1] base64 解码失败: %s", e)
        return None

    encoding = best_match.get("encoding")
    offset = best_match.get("offset", 0)
    old_value = best_match.get("value", 0)

    if encoding == "ascii_seconds":
        new_ts_str = str(current_ts).encode("ascii")
        old_ts_str = str(old_value).encode("ascii")
        if len(new_ts_str) == len(old_ts_str) and offset + len(old_ts_str) <= len(decoded):
            decoded[offset:offset + len(old_ts_str)] = new_ts_str
            logger.info(
                "[方案K-Route1] 替换 ASCII 秒级时间戳 offset=%d old=%d new=%d",
                offset, old_value, current_ts,
            )
        else:
            logger.debug("[方案K-Route1] 秒级时间戳长度不匹配或越界，跳过")
            return None
    elif encoding == "ascii_millis":
        new_ts_ms = current_ts * 1000
        new_ts_str = str(new_ts_ms).encode("ascii")
        old_ts_str = str(old_value).encode("ascii")
        if len(new_ts_str) == len(old_ts_str) and offset + len(old_ts_str) <= len(decoded):
            decoded[offset:offset + len(old_ts_str)] = new_ts_str
            logger.info(
                "[方案K-Route1] 替换 ASCII 毫秒级时间戳 offset=%d old=%d new=%d",
                offset, old_value, new_ts_ms,
            )
        else:
            logger.debug("[方案K-Route1] 毫秒时间戳长度不匹配或越界，跳过")
            return None
    else:
        logger.debug("[方案K-Route1] 不支持的时间戳编码 %s，跳过", encoding)
        return None

    try:
        new_x5sec = base64.urlsafe_b64encode(bytes(decoded)).decode("ascii").rstrip("=")
        logger.info("[方案K-Route1] ✓ 模板替换完成，生成新 x5sec 长度=%d", len(new_x5sec))
        return new_x5sec
    except Exception as e:
        logger.warning("[方案K-Route1] base64 重新编码失败: %s", e)
        return None


def _trigger_x5sec_via_mtop_api(cookie_str: str, m_h5_tk: str) -> Optional[str]:
    """Route 3：调用轻量 MTOP API 触发服务端在 Set-Cookie 中下发 x5sec。

    原理：某些低风控等级的 MTOP API 调用时，服务端会在响应的 Set-Cookie
    头中附带 x5sec（作为会话续期/风控放行令牌）。这等同于"服务端生成 x5sec"，
    但无需完整 Baxia 验证流程。

    与 _try_http_x5sec_extract 的区别：
    - _try_http_x5sec_extract 侧重 GET 请求探测（首页/im 页/personal 页）
    - 本函数侧重 MTOP API POST 请求（带签名），尝试不同的 API 端点
    - 端点列表互补：_try_http 用 mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get，
      本函数用 mtop.taobao.idle.user.get / session.check / config.get

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值

    Returns:
        从 Set-Cookie 提取的 x5sec 值，或 None（所有端点均未下发）
    """
    token = extract_token_from_m_h5_tk(m_h5_tk)
    if not token:
        logger.debug("[方案K-Route3] 无法从 _m_h5_tk 提取 token，跳过")
        return None

    try:
        import requests as _requests
    except ImportError:
        logger.debug("[方案K-Route3] requests 模块不可用，跳过")
        return None

    t_ms = int(time.time() * 1000)
    data_str = "{}"
    sign = make_mtop_sign(token, t_ms, data_str)

    for api_name in _X5SEC_TRIGGER_MTOP_APIS:
        try:
            url = f"{H5_API_BASE}/{api_name}/1.0/"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": cookie_str,
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.goofish.com/",
                "Origin": "https://www.goofish.com",
            }
            params = {
                "jsv": "2.7.2",
                "appKey": APP_KEY,
                "t": str(t_ms),
                "sign": sign,
                "api": api_name,
                "v": "1.0",
                "type": "originaljson",
                "dataType": "json",
                "data": data_str,
            }
            resp = _requests.post(
                url, headers=headers, data=params, timeout=8, allow_redirects=False
            )

            x5sec, source, risk_triggered = _extract_x5sec_from_response(resp)

            if x5sec:
                logger.info(
                    "[方案K-Route3] ✓ MTOP API %s 下发 x5sec (长度=%d, source=%s, risk=%s)",
                    api_name, len(x5sec), source, risk_triggered,
                )
                return x5sec
            logger.debug(
                "[方案K-Route3] MTOP API %s 未下发 x5sec (status=%d, risk=%s)",
                api_name, resp.status_code, risk_triggered,
            )
        except Exception as e:
            logger.debug("[方案K-Route3] MTOP API %s 调用失败: %s", api_name, e)

    logger.info("[方案K-Route3] 所有 MTOP API 端点均未下发 x5sec")
    return None


def _trigger_x5sec_via_fireyejs_browser(cookie_str: str, m_h5_tk: str) -> Optional[str]:
    """Route I：调用 crawler-service 浏览器执行 FireyeJS NC 链获取 x5sec。

    原理：在真实浏览器中加载 FireyeJS，执行 getFYToken()/getUidToken()
    获取真实设备指纹令牌，然后喂给 um.json → initialize.jsonp → analyze.jsonp
    链路，触发服务端 Baxia 验证通过后下发 x5sec。

    与 Route J（已废弃）的区别：
    - Route J 在匿名 + 服务器 IP 条件下判定不可行（13.8 节结论）
    - Route I 使用真实账号 Cookie + 住宅 IP 代理（useProxy=true）
    - 这是 Route J 的修正版，复用 Plan E 的成功条件（真实 Cookie + 住宅 IP）

    复用已有端点：POST /api/fireyejs/route-j-flow（crawler-service）
    该端点已在 fireyejsToken.ts 中实现完整 NC 链。

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值（未使用，保持接口一致）

    Returns:
        从 NC 链响应提取的 x5sec 值，或 None
    """
    crawler_url = os.environ.get("CRAWLER_SERVICE_URL", "http://localhost:3001")
    endpoint = f"{crawler_url}/api/fireyejs/route-j-flow"

    try:
        import requests as _requests
    except ImportError:
        logger.debug("[方案K-RouteI] requests 模块不可用，跳过")
        return None

    # 超时分级：连接超时 5 秒（crawler-service 不可达时快速失败），
    # 读取超时 45 秒（NC 链浏览器执行较慢，需要足够时间）
    timeout = (5, 45)

    try:
        resp = _requests.post(
            endpoint,
            json={
                "cookie": cookie_str,
                "useProxy": True,
                "debug": False,
            },
            timeout=timeout,
        )
    except _requests.exceptions.ConnectTimeout:
        logger.warning("[方案K-RouteI] crawler-service 连接超时（5s），服务不可达，跳过")
        return None
    except _requests.exceptions.ReadTimeout:
        logger.warning("[方案K-RouteI] crawler-service 读取超时（45s），NC 链未完成")
        return None
    except _requests.exceptions.ConnectionError as e:
        logger.warning("[方案K-RouteI] crawler-service 连接失败: %s", str(e)[:150])
        return None
    except Exception as e:
        logger.warning("[方案K-RouteI] crawler-service 请求异常: %s", str(e)[:150])
        return None

    if resp.status_code != 200:
        if resp.status_code == 422:
            try:
                data = resp.json()
                logger.debug(
                    "[方案K-RouteI] route-j-flow 返回 422: %s",
                    str(data.get("error", ""))[:150],
                )
            except Exception:
                logger.debug("[方案K-RouteI] route-j-flow 返回 422（无 JSON 体）")
        else:
            logger.debug("[方案K-RouteI] crawler-service 返回 %d", resp.status_code)
        return None

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("[方案K-RouteI] 响应非 JSON: %s", str(e)[:150])
        return None

    if not data.get("ok"):
        logger.debug(
            "[方案K-RouteI] route-j-flow ok=false: %s",
            str(data.get("error", ""))[:150],
        )
        return None

    # 主路径：x5sec 字段直接提取
    x5sec = data.get("x5sec")
    x5sec_source = data.get("x5secSource", "direct")

    # 回退路径：从 finalCookies 提取（浏览器最终所有 cookie）
    if not x5sec:
        final_cookies = data.get("finalCookies") or ""
        if final_cookies:
            x5sec = extract_x5sec_from_response_headers(final_cookies)
            if x5sec:
                x5sec_source = "final_cookies"

    # 住宅 IP 代理使用检测：
    # Route I 请求 useProxy=true，若 proxyUsed=false 说明住宅代理池为空，
    # fallback 到服务器 IP。Route J 已证明服务器 IP 下 NC 链不可行（13.8 节），
    # 此条件下即使返回 x5sec 也可能是无效的，不信任结果。
    proxy_used = data.get("proxyUsed")
    if proxy_used is False:
        logger.warning(
            "[方案K-RouteI] 住宅代理未实际使用（proxyUsed=false，fallback 服务器 IP），"
            "Route J 已证明此条件不可行，不信任结果"
        )
        return None

    if x5sec and len(x5sec) > 5:
        logger.info(
            "[方案K-RouteI] ✓ FireyeJS 浏览器 NC 链提取 x5sec 成功 "
            "(长度=%d, source=%s, proxyUsed=%s)",
            len(x5sec), x5sec_source, proxy_used,
        )
        return x5sec

    logger.info(
        "[方案K-RouteI] route-j-flow ok 但无 x5sec (analyzeCode=%s, sig=%s, proxyUsed=%s)",
        data.get("analyzeResultCode"), bool(data.get("analyzeSig")), proxy_used,
    )
    return None


def generate_x5sec_locally(cookie_str: str, m_h5_tk: str) -> Optional[str]:
    """方案 K 核心：尝试多种路线生成/获取有效 x5sec。

    **实现状态（2026-08-05 迭代）**：
    - Route 1（模板替换）：已实现 —— 从缓存 x5sec 替换时间戳刷新（无网络请求）
    - Route 2（完整逆向）：未实现 —— Baxia 加密算法逆向未完成
      （研究结论：x5sec 服务端生成，静态 JS 中不含 x5sec 关键字）
    - Route 3（MTOP API 触发）：已实现 —— 调用轻量 MTOP API 触发服务端下发
    - Route I（FireyeJS 浏览器）：已实现 —— 调用 crawler-service NC 链（useProxy）

    按优先级尝试（从快到慢）：
    1. Route 1：模板替换（无网络请求，最快，成功率低）
    2. Route 3：MTOP API 触发（轻量 HTTP 请求，~1s，成功率中等）
    3. Route I：FireyeJS 浏览器（重量级，~10-30s，成功率取决于住宅 IP）

    任一路线成功则返回 x5sec，由 try_plan_k_x5sec 注入后调用 Token API 验证。
    所有路线失败返回 None，优先级链继续到优先级 2（x5sec 缓存注入）。

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值

    Returns:
        生成的 x5sec 值，或 None（所有路线失败）
    """
    if not PLAN_K_ENABLED:
        return None

    if not cookie_str or not m_h5_tk:
        return None

    # Route 1：模板替换（无网络请求，最快）
    try:
        x5sec = _refresh_x5sec_via_template(cookie_str, m_h5_tk)
        if x5sec:
            logger.info("[方案K] Route 1（模板替换）生成 x5sec 成功")
            return x5sec
    except Exception as e:
        logger.debug("[方案K] Route 1 异常: %s", e)

    # Route 3：MTOP API 触发（轻量 HTTP 请求）
    try:
        x5sec = _trigger_x5sec_via_mtop_api(cookie_str, m_h5_tk)
        if x5sec:
            logger.info("[方案K] Route 3（MTOP API 触发）获取 x5sec 成功")
            return x5sec
    except Exception as e:
        logger.debug("[方案K] Route 3 异常: %s", e)

    # Route I：FireyeJS 浏览器（重量级，最后尝试）
    try:
        x5sec = _trigger_x5sec_via_fireyejs_browser(cookie_str, m_h5_tk)
        if x5sec:
            logger.info("[方案K] Route I（FireyeJS 浏览器）获取 x5sec 成功")
            return x5sec
    except Exception as e:
        logger.debug("[方案K] Route I 异常: %s", e)

    logger.debug("[方案K] generate_x5sec_locally: 所有路线失败，返回 None")
    return None


# ============================================================
# 4. 方案 K 调用入口（优先级 1.5）
# ============================================================

def try_plan_k_x5sec(cookie_str: str, m_h5_tk: str) -> Tuple[Optional[str], Optional[str]]:
    """方案 K 入口：尝试本地生成 x5sec 并注入后调用 Token API。

    **实现状态（2026-08-05 迭代）**：
    generate_x5sec_locally 已实现 Route 1/3/I 三条路线，本函数不再
    始终返回 (None, None)。当 PLAN_K_ENABLED=true 时会按优先级尝试
    各路线，成功则注入 x5sec 并调用 Token API 验证。

    在优先级链中作为优先级 1.5 调用：
    - 优先级 1：直接 Token API（无 x5sec）
    - 优先级 1.5：方案 K 本地生成 x5sec（本函数，待逆向完成）
    - 优先级 2：x5sec 缓存注入（Redis）
    - 优先级 2.5：纯 HTTP x5sec 提取
    - 优先级 3：静默提取（浏览器）
    - 优先级 4：滑块求解（浏览器）

    逆向完成后，本函数应：
    1. 调用 generate_x5sec_locally 生成本地 x5sec
    2. 注入到 cookie
    3. 调用 Token API 验证
    4. 成功则返回 (accessToken, injected_cookie)

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值

    Returns:
        (accessToken, injected_cookie_str) — 成功时两个都有值；失败时两个都是 None
    """
    if not PLAN_K_ENABLED:
        return None, None

    if not cookie_str or not m_h5_tk:
        return None, None

    # 尝试本地生成 x5sec
    x5sec = generate_x5sec_locally(cookie_str, m_h5_tk)
    if not x5sec:
        logger.debug("[方案K] try_plan_k_x5sec: 本地生成 x5sec 失败（逆向未完成）")
        return None, None

    # 注入 x5sec 到 cookie
    try:
        from .x5sec_cache_client import inject_x5sec_into_cookie
        injected_cookie = inject_x5sec_into_cookie(cookie_str, x5sec)
        if not injected_cookie or injected_cookie == cookie_str:
            logger.warning("[方案K] try_plan_k_x5sec: x5sec 注入失败")
            return None, None
    except ImportError:
        logger.debug("[方案K] try_plan_k_x5sec: x5sec_cache_client 模块不可用")
        return None, None

    # 调用 Token API 验证（复用 ws_token._call_token_api）
    try:
        from .ws_token import _call_token_api, CAPTCHA_NEEDED
        result = _call_token_api(injected_cookie, m_h5_tk)
        if result == CAPTCHA_NEEDED:
            logger.warning("[方案K] try_plan_k_x5sec: 本地生成的 x5sec 被服务端拒绝（CAPTCHA_NEEDED）")
            return None, None
        elif result:
            logger.info("[方案K] try_plan_k_x5sec: ✓ 本地生成 x5sec 成功! accessToken 长度=%d", len(result))
            return result, injected_cookie
        else:
            logger.warning("[方案K] try_plan_k_x5sec: 注入本地 x5sec 后 Token API 返回空")
            return None, None
    except Exception as e:
        logger.warning("[方案K] try_plan_k_x5sec: 调用 Token API 失败: %s", e)
        return None, None


# ============================================================
# 5. 研究工具：从历史样本中提取模式
# ============================================================

def extract_x5sec_from_response_headers(set_cookie: str) -> Optional[str]:
    """从 Set-Cookie 头提取 x5sec 值（研究工具）。

    用于在 CAPTCHA 响应、首页响应等场景中提取 x5sec 样本。
    与 ws_token._call_token_api 中的提取逻辑一致，但本函数用于研究目的。

    Args:
        set_cookie: Set-Cookie 头值

    Returns:
        x5sec 值，或 None
    """
    if not set_cookie:
        return None
    match = re.search(r"x5sec=([^;]+)", set_cookie)
    if match and match.group(1):
        return match.group(1)
    return None


def is_x5sec_likely_valid(x5sec: str) -> bool:
    """启发式判断 x5sec 是否看起来有效（研究工具）。

    基于 x5sec 样本观察：
    - 有效 x5sec 长度通常 > 50
    - 通常是 base64 编码（含 A-Za-z0-9+/= 或 url-safe 变体）
    - 解码后长度 > 32

    Args:
        x5sec: x5sec 值

    Returns:
        True 表示可能是有效 x5sec
    """
    if not x5sec or len(x5sec) < 50:
        return False
    # 检查是否是 base64 字符集
    base64_pattern = re.compile(r"^[A-Za-z0-9+/=_-]+$")
    if not base64_pattern.match(x5sec):
        return False
    # 检查解码后长度
    analysis = analyze_x5sec_structure(x5sec)
    if analysis["decoded_length"] < 32:
        return False
    return True


# ============================================================
# 6. 多样本对比工具（离线研究）
# ============================================================

def load_samples_from_file(sample_file: str) -> list:
    """从 JSONL 样本文件加载所有样本。

    与 _persist_x5sec_sample 写入格式对应，用于离线分析。

    Args:
        sample_file: JSONL 文件路径

    Returns:
        样本列表，每个元素是一个 dict（含 ts/source/unb/x5sec/analysis 等字段）
    """
    samples: list = []
    if not sample_file or not os.path.exists(sample_file):
        return samples
    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                    if isinstance(sample, dict) and sample.get("x5sec"):
                        samples.append(sample)
                except Exception:
                    continue
    except Exception as e:
        logger.debug("[方案K] load_samples_from_file: 读取失败: %s", e)
    return samples


def compare_x5sec_samples(samples: list) -> Dict[str, Any]:
    """对比多个 x5sec 样本，识别固定字段与变化字段。

    这是方案 K 逆向的核心研究工具。通过对比大量样本，可以识别：
    - 长度是否固定（若固定，可能是定长加密结构）
    - 前缀是否固定（若固定，可能包含版本号或 magic bytes）
    - 哪些字节位置变化（变化区域可能含时间戳/随机数/签名）
    - 哪些字节位置固定（固定区域可能含算法标识/用户标识）

    分析结果用于指导后续逆向：
    - 若长度固定 + 前缀固定 → 可能是定长加密结构，需逆向加密算法
    - 若长度变化 → 可能含可变长度 payload（如 JSON）
    - 若前 N 字节固定 → 可能是结构头（magic + version + length）

    Args:
        samples: 样本列表（来自 load_samples_from_file）

    Returns:
        对比分析结果 dict：
        {
            "count": int,
            "lengths": {"min": int, "max": int, "unique": list, "is_fixed": bool},
            "prefix_hex_common": str,          # 所有样本共享的最长前缀（原始 base64 字符串，非解码 hex）
            "prefix_hex_common_len": int,      # 共享前缀字符数
            "suffix_hex_common": str,          # 所有样本共享的最长后缀（原始 base64 字符串）
            "byte_position_variance": list,    # 每个字节位置（解码后）的取值数量（1=固定，>1=变化）
            "fixed_byte_positions": int,       # 固定字节数（variance=1，仅定长时有值）
            "variable_byte_positions": int,    # 变化字节数（variance>1，仅定长时有值）
            "sources": dict,                   # 按来源统计
            "unbs": dict,                      # 按账号统计
        }

    注意：prefix_hex_common / suffix_hex_common 字段名保留历史命名，
    实际返回的是原始 x5sec 字符串（通常是 base64）的公共前/后缀，需解码后查看明文。
    """
    result: Dict[str, Any] = {
        "count": 0,
        "lengths": {"min": 0, "max": 0, "unique": [], "is_fixed": False},
        "prefix_hex_common": "",
        "prefix_hex_common_len": 0,
        "suffix_hex_common": "",
        "byte_position_variance": [],
        "fixed_byte_positions": 0,
        "variable_byte_positions": 0,
        "sources": {},
        "unbs": {},
    }

    if not samples:
        return result

    result["count"] = len(samples)

    # 统计来源与账号分布
    for s in samples:
        src = s.get("source", "unknown")
        result["sources"][src] = result["sources"].get(src, 0) + 1
        unb = s.get("unb", "unknown")
        result["unbs"][unb] = result["unbs"].get(unb, 0) + 1

    # 解码所有样本为 bytes
    decoded_list: list = []
    lengths: list = []
    for s in samples:
        x5sec = s.get("x5sec", "")
        try:
            cleaned = x5sec.replace("-", "+").replace("_", "/")
            padding = 4 - (len(cleaned) % 4)
            if padding != 4:
                cleaned = cleaned + "=" * padding
            decoded = base64.b64decode(cleaned, validate=False)
            decoded_list.append(decoded)
            lengths.append(len(decoded))
        except Exception:
            continue

    if not decoded_list:
        return result

    # 长度统计
    result["lengths"]["min"] = min(lengths)
    result["lengths"]["max"] = max(lengths)
    result["lengths"]["unique"] = sorted(set(lengths))
    result["lengths"]["is_fixed"] = len(set(lengths)) == 1

    # 共享前缀（基于原始 x5sec 字符串）
    x5sec_strs = [s.get("x5sec", "") for s in samples if s.get("x5sec")]
    if x5sec_strs:
        common_prefix = os.path.commonprefix(x5sec_strs)
        result["prefix_hex_common"] = common_prefix[:64]
        result["prefix_hex_common_len"] = len(common_prefix)

        # 共享后缀
        reversed_strs = [s[::-1] for s in x5sec_strs]
        common_suffix = os.path.commonprefix(reversed_strs)[::-1]
        result["suffix_hex_common"] = common_suffix[:64]

    # 字节位置方差分析（仅当所有样本长度一致时）
    if len(set(lengths)) == 1:
        fixed_len = lengths[0]
        # 每个字节位置的取值集合
        position_values: list = [set() for _ in range(fixed_len)]
        for decoded in decoded_list:
            for i in range(min(fixed_len, len(decoded))):
                position_values[i].add(decoded[i])

        variance_list: list = []
        fixed_count = 0
        variable_count = 0
        for i, vals in enumerate(position_values):
            v = len(vals)
            variance_list.append(v)
            if v == 1:
                fixed_count += 1
            else:
                variable_count += 1

        result["byte_position_variance"] = variance_list
        result["fixed_byte_positions"] = fixed_count
        result["variable_byte_positions"] = variable_count

    return result


def find_timestamp_in_x5sec(x5sec: str, reference_ts: Optional[int] = None) -> Dict[str, Any]:
    """在 x5sec 中寻找时间戳模式（研究工具）。

    x5sec 可能包含签发时间戳，用于服务端校验时效性。
    本函数尝试多种编码格式寻找时间戳：

    1. ASCII 数字串（10 位秒级 / 13 位毫秒级）
    2. 4 字节大端序 uint32（秒级时间戳）
    3. 8 字节大端序 uint64（毫秒级时间戳）
    4. JSON 字段中的 ts / timestamp / exp 字段

    Args:
        x5sec: x5sec 值
        reference_ts: 参考时间戳（秒），用于验证找到的时间戳是否合理
                      默认为当前时间

    Returns:
        分析结果 dict：
        {
            "found": bool,
            "matches": [
                {"encoding": "ascii_seconds", "value": 1700000000, "offset": 10,
                 "delta_from_ref": 0, "plausible": True},
                ...
            ],
        }
    """
    if reference_ts is None:
        reference_ts = int(time.time())

    result: Dict[str, Any] = {"found": False, "matches": []}

    if not x5sec:
        return result

    # 1. JSON 字段中的时间戳
    analysis = analyze_x5sec_structure(x5sec)
    if analysis["has_json_structure"]:
        try:
            cleaned = x5sec.replace("-", "+").replace("_", "/")
            padding = 4 - (len(cleaned) % 4)
            if padding != 4:
                cleaned = cleaned + "=" * padding
            decoded = base64.b64decode(cleaned, validate=False)
            parsed = json.loads(decoded.decode("utf-8", errors="replace"))
            if isinstance(parsed, dict):
                for field in ("ts", "timestamp", "exp", "t", "time", "created", "issued"):
                    if field in parsed and isinstance(parsed[field], (int, float)):
                        val = int(parsed[field])
                        # 判断秒级还是毫秒级
                        if val > 1e12:  # 13 位毫秒级
                            val_sec = val // 1000
                            delta = val_sec - reference_ts
                        else:
                            val_sec = val
                            delta = val - reference_ts
                        # 合理性判断：与参考时间差在 7 天内
                        plausible = abs(delta) < 7 * 24 * 3600
                        result["matches"].append({
                            "encoding": f"json_field:{field}",
                            "value": val,
                            "delta_from_ref": delta,
                            "plausible": plausible,
                        })
        except Exception:
            pass

    # 2. ASCII 数字串
    try:
        cleaned = x5sec.replace("-", "+").replace("_", "/")
        padding = 4 - (len(cleaned) % 4)
        if padding != 4:
            cleaned = cleaned + "=" * padding
        decoded = base64.b64decode(cleaned, validate=False)

        # 寻找 10 位数字串（秒级）
        ascii_str = decoded.decode("latin-1", errors="replace")
        for m in re.finditer(r"\d{10}", ascii_str):
            val = int(m.group())
            delta = val - reference_ts
            plausible = abs(delta) < 7 * 24 * 3600
            result["matches"].append({
                "encoding": "ascii_seconds",
                "value": val,
                "offset": m.start(),
                "delta_from_ref": delta,
                "plausible": plausible,
            })

        # 寻找 13 位数字串（毫秒级）
        for m in re.finditer(r"\d{13}", ascii_str):
            val = int(m.group())
            val_sec = val // 1000
            delta = val_sec - reference_ts
            plausible = abs(delta) < 7 * 24 * 3600
            result["matches"].append({
                "encoding": "ascii_millis",
                "value": val,
                "offset": m.start(),
                "delta_from_ref": delta,
                "plausible": plausible,
            })
    except Exception:
        pass

    # 3. 二进制大端序时间戳
    try:
        cleaned = x5sec.replace("-", "+").replace("_", "/")
        padding = 4 - (len(cleaned) % 4)
        if padding != 4:
            cleaned = cleaned + "=" * padding
        decoded = base64.b64decode(cleaned, validate=False)

        # 4 字节大端序 uint32（秒级）
        import struct
        for i in range(len(decoded) - 4):
            val = struct.unpack(">I", decoded[i:i + 4])[0]
            # 合理范围：2000-01-01 到 2100-01-01
            if 946684800 <= val <= 4102444800:
                delta = val - reference_ts
                plausible = abs(delta) < 7 * 24 * 3600
                result["matches"].append({
                    "encoding": "binary_be32",
                    "value": val,
                    "offset": i,
                    "delta_from_ref": delta,
                    "plausible": plausible,
                })
    except Exception:
        pass

    result["found"] = len(result["matches"]) > 0
    # 只保留 plausible 的前 10 个，避免结果过多
    plausible_matches = [m for m in result["matches"] if m.get("plausible")]
    result["matches"] = plausible_matches[:10]
    result["found"] = len(result["matches"]) > 0
    return result


def summarize_samples(sample_file: Optional[str] = None) -> Dict[str, Any]:
    """生成样本集摘要报告（离线研究工具）。

    加载指定 JSONL 文件（或当天默认文件），执行多样本对比与时间戳分析，
    返回结构化报告。可用于：
    - 评估样本数量是否足够（建议 > 50 个）
    - 识别 x5sec 结构是否固定长度
    - 识别固定/变化字节区域
    - 发现潜在时间戳字段

    Args:
        sample_file: JSONL 文件路径，None 时使用当天默认文件

    Returns:
        摘要报告 dict（含 count/lengths/prefix/variance/timestamp 等字段）
    """
    if sample_file is None:
        sample_dir = os.environ.get("PLAN_K_SAMPLE_DIR", "/tmp/x5sec_samples")
        date_str = time.strftime("%Y%m%d", time.localtime())
        sample_file = os.path.join(sample_dir, f"x5sec_samples_{date_str}.jsonl")

    samples = load_samples_from_file(sample_file)
    if not samples:
        return {
            "sample_file": sample_file,
            "count": 0,
            "message": "无样本或文件不存在",
        }

    comparison = compare_x5sec_samples(samples)

    # 对第一个样本做时间戳分析（代表性）
    first_sample = samples[0]
    ts_analysis = find_timestamp_in_x5sec(first_sample.get("x5sec", ""))

    return {
        "sample_file": sample_file,
        "count": comparison["count"],
        "sources": comparison["sources"],
        "unbs": comparison["unbs"],
        "lengths": comparison["lengths"],
        "prefix_hex_common": comparison["prefix_hex_common"],
        "prefix_hex_common_len": comparison["prefix_hex_common_len"],
        "suffix_hex_common": comparison["suffix_hex_common"],
        "fixed_byte_positions": comparison["fixed_byte_positions"],
        "variable_byte_positions": comparison["variable_byte_positions"],
        "timestamp_analysis_first_sample": ts_analysis,
        "recommendation": _research_recommendation(comparison),
    }


def _research_recommendation(comparison: Dict[str, Any]) -> str:
    """基于样本对比结果给出研究建议（内部工具）。"""
    count = comparison.get("count", 0)
    if count < 10:
        return f"样本量不足（{count} < 10），建议先收集更多样本再分析"

    lengths = comparison.get("lengths", {})
    is_fixed = lengths.get("is_fixed", False)
    fixed_bytes = comparison.get("fixed_byte_positions", 0)
    variable_bytes = comparison.get("variable_byte_positions", 0)

    if is_fixed:
        if fixed_bytes > variable_bytes:
            return f"定长结构（{lengths.get('min')} 字节），固定字节占比高（{fixed_bytes}/{fixed_bytes + variable_bytes}），可能含 magic+version 头，建议逆向固定区域"
        else:
            return f"定长结构（{lengths.get('min')} 字节），变化字节占比高（{variable_bytes}/{fixed_bytes + variable_bytes}），可能是加密 payload，建议逆向加密算法"
    else:
        return f"变长结构（{lengths.get('min')}-{lengths.get('max')} 字节），可能含可变长度 payload（如 JSON），建议分析长度分布"


# ============================================================
# 7. Baxia JS 逆向研究工具（方案 K 核心研究方向）
# ============================================================

# Baxia 相关的 JS 文件特征（用于从页面中识别）
BAXIA_JS_PATTERNS = [
    r"fireyejs",
    r"nocaptcha",
    r"baxia",
    r"x5sec",
    r"uab_collerr",
    r"aeis",
    r"awsc",
    r"nch5",
]

# 已知的 Baxia JS 端点（从公开资料和观察得到）
BAXIA_JS_ENDPOINTS = [
    "https://g.alicdn.com/sd/baxia/baxia.js",
    "https://g.alicdn.com/sd/nch5/index.js",
    "https://g.alicdn.com/AWSC/AWSC/awsc.js",
    "https://g.alicdn.com/sd/baxia-entry/baxiaCommon.js",
]

# 单个 JS 文件最大下载字节数（避免下载超大文件耗尽内存）
# 200KB 足以覆盖绝大多数 Baxia JS 文件
MAX_JS_DOWNLOAD_BYTES = 200_000

# JS 代码深度分析关键词（用于在完整 JS 中定位 x5sec 生成逻辑）
# 这些关键词基于公开的 Baxia/FireyeJS 逆向资料
DEEP_ANALYSIS_KEYWORDS = [
    "x5sec",
    "x5secdata",
    "setCookie",
    "document.cookie",
    "getToken",
    "setData",
    "getData",
    "_nc",
    "ncToken",
    "sessionId",
    "baxia_token",
    "fireye",
    "aeis",
    "uab_collerr",
    "punish",
    "validate",
    "captcha",
    "slider",
    "behavior",
    "fingerprint",
    "deviceFingerprint",
    "collect",
    "report",
    "sign",
    "encrypt",
    "decrypt",
    "base64",
    "btoa",
    "atob",
    "JSON.stringify",
    "JSON.parse",
]


def fetch_homepage_and_extract_baxia_js(cookie_str: str = "") -> Dict[str, Any]:
    """访问闲鱼首页，提取 Baxia 相关的 JS 脚本和配置。

    方案 K 核心研究方向：通过分析 Baxia JS 代码，逆向 x5sec 生成逻辑。

    本函数：
    1. 访问 https://www.goofish.com/ 首页
    2. 从 HTML 中提取所有 <script> 标签的 src
    3. 筛选 Baxia 相关的 JS 文件
    4. 下载并分析这些 JS 文件
    5. 提取 x5sec 生成相关的代码片段

    Args:
        cookie_str: Cookie 字符串（可选，空字符串表示匿名访问）

    Returns:
        分析结果 dict：
        {
            "homepage_status": int,
            "script_sources": list,       # 所有 script src
            "baxia_scripts": list,        # Baxia 相关的 script src
            "baxia_js_contents": dict,    # {url: content_prefix}
            "x5sec_related_code": list,   # 包含 x5sec 关键词的代码片段
            "set_cookies": str,           # 首页 Set-Cookie 头
            "x5sec_from_homepage": str,   # 首页直接下发的 x5sec（如有）
        }
    """
    result: Dict[str, Any] = {
        "homepage_status": 0,
        "script_sources": [],
        "baxia_scripts": [],
        "baxia_js_contents": {},
        "x5sec_related_code": [],
        "set_cookies": "",
        "x5sec_from_homepage": "",
    }

    try:
        import requests as _requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        # 1. 访问首页
        resp = _requests.get("https://www.goofish.com/", headers=headers, timeout=15, allow_redirects=True)
        result["homepage_status"] = resp.status_code
        result["set_cookies"] = resp.headers.get("set-cookie", "")

        # 检查首页是否直接下发 x5sec
        x5sec_match = re.search(r"x5sec=([^;]+)", result["set_cookies"])
        if x5sec_match:
            result["x5sec_from_homepage"] = x5sec_match.group(1)
            logger.info("[方案K] 首页直接下发 x5sec（长度=%d）", len(result["x5sec_from_homepage"]))

        # 2. 从 HTML 提取所有 script src
        html = resp.text
        script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        result["script_sources"] = script_srcs

        # 3. 筛选 Baxia 相关的 JS
        for src in script_srcs:
            src_lower = src.lower()
            for pattern in BAXIA_JS_PATTERNS:
                if re.search(pattern, src_lower):
                    result["baxia_scripts"].append(src)
                    break

        # 同时检查已知的 Baxia JS 端点
        for endpoint in BAXIA_JS_ENDPOINTS:
            if endpoint not in result["baxia_scripts"]:
                # 检查 HTML 中是否引用了这些端点
                if endpoint in html or endpoint.split("/")[-1] in html:
                    result["baxia_scripts"].append(endpoint)

        logger.info(
            "[方案K] 首页分析：status=%d scripts=%d baxia_scripts=%d",
            resp.status_code,
            len(script_srcs),
            len(result["baxia_scripts"]),
        )

        # 4. 下载并分析 Baxia JS 文件（下载完整内容，便于深度分析）
        # 优化：原版只取前 5000 字符，遗漏了 x5sec 生成逻辑（JS 文件通常 50KB+）
        for js_url in result["baxia_scripts"][:5]:  # 最多分析 5 个
            try:
                # 确保 URL 是完整的
                if js_url.startswith("//"):
                    js_url = "https:" + js_url
                elif js_url.startswith("/"):
                    js_url = "https://www.goofish.com" + js_url

                js_resp = _requests.get(js_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "*/*",
                    "Referer": "https://www.goofish.com/",
                }, timeout=15)
                if js_resp.status_code == 200:
                    # 下载完整内容（限制最大字节数避免内存爆炸）
                    content = js_resp.text[:MAX_JS_DOWNLOAD_BYTES]
                    result["baxia_js_contents"][js_url] = content
                    logger.info(
                        "[方案K] 下载 JS 完成：%s (长度=%d)",
                        js_url,
                        len(content),
                    )

                    # 5. 深度提取 x5sec 相关代码片段
                    # 5.1 搜索 x5sec 关键词附近的代码（扩大上下文窗口至 500 字符）
                    for match in re.finditer(r'x5sec', content, re.IGNORECASE):
                        start = max(0, match.start() - 200)
                        end = min(len(content), match.end() + 500)
                        snippet = content[start:end]
                        result["x5sec_related_code"].append({
                            "url": js_url,
                            "offset": match.start(),
                            "snippet": snippet,
                            "type": "x5sec",
                        })

                    # 5.2 搜索 sign 生成相关代码
                    for match in re.finditer(r'(function\s*\w*sign|sign\s*[:=]\s*function|\.sign\s*=)', content):
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 500)
                        snippet = content[start:end]
                        result["x5sec_related_code"].append({
                            "url": js_url,
                            "offset": match.start(),
                            "snippet": snippet,
                            "type": "sign_function",
                        })

                    # 5.3 搜索 setCookie / document.cookie 相关代码
                    # （x5sec 通常通过 document.cookie 写入）
                    for match in re.finditer(r'(document\.cookie|setCookie|set_cookie)', content):
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 400)
                        snippet = content[start:end]
                        result["x5sec_related_code"].append({
                            "url": js_url,
                            "offset": match.start(),
                            "snippet": snippet,
                            "type": "cookie_write",
                        })

                    # 5.4 搜索 getToken / setData / getData 相关代码
                    # （FireyeJS 的核心数据收集 API）
                    for match in re.finditer(r'(getToken|setData|getData|baxia_token|ncToken)', content):
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 400)
                        snippet = content[start:end]
                        result["x5sec_related_code"].append({
                            "url": js_url,
                            "offset": match.start(),
                            "snippet": snippet,
                            "type": "token_api",
                        })

                    # 5.5 搜索 encrypt/encrypt/base64 相关代码
                    # （x5sec 可能通过加密算法生成）
                    for match in re.finditer(r'(encrypt|decrypt|btoa|atob|base64)', content, re.IGNORECASE):
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 400)
                        snippet = content[start:end]
                        result["x5sec_related_code"].append({
                            "url": js_url,
                            "offset": match.start(),
                            "snippet": snippet,
                            "type": "crypto",
                        })

                    # 5.6 搜索 punish / validate / captcha 相关代码
                    # （Baxia 风控流程关键词）
                    for match in re.finditer(r'(punish|validate|captcha|slider|behavior)', content, re.IGNORECASE):
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 400)
                        snippet = content[start:end]
                        result["x5sec_related_code"].append({
                            "url": js_url,
                            "offset": match.start(),
                            "snippet": snippet,
                            "type": "baxia_flow",
                        })
            except Exception as e:
                logger.warning("[方案K] 下载 JS 失败 %s: %s", js_url, e)

    except Exception as e:
        logger.warning("[方案K] fetch_homepage_and_extract_baxia_js 失败: %s", e)
        result["error"] = str(e)

    return result


def analyze_baxia_js_structure(js_content: str) -> Dict[str, Any]:
    """分析 Baxia JS 代码结构，识别 x5sec 生成相关的函数和算法。

    增强：支持完整 JS 文件的深度分析，统计所有关键词出现次数，
    并提取函数边界用于后续逆向。

    Args:
        js_content: JS 代码内容

    Returns:
        分析结果 dict
    """
    result: Dict[str, Any] = {
        "length": len(js_content) if js_content else 0,
        "has_x5sec_reference": False,
        "x5sec_occurrences": 0,
        "has_sign_function": False,
        "has_hmac": False,
        "has_aes": False,
        "has_base64": False,
        "has_md5": False,
        "has_fireyejs": False,
        "has_nocaptcha": False,
        "function_names": [],
        "crypto_indicators": [],
        # 新增：深度分析字段
        "keyword_occurrences": {},       # 每个关键词的出现次数
        "is_minified": False,            # 是否压缩混淆
        "avg_function_name_length": 0,   # 平均函数名长度（压缩后通常 1-2 字符）
        "function_count": 0,             # 函数总数
        "eval_usage_count": 0,           # eval 使用次数（混淆指示器）
        "string_constant_count": 0,      # 字符串常量数量
        "has_set_cookie": False,         # 是否包含 document.cookie 写入
        "has_get_token": False,          # 是否包含 getToken 调用
        "has_punish_handler": False,     # 是否包含 punish 处理逻辑
    }

    if not js_content:
        return result

    # 统计 x5sec 出现次数
    x5sec_matches = re.findall(r'x5sec', js_content, re.IGNORECASE)
    result["x5sec_occurrences"] = len(x5sec_matches)
    result["has_x5sec_reference"] = len(x5sec_matches) > 0

    # 检查加密相关关键词
    crypto_patterns = {
        "has_sign_function": r'(function\s*\w*sign|sign\s*[:=]\s*function|\.sign\s*=)',
        "has_hmac": r'(hmac|HMAC|createHmac)',
        "has_aes": r'(aes|AES|createCipher|createDecipher)',
        "has_base64": r'(base64|btoa|atob|Base64)',
        "has_md5": r'(md5|MD5|createHash)',
        "has_fireyejs": r'(fireyejs|FireyeJS|fireye)',
        "has_nocaptcha": r'(nocaptcha|NoCaptcha|noCaptcha)',
    }

    for key, pattern in crypto_patterns.items():
        if re.search(pattern, js_content):
            result[key] = True
            result["crypto_indicators"].append(key.replace("has_", ""))

    # 提取函数名
    func_matches = re.findall(r'function\s+(\w+)', js_content)
    result["function_names"] = list(set(func_matches))[:30]  # 去重，最多 30 个
    result["function_count"] = len(func_matches)

    # ===== 新增：深度关键词统计 =====
    for kw in DEEP_ANALYSIS_KEYWORDS:
        # 使用单词边界匹配，避免子串误匹配
        count = len(re.findall(re.escape(kw), js_content, re.IGNORECASE))
        if count > 0:
            result["keyword_occurrences"][kw] = count

    # 关键功能标记
    result["has_set_cookie"] = bool(re.search(r'document\.cookie\s*=', js_content))
    result["has_get_token"] = bool(re.search(r'getToken\s*\(', js_content))
    result["has_punish_handler"] = bool(re.search(r'punish', js_content, re.IGNORECASE))

    # ===== 新增：JS 混淆/压缩检测 =====
    # 压缩 JS 的特征：
    # 1. 函数名很短（1-2 字符）
    # 2. eval 使用频繁
    # 3. 文件密度高（字符数/行数比高）
    result["eval_usage_count"] = len(re.findall(r'\beval\s*\(', js_content))
    result["string_constant_count"] = len(re.findall(r'"[^"]{3,}"|\'[^\'\"]{3,}\'', js_content))

    # 计算平均函数名长度
    if func_matches:
        unique_names = list(set(func_matches))
        avg_len = sum(len(n) for n in unique_names) / len(unique_names)
        result["avg_function_name_length"] = round(avg_len, 2)
        # 平均函数名长度 < 3 且函数数 > 50 → 很可能是压缩混淆
        if avg_len < 3 and len(func_matches) > 50:
            result["is_minified"] = True

    return result


# ============================================================
# 8. x5sec 生成算法研究框架（基于公开资料）
# ============================================================

# 基于公开资料和社区研究的 x5sec 结构假设
# x5sec 可能的结构（待验证）：
# 1. base64(json({uid, ts, sign, ...}))
# 2. base64(encrypted_payload)
# 3. 自定义二进制格式
X5SEC_STRUCTURE_HYPOTHESES = {
    "h1_json_base64": "x5sec = base64(json({uid, ts, sign, v, ...}))",
    "h2_encrypted": "x5sec = base64(aes_encrypt(json_payload, key))",
    "h3_custom_binary": "x5sec = base64(magic + version + length + payload + checksum)",
    "h4_hybrid": "x5sec = base64(header + encrypted_body)",
}


def try_generate_x5sec_from_template(
    cookie_str: str,
    m_h5_tk: str,
    template_x5sec: Optional[str] = None,
) -> Optional[str]:
    """基于模板的 x5sec 生成尝试（研究阶段）。

    思路：如果有一个有效的 x5sec 样本，尝试替换其中的时间戳字段，
    看是否能生成新的有效 x5sec。

    **当前状态：研究阶段，仅做结构分析，不实际生成**

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值
        template_x5sec: 模板 x5sec（来自历史样本）

    Returns:
        生成的 x5sec 值，或 None（当前始终返回 None）
    """
    if not PLAN_K_ENABLED:
        return None

    if not template_x5sec:
        logger.debug("[方案K] try_generate_x5sec_from_template: 无模板样本")
        return None

    # 分析模板结构
    analysis = analyze_x5sec_structure(template_x5sec)
    logger.info(
        "[方案K] 模板分析：length=%d is_base64=%s has_json=%s encrypted=%s",
        analysis["length"],
        analysis["is_base64"],
        analysis["has_json_structure"],
        analysis["looks_like_encrypted"],
    )

    # 假设 1：如果是 JSON 结构，尝试替换时间戳
    if analysis["has_json_structure"]:
        try:
            cleaned = template_x5sec.replace("-", "+").replace("_", "/")
            padding = 4 - (len(cleaned) % 4)
            if padding != 4:
                cleaned = cleaned + "=" * padding
            decoded = base64.b64decode(cleaned, validate=False)
            parsed = json.loads(decoded.decode("utf-8", errors="replace"))

            if isinstance(parsed, dict):
                logger.info("[方案K] JSON 结构字段：%s", list(parsed.keys()))

                # 尝试替换时间戳字段
                current_ts = int(time.time())
                modified = False
                for ts_field in ["ts", "timestamp", "exp", "t", "time"]:
                    if ts_field in parsed:
                        old_val = parsed[ts_field]
                        # 判断秒级还是毫秒级
                        if isinstance(old_val, (int, float)) and old_val > 1e12:
                            parsed[ts_field] = current_ts * 1000
                        else:
                            parsed[ts_field] = current_ts
                        modified = True
                        logger.info("[方案K] 替换 %s: %s -> %s", ts_field, old_val, parsed[ts_field])

                if modified:
                    # 重新编码
                    new_json = json.dumps(parsed, separators=(",", ":"))
                    new_x5sec = base64.b64encode(new_json.encode()).decode()
                    logger.info("[方案K] 基于模板生成新 x5sec（长度=%d）", len(new_x5sec))
                    # 注意：这里生成的 x5sec 大概率无效，因为缺少正确的签名
                    # 仅用于研究目的，验证服务端的校验逻辑
                    return new_x5sec
        except Exception as e:
            logger.debug("[方案K] JSON 模板处理失败: %s", e)

    # 假设 2：如果是加密结构，需要逆向加密算法
    if analysis["looks_like_encrypted"]:
        logger.info("[方案K] x5sec 看起来是加密结构，需要逆向加密算法（未实现）")
        # TODO: 逆向 Baxia 的加密算法后填充

    return None


def capture_x5sec_via_browser(
    cookie_str: str,
    target_url: str = "https://www.goofish.com/",
) -> Dict[str, Any]:
    """通过 crawler-service 浏览器捕获 x5sec 生成过程。

    调用 crawler-service 的浏览器访问目标页面，捕获：
    1. 所有 Set-Cookie 中的 x5sec
    2. Baxia JS 的执行日志
    3. 网络请求中的 x5sec

    这是收集 x5sec 样本的最可靠方式，因为浏览器会完整执行 Baxia JS。

    Args:
        cookie_str: Cookie 字符串
        target_url: 目标 URL（默认闲鱼首页）

    Returns:
        捕获结果 dict：
        {
            "success": bool,
            "x5sec_samples": list,    # 捕获到的 x5sec 列表
            "baxia_js_executed": bool,
            "network_x5sec": list,    # 网络请求中的 x5sec
            "cookie_x5sec": list,     # Cookie 中的 x5sec
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "x5sec_samples": [],
        "baxia_js_executed": False,
        "network_x5sec": [],
        "cookie_x5sec": [],
    }

    try:
        import requests as _requests

        # crawler-service 的浏览器接口
        crawler_url = os.environ.get("CRAWLER_SERVICE_URL", "http://crawler-service:3001")

        # 调用 crawler-service 的 x5sec 捕获接口
        # 注意：这个接口需要在 crawler-service 中实现
        capture_endpoint = f"{crawler_url}/api/capture-x5sec"

        payload = {
            "cookie": cookie_str,
            "target_url": target_url,
        }

        internal_token = os.environ.get("INTERNAL_API_TOKEN", "")
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": internal_token,
        }

        resp = _requests.post(capture_endpoint, json=payload, headers=headers, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            result["success"] = data.get("success", False)
            result["x5sec_samples"] = data.get("x5sec_samples", [])
            result["baxia_js_executed"] = data.get("baxia_js_executed", False)
            result["network_x5sec"] = data.get("network_x5sec", [])
            result["cookie_x5sec"] = data.get("cookie_x5sec", [])

            logger.info(
                "[方案K] 浏览器捕获 x5sec：success=%s samples=%d",
                result["success"],
                len(result["x5sec_samples"]),
            )
        else:
            logger.warning("[方案K] crawler-service x5sec 捕获接口返回 %d", resp.status_code)
            result["error"] = f"HTTP {resp.status_code}"

    except Exception as e:
        logger.warning("[方案K] capture_x5sec_via_browser 失败: %s", e)
        result["error"] = str(e)

    return result


def research_x5sec_generation_algorithm(cookie_str: str, m_h5_tk: str) -> Dict[str, Any]:
    """方案 K 核心研究函数：综合分析 x5sec 生成算法。

    增强：整合完整 JS 下载、深度关键词统计、混淆检测、
    并按代码片段类型分类整理，便于人工逆向。

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值

    Returns:
        综合分析结果 dict
    """
    result: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "steps": {},
        "findings": [],
        "recommendations": [],
        # 新增：按类型分类的代码片段
        "code_snippets_by_type": {},
        # 新增：JS 文件摘要
        "js_files_summary": [],
    }

    # 步骤 1：从首页提取 Baxia JS（下载完整内容）
    logger.info("[方案K] 研究步骤 1：提取 Baxia JS（完整下载）")
    homepage_analysis = fetch_homepage_and_extract_baxia_js(cookie_str)
    result["steps"]["homepage_analysis"] = {
        "status": homepage_analysis.get("homepage_status"),
        "script_count": len(homepage_analysis.get("script_sources", [])),
        "baxia_script_count": len(homepage_analysis.get("baxia_scripts", [])),
        "baxia_scripts": homepage_analysis.get("baxia_scripts", []),
        "x5sec_from_homepage": bool(homepage_analysis.get("x5sec_from_homepage")),
        "x5sec_related_code_count": len(homepage_analysis.get("x5sec_related_code", [])),
    }

    if homepage_analysis.get("x5sec_from_homepage"):
        result["findings"].append({
            "type": "x5sec_from_homepage",
            "message": "首页直接下发 x5sec，无需 Baxia 验证",
            "value_length": len(homepage_analysis["x5sec_from_homepage"]),
        })

    # 步骤 2：分析 Baxia JS 代码结构（完整内容）
    logger.info("[方案K] 研究步骤 2：分析 Baxia JS 代码结构（完整内容深度分析）")
    baxia_analysis_results = []
    for js_url, js_content in homepage_analysis.get("baxia_js_contents", {}).items():
        analysis = analyze_baxia_js_structure(js_content)
        analysis["url"] = js_url
        baxia_analysis_results.append(analysis)

        # 生成 JS 文件摘要
        js_summary = {
            "url": js_url,
            "length": analysis["length"],
            "is_minified": analysis["is_minified"],
            "function_count": analysis["function_count"],
            "avg_function_name_length": analysis["avg_function_name_length"],
            "x5sec_occurrences": analysis["x5sec_occurrences"],
            "has_x5sec_reference": analysis["has_x5sec_reference"],
            "crypto_indicators": analysis["crypto_indicators"],
            "keyword_occurrences": analysis["keyword_occurrences"],
            "has_set_cookie": analysis["has_set_cookie"],
            "has_get_token": analysis["has_get_token"],
            "has_punish_handler": analysis["has_punish_handler"],
        }
        result["js_files_summary"].append(js_summary)

        if analysis["has_x5sec_reference"]:
            result["findings"].append({
                "type": "x5sec_in_js",
                "message": f"JS {js_url} 中包含 x5sec 引用（{analysis['x5sec_occurrences']} 次）",
                "url": js_url,
                "occurrences": analysis["x5sec_occurrences"],
            })

        if analysis["has_sign_function"]:
            result["findings"].append({
                "type": "sign_function",
                "message": f"JS {js_url} 中包含签名函数",
                "url": js_url,
            })

        if analysis["has_set_cookie"]:
            result["findings"].append({
                "type": "cookie_write",
                "message": f"JS {js_url} 中包含 document.cookie 写入操作",
                "url": js_url,
            })

        if analysis["has_get_token"]:
            result["findings"].append({
                "type": "token_api",
                "message": f"JS {js_url} 中包含 getToken 调用",
                "url": js_url,
            })

        if analysis["has_punish_handler"]:
            result["findings"].append({
                "type": "punish_handler",
                "message": f"JS {js_url} 中包含 punish 处理逻辑",
                "url": js_url,
            })

        if analysis["is_minified"]:
            result["findings"].append({
                "type": "minified_js",
                "message": f"JS {js_url} 已压缩混淆（平均函数名长度={analysis['avg_function_name_length']}，函数数={analysis['function_count']}）",
                "url": js_url,
            })

    result["steps"]["baxia_js_analysis"] = baxia_analysis_results

    # 步骤 3：分析 x5sec 相关代码片段（按类型分类）
    x5sec_code_snippets = homepage_analysis.get("x5sec_related_code", [])

    # 按类型分组
    snippets_by_type: Dict[str, list] = {}
    for snippet in x5sec_code_snippets:
        snippet_type = snippet.get("type", "unknown")
        if snippet_type not in snippets_by_type:
            snippets_by_type[snippet_type] = []
        snippets_by_type[snippet_type].append({
            "url": snippet.get("url"),
            "offset": snippet.get("offset"),
            "snippet": snippet.get("snippet", "")[:500],  # 限制单片段长度
        })
    result["code_snippets_by_type"] = snippets_by_type

    result["steps"]["x5sec_code_analysis"] = {
        "total_snippet_count": len(x5sec_code_snippets),
        "type_distribution": {k: len(v) for k, v in snippets_by_type.items()},
        # 每种类型最多展示 3 个片段（避免报告过大）
        "samples": {
            t: items[:3] for t, items in snippets_by_type.items()
        },
    }

    # 步骤 4：给出研究建议（基于完整分析）
    if not baxia_analysis_results:
        result["recommendations"].append("未找到 Baxia JS 文件，可能需要通过浏览器执行才能触发")
    else:
        has_encrypted = any(
            a.get("has_aes") or a.get("looks_like_encrypted")
            for a in baxia_analysis_results
        )
        has_sign = any(a.get("has_sign_function") for a in baxia_analysis_results)
        has_x5sec_ref = any(a.get("has_x5sec_reference") for a in baxia_analysis_results)
        has_cookie_write = any(a.get("has_set_cookie") for a in baxia_analysis_results)
        has_token_api = any(a.get("has_get_token") for a in baxia_analysis_results)
        all_minified = all(a.get("is_minified") for a in baxia_analysis_results)

        if has_x5sec_ref:
            result["recommendations"].append(
                "✓ 检测到 x5sec 引用：建议优先分析 x5sec 类型代码片段，"
                "定位 x5sec 变量赋值位置，回溯生成函数"
            )
        else:
            result["recommendations"].append(
                "✗ 未在任何 Baxia JS 中检测到 x5sec 关键词："
                "x5sec 生成逻辑可能 (a) 在动态加载的子模块中，"
                "(b) 在服务端生成而非客户端，(c) 使用了完全混淆的变量名"
            )

        if has_encrypted:
            result["recommendations"].append(
                "检测到加密算法（AES）：x5sec 可能使用对称加密，"
                "需逆向密钥（通常硬编码在 JS 中或从 cookie 派生）"
            )
        if has_sign:
            result["recommendations"].append(
                "检测到签名函数：x5sec 可能包含 HMAC 签名，"
                "需逆向签名算法和密钥来源"
            )
        if has_cookie_write:
            result["recommendations"].append(
                "检测到 document.cookie 写入：建议分析 cookie_write 类型代码片段，"
                "定位 x5sec 写入 cookie 的具体代码路径"
            )
        if has_token_api:
            result["recommendations"].append(
                "检测到 getToken 调用：建议分析 token_api 类型代码片段，"
                "FireyeJS 的 getToken 可能返回 x5sec"
            )
        if all_minified:
            result["recommendations"].append(
                "所有 Baxia JS 都已压缩混淆：建议使用浏览器开发者工具"
                "断点调试，或在 crawler-service 中注入未压缩版本"
            )
        if not has_encrypted and not has_sign and not has_x5sec_ref:
            result["recommendations"].append(
                "未检测到明显算法特征：可能使用了自定义混淆算法，"
                "建议通过 crawler-service 浏览器捕获 Baxia JS 的运行时行为"
            )

    result["recommendations"].append(
        "建议通过 crawler-service 浏览器捕获完整的 x5sec 生成过程，"
        "使用断点调试在 document.cookie 写入时回溯调用栈"
    )

    return result


# ============================================================
# 9. 研究结果持久化（便于跨会话分析）
# ============================================================

def save_research_report(report: Dict[str, Any], report_type: str = "analysis") -> Optional[str]:
    """保存研究报告到文件，便于跨会话分析。

    Args:
        report: 报告内容 dict
        report_type: 报告类型（analysis / baxia_js / sample_comparison）

    Returns:
        保存的文件路径，或 None
    """
    try:
        sample_dir = os.environ.get("PLAN_K_SAMPLE_DIR", "/tmp/x5sec_samples")
        os.makedirs(sample_dir, exist_ok=True)

        timestamp = int(time.time())
        date_str = time.strftime("%Y%m%d", time.localtime())
        filename = f"research_{report_type}_{date_str}_{timestamp}.json"
        filepath = os.path.join(sample_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("[方案K] 研究报告已保存：%s", filepath)
        return filepath
    except Exception as e:
        logger.warning("[方案K] 保存研究报告失败: %s", e)
        return None


# ============================================================
# 10. Baxia 服务端端点分析（路线 C：直接调用 Baxia 验证端点）
# ============================================================

# 已知的 Baxia / 阿里风控相关端点（从 JS 代码和公开资料收集）
BAXIA_ENDPOINTS = {
    "fourier_taobao": {
        "url": "https://fourier.taobao.com/rp",
        "description": "FireyeJS 行为数据上报端点（采集鼠标/键盘/设备指纹）",
        "method": "GET",
        "params": ["ext", "data", "random", "href", "protocol", "callback"],
    },
    "fourier_taobao_assist": {
        "url": "https://fourier.taobao.com/assist",
        "description": "FireyeJS 辅助端点（用途待确认）",
        "method": "GET",
    },
    "gm_mmstat": {
        "url": "https://gm.mmstat.com/fsp.1.1",
        "description": "Baxia punish 上报端点（风控触发时上报）",
        "method": "GET",
        "params": ["code", "msg", "pid", "page", "query", "hash", "referrer",
                   "title", "ua", "c1", "c2"],
    },
    "nocaptcha_check": {
        "url": "https://h5api.m.goofish.com/h5/mtop.taobao.idle.user.validate/1.0/",
        "description": "NoCaptcha 验证端点（可能下发 x5sec）",
        "method": "POST",
    },
}


def extract_baxia_endpoints_from_js(js_content: str) -> Dict[str, list]:
    """从 Baxia JS 代码中提取所有服务端端点 URL。

    路线 C 的核心研究工具：找到 Baxia 与服务端交互的所有端点，
    分析哪些端点可能下发 x5sec。

    提取的 URL 模式：
    - https://*.taobao.com/*
    - https://*.mmstat.com/*
    - https://*.alicdn.com/sd/*
    - https://h5api.m.goofish.com/*
    - /punish, /validate 等路径

    Args:
        js_content: JS 代码内容

    Returns:
        按域名分组的 URL 列表：
        {
            "taobao.com": ["https://fourier.taobao.com/rp?...", ...],
            "mmstat.com": ["https://gm.mmstat.com/fsp.1.1?...", ...],
            ...
        }
    """
    result: Dict[str, list] = {}

    if not js_content:
        return result

    # URL 正则：匹配 https:// 和 // 开头的 URL
    url_patterns = [
        r'https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9\-_\.?=&%]+)?',
        r'//[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9\-_\.?=&%]+)?',
    ]

    seen_urls = set()
    for pattern in url_patterns:
        for match in re.finditer(pattern, js_content):
            url = match.group()
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 提取域名
            domain_match = re.search(r'(?:https?:)?//([a-zA-Z0-9\-\.]+)', url)
            if domain_match:
                domain = domain_match.group(1)
                if domain not in result:
                    result[domain] = []
                # 限制 URL 长度避免过长
                result[domain].append(url[:200])

    # 同时搜索相对路径（/punish, /validate 等）
    relative_path_patterns = [
        r'["\'](/[a-zA-Z][a-zA-Z0-9\-_]*(?:/[a-zA-Z0-9\-_]+)*)["\']',
    ]
    for pattern in relative_path_patterns:
        for match in re.finditer(pattern, js_content):
            path = match.group(1)
            # 过滤掉明显的静态资源路径
            if any(path.endswith(ext) for ext in [".js", ".css", ".png", ".jpg", ".ico"]):
                continue
            # 只保留可能与风控相关的路径
            if any(kw in path.lower() for kw in ["punish", "validate", "captcha", "verify", "check", "token", "x5sec"]):
                if "relative_paths" not in result:
                    result["relative_paths"] = []
                if path not in result["relative_paths"]:
                    result["relative_paths"].append(path)

    return result


def analyze_baxia_endpoint(
    endpoint_url: str,
    cookie_str: str = "",
    method: str = "GET",
) -> Dict[str, Any]:
    """分析单个 Baxia 端点的响应（研究工具）。

    本函数用于探测 Baxia 端点的行为：
    - 是否返回 x5sec（在 Set-Cookie 或响应体中）
    - 返回的状态码和内容
    - 是否触发重定向到验证页面

    **注意**：本函数仅用于研究目的，不会自动重试或注入 x5sec。
    生产环境的 x5sec 获取应通过 ws_token.py 的优先级链。

    Args:
        endpoint_url: 端点 URL
        cookie_str: Cookie 字符串（可选）
        method: HTTP 方法（GET / POST）

    Returns:
        分析结果 dict：
        {
            "url": str,
            "method": str,
            "status_code": int,
            "response_length": int,
            "set_cookie": str,
            "x5sec_in_set_cookie": str,
            "x5sec_in_body": bool,
            "response_preview": str,
            "error": str,
        }
    """
    result: Dict[str, Any] = {
        "url": endpoint_url,
        "method": method,
        "status_code": 0,
        "response_length": 0,
        "set_cookie": "",
        "x5sec_in_set_cookie": "",
        "x5sec_in_body": False,
        "response_preview": "",
        "error": "",
    }

    try:
        import requests as _requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.goofish.com/",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        if method.upper() == "GET":
            resp = _requests.get(endpoint_url, headers=headers, timeout=10, allow_redirects=False)
        else:
            resp = _requests.post(endpoint_url, headers=headers, timeout=10, allow_redirects=False)

        result["status_code"] = resp.status_code
        result["response_length"] = len(resp.text)
        result["set_cookie"] = resp.headers.get("set-cookie", "")

        # 检查 Set-Cookie 中的 x5sec
        x5sec_match = re.search(r"x5sec=([^;]+)", result["set_cookie"])
        if x5sec_match:
            result["x5sec_in_set_cookie"] = x5sec_match.group(1)
            logger.info(
                "[方案K] 端点 %s 返回 x5sec（长度=%d）",
                endpoint_url,
                len(result["x5sec_in_set_cookie"]),
            )

        # 检查响应体中的 x5sec
        if "x5sec" in resp.text:
            result["x5sec_in_body"] = True
            logger.info("[方案K] 端点 %s 响应体包含 x5sec 关键词", endpoint_url)

        result["response_preview"] = resp.text[:500]

    except Exception as e:
        result["error"] = str(e)
        logger.debug("[方案K] 分析端点 %s 失败: %s", endpoint_url, e)

    return result


def research_baxia_endpoints(cookie_str: str = "") -> Dict[str, Any]:
    """路线 C 核心研究函数：综合分析 Baxia 服务端端点。

    本函数整合端点提取和探测：
    1. 从 Baxia JS 中提取所有服务端端点
    2. 探测已知端点的响应行为
    3. 识别可能下发 x5sec 的端点

    Args:
        cookie_str: Cookie 字符串（可选）

    Returns:
        综合分析结果 dict
    """
    result: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "endpoints_from_js": {},
        "endpoint_probes": [],
        "findings": [],
        "recommendations": [],
    }

    # 步骤 1：从首页 JS 提取端点
    logger.info("[方案K-路线C] 步骤 1：从 Baxia JS 提取服务端端点")
    homepage_analysis = fetch_homepage_and_extract_baxia_js(cookie_str)

    all_endpoints: Dict[str, list] = {}
    for js_url, js_content in homepage_analysis.get("baxia_js_contents", {}).items():
        endpoints = extract_baxia_endpoints_from_js(js_content)
        for domain, urls in endpoints.items():
            if domain not in all_endpoints:
                all_endpoints[domain] = []
            for url in urls:
                if url not in all_endpoints[domain]:
                    all_endpoints[domain].append(url)

    result["endpoints_from_js"] = all_endpoints

    # 步骤 2：探测已知端点
    logger.info("[方案K-路线C] 步骤 2：探测已知 Baxia 端点")
    for name, info in BAXIA_ENDPOINTS.items():
        probe_result = analyze_baxia_endpoint(
            info["url"],
            cookie_str=cookie_str,
            method=info.get("method", "GET"),
        )
        probe_result["endpoint_name"] = name
        probe_result["description"] = info.get("description", "")
        result["endpoint_probes"].append(probe_result)

        if probe_result["x5sec_in_set_cookie"]:
            result["findings"].append({
                "type": "x5sec_endpoint",
                "message": f"端点 {name} ({info['url']}) 返回了 x5sec！",
                "endpoint": info["url"],
                "x5sec_length": len(probe_result["x5sec_in_set_cookie"]),
            })

    # 步骤 3：给出研究建议
    domains_found = list(all_endpoints.keys())
    if domains_found:
        result["recommendations"].append(
            f"从 Baxia JS 中提取到 {len(domains_found)} 个域名的端点："
            f"{', '.join(domains_found[:5])}"
        )

    x5sec_endpoints = [p for p in result["endpoint_probes"] if p["x5sec_in_set_cookie"]]
    if x5sec_endpoints:
        result["recommendations"].append(
            f"✓ 发现 {len(x5sec_endpoints)} 个端点返回 x5sec，"
            f"建议重点分析这些端点的请求格式"
        )
    else:
        result["recommendations"].append(
            "✗ 已知端点均未直接返回 x5sec，"
            "x5sec 可能需要先通过 FireyeJS 行为验证后才会下发"
        )

    result["recommendations"].append(
        "建议下一步：分析 fourier.taobao.com/rp 端点的请求格式，"
        "尝试构造合法的行为数据上报，观察是否触发 x5sec 下发"
    )

    return result


# ============================================================
# 11. 路线 D：analyze.jsonp 端点逆向（NoCaptcha 验证核心）
# ============================================================
#
# 关键认知（来自 nc.js 源码分析）：
#   nc.js 从不生成 token！它把 FireyeJS 的 getFYToken() 结果作为参数 n
#   发给后端 analyze.jsonp，token 完全由后端在 result.value 和
#   result.csessionid 中返回。
#
# token 生成流程：
#   用户拖动滑块到终点
#     → m() 函数启动 20ms 轮询 getFYToken()
#     → 轮询退出条件：FYToken 不含 "default" OR 计数器 > 50（约 1 秒）
#     → 构造请求参数：a=appkey, t=token, n=FYToken, p=行为指纹, scene, asyn, lang, v
#     → JSONP 请求 analyze.jsonp（或 replaceCallback 交给宿主）
#     → 后端响应 result.code:
#         0   → 成功：填充 sig=result.value, sessionId=result.csessionid
#         300 → FAIL：验证失败
#         69634 → FAIL：验证失败
#         8778 → BXMARK：行为标记异常
#         8776 → BXFASTMARK：操作太快
#
# 路线 D 的目标：
#   1. 下载 nc.js，提取 analyze.jsonp 端点 URL 和请求参数构造逻辑
#   2. 探测端点响应行为
#   3. 尝试构造合法的 analyze.jsonp 请求（需逆向 n/p 参数生成逻辑）

# NoCaptcha 相关的 JS 端点（从公开资料和观察得到）
NOCAPTCHA_JS_ENDPOINTS = [
    "https://g.alicdn.com/AWSC/nc/1.97.0/nc.js",          # NoCaptcha 主程序
    "https://g.alicdn.com/AWSC/fireyejs/1.234.20/fireyejs.js",  # FireyeJS 行为分析
    "https://g.alicdn.com/sd/nch5/index.js",              # NoCaptcha H5 入口
    "https://g.alicdn.com/AWSC/AWSC/awsc.js",             # AWSC 主程序
]

# analyze.jsonp 请求参数关键字（从 nc.js 源码分析得到）
# 这些参数是构造合法 analyze.jsonp 请求的关键
ANALYZE_JSONP_PARAMS = {
    "a": {
        "description": "appkey（应用标识）",
        "required": True,
        "source": "前端配置或页面 appkey",
    },
    "t": {
        "description": "token（NoCaptcha 会话 token，1a3b... 格式）",
        "required": True,
        "source": "页面加载时从后端获取",
    },
    "n": {
        "description": "FYToken（FireyeJS 的 getFYToken() 结果）",
        "required": True,
        "source": "FireyeJS 行为采集 + 设备指纹",
    },
    "p": {
        "description": "行为指纹（ncSessionID + 元素尺寸等）",
        "required": True,
        "source": "客户端 DOM 计算得出",
    },
    "scene": {
        "description": "场景标识（如 nc_login）",
        "required": True,
        "source": "前端配置",
    },
    "asyn": {
        "description": "异步模式（0/1）",
        "required": False,
        "source": "默认 0",
    },
    "lang": {
        "description": "语言（如 zh_CN）",
        "required": False,
        "source": "navigator.language",
    },
    "v": {
        "description": "版本号（如 1.97.0）",
        "required": False,
        "source": "nc.js 版本",
    },
    "callback": {
        "description": "JSONP 回调函数名",
        "required": True,
        "source": "动态生成",
    },
}

# nc.js 源码中的关键函数名（用于定位 analyze.jsonp 请求构造逻辑）
NC_JS_KEY_FUNCTIONS = [
    "analyze",       # analyze.jsonp 请求构造
    "getFYToken",    # FireyeJS token 获取
    "ncSessionID",   # 行为指纹计算
    "replaceCallback",  # 宿主回调处理
    "success",       # 成功回调
    "fail",          # 失败回调
    "bxmark",        # 行为标记
    "token",         # token 处理
    "sig",           # 签名处理
    "sessionId",     # 会话 ID
]


def download_nc_js(nc_js_url: str = "") -> Dict[str, Any]:
    """下载 NoCaptcha JS 文件（nc.js / fireyejs.js / nch5/index.js）。

    路线 D 的第一步：获取 nc.js 源码，分析 analyze.jsonp 请求构造逻辑。

    Args:
        nc_js_url: JS 文件 URL，空字符串时下载所有已知 NoCaptcha JS

    Returns:
        下载结果 dict：
        {
            "downloads": [
                {
                    "url": str,
                    "status_code": int,
                    "length": int,
                    "content": str,  # JS 内容（限制 500KB）
                    "error": str,
                },
                ...
            ],
        }
    """
    result: Dict[str, Any] = {"downloads": []}

    urls_to_download = [nc_js_url] if nc_js_url else NOCAPTCHA_JS_ENDPOINTS

    try:
        import requests as _requests

        for url in urls_to_download:
            download_result: Dict[str, Any] = {
                "url": url,
                "status_code": 0,
                "length": 0,
                "content": "",
                "error": "",
            }
            try:
                resp = _requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "*/*",
                        "Referer": "https://www.goofish.com/",
                    },
                    timeout=20,
                )
                download_result["status_code"] = resp.status_code
                if resp.status_code == 200:
                    # 限制最大 500KB（fireyejs.js 约 570KB）
                    content = resp.text[:500_000]
                    download_result["length"] = len(resp.text)
                    download_result["content"] = content
                    logger.info(
                        "[方案K-路线D] 下载 %s 完成（长度=%d）",
                        url,
                        len(resp.text),
                    )
                else:
                    download_result["error"] = f"HTTP {resp.status_code}"
            except Exception as e:
                download_result["error"] = str(e)
                logger.warning("[方案K-路线D] 下载 %s 失败: %s", url, e)

            result["downloads"].append(download_result)

    except Exception as e:
        logger.warning("[方案K-路线D] download_nc_js 失败: %s", e)
        result["error"] = str(e)

    return result


def extract_analyze_jsonp_from_nc_js(nc_js_content: str) -> Dict[str, Any]:
    """从 nc.js 源码中提取 analyze.jsonp 端点 URL 和请求构造逻辑。

    路线 D 的核心研究工具：定位 nc.js 中构造 analyze.jsonp 请求的代码，
    提取端点 URL、请求参数、回调处理等关键信息。

    Args:
        nc_js_content: nc.js 源码内容

    Returns:
        分析结果 dict：
        {
            "analyze_endpoints": list,       # 提取到的 analyze.jsonp 端点 URL
            "request_construction": list,    # 请求构造代码片段
            "param_patterns": dict,          # 参数出现位置
            "callback_handling": list,       # 回调处理代码片段
            "result_code_handling": list,    # result.code 处理代码片段
            "key_function_locations": dict,  # 关键函数位置
        }
    """
    result: Dict[str, Any] = {
        "analyze_endpoints": [],
        "request_construction": [],
        "param_patterns": {},
        "callback_handling": [],
        "result_code_handling": [],
        "key_function_locations": {},
    }

    if not nc_js_content:
        return result

    # 1. 提取 analyze.jsonp 端点 URL
    # nc.js 中可能有多种形式：
    # - "https://xxx.aliyun.com/analyze.jsonp"
    # - "/analyze.jsonp"
    # - "analyze.jsonp"（相对路径）
    analyze_patterns = [
        r'https?://[a-zA-Z0-9\-\.]+(?:/[a-zA-Z0-9\-_\.]+)*?analyze\.jsonp[a-zA-Z0-9\-_\.?=&%]*',
        r'["\']([^"\']*analyze\.jsonp[^"\']*)["\']',
        r'analyze\.jsonp',
    ]
    seen_endpoints = set()
    for pattern in analyze_patterns:
        for match in re.finditer(pattern, nc_js_content):
            endpoint = match.group() if match.groups() else match.group(0)
            if endpoint not in seen_endpoints:
                seen_endpoints.add(endpoint)
                # 提取上下文
                start = max(0, match.start() - 200)
                end = min(len(nc_js_content), match.end() + 400)
                result["analyze_endpoints"].append({
                    "endpoint": endpoint,
                    "context": nc_js_content[start:end],
                    "offset": match.start(),
                })

    # 2. 提取请求构造代码（含参数 a/t/n/p/scene/asyn/lang/v）
    # nc.js 中构造请求的代码通常形如：
    #   params.a = appkey; params.t = token; params.n = FYToken; ...
    param_patterns = {
        "a": r'\.a\s*[:=]\s*[^,;]+',
        "t": r'\.t\s*[:=]\s*[^,;]+',
        "n": r'\.n\s*[:=]\s*[^,;]+',
        "p": r'\.p\s*[:=]\s*[^,;]+',
        "scene": r'\.scene\s*[:=]\s*[^,;]+',
        "asyn": r'\.asyn\s*[:=]\s*[^,;]+',
        "lang": r'\.lang\s*[:=]\s*[^,;]+',
        "v": r'\.v\s*[:=]\s*[^,;]+',
        "callback": r'\.callback\s*[:=]\s*[^,;]+',
    }
    for param_name, pattern in param_patterns.items():
        matches = []
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 200)
            matches.append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })
        if matches:
            result["param_patterns"][param_name] = matches
            result["request_construction"].extend(matches)

    # 3. 提取 callback 处理代码（success/fail）
    callback_patterns = [
        r'(success\s*[:=]\s*function\s*\([^)]*\)\s*\{[^}]+\})',
        r'(fail\s*[:=]\s*function\s*\([^)]*\)\s*\{[^}]+\})',
        r'(error\s*[:=]\s*function\s*\([^)]*\)\s*\{[^}]+\})',
    ]
    for pattern in callback_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 200)
            result["callback_handling"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 4. 提取 result.code 处理代码
    # nc.js 中处理响应的代码：if(0===t.result.code){...}
    result_code_patterns = [
        r'(result\.code\s*[=!]==?\s*\d+\s*[^;]+)',
        r'(0\s*===\s*t\.result\.code[^}]+\})',
        r'(\.csessionid\s*[=:]\s*[^,;]+)',
        r'(\.value\s*[=:]\s*[^,;]+)',
    ]
    for pattern in result_code_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 300)
            result["result_code_handling"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
                "pattern": pattern,
            })

    # 5. 定位关键函数
    for func_name in NC_JS_KEY_FUNCTIONS:
        # 搜索函数定义：function name / name: function / name = function
        patterns = [
            rf'function\s+{re.escape(func_name)}\s*\(',
            rf'{re.escape(func_name)}\s*[:=]\s*function\s*\(',
            rf'\.{re.escape(func_name)}\s*\(',
        ]
        locations = []
        for pattern in patterns:
            for match in re.finditer(pattern, nc_js_content):
                locations.append({
                    "offset": match.start(),
                    "matched": match.group(),
                    "context": nc_js_content[max(0, match.start() - 50):
                                             min(len(nc_js_content), match.end() + 150)],
                })
        if locations:
            result["key_function_locations"][func_name] = locations

    return result


def probe_analyze_jsonp_endpoint(
    endpoint_url: str,
    cookie_str: str = "",
    appkey: str = "XFFXFXFF",
    token: str = "",
    fy_token: str = "",
    scene: str = "nc_h5",
    behavior_data: str = "",
    use_post: bool = False,
) -> Dict[str, Any]:
    """探测/调用 analyze.jsonp 端点（路线 D + 路线 J 完整版）。

    2026-08-03 升级：从研究工具升级为完整的 analyze.jsonp 调用器。
    支持传入 initialize.jsonp 返回的 token、FireyeJS 的 fyToken、行为指纹数据，
    构造合法的 analyze.jsonp 请求并解析响应。

    **nc.js 真实请求构造逻辑**（从源码逆向）：
    - a = appkey
    - t = token（initialize.jsonp 返回的 t 字段，1a3b... 格式）
    - n = FYToken（FireyeJS getFYToken() 结果）
    - p = 行为指纹（ncSessionID + 元素尺寸等编码后字符串）
    - scene, asyn, lang, v, callback

    **响应解析**：
    - result.code: 0=成功, 300/69634=失败, 8778=行为异常, 8776=太快
    - result.value: 成功时为 sig（签名，用于构造 x5secdata cookie）
    - result.csessionid: 会话 ID（与 sig 一起用于 Baxia 校验）

    Args:
        endpoint_url: analyze.jsonp 端点 URL
        cookie_str: Cookie 字符串（可选，应包含 um.json 返回的 umt cookie）
        appkey: 应用标识（默认 XFFXFXFF）
        token: initialize.jsonp 返回的 token（t 字段）
        fy_token: FireyeJS getFYToken() 返回值（n 字段）
        scene: 场景标识（默认 nc_h5）
        behavior_data: 行为指纹数据（p 字段，ncSessionID+尺寸编码）
        use_post: 是否使用 POST 方法（默认 False，nc.js 使用 GET JSONP）

    Returns:
        探测结果 dict：
        {
            "url": str,
            "status_code": int,
            "response_length": int,
            "response_preview": str,
            "set_cookie": str,
            "x5sec_in_set_cookie": str,
            "x5sec_in_body": bool,
            "result_code": Optional[int],
            "result_value": str,            # sig（成功时）
            "result_csessionid": str,
            "all_fields": dict,             # 完整响应字段
            "error": str,
        }
    """
    result: Dict[str, Any] = {
        "url": endpoint_url,
        "appkey": appkey,
        "has_token": bool(token),
        "has_fy_token": bool(fy_token),
        "status_code": 0,
        "response_length": 0,
        "response_preview": "",
        "set_cookie": "",
        "x5sec_in_set_cookie": "",
        "x5sec_in_body": False,
        "result_code": None,
        "result_value": "",
        "result_csessionid": "",
        "all_fields": {},
        "error": "",
    }

    try:
        import requests as _requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.goofish.com/",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        # JSONP 回调函数名（与 nc.js 一致）
        callback_name = "nc_jsonp_callback"

        # 构造请求参数（与 nc.js 源码对齐）
        params: Dict[str, Any] = {
            "a": appkey,
            "scene": scene,
            "asyn": "0",
            "lang": "zh_CN",
            "v": "1.97.0",
            "callback": callback_name,
        }

        # 如果传入了 token 和 fy_token，使用完整模式（路线 J）
        if token:
            params["t"] = token
        else:
            # 占位 token（探测模式）
            params["t"] = "1a3btest"

        if fy_token:
            params["n"] = fy_token

        if behavior_data:
            params["p"] = behavior_data
        else:
            # 默认行为数据（占位，会被服务端拒绝但能观察响应格式）
            params["p"] = "0_0_0_0_0_0_0_0_0_0"

        if use_post:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            resp = _requests.post(
                endpoint_url,
                data=params,
                headers=headers,
                timeout=15,
                allow_redirects=False,
            )
        else:
            resp = _requests.get(
                endpoint_url,
                params=params,
                headers=headers,
                timeout=15,
                allow_redirects=False,
            )

        result["status_code"] = resp.status_code
        result["response_length"] = len(resp.text)
        result["response_preview"] = resp.text[:1500]
        result["set_cookie"] = resp.headers.get("set-cookie", "")

        # 检查 Set-Cookie 中的 x5sec
        x5sec_match = re.search(r"x5sec=([^;]+)", result["set_cookie"])
        if x5sec_match:
            result["x5sec_in_set_cookie"] = x5sec_match.group(1)
            logger.info(
                "[方案K-路线D] analyze.jsonp 返回 x5sec（长度=%d）",
                len(result["x5sec_in_set_cookie"]),
            )

        # 检查响应体中的 x5sec
        if "x5sec" in resp.text:
            result["x5sec_in_body"] = True

        # 尝试解析 JSONP 响应
        # JSONP 格式：callback_name({...json...})
        jsonp_match = re.search(
            rf'{re.escape(callback_name)}\s*\(\s*(\{{.*?\}})\s*\)',
            resp.text,
            re.DOTALL,
        )
        if jsonp_match:
            try:
                json_data = json.loads(jsonp_match.group(1))
                if isinstance(json_data, dict):
                    result["all_fields"] = json_data
                    result_data = json_data.get("result", json_data)
                    if isinstance(result_data, dict):
                        result["result_code"] = result_data.get("code")
                        result["result_value"] = str(result_data.get("value", ""))
                        result["result_csessionid"] = str(result_data.get("csessionid", ""))
            except Exception as e:
                logger.debug("[方案K-路线D] JSONP 解析失败: %s", e)
        else:
            # 尝试直接解析 JSON
            try:
                json_data = resp.json()
                if isinstance(json_data, dict):
                    result["all_fields"] = json_data
                    result_data = json_data.get("result", json_data)
                    if isinstance(result_data, dict):
                        result["result_code"] = result_data.get("code")
                        result["result_value"] = str(result_data.get("value", ""))
                        result["result_csessionid"] = str(result_data.get("csessionid", ""))
            except Exception:
                pass

        # 成功标志：result.code == 0 且有 value (sig)
        if result["result_code"] == 0 and result["result_value"]:
            logger.info(
                "[方案K-路线D] ✓ analyze.jsonp 验证成功！sig长度=%d csessionid长度=%d",
                len(result["result_value"]),
                len(result["result_csessionid"]),
            )
        elif result["result_code"] is not None:
            logger.info(
                "[方案K-路线D] analyze.jsonp 返回 code=%s（sig=%s）",
                result["result_code"],
                "有" if result["result_value"] else "无",
            )

    except Exception as e:
        result["error"] = str(e)
        logger.debug("[方案K-路线D] 探测 %s 失败: %s", endpoint_url, e)

    return result


def research_analyze_jsonp(cookie_str: str = "") -> Dict[str, Any]:
    """路线 D 核心研究函数：综合分析 analyze.jsonp 端点。

    本函数整合 nc.js 下载、端点提取、请求格式分析、端点探测：
    1. 下载 nc.js 和相关 JS 文件
    2. 从 nc.js 中提取 analyze.jsonp 端点 URL
    3. 分析请求参数构造逻辑
    4. 探测端点响应行为
    5. 识别获取 x5sec 的可行路径

    Args:
        cookie_str: Cookie 字符串（可选）

    Returns:
        综合分析结果 dict
    """
    result: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "js_downloads": [],
        "analyze_jsonp_extraction": {},
        "endpoint_probes": [],
        "findings": [],
        "recommendations": [],
    }

    # 步骤 1：下载 NoCaptcha JS 文件
    logger.info("[方案K-路线D] 步骤 1：下载 NoCaptcha JS 文件")
    download_result = download_nc_js()
    result["js_downloads"] = [
        {
            "url": d["url"],
            "status_code": d["status_code"],
            "length": d["length"],
            "error": d["error"],
        }
        for d in download_result.get("downloads", [])
    ]

    # 步骤 2：从 nc.js 中提取 analyze.jsonp 端点和请求构造逻辑
    logger.info("[方案K-路线D] 步骤 2：从 nc.js 提取 analyze.jsonp 端点")
    nc_js_content = ""
    for d in download_result.get("downloads", []):
        if "nc.js" in d["url"] and d["content"]:
            nc_js_content = d["content"]
            break

    if nc_js_content:
        extraction = extract_analyze_jsonp_from_nc_js(nc_js_content)
        result["analyze_jsonp_extraction"] = {
            "analyze_endpoints_count": len(extraction.get("analyze_endpoints", [])),
            "analyze_endpoints": extraction.get("analyze_endpoints", [])[:5],
            "param_patterns_keys": list(extraction.get("param_patterns", {}).keys()),
            "request_construction_count": len(extraction.get("request_construction", [])),
            "callback_handling_count": len(extraction.get("callback_handling", [])),
            "result_code_handling_count": len(extraction.get("result_code_handling", [])),
            "key_function_locations": {
                k: len(v) for k, v in extraction.get("key_function_locations", {}).items()
            },
            # 包含完整提取结果用于深度分析
            "full_extraction": extraction,
        }

        if extraction.get("analyze_endpoints"):
            result["findings"].append({
                "type": "analyze_endpoints_found",
                "message": f"从 nc.js 中提取到 {len(extraction['analyze_endpoints'])} 个 analyze.jsonp 端点引用",
                "endpoints": [e["endpoint"] for e in extraction["analyze_endpoints"][:3]],
            })
        else:
            result["findings"].append({
                "type": "no_analyze_endpoints",
                "message": "nc.js 中未直接提取到 analyze.jsonp 端点，可能使用相对路径或动态构造",
            })

        if extraction.get("param_patterns"):
            result["findings"].append({
                "type": "request_params_found",
                "message": f"找到请求参数构造代码：{list(extraction['param_patterns'].keys())}",
            })

        if extraction.get("result_code_handling"):
            result["findings"].append({
                "type": "result_code_handling_found",
                "message": f"找到 result.code 处理代码 {len(extraction['result_code_handling'])} 处",
            })
    else:
        result["findings"].append({
            "type": "nc_js_download_failed",
            "message": "nc.js 下载失败，无法提取 analyze.jsonp 端点",
        })

    # 步骤 3：探测已知 analyze.jsonp 端点
    logger.info("[方案K-路线D] 步骤 3：探测 analyze.jsonp 端点")
    # 已知的 NoCaptcha 端点（从公开资料和 JS 提取）
    known_analyze_endpoints = [
        "https://cf.aliyun.com/nocaptcha/analyze.jsonp",
        "https://cf2.aliyun.com/nocaptcha/analyze.jsonp",
        "https://nocaptcha.alibaba.com/analyze.jsonp",
        "https://h5api.m.goofish.com/h5/mtop.taobao.idle.user.validate/1.0/",
    ]

    # 从 nc.js 提取的端点（如果有完整 URL）
    extracted_endpoints = []
    if nc_js_content:
        for match in re.finditer(
            r'https?://[a-zA-Z0-9\-\.]+/[a-zA-Z0-9\-_/]*analyze\.jsonp',
            nc_js_content,
        ):
            extracted_endpoints.append(match.group())

    # 合并去重
    all_endpoints = list(set(known_analyze_endpoints + extracted_endpoints))

    for endpoint in all_endpoints:
        probe = probe_analyze_jsonp_endpoint(endpoint, cookie_str=cookie_str)
        result["endpoint_probes"].append(probe)

        if probe["x5sec_in_set_cookie"]:
            result["findings"].append({
                "type": "x5sec_from_analyze",
                "message": f"端点 {endpoint} 返回了 x5sec！",
                "x5sec_length": len(probe["x5sec_in_set_cookie"]),
            })

        if probe["result_code"] is not None:
            result["findings"].append({
                "type": "result_code_returned",
                "message": f"端点 {endpoint} 返回 result.code={probe['result_code']}",
                "result_value": probe["result_value"][:50],
                "result_csessionid": probe["result_csessionid"][:50],
            })

    # 步骤 4：给出研究建议
    if result["endpoint_probes"]:
        x5sec_probes = [p for p in result["endpoint_probes"] if p["x5sec_in_set_cookie"]]
        if x5sec_probes:
            result["recommendations"].append(
                f"✓ 发现 {len(x5sec_probes)} 个端点返回 x5sec，"
                f"建议重点分析这些端点的完整请求格式"
            )
        else:
            result["recommendations"].append(
                "✗ 已知 analyze.jsonp 端点均未直接返回 x5sec，"
                "说明需要提供合法的 a/t/n/p 参数才能通过验证"
            )

    result["recommendations"].append(
        "下一步研究方向：\n"
        "1. 深度逆向 nc.js 中的 getFYToken() 调用链，理解 FireyeJS token 生成\n"
        "2. 逆向 ncSessionID 计算逻辑（基于 DOM 元素尺寸）\n"
        "3. 尝试通过 crawler-service 浏览器捕获真实的 analyze.jsonp 请求\n"
        "4. 研究是否可以复用历史有效的 FYToken（如果服务端不校验时效性）"
    )

    result["recommendations"].append(
        "备选方案（如果 analyze.jsonp 逆向不可行）：\n"
        "1. 通过 crawler-service 浏览器在真实环境中捕获 analyze.jsonp 请求和响应\n"
        "2. 研究是否可以通过 NoCaptcha 的 initialize.jsonp 端点获取有效 token\n"
        "3. 探索 punish iframe 中的 form 提交机制（可能绕过 analyze.jsonp）"
    )

    return result


# ============================================================
# 12. 路线 E：浏览器真实请求捕获（通过 crawler-service）
# ============================================================
#
# 路线 D 的局限：analyze.jsonp 需要合法的 a/t/n/p 参数，这些参数依赖
# FireyeJS 的 getFYToken() 和 ncSessionID 计算，难以纯 HTTP 构造。
#
# 路线 E 的思路：通过 crawler-service 的浏览器，在真实环境中捕获
# analyze.jsonp 请求和响应，获取完整的请求参数和响应格式。
# 即使无法直接构造请求，也能通过捕获真实请求理解参数生成逻辑。


# ============================================================
# 13. 路线 F：initialize.jsonp 端点分析（获取合法 token t）
# ============================================================
#
# 重大发现（来自路线 D 的 nc.js 分析）：
#   nc.js 中定义了 initialize.jsonp 端点，用于获取 NoCaptcha 会话 token (t)：
#     t.URL={
#       cn:{
#         serviceUrl:"https://ynuf.aliapp.org/service/um.json",
#         initialize:"https://cf.aliyun.com/nocaptcha/initialize.jsonp",
#         analyze:"https://cf.aliyun.com/nocaptcha/analyze.jsonp"
#       },
#       us:{
#         initialize:"https://cfall.aliyun.com/nocaptcha/initialize.jsonp",
#         analyze:"https://cfall.aliyun.com/nocaptcha/analyze.jsonp"
#       }
#     }
#
# 路线 F 的目标：
#   1. 探测 initialize.jsonp 端点，观察响应格式
#   2. 分析响应中的 token (t) 字段
#   3. 尝试获取合法 token，用于后续 analyze.jsonp 请求
#
# 关键认知：
#   - analyze.jsonp 需要 token (t) 参数，这个 token 来自 initialize.jsonp
#   - 如果 initialize.jsonp 不需要严格的风控校验，就可以获取合法 token
#   - 有了合法 token + 模拟的 ncSessionID + FYToken，可能通过 analyze.jsonp

# 已知的 initialize.jsonp 端点（从 nc.js 提取）
INITIALIZE_JSONP_ENDPOINTS = [
    "https://cf.aliyun.com/nocaptcha/initialize.jsonp",        # 中国
    "https://cfall.aliyun.com/nocaptcha/initialize.jsonp",     # 美国/备用
    "https://cf-app-waf.cfc.aliyuncs.com/nocaptcha/initialize.jsonp",  # WAF
    "https://cfdus.aliyun.com/nocaptcha/initialize.jsonp",     # 德国
]

# 已知的 analyze.jsonp 端点（与 initialize.jsonp 端点共享 base URL）
# 路径：{base}/nocaptcha/analyze.jsonp
ANALYZE_JSONP_ENDPOINTS = [
    "https://cf.aliyun.com/nocaptcha/analyze.jsonp",           # 中国（主）
    "https://cfall.aliyun.com/nocaptcha/analyze.jsonp",        # 美国/备用
    "https://cf-app-waf.cfc.aliyuncs.com/nocaptcha/analyze.jsonp",  # WAF
    "https://cfdus.aliyun.com/nocaptcha/analyze.jsonp",        # 德国
]

# 路线 J 默认使用的 appkey 和 scene
# 注意：nc_h5 是 NoCaptcha H5 场景，XFFXFXFF 是闲鱼使用的 appkey
ROUTE_J_DEFAULT_APPKEY = "XFFXFXFF"
ROUTE_J_DEFAULT_SCENE = "nc_h5"

# NoCaptcha 已知 appkey（从 nc.js 和公开资料提取）
NOCAPTCHA_APPKEYS = {
    "CF_APP_1": {
        "description": "测试 appkey（nc.js 中 test 模式使用）",
        "scene": "nvc_register",
        "is_test": True,
    },
    "CF_APP_WAF": {
        "description": "WAF 场景 appkey（Web Application Firewall）",
        "scene": "nc_waf",
        "is_test": False,
    },
    "XFFXFXFF": {
        "description": "占位 appkey（用于探测）",
        "scene": "nc_h5",
        "is_test": False,
    },
}


def probe_initialize_jsonp_endpoint(
    endpoint_url: str,
    appkey: str = "XFFXFXFF",
    scene: str = "nc_h5",
    cookie_str: str = "",
) -> Dict[str, Any]:
    """探测 initialize.jsonp 端点的响应行为。

    initialize.jsonp 是获取 NoCaptcha 会话 token (t) 的入口。
    本函数发送请求观察：
    - 是否返回合法 token
    - 响应格式（JSONP / JSON）
    - 是否需要特定 appkey/scene
    - 是否触发风控

    Args:
        endpoint_url: initialize.jsonp 端点 URL
        appkey: 应用标识
        scene: 场景标识
        cookie_str: Cookie 字符串（可选）

    Returns:
        探测结果 dict：
        {
            "url": str,
            "status_code": int,
            "response_length": int,
            "response_preview": str,
            "set_cookie": str,
            "x5sec_in_set_cookie": str,
            "token": str,                # 提取到的 token
            "result_code": Optional[int],
            "all_fields": dict,          # 响应中的所有字段
            "error": str,
        }
    """
    result: Dict[str, Any] = {
        "url": endpoint_url,
        "appkey": appkey,
        "scene": scene,
        "status_code": 0,
        "response_length": 0,
        "response_preview": "",
        "set_cookie": "",
        "x5sec_in_set_cookie": "",
        "token": "",
        "result_code": None,
        "all_fields": {},
        "error": "",
    }

    try:
        import requests as _requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.goofish.com/",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        # JSONP 回调函数名
        callback_name = "nc_init_callback"
        params = {
            "a": appkey,
            "scene": scene,
            "lang": "zh_CN",
            "v": "1.97.0",
            "callback": callback_name,
        }

        resp = _requests.get(
            endpoint_url,
            params=params,
            headers=headers,
            timeout=10,
            allow_redirects=False,
        )

        result["status_code"] = resp.status_code
        result["response_length"] = len(resp.text)
        result["response_preview"] = resp.text[:1000]
        result["set_cookie"] = resp.headers.get("set-cookie", "")

        # 检查 Set-Cookie 中的 x5sec
        x5sec_match = re.search(r"x5sec=([^;]+)", result["set_cookie"])
        if x5sec_match:
            result["x5sec_in_set_cookie"] = x5sec_match.group(1)
            logger.info(
                "[方案K-路线F] initialize.jsonp 返回 x5sec（长度=%d）",
                len(result["x5sec_in_set_cookie"]),
            )

        # 尝试解析 JSONP 响应
        jsonp_match = re.search(
            rf'{re.escape(callback_name)}\s*\(\s*(\{{.*?\}})\s*\)',
            resp.text,
            re.DOTALL,
        )
        if jsonp_match:
            try:
                json_data = json.loads(jsonp_match.group(1))
                if isinstance(json_data, dict):
                    result["all_fields"] = json_data
                    # 提取 token
                    result["token"] = str(json_data.get("token", ""))
                    # 提取 result.code
                    result_data = json_data.get("result", json_data)
                    if isinstance(result_data, dict):
                        result["result_code"] = result_data.get("code")
            except Exception as e:
                logger.debug("[方案K-路线F] JSONP 解析失败: %s", e)
        else:
            # 尝试直接解析 JSON
            try:
                json_data = resp.json()
                if isinstance(json_data, dict):
                    result["all_fields"] = json_data
                    result["token"] = str(json_data.get("token", ""))
                    result_data = json_data.get("result", json_data)
                    if isinstance(result_data, dict):
                        result["result_code"] = result_data.get("code")
            except Exception:
                pass

        if result["token"]:
            logger.info(
                "[方案K-路线F] initialize.jsonp 返回 token（长度=%d）",
                len(result["token"]),
            )

    except Exception as e:
        result["error"] = str(e)
        logger.debug("[方案K-路线F] 探测 %s 失败: %s", endpoint_url, e)

    return result


def research_initialize_jsonp(cookie_str: str = "") -> Dict[str, Any]:
    """路线 F 核心研究函数：综合分析 initialize.jsonp 端点。

    本函数探测所有已知的 initialize.jsonp 端点，使用不同的 appkey/scene 组合，
    分析响应格式，识别获取合法 token 的可行路径。

    Args:
        cookie_str: Cookie 字符串（可选）

    Returns:
        综合分析结果 dict
    """
    result: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "endpoint_probes": [],
        "findings": [],
        "recommendations": [],
    }

    logger.info("[方案K-路线F] 探测 initialize.jsonp 端点")

    # 步骤 1：使用不同 appkey 探测所有端点
    test_configs = [
        # (appkey, scene, description)
        ("XFFXFXFF", "nc_h5", "占位 appkey + nc_h5 场景"),
        ("CF_APP_1", "nvc_register", "测试 appkey + nvc_register 场景"),
        ("CF_APP_WAF", "nc_waf", "WAF appkey + nc_waf 场景"),
    ]

    for endpoint in INITIALIZE_JSONP_ENDPOINTS:
        for appkey, scene, desc in test_configs:
            logger.info(
                "[方案K-路线F] 探测 %s (appkey=%s, scene=%s)",
                endpoint,
                appkey,
                scene,
            )
            probe = probe_initialize_jsonp_endpoint(
                endpoint,
                appkey=appkey,
                scene=scene,
                cookie_str=cookie_str,
            )
            probe["description"] = desc
            result["endpoint_probes"].append(probe)

            if probe["token"]:
                result["findings"].append({
                    "type": "token_returned",
                    "message": f"端点 {endpoint} (appkey={appkey}) 返回了 token！",
                    "token_length": len(probe["token"]),
                    "token_prefix": probe["token"][:30],
                })

            if probe["x5sec_in_set_cookie"]:
                result["findings"].append({
                    "type": "x5sec_from_initialize",
                    "message": f"端点 {endpoint} 返回了 x5sec！",
                    "x5sec_length": len(probe["x5sec_in_set_cookie"]),
                })

            if probe["result_code"] is not None:
                result["findings"].append({
                    "type": "result_code_returned",
                    "message": f"端点 {endpoint} (appkey={appkey}) 返回 result.code={probe['result_code']}",
                    "all_fields_keys": list(probe["all_fields"].keys()) if isinstance(probe["all_fields"], dict) else [],
                })

    # 步骤 2：分析发现
    token_probes = [p for p in result["endpoint_probes"] if p["token"]]
    x5sec_probes = [p for p in result["endpoint_probes"] if p["x5sec_in_set_cookie"]]

    if token_probes:
        result["recommendations"].append(
            f"✓ 发现 {len(token_probes)} 个配置返回了 token，"
            f"建议使用这些 token 尝试 analyze.jsonp 请求"
        )
        # 分析 token 格式
        first_token = token_probes[0]["token"]
        result["recommendations"].append(
            f"token 格式分析：长度={len(first_token)}，前缀={first_token[:20]}，"
            f"是否含 1a3b 前缀={first_token.startswith('1a3b')}"
        )
    else:
        result["recommendations"].append(
            "✗ 所有 initialize.jsonp 探测均未返回 token，"
            "可能需要：(a) 合法的 appkey，(b) 浏览器环境，(c) Referer/Cookie 校验"
        )

    if x5sec_probes:
        result["recommendations"].append(
            f"✓ 发现 {len(x5sec_probes)} 个配置返回了 x5sec，"
            f"这是重大突破！initialize.jsonp 可能直接下发 x5sec"
        )
    else:
        result["recommendations"].append(
            "✗ initialize.jsonp 未直接返回 x5sec，"
            "x5sec 仍需通过 analyze.jsonp 验证后才会下发"
        )

    result["recommendations"].append(
        "下一步研究方向：\n"
        "1. 如果获取到合法 token，尝试用该 token + 模拟的 ncSessionID + "
        "占位 FYToken 调用 analyze.jsonp，观察 result.code 是否变化\n"
        "2. 研究 initialize.jsonp 是否需要特定的 Referer 或 Origin 头\n"
        "3. 通过 crawler-service 浏览器捕获真实的 initialize.jsonp 请求\n"
        "4. 研究 ynuf.aliapp.org/service/um.json 端点（设备指纹服务）"
    )

    return result


def capture_analyze_jsonp_via_browser(
    cookie_str: str = "",
    target_url: str = "https://www.goofish.com/",
) -> Dict[str, Any]:
    """通过 crawler-service 浏览器捕获 analyze.jsonp 请求。

    路线 E 的核心：在真实浏览器环境中加载页面，监听网络请求，
    捕获 analyze.jsonp 的完整请求和响应。

    需要在 crawler-service 中实现 /api/capture-analyze-jsonp 接口。

    Args:
        cookie_str: Cookie 字符串
        target_url: 目标 URL

    Returns:
        捕获结果 dict
    """
    result: Dict[str, Any] = {
        "success": False,
        "analyze_requests": [],
        "analyze_responses": [],
        "error": "",
    }

    try:
        import requests as _requests

        crawler_url = os.environ.get("CRAWLER_SERVICE_URL", "http://crawler-service:3001")
        capture_endpoint = f"{crawler_url}/api/capture-analyze-jsonp"

        payload = {
            "cookie": cookie_str,
            "target_url": target_url,
        }

        internal_token = os.environ.get("INTERNAL_API_TOKEN", "")
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": internal_token,
        }

        resp = _requests.post(capture_endpoint, json=payload, headers=headers, timeout=60)

        if resp.status_code == 200:
            data = resp.json()
            result["success"] = data.get("success", False)
            result["analyze_requests"] = data.get("analyze_requests", [])
            result["analyze_responses"] = data.get("analyze_responses", [])

            logger.info(
                "[方案K-路线E] 浏览器捕获 analyze.jsonp：success=%s requests=%d",
                result["success"],
                len(result["analyze_requests"]),
            )
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning(
                "[方案K-路线E] crawler-service 返回 %d: %s",
                resp.status_code,
                resp.text[:200],
            )

    except Exception as e:
        result["error"] = str(e)
        logger.warning("[方案K-路线E] capture_analyze_jsonp_via_browser 失败: %s", e)

    return result


# ============================================================
# 14. 路线 G：um.json 设备指纹采集（NoCaptcha 入口瓶颈）
# ============================================================
#
# 当前瓶颈（来自路线 F 的研究结果）：
#   - initialize.jsonp 端点全部返回 {"result":{"msg":"fail","success":false}}
#   - 原因：缺少前置的设备指纹 cookie（umt / cna / isg 等）
#   - 这些 cookie 由 ynuf.aliapp.org/service/um.json 端点下发
#
# 路线 G 的目标：
#   1. 探测 um.json 端点的请求格式和响应行为
#   2. 分析设备指纹的采集逻辑（从 nc.js 提取）
#   3. 构造最小可用的设备指纹请求，获取 umt/cna cookie
#   4. 使用获取的 cookie 重试 initialize.jsonp，观察是否返回 token
#
# 关键认知：
#   - um.json 是 NoCaptcha 流程的"入口门槛"
#   - 没有有效的设备指纹 cookie，initialize.jsonp 直接拒绝
#   - um.json 接收 POST 请求，包含设备指纹数据（JSON 格式）
#   - 响应通过 Set-Cookie 下发 umt/cna/isg 等 cookie
#   - 这些 cookie 后续被 initialize.jsonp 和 analyze.jsonp 校验

# 已知的 um.json 端点（从 nc.js 的 t.URL.serviceUrl 提取）
# 测试发现：https://ynuf.aliapp.org/service/um.json 返回 {"id":""}（接受了请求但缺少必要字段）
# 新发现：nc.js 中存在 us 区域端点 https://us.ynuf.aliapp.org/service/um.json
UM_JSON_ENDPOINTS = [
    "https://ynuf.aliapp.org/service/um.json",                # 中国（主）
    "https://us.ynuf.aliapp.org/service/um.json",             # 美国（新发现）
    "https://ynuf.aliapp.org/service/um.jsonp",               # JSONP 变体（已确认 404）
]

# NVC_Data 结构（从 nc.js 提取的真实请求体格式）
# 代码位置：nc.js 偏移 22595 附近
# 关键代码：
#   e.NVC_Data.h=e.options.trans||{};
#   var t=e.NVC_Data;
#   return t.b=e.__fy&&e.__fy.getFYToken&&e.__fy.getFYToken(e.__fy_options),
#          t.h.umidToken=e.__fy&&e.__fy.getFYToken&&e.__fy.getUidToken(),
#          e.NVC_Result.nvcPreRes&&(t.e=e.NVC_Result.nvcPreRes.c),
#          e.NVC_Data
# 字段含义：
#   b: FireyeJS getFYToken() 返回值（行为特征 token）
#   h.umidToken: FireyeJS getUidToken() 返回值（设备指纹 token）
#   h: options.trans（传输数据，dict）
#   e: NVC_Result.nvcPreRes.c（预验证结果）
#   d: options.scene（场景标识）
NVC_DATA_STRUCTURE = {
    "b": "FYToken - FireyeJS getFYToken() 返回值（行为特征 token）",
    "h": {
        "umidToken": "FireyeJS getUidToken() 返回值（设备指纹 token）",
        "_trans": "options.trans 传输数据（dict）",
    },
    "e": "NVC_Result.nvcPreRes.c 预验证结果（可选）",
    "d": "options.scene 场景标识",
}

# um.json 已知 appkey（与 NoCaptcha appkey 共享）
UM_JSON_APPKEYS = {
    "XFFXFXFF": {
        "description": "占位 appkey（用于探测）",
        "scene": "nc_h5",
    },
    "FavorAlipay": {
        "description": "支付宝场景 appkey",
        "scene": "nc_other_login",
    },
}

# um.json 设备指纹字段（基于 FireyeJS 已知检测维度）
UM_JSON_FINGERPRINT_FIELDS = {
    # 基础环境字段
    "ua": "User-Agent",
    "lang": "浏览器语言",
    "tz": "时区",
    "tzOffset": "时区偏移（分钟）",
    "screen": "屏幕分辨率（宽x高）",
    "colorDepth": "颜色深度",
    "pixelRatio": "设备像素比",
    "platform": " navigator.platform",
    "vendor": "navigator.vendor",
    "pluginCount": "插件数量",
    # Canvas/WebGL 指纹
    "canvas": "Canvas 指纹 hash",
    "webgl": "WebGL 指纹 hash",
    "webglVendor": "WebGL 厂商",
    "webglRenderer": "WebGL 渲染器",
    # AudioContext 指纹
    "audio": "AudioContext 指纹",
    # 行为字段
    "mouseMoves": "鼠标移动次数",
    "mouseClicks": "点击次数",
    "keyStrokes": "按键次数",
    "touchEvents": "触摸事件次数",
    # 时间字段
    "ts": "时间戳",
    "startTs": "页面加载时间戳",
}


def probe_um_json_endpoint(
    endpoint_url: str,
    appkey: str = "XFFXFXFF",
    cookie_str: str = "",
    use_post: bool = True,
    use_nvc_data: bool = True,
    fy_token: str = "",
    umid_token: str = "",
) -> Dict[str, Any]:
    """探测 um.json 端点的响应行为。

    um.json 是 NoCaptcha 设备指纹采集端点。本函数发送 GET/POST 请求观察：
    - 是否返回成功（200 状态码）
    - 响应格式（JSON / JSONP / 空）
    - Set-Cookie 中是否包含 umt/cna/isg 等 cookie
    - 是否需要特定 appkey
    - 是否触发风控

    支持两种请求体格式：
    - NVC_Data 结构（use_nvc_data=True）：基于 nc.js 提取的真实请求体格式
      包含 b（FYToken）、h.umidToken、d（scene）、e（nvcPreRes.c）字段
    - 简单字段格式（use_nvc_data=False）：用于探测端点响应行为

    Args:
        endpoint_url: um.json 端点 URL
        appkey: 应用标识
        cookie_str: Cookie 字符串（可选）
        use_post: 是否使用 POST 方法（默认 True）
        use_nvc_data: 是否使用 NVC_Data 结构作为请求体（默认 True）
        fy_token: 预计算的 FYToken（可选，用于 NVC_Data 模式）
        umid_token: 预计算的 umidToken（可选，用于 NVC_Data 模式）

    Returns:
        探测结果 dict：
        {
            "url": str,
            "method": str,
            "status_code": int,
            "response_length": int,
            "response_preview": str,
            "set_cookie": str,
            "cookies_obtained": list,    # 获取到的 cookie 名称
            "umt_cookie": str,            # umt cookie 值
            "cna_cookie": str,            # cna cookie 值
            "isg_cookie": str,            # isg cookie 值
            "x5sec_in_set_cookie": str,
            "all_fields": dict,           # 响应 JSON 字段
            "umid_id": str,               # 响应中的 id 字段（umidToken）
            "error": str,
        }
    """
    result: Dict[str, Any] = {
        "url": endpoint_url,
        "method": "POST" if use_post else "GET",
        "appkey": appkey,
        "use_nvc_data": use_nvc_data,
        "status_code": 0,
        "response_length": 0,
        "response_preview": "",
        "set_cookie": "",
        "cookies_obtained": [],
        "umt_cookie": "",
        "cna_cookie": "",
        "isg_cookie": "",
        "x5sec_in_set_cookie": "",
        "all_fields": {},
        "umid_id": "",
        "error": "",
    }

    try:
        import requests as _requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.goofish.com/",
            "Origin": "https://www.goofish.com",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        # 构造请求体
        ts_now = int(time.time() * 1000)

        if use_nvc_data:
            # NVC_Data 结构（真实请求体格式）
            # 字段含义参考 NVC_DATA_STRUCTURE 常量
            fingerprint_data = {
                "a": appkey,                    # appkey
                "scene": "nc_h5",               # 场景
                "b": fy_token or "",            # FYToken（FireyeJS getFYToken）
                "h": {
                    "umidToken": umid_token or "",  # umidToken（FireyeJS getUidToken）
                    "trans": {},                    # options.trans
                },
                "d": "nc_h5",                   # scene
                "ts": ts_now,
                "ua": headers["User-Agent"],
                "lang": "zh-CN",
                "tz": "Asia/Shanghai",
                "tzOffset": -480,
                "screen": "1920x1080",
                "colorDepth": 24,
                "pixelRatio": 1,
                "platform": "Win32",
                "vendor": "Google Inc.",
                "pluginCount": 5,
                "mouseMoves": 3,
                "mouseClicks": 1,
                "keyStrokes": 0,
                "touchEvents": 0,
                "startTs": ts_now - 2000,
            }
        else:
            # 简单字段格式（用于探测）
            fingerprint_data = {
                "a": appkey,
                "ts": ts_now,
                "ua": headers["User-Agent"],
                "lang": "zh-CN",
                "tz": "Asia/Shanghai",
                "tzOffset": -480,
                "screen": "1920x1080",
                "colorDepth": 24,
                "pixelRatio": 1,
                "platform": "Win32",
                "vendor": "Google Inc.",
                "pluginCount": 5,
                "mouseMoves": 3,
                "mouseClicks": 1,
                "keyStrokes": 0,
                "touchEvents": 0,
                "startTs": ts_now - 2000,
            }

        if use_post:
            headers["Content-Type"] = "application/json;charset=UTF-8"
            resp = _requests.post(
                endpoint_url,
                json=fingerprint_data,
                headers=headers,
                timeout=10,
                allow_redirects=False,
            )
        else:
            # GET 方式：将指纹数据作为查询参数
            params = {"a": appkey, "ts": str(ts_now)}
            resp = _requests.get(
                endpoint_url,
                params=params,
                headers=headers,
                timeout=10,
                allow_redirects=False,
            )

        result["status_code"] = resp.status_code
        result["response_length"] = len(resp.text)
        result["response_preview"] = resp.text[:1000]
        result["set_cookie"] = resp.headers.get("set-cookie", "")

        # 解析 Set-Cookie 中的所有 cookie 名称
        if result["set_cookie"]:
            cookie_names = re.findall(r"([a-zA-Z0-9_]+)\s*=", result["set_cookie"])
            result["cookies_obtained"] = list(set(cookie_names))

            # 提取关键 cookie
            umt_match = re.search(r"umt=([^;]+)", result["set_cookie"])
            if umt_match:
                result["umt_cookie"] = umt_match.group(1)

            cna_match = re.search(r"cna=([^;]+)", result["set_cookie"])
            if cna_match:
                result["cna_cookie"] = cna_match.group(1)

            isg_match = re.search(r"isg=([^;]+)", result["set_cookie"])
            if isg_match:
                result["isg_cookie"] = isg_match.group(1)

            x5sec_match = re.search(r"x5sec=([^;]+)", result["set_cookie"])
            if x5sec_match:
                result["x5sec_in_set_cookie"] = x5sec_match.group(1)
                logger.info(
                    "[方案K-路线G] um.json 直接返回 x5sec（长度=%d）",
                    len(result["x5sec_in_set_cookie"]),
                )

        # 尝试解析 JSON 响应
        try:
            json_data = resp.json()
            if isinstance(json_data, dict):
                result["all_fields"] = json_data
                # 提取 id 字段（umidToken）
                if "id" in json_data:
                    result["umid_id"] = str(json_data["id"])
                    if result["umid_id"]:
                        logger.info(
                            "[方案K-路线G] um.json 返回有效 umidToken（长度=%d）",
                            len(result["umid_id"]),
                        )
                logger.info(
                    "[方案K-路线G] um.json 返回 JSON，字段数=%d",
                    len(json_data),
                )
        except Exception:
            # 可能是 JSONP 格式
            jsonp_match = re.search(
                r'\w+\s*\(\s*(\{.*?\})\s*\)',
                resp.text,
                re.DOTALL,
            )
            if jsonp_match:
                try:
                    json_data = json.loads(jsonp_match.group(1))
                    if isinstance(json_data, dict):
                        result["all_fields"] = json_data
                        if "id" in json_data:
                            result["umid_id"] = str(json_data["id"])
                except Exception:
                    pass

        if result["umt_cookie"] or result["cna_cookie"] or result["umid_id"]:
            logger.info(
                "[方案K-路线G] um.json 下发设备指纹：umt=%s cna=%s isg=%s umid_id=%s",
                "✓" if result["umt_cookie"] else "✗",
                "✓" if result["cna_cookie"] else "✗",
                "✓" if result["isg_cookie"] else "✗",
                "✓" if result["umid_id"] else "✗",
            )

    except Exception as e:
        result["error"] = str(e)
        logger.debug("[方案K-路线G] 探测 %s 失败: %s", endpoint_url, e)

    return result


def extract_um_json_from_nc_js(nc_js_content: str) -> Dict[str, Any]:
    """从 nc.js 源码中提取 um.json 相关代码。

    本函数定位 nc.js 中：
    - um.json 端点 URL 引用
    - 设备指纹采集逻辑（FireyeJS 调用）
    - POST 请求构造代码
    - Set-Cookie 处理代码

    Args:
        nc_js_content: nc.js 源码内容

    Returns:
        分析结果 dict：
        {
            "um_json_endpoints": list,       # um.json 端点 URL 引用
            "fingerprint_collection": list,  # 设备指纹采集代码片段
            "request_construction": list,    # POST 请求构造代码
            "cookie_handling": list,         # Set-Cookie 处理代码
            "fireyejs_calls": list,          # FireyeJS 调用位置
        }
    """
    result: Dict[str, Any] = {
        "um_json_endpoints": [],
        "fingerprint_collection": [],
        "request_construction": [],
        "cookie_handling": [],
        "fireyejs_calls": [],
    }

    if not nc_js_content:
        return result

    # 1. 提取 um.json 端点 URL
    um_patterns = [
        r'https?://[a-zA-Z0-9\-\.]+(?:/[a-zA-Z0-9\-_\.]+)*?um\.json[a-zA-Z0-9\-_\.?=&%]*',
        r'["\']([^"\']*um\.json[^"\']*)["\']',
        r'um\.json',
        r'serviceUrl\s*[:=]\s*["\']([^"\']+)["\']',
    ]
    seen_endpoints = set()
    for pattern in um_patterns:
        for match in re.finditer(pattern, nc_js_content):
            endpoint = match.group(1) if match.groups() else match.group(0)
            if endpoint and endpoint not in seen_endpoints:
                seen_endpoints.add(endpoint)
                start = max(0, match.start() - 200)
                end = min(len(nc_js_content), match.end() + 400)
                result["um_json_endpoints"].append({
                    "endpoint": endpoint,
                    "context": nc_js_content[start:end],
                    "offset": match.start(),
                })

    # 2. 提取设备指纹采集代码（FireyeJS 字段引用）
    fingerprint_patterns = {
        "ua": r'navigator\.userAgent',
        "lang": r'navigator\.language',
        "platform": r'navigator\.platform',
        "vendor": r'navigator\.vendor',
        "screen": r'screen\.(width|height|availWidth|availHeight)',
        "colorDepth": r'screen\.colorDepth',
        "pixelRatio": r'window\.devicePixelRatio',
        "tz": r'getTimezoneOffset|Intl\.DateTimeFormat',
        "canvas": r'getContext\s*\(\s*["\']2d["\']\s*\)|toDataURL',
        "webgl": r'getContext\s*\(\s*["\']webgl|WEBGL_debug_renderer_info',
        "audio": r'AudioContext|webkitAudioContext|OfflineAudioContext',
        "plugins": r'navigator\.plugins',
        "localStorage": r'window\.localStorage|try\s*\{[^}]*localStorage',
        "sessionStorage": r'window\.sessionStorage',
    }
    for field_name, pattern in fingerprint_patterns.items():
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 200)
            result["fingerprint_collection"].append({
                "field": field_name,
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 3. 提取 POST 请求构造代码
    post_patterns = [
        r'(open\s*\(\s*["\']POST["\'])',
        r'(send\s*\(\s*JSON\.stringify)',
        r'(XMLHttpRequest|fetch\s*\()',
    ]
    for pattern in post_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 200)
            end = min(len(nc_js_content), match.end() + 300)
            result["request_construction"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 4. 提取 Set-Cookie 处理代码
    cookie_patterns = [
        r'(document\.cookie\s*=[^;]+;)',
        r'(set-cookie|Set-Cookie)',
        r'(umt|cna|isg)\s*[:=]',
    ]
    for pattern in cookie_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 200)
            result["cookie_handling"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 5. 提取 FireyeJS 调用位置
    fireyejs_patterns = [
        r'FireyeJS',
        r'getFYToken',
        r'fireye',
        r'fy_token',
    ]
    for pattern in fireyejs_patterns:
        for match in re.finditer(pattern, nc_js_content, re.IGNORECASE):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 200)
            result["fireyejs_calls"].append({
                "pattern": pattern,
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    return result


def research_um_json(cookie_str: str = "") -> Dict[str, Any]:
    """路线 G 核心研究函数：综合分析 um.json 设备指纹端点。

    本函数执行以下研究步骤：
    1. 探测所有已知 um.json 端点（POST/GET 两种方式 × NVC_Data/简单字段两种格式）
    2. 使用不同 appkey 组合
    3. 分析响应格式、Set-Cookie 行为、umid_id 字段
    4. 识别可用的设备指纹 cookie（umt/cna/isg）和 umidToken
    5. 如果获取到 cookie 或 umidToken，尝试重试 initialize.jsonp

    Args:
        cookie_str: Cookie 字符串（可选）

    Returns:
        综合研究结果 dict：
        {
            "endpoint_probes": list,       # 所有端点探测结果
            "umt_obtained": bool,           # 是否获取到 umt cookie
            "cna_obtained": bool,           # 是否获取到 cna cookie
            "umid_obtained": bool,          # 是否获取到 umidToken（id 字段）
            "best_probe": dict,             # 最佳探测结果
            "findings": list,               # 研究发现
            "recommendations": list,        # 后续建议
            "initialize_retry": dict,       # 使用获取的 cookie 重试 initialize.jsonp 的结果
        }
    """
    result: Dict[str, Any] = {
        "endpoint_probes": [],
        "umt_obtained": False,
        "cna_obtained": False,
        "isg_obtained": False,
        "umid_obtained": False,
        "best_probe": None,
        "findings": [],
        "recommendations": [],
        "initialize_retry": None,
    }

    logger.info("[方案K-路线G] 开始 um.json 设备指纹端点综合研究（v2: NVC_Data 结构）")

    # 步骤 1：探测所有端点（POST + GET 方式 × NVC_Data + 简单字段两种格式）
    # 优先测试 NVC_Data 结构（真实请求体格式），再测试简单字段格式
    for endpoint in UM_JSON_ENDPOINTS:
        for use_nvc in [True, False]:  # True=NVC_Data, False=简单字段
            for method in [True, False]:  # True=POST, False=GET
                for appkey in UM_JSON_APPKEYS.keys():
                    probe = probe_um_json_endpoint(
                        endpoint_url=endpoint,
                        appkey=appkey,
                        cookie_str=cookie_str,
                        use_post=method,
                        use_nvc_data=use_nvc,
                    )
                    result["endpoint_probes"].append(probe)

                    if probe["umt_cookie"]:
                        result["umt_obtained"] = True
                    if probe["cna_cookie"]:
                        result["cna_obtained"] = True
                    if probe["isg_cookie"]:
                        result["isg_obtained"] = True
                    if probe.get("umid_id"):
                        result["umid_obtained"] = True

                    # 记录第一个成功的探测为 best_probe
                    if not result["best_probe"] and (
                        probe["umt_cookie"] or probe["cna_cookie"] or probe.get("umid_id")
                    ):
                        result["best_probe"] = probe
                        logger.info(
                            "[方案K-路线G] ✓ 获取到设备指纹：%s",
                            endpoint,
                        )

    # 步骤 2：研究发现
    success_probes = [
        p for p in result["endpoint_probes"]
        if p["umt_cookie"] or p["cna_cookie"] or p.get("umid_id")
    ]
    fail_probes = [
        p for p in result["endpoint_probes"]
        if not (p["umt_cookie"] or p["cna_cookie"] or p.get("umid_id"))
    ]

    if success_probes:
        result["findings"].append({
            "type": "success",
            "message": f"✓ 发现 {len(success_probes)} 个端点配置返回了设备指纹",
        })
        # 分析成功配置
        for p in success_probes[:3]:
            result["findings"].append({
                "type": "success_detail",
                "message": (
                    f"  端点：{p['url']} 方法：{p['method']} NVC_Data：{p.get('use_nvc_data')} "
                    f"appkey：{p['appkey']} 状态码：{p['status_code']} "
                    f"cookies：{p['cookies_obtained']} umid_id：{bool(p.get('umid_id'))}"
                ),
            })
    else:
        result["findings"].append({
            "type": "failure",
            "message": (
                f"✗ 所有 {len(result['endpoint_probes'])} 个探测均未获取到 umt/cna cookie 或 umidToken，"
                f"um.json 可能需要：(a) FireyeJS 计算的 FYToken/umidToken，"
                f"(b) 浏览器环境，(c) 特定的 Referer/Origin，(d) JS 计算的签名"
            ),
        })

    # 分析失败响应的状态码分布和响应内容
    if fail_probes:
        status_dist = {}
        response_samples = {}
        for p in fail_probes:
            status = p["status_code"] or "error"
            status_dist[status] = status_dist.get(status, 0) + 1
            # 收集每种状态码的响应预览样本
            if status not in response_samples and p.get("response_preview"):
                response_samples[status] = p["response_preview"][:200]
        result["findings"].append({
            "type": "status_distribution",
            "message": f"失败探测状态码分布：{status_dist}",
        })
        result["findings"].append({
            "type": "response_samples",
            "message": f"失败响应样本：{response_samples}",
        })

    # 步骤 3：建议
    if result["umt_obtained"] or result["cna_obtained"] or result["umid_obtained"]:
        result["recommendations"].append(
            "✓ 已获取设备指纹，下一步："
            "1. 将 umt/cna/isg cookie 或 umidToken 注入到 initialize.jsonp 请求中重试，"
            "观察是否返回合法 token；"
            "2. 如果 initialize.jsonp 返回 token，进一步尝试 analyze.jsonp；"
            "3. 如果 analyze.jsonp 通过，最终获取 x5sec"
        )
    else:
        result["recommendations"].append(
            "✗ 未获取设备指纹，下一步研究方向：\n"
            "1. **【关键】** 研究 FireyeJS 的 getFYToken() 和 getUidToken() 函数，"
            "um.json 请求体的 b 和 h.umidToken 字段需要这两个函数的返回值；\n"
            "2. 通过 crawler-service 浏览器捕获真实的 um.json 请求，"
            "获取完整的 NVC_Data 数据格式（含真实 FYToken）；\n"
            "3. 检查 um.json 是否需要先访问主页获取 cna cookie（先有 cna 才有 umt）；\n"
            "4. 尝试不同的 Origin/Referer 组合（如 alipay.com / taobao.com）；\n"
            "5. 研究 FireyeJS 是否有独立的初始化端点（可能不是 um.json）"
        )

    # 步骤 4：如果获取到 cookie 或 umidToken，尝试重试 initialize.jsonp
    if result["best_probe"]:
        retry_result = _retry_initialize_with_fingerprint_cookies(
            result["best_probe"],
            cookie_str,
        )
        result["initialize_retry"] = retry_result

    return result


def _retry_initialize_with_fingerprint_cookies(
    um_json_probe: Dict[str, Any],
    original_cookie: str = "",
) -> Dict[str, Any]:
    """使用 um.json 获取的设备指纹 cookie 或 umidToken 重试 initialize.jsonp。

    本函数是路线 G 与路线 F 的衔接点：
    - 路线 G 获取 umt/cna/isg cookie 或 umidToken（id 字段）
    - 将 cookie 注入到请求头中，umidToken 作为查询参数
    - 重试 initialize.jsonp，观察是否返回合法 token

    Args:
        um_json_probe: probe_um_json_endpoint 的返回结果
        original_cookie: 原始 Cookie 字符串

    Returns:
        重试结果 dict：
        {
            "injected_cookies": dict,    # 注入的 cookie
            "umid_token": str,            # 注入的 umidToken
            "initialize_probes": list,   # initialize.jsonp 重试结果
            "token_obtained": bool,
            "best_token": str,
        }
    """
    result: Dict[str, Any] = {
        "injected_cookies": {},
        "umid_token": "",
        "initialize_probes": [],
        "token_obtained": False,
        "best_token": "",
    }

    # 构造注入的 cookie 字符串
    injected_parts = []
    if um_json_probe.get("umt_cookie"):
        result["injected_cookies"]["umt"] = um_json_probe["umt_cookie"]
        injected_parts.append(f"umt={um_json_probe['umt_cookie']}")
    if um_json_probe.get("cna_cookie"):
        result["injected_cookies"]["cna"] = um_json_probe["cna_cookie"]
        injected_parts.append(f"cna={um_json_probe['cna_cookie']}")
    if um_json_probe.get("isg_cookie"):
        result["injected_cookies"]["isg"] = um_json_probe["isg_cookie"]
        injected_parts.append(f"isg={um_json_probe['isg_cookie']}")

    # 提取 umidToken（id 字段）
    if um_json_probe.get("umid_id"):
        result["umid_token"] = um_json_probe["umid_id"]

    if not injected_parts and not result["umid_token"]:
        result["error"] = "无设备指纹 cookie 或 umidToken 可注入"
        return result

    # 合并原始 cookie + 注入的 cookie
    base_cookie = original_cookie or ""
    combined_cookie = base_cookie
    for part in injected_parts:
        # 如果原始 cookie 中已有同名字段，先移除
        cookie_name = part.split("=")[0]
        combined_cookie = re.sub(
            rf'(?:^|;\s*){cookie_name}=[^;]+;?\s*',
            '',
            combined_cookie,
        )
        combined_cookie = f"{combined_cookie}; {part}".lstrip("; ")

    logger.info(
        "[方案K-路线G] 使用设备指纹重试 initialize.jsonp：cookies=%s umidToken=%s",
        list(result["injected_cookies"].keys()),
        "✓" if result["umid_token"] else "✗",
    )

    # 重试所有 initialize.jsonp 端点
    # 如果有 umidToken，作为查询参数传入（nc.js 中的初始化流程）
    for endpoint in INITIALIZE_JSONP_ENDPOINTS:
        for appkey_name, appkey_info in NOCAPTCHA_APPKEYS.items():
            probe = probe_initialize_jsonp_endpoint(
                endpoint_url=endpoint,
                appkey=appkey_name,
                scene=appkey_info.get("scene", "nc_h5"),
                cookie_str=combined_cookie,
            )

            # 如果有 umidToken，尝试作为查询参数重试
            if result["umid_token"] and not probe.get("token"):
                # 构造带 umidToken 的 URL
                separator = "&" if "?" in endpoint else "?"
                endpoint_with_umid = f"{endpoint}{separator}umidToken={result['umid_token']}"
                probe_with_umid = probe_initialize_jsonp_endpoint(
                    endpoint_url=endpoint_with_umid,
                    appkey=appkey_name,
                    scene=appkey_info.get("scene", "nc_h5"),
                    cookie_str=combined_cookie,
                )
                if probe_with_umid.get("token"):
                    probe = probe_with_umid

            result["initialize_probes"].append(probe)

            if probe.get("token"):
                result["token_obtained"] = True
                if not result["best_token"]:
                    result["best_token"] = probe["token"]
                    logger.info(
                        "[方案K-路线G] ✓✓ initialize.jsonp 返回 token（长度=%d）",
                        len(probe["token"]),
                    )

    return result


# ============================================================
# 模块初始化日志
# ============================================================

if PLAN_K_ENABLED:
    logger.info("[方案K] 模块已启用 PLAN_K_ENABLED=true（研究阶段，generate_x5sec_locally 仍返回 None）")
else:
    logger.debug("[方案K] 模块未启用（PLAN_K_ENABLED=false），仅作为研究框架存在")


# ============================================================
# 15. 路线 H：FireyeJS 逆向研究（um.json 的关键瓶颈）
# ============================================================
#
# 当前瓶颈（来自路线 G 的研究结果）：
#   - um.json 端点接受请求但返回 {"id":""}（缺少必要字段）
#   - 原因：um.json 请求体需要 FireyeJS 计算的两个 token：
#     * b 字段 = __fy.getFYToken(__fy_options) ← 行为特征 token
#     * h.umidToken = __fy.getUidToken() ← 设备指纹 token
#   - 没有 FireyeJS 计算的 token，um.json 不会返回有效的 umidToken
#
# 路线 H 的目标：
#   1. 从 nc.js 中提取 FireyeJS 的初始化代码和 __fy_options 结构
#   2. 分析 getFYToken() 和 getUidToken() 的输入输出
#   3. 研究 FireyeJS 是否有独立的 JS 文件（如 fireye.js）
#   4. 尝试通过 crawler-service 浏览器执行 FireyeJS 获取真实 token
#   5. 如果获取到 token，注入到 um.json 请求体重试
#
# 关键认知：
#   - FireyeJS 是阿里集团的反爬虫 JS 库（类似 reCAPTCHA）
#   - __fy 是 FireyeJS 的全局对象，挂载在 window.__fy
#   - __fy_options 是 FireyeJS 的配置对象（含 appkey/scene/行为数据）
#   - getFYToken() 返回行为特征 token（基于鼠标/键盘/触摸事件）
#   - getUidToken() 返回设备指纹 token（基于 Canvas/WebGL/AudioContext）
#   - FireyeJS 可能动态加载（不在主页静态 JS 中）

# FireyeJS 关键标识符（用于在 JS 中定位）
FIREYEJS_IDENTIFIERS = [
    "__fy",
    "FireyeJS",
    "getFYToken",
    "getUidToken",
    "__fy_options",
    "fy_token",
    "fireye",
    "NVC_Data",
    "NVC_Result",
    "nvcPreRes",
]

# FireyeJS 可能的 JS 文件 URL 模式
FIREYEJS_JS_PATTERNS = [
    r'https?://[^"\']*fireye[^"\']*\.js',
    r'https?://[^"\']*fy[^"\']*\.js',
    r'https?://[^"\']*nocaptcha[^"\']*\.js',
    r'https?://[^"\']*nc[^"\']*\.js',
    r'/[^"\']*fireye[^"\']*\.js',
    r'/[^"\']*fy[^"\']*\.js',
]


def extract_fireyejs_from_nc_js(nc_js_content: str) -> Dict[str, Any]:
    """从 nc.js 源码中提取 FireyeJS 相关代码。

    本函数定位 nc.js 中：
    - FireyeJS 初始化代码（__fy 对象创建）
    - __fy_options 配置结构
    - getFYToken() 调用位置
    - getUidToken() 调用位置
    - NVC_Data 构造逻辑
    - FireyeJS 外部 JS 引用

    Args:
        nc_js_content: nc.js 源码内容

    Returns:
        分析结果 dict：
        {
            "identifiers": dict,           # 各标识符出现位置
            "fy_init_code": list,          # FireyeJS 初始化代码
            "fy_options_structure": list,  # __fy_options 配置代码
            "get_fy_token_calls": list,    # getFYToken 调用
            "get_uid_token_calls": list,   # getUidToken 调用
            "nvc_data_construction": list, # NVC_Data 构造
            "external_js_refs": list,      # 外部 JS 引用
        }
    """
    result: Dict[str, Any] = {
        "identifiers": {},
        "fy_init_code": [],
        "fy_options_structure": [],
        "get_fy_token_calls": [],
        "get_uid_token_calls": [],
        "nvc_data_construction": [],
        "external_js_refs": [],
    }

    if not nc_js_content:
        return result

    # 1. 统计各标识符出现次数和位置
    for identifier in FIREYEJS_IDENTIFIERS:
        locations = []
        for match in re.finditer(re.escape(identifier), nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 300)
            locations.append({
                "offset": match.start(),
                "context": nc_js_content[start:end],
            })
        result["identifiers"][identifier] = {
            "count": len(locations),
            "first_locations": locations[:3],  # 只保留前 3 个位置
        }

    # 2. 提取 FireyeJS 初始化代码（__fy = ... 或 window.__fy = ...）
    init_patterns = [
        r'(?:window\.)?__fy\s*[:=]\s*[^;]+',
        r'(?:window\.)?__fy\s*=\s*new\s+[^;]+',
        r'FireyeJS\s*\([^)]*\)',
    ]
    for pattern in init_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 400)
            result["fy_init_code"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 3. 提取 __fy_options 配置结构
    options_patterns = [
        r'__fy_options\s*[:=]\s*\{[^}]+\}',
        r'__fy_options\.\w+\s*[:=]\s*[^;]+',
        r'fy_options\s*[:=]\s*\{[^}]+\}',
    ]
    for pattern in options_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 300)
            result["fy_options_structure"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 4. 提取 getFYToken 调用
    for match in re.finditer(r'getFYToken\s*\([^)]*\)', nc_js_content):
        start = max(0, match.start() - 200)
        end = min(len(nc_js_content), match.end() + 300)
        result["get_fy_token_calls"].append({
            "code": nc_js_content[start:end],
            "offset": match.start(),
        })

    # 5. 提取 getUidToken 调用
    for match in re.finditer(r'getUidToken\s*\([^)]*\)', nc_js_content):
        start = max(0, match.start() - 200)
        end = min(len(nc_js_content), match.end() + 300)
        result["get_uid_token_calls"].append({
            "code": nc_js_content[start:end],
            "offset": match.start(),
        })

    # 6. 提取 NVC_Data 构造逻辑
    nvc_patterns = [
        r'NVC_Data\s*[:=]\s*\{[^}]+\}',
        r'NVC_Data\.\w+\s*[:=]\s*[^;]+',
        r'NVC_Result\s*[:=]\s*\{[^}]+\}',
        r'NVC_Result\.\w+\s*[:=]\s*[^;]+',
    ]
    for pattern in nvc_patterns:
        for match in re.finditer(pattern, nc_js_content):
            start = max(0, match.start() - 100)
            end = min(len(nc_js_content), match.end() + 300)
            result["nvc_data_construction"].append({
                "code": nc_js_content[start:end],
                "offset": match.start(),
            })

    # 7. 提取外部 JS 引用（可能是 FireyeJS 独立文件）
    for pattern in FIREYEJS_JS_PATTERNS:
        for match in re.finditer(pattern, nc_js_content, re.IGNORECASE):
            result["external_js_refs"].append({
                "url": match.group(0),
                "offset": match.start(),
            })

    return result


def research_fireyejs(cookie_str: str = "") -> Dict[str, Any]:
    """路线 H 核心研究函数：综合分析 FireyeJS 逆向可行性。

    本函数执行以下研究步骤：
    1. 下载 nc.js 并提取 FireyeJS 相关代码
    2. 分析 FireyeJS 初始化逻辑和 __fy_options 结构
    3. 定位 getFYToken() 和 getUidToken() 调用位置
    4. 识别 FireyeJS 是否有独立的 JS 文件
    5. 评估逆向可行性（是否能纯 Python 复现）

    Args:
        cookie_str: Cookie 字符串（可选）

    Returns:
        综合研究结果 dict：
        {
            "nc_js_download": dict,        # nc.js 下载结果
            "fireyejs_extraction": dict,   # FireyeJS 代码提取结果
            "findings": list,              # 研究发现
            "recommendations": list,       # 后续建议
            "feasibility": str,            # 逆向可行性评估
        }
    """
    result: Dict[str, Any] = {
        "nc_js_download": None,
        "fireyejs_extraction": None,
        "findings": [],
        "recommendations": [],
        "feasibility": "unknown",
    }

    logger.info("[方案K-路线H] 开始 FireyeJS 逆向研究")

    # 步骤 1：下载 nc.js
    download_result = download_nc_js()
    result["nc_js_download"] = download_result

    nc_js_content = ""
    for d in download_result.get("downloads", []):
        if "nc.js" in d["url"] and d["content"]:
            nc_js_content = d["content"]
            break

    if not nc_js_content:
        result["findings"].append({
            "type": "error",
            "message": "✗ nc.js 下载失败，无法进行 FireyeJS 逆向研究",
        })
        result["feasibility"] = "blocked"
        return result

    # 步骤 2：提取 FireyeJS 相关代码
    extraction = extract_fireyejs_from_nc_js(nc_js_content)
    result["fireyejs_extraction"] = extraction

    # 步骤 3：分析发现
    identifiers = extraction.get("identifiers", {})
    fy_init_count = len(extraction.get("fy_init_code", []))
    fy_options_count = len(extraction.get("fy_options_structure", []))
    get_fy_token_count = len(extraction.get("get_fy_token_calls", []))
    get_uid_token_count = len(extraction.get("get_uid_token_calls", []))
    nvc_data_count = len(extraction.get("nvc_data_construction", []))
    external_js_count = len(extraction.get("external_js_refs", []))

    result["findings"].append({
        "type": "identifier_stats",
        "message": (
            f"FireyeJS 标识符统计："
            f"__fy={identifiers.get('__fy', {}).get('count', 0)}次, "
            f"getFYToken={identifiers.get('getFYToken', {}).get('count', 0)}次, "
            f"getUidToken={identifiers.get('getUidToken', {}).get('count', 0)}次, "
            f"__fy_options={identifiers.get('__fy_options', {}).get('count', 0)}次"
        ),
    })

    result["findings"].append({
        "type": "code_extraction",
        "message": (
            f"代码提取统计："
            f"初始化代码={fy_init_count}处, "
            f"__fy_options配置={fy_options_count}处, "
            f"getFYToken调用={get_fy_token_count}处, "
            f"getUidToken调用={get_uid_token_count}处, "
            f"NVC_Data构造={nvc_data_count}处, "
            f"外部JS引用={external_js_count}处"
        ),
    })

    # 分析 FireyeJS 是否在 nc.js 中内联实现
    if identifiers.get("getFYToken", {}).get("count", 0) > 0:
        result["findings"].append({
            "type": "inline_implementation",
            "message": (
                "✓ FireyeJS 的 getFYToken 在 nc.js 中有实现，"
                "可能是内联代码（不需要额外加载 fireye.js）"
            ),
        })
    else:
        result["findings"].append({
            "type": "external_implementation",
            "message": (
                "✗ nc.js 中没有 getFYToken 实现，"
                "FireyeJS 可能通过外部 JS 文件动态加载"
            ),
        })

    # 分析外部 JS 引用
    if external_js_count > 0:
        external_urls = [ref["url"] for ref in extraction.get("external_js_refs", [])]
        result["findings"].append({
            "type": "external_js",
            "message": f"发现 {external_js_count} 个外部 JS 引用：{external_urls[:5]}",
        })

    # 步骤 4：可行性评估
    if get_fy_token_count > 0 and get_uid_token_count > 0:
        # 如果 getFYToken 和 getUidToken 都在 nc.js 中实现
        result["feasibility"] = "medium"
        result["findings"].append({
            "type": "feasibility",
            "message": (
                "逆向可行性：中等。getFYToken 和 getUidToken 在 nc.js 中有实现，"
                "但代码经过压缩混淆，需要深入分析算法逻辑。"
                "建议通过 crawler-service 浏览器执行 JS 获取真实 token，"
                "而不是纯 Python 复现。"
            ),
        })
    elif external_js_count > 0:
        result["feasibility"] = "low"
        result["findings"].append({
            "type": "feasibility",
            "message": (
                "逆向可行性：低。FireyeJS 通过外部 JS 动态加载，"
                "需要先下载并分析外部 JS 文件。"
            ),
        })
    else:
        result["feasibility"] = "unknown"
        result["findings"].append({
            "type": "feasibility",
            "message": "逆向可行性：未知。需要进一步分析 nc.js 代码结构。",
        })

    # 步骤 5：建议
    result["recommendations"].append(
        "下一步研究方向：\n"
        "1. **【推荐】** 通过 crawler-service 浏览器执行 FireyeJS，"
        "获取真实的 FYToken 和 umidToken，注入到 um.json 请求体；\n"
        "2. 深入分析 nc.js 中 getFYToken 的实现代码，"
        "识别其依赖的浏览器 API（Canvas/WebGL/AudioContext）；\n"
        "3. 检查 __fy_options 的完整结构，"
        "确定 FireyeJS 初始化需要哪些配置参数；\n"
        "4. 研究 FireyeJS 是否有公开的 API 文档或开源实现；\n"
        "5. 尝试在 Node.js 环境中执行 nc.js（需 mock 浏览器 API），"
        "获取 FireyeJS token"
    )

    return result


# ============================================================
# 16. 路线 I：fireyejs.js 独立文件深度分析
# ============================================================
# 背景：
#   路线 H 发现 nc.js 中存在 getFYToken/getUidToken 的调用，但代码高度混淆，
#   难以直接分析算法逻辑。同时 nc.js 引用了独立文件 fireyejs.js（约 580KB），
#   该文件包含 FireyeJS 的完整实现。
#
# 路线 I 的目标：
#   1. 下载独立的 fireyejs.js 文件（多版本探测）
#   2. 深度分析 JS 结构（函数列表、加密算法、浏览器 API 依赖）
#   3. 定位 getFYToken() 和 getUidToken() 的实现位置
#   4. 识别所有浏览器 API 依赖（Canvas/WebGL/AudioContext/navigator/screen）
#   5. 评估在 Node.js 环境中 mock 浏览器 API 执行 FireyeJS 的可行性
#
# 关键认知：
#   - FireyeJS 是阿里集团的反爬虫 JS 库，独立文件比 nc.js 内联代码更完整
#   - getFYToken() 依赖鼠标/键盘/触摸事件采集（行为特征）
#   - getUidToken() 依赖 Canvas/WebGL/AudioContext（设备指纹）
#   - 在 Node.js 中 mock 浏览器 API 是可行的，但需要 mock 大量 API
#   - 已知 FireyeJS 版本：1.234.20（当前）、可能存在历史版本

# FireyeJS 已知版本 URL 列表（按优先级排序，新版本可能更稳定）
FIREYEJS_VERSION_URLS = [
    "https://g.alicdn.com/AWSC/fireyejs/1.234.20/fireyejs.js",  # 当前版本
    "https://g.alicdn.com/AWSC/fireyejs/1.234.19/fireyejs.js",  # 历史版本
    "https://g.alicdn.com/AWSC/fireyejs/1.234.18/fireyejs.js",
    "https://g.alicdn.com/AWSC/fireyejs/1.234.17/fireyejs.js",
    "https://g.alicdn.com/AWSC/fireyejs/1.234.16/fireyejs.js",
]

# 浏览器 API 依赖模式（用于识别 FireyeJS 调用的浏览器 API）
# 这些 API 是 getFYToken() 和 getUidToken() 的关键依赖
FIREYEJS_BROWSER_API_PATTERNS = {
    # 设备指纹相关
    "canvas": [
        r"\.getContext\s*\(\s*['\"]2d['\"]\s*\)",
        r"\.getContext\s*\(\s*['\"]webgl['\"]\s*\)",
        r"\.getContext\s*\(\s*['\"]experimental-webgl['\"]\s*\)",
        r"canvas\.toDataURL",
        r"getImageData",
        r"fillText",
        r"measureText",
    ],
    "webgl": [
        r"getParameter\s*\(",
        r"getExtension\s*\(",
        r"getSupportedExtensions",
        r"UNMASKED_VENDOR_WEBGL",
        r"UNMASKED_RENDERER_WEBGL",
        r"createBuffer",
        r"shaderSource",
    ],
    "audio": [
        r"AudioContext",
        r"webkitAudioContext",
        r"OfflineAudioContext",
        r"createOscillator",
        r"createAnalyser",
        r"createDynamicsCompressor",
        r"createGain",
        r"startRendering",
        r"getChannelData",
    ],
    "navigator": [
        r"navigator\.userAgent",
        r"navigator\.platform",
        r"navigator\.language",
        r"navigator\.languages",
        r"navigator\.hardwareConcurrency",
        r"navigator\.deviceMemory",
        r"navigator\.maxTouchPoints",
        r"navigator\.plugins",
        r"navigator\.cookieEnabled",
        r"navigator\.doNotTrack",
        r"navigator\.vendor",
        r"navigator\.connection",
    ],
    "screen": [
        r"screen\.width",
        r"screen\.height",
        r"screen\.availWidth",
        r"screen\.availHeight",
        r"screen\.colorDepth",
        r"screen\.pixelDepth",
        r"window\.devicePixelRatio",
        r"window\.innerWidth",
        r"window\.innerHeight",
        r"window\.outerWidth",
        r"window\.outerHeight",
    ],
    "storage": [
        r"localStorage",
        r"sessionStorage",
        r"indexedDB",
        r"document\.cookie",
    ],
    "timing": [
        r"performance\.now",
        r"performance\.timing",
        r"Date\.now",
        r"performance\.getEntries",
        r"requestAnimationFrame",
    ],
    "events": [
        r"addEventListener\s*\(",
        r"removeEventListener",
        r"onmousemove",
        r"onmousedown",
        r"onmouseup",
        r"onkeydown",
        r"onkeyup",
        r"ontouchstart",
        r"ontouchend",
        r"ontouchmove",
        r"ondevicemotion",
        r"ondeviceorientation",
    ],
    "crypto_api": [
        r"window\.crypto",
        r"crypto\.subtle",
        r"crypto\.getRandomValues",
        r"msCrypto",
    ],
    "worker": [
        r"Worker\s*\(",
        r"SharedWorker",
        r"ServiceWorker",
        r"postMessage",
    ],
    "webrtc": [
        r"RTCPeerConnection",
        r"webkitRTCPeerConnection",
        r"createDataChannel",
        r"createOffer",
        r"onicecandidate",
    ],
    "battery": [
        r"navigator\.getBattery",
        r"battery\.level",
        r"battery\.charging",
    ],
    "media": [
        r"navigator\.mediaDevices",
        r"enumerateDevices",
        r"getUserMedia",
    ],
}

# 加密算法指示器（用于识别 FireyeJS 内部使用的加密算法）
FIREYEJS_CRYPTO_INDICATORS = {
    "md5": [
        r"\bmd5\s*\(",
        r"0xefcdab89",
        r"0x98badcfe",
        r"0x10325476",
        r"0x67452301",
    ],
    "sha1": [
        r"\bsha1\s*\(",
        r"0xc3d2e1f0",
        r"0x5a827999",
        r"0x6ed9eba1",
    ],
    "sha256": [
        r"\bsha256\s*\(",
        r"0x6a09e667",
        r"0xbb67ae85",
        r"0x3c6ef372",
    ],
    "aes": [
        r"\bAES\s*\(",
        r"encrypt\s*\(",
        r"decrypt\s*\(",
        r"Rijndael",
        r"SubBytes",
        r"ShiftRows",
        r"MixColumns",
    ],
    "hmac": [
        r"\bhmac\s*\(",
        r"HmacSHA",
        r"HmacMD5",
    ],
    "base64": [
        r"btoa\s*\(",
        r"atob\s*\(",
        r"fromCharCode",
        r"charCodeAt",
        r"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    ],
    "xor": [
        r"\^0x[0-9a-fA-F]+",
        r"fromCharCode\s*\(\s*\w+\s*\^\s*\w+\s*\)",
    ],
    "rc4": [
        r"\brc4\s*\(",
        r"\bRC4\s*\(",
    ],
    "custom_hash": [
        r"0x9e3779b9",  # TEA/XTEA 算法魔数
        r"0xc6ef3720",  # TEA delta
        r"\btea\s*\(",
        r"\bxtea\s*\(",
    ],
}

# FireyeJS 内部关键标识符（用于定位核心函数实现）
FIREYEJS_INTERNAL_MARKERS = [
    # 函数名
    "getFYToken",
    "getUidToken",
    "getToken",
    "getUMIDToken",
    "getUmidToken",
    # 内部对象
    "__fy",
    "FireyeJS",
    "fireye",
    "fy_options",
    # 输出字段
    "FYToken",
    "umidToken",
    "uToken",
    "behaviorToken",
    "deviceToken",
    # 配置
    "appkey",
    "scene",
    "isInit",
    # 序列化
    "JSON.stringify",
    "JSON.parse",
]


def download_fireyejs_js(version_url: str = "") -> Dict[str, Any]:
    """下载独立的 fireyejs.js 文件。

    路线 I 第一步：获取 FireyeJS 独立 JS 文件的完整内容。
    支持多版本探测，按优先级依次尝试下载。

    Args:
        version_url: 指定版本的 URL，空字符串时按优先级下载所有已知版本

    Returns:
        下载结果 dict：
        {
            "downloads": [
                {
                    "url": str,
                    "status_code": int,
                    "length": int,
                    "content": str,  # JS 内容（限制 800KB）
                    "error": str,
                    "duration_ms": int,
                },
            ],
            "best_version": str,  # 最优先成功的 URL
        }
    """
    result: Dict[str, Any] = {"downloads": [], "best_version": ""}

    urls_to_download = [version_url] if version_url else FIREYEJS_VERSION_URLS

    try:
        import requests as _requests
        import time as _time

        for url in urls_to_download:
            download_result: Dict[str, Any] = {
                "url": url,
                "status_code": 0,
                "length": 0,
                "content": "",
                "error": "",
                "duration_ms": 0,
            }
            try:
                t0 = _time.time()
                resp = _requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "*/*",
                        "Referer": "https://www.goofish.com/",
                    },
                    timeout=15,
                )
                download_result["status_code"] = resp.status_code
                download_result["duration_ms"] = int((_time.time() - t0) * 1000)

                if resp.status_code == 200:
                    # 限制 800KB（fireyejs.js 约 580KB）
                    content = resp.text[:800_000]
                    download_result["content"] = content
                    download_result["length"] = len(content)
                    logger.info(
                        "[方案K-路线I] fireyejs.js 下载成功: %s (长度=%d, 耗时=%dms)",
                        url, len(content), download_result["duration_ms"],
                    )
                    if not result["best_version"]:
                        result["best_version"] = url
                else:
                    download_result["error"] = f"HTTP {resp.status_code}"
                    logger.debug(
                        "[方案K-路线I] fireyejs.js 下载失败: %s (状态码=%d)",
                        url, resp.status_code,
                    )
            except Exception as e:
                download_result["error"] = str(e)
                logger.warning(
                    "[方案K-路线I] fireyejs.js 下载异常: %s - %s", url, e,
                )
            result["downloads"].append(download_result)

    except Exception as e:
        logger.error("[方案K-路线I] download_fireyejs_js 异常: %s", e)

    return result


def analyze_fireyejs_js_structure(js_content: str) -> Dict[str, Any]:
    """深度分析 fireyejs.js 的代码结构。

    路线 I 第二步：分析 JS 文件的函数列表、压缩混淆程度、
    加密算法指示器、浏览器 API 依赖等。

    Args:
        js_content: fireyejs.js 的完整内容

    Returns:
        分析结果 dict：
        {
            "length": int,
            "is_minified": bool,
            "function_count": int,
            "function_names": list,
            "avg_function_name_length": float,
            "eval_usage_count": int,
            "string_constant_count": int,
            "has_x5sec_reference": bool,
            "has_set_cookie": bool,
            "has_get_token": bool,
            "has_punish_handler": bool,
            "crypto_indicators": dict,  # 各加密算法命中情况
            "browser_api_usage": dict,  # 各浏览器 API 命中情况
            "internal_markers": dict,   # 内部标识符命中情况
            "token_generation_locations": list,  # token 生成函数位置
            "findings": list,
        }
    """
    result: Dict[str, Any] = {
        "length": len(js_content) if js_content else 0,
        "is_minified": False,
        "function_count": 0,
        "function_names": [],
        "avg_function_name_length": 0.0,
        "eval_usage_count": 0,
        "string_constant_count": 0,
        "has_x5sec_reference": False,
        "has_set_cookie": False,
        "has_get_token": False,
        "has_punish_handler": False,
        "crypto_indicators": {},
        "browser_api_usage": {},
        "internal_markers": {},
        "token_generation_locations": [],
        "findings": [],
    }

    if not js_content:
        result["findings"].append({"type": "error", "message": "JS 内容为空"})
        return result

    # 1. 基础结构分析
    # 函数定义计数（function xxx(, var xxx = function, xxx: function）
    function_pattern = re.compile(
        r'(?:function\s+([a-zA-Z_$][\w$]*)\s*\(|'
        r'(?:var|let|const)\s+([a-zA-Z_$][\w$]*)\s*=\s*function\s*\(|'
        r'([a-zA-Z_$][\w$]*)\s*:\s*function\s*\()'
    )
    function_names = []
    for match in function_pattern.finditer(js_content):
        name = match.group(1) or match.group(2) or match.group(3)
        if name:
            function_names.append(name)

    result["function_count"] = len(function_names)
    result["function_names"] = function_names[:50]  # 只保留前 50 个
    if function_names:
        avg_len = sum(len(n) for n in function_names) / len(function_names)
        result["avg_function_name_length"] = round(avg_len, 2)

    # 压缩混淆判断：平均函数名长度 < 3 或 eval 使用频繁
    result["eval_usage_count"] = len(re.findall(r'\beval\s*\(', js_content))
    result["is_minified"] = (
        result["avg_function_name_length"] < 3
        or (result["length"] > 100_000 and result["function_count"] < 50)
    )

    # 字符串常量计数
    result["string_constant_count"] = len(re.findall(r'"[^"]{3,}"|\'[^\']{3,}\'', js_content))

    # 2. 关键功能检测
    result["has_x5sec_reference"] = "x5sec" in js_content.lower()
    result["has_set_cookie"] = "document.cookie" in js_content and "=" in js_content
    result["has_get_token"] = bool(re.search(r'get(?:FY|Uid|UMID|Umid)?Token\s*\(', js_content))
    result["has_punish_handler"] = "punish" in js_content.lower()

    # 3. 加密算法指示器检测
    for algo, patterns in FIREYEJS_CRYPTO_INDICATORS.items():
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, js_content, re.IGNORECASE)
            if found:
                matches.append({"pattern": pattern, "count": len(found)})
        if matches:
            result["crypto_indicators"][algo] = {
                "total_matches": sum(m["count"] for m in matches),
                "patterns": matches,
            }

    # 4. 浏览器 API 依赖检测
    for api_category, patterns in FIREYEJS_BROWSER_API_PATTERNS.items():
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, js_content)
            if found:
                matches.append({"pattern": pattern, "count": len(found)})
        if matches:
            result["browser_api_usage"][api_category] = {
                "total_matches": sum(m["count"] for m in matches),
                "patterns": matches,
            }

    # 5. 内部标识符命中情况
    for marker in FIREYEJS_INTERNAL_MARKERS:
        count = js_content.count(marker)
        if count > 0:
            # 找到前 3 个出现位置
            locations = []
            for match in re.finditer(re.escape(marker), js_content):
                start = max(0, match.start() - 100)
                end = min(len(js_content), match.end() + 200)
                locations.append({
                    "offset": match.start(),
                    "context": js_content[start:end],
                })
                if len(locations) >= 3:
                    break
            result["internal_markers"][marker] = {
                "count": count,
                "locations": locations,
            }

    # 6. 定位 token 生成函数实现位置
    token_funcs = ["getFYToken", "getUidToken", "getUMIDToken", "getUmidToken", "getToken"]
    for func_name in token_funcs:
        # 匹配函数定义（支持多种定义方式）
        patterns = [
            rf'{re.escape(func_name)}\s*:\s*function\s*\([^)]*\)\s*\{{',
            rf'{re.escape(func_name)}\s*=\s*function\s*\([^)]*\)\s*\{{',
            rf'function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{',
            rf'{re.escape(func_name)}\s*[:=]\s*function',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, js_content):
                start = max(0, match.start() - 100)
                # 截取函数前 800 字符作为预览
                end = min(len(js_content), match.start() + 800)
                result["token_generation_locations"].append({
                    "function": func_name,
                    "offset": match.start(),
                    "preview": js_content[start:end],
                    "pattern": pattern,
                })

    # 7. 生成发现
    if result["is_minified"]:
        result["findings"].append({
            "type": "minified",
            "message": f"✓ fireyejs.js 经过压缩混淆（长度={result['length']}, 函数数={result['function_count']}, 平均函数名长度={result['avg_function_name_length']}）",
        })
    else:
        result["findings"].append({
            "type": "readable",
            "message": f"✓ fireyejs.js 未压缩（长度={result['length']}, 函数数={result['function_count']}），可读性较好",
        })

    if result["crypto_indicators"]:
        algos = list(result["crypto_indicators"].keys())
        result["findings"].append({
            "type": "crypto",
            "message": f"✓ 检测到加密算法指示器：{algos}",
        })

    if result["browser_api_usage"]:
        apis = list(result["browser_api_usage"].keys())
        result["findings"].append({
            "type": "browser_api",
            "message": f"✓ 检测到浏览器 API 依赖：{apis}",
        })

    if result["token_generation_locations"]:
        result["findings"].append({
            "type": "token_func",
            "message": f"✓ 定位到 {len(result['token_generation_locations'])} 处 token 生成函数实现",
        })

    return result


def extract_browser_api_dependencies(js_content: str) -> Dict[str, Any]:
    """提取 FireyeJS 的所有浏览器 API 依赖，并评估 mock 难度。

    路线 I 第三步：详细列出所有浏览器 API 调用，
    评估在 Node.js 中 mock 这些 API 的难度。

    Args:
        js_content: fireyejs.js 的完整内容

    Returns:
        依赖分析结果 dict：
        {
            "api_categories": dict,  # 各 API 类别的详细命中
            "total_api_calls": int,
            "mock_difficulty": str,  # easy/medium/hard/very_hard
            "mock_strategy": dict,   # 各类别的 mock 策略
            "critical_apis": list,   # 关键 API（必须 mock）
            "optional_apis": list,   # 可选 API（可跳过）
            "findings": list,
        }
    """
    result: Dict[str, Any] = {
        "api_categories": {},
        "total_api_calls": 0,
        "mock_difficulty": "unknown",
        "mock_strategy": {},
        "critical_apis": [],
        "optional_apis": [],
        "findings": [],
    }

    if not js_content:
        return result

    # Mock 策略映射（每个 API 类别的 mock 难度和策略）
    mock_strategies = {
        "canvas": {
            "difficulty": "medium",
            "strategy": "使用 node-canvas 或 jsdom + canvas 包提供 Canvas API",
            "must_mock": True,
            "reason": "getUidToken 核心依赖 Canvas 指纹",
        },
        "webgl": {
            "difficulty": "hard",
            "strategy": "使用 headless-gl 或自定义 WebGL mock 返回固定参数",
            "must_mock": True,
            "reason": "WebGL 指纹是设备指纹的关键组成",
        },
        "audio": {
            "difficulty": "hard",
            "strategy": "mock OfflineAudioContext 返回固定的 AudioBuffer",
            "must_mock": True,
            "reason": "AudioContext 指纹难以伪造但 FireyeJS 必检测",
        },
        "navigator": {
            "difficulty": "easy",
            "strategy": "直接设置 navigator.userAgent/platform/language 等属性",
            "must_mock": True,
            "reason": "navigator 是最基础的设备信息来源",
        },
        "screen": {
            "difficulty": "easy",
            "strategy": "直接设置 screen.width/height 等属性",
            "must_mock": True,
            "reason": "screen 尺寸是基础指纹信息",
        },
        "storage": {
            "difficulty": "easy",
            "strategy": "使用 mock localStorage/sessionStorage（内存对象）",
            "must_mock": True,
            "reason": "FireyeJS 可能用 localStorage 存储 token",
        },
        "timing": {
            "difficulty": "easy",
            "strategy": "mock performance.now() 返回递增时间戳",
            "must_mock": True,
            "reason": "时间戳是行为采集的基础",
        },
        "events": {
            "difficulty": "medium",
            "strategy": "使用 jsdom 提供事件系统，或 mock 事件数据",
            "must_mock": False,
            "reason": "行为事件可伪造（生成模拟鼠标轨迹）",
        },
        "crypto_api": {
            "difficulty": "medium",
            "strategy": "使用 Node.js crypto 模块实现 Web Crypto API",
            "must_mock": True,
            "reason": "crypto.subtle 用于加密/token 生成",
        },
        "worker": {
            "difficulty": "hard",
            "strategy": "使用 Node.js worker_threads 或跳过 Worker 功能",
            "must_mock": False,
            "reason": "Worker 可能用于性能优化，可跳过",
        },
        "webrtc": {
            "difficulty": "very_hard",
            "strategy": "mock RTCPeerConnection 返回固定 ICE 候选",
            "must_mock": False,
            "reason": "WebRTC 用于获取本地 IP，mock 难度极高但可跳过",
        },
        "battery": {
            "difficulty": "easy",
            "strategy": "mock navigator.getBattery() 返回固定值",
            "must_mock": False,
            "reason": "电池 API 已废弃，可跳过",
        },
        "media": {
            "difficulty": "hard",
            "strategy": "mock mediaDevices.enumerateDevices() 返回固定设备列表",
            "must_mock": False,
            "reason": "媒体设备枚举可跳过",
        },
    }

    total_calls = 0
    for category, patterns in FIREYEJS_BROWSER_API_PATTERNS.items():
        category_hits = []
        category_total = 0
        for pattern in patterns:
            found = re.findall(pattern, js_content)
            if found:
                category_hits.append({"pattern": pattern, "count": len(found)})
                category_total += len(found)
        if category_hits:
            result["api_categories"][category] = {
                "total_matches": category_total,
                "patterns": category_hits,
                "mock_strategy": mock_strategies.get(category, {}),
            }
            total_calls += category_total

            strategy = mock_strategies.get(category, {})
            if strategy.get("must_mock"):
                result["critical_apis"].append(category)
            else:
                result["optional_apis"].append(category)

            result["mock_strategy"][category] = strategy

    result["total_api_calls"] = total_calls

    # 评估整体 mock 难度
    if result["critical_apis"]:
        hard_apis = [
            c for c in result["critical_apis"]
            if mock_strategies.get(c, {}).get("difficulty") in ("hard", "very_hard")
        ]
        if len(hard_apis) >= 3:
            result["mock_difficulty"] = "very_hard"
        elif len(hard_apis) >= 1:
            result["mock_difficulty"] = "hard"
        else:
            result["mock_difficulty"] = "medium"
    else:
        result["mock_difficulty"] = "easy"

    # 生成发现
    result["findings"].append({
        "type": "api_stats",
        "message": (
            f"浏览器 API 依赖统计：共 {total_calls} 次调用，"
            f"覆盖 {len(result['api_categories'])} 个类别，"
            f"其中 {len(result['critical_apis'])} 个关键 API 必须 mock"
        ),
    })

    result["findings"].append({
        "type": "difficulty",
        "message": (
            f"Node.js mock 整体难度：{result['mock_difficulty']}。"
            f"关键 API：{result['critical_apis']}，"
            f"可选 API：{result['optional_apis']}"
        ),
    })

    if "audio" in result["critical_apis"]:
        result["findings"].append({
            "type": "audio_warning",
            "message": (
                "⚠ AudioContext 指纹是最难 mock 的部分："
                "FireyeJS 通过 OfflineAudioContext 生成音频指纹，"
                "需要返回精确的浮点数组（getChannelData），"
                "建议从真实浏览器录制一份 AudioBuffer 数据并固化"
            ),
        })

    if "webgl" in result["critical_apis"]:
        result["findings"].append({
            "type": "webgl_warning",
            "message": (
                "⚠ WebGL 指纹需要返回真实的 GPU 参数："
                "getParameter(UNMASKED_VENDOR_WEBGL/UNMASKED_RENDERER_WEBGL) "
                "需要返回与 User-Agent 一致的 GPU 信息"
            ),
        })

    return result


def extract_token_generation_logic(js_content: str) -> Dict[str, Any]:
    """提取 FireyeJS 的 token 生成逻辑（getFYToken/getUidToken 实现）。

    路线 I 第四步：定位 token 生成函数的具体实现，
    提取函数体代码，分析其依赖的内部函数和外部 API。

    Args:
        js_content: fireyejs.js 的完整内容

    Returns:
        token 生成逻辑分析结果 dict：
        {
            "token_functions": list,  # 找到的 token 生成函数
            "internal_dependencies": list,  # 内部函数依赖
            "external_dependencies": list,  # 外部 API 依赖
            "data_flow": dict,  # 数据流分析
            "findings": list,
        }
    """
    result: Dict[str, Any] = {
        "token_functions": [],
        "internal_dependencies": [],
        "external_dependencies": [],
        "data_flow": {},
        "findings": [],
    }

    if not js_content:
        return result

    # 目标函数列表
    target_functions = ["getFYToken", "getUidToken", "getUMIDToken", "getUmidToken"]

    for func_name in target_functions:
        # 多种函数定义模式
        patterns = [
            rf'{re.escape(func_name)}\s*:\s*function\s*\([^)]*\)\s*\{{',
            rf'{re.escape(func_name)}\s*=\s*function\s*\([^)]*\)\s*\{{',
            rf'function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, js_content):
                # 提取函数体（简单的大括号匹配）
                func_start = match.start()
                func_body = _extract_function_body(js_content, match.end() - 1)

                if not func_body:
                    continue

                # 提取函数签名
                sig_match = re.search(rf'{re.escape(func_name)}\s*[:=]?\s*function\s*\(([^)]*)\)', js_content[func_start:match.end()])
                params = sig_match.group(1) if sig_match else ""

                # 分析函数体中的依赖
                internal_calls = _extract_internal_function_calls(func_body)
                external_calls = _extract_external_api_calls(func_body)

                result["token_functions"].append({
                    "name": func_name,
                    "offset": func_start,
                    "signature": f"{func_name}({params})",
                    "body_length": len(func_body),
                    "body_preview": func_body[:2000],  # 前 2000 字符预览
                    "body_full": func_body[:10000],  # 前 10000 字符（用于深度分析）
                    "internal_calls": internal_calls[:20],
                    "external_calls": external_calls[:20],
                })

                for call in internal_calls:
                    if call not in result["internal_dependencies"]:
                        result["internal_dependencies"].append(call)
                for call in external_calls:
                    if call not in result["external_dependencies"]:
                        result["external_dependencies"].append(call)

    # 数据流分析
    result["data_flow"] = {
        "input_sources": [],
        "processing_steps": [],
        "output_formats": [],
    }

    # 识别输入源
    input_patterns = [
        (r'navigator\.(\w+)', "navigator"),
        (r'screen\.(\w+)', "screen"),
        (r'window\.(\w+)', "window"),
        (r'document\.(\w+)', "document"),
        (r'localStorage\.(\w+)', "localStorage"),
    ]
    for pattern, source in input_patterns:
        matches = re.findall(pattern, js_content)
        if matches:
            unique_props = list(set(matches))[:10]
            result["data_flow"]["input_sources"].append({
                "source": source,
                "properties": unique_props,
                "count": len(matches),
            })

    # 识别输出格式
    output_patterns = [
        (r'JSON\.stringify', "JSON.stringify"),
        (r'btoa\s*\(', "base64_encode"),
        (r'fromCharCode', "charCode_to_string"),
        (r'charCodeAt', "string_to_charCode"),
        (r'toString\s*\(\s*16\s*\)', "hex_string"),
        (r'toString\s*\(\s*36\s*\)', "base36_string"),
    ]
    for pattern, name in output_patterns:
        count = len(re.findall(pattern, js_content))
        if count > 0:
            result["data_flow"]["output_formats"].append({
                "format": name,
                "count": count,
            })

    # 生成发现
    if result["token_functions"]:
        func_names_list = [f["name"] for f in result["token_functions"]]
        result["findings"].append({
            "type": "functions_found",
            "message": (
                f"✓ 找到 {len(result['token_functions'])} 个 token 生成函数实现："
                + ", ".join(func_names_list)
            ),
        })
    else:
        result["findings"].append({
            "type": "no_functions",
            "message": "✗ 未找到 token 生成函数实现，可能高度混淆或函数名已变形",
        })

    if result["internal_dependencies"]:
        result["findings"].append({
            "type": "internal_deps",
            "message": f"内部函数依赖（{len(result['internal_dependencies'])} 个）：{result['internal_dependencies'][:10]}",
        })

    if result["external_dependencies"]:
        result["findings"].append({
            "type": "external_deps",
            "message": f"外部 API 依赖（{len(result['external_dependencies'])} 个）：{result['external_dependencies'][:10]}",
        })

    return result


def _extract_function_body(js_content: str, brace_start: int) -> str:
    """从大括号开始位置提取完整的函数体（匹配大括号嵌套）。

    Args:
        js_content: JS 源码
        brace_start: 函数体开始大括号 { 的位置

    Returns:
        函数体内容（不含外层大括号），失败时返回空字符串
    """
    if brace_start >= len(js_content) or js_content[brace_start] != '{':
        return ""

    depth = 0
    in_string = False
    string_char = ""
    in_comment = False
    comment_char = ""
    in_regex = False
    escape_next = False

    body_start = brace_start + 1
    for i in range(brace_start, len(js_content)):
        ch = js_content[i]

        if escape_next:
            escape_next = False
            continue

        if ch == '\\':
            escape_next = True
            continue

        # 字符串处理
        if not in_comment and not in_regex:
            if not in_string and ch in ('"', "'", '`'):
                in_string = True
                string_char = ch
                continue
            if in_string and ch == string_char:
                in_string = False
                string_char = ""
                continue

        if in_string:
            continue

        # 注释处理
        if not in_comment and i + 1 < len(js_content):
            if ch == '/' and js_content[i + 1] == '*':
                in_comment = True
                comment_char = '*/'
                continue
            if ch == '/' and js_content[i + 1] == '/':
                # 单行注释，跳到行尾
                while i < len(js_content) and js_content[i] != '\n':
                    i += 1
                continue

        if in_comment:
            if i + 1 < len(js_content) and ch == '*' and js_content[i + 1] == '/':
                in_comment = False
            continue

        # 大括号匹配
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return js_content[body_start:i]

    return js_content[body_start:]


def _extract_internal_function_calls(func_body: str) -> List[str]:
    """从函数体中提取内部函数调用（非浏览器 API）。

    Args:
        func_body: 函数体代码

    Returns:
        内部函数名列表
    """
    calls = []
    # 匹配 this.xxx(), obj.xxx(), xxx() 形式的调用
    patterns = [
        r'(?:this|self)\.(\w+)\s*\(',
        r'\b(\w{2,})\s*\(',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, func_body):
            name = match.group(1)
            # 排除浏览器 API 和关键字
            browser_apis = {
                'getContext', 'getParameter', 'getExtension', 'fillText',
                'measureText', 'getImageData', 'toDataURL', 'createBuffer',
                'shaderSource', 'createOscillator', 'createAnalyser',
                'createDynamicsCompressor', 'createGain', 'startRendering',
                'getChannelData', 'btoa', 'atob', 'fromCharCode', 'charCodeAt',
                'stringify', 'parse',
            }
            keywords = {'if', 'else', 'for', 'while', 'switch', 'case',
                       'return', 'function', 'var', 'let', 'const', 'new',
                       'typeof', 'instanceof', 'in', 'of', 'do', 'try',
                       'catch', 'finally', 'throw', 'break', 'continue'}
            if name not in browser_apis and name not in keywords and len(name) > 2:
                if name not in calls:
                    calls.append(name)
    return calls


def _extract_external_api_calls(func_body: str) -> List[str]:
    """从函数体中提取外部浏览器 API 调用。

    Args:
        func_body: 函数体代码

    Returns:
        外部 API 调用列表
    """
    calls = []
    patterns = [
        r'\b(navigator\.\w+)',
        r'\b(screen\.\w+)',
        r'\b(window\.\w+)',
        r'\b(document\.\w+)',
        r'\b(localStorage\.\w+)',
        r'\b(sessionStorage\.\w+)',
        r'\b(performance\.\w+)',
        r'\b(AudioContext\w*)',
        r'\b(webkitAudioContext)',
        r'\b(OfflineAudioContext)',
        r'\b(RTCPeerConnection\w*)',
        r'\b(crypto\.\w+)',
        r'\b(Worker\w*)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, func_body):
            call = match.group(1)
            if call not in calls:
                calls.append(call)
    return calls


def evaluate_nodejs_mock_feasibility(
    structure_analysis: Dict[str, Any],
    api_dependencies: Dict[str, Any],
    token_logic: Dict[str, Any],
) -> Dict[str, Any]:
    """评估在 Node.js 中 mock 浏览器 API 执行 FireyeJS 的可行性。

    路线 I 第五步：综合结构分析、API 依赖、token 逻辑，
    评估 Node.js 执行方案的可行性并给出实施建议。

    Args:
        structure_analysis: analyze_fireyejs_js_structure 的返回结果
        api_dependencies: extract_browser_api_dependencies 的返回结果
        token_logic: extract_token_generation_logic 的返回结果

    Returns:
        可行性评估结果 dict：
        {
            "feasibility": str,  # high/medium/low/blocked
            "score": int,  # 0-100 分
            "blocking_issues": list,  # 阻塞性问题
            "risk_issues": list,  # 风险性问题
            "implementation_plan": list,  # 实施步骤
            "required_packages": list,  # 需要的 npm 包
            "estimated_effort": str,  # 预估工作量
            "alternative_approaches": list,  # 备选方案
            "findings": list,
        }
    """
    result: Dict[str, Any] = {
        "feasibility": "unknown",
        "score": 0,
        "blocking_issues": [],
        "risk_issues": [],
        "implementation_plan": [],
        "required_packages": [],
        "estimated_effort": "unknown",
        "alternative_approaches": [],
        "findings": [],
    }

    # 评分项
    score = 0

    # 1. JS 可读性（满分 15）
    if not structure_analysis.get("is_minified", True):
        score += 15
        result["findings"].append({
            "type": "readable",
            "message": "✓ fireyejs.js 未压缩，可直接分析算法逻辑（+15 分）",
        })
    else:
        # 压缩但能定位到函数
        if structure_analysis.get("token_generation_locations"):
            score += 8
            result["findings"].append({
                "type": "minified_but_locatable",
                "message": "△ fireyejs.js 压缩混淆，但能定位到 token 生成函数（+8 分）",
            })
        else:
            result["blocking_issues"].append("JS 高度压缩混淆，无法定位 token 生成函数")

    # 2. token 函数定位（满分 20）
    token_funcs = token_logic.get("token_functions", [])
    if token_funcs:
        target_found = [f for f in token_funcs if f["name"] in ("getFYToken", "getUidToken")]
        if len(target_found) >= 2:
            score += 20
            result["findings"].append({
                "type": "both_targets_found",
                "message": "✓ getFYToken 和 getUidToken 实现均已定位（+20 分）",
            })
        elif len(target_found) == 1:
            score += 12
            result["findings"].append({
                "type": "one_target_found",
                "message": "△ 仅定位到一个 token 函数（+12 分）",
            })
    else:
        result["blocking_issues"].append("未找到任何 token 生成函数实现")

    # 3. API mock 难度（满分 30）
    mock_difficulty = api_dependencies.get("mock_difficulty", "unknown")
    if mock_difficulty == "easy":
        score += 30
    elif mock_difficulty == "medium":
        score += 20
    elif mock_difficulty == "hard":
        score += 10
        result["risk_issues"].append(f"API mock 难度为 hard：{api_dependencies.get('critical_apis', [])}")
    elif mock_difficulty == "very_hard":
        score += 5
        result["risk_issues"].append(f"API mock 难度为 very_hard：包含 {api_dependencies.get('critical_apis', [])}")

    # 4. 加密算法识别（满分 15）
    crypto_indicators = structure_analysis.get("crypto_indicators", {})
    if crypto_indicators:
        # 识别到的加密算法越多，越可能在 Node.js 中复现
        known_algos = {"md5", "sha1", "sha256", "aes", "hmac", "base64", "xor", "rc4"}
        found_algos = set(crypto_indicators.keys()) & known_algos
        if found_algos:
            score += min(15, len(found_algos) * 3)
            result["findings"].append({
                "type": "crypto_identified",
                "message": f"✓ 识别到 {len(found_algos)} 种已知加密算法：{found_algos}（+{min(15, len(found_algos) * 3)} 分）",
            })

    # 5. 数据流清晰度（满分 10）
    data_flow = token_logic.get("data_flow", {})
    if data_flow.get("input_sources") and data_flow.get("output_formats"):
        score += 10
        result["findings"].append({
            "type": "data_flow_clear",
            "message": "✓ 数据流清晰：输入源和输出格式均已识别（+10 分）",
        })
    elif data_flow.get("input_sources"):
        score += 5

    # 6. 内部依赖复杂度（满分 10）
    internal_deps = token_logic.get("internal_dependencies", [])
    if len(internal_deps) <= 5:
        score += 10
    elif len(internal_deps) <= 15:
        score += 7
    elif len(internal_deps) <= 30:
        score += 4
    else:
        score += 2
        result["risk_issues"].append(f"内部函数依赖过多（{len(internal_deps)} 个），需要逐个分析")

    result["score"] = min(100, score)

    # 综合可行性评估
    if result["blocking_issues"]:
        result["feasibility"] = "blocked"
    elif result["score"] >= 70:
        result["feasibility"] = "high"
    elif result["score"] >= 50:
        result["feasibility"] = "medium"
    elif result["score"] >= 30:
        result["feasibility"] = "low"
    else:
        result["feasibility"] = "blocked"

    # 实施计划
    result["implementation_plan"] = [
        "1. 使用 jsdom + canvas + headless-gl 搭建 Node.js 浏览器环境",
        "2. 录制真实浏览器的 Canvas/WebGL/Audio 指纹数据并固化为常量",
        "3. mock navigator/screen/document 对象，使用真实浏览器 User-Agent",
        "4. 加载 fireyejs.js 到 Node.js 环境，初始化 __fy 对象",
        "5. 调用 __fy.getFYToken(__fy_options) 和 __fy.getUidToken()",
        "6. 将获取的 token 注入到 um.json 请求体（b 和 h.umidToken 字段）",
        "7. 调用 um.json 获取有效的 umidToken",
        "8. 调用 initialize.jsonp 获取 NoCaptcha 会话 token",
        "9. 调用 analyze.jsonp 完成 NoCaptcha 验证",
        "10. 从验证结果中提取 x5sec",
    ]

    # 必需的 npm 包
    result["required_packages"] = [
        "jsdom（提供 DOM 环境）",
        "canvas（node-canvas，提供 Canvas API）",
        "gl（headless-gl，提供 WebGL API）",
        "web-audio-api（提供 AudioContext mock）",
        "mock-require（mock 模块依赖）",
    ]

    # 预估工作量
    if result["feasibility"] == "high":
        result["estimated_effort"] = "2-3 天（已有清晰的算法路径）"
    elif result["feasibility"] == "medium":
        result["estimated_effort"] = "1-2 周（需要解决部分 API mock 问题）"
    elif result["feasibility"] == "low":
        result["estimated_effort"] = "2-4 周（API mock 复杂，需反复调试）"
    else:
        result["estimated_effort"] = "未知（存在阻塞性问题）"

    # 备选方案
    result["alternative_approaches"] = [
        "方案 A：使用 Playwright/Puppeteer 在真实浏览器中执行 FireyeJS，"
        "通过 page.evaluate() 获取 token（最可靠但启动慢）",
        "方案 B：使用 Node.js + vm2 模块在沙箱中执行 fireyejs.js，"
        "配合 jsdom 提供 DOM 环境（中等复杂度）",
        "方案 C：深度逆向 fireyejs.js 的算法，纯 Python 复现 "
        "getFYToken/getUidToken（工作量最大但性能最好）",
        "方案 D：使用 crawler-service 已有的 Playwright 浏览器，"
        "导航到 goofish.com 后注入 JS 获取 token（推荐）",
    ]

    return result


def research_fireyejs_standalone(cookie_str: str = "") -> Dict[str, Any]:
    """路线 I 综合研究函数：fireyejs.js 独立文件深度分析。

    本函数执行以下研究步骤：
    1. 下载独立的 fireyejs.js 文件（多版本探测）
    2. 深度分析 JS 结构（函数/加密算法/浏览器 API）
    3. 提取所有浏览器 API 依赖，评估 mock 难度
    4. 定位并提取 getFYToken/getUidToken 函数实现
    5. 评估 Node.js 执行方案的可行性

    Args:
        cookie_str: Cookie 字符串（可选，目前未使用）

    Returns:
        综合研究结果 dict：
        {
            "fireyejs_download": dict,    # 下载结果
            "structure_analysis": dict,   # 结构分析
            "api_dependencies": dict,     # API 依赖分析
            "token_logic": dict,          # token 生成逻辑
            "feasibility_evaluation": dict,  # 可行性评估
            "findings": list,
            "recommendations": list,
            "summary": str,
        }
    """
    result: Dict[str, Any] = {
        "fireyejs_download": None,
        "structure_analysis": None,
        "api_dependencies": None,
        "token_logic": None,
        "feasibility_evaluation": None,
        "findings": [],
        "recommendations": [],
        "summary": "",
    }

    logger.info("[方案K-路线I] 开始 fireyejs.js 独立文件深度分析")

    # 步骤 1：下载 fireyejs.js
    logger.info("[方案K-路线I] 步骤 1：下载 fireyejs.js")
    download_result = download_fireyejs_js()
    result["fireyejs_download"] = download_result

    # 获取第一个成功下载的内容
    js_content = ""
    best_url = download_result.get("best_version", "")
    for d in download_result.get("downloads", []):
        if d.get("content") and d.get("status_code") == 200:
            js_content = d["content"]
            break

    if not js_content:
        result["findings"].append({
            "type": "error",
            "message": "✗ fireyejs.js 下载失败，所有版本均不可用",
        })
        result["summary"] = "fireyejs.js 下载失败，研究受阻"
        return result

    result["findings"].append({
        "type": "download_success",
        "message": f"✓ fireyejs.js 下载成功：{best_url}（长度={len(js_content)}）",
    })

    # 步骤 2：深度结构分析
    logger.info("[方案K-路线I] 步骤 2：深度分析 fireyejs.js 结构")
    structure = analyze_fireyejs_js_structure(js_content)
    result["structure_analysis"] = structure
    result["findings"].extend(structure.get("findings", []))

    # 步骤 3：提取浏览器 API 依赖
    logger.info("[方案K-路线I] 步骤 3：提取浏览器 API 依赖")
    api_deps = extract_browser_api_dependencies(js_content)
    result["api_dependencies"] = api_deps
    result["findings"].extend(api_deps.get("findings", []))

    # 步骤 4：提取 token 生成逻辑
    logger.info("[方案K-路线I] 步骤 4：提取 token 生成逻辑")
    token_logic = extract_token_generation_logic(js_content)
    result["token_logic"] = token_logic
    result["findings"].extend(token_logic.get("findings", []))

    # 步骤 5：评估 Node.js 执行可行性
    logger.info("[方案K-路线I] 步骤 5：评估 Node.js mock 可行性")
    feasibility = evaluate_nodejs_mock_feasibility(structure, api_deps, token_logic)
    result["feasibility_evaluation"] = feasibility
    result["findings"].extend(feasibility.get("findings", []))

    # 综合建议
    result["recommendations"] = [
        f"可行性评分：{feasibility['score']}/100（{feasibility['feasibility']}）",
        f"预估工作量：{feasibility['estimated_effort']}",
        "",
        "推荐实施路径：",
    ]
    result["recommendations"].extend(feasibility.get("implementation_plan", []))
    result["recommendations"].append("")
    result["recommendations"].append("备选方案：")
    for i, alt in enumerate(feasibility.get("alternative_approaches", []), 1):
        result["recommendations"].append(f"  {i}. {alt}")

    # 阻塞性问题
    if feasibility.get("blocking_issues"):
        result["recommendations"].append("")
        result["recommendations"].append("⚠ 阻塞性问题：")
        for issue in feasibility["blocking_issues"]:
            result["recommendations"].append(f"  - {issue}")

    # 综合总结
    result["summary"] = (
        f"fireyejs.js 独立文件深度分析完成："
        f"长度={len(js_content)}, "
        f"函数数={structure.get('function_count', 0)}, "
        f"加密算法={list(structure.get('crypto_indicators', {}).keys())}, "
        f"浏览器API={list(api_deps.get('api_categories', {}).keys())}, "
        f"token函数={len(token_logic.get('token_functions', []))}, "
        f"可行性={feasibility['feasibility']}({feasibility['score']}分)"
    )

    logger.info("[方案K-路线I] 研究完成：%s", result["summary"])

    return result


# ============================================================
# 17. 路线 I 增强：VM 混淆检测与动态分析建议
# ============================================================
# 背景：
#   路线 I 首次测试发现 fireyejs.js 中所有标识符和浏览器 API 均未命中，
#   经检查发现 fireyejs.js 使用了虚拟机（VM）混淆技术：
#   - 字符串被编码为字节数组（Hex/Unicode 编码）
#   - 通过 DataView 的 getInt8/getUint8 等方法解码
#   - 所有操作通过 VM 指令解释器执行（switch-case 调度）
#   - 标识符不以明文形式出现在 JS 中
#
# 本节目标：
#   1. 检测 JS 是否使用了 VM 混淆
#   2. 识别 VM 解释器的位置和结构
#   3. 评估动态分析的可行性（在浏览器/Node.js 中执行 JS）
#   4. 给出实施动态分析的具体方案

# VM 混淆特征模式
VM_OBFUSCATION_PATTERNS = {
    # VM 解释器核心特征：大 switch-case 调度
    "vm_dispatcher": [
        r"switch\s*\(\s*\w{1,3}\s*&\s*\w+\s*\)\s*\{",
        r"case\s+\d+\s*:",
        r"d\[\d+\]\s*=\s*\w+\s*>>\s*\d+\s*&\s*\w+",  # 指令解码
    ],
    # DataView 操作（用于字符串解码）
    "dataview_ops": [
        r"getInt8",
        r"getInt16",
        r"getInt32",
        r"getUint8",
        r"getUint16",
        r"getUint32",
        r"getFloat32",
        r"getFloat64",
        r"DataView",
    ],
    # 数组索引访问（VM 寄存器/栈操作）
    "array_register": [
        r"\b\w{1,3}\[\d+\]\s*=",   # 寄存器写入
        r"=\s*\w{1,3}\[\d+\]",      # 寄存器读取
        r"\b\w{1,3}\[\d+\]\s*[+\-*/^&|]\s*",  # 寄存器运算
    ],
    # Uint8Array/ArrayBuffer（字节操作）
    "byte_operations": [
        r"Uint8Array",
        r"ArrayBuffer",
        r"Uint16Array",
        r"Int8Array",
        r"Int16Array",
        r"Int32Array",
    ],
    # 字节级运算（解码操作）
    "byte_arithmetic": [
        r"\^\s*0x[0-9a-fA-F]+",       # XOR 操作
        r"&\s*0x[0-9a-fA-F]+",        # AND 操作
        r">>>\s*\d+",                  # 无符号右移
        r"<<\s*\d+",                   # 左移
        r"charCodeAt\s*\(\s*\d+\s*\)",  # 字符码读取
    ],
    # 函数构造器（动态函数创建）
    "function_constructor": [
        r"\bFunction\s*\(",
        r"new\s+Function\s*\(",
        r"eval\s*\(",
        r"Function\[",
    ],
    # 原型链间接调用
    "prototype_indirect": [
        r"prototype\s*\[",
        r"\[\"call\"\]",
        r"\[\"bind\"\]",
        r"\[\"apply\"\]",
        r"\[\"push\"\]",
    ],
}


def detect_vm_obfuscation(js_content: str) -> Dict[str, Any]:
    """检测 JS 是否使用了虚拟机（VM）混淆技术。

    VM 混淆的核心特征：
    1. 大量使用 switch-case 作为指令调度器
    2. 使用 DataView/Uint8Array 进行字节级操作（字符串解码）
    3. 数组索引访问代替变量名（寄存器/栈模拟）
    4. 原型链间接调用（隐藏真实方法名）

    Args:
        js_content: JS 源码

    Returns:
        VM 混淆检测结果 dict：
        {
            "is_vm_obfuscated": bool,
            "confidence": str,  # high/medium/low
            "score": int,  # 0-100
            "vm_indicators": dict,  # 各特征命中情况
            "vm_dispatcher_location": list,  # VM 调度器位置
            "dataview_usage": dict,  # DataView 使用情况
            "register_count": int,  # 寄存器访问次数
            "byte_op_count": int,  # 字节操作次数
            "findings": list,
            "recommendation": str,  # 分析建议
        }
    """
    result: Dict[str, Any] = {
        "is_vm_obfuscated": False,
        "confidence": "low",
        "score": 0,
        "vm_indicators": {},
        "vm_dispatcher_location": [],
        "dataview_usage": {},
        "register_count": 0,
        "byte_op_count": 0,
        "findings": [],
        "recommendation": "",
    }

    if not js_content:
        return result

    score = 0
    total_register_access = 0
    total_byte_ops = 0

    # 检测各类 VM 混淆特征
    for category, patterns in VM_OBFUSCATION_PATTERNS.items():
        category_matches = []
        category_total = 0
        for pattern in patterns:
            found = re.findall(pattern, js_content)
            if found:
                category_matches.append({
                    "pattern": pattern,
                    "count": len(found),
                })
                category_total += len(found)

                # 收集前 3 个位置用于 VM 调度器定位
                if category == "vm_dispatcher" and len(result["vm_dispatcher_location"]) < 5:
                    for match in re.finditer(pattern, js_content):
                        start = max(0, match.start() - 50)
                        end = min(len(js_content), match.end() + 200)
                        result["vm_dispatcher_location"].append({
                            "offset": match.start(),
                            "pattern": pattern,
                            "context": js_content[start:end],
                        })
                        if len(result["vm_dispatcher_location"]) >= 5:
                            break

        if category_matches:
            result["vm_indicators"][category] = {
                "total_matches": category_total,
                "patterns": category_matches,
            }

            # 评分权重
            weight = {
                "vm_dispatcher": 25,        # VM 调度器是最强特征
                "dataview_ops": 15,         # DataView 操作是字符串解码的关键
                "array_register": 10,       # 数组索引访问是寄存器模拟
                "byte_operations": 10,      # 字节操作是解码的基础
                "byte_arithmetic": 10,      # 字节运算是解码算法
                "function_constructor": 5,  # 动态函数创建
                "prototype_indirect": 5,    # 原型链间接调用
            }.get(category, 5)

            # 该类别命中即加分（有上限）
            score += min(weight, category_total)

            # 累计寄存器访问和字节操作
            if category == "array_register":
                total_register_access += category_total
            if category in ("byte_operations", "byte_arithmetic"):
                total_byte_ops += category_total

    result["register_count"] = total_register_access
    result["byte_op_count"] = total_byte_ops
    result["score"] = min(100, score)

    # 置信度评估
    has_dispatcher = "vm_dispatcher" in result["vm_indicators"]
    has_dataview = "dataview_ops" in result["vm_indicators"]
    has_register = "array_register" in result["vm_indicators"]

    if has_dispatcher and has_dataview and has_register:
        result["is_vm_obfuscated"] = True
        result["confidence"] = "high"
        result["findings"].append({
            "type": "vm_confirmed",
            "message": (
                "✓ 确认使用 VM 混淆技术：检测到 VM 调度器（switch-case）、"
                "DataView 字节操作、数组寄存器访问三大核心特征。"
                "所有字符串和标识符都被编码为字节数组，运行时通过 VM 解码。"
            ),
        })
    elif has_dispatcher and has_register:
        result["is_vm_obfuscated"] = True
        result["confidence"] = "medium"
        result["findings"].append({
            "type": "vm_likely",
            "message": "△ 很可能使用 VM 混淆：检测到 VM 调度器和数组寄存器访问",
        })
    elif has_dataview and has_register:
        result["is_vm_obfuscated"] = True
        result["confidence"] = "medium"
        result["findings"].append({
            "type": "vm_likely",
            "message": "△ 很可能使用 VM 混淆：检测到 DataView 操作和数组寄存器访问",
        })
    else:
        result["findings"].append({
            "type": "no_vm",
            "message": "✗ 未检测到明显的 VM 混淆特征",
        })

    # 额外发现
    if total_register_access > 1000:
        result["findings"].append({
            "type": "high_register_usage",
            "message": (
                f"⚠ 数组寄存器访问次数极高（{total_register_access} 次），"
                "这是 VM 混淆的强特征：所有变量操作都通过数组索引完成"
            ),
        })

    if has_dataview:
        dv_methods = []
        for pattern_info in result["vm_indicators"].get("dataview_ops", {}).get("patterns", []):
            dv_methods.append(pattern_info["pattern"])
        result["findings"].append({
            "type": "dataview_decoding",
            "message": (
                f"✓ 检测到 DataView 操作：{dv_methods}。"
                "DataView 用于从字节数组解码字符串，"
                "这是 VM 混淆中字符串还原的关键机制"
            ),
        })

    # 分析建议
    if result["is_vm_obfuscated"]:
        result["recommendation"] = (
            "【关键结论】fireyejs.js 使用了 VM 混淆技术，静态分析无法提取 token 生成逻辑。\n"
            "\n"
            "推荐方案（按优先级排序）：\n"
            "1. 【强烈推荐】路线 J：使用 crawler-service 的 Playwright 浏览器执行 FireyeJS\n"
            "   - 在真实浏览器环境中加载 fireyejs.js\n"
            "   - 通过 page.evaluate() 调用 __fy.getFYToken() 和 __fy.getUidToken()\n"
            "   - 获取真实的 token 后注入到 um.json 请求体\n"
            "   - 优点：100% 可靠，无需逆向 VM\n"
            "   - 缺点：启动浏览器有性能开销（约 2-3 秒）\n"
            "\n"
            "2. 【备选】Node.js + jsdom 执行 fireyejs.js\n"
            "   - 使用 jsdom 提供 DOM 环境\n"
            "   - mock Canvas/WebGL/AudioContext API\n"
            "   - 在 Node.js 中加载并执行 fireyejs.js\n"
            "   - 优点：比浏览器轻量\n"
            "   - 缺点：需要 mock 大量浏览器 API，可能触发 VM 内的反调试检测\n"
            "\n"
            "3. 【不推荐】深度逆向 VM 指令集\n"
            "   - 需要完整分析 VM 调度器的所有 case 分支\n"
            "   - 工作量极大（预计 1-3 个月）\n"
            "   - 且 FireyeJS 版本更新后需要重新逆向\n"
        )
    else:
        result["recommendation"] = (
            "未检测到 VM 混淆，可继续进行静态分析。"
            "建议使用 extract_token_generation_logic() 提取 token 生成函数。"
        )

    return result


def analyze_fireyejs_with_vm_detection(js_content: str) -> Dict[str, Any]:
    """路线 I 增强版：结合 VM 混淆检测分析 fireyejs.js。

    本函数在原 analyze_fireyejs_js_structure 基础上增加 VM 混淆检测，
    并根据检测结果调整分析策略和可行性评估。

    Args:
        js_content: fireyejs.js 的完整内容

    Returns:
        增强分析结果 dict：
        {
            "structure_analysis": dict,      # 原结构分析
            "vm_detection": dict,            # VM 混淆检测
            "browser_api_partial_match": dict,  # 浏览器 API 部分匹配
            "identifier_partial_match": dict,   # 标识符部分匹配
            "findings": list,
            "recommendation": str,
            "summary": str,
        }
    """
    result: Dict[str, Any] = {
        "structure_analysis": None,
        "vm_detection": None,
        "browser_api_partial_match": {},
        "identifier_partial_match": {},
        "findings": [],
        "recommendation": "",
        "summary": "",
    }

    if not js_content:
        return result

    # 1. 原结构分析
    structure = analyze_fireyejs_js_structure(js_content)
    result["structure_analysis"] = structure
    result["findings"].extend(structure.get("findings", []))

    # 2. VM 混淆检测
    vm_detection = detect_vm_obfuscation(js_content)
    result["vm_detection"] = vm_detection
    result["findings"].extend(vm_detection.get("findings", []))
    result["recommendation"] = vm_detection.get("recommendation", "")

    # 3. 浏览器 API 部分匹配（不要求精确匹配，检测关键词出现）
    browser_keywords = [
        "navigator", "screen", "canvas", "webgl", "AudioContext",
        "localStorage", "document", "window", "performance", "crypto",
        "Worker", "RTCPeerConnection", "getElementById", "createElement",
        "addEventListener", "setTimeout", "setInterval", "XMLHttpRequest",
        "fetch", "WebSocket", "IndexedDB", "requestAnimationFrame",
    ]
    for kw in browser_keywords:
        # 精确匹配
        exact_count = js_content.count(kw)
        # 忽略大小写匹配
        lower_count = js_content.lower().count(kw.lower()) if exact_count == 0 else 0

        if exact_count > 0:
            result["browser_api_partial_match"][kw] = {
                "count": exact_count,
                "match_type": "exact",
            }
        elif lower_count > 0:
            result["browser_api_partial_match"][kw] = {
                "count": lower_count,
                "match_type": "case_insensitive",
            }

    # 4. 标识符部分匹配（检测关键字符串的片段）
    identifier_fragments = [
        "FY", "Token", "umid", "fire", "getF", "getU", "Uid", "fy",
        "__fy", "NVC", "FireyeJS", "appkey", "scene", "behavior",
        "fingerprint", "device", "collect", "report",
    ]
    for frag in identifier_fragments:
        count = js_content.count(frag)
        if count > 0:
            # 找到第一个出现位置
            first_loc = -1
            for match in re.finditer(re.escape(frag), js_content):
                first_loc = match.start()
                break
            result["identifier_partial_match"][frag] = {
                "count": count,
                "first_offset": first_loc,
            }

    # 5. 综合发现
    vm_confidence = vm_detection.get("confidence", "low")
    if vm_detection.get("is_vm_obfuscated") and vm_confidence == "high":
        result["findings"].append({
            "type": "vm_confirmed_analysis",
            "message": (
                "【关键发现】fireyejs.js 确认使用 VM 混淆技术。"
                "所有字符串标识符（getFYToken/getUidToken/navigator/canvas 等）"
                "都被编码为字节数组，通过 DataView 解码后由 VM 指令解释器执行。"
                "这解释了为什么静态分析无法命中任何标识符。"
            ),
        })

    browser_api_count = len(result["browser_api_partial_match"])
    if browser_api_count > 0:
        found_apis = list(result["browser_api_partial_match"].keys())
        result["findings"].append({
            "type": "browser_api_partial",
            "message": (
                f"浏览器 API 部分匹配：检测到 {browser_api_count} 个 API 关键词：{found_apis}。"
                "注意：VM 混淆下这些可能是解码后的残留或 VM 解释器自身的依赖，"
                "不一定代表 FireyeJS 直接调用了这些 API"
            ),
        })

    identifier_count = len(result["identifier_partial_match"])
    if identifier_count > 0:
        found_frags = list(result["identifier_partial_match"].keys())
        result["findings"].append({
            "type": "identifier_partial",
            "message": (
                f"标识符片段部分匹配：检测到 {identifier_count} 个片段：{found_frags}。"
                "这些片段可能出现在 VM 解释器代码中，但不代表完整的标识符明文"
            ),
        })

    # 6. 综合总结
    result["summary"] = (
        f"fireyejs.js 增强分析完成："
        f"VM混淆={vm_detection.get('is_vm_obfuscated', False)}"
        f"({vm_confidence}, {vm_detection.get('score', 0)}分), "
        f"寄存器访问={vm_detection.get('register_count', 0)}次, "
        f"字节操作={vm_detection.get('byte_op_count', 0)}次, "
        f"浏览器API部分匹配={browser_api_count}个, "
        f"标识符片段匹配={identifier_count}个"
    )

    return result


def recommend_dynamic_analysis_route(vm_detection: Dict[str, Any]) -> Dict[str, Any]:
    """基于 VM 混淆检测结果，推荐动态分析路线（路线 J）。

    路线 J：使用 crawler-service 的 Playwright 浏览器执行 FireyeJS，
    获取真实的 FYToken 和 umidToken。

    Args:
        vm_detection: detect_vm_obfuscation 的返回结果

    Returns:
        路线 J 实施建议 dict：
        {
            "route_name": str,
            "feasibility": str,
            "implementation_steps": list,
            "code_template": str,  # 代码模板
            "estimated_effort": str,
            "risk_mitigation": list,
        }
    """
    is_vm = vm_detection.get("is_vm_obfuscated", False)
    confidence = vm_detection.get("confidence", "low")

    result: Dict[str, Any] = {
        "route_name": "路线 J：crawler-service 浏览器执行 FireyeJS",
        "feasibility": "high" if is_vm and confidence == "high" else "medium",
        "implementation_steps": [],
        "code_template": "",
        "estimated_effort": "",
        "risk_mitigation": [],
    }

    result["implementation_steps"] = [
        "1. 在 crawler-service 中新增 /api/fireyejs/get-token 端点",
        "2. 该端点接收 cookie 参数，启动 Playwright 浏览器",
        "3. 导航到 https://www.goofish.com/（或 about:blank）",
        "4. 注入 cookie 到浏览器上下文",
        "5. 通过 page.addScriptTag() 加载 fireyejs.js",
        "6. 等待 fireyejs.js 加载完成（window.__fy 可用）",
        "7. 调用 page.evaluate(() => __fy.getFYToken(__fy_options)) 获取 FYToken",
        "8. 调用 page.evaluate(() => __fy.getUidToken()) 获取 umidToken",
        "9. 返回 {fyToken, umidToken} 给调用方",
        "10. automation-service 将 token 注入 um.json 请求体",
        "11. 调用 um.json 获取有效的 umidToken",
        "12. 调用 initialize.jsonp 获取 NoCaptcha 会话 token",
        "13. 调用 analyze.jsonp 完成 NoCaptcha 验证",
        "14. 从验证结果中提取 x5sec",
    ]

    # 代码模板（TypeScript，用于 crawler-service）
    result["code_template"] = '''// crawler-service/src/crawler/fireyejsToken.ts
import { Page, Browser } from 'playwright';

export interface FireyejsTokenResult {
  fyToken: string;
  umidToken: string;
  durationMs: number;
}

/**
 * 通过 Playwright 浏览器执行 FireyeJS，获取 FYToken 和 umidToken。
 *
 * 实现思路：
 * 1. 启动浏览器，导航到 goofish.com
 * 2. 注入用户 cookie
 * 3. 等待页面加载完成（fireyejs.js 会被自动加载）
 * 4. 通过 page.evaluate 调用 __fy.getFYToken() 和 __fy.getUidToken()
 *
 * 注意事项：
 * - fireyejs.js 使用 VM 混淆，必须在真实浏览器环境中执行
 * - 需要等待 window.__fy 对象可用（可能需要 1-2 秒）
 * - FYToken 依赖行为数据，可能需要模拟鼠标移动
 */
export async function getFireyejsToken(
  browser: Browser,
  cookie: string,
): Promise<FireyejsTokenResult> {
  const t0 = Date.now();
  const page = await browser.newPage();

  try {
    // 1. 设置 cookie
    const cookies = parseCookieString(cookie);
    await page.context().addCookies(cookies);

    // 2. 导航到 goofish.com（触发 fireyejs.js 加载）
    await page.goto('https://www.goofish.com/', {
      waitUntil: 'networkidle',
      timeout: 15000,
    });

    // 3. 等待 window.__fy 可用
    await page.waitForFunction(() => {
      return (window as any).__fy && (window as any).__fy.getFYToken;
    }, { timeout: 10000 });

    // 4. 模拟鼠标移动（生成行为数据）
    await page.mouse.move(100, 100);
    await page.mouse.move(200, 200);
    await page.waitForTimeout(500);

    // 5. 获取 FYToken
    const fyToken = await page.evaluate(() => {
      const fy = (window as any).__fy;
      const options = (window as any).__fy_options || {};
      return fy.getFYToken(options);
    });

    // 6. 获取 umidToken
    const umidToken = await page.evaluate(() => {
      const fy = (window as any).__fy;
      return fy.getUidToken();
    });

    return {
      fyToken,
      umidToken,
      durationMs: Date.now() - t0,
    };
  } finally {
    await page.close();
  }
}

function parseCookieString(cookieStr: string) {
  return cookieStr.split(';').map(pair => {
    const [name, ...valueParts] = pair.trim().split('=');
    return {
      name,
      value: valueParts.join('='),
      domain: '.goofish.com',
      path: '/',
    };
  }).filter(c => c.name && c.value);
}
'''

    if is_vm and confidence == "high":
        result["estimated_effort"] = "3-5 天（浏览器执行方案成熟，主要是集成和调试）"
    elif is_vm:
        result["estimated_effort"] = "5-7 天（需要验证 VM 混淆的影响）"
    else:
        result["estimated_effort"] = "2-3 天（无 VM 混淆，可直接静态分析）"

    result["risk_mitigation"] = [
        "风险1：fireyejs.js 可能检测 headless 浏览器 → 使用 stealth 模式（crawler-service 已支持）",
        "风险2：FYToken 依赖行为数据 → 模拟鼠标移动和键盘输入",
        "风险3：浏览器启动慢（2-3 秒） → 缓存 token，5 分钟内复用",
        "风险4：并发限制 → 使用浏览器池（crawler-service 已有）",
        "风险5：fireyejs.js 版本更新 → 监控版本变化，自动适配新 URL",
        "风险6：页面加载失败 → 重试机制 + 降级到 silent-extract",
    ]

    return result


# ============================================================
# 路线 J 实现：通过 crawler-service 浏览器执行 FireyeJS 获取真实 token
# ============================================================

# FireyeJS token 内存缓存（cookie_str 哈希 → token + 过期时间）
# 5 分钟内同一 cookie 复用 token，避免重复启动浏览器
_FIREYEJS_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}
_FIREYEJS_TOKEN_CACHE_TTL_SEC = 300  # 5 分钟


def _get_cache_key(cookie_str: str) -> str:
    """生成 cookie 的缓存键（md5 哈希，避免明文存储 cookie）"""
    import hashlib
    return hashlib.md5(cookie_str.encode("utf-8")).hexdigest()


def get_cached_fireyejs_token(cookie_str: str) -> Optional[Dict[str, Any]]:
    """从内存缓存读取 FireyeJS token。

    缓存策略：
    - 同一 cookie 5 分钟内复用 token
    - 缓存过期后自动失效
    - 匿名访问（空 cookie）也缓存，但 TTL 更短（60 秒）

    Args:
        cookie_str: Cookie 字符串

    Returns:
        缓存的 token dict（含 fyToken/umidToken），无缓存或已过期返回 None
    """
    cache_key = _get_cache_key(cookie_str or "anonymous")
    now = time.time()

    cached = _FIREYEJS_TOKEN_CACHE.get(cache_key)
    if not cached:
        return None

    # 匿名访问缓存 60 秒，登录态缓存 5 分钟
    ttl = 60 if not cookie_str else _FIREYEJS_TOKEN_CACHE_TTL_SEC
    if now - cached.get("cached_at", 0) > ttl:
        # 缓存已过期
        _FIREYEJS_TOKEN_CACHE.pop(cache_key, None)
        return None

    return cached


def set_cached_fireyejs_token(cookie_str: str, token_data: Dict[str, Any]) -> None:
    """缓存 FireyeJS token 到内存。

    Args:
        cookie_str: Cookie 字符串
        token_data: token 数据（含 fyToken/umidToken）
    """
    cache_key = _get_cache_key(cookie_str or "anonymous")
    _FIREYEJS_TOKEN_CACHE[cache_key] = {
        **token_data,
        "cached_at": time.time(),
    }

    # 清理过期缓存（避免内存泄漏）
    now = time.time()
    expired_keys = [
        k for k, v in _FIREYEJS_TOKEN_CACHE.items()
        if now - v.get("cached_at", 0) > _FIREYEJS_TOKEN_CACHE_TTL_SEC * 2
    ]
    for k in expired_keys:
        _FIREYEJS_TOKEN_CACHE.pop(k, None)


def fetch_fireyejs_token_via_browser(
    cookie_str: str = "",
    target_url: str = "",
    use_cache: bool = True,
    debug: bool = False,
) -> Dict[str, Any]:
    """通过 crawler-service 浏览器执行 FireyeJS，获取真实的 FYToken 和 umidToken。

    路线 J 核心实现：
    1. 检查内存缓存，命中则直接返回（5 分钟内复用）
    2. 调用 crawler-service 的 /api/fireyejs/get-token 端点
    3. crawler-service 启动 Playwright 浏览器访问闲鱼首页
    4. fireyejs.js 在真实浏览器环境中执行（绕过 VM 混淆）
    5. 返回 {fyToken, umidToken} 给调用方
    6. 缓存 token，5 分钟内复用

    Args:
        cookie_str: Cookie 字符串（可选，匿名访问时留空）
        target_url: 目标页面 URL（默认闲鱼首页）
        use_cache: 是否使用缓存（默认 True）
        debug: 是否启用调试日志

    Returns:
        结果 dict：
        {
            "ok": bool,
            "fyToken": str,          # FireyeJS getFYToken 返回值
            "umidToken": str,        # FireyeJS getUidToken 返回值
            "durationMs": int,       # 总耗时
            "cached": bool,          # 是否命中缓存
            "error": str,            # 错误信息（失败时）
            "fireyejsVersion": str,  # FireyeJS 版本（调试用）
        }
    """
    # 1. 检查缓存
    if use_cache:
        cached = get_cached_fireyejs_token(cookie_str)
        if cached:
            logger.info(
                "[方案K-路线J] FireyeJS token 缓存命中 fyToken长度=%d",
                len(cached.get("fyToken", "")),
            )
            return {
                "ok": True,
                "fyToken": cached.get("fyToken", ""),
                "umidToken": cached.get("umidToken", ""),
                "durationMs": 0,
                "cached": True,
            }

    # 2. 调用 crawler-service
    try:
        import requests as _requests
    except ImportError:
        return {
            "ok": False,
            "fyToken": "",
            "umidToken": "",
            "durationMs": 0,
            "error": "requests 模块不可用",
        }

    crawler_url = os.environ.get(
        "CRAWLER_SERVICE_URL", "http://crawler-service:3001"
    )
    endpoint = f"{crawler_url.rstrip('/')}/api/fireyejs/get-token"

    payload: Dict[str, Any] = {
        "simulateBehavior": True,
        "debug": debug,
    }
    if cookie_str:
        payload["cookie"] = cookie_str
    if target_url:
        payload["targetUrl"] = target_url

    # 代理配置（可选，复用账号绑定代理）
    # 注意：FireyeJS token 获取不强依赖代理，但使用代理可能降低风控触发率
    # 调用方可在 payload 中传入 proxy 字段

    # 鉴权头：crawler-service 要求 X-Internal-Token
    # FireyeJS 端点豁免 tenant ID 检查，但仍需 internal token
    internal_token = os.environ.get("INTERNAL_API_TOKEN", "")
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
    }

    try:
        resp = _requests.post(endpoint, json=payload, headers=headers, timeout=90)
    except Exception as e:
        logger.warning("[方案K-路线J] 调用 crawler-service 失败: %s", e)
        return {
            "ok": False,
            "fyToken": "",
            "umidToken": "",
            "durationMs": 0,
            "error": f"crawler-service 调用失败: {e}",
        }

    if resp.status_code != 200:
        logger.warning(
            "[方案K-路线J] crawler-service 返回 %d: %s",
            resp.status_code,
            resp.text[:200],
        )
        try:
            err_data = resp.json()
            err_msg = err_data.get("error", f"HTTP {resp.status_code}")
        except Exception:
            err_msg = f"HTTP {resp.status_code}"
        return {
            "ok": False,
            "fyToken": "",
            "umidToken": "",
            "durationMs": 0,
            "error": err_msg,
        }

    try:
        data = resp.json()
    except Exception as e:
        return {
            "ok": False,
            "fyToken": "",
            "umidToken": "",
            "durationMs": 0,
            "error": f"响应解析失败: {e}",
        }

    if not data.get("ok"):
        return {
            "ok": False,
            "fyToken": "",
            "umidToken": "",
            "durationMs": data.get("durationMs", 0),
            "error": data.get("error", "未知错误"),
            "fireyejsVersion": data.get("fireyejsVersion", ""),
        }

    fy_token = data.get("fyToken", "")
    umid_token = data.get("umidToken", "")
    duration_ms = data.get("durationMs", 0)
    fireyejs_version = data.get("fireyejsVersion", "")

    logger.info(
        "[方案K-路线J] ✓ FireyeJS token 获取成功 fyToken长度=%d umidToken长度=%d 耗时=%dms 版本=%s",
        len(fy_token),
        len(umid_token),
        duration_ms,
        fireyejs_version or "unknown",
    )

    # 3. 缓存 token
    if use_cache and fy_token:
        set_cached_fireyejs_token(cookie_str, {
            "fyToken": fy_token,
            "umidToken": umid_token,
        })

    return {
        "ok": True,
        "fyToken": fy_token,
        "umidToken": umid_token,
        "durationMs": duration_ms,
        "cached": False,
        "fireyejsVersion": fireyejs_version,
    }


def research_route_j_fireyejs_browser(cookie_str: str = "") -> Dict[str, Any]:
    """路线 J 研究：通过 crawler-service 浏览器执行 FireyeJS 获取真实 token。

    本函数是路线 J 的研究入口，执行完整流程：
    1. 调用 fetch_fireyejs_token_via_browser 获取 FireyeJS token
    2. 用获取到的 token 调用 um.json 端点
    3. 分析 um.json 响应，判断 token 是否被服务器接受
    4. 如 um.json 返回有效 umidToken，继续调用 initialize.jsonp

    Args:
        cookie_str: Cookie 字符串（可选）

    Returns:
        研究 result dict，包含：
        - fireyejs_token_result: FireyeJS token 获取结果
        - um_json_result: um.json 端点响应
        - initialize_result: initialize.jsonp 端点响应（如有）
        - findings: 发现列表
        - recommendations: 建议列表
    """
    result: Dict[str, Any] = {
        "route_name": "路线 J：crawler-service 浏览器执行 FireyeJS",
        "fireyejs_token_result": {},
        "um_json_result": {},
        "initialize_result": {},
        "findings": [],
        "recommendations": [],
    }

    # 步骤 1：获取 FireyeJS token
    logger.info("[方案K-路线J] 步骤 1：通过 crawler-service 获取 FireyeJS token")
    token_result = fetch_fireyejs_token_via_browser(
        cookie_str=cookie_str,
        use_cache=False,  # 研究模式不使用缓存
        debug=True,
    )
    result["fireyejs_token_result"] = token_result

    if not token_result.get("ok"):
        result["findings"].append({
            "type": "fireyejs_token_failed",
            "message": f"FireyeJS token 获取失败: {token_result.get('error')}",
        })
        result["recommendations"].append(
            "检查 crawler-service 的 /api/fireyejs/get-token 端点是否正常工作"
        )
        return result

    fy_token = token_result.get("fyToken", "")
    umid_token = token_result.get("umidToken", "")

    result["findings"].append({
        "type": "fireyejs_token_success",
        "message": (
            f"FireyeJS token 获取成功: fyToken长度={len(fy_token)} "
            f"umidToken长度={len(umid_token)} 耗时={token_result.get('durationMs')}ms"
        ),
    })

    if fy_token:
        result["findings"].append({
            "type": "fy_token_sample",
            "message": f"FYToken 前 50 字符: {fy_token[:50]}...",
        })

    if umid_token:
        result["findings"].append({
            "type": "umid_token_sample",
            "message": f"umidToken 前 50 字符: {umid_token[:50]}...",
        })

    # 步骤 2：用 FireyeJS token 调用 um.json 端点
    logger.info("[方案K-路线J] 步骤 2：用 FireyeJS token 调用 um.json 端点")

    # 选择 um.json 端点（中国 region）
    um_json_url = "https://ynuf.aliapp.org/service/um.json"

    um_result = probe_um_json_endpoint(
        endpoint_url=um_json_url,
        appkey="XFFXFXFF",
        cookie_str=cookie_str,
        use_post=True,
        use_nvc_data=True,
        fy_token=fy_token,
        umid_token=umid_token,
    )
    result["um_json_result"] = um_result

    if um_result.get("status_code") == 200:
        result["findings"].append({
            "type": "um_json_success",
            "message": (
                f"um.json 返回 200，响应长度={um_result.get('response_length')} "
                f"umt_cookie={'有' if um_result.get('umt_cookie') else '无'}"
            ),
        })

        # 如果 um.json 返回 umt cookie，继续调用 initialize.jsonp
        if um_result.get("umt_cookie") or um_result.get("umid_id"):
            logger.info("[方案K-路线J] 步骤 3：um.json 返回有效响应，继续调用 initialize.jsonp")

            # 从 um.json 响应中提取 umidToken
            obtained_umid_token = (
                um_result.get("umid_id")
                or um_result.get("umt_cookie")
                or umid_token
            )
            result["obtained_umid_token"] = obtained_umid_token

            # 选择 initialize.jsonp 端点（中国 region）
            # 注意：probe_initialize_jsonp_endpoint 当前不接受 umid_token 参数，
            # umid_token 通过 cookie_str 传递（um.json 返回的 Set-Cookie 会被合并到 cookie_str）
            # 这里传入增强后的 cookie（包含 um.json 返回的 umt cookie）
            enhanced_cookie = cookie_str
            if um_result.get("umt_cookie"):
                enhanced_cookie = (
                    cookie_str + "; umt=" + um_result["umt_cookie"]
                    if cookie_str
                    else "umt=" + um_result["umt_cookie"]
                )

            init_url = "https://ynuf.aliapp.org/service/initialize.jsonp"

            init_result = probe_initialize_jsonp_endpoint(
                endpoint_url=init_url,
                appkey="XFFXFXFF",
                cookie_str=enhanced_cookie,
            )
            result["initialize_result"] = init_result

            if init_result.get("status_code") == 200:
                result["findings"].append({
                    "type": "initialize_success",
                    "message": (
                        f"initialize.jsonp 返回 200，token={'有' if init_result.get('token') else '无'} "
                        f"csessionid={'有' if init_result.get('csessionid') else '无'}"
                    ),
                })
                result["recommendations"].append(
                    "initialize.jsonp 成功，可继续调用 analyze.jsonp 完成 NoCaptcha 验证"
                )
            else:
                result["findings"].append({
                    "type": "initialize_failed",
                    "message": (
                        f"initialize.jsonp 返回 {init_result.get('status_code')}: "
                        f"{init_result.get('error') or init_result.get('response_preview', '')[:100]}"
                    ),
                })
        else:
            result["findings"].append({
                "type": "um_json_no_umt",
                "message": "um.json 返回 200 但未返回 umt cookie",
            })
    else:
        result["findings"].append({
            "type": "um_json_failed",
            "message": (
                f"um.json 返回 {um_result.get('status_code')}: "
                f"{um_result.get('error') or um_result.get('response_preview', '')[:100]}"
            ),
        })

    # 综合建议
    if result["findings"]:
        success_findings = [f for f in result["findings"] if "success" in f.get("type", "")]
        if len(success_findings) >= 2:
            result["recommendations"].append(
                "路线 J 验证成功：FireyeJS token 可用于 um.json 和 initialize.jsonp，"
                "建议继续实现 analyze.jsonp 调用流程"
            )
        elif len(success_findings) == 1:
            result["recommendations"].append(
                "路线 J 部分成功：FireyeJS token 获取成功，但后续端点调用失败，"
                "需要分析失败原因（可能是 appkey/scene 配置不正确）"
            )
        else:
            result["recommendations"].append(
                "路线 J 需要进一步调试：FireyeJS token 获取成功但所有后续端点调用失败，"
                "建议检查 um.json 请求体格式和 appkey 配置"
            )

    return result


# ============================================================
# 14. 路线 J 完整 x5sec 流程：FireyeJS → um.json → initialize.jsonp → analyze.jsonp
# ============================================================
#
# 2026-08-03 实现：基于已成功的 FireyeJS token 提取（路线 J 第 1 步），
# 扩展为完整的 x5sec 生成闭环，串联四个端点：
#
# 1. FireyeJS token 提取（fetch_fireyejs_token_via_browser）
#    - 浏览器执行 FireyeJS（绕过 VM 混淆）
#    - 获取 fyToken + umidToken
#
# 2. um.json POST 设备指纹（probe_um_json_endpoint）
#    - 提交 NVC_Data 结构（包含 fyToken/umidToken）
#    - 服务端 Set-Cookie 下发 umt cookie
#
# 3. initialize.jsonp GET 获取 token（probe_initialize_jsonp_endpoint）
#    - 使用 um.json 返回的 cookie
#    - 服务端返回 NoCaptcha session token (t 字段，1a3b... 格式)
#
# 4. analyze.jsonp GET 验证（probe_analyze_jsonp_endpoint）
#    - 传入 token + fyToken + 行为指纹 p
#    - 服务端校验通过后返回 result.value (sig) 和 result.csessionid
#    - sig 用于构造 x5secdata cookie，或服务端直接 Set-Cookie 下发 x5sec
#
# 成功标志：
#   - analyze.jsonp 返回 result.code=0 且有 result.value (sig)
#   - 或 analyze.jsonp Set-Cookie 中包含 x5sec


def _build_behavior_data_p(cookie_str: str = "", fy_token: str = "") -> str:
    """构造 analyze.jsonp 的 p 参数（行为指纹）。

    nc.js 中 p 参数格式：ncSessionID_width_height_offsetX_offsetY_...
    由客户端 DOM 计算得出，包含滑块元素尺寸、位置、鼠标轨迹等。

    路线 J 中使用模拟值（占位），因为：
    1. 我们没有真实渲染 NoCaptcha 滑块 UI
    2. 服务器主要校验 n (FYToken) 和 t (token)，p 用于行为分析辅助
    3. 如果服务端要求 p 严格匹配，需进一步逆向 nc.js 的 p 生成逻辑

    Args:
        cookie_str: Cookie 字符串（用于提取 sessionId 等信息）
        fy_token: FYToken（用于校验）

    Returns:
        p 参数字符串
    """
    # 模拟真实的 p 参数格式（nc.js 源码逆向得到）
    # 格式：sessionId_width_height_offsetX_offsetY_trackLength_actionCount_...
    # 这里使用合理的默认值，让服务端能识别为合法格式
    # 真实 nc.js 的 p 参数示例：
    #   "01HV9P8N_300_40_0_0_1_1_1_1691500000000_1691500001000"

    # 生成随机的 sessionId（24 位字符，与 ncSessionID 格式一致）
    import random as _random
    import string as _string
    session_id = "".join(_random.choices(_string.ascii_letters + _string.digits, k=16))

    # 当前时间戳
    ts_now = int(time.time() * 1000)
    ts_start = ts_now - 2000  # 模拟 2 秒前开始

    # 构造 p 参数
    # 字段含义（从 nc.js 源码逆向）：
    # 1. ncSessionID（16-32 位随机字符串）
    # 2. 滑块容器 width
    # 3. 滑块容器 height
    # 4. offsetX（鼠标在滑块上的相对 X）
    # 5. offsetY（鼠标在滑块上的相对 Y）
    # 6. 拖动距离（像素）
    # 7. 拖动时长（毫秒）
    # 8. actionCount（鼠标动作数量）
    # 9. startTs（开始时间戳）
    # 10. endTs（结束时间戳）
    p_value = f"{session_id}_300_40_150_20_298_1200_5_{ts_start}_{ts_now}"

    return p_value


def _build_x5secdata_cookie(sig: str, csessionid: str, appkey: str = "XFFXFXFF") -> str:
    """构造 x5secdata cookie 值（基于 analyze.jsonp 返回的 sig 和 csessionid）。

    x5secdata cookie 格式（从浏览器观察得到）：
        x5secdata=<appkey>%3D<sig>%3D<csessionid>

    或者 URL 编码后：
        x5secdata=XFFXFXFF=<sig>=<csessionid>

    服务端在收到带 x5secdata 的 MTOP API 请求后，会校验 sig 并下发 x5sec cookie。

    Args:
        sig: analyze.jsonp 返回的 result.value（签名）
        csessionid: analyze.jsonp 返回的 result.csessionid
        appkey: 应用标识

    Returns:
        x5secdata cookie 值（不含 "x5secdata=" 前缀）
    """
    if not sig:
        return ""
    # 简单格式：appkey=sig=csessionid（与服务端约定的格式）
    if csessionid:
        return f"{appkey}={sig}={csessionid}"
    return f"{appkey}={sig}="


def complete_route_j_x5sec_flow(
    cookie_str: str = "",
    target_url: str = "",
    use_cache: bool = False,
    debug: bool = True,
) -> Dict[str, Any]:
    """路线 J 完整 x5sec 生成流程（方案 K 闭环实现）。

    串联四个端点完成 x5sec 生成：
    1. FireyeJS → fyToken + umidToken
    2. um.json → umt cookie
    3. initialize.jsonp → token (t)
    4. analyze.jsonp → sig + csessionid（或直接返回 x5sec）

    成功后返回 x5sec 值，可用于：
    - 注入到 cookie_str，跳过滑块求解
    - 缓存到 Redis（x5sec_cache_client），24 小时内复用
    - 直接调用 MTOP Token API 验证

    Args:
        cookie_str: Cookie 字符串（可选，匿名访问时留空）
        target_url: 目标页面 URL（默认闲鱼首页）
        use_cache: 是否使用 FireyeJS token 缓存（默认 False，研究模式）
        debug: 是否启用调试日志（默认 True）

    Returns:
        结果 dict：
        {
            "ok": bool,                    # 整体是否成功
            "x5sec": str,                  # 成功时为 x5sec 值
            "x5sec_source": str,           # x5sec 来源：analyze_set_cookie / analyze_body / constructed
            "sig": str,                    # analyze.jsonp 返回的 sig
            "csessionid": str,             # analyze.jsonp 返回的 csessionid
            "fy_token": str,               # FireyeJS fyToken
            "umid_token": str,             # FireyeJS umidToken
            "umt_cookie": str,             # um.json 返回的 umt cookie
            "nc_token": str,               # initialize.jsonp 返回的 token (t)
            "enhanced_cookie": str,        # 包含所有 cookie 的增强 cookie 字符串
            "steps": dict,                 # 各步骤结果
            "duration_ms": int,            # 总耗时
            "error": str,                  # 失败原因
        }
    """
    start_ts = time.time()
    result: Dict[str, Any] = {
        "ok": False,
        "x5sec": "",
        "x5sec_source": "",
        "sig": "",
        "csessionid": "",
        "fy_token": "",
        "umid_token": "",
        "umt_cookie": "",
        "nc_token": "",
        "enhanced_cookie": cookie_str,
        "steps": {},
        "duration_ms": 0,
        "error": "",
    }

    logger.info("[方案K-路线J-完整流程] 启动 x5sec 生成闭环")

    # ============================================================
    # 步骤 1：FireyeJS token 提取
    # ============================================================
    logger.info("[方案K-路线J-完整流程] 步骤 1：获取 FireyeJS token")
    token_result = fetch_fireyejs_token_via_browser(
        cookie_str=cookie_str,
        target_url=target_url,
        use_cache=use_cache,
        debug=debug,
    )
    result["steps"]["fireyejs"] = {
        "ok": token_result.get("ok"),
        "fyToken_len": len(token_result.get("fyToken", "")),
        "umidToken_len": len(token_result.get("umidToken", "")),
        "duration_ms": token_result.get("durationMs"),
        "error": token_result.get("error"),
    }

    if not token_result.get("ok"):
        result["error"] = f"步骤1 FireyeJS token 失败: {token_result.get('error')}"
        result["duration_ms"] = int((time.time() - start_ts) * 1000)
        logger.warning("[方案K-路线J-完整流程] ✗ 步骤 1 失败: %s", result["error"])
        return result

    fy_token = token_result.get("fyToken", "")
    umid_token = token_result.get("umidToken", "")
    result["fy_token"] = fy_token
    result["umid_token"] = umid_token

    logger.info(
        "[方案K-路线J-完整流程] ✓ 步骤 1 成功 fyToken长度=%d umidToken长度=%d",
        len(fy_token),
        len(umid_token),
    )

    # ============================================================
    # 步骤 2：um.json POST 设备指纹
    # ============================================================
    logger.info("[方案K-路线J-完整流程] 步骤 2：提交 um.json 设备指纹")
    um_url = "https://ynuf.aliapp.org/service/um.json"
    um_result = probe_um_json_endpoint(
        endpoint_url=um_url,
        appkey=ROUTE_J_DEFAULT_APPKEY,
        cookie_str=cookie_str,
        use_post=True,
        use_nvc_data=True,
        fy_token=fy_token,
        umid_token=umid_token,
    )
    result["steps"]["um_json"] = {
        "status_code": um_result.get("status_code"),
        "response_length": um_result.get("response_length"),
        "umt_cookie": bool(um_result.get("umt_cookie")),
        "cna_cookie": bool(um_result.get("cna_cookie")),
        "umid_id": bool(um_result.get("umid_id")),
        "x5sec_in_set_cookie": bool(um_result.get("x5sec_in_set_cookie")),
        "error": um_result.get("error"),
    }

    # 检查 um.json 是否直接返回 x5sec（罕见但可能）
    if um_result.get("x5sec_in_set_cookie"):
        result["x5sec"] = um_result["x5sec_in_set_cookie"]
        result["x5sec_source"] = "um_json_set_cookie"
        result["ok"] = True
        result["duration_ms"] = int((time.time() - start_ts) * 1000)
        logger.info(
            "[方案K-路线J-完整流程] ✓ um.json 直接返回 x5sec！长度=%d 耗时=%dms",
            len(result["x5sec"]),
            result["duration_ms"],
        )
        return result

    if um_result.get("status_code") != 200:
        logger.warning(
            "[方案K-路线J-完整流程] ⚠ 步骤 2 um.json 返回 %s，继续尝试后续步骤",
            um_result.get("status_code"),
        )
    else:
        logger.info(
            "[方案K-路线J-完整流程] ✓ 步骤 2 um.json 返回 200 umt=%s cna=%s",
            "✓" if um_result.get("umt_cookie") else "✗",
            "✓" if um_result.get("cna_cookie") else "✗",
        )

    # 增强 cookie：合并 um.json 返回的 cookie
    enhanced_cookie = cookie_str
    if um_result.get("umt_cookie"):
        result["umt_cookie"] = um_result["umt_cookie"]
        # 如果原 cookie 中已有 umt，先移除再追加新的
        enhanced_cookie = re.sub(r"\s*umt=[^;]+;?\s*", "", enhanced_cookie or "")
        enhanced_cookie = (enhanced_cookie + "; umt=" + um_result["umt_cookie"]).lstrip("; ")
    if um_result.get("cna_cookie"):
        enhanced_cookie = re.sub(r"\s*cna=[^;]+;?\s*", "", enhanced_cookie or "")
        enhanced_cookie = (enhanced_cookie + "; cna=" + um_result["cna_cookie"]).lstrip("; ")
    result["enhanced_cookie"] = enhanced_cookie

    # ============================================================
    # 步骤 3：initialize.jsonp GET 获取 token
    # ============================================================
    logger.info("[方案K-路线J-完整流程] 步骤 3：调用 initialize.jsonp 获取 token")
    init_url = "https://cf.aliyun.com/nocaptcha/initialize.jsonp"
    init_result = probe_initialize_jsonp_endpoint(
        endpoint_url=init_url,
        appkey=ROUTE_J_DEFAULT_APPKEY,
        scene=ROUTE_J_DEFAULT_SCENE,
        cookie_str=enhanced_cookie,
    )
    result["steps"]["initialize_jsonp"] = {
        "status_code": init_result.get("status_code"),
        "response_length": init_result.get("response_length"),
        "token_len": len(init_result.get("token", "")),
        "result_code": init_result.get("result_code"),
        "x5sec_in_set_cookie": bool(init_result.get("x5sec_in_set_cookie")),
        "error": init_result.get("error"),
    }

    # 检查 initialize.jsonp 是否直接返回 x5sec（罕见但可能）
    if init_result.get("x5sec_in_set_cookie"):
        result["x5sec"] = init_result["x5sec_in_set_cookie"]
        result["x5sec_source"] = "initialize_set_cookie"
        result["ok"] = True
        result["duration_ms"] = int((time.time() - start_ts) * 1000)
        logger.info(
            "[方案K-路线J-完整流程] ✓ initialize.jsonp 直接返回 x5sec！长度=%d 耗时=%dms",
            len(result["x5sec"]),
            result["duration_ms"],
        )
        return result

    nc_token = init_result.get("token", "")
    if nc_token:
        result["nc_token"] = nc_token
        logger.info(
            "[方案K-路线J-完整流程] ✓ 步骤 3 成功获取 token 长度=%d 前缀=%s",
            len(nc_token),
            nc_token[:8],
        )
    else:
        logger.warning(
            "[方案K-路线J-完整流程] ⚠ 步骤 3 initialize.jsonp 未返回 token，仍尝试 analyze.jsonp"
        )

    # ============================================================
    # 步骤 4：analyze.jsonp GET 验证（核心步骤）
    # ============================================================
    logger.info("[方案K-路线J-完整流程] 步骤 4：调用 analyze.jsonp 验证")
    analyze_url = "https://cf.aliyun.com/nocaptcha/analyze.jsonp"

    # 构造行为指纹 p 参数
    behavior_p = _build_behavior_data_p(cookie_str=enhanced_cookie, fy_token=fy_token)

    # 如果没有 nc_token，使用占位 token（让服务端返回明确的错误码便于诊断）
    token_for_analyze = nc_token or "1a3btest"

    # 优先 GET 模式（nc.js 默认使用 GET JSONP）
    analyze_result = probe_analyze_jsonp_endpoint(
        endpoint_url=analyze_url,
        cookie_str=enhanced_cookie,
        appkey=ROUTE_J_DEFAULT_APPKEY,
        token=token_for_analyze,
        fy_token=fy_token,
        scene=ROUTE_J_DEFAULT_SCENE,
        behavior_data=behavior_p,
        use_post=False,
    )

    # 如果 GET 失败，尝试 POST 模式
    if (not analyze_result.get("result_value")
            and not analyze_result.get("x5sec_in_set_cookie")
            and analyze_result.get("status_code") != 200):
        logger.info("[方案K-路线J-完整流程] GET 失败，尝试 POST 模式")
        analyze_result_post = probe_analyze_jsonp_endpoint(
            endpoint_url=analyze_url,
            cookie_str=enhanced_cookie,
            appkey=ROUTE_J_DEFAULT_APPKEY,
            token=token_for_analyze,
            fy_token=fy_token,
            scene=ROUTE_J_DEFAULT_SCENE,
            behavior_data=behavior_p,
            use_post=True,
        )
        # 使用 POST 结果（如果更好的话）
        if (analyze_result_post.get("result_value")
                or analyze_result_post.get("x5sec_in_set_cookie")):
            analyze_result = analyze_result_post

    result["steps"]["analyze_jsonp"] = {
        "status_code": analyze_result.get("status_code"),
        "response_length": analyze_result.get("response_length"),
        "result_code": analyze_result.get("result_code"),
        "result_value_len": len(analyze_result.get("result_value", "")),
        "result_csessionid_len": len(analyze_result.get("result_csessionid", "")),
        "x5sec_in_set_cookie": bool(analyze_result.get("x5sec_in_set_cookie")),
        "x5sec_in_body": analyze_result.get("x5sec_in_body"),
        "error": analyze_result.get("error"),
    }

    # ============================================================
    # 步骤 5：提取 x5sec
    # ============================================================
    logger.info("[方案K-路线J-完整流程] 步骤 5：提取 x5sec")

    # 5.1 优先：analyze.jsonp Set-Cookie 中的 x5sec
    if analyze_result.get("x5sec_in_set_cookie"):
        result["x5sec"] = analyze_result["x5sec_in_set_cookie"]
        result["x5sec_source"] = "analyze_set_cookie"
        result["ok"] = True
        logger.info(
            "[方案K-路线J-完整流程] ✓ analyze.jsonp Set-Cookie 返回 x5sec 长度=%d",
            len(result["x5sec"]),
        )

    # 5.2 次选：analyze.jsonp 响应体中包含 x5sec（手动搜索）
    elif analyze_result.get("x5sec_in_body"):
        # 尝试从响应中提取 x5sec
        body_text = analyze_result.get("response_preview", "")
        # 常见格式：x5sec=... 或 "x5sec":"..."
        body_x5sec_match = re.search(r'"?x5sec"?\s*[:=]\s*"?([^";,\s\}]+)', body_text)
        if body_x5sec_match:
            result["x5sec"] = body_x5sec_match.group(1)
            result["x5sec_source"] = "analyze_body"
            result["ok"] = True
            logger.info(
                "[方案K-路线J-完整流程] ✓ analyze.jsonp 响应体包含 x5sec 长度=%d",
                len(result["x5sec"]),
            )

    # 5.3 兜底：使用 sig + csessionid 构造 x5secdata（等待 MTOP API 触发 x5sec 下发）
    sig = analyze_result.get("result_value", "")
    csessionid = analyze_result.get("result_csessionid", "")
    result["sig"] = sig
    result["csessionid"] = csessionid

    if sig and analyze_result.get("result_code") == 0:
        # analyze.jsonp 验证成功，构造 x5secdata cookie
        x5secdata_value = _build_x5secdata_cookie(
            sig=sig,
            csessionid=csessionid,
            appkey=ROUTE_J_DEFAULT_APPKEY,
        )
        if x5secdata_value:
            # 将 x5secdata 加入 cookie，作为"准 x5sec"返回
            # 后续 MTOP API 调用会校验 x5secdata，通过后服务端会下发真正的 x5sec
            result["x5sec"] = x5secdata_value
            result["x5sec_source"] = "constructed_from_sig"
            result["ok"] = True
            logger.info(
                "[方案K-路线J-完整流程] ✓ 基于 sig 构造 x5secdata 长度=%d（需 MTOP API 触发下发）",
                len(result["x5sec"]),
            )

            # 增强 cookie：加入 x5secdata
            enhanced_cookie = re.sub(
                r"\s*x5secdata=[^;]+;?\s*", "", enhanced_cookie or ""
            )
            enhanced_cookie = (
                enhanced_cookie + "; x5secdata=" + x5secdata_value
            ).lstrip("; ")
            result["enhanced_cookie"] = enhanced_cookie

    if not result["ok"]:
        # 汇总失败原因
        error_parts = []
        if not analyze_result.get("result_value"):
            error_parts.append("analyze.jsonp 未返回 sig")
        if analyze_result.get("result_code") not in (0, None):
            error_parts.append(f"result.code={analyze_result.get('result_code')}")
        if analyze_result.get("error"):
            error_parts.append(f"analyze.jsonp 错误: {analyze_result.get('error')}")

        result["error"] = "；".join(error_parts) or "analyze.jsonp 验证未通过"
        logger.warning(
            "[方案K-路线J-完整流程] ✗ 步骤 5 失败: %s (result.code=%s)",
            result["error"],
            analyze_result.get("result_code"),
        )

    result["duration_ms"] = int((time.time() - start_ts) * 1000)

    # 综合日志
    if result["ok"]:
        logger.info(
            "[方案K-路线J-完整流程] ✓✓✓ x5sec 生成成功！来源=%s 长度=%d 总耗时=%dms",
            result["x5sec_source"],
            len(result["x5sec"]),
            result["duration_ms"],
        )
    else:
        logger.warning(
            "[方案K-路线J-完整流程] ✗ x5sec 生成失败，总耗时=%dms",
            result["duration_ms"],
        )

    return result


def try_route_j_x5sec(cookie_str: str, m_h5_tk: str = "") -> Tuple[Optional[str], Optional[str]]:
    """路线 J x5sec 生成入口（用于 ws_token 优先级链）。

    本函数是方案 K 路线 J 的对外接口，调用 complete_route_j_x5sec_flow
    生成 x5sec，并返回 (x5sec, enhanced_cookie) 用于注入。

    **集成位置**：在 ws_token.get_ws_token_with_refreshed_m_h5_tk 的优先级链中，
    作为优先级 1.6 调用（在方案 K 本地生成之后，x5sec 缓存之前）。

    优先级链（更新后）：
    - 优先级 1：直接 Token API（无 x5sec）
    - 优先级 1.5：方案 K 本地生成 x5sec（待逆向完成）
    - 优先级 1.6：方案 K 路线 J（FireyeJS → um.json → initialize.jsonp → analyze.jsonp）← 本函数
    - 优先级 2：x5sec 缓存注入（Redis）
    - 优先级 2.5：纯 HTTP x5sec 提取
    - 优先级 3：静默提取（浏览器）
    - 优先级 4：滑块求解（浏览器）

    Args:
        cookie_str: Cookie 字符串
        m_h5_tk: _m_h5_tk 值（可选，路线 J 不依赖此值）

    Returns:
        (x5sec, enhanced_cookie) — 成功时两个都有值；失败时两个都是 None
    """
    if not cookie_str:
        return None, None

    # 路线 J 开关：默认关闭，通过环境变量 ROUTE_J_ENABLED=true 启用
    route_j_enabled = os.environ.get("ROUTE_J_ENABLED", "false").lower() == "true"
    if not route_j_enabled:
        logger.debug("[方案K-路线J] ROUTE_J_ENABLED=false，跳过")
        return None, None

    try:
        # 2026-08-03 v5 优化：优先使用 crawler-service 的 route-j-flow 端点
        # 该端点在浏览器内完成整个流程，解决 IP 不一致问题
        flow_result = fetch_route_j_flow_via_browser(cookie_str=cookie_str)

        # 如果 route-j-flow 端点失败，回退到 Python 端串联调用（旧逻辑）
        if not flow_result or not flow_result.get("ok"):
            logger.info(
                "[方案K-路线J] route-j-flow 端点失败，回退到 Python 串联模式: %s",
                flow_result.get("error") if flow_result else "无响应",
            )
            flow_result = complete_route_j_x5sec_flow(
                cookie_str=cookie_str,
                use_cache=True,
                debug=False,
            )

        if not flow_result.get("ok"):
            logger.info(
                "[方案K-路线J] x5sec 生成失败: %s 耗时=%dms",
                flow_result.get("error"),
                flow_result.get("duration_ms") or flow_result.get("durationMs", 0),
            )
            return None, None

        x5sec = flow_result.get("x5sec", "")
        # 浏览器端返回的字段名是 finalCookies，Python 端是 enhanced_cookie
        enhanced_cookie = (
            flow_result.get("enhanced_cookie")
            or flow_result.get("finalCookies")
            or cookie_str
        )

        if not x5sec:
            return None, None

        # 如果 x5sec 是从 analyze.jsonp 直接返回的，注入到 cookie
        # 如果是基于 sig 构造的 x5secdata，注入后需要 MTOP API 触发下发
        try:
            from .x5sec_cache_client import inject_x5sec_into_cookie
            injected_cookie = inject_x5sec_into_cookie(enhanced_cookie, x5sec)
            if injected_cookie and injected_cookie != enhanced_cookie:
                enhanced_cookie = injected_cookie
        except ImportError:
            logger.debug("[方案K-路线J] x5sec_cache_client 不可用，跳过 cookie 注入")

        logger.info(
            "[方案K-路线J] ✓ x5sec 生成成功 来源=%s 长度=%d",
            flow_result.get("x5sec_source") or flow_result.get("x5secSource"),
            len(x5sec),
        )
        return x5sec, enhanced_cookie

    except Exception as e:
        logger.warning("[方案K-路线J] 异常: %s", e)
        return None, None


def fetch_route_j_flow_via_browser(
    cookie_str: str = "",
    target_url: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """通过 crawler-service 的 route-j-flow 端点完成完整 x5sec 流程。

    2026-08-03 v5 新增：调用 crawler-service 的 /api/fireyejs/route-j-flow 端点，
    让浏览器内完成 FireyeJS → um.json → initialize.jsonp → analyze.jsonp 全流程。

    优势（相比 Python 端串联调用）：
    1. IP 一致性：FireyeJS token 和 um.json 都从同一浏览器发出
    2. Cookie 一致性：浏览器自动管理 Set-Cookie
    3. Referer/Origin：浏览器自动添加正确的请求头
    4. CORS：浏览器自动处理跨域

    Args:
        cookie_str: Cookie 字符串（可选）
        target_url: 目标页面 URL（默认闲鱼首页）
        debug: 是否启用调试日志

    Returns:
        RouteJFlowResult 完整结构（包含所有步骤的响应）
    """
    try:
        import requests as _requests
    except ImportError:
        return {"ok": False, "error": "requests 模块不可用"}

    crawler_url = os.environ.get(
        "CRAWLER_SERVICE_URL", "http://crawler-service:3001"
    )
    endpoint = f"{crawler_url.rstrip('/')}/api/fireyejs/route-j-flow"

    payload: Dict[str, Any] = {
        "simulateBehavior": True,
        "debug": debug,
    }
    if cookie_str:
        payload["cookie"] = cookie_str
    if target_url:
        payload["targetUrl"] = target_url

    internal_token = os.environ.get("INTERNAL_API_TOKEN", "")
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
    }

    try:
        resp = _requests.post(endpoint, json=payload, headers=headers, timeout=120)
    except Exception as e:
        logger.warning("[方案K-路线J-v5] 调用 route-j-flow 端点失败: %s", e)
        return {"ok": False, "error": f"crawler-service 调用失败: {e}"}

    if resp.status_code not in (200, 422):
        logger.warning(
            "[方案K-路线J-v5] route-j-flow 返回 %d: %s",
            resp.status_code,
            resp.text[:200],
        )
        return {"ok": False, "error": f"HTTP {resp.status_code}"}

    try:
        data = resp.json()
    except Exception as e:
        return {"ok": False, "error": f"响应解析失败: {e}"}

    if data.get("ok"):
        logger.info(
            "[方案K-路线J-v5] ✓ route-j-flow 成功 x5sec长度=%d 来源=%s 耗时=%dms",
            len(data.get("x5sec", "")),
            data.get("x5secSource", ""),
            data.get("durationMs", 0),
        )
    else:
        logger.info(
            "[方案K-路线J-v5] route-j-flow 失败: %s 耗时=%dms",
            data.get("error"),
            data.get("durationMs", 0),
        )

    return data
