"""
滑块验证处理服务
================

实现两部分能力：

1. **智能检测**：从 MTOP API 响应中检测滑块/人机验证需求
   - 关键词：FAIL_SYS_USER_VALIDATE / RGV587_ERROR / 被挤爆啦 / CAPTCHA_NEEDED
   - 提取验证 URL（data.url）

2. **操作指引**：为前端提供详细的分步操作指引
   - 检测到滑块后返回结构化指引数据
   - 包含：访问 URL、操作步骤、Cookie 更新提示

3. **自动拖动**：调用 crawler-service 的 Playwright 滑块求解接口
   - 通过 HTTP 调用 crawler-service 的 /api/goofish/slide-solve
   - 失败时回退到人工处理指引

调用方式：
- detect_captcha(response) -> 检测是否需要滑块
- build_instructions(account_id, captcha_url) -> 构建操作指引
- try_auto_solve(account_id) -> 调用 Playwright 自动求解
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from sqlalchemy import text

from ..core.config import settings
from ..core.cookie_crypto import decrypt_cookie_if_needed, encrypt_cookie_for_storage
from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)


def _resolve_headless_mode(value: Optional[bool]) -> bool:
    if value is not None:
        return bool(value)
    return os.name != "nt" and not os.environ.get("DISPLAY")


# ============================================================
# 滑块验证检测关键词
# ============================================================
CAPTCHA_KEYWORDS = (
    "FAIL_SYS_USER_VALIDATE",
    "RGV587_ERROR",
    "被挤爆啦",
    "CAPTCHA_NEEDED",
    "xcaptcha",
    "baxia",
    "punish",
)

CAPTCHA_URL_KEYWORDS = (
    "url",
    "captcha_url",
    "captchaUrl",
    "verifyUrl",
    "verify_url",
)


@dataclass
class CaptchaDetectResult:
    """滑块检测结果"""
    detected: bool
    captcha_url: Optional[str] = None
    reason: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class CaptchaInstructions:
    """操作指引"""
    account_id: int
    captcha_url: Optional[str]
    steps: list[str] = field(default_factory=list)
    title: str = "检测到账号需要完成滑块验证"
    auto_solve_available: bool = True
    manual_fallback_url: str = "https://www.goofish.com/"
    message: str = ""


# ============================================================
# 1. 智能检测
# ============================================================
def detect_captcha_from_response(response: dict | str | None) -> CaptchaDetectResult:
    """从 MTOP API 响应中检测滑块验证需求。

    支持两种输入：
    - dict: 完整的 MTOP 响应 JSON
    - str: 响应文本（直接搜索关键词）

    返回 CaptchaDetectResult，包含验证 URL（如果有的话）。
    """
    if not response:
        return CaptchaDetectResult(detected=False)

    if isinstance(response, str):
        text_lower = response.lower()
        for kw in CAPTCHA_KEYWORDS:
            if kw.lower() in text_lower:
                return CaptchaDetectResult(
                    detected=True,
                    reason=f"响应包含关键词: {kw}",
                )
        return CaptchaDetectResult(detected=False)

    # dict 类型：先查 ret 字段，再查 data.url
    ret_list = response.get("ret") or []
    if isinstance(ret_list, list):
        ret_str = " | ".join(str(r) for r in ret_list)
    else:
        ret_str = str(ret_list)

    for kw in CAPTCHA_KEYWORDS:
        if kw in ret_str:
            # 尝试提取验证 URL
            data = response.get("data") or {}
            captcha_url = None
            if isinstance(data, dict):
                for url_key in CAPTCHA_URL_KEYWORDS:
                    if url_key in data and data[url_key]:
                        captcha_url = str(data[url_key])
                        break

            return CaptchaDetectResult(
                detected=True,
                captcha_url=captcha_url,
                reason=f"ret 包含 {kw}",
                raw_response=response,
            )

    # 兜底：检查整个响应的字符串形式
    response_str = str(response)
    for kw in CAPTCHA_KEYWORDS:
        if kw in response_str:
            return CaptchaDetectResult(
                detected=True,
                reason=f"响应包含关键词: {kw}",
                raw_response=response if isinstance(response, dict) else None,
            )

    return CaptchaDetectResult(detected=False)


# ============================================================
# 2. 操作指引
# ============================================================
def build_captcha_instructions(
    account_id: int,
    captcha_url: Optional[str] = None,
    account_name: Optional[str] = None,
) -> CaptchaInstructions:
    """构建详细的滑块验证操作指引。

    返回的指引包含：
    - 自动求解：调用 Playwright 自动拖动（auto_solve_available=True）
    - 人工兜底：4 步指引（访问闲鱼→完成验证→复制 Cookie→更新 Cookie）
    """
    steps = [
        '【方案一·自动求解】点击下方"自动求解"按钮，系统将启动浏览器自动拖动滑块完成验证（推荐先尝试）',
        "【方案二·人工处理】如果自动求解失败，请按以下步骤操作：",
        "  1. 点击访问闲鱼主页 https://www.goofish.com/ 并登录（如已登录可跳过）",
        "  2. 在闲鱼页面完成滑块验证（通常出现在消息、商品发布等场景）",
        "  3. 验证通过后，按 F12 打开开发者工具 → Application → Cookies → 复制 .goofish.com 域下的完整 Cookie",
        '  4. 返回本页面，点击"手动更新 Cookie"按钮，粘贴复制的 Cookie 并保存',
        '  5. 保存后点击"启动连接"，系统会自动刷新 WebSocket Token 并重连',
    ]

    name_prefix = f"账号 {account_name or account_id} " if account_id else ""
    return CaptchaInstructions(
        account_id=account_id,
        captcha_url=captcha_url,
        steps=steps,
        title=f"{name_prefix}检测到滑块验证",
        auto_solve_available=True,
        message=(
            "检测到账号需要完成滑块验证。请先尝试自动求解；"
            "如自动求解失败，请按指引手动完成验证并更新 Cookie。"
            "更新 Cookie 后点击启动连接，会自动刷新 Token，"
            "滑块校验生效会延迟，稍等片刻会自动连接。"
        ),
    )


# ============================================================
# 3. Playwright 自动求解
# ============================================================
async def try_auto_solve(
    account_id: int,
    tenant_id: int,
    target_url: Optional[str] = None,
    headless: Optional[bool] = None,
    max_retries: int = 5,
    *,
    force: bool = False,
    profile_strategy: str = "persistent",
    semi_auto_fallback: bool = False,
) -> dict:
    """调用 crawler-service 的 Playwright 滑块求解接口。

    Args:
        account_id: 账号 ID（用于读取 Cookie）
        target_url: 目标页面 URL（默认闲鱼首页）
        headless: 是否无头模式（默认 false，滑块识别有头更稳定）
        max_retries: 最大重试次数
        force: 是否跳过指数退避（默认 False，全自动遵守退避）

    Returns:
        {
            "success": bool,
            "solved": bool,
            "captchaDetected": bool,
            "attempts": int,
            "error": Optional[str],
            "durationMs": int,
        }
    """
    # 全自动指数退避：冷却期内直接拒绝，避免 punish 加码
    from .captcha_backoff import assert_auto_solve_allowed, record_solve_failure, record_solve_success
    from .account_proxy import load_account_proxy, proxy_to_playwright, proxy_public_label

    blocked = await assert_auto_solve_allowed(account_id, tenant_id, force=force)
    if blocked:
        logger.warning(
            "滑块求解被指数退避拦截 accountId=%d error=%s",
            account_id, blocked.get("error"),
        )
        return blocked

    # 读取账号 Cookie
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT encrypted_cookie, tenant_id FROM xianyu_account_auth "
                    "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
    except Exception as e:
        log_service_failure(
            logger, e, operation="load_captcha_account_cookie",
            tenant_id=tenant_id, account_id=account_id,
        )
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "errorCode": "CAPTCHA_ACCOUNT_LOAD_FAILED",
            "error": "读取账号信息失败，请稍后重试",
            "durationMs": 0,
        }

    if not row:
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "error": "账号不存在或未配置 Cookie",
            "durationMs": 0,
        }

    cookie_str = decrypt_cookie_if_needed(row["encrypted_cookie"])
    if not cookie_str:
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "error": "Cookie 解密失败",
            "durationMs": 0,
        }

    # 按账号绑定代理（可选）
    proxy = await load_account_proxy(account_id, tenant_id)
    proxy_payload = proxy_to_playwright(proxy)
    if proxy_payload:
        logger.info(
            "滑块求解使用账号绑定代理 accountId=%d proxy=%s",
            account_id, proxy_public_label(proxy),
        )

    # 调用 crawler-service
    crawler_url = getattr(settings, "crawler_service_url", None) or os.environ.get(
        "CRAWLER_SERVICE_URL", "http://localhost:3001"
    )
    endpoint = f"{crawler_url.rstrip('/')}/api/goofish/slide-solve"

    # 内部 token
    internal_token = (
        getattr(settings, "internal_api_token", None)
        or os.environ.get("INTERNAL_API_TOKEN")
        or "dev-only-internal-api-token-change-me-32-chars"
    )
    tenant_id = int(row["tenant_id"])

    resolved_headless = _resolve_headless_mode(headless)

    # crawler-service 内部重试次数：保留传入值（默认 5 次）
    # 重试覆盖场景：点击框体重试、加载转圈、下载消息失败刷新等，单次操作很快，
    # 5 次重试整体通常在 120-150 秒内完成，能显著提升偶发抖动场景的成功率。
    #
    # 项目硬约束（不可违反）：
    # - httpx 超时必须保持 180s
    # - maxRetries 必须保持 5
    # - timeoutMs 必须保持 30000（单次操作超时 30 秒）
    # 理论最大耗时 5×30s=150s，在 httpx 180s 超时以内，确保 5 次重试能完整执行。
    # 2026-07-29 修复：原先 timeoutMs=90000，理论最大 5×90s=450s 远超 httpx 180s，
    # 导致单次操作卡住时 httpx 先超时，retry_count=0，5 次重试根本没机会执行。
    # 降到 30 秒后，单次操作超时后立即进入下一次重试，5 次总耗时 ≤150s < 180s。
    # 详见 project_memory.md "滑块求解时长配置硬约束"。
    effective_max_retries = max(1, min(int(max_retries), 5))
    payload = {
        "cookie": cookie_str,
        "targetUrl": target_url,
        "headless": resolved_headless,
        "maxRetries": effective_max_retries,
        "timeoutMs": 30000,
        # profile 策略：persistent（默认持久化，累积历史降低风控）/ seed / temp
        "profileStrategy": profile_strategy,
        # 半自动人工兜底：全自动失败后保留窗口供人工拖拽
        "semiAutoFallback": semi_auto_fallback,
    }
    if proxy_payload:
        payload["proxy"] = proxy_payload
    else:
        # 2026-08-02 新增：无账号绑定代理时，请求 crawler-service 使用住址IP代理池
        # 业务目的：测试住址IP vs 服务器IP的求解成功率对比
        # crawler-service 会根据 USE_RESIDENTIAL_PROXY 环境变量决定是否启用
        # 详见 .trae/rules/x5sec-research-knowledge.md 方案 E
        use_residential = os.environ.get("USE_RESIDENTIAL_PROXY", "false").lower() == "true"
        if use_residential:
            payload["useResidentialProxy"] = True
            logger.info("滑块求解请求使用住址IP代理池 accountId=%d", account_id)

    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": str(tenant_id),
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            data = resp.json()
    except httpx.TimeoutException as e:
        # HTTP 超时（ReadTimeout/ConnectTimeout/PoolTimeout）
        # 2026-07-29 事故修复：原先所有 httpx 异常统一归为 CAPTCHA_SOLVER_UNAVAILABLE → service_unavailable
        # （不可重试 + 累加退避），导致 crawler-service 临时繁忙/浏览器操作耗时较长时账号被冷却 60s，
        # WS 每次重连触发求解都被 assert_auto_solve_allowed 拦截，账号长时间无法自动求解。
        # 修复：超时是临时性错误，归为 timeout（可重试 1 次 + 不累加退避）。
        # 注意：httpx 超时 180s 是项目硬约束，不得缩短（见 project_memory.md）。
        log_service_failure(
            logger, e, operation="solve_captcha",
            tenant_id=tenant_id, account_id=account_id,
        )
        await record_solve_failure(
            account_id, tenant_id,
            error=f"滑块求解超时：{type(e).__name__}",
            skip_backoff=True,  # 超时是临时性错误，不累加退避
        )
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "errorCode": "CAPTCHA_SOLVER_TIMEOUT",
            "error": f"滑块求解超时（{type(e).__name__}），请稍后重试",
            "durationMs": int((time.time() - started) * 1000),
        }
    except (httpx.ConnectError, httpx.NetworkError) as e:
        # 网络连接错误（ConnectError/ReadError/WriteError 等）
        # 2026-07-29 事故修复：原先归为 service_unavailable 并累加退避，
        # 但网络错误也是临时性，不累加退避避免账号被冷却。
        log_service_failure(
            logger, e, operation="solve_captcha",
            tenant_id=tenant_id, account_id=account_id,
        )
        await record_solve_failure(
            account_id, tenant_id,
            error=f"滑块求解网络错误：{type(e).__name__}",
            skip_backoff=True,  # 网络错误是临时性，不累加退避
        )
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "errorCode": "CAPTCHA_SOLVER_UNAVAILABLE",
            "error": "滑块求解服务网络异常，请稍后重试",
            "durationMs": int((time.time() - started) * 1000),
        }
    except Exception as e:
        log_service_failure(
            logger, e, operation="solve_captcha",
            tenant_id=tenant_id, account_id=account_id,
        )
        await record_solve_failure(
            account_id, tenant_id, error="滑块求解服务暂时不可用",
        )
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "errorCode": "CAPTCHA_SOLVER_UNAVAILABLE",
            "error": "滑块求解服务暂时不可用，请稍后重试",
            "durationMs": int((time.time() - started) * 1000),
        }

    duration_ms = int((time.time() - started) * 1000)
    solve_ok = bool(data.get("ok"))
    crawler_error = data.get("error") or ""

    # 读取求解成功后的最新 cookies（Baxia 验证通过后服务器下发新 token，如 _m_h5_tk）
    fresh_cookies = data.get("cookies") or ""

    # 退避状态：成功清零 / 失败累加（含 captchaDetected 但未通过）
    if solve_ok and bool(data.get("solved")):
        await record_solve_success(account_id, tenant_id)
    else:
        # 浏览器崩溃错误跳过指数退避（临时性错误，重试可能成功）
        # 2026-07-29 事故修复：浏览器崩溃（Page crashed / browserContext closed）
        # 原先累加退避导致账号被冷却 60s，WS 每次重连触发求解都被
        # assert_auto_solve_allowed 拦截，账号长时间无法自动求解。
        is_browser_crash = _is_browser_launch_failure(crawler_error)
        # 2026-07-31 优化：cookie_invalid 失败也跳过指数退避
        # 原因：cookie_invalid 是 Cookie 失效，不是求解器问题。
        # 累加 fail_count 没有意义（用户重新登录后 Cookie 恢复，fail_count 应清零）。
        # 不累加退避让 WS 下次重连能立即触发求解，用户重新登录后能更快恢复。
        # 频率控制由 captcha_queue.py 的队列进程去重保证（queued/retrying 状态检查）。
        #
        # 2026-08-01 修正：移除 "login.token" 作为 cookie_invalid 判定条件。
        # 原因：mtop.taobao.idlemessage.pc.login.token 是 WS token 刷新 API 的名字，
        # Baxia 挑战该 API 时 iframe URL 会含 login.token，但 Cookie 仍可能有效。
        # 之前把 "login.token" 当作 cookie_invalid 是误判，导致 Cookie 有效的账号
        # 被错误标记为 Cookie 失效（详见 project_memory.md 2026-07-31 事故）。
        # Cookie 是否真正失效只能通过 checkLoginPage 检测真实登录页跳转判断。
        #
        # 2026-08-01 二次修正：cookie_invalid 不再 skip_backoff。
        # 原因：真正的 cookie_invalid（Cookie 已过期）短期内重试必然失败，浪费资源。
        # captcha_backoff.py 统一 60 秒冷却（MAX_COOLDOWN_SEC=60），等用户重新登录。
        # 累加 fail_count 让 60 秒冷却生效，避免瞬时高频触发 Baxia 风控。
        is_cookie_invalid = "Cookie Session" in crawler_error or "Cookie 已过期" in crawler_error or "FAIL_SYS_SESSION_EXPIRED" in crawler_error
        # 2026-08-02 修正：累进冷却已废弃，所有失败统一 60 秒冷却（见 cookie-valid-ws-persistence.md）
        # - slider_fail：60 秒冷却（快速重试，服务于 WS 持久化目标）
        # - cookie_invalid：60 秒冷却（等用户重新登录）
        # - browser_crashed：跳过退避（临时性错误，不累加 fail_count）
        # - 其他失败：60 秒冷却
        if is_browser_crash:
            failure_reason_for_cooldown = "browser_crashed"
        elif is_cookie_invalid:
            failure_reason_for_cooldown = "cookie_invalid"
        else:
            failure_reason_for_cooldown = "slider_fail"
        await record_solve_failure(
            account_id, tenant_id,
            error=crawler_error or "滑块验证未通过",
            skip_backoff=is_browser_crash,  # cookie_invalid 不再 skip_backoff，让 60 秒冷却生效
            failure_reason=failure_reason_for_cooldown,
        )

    # 如果求解成功且有最新 cookies，立即更新数据库中的 cookie
    # 关键：Baxia 验证通过后浏览器中的 cookie 已更新，必须持久化到数据库，
    # 否则后续 _verify_cookie_via_token_api 和 API 调用仍用旧 cookie 会失败
    if solve_ok and fresh_cookies:
        # 2026-08-03 修复"滑块成功但cookie失效"误判（用户质疑的核心问题）
        # 原因：crawler-service 返回的 cookies 和 x5sec 是两个独立字段，
        #       fresh_cookies 可能不包含 x5sec（Baxia 验证通过后获得的标记）。
        #       如果不注入 x5sec 就更新数据库，后续 _verify_cookie_via_token_api
        #       读取的 cookie 缺少 x5sec，调用 Token API 又被 Baxia 拦截，
        #       返回 FAIL_SYS_SESSION_EXPIRED，被误判为 Cookie 失效。
        #       实际上 Cookie 是有效的（能让浏览器登录、加载滑块、拖动通过），
        #       只是缺少 x5sec 标记。用户逻辑："滑块成功说明cookie有效"是正确的。
        x5sec_value = data.get("x5sec") or ""
        # 2026-08-03 修复 x5sec 注入条件 bug：
        # 原条件 `if x5sec_value and "x5sec=" not in fresh_cookies:` 有 bug——
        # 如果 fresh_cookies 已包含旧 x5sec（被 Baxia punish 的旧值），就不注入新 x5sec，
        # 导致后续 Token API 调用仍用旧 x5sec 失败，被误判为 cookie_invalid。
        # inject_x5sec_into_cookie 是幂等的（内部 re.sub 替换旧值），
        # 所以只要 x5sec_value 有值就强制注入（替换或追加）。
        if x5sec_value:
            try:
                from .x5sec_cache_client import inject_x5sec_into_cookie
                # 检查 fresh_cookies 是否已包含 x5sec（用于日志区分"替换"vs"追加"）
                had_x5sec = "x5sec=" in fresh_cookies
                fresh_cookies = inject_x5sec_into_cookie(fresh_cookies, x5sec_value)
                logger.info(
                    "已将 x5sec 注入到 fresh_cookies accountId=%d x5secLen=%d cookieLen=%d action=%s",
                    account_id, len(x5sec_value), len(fresh_cookies),
                    "replace" if had_x5sec else "append",
                )
            except Exception as e:
                log_service_failure(
                    logger, e, operation="inject_x5sec_to_fresh_cookies",
                    tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                )

        # 2026-08-03 新增：将 x5sec 缓存到 Redis，实现后续 WS 重连免滑块
        # 原因：crawler-service 的 cacheX5sec 已在 slide-solve 端点中调用，
        #       但 Python 端缺少缓存写入函数，导致通过 _try_silent_extract /
        #       _try_http_x5sec_extract 获取的 x5sec 无法缓存。
        #       此处作为双重保障：即使 crawler-service 缓存失败，Python 端也缓存一次。
        if x5sec_value:
            try:
                from .x5sec_cache_client import cache_x5sec
                cache_x5sec(fresh_cookies or cookie_str, x5sec_value)
                logger.info(
                    "已缓存 x5sec 到 Redis accountId=%d x5secLen=%d",
                    account_id, len(x5sec_value),
                )
            except Exception as e:
                log_service_failure(
                    logger, e, operation="cache_x5sec_after_solve",
                    tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                )
            # 方案 K：记录滑块求解获取的 x5sec 样本（用于离线逆向分析）
            # 滑块求解成功是最高价值的样本（确认 Baxia 验证通过后服务端下发的 x5sec）
            try:
                from .mtop_sign_research import log_x5sec_sample
                log_x5sec_sample(fresh_cookies or cookie_str, x5sec_value, source="slider_solve")
            except Exception:
                pass
        try:
            from .ws_token import extract_m_h5_tk_from_cookie
            m_h5_tk = extract_m_h5_tk_from_cookie(fresh_cookies)
            encrypted_cookie = encrypt_cookie_for_storage(fresh_cookies)
            encrypted_token = encrypt_cookie_for_storage(m_h5_tk) if m_h5_tk else None
            async with async_session() as db:
                await db.execute(
                    text("""
                        UPDATE xianyu_account_auth
                        SET encrypted_cookie = :cookie,
                            encrypted_token = COALESCE(:token, encrypted_token),
                            updated_time = NOW()
                        WHERE account_id = :account_id AND tenant_id = :tenant_id
                          AND COALESCE(deleted, 0) = 0
                    """),
                    {
                        "cookie": encrypted_cookie,
                        "token": encrypted_token,
                        "account_id": account_id,
                        "tenant_id": tenant_id,
                    },
                )
                await db.commit()
            logger.info(
                "滑块求解成功，已更新数据库 Cookie accountId=%d cookieLen=%d hasToken=%s hasX5sec=%s",
                account_id, len(fresh_cookies), bool(m_h5_tk),
                "x5sec=" in fresh_cookies,
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="update_captcha_fresh_cookies",
                tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
            )

    return {
        "success": solve_ok,
        "solved": bool(data.get("solved")),
        "captchaDetected": bool(data.get("captchaDetected")),
        "attempts": int(data.get("attempts") or 0),
        "errorCode": "" if solve_ok else "CAPTCHA_SOLVE_FAILED",
        "error": None if solve_ok else (crawler_error or "滑块验证未通过，请改用人工验证"),
        "screenshotPath": data.get("screenshotPath"),
        "durationMs": duration_ms,
        "cookies": fresh_cookies if solve_ok else None,
        # 每次尝试的明细（用于成功率统计），由 crawler-service 的 sliderSolver 采集
        "attemptsDetail": data.get("attemptsDetail") or [],
        # 2026-08-02 新增：标识是否为 x5sec 缓存命中（免滑块）
        # 用于 handle_captcha_for_account 中判断：缓存命中但 Token API 验证失败时清除失效缓存
        "cached": bool(data.get("cached")),
        # 2026-08-02 新增：代理来源标识（用于统计住址IP vs 服务器IP的求解成功率）
        # server_ip=服务器IP / residential_ip=住址IP / account_bound=账号绑定代理 / none=无代理
        "proxySource": data.get("proxySource") or "unknown",
        # 住址IP元数据（仅 residential_ip 时有值，便于日志审计）
        "residentialProxy": data.get("residentialProxy"),
    }


# ============================================================
# 4. 综合处理：检测 + 通知 + 自动求解
# ============================================================
async def _update_cookie_status_for_captcha(
    account_id: int,
    tenant_id: int,
    cookie_status: int,
    status_code: str,
    status_message: str,
) -> None:
    """滑块求解过程中同步更新 Cookie 状态（xianyu_account_auth + xianyu_account_runtime）。

    同时通过 SSE 广播 cookie_status_changed 事件，让前端账号列表实时刷新 Cookie 状态列。

    Args:
        cookie_status: 0=不可用/验证中, 1=可用
        status_code: last_login_status_code（VERIFYING/CAPTCHA_FAILED/SESSION_EXPIRED/OK）
        status_message: last_login_status_message
    """
    try:
        async with async_session() as db:
            # xianyu_account_auth：只更新 cookie 相关字段
            await db.execute(
                text(
                    "UPDATE xianyu_account_auth SET cookie_status = :cs, "
                    "last_login_status_code = :sc, last_login_status_message = :sm, "
                    "last_login_check_time = NOW(), updated_time = NOW() "
                    "WHERE account_id = :aid AND tenant_id = :tid"
                ),
                {
                    "cs": cookie_status,
                    "sc": status_code,
                    "sm": status_message,
                    "aid": account_id,
                    "tid": tenant_id,
                },
            )
            # xianyu_account_runtime：cookie_status=0 时联动置 ws_status=0、online_status=0
            # 关键修复：原先只更新 cookie_status，导致 Cookie 失效后 ws_status 仍为 1，
            # 前端显示"WS 已连接"但实际无法收消息（Cookie 都失效了，WS 必然连不上）。
            await db.execute(
                text(
                    "UPDATE xianyu_account_runtime SET cookie_status = :cs, "
                    "ws_status = CASE WHEN :cs = 0 THEN 0 ELSE ws_status END, "
                    "online_status = CASE WHEN :cs = 0 THEN 0 ELSE online_status END, "
                    "last_login_status_code = :sc, "
                    "last_login_status_message = :sm, "
                    "last_login_check_time = NOW(), updated_time = NOW() "
                    "WHERE account_id = :aid AND tenant_id = :tid"
                ),
                {
                    "cs": cookie_status,
                    "sc": status_code,
                    "sm": status_message,
                    "aid": account_id,
                    "tid": tenant_id,
                },
            )
            await db.commit()
    except Exception as e:
        log_service_failure(
            logger, e, operation="update_cookie_status_for_captcha",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )

    # 通过 SSE 广播 cookie_status_changed 事件，前端账号列表实时刷新 Cookie 状态列
    try:
        from .ws_sse import broadcaster
        await broadcaster.broadcast(tenant_id, "cookie_status_changed", {
            "accountId": account_id,
            "tenantId": tenant_id,
            "cookieStatus": cookie_status,
            "loginStatusCode": status_code,
            "loginStatusMessage": status_message,
        })
        logger.info(
            "SSE 已广播 cookie_status_changed（滑块求解）: accountId=%d, status=%d, code=%s",
            account_id, cookie_status, status_code,
        )
    except Exception as sse_err:
        log_service_failure(
            logger, sse_err, operation="broadcast_captcha_cookie_status",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )


async def _verify_cookie_via_token_api(account_id: int, tenant_id: int) -> tuple[bool, str]:
    """滑块求解成功后，调用 Token API 二次验证 Cookie 是否真正可用。

    2026-08-03 根因修复：用户质疑"滑块成功但cookie失效"的逻辑矛盾。
    核心逻辑：滑块拖动通过 = Cookie 一定有效（Cookie 失效无法登录看到滑块）。
    Token API 返回 captcha（Baxia 风控）≠ Cookie 失效，只是 Token API 调用本身
    被 Baxia 二次风控了。原先把 captcha 也当作 Cookie 失效，导致大量误判。

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID

    Returns:
        (is_valid, error_type) 二元组：
        - (True, None): Token API 验证通过，Cookie 确实可用
        - (True, "captcha"): Token API 被 Baxia 风控（captcha），但滑块已通过
                             说明 Cookie 仍有效，只是 Token API 触发了二次风控
        - (False, "expired"): Cookie 真的过期了（极少见，滑块通过说明 Cookie 有效）
        - (False, "unknown"): 其他未知错误
    """
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT encrypted_cookie, encrypted_token "
                    "FROM xianyu_account_auth "
                    "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
        if not row:
            logger.warning("_verify_cookie_via_token_api: 账号不存在 accountId=%d", account_id)
            return False, "unknown"

        cookie_str = decrypt_cookie_if_needed(row["encrypted_cookie"])
        if not cookie_str:
            logger.warning("_verify_cookie_via_token_api: Cookie 为空 accountId=%d", account_id)
            return False, "unknown"

        m_h5_tk = None
        if row["encrypted_token"]:
            m_h5_tk = decrypt_cookie_if_needed(row["encrypted_token"])

        # 调用 ws_token 模块的完整 Token 获取流程
        # （会自动尝试 cookie 中的 _m_h5_tk、DB 中的 _m_h5_tk、刷新 _m_h5_tk 三种路径）
        from .ws_token import get_ws_token_with_refreshed_m_h5_tk
        # 重试机制（最多 3 次，间隔 3 秒）
        # 场景：滑块刚通过时，闲鱼服务端 Baxia 风控状态可能还没更新，
        # Token API 暂时返回 captcha，但这不是 Cookie 失效。
        # 等待几秒后重试可能通过（Baxia 风控状态恢复）。
        max_verify_retries = 3
        last_error_type = None
        captcha_count = 0
        expired_count = 0
        for attempt in range(1, max_verify_retries + 1):
            access_token, _, error_type, _ = await asyncio.to_thread(
                get_ws_token_with_refreshed_m_h5_tk, cookie_str, m_h5_tk
            )
            if access_token:
                logger.info(
                    "_verify_cookie_via_token_api: Cookie 验证通过 accountId=%d, accessToken长度=%d, attempt=%d/%d",
                    account_id, len(access_token), attempt, max_verify_retries,
                )
                return True, None
            last_error_type = error_type
            # 统计 error_type 分布，用于最终判定
            if error_type == "captcha":
                captcha_count += 1
            elif error_type == "expired":
                expired_count += 1
            logger.warning(
                "_verify_cookie_via_token_api: Cookie 验证失败 accountId=%d, error_type=%s, attempt=%d/%d",
                account_id, error_type, attempt, max_verify_retries,
            )
            if attempt < max_verify_retries:
                await asyncio.sleep(3)  # 等待 3 秒让 Baxia 风控状态更新

        # 2026-08-03 根因修复：根据 error_type 分布判定 Cookie 有效性
        # 用户逻辑：滑块拖动通过 = Cookie 一定有效（用户质疑的核心）
        # - 全部是 captcha（Baxia 风控）→ Cookie 仍有效，只是 Token API 被风控
        # - 全部是 expired → Cookie 真的过期（极少见，理论上滑块通过就不会 expired）
        # - 混合或未知 → 保守起见视为有效（滑块通过的先验概率更高）
        if expired_count > 0 and captcha_count == 0:
            # 全部是 expired，Cookie 真的过期
            logger.warning(
                "_verify_cookie_via_token_api: Cookie 真正过期 accountId=%d (expired=%d, captcha=%d)",
                account_id, expired_count, captcha_count,
            )
            return False, "expired"
        else:
            # captcha 占多数或混合 → Cookie 仍有效（滑块已通过）
            # 这是最关键的修复：不再把 captcha 误判为 cookie_invalid
            logger.info(
                "_verify_cookie_via_token_api: Token API 被 Baxia 风控（captcha），"
                "但滑块已通过，Cookie 视为有效 accountId=%d (expired=%d, captcha=%d, last_error=%s)",
                account_id, expired_count, captcha_count, last_error_type,
            )
            return True, "captcha"
    except Exception as e:
        log_service_failure(
            logger, e, operation="verify_captcha_cookie",
            tenant_id=tenant_id, account_id=account_id,
        )
        return False, "unknown"


# ============================================================
# 浏览器启动/崩溃错误识别
# ============================================================
# 这类错误表明 crawler-service 资源耗尽或 Chrome 进程异常，
# 不是滑块求解本身的问题，应归类为 service_unavailable（不可重试），
# 避免 slider_fail 重试 3 次放大记录数。
# 匹配 sliderSolver.ts catch 块返回的原始异常消息。
_BROWSER_LAUNCH_FAILURE_PATTERNS = (
    # 2026-08-01 修复：大幅缩小模式范围，只保留真正的浏览器启动失败/资源耗尽错误。
    # 原先包含 "page.waitForTimeout"、"Browser logs:"、"has been closed" 等过于宽泛的模式，
    # 导致 Playwright 超时、Python fallback 失败等 slider_fail 被误判为浏览器崩溃，
    # 从而 skip_backoff=True，fail_count 不累加，冷却机制完全失效。
    # 账号86因此被反复触发 3000+ 次仍处于 fail_count=1 的 10 分钟冷却。
    "spawn /opt/google/chrome/chrome",    # Chrome 二进制 spawn 失败
    "spawn EAGAIN",                       # 资源不足无法 spawn
    "pthread_create",                     # 线程创建失败（资源耗尽）
    "Failed to start BrowserThread",      # Chrome BrowserThread 启动失败
    "Failed to start",                    # Chrome 启动失败通用错误
    "Page crashed",                       # Chrome 页面崩溃（内存/资源不足导致 tab 进程死亡）
    "browser_crashed",                    # Playwright browser_crashed 事件
    "ERR_INSUFFICIENT_RESOURCES",         # Chrome 资源不足
    "Navigation failed because",          # 导航失败（浏览器崩溃/资源不足）
)


def _is_browser_launch_failure(error_msg: str) -> bool:
    """判断错误消息是否为浏览器启动失败/崩溃/资源耗尽类错误。

    Args:
        error_msg: sliderSolver 返回的原始错误消息

    Returns:
        True 表示这是浏览器层面错误（应归类为 service_unavailable 不可重试），
        False 表示可能是滑块求解本身失败（保持 slider_fail 可重试）
    """
    if not error_msg:
        return False
    msg_lower = error_msg.lower() if isinstance(error_msg, str) else str(error_msg).lower()
    return any(pattern.lower() in msg_lower for pattern in _BROWSER_LAUNCH_FAILURE_PATTERNS)


async def handle_captcha_for_account(
    account_id: int,
    tenant_id: int,
    response: dict | str | None = None,
    auto_solve: bool = False,
    trigger_scene: str = "manual",
    open_reason: str = "",
    solve_reason: str = "",
    record_id: Optional[int] = None,
    priority: int = 0,
) -> dict:
    """综合处理账号的滑块验证场景。

    1. 如果提供了 response，先检测是否真的需要滑块
    2. 如果检测到，写入 cookie_status=0 并通知用户
    3. 如果 auto_solve=True，先进行三重预校验（Cookie/活跃度/账号状态）
    4. 预校验通过后尝试自动求解
    5. 自动求解成功后，刷新 token 并恢复 cookie_status

    Args:
        trigger_scene: 触发场景 (ws_connect/cookie_keepalive/token_refresh/manual)，
                       用于写入求解记录和 SSE 广播
        open_reason: 开启原因（为什么打开滑块求解流程）
        solve_reason: 求解原因（为什么进行滑块求解，具体业务原因）
        record_id: 已有的求解记录 ID（由队列管理器创建时传入，复用记录避免重复创建）
        priority: 优先级（2=SVIP, 1=VIP, 0=普通，写入记录）

    Returns:
        {
            "detected": bool,
            "captchaUrl": Optional[str],
            "instructions": dict,
            "autoSolveResult": Optional[dict],
            "recovered": bool,  # 是否成功恢复
            "failureReason": str,  # 失败原因分类（空字符串表示成功）
        }
    """
    from .notify_dispatcher import notify_captcha_required
    from .captcha_solve_record import (
        create_solve_record, update_solve_record, broadcast_captcha_solve,
        _lookup_account_name, batch_insert_solve_attempts,
    )
    from .captcha_precheck import (
        precheck_cookie_status, precheck_account_active,
    )

    detected = False
    captcha_url = None
    if response is not None:
        result = detect_captcha_from_response(response)
        detected = result.detected
        captcha_url = result.captcha_url

    instructions = build_captcha_instructions(account_id, captcha_url)
    auto_solve_result = None
    recovered = False
    solve_record_id = record_id
    failure_reason = ""

    if detected or auto_solve:
        # 通知用户
        try:
            await notify_captcha_required(
                tenant_id, account_id,
                scene=f"账号触发滑块验证（自动求解={'开启' if auto_solve else '关闭'}）",
            )
        except Exception as exc:
            log_service_failure(
                logger, exc, operation="notify_captcha_required",
                tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
            )

    if auto_solve and (detected or response is None):
        logger.info("开始为账号 %d 自动求解滑块 (scene=%s)", account_id, trigger_scene)
        account_name = await _lookup_account_name(tenant_id, account_id)

        # === 三重预校验：账号活跃度 + 账号状态 + Cookie 状态 ===
        # 预校验失败时不启动浏览器，避免浪费资源，直接落库失败记录

        # 1. 账号活跃度与状态检查（先检查，避免对不活跃账号调用 hasLogin API）
        active_pass, active_reason, active_msg = await precheck_account_active(account_id, tenant_id)
        if not active_pass:
            failure_reason = active_reason
            logger.info("滑块求解预校验拒绝（活跃度）accountId=%d reason=%s", account_id, failure_reason)
            # 创建或复用记录
            if not solve_record_id:
                solve_record_id = await create_solve_record(
                    account_id, tenant_id, trigger_scene=trigger_scene,
                    open_reason=open_reason or "预校验拒绝",
                    solve_reason=solve_reason or active_msg,
                )
            if solve_record_id:
                await update_solve_record(
                    solve_record_id, status="precheck_rejected", result="precheck_fail",
                    error_message=active_msg,
                    engine="Precheck",
                )
                # 更新 failure_reason 和 priority
                try:
                    async with async_session() as db:
                        await db.execute(
                            text(
                                "UPDATE xianyu_captcha_solve_record "
                                "SET failure_reason = :fr, priority = :pri, finished_at = NOW() "
                                "WHERE id = :rid"
                            ),
                            {"fr": failure_reason, "pri": priority, "rid": solve_record_id},
                        )
                        await db.commit()
                except Exception as e:
                    log_service_failure(logger, e, operation="update_precheck_record", level=logging.WARNING)
                await broadcast_captcha_solve(
                    tenant_id, account_id, account_name,
                    status="precheck_rejected", result="precheck_fail",
                    reason=active_msg,
                    record_id=solve_record_id,
                )
            return {
                "detected": detected,
                "captchaUrl": captcha_url,
                "instructions": {
                    "title": instructions.title,
                    "steps": instructions.steps,
                    "message": instructions.message,
                    "autoSolveAvailable": instructions.auto_solve_available,
                    "manualFallbackUrl": instructions.manual_fallback_url,
                },
                "autoSolveResult": {
                    "success": False,
                    "solved": False,
                    "captchaDetected": False,
                    "attempts": 0,
                    "errorCode": "PRECHECK_REJECTED",
                    "error": active_msg,
                    "durationMs": 0,
                },
                "recovered": False,
                "failureReason": failure_reason,
            }

        # 2. Cookie 状态预校验（调用 hasLogin API）
        cookie_pass, cookie_reason, cookie_msg = await precheck_cookie_status(account_id, tenant_id)
        if not cookie_pass:
            failure_reason = cookie_reason
            logger.info("滑块求解预校验拒绝（Cookie）accountId=%d reason=%s", account_id, failure_reason)
            # Cookie 失效时更新数据库状态
            if failure_reason == "cookie_invalid":
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=0,
                    status_code="SESSION_EXPIRED",
                    status_message=cookie_msg,
                )
                # 主动断开 WS 连接
                try:
                    from .ws_client import ws_manager
                    await ws_manager.stop_client(account_id)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="stop_ws_after_precheck",
                        tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                    )
            # 创建或复用记录
            if not solve_record_id:
                solve_record_id = await create_solve_record(
                    account_id, tenant_id, trigger_scene=trigger_scene,
                    open_reason=open_reason or "预校验拒绝",
                    solve_reason=solve_reason or cookie_msg,
                )
            if solve_record_id:
                await update_solve_record(
                    solve_record_id, status="precheck_rejected", result="precheck_fail",
                    error_message=cookie_msg,
                    engine="Precheck",
                )
                try:
                    async with async_session() as db:
                        await db.execute(
                            text(
                                "UPDATE xianyu_captcha_solve_record "
                                "SET failure_reason = :fr, priority = :pri, finished_at = NOW() "
                                "WHERE id = :rid"
                            ),
                            {"fr": failure_reason, "pri": priority, "rid": solve_record_id},
                        )
                        await db.commit()
                except Exception as e:
                    log_service_failure(logger, e, operation="update_precheck_record", level=logging.WARNING)
                await broadcast_captcha_solve(
                    tenant_id, account_id, account_name,
                    status="precheck_rejected", result="precheck_fail",
                    reason=cookie_msg,
                    record_id=solve_record_id,
                )
            return {
                "detected": detected,
                "captchaUrl": captcha_url,
                "instructions": {
                    "title": instructions.title,
                    "steps": instructions.steps,
                    "message": instructions.message,
                    "autoSolveAvailable": instructions.auto_solve_available,
                    "manualFallbackUrl": instructions.manual_fallback_url,
                },
                "autoSolveResult": {
                    "success": False,
                    "solved": False,
                    "captchaDetected": False,
                    "attempts": 0,
                    "errorCode": "PRECHECK_REJECTED",
                    "error": cookie_msg,
                    "durationMs": 0,
                },
                "recovered": False,
                "failureReason": failure_reason,
            }

        # === 预校验通过，开始实际求解 ===

        # 先查冷却：冷却中则直接落库失败记录，不启动浏览器
        # 手动触发场景（manual/manual_retry）跳过冷却，让用户能主动解除冷却并求解
        from .captcha_backoff import assert_auto_solve_allowed, record_solve_failure
        from .captcha_precheck import MANUAL_TRIGGER_SCENES
        skip_cooldown = trigger_scene in MANUAL_TRIGGER_SCENES
        blocked = await assert_auto_solve_allowed(account_id, tenant_id, force=skip_cooldown)
        if blocked:
            # 冷却拦截本质是预校验拒绝（不需要尝试求解），
            # 归类为 precheck_rejected（在 NON_RETRYABLE_REASONS 中，不会触发重试），
            # engine=Backoff 标识拦截来源，前端据此区分展示（而非误判为 Cookie 失效）。
            failure_reason = "precheck_rejected"
            backoff_msg = blocked.get("error") or "滑块求解冷却中"
            remaining_sec = int(blocked.get("remainingSec") or 0)
            err_detail = f"{backoff_msg}（剩余 {remaining_sec} 秒，failCount={blocked.get('failCount', 0)}）"
            if not solve_record_id:
                solve_record_id = await create_solve_record(
                    account_id, tenant_id, trigger_scene=trigger_scene,
                    open_reason=open_reason or "全自动冷却拦截",
                    solve_reason=solve_reason or err_detail,
                )
            # 注意：result 必须用 precheck_fail（与预校验失败一致），
            # status 用 precheck_rejected，engine=Backoff 标识退避拦截来源
            await update_solve_record(
                solve_record_id, status="precheck_rejected", result="precheck_fail",
                error_message=err_detail,
                engine="Backoff",
            )
            # 同步更新 failure_reason 字段（update_solve_record 不支持 failure_reason 参数）
            if solve_record_id:
                try:
                    async with async_session() as db:
                        await db.execute(
                            text(
                                "UPDATE xianyu_captcha_solve_record "
                                "SET failure_reason = :fr, finished_at = NOW() WHERE id = :rid"
                            ),
                            {"fr": failure_reason, "rid": solve_record_id},
                        )
                        await db.commit()
                except Exception as e:
                    log_service_failure(logger, e, operation="update_backoff_failure_reason", level=logging.WARNING)
            await broadcast_captcha_solve(
                tenant_id, account_id, account_name,
                status="precheck_rejected", result="precheck_fail",
                reason=err_detail,
                record_id=solve_record_id,
            )
            return {
                "detected": detected,
                "captchaUrl": captcha_url,
                "instructions": {
                    "title": instructions.title,
                    "steps": instructions.steps,
                    "message": instructions.message,
                    "autoSolveAvailable": instructions.auto_solve_available,
                    "manualFallbackUrl": instructions.manual_fallback_url,
                },
                "autoSolveResult": blocked,
                "recovered": False,
                "failureReason": failure_reason,
            }

        # 创建求解记录（如果队列未预创建）+ 广播"求解中"状态
        if not solve_record_id:
            solve_record_id = await create_solve_record(
                account_id, tenant_id, trigger_scene=trigger_scene,
                open_reason=open_reason, solve_reason=solve_reason,
            )
        # 更新记录的优先级
        if solve_record_id:
            try:
                async with async_session() as db:
                    await db.execute(
                        text(
                            "UPDATE xianyu_captcha_solve_record SET priority = :pri WHERE id = :rid"
                        ),
                        {"pri": priority, "rid": solve_record_id},
                    )
                    await db.commit()
            except Exception as e:
                log_service_failure(logger, e, operation="update_solve_priority", level=logging.WARNING)

        await broadcast_captcha_solve(
            tenant_id, account_id, account_name,
            status="retrying", reason=f"正在求解滑块（{trigger_scene}）",
            record_id=solve_record_id,
        )

        # 同步更新 Cookie 状态为"验证中"，让前端账号列表立即反映求解状态
        await _update_cookie_status_for_captcha(
            account_id, tenant_id,
            cookie_status=0,
            status_code="VERIFYING",
            status_message=f"正在自动求解滑块验证（{trigger_scene}）",
        )

        auto_solve_result = await try_auto_solve(account_id, tenant_id)

        # === 成功率统计：批量写入每次尝试的明细（用于后台成功率统计） ===
        # crawler-service 的 sliderSolver 已在 attemptsDetail 中采集每次 attempt 的方案/方法/策略/成功状态/耗时
        # 此处持久化到 xianyu_captcha_solve_attempt 表，供后台统计页面聚合查询
        # 失败不影响主流程，batch_insert_solve_attempts 内部已捕获异常
        attempts_detail_data = auto_solve_result.get("attemptsDetail") or []
        if attempts_detail_data and solve_record_id:
            try:
                inserted = await batch_insert_solve_attempts(
                    record_id=solve_record_id,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    attempts_detail=attempts_detail_data,
                )
                if inserted:
                    logger.info(
                        "已记录滑块求解尝试明细 recordId=%d count=%d accountId=%d",
                        solve_record_id, inserted, account_id,
                    )
            except Exception as e:
                log_service_failure(
                    logger, e, operation="persist_solve_attempts_detail",
                    tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                )
        elif solve_record_id and auto_solve_result.get("solved"):
            # 2026-08-05 修复：求解成功但 attemptsDetail 为空时，写入一条合成明细，
            # 确保成功率统计能覆盖此类"免滑块"成功记录。
            # 根因：sliderSolver 的"未检测到 Baxia 弹窗"分支返回 captchaDetected=false
            # 且 attemptsDetail=[]，导致 batch_insert_solve_attempts 因明细数据为空而跳过写入，
            # 后台成功率统计因此看不到这些成功记录。
            # 同理：x5sec 缓存命中（cached=true）时 attemptsDetail 也为空，也需要合成明细。
            try:
                is_x5sec_cached = bool(auto_solve_result.get("cached"))
                synthetic_detail = [{
                    "attemptNo": 1,
                    "solveScheme": "x5sec_cached" if is_x5sec_cached else "no_captcha",
                    "dragMethod": "none",
                    "speedStrategy": "none",
                    "durationMs": auto_solve_result.get("durationMs") or 0,
                    "success": True,
                    "errorMessage": "",
                }]
                inserted = await batch_insert_solve_attempts(
                    record_id=solve_record_id,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    attempts_detail=synthetic_detail,
                )
                if inserted:
                    logger.info(
                        "已记录'免滑块'成功尝试明细 recordId=%d accountId=%d scheme=%s durationMs=%s",
                        solve_record_id, account_id,
                        "x5sec_cached" if is_x5sec_cached else "no_captcha",
                        auto_solve_result.get("durationMs"),
                    )
            except Exception as e:
                log_service_failure(
                    logger, e, operation="persist_solve_attempts_no_captcha",
                    tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                )

        if auto_solve_result.get("solved"):
            logger.info("账号 %d 滑块自动求解成功", account_id)

            # === 关键二次验证：调用 Token API 确认 Cookie 真实可用 ===
            # 2026-08-03 根因修复：_verify_cookie_via_token_api 现在返回 (is_valid, error_type) 二元组
            # - (True, None): Token API 验证通过
            # - (True, "captcha"): Token API 被 Baxia 风控，但滑块已通过 → Cookie 仍有效
            # - (False, "expired"): Cookie 真过期（极少见）
            # - (False, "unknown"): 其他错误
            #
            # 用户逻辑（铁律）：滑块拖动通过 = Cookie 一定有效。
            # Cookie 失效无法登录看到滑块，更不可能拖动通过。
            # 所以 captcha（Baxia 风控）不应判定为 cookie_invalid。
            cookie_valid, verify_error_type = await _verify_cookie_via_token_api(account_id, tenant_id)
            if not cookie_valid:
                # 只有 verify_error_type == "expired" 才是真正的 Cookie 过期
                # 其他情况（unknown）保守起见也标记为 cookie_invalid，但记录详细 error_type
                failure_reason = "cookie_invalid"
                logger.warning(
                    "账号 %d 滑块求解器报告成功，但 Token API 验证 Cookie 不可用 "
                    "error_type=%s，Cookie Session 可能已真正过期，需要用户重新扫码登录",
                    account_id, verify_error_type,
                )

                # 2026-08-02 强化：如果本次求解是 x5sec 缓存命中（免滑块），
                # 但 Token API 验证失败，说明缓存的 x5sec 已失效，主动清除缓存。
                # 否则后续 WS 重连和滑块求解会继续用失效的 x5sec，导致无效循环。
                if auto_solve_result.get("cached"):
                    try:
                        from .x5sec_cache_client import evict_cached_x5sec
                        # 读取当前 DB 中的 cookie（可能是注入 x5sec 后的 cookie）来生成缓存 key
                        async with async_session() as db:
                            cred_row = (await db.execute(
                                text(
                                    "SELECT encrypted_cookie FROM xianyu_account_auth "
                                    "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                                ),
                                {"aid": account_id, "tid": tenant_id},
                            )).mappings().first()
                        if cred_row:
                            db_cookie = decrypt_cookie_if_needed(cred_row["encrypted_cookie"])
                            if db_cookie:
                                evict_cached_x5sec(db_cookie)
                                logger.info(
                                    "账号 %d x5sec 缓存命中但 Token API 验证失败，已清除失效的 x5sec 缓存",
                                    account_id,
                                )
                    except Exception as e:
                        log_service_failure(
                            logger, e, operation="evict_x5sec_on_verify_fail",
                            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                        )
                # 不恢复 cookie_status=1，保持 0 状态，并附带明确错误信息
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=0,
                    status_code="SESSION_EXPIRED",
                    status_message="Cookie Session 已过期，请重新扫码登录闲鱼账号",
                )

                # Cookie 已失效，主动断开 WS 连接
                try:
                    from .ws_client import ws_manager
                    await ws_manager.stop_client(account_id)
                    logger.info("Cookie 验证失败，已断开 WS 连接 accountId=%d", account_id)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="stop_captcha_ws_client",
                        tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                    )

                auto_solve_result["cookieVerified"] = False
                # 2026-08-03 修复：根据 verify_error_type 区分错误信息
                if verify_error_type == "expired":
                    err_msg_detail = "Cookie Session 已过期（expired），需重新扫码登录"
                    err_msg_user = (
                        "滑块已通过，但 Cookie Session 已真正过期（FAIL_SYS_SESSION_EXPIRED），"
                        "请前往账号管理页重新扫码登录闲鱼账号获取新 Cookie"
                    )
                else:
                    err_msg_detail = f"Token API 验证失败 error_type={verify_error_type}，需重新扫码登录"
                    err_msg_user = (
                        f"滑块已通过，但 Token API 验证 Cookie 不可用（{verify_error_type}），"
                        "请前往账号管理页重新扫码登录闲鱼账号获取新 Cookie"
                    )
                auto_solve_result["error"] = err_msg_user
                auto_solve_result["failureReason"] = failure_reason
                # 更新求解记录为失败 + 广播失败事件
                await update_solve_record(
                    solve_record_id, status="fail", result="slider_success",
                    error_message=err_msg_detail,
                    retry_count=int(auto_solve_result.get("attempts") or 0),
                    duration_ms=int(auto_solve_result.get("durationMs") or 0),
                    screenshot_path=str(auto_solve_result.get("screenshotPath") or ""),
                    engine="Playwright",
                )
                # 更新 failure_reason
                try:
                    async with async_session() as db:
                        await db.execute(
                            text(
                                "UPDATE xianyu_captcha_solve_record "
                                "SET failure_reason = :fr, finished_at = NOW() WHERE id = :rid"
                            ),
                            {"fr": failure_reason, "rid": solve_record_id},
                        )
                        await db.commit()
                except Exception as e:
                    log_service_failure(logger, e, operation="update_failure_reason", level=logging.WARNING)
                await broadcast_captcha_solve(
                    tenant_id, account_id, account_name,
                    status="fail", result="slider_success",
                    reason="滑块已通过但 Cookie Session 已过期，需重新扫码登录",
                    record_id=solve_record_id,
                )
            else:
                logger.info("账号 %d Cookie 二次验证通过，恢复 cookie_status=1", account_id)
                recovered = True

                # 清除账号状态通知去重标记
                try:
                    from .notify_dispatcher import clear_all_account_status_notifications
                    await clear_all_account_status_notifications(tenant_id, account_id)
                except Exception:
                    pass

                # 恢复 cookie_status=1
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=1,
                    status_code="OK",
                    status_message="滑块验证已通过（自动求解+Token API 二次验证）",
                )

                # 触发 _m_h5_tk 刷新
                try:
                    from .cookie_token_refresher import force_refresh_account
                    await force_refresh_account(account_id, tenant_id, "mh5tk")
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="refresh_captcha_account_token",
                        tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                    )

                # 关键修复：求解成功后强制重启 WS 客户端，确保使用新 Cookie 建立 WS 连接
                # 原先只刷新 m_h5_tk 但不重启 WS，若 WS 客户端处于 token_failed/closed 状态，
                # 重连循环仍在用旧 cookie，即使 cookie_status=1 也无法真正建立 WS 连接，
                # 导致前端显示"WS 状态已连接"但实际收不到新消息。
                # 现在主动重启 WS 客户端，让 _persist_ws_online() 在真正建立连接后才更新 ws_status=1。
                #
                # 2026-08-02 强化：求解成功后等待 WS 连接结果，只有 WS 连接成功才算求解成功。
                # 用户要求：只有 WS 连接才算是求解成功。
                # 等待 8 秒（足够 WS 完成 _refresh_token + connect + reg + sync），
                # 然后检查 ws_status，决定求解记录的最终状态。
                ws_connected = False
                try:
                    from .ws_client import ws_manager
                    from .ws_token import extract_m_h5_tk_from_cookie
                    # 读取最新 cookie 和 m_h5_tk（已被 force_refresh_account 更新到 DB）
                    async with async_session() as db:
                        cred_row = (await db.execute(
                            text(
                                "SELECT encrypted_cookie, encrypted_token "
                                "FROM xianyu_account_auth "
                                "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                            ),
                            {"aid": account_id, "tid": tenant_id},
                        )).mappings().first()
                    if cred_row:
                        fresh_cookie = decrypt_cookie_if_needed(cred_row["encrypted_cookie"])
                        fresh_token = decrypt_cookie_if_needed(cred_row["encrypted_token"]) if cred_row["encrypted_token"] else None
                        # 优先用 DB 中的 token，若为空则从 cookie 中提取
                        if not fresh_token:
                            fresh_token = extract_m_h5_tk_from_cookie(fresh_cookie)
                        # 从 cookie 字符串中提取 unb（与 ws_client.py 的 _ensure_cookie_has_mh5tk 同款逻辑）
                        unb_value = ""
                        if fresh_cookie:
                            import re as _re
                            _unb_match = _re.search(r'\bunb=([^;]+)', fresh_cookie)
                            if _unb_match:
                                unb_value = _unb_match.group(1)
                        if fresh_cookie and fresh_token and unb_value:
                            # 关键：先停止旧客户端，再启动新客户端（使用最新 cookie + token）
                            await ws_manager.stop_client(account_id)
                            await ws_manager.start_client(
                                account_id, tenant_id, fresh_cookie, fresh_token, unb_value
                            )
                            # 2026-08-03 优化：设置求解后重启时间戳
                            # 用于抑制 _auto_solve_captcha_after_failure 在 WS 重连期间重复触发求解
                            new_client = ws_manager.get_client(account_id)
                            if new_client is not None:
                                new_client._last_solve_restart_at = time.time()
                            logger.info(
                                "滑块求解成功后已强制重启 WS 客户端 accountId=%d cookieLen=%d tokenLen=%d "
                                "（已设置求解后抑制期 5 分钟）",
                                account_id, len(fresh_cookie), len(fresh_token),
                            )

                            # 2026-08-03 优化：等待 WS 连接结果，使用轮询代替固定 sleep
                            # WS 连接流程：_refresh_token(1-3s) + connect(≤10s) + reg(1-2s) + sync(1s) ≈ 3-15s
                            # 原先固定等待 8 秒，但 Token API 可能需要更长时间（尤其是 Baxia 风控恢复期）
                            # 现改为轮询：每 3 秒检查一次，最多等待 25 秒
                            # 25 秒是折中值：足够 WS 完成两轮 Token API 调用（60s 重试间隔内），
                            # 不会过度阻塞队列 worker（求解本身已耗时 30-120s，多等 17s 影响有限）
                            ws_wait_max_seconds = 25
                            ws_poll_interval = 3
                            logger.info(
                                "等待 WS 连接结果 accountId=%d maxWait=%ds pollInterval=%ds",
                                account_id, ws_wait_max_seconds, ws_poll_interval,
                            )
                            ws_elapsed = 0
                            while ws_elapsed < ws_wait_max_seconds:
                                await asyncio.sleep(ws_poll_interval)
                                ws_elapsed += ws_poll_interval
                                client = ws_manager.get_client(account_id)
                                if client and client.is_connected:
                                    ws_connected = True
                                    logger.info(
                                        "滑块求解成功且 WS 已连接 accountId=%d phase=%s elapsed=%ds",
                                        account_id, getattr(client, "phase", "unknown"), ws_elapsed,
                                    )
                                    break
                                # 检查是否处于 token_failed 状态（Token API 返回 captcha）
                                # 如果是，提前退出等待，避免无意义地等满 25 秒
                                client_phase = getattr(client, "phase", "unknown") if client else "no_client"
                                if client_phase == "token_failed":
                                    logger.warning(
                                        "滑块求解成功但 WS 进入 token_failed 状态，提前结束等待 "
                                        "accountId=%d elapsed=%ds — Token API 被 Baxia 二次风控",
                                        account_id, ws_elapsed,
                                    )
                                    break

                            # 最终检查 WS 连接状态
                            if not ws_connected:
                                client = ws_manager.get_client(account_id)
                                client_phase = getattr(client, "phase", "unknown") if client else "no_client"
                                client_error = getattr(client, "last_error", "") if client else ""
                                logger.warning(
                                    "滑块求解成功但 WS 未连接 accountId=%d phase=%s error=%s elapsed=%ds",
                                    account_id, client_phase, client_error[:100], ws_elapsed,
                                )
                        else:
                            logger.warning(
                                "滑块求解成功但缺少 WS 重启所需凭据 accountId=%d hasCookie=%s hasToken=%s hasUnb=%s",
                                account_id, bool(fresh_cookie), bool(fresh_token), bool(unb_value),
                            )
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="restart_ws_after_captcha_solve",
                        tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                    )

                # 2026-08-02 强化：根据 WS 连接结果决定求解记录的最终状态
                # 用户要求：只有 WS 连接才算是求解成功
                solve_duration_ms = int(auto_solve_result.get("durationMs") or 0)
                if ws_connected:
                    # WS 连接成功，求解记录标记为 success
                    await update_solve_record(
                        solve_record_id, status="success", result="slider_success",
                        retry_count=int(auto_solve_result.get("attempts") or 0),
                        engine="Playwright",
                        error_message=(
                            f"[durationMs={solve_duration_ms}] 滑块求解成功，WS 已连接"
                        ),
                    )
                    # 更新 finished_at
                    try:
                        async with async_session() as db:
                            await db.execute(
                                text(
                                    "UPDATE xianyu_captcha_solve_record "
                                    "SET finished_at = NOW() WHERE id = :rid"
                                ),
                                {"rid": solve_record_id},
                            )
                            await db.commit()
                    except Exception as e:
                        log_service_failure(logger, e, operation="update_finished_at", level=logging.WARNING)
                    await broadcast_captcha_solve(
                        tenant_id, account_id, account_name,
                        status="success", result="slider_success",
                        reason="滑块求解成功，WS 已连接",
                        record_id=solve_record_id,
                    )
                else:
                    # 2026-08-03 重大修复：WS 连接失败时标记为 fail，不再标记为 success
                    # 原先标记为 success 导致冷却被重置（record_solve_success 已在 solve_captcha 中调用），
                    # ws_health_check 5 分钟后再次触发求解，形成"求解→WS未连→待确认→5分钟→再求解"循环。
                    # 用户要求："只有连接成功，才算成功"
                    # 修复：标记为 fail + 调用 record_solve_failure 重新武装 60 秒冷却，
                    # 阻止 ws_health_check 和 token_refresh 在短时间内重复触发求解。
                    # Cookie 已恢复（cookie_status=1），WS 会在 _connect_loop 中继续重试。
                    await record_solve_failure(
                        account_id, tenant_id,
                        error=f"滑块求解成功但 WS 连接失败（8 秒内未建立连接），"
                              f"phase={getattr(client, 'phase', 'unknown') if client else 'no_client'}",
                        failure_reason="ws_connect_failed",
                    )
                    await update_solve_record(
                        solve_record_id, status="fail", result="slider_success",
                        retry_count=int(auto_solve_result.get("attempts") or 0),
                        engine="Playwright",
                        error_message=(
                            f"[durationMs={solve_duration_ms}] 滑块求解成功，Cookie 已恢复，"
                            f"但 WS 连接失败（将在 _connect_loop 中继续重试）"
                        ),
                    )
                    # 更新 failure_reason + finished_at
                    try:
                        async with async_session() as db:
                            await db.execute(
                                text(
                                    "UPDATE xianyu_captcha_solve_record "
                                    "SET failure_reason = 'ws_connect_failed', finished_at = NOW() "
                                    "WHERE id = :rid"
                                ),
                                {"rid": solve_record_id},
                            )
                            await db.commit()
                    except Exception as e:
                        log_service_failure(logger, e, operation="update_failure_reason", level=logging.WARNING)
                    await broadcast_captcha_solve(
                        tenant_id, account_id, account_name,
                        status="fail", result="slider_success",
                        reason="滑块求解成功但 WS 连接失败，将在重连周期继续尝试",
                        record_id=solve_record_id,
                    )
                    logger.warning(
                        "滑块求解成功但 WS 连接失败，已标记为 fail 并武装 60 秒冷却 "
                        "accountId=%d phase=%s — 阻止 ws_health_check 短时间内重复触发求解",
                        account_id,
                        getattr(client, "phase", "unknown") if client else "no_client",
                    )
        else:
            # 滑块求解失败
            failure_reason = "slider_fail"
            logger.warning("账号 %d 滑块自动求解失败", account_id)
            error_msg = auto_solve_result.get("error") or "滑块验证未通过"
            error_code = auto_solve_result.get("errorCode") or ""

            # 根据错误码/错误消息细分失败原因
            if error_code == "CAPTCHA_SOLVER_TIMEOUT":
                # HTTP 超时（httpx ReadTimeout/ConnectTimeout/PoolTimeout）
                # 2026-07-29 事故修复：原先超时被归为 service_unavailable（不可重试 + 累加退避），
                # 导致 crawler-service 临时繁忙时账号被冷却 60s，WS 每次重连触发求解都被拦截。
                # 修复：归为 timeout（可重试 1 次 + 不累加退避），让队列自动重试一次。
                # 注意：httpx 超时 180s 是项目硬约束，不得缩短（见 project_memory.md）。
                failure_reason = "timeout"
                logger.warning(
                    "账号 %d 滑块求解失败：HTTP 超时，归类为 timeout（可重试1次，不累加退避）error=%s",
                    account_id, error_msg[:200],
                )
            elif error_code == "CAPTCHA_SOLVER_UNAVAILABLE":
                failure_reason = "service_unavailable"
            elif "Cookie Session" in error_msg or "Cookie 已过期" in error_msg or "FAIL_SYS_SESSION_EXPIRED" in error_msg:
                # 2026-08-01 修正：cookie_invalid 判定收紧。
                # 原先 "Cookie" in error_msg 过于宽泛，sliderSolver.ts 返回的错误消息
                # 可能含 "cookie" 字样但实际不是 Cookie 失效（如 "清除 risk cookies" 等日志）。
                # 现在仅匹配明确的 Cookie 失效信号：
                # - "Cookie Session"：Cookie Session 已过期
                # - "Cookie 已过期"：Cookie 已过期
                # - "FAIL_SYS_SESSION_EXPIRED"：淘宝 API 返回的 Session 过期错误码
                # 注意：login.token 不再作为 cookie_invalid 判定条件（详见 project_memory.md）。
                failure_reason = "cookie_invalid"
            elif _is_browser_launch_failure(error_msg):
                # Chrome 启动失败/浏览器崩溃/资源耗尽 → browser_crashed（可重试 1 次，不累加退避）
                # 原因：sliderSolver.ts 返回的这类错误无 errorCode，仅含 error 消息。
                # 演进历史：
                # - v1：归为 slider_fail（会重试 3 次），每次重试又立即失败，
                #   配合 WS 频繁重连导致记录数爆炸增长（曾出现单账号 13000+ 条失败记录）
                # - v2：归为 service_unavailable（不可重试 + 累加退避），避免无效重试放大问题
                # - v3（当前）：归为 browser_crashed（可重试 1 次 + 不累加退避）
                #   原因：浏览器崩溃是临时性资源问题，重试一次可能就成功。
                #   不累加退避避免账号被冷却 60s 导致 WS 重连触发求解被拦截。
                #   仅重试 1 次（而非 slider_fail 的 3 次）避免记录数爆炸。
                failure_reason = "browser_crashed"
                logger.warning(
                    "账号 %d 滑块求解失败：浏览器启动/崩溃错误，归类为 browser_crashed（可重试1次，不累加退避）error=%s",
                    account_id, error_msg[:200],
                )

            # Cookie 状态更新策略：
            # - cookie_invalid: Cookie 真失效，设 cookie_status=0
            # - service_unavailable / slider_fail: 滑块求解失败但 Cookie 可能仍有效
            #   （Chrome EARGIN/Playwright 错误/滑块识别失败等非 Cookie 原因），
            #   恢复 cookie_status=1，避免有效 Cookie 的账号被跳过保活和后续求解。
            #   预校验已通过 hasLogin 验证 Cookie 有效，求解失败不代表 Cookie 失效。
            if failure_reason == "cookie_invalid":
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=0,
                    status_code="SESSION_EXPIRED",
                    status_message=f"滑块求解失败（Cookie 失效）：{error_msg}",
                )
            else:
                # 恢复 cookie_status=1（求解失败但 Cookie 仍有效，避免误标记）
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=1,
                    status_code="OK",
                    status_message=f"滑块求解失败但 Cookie 仍有效（{failure_reason}），等待重试",
                )
            await update_solve_record(
                solve_record_id, status="fail", result="slider_fail",
                error_message=error_msg,
                retry_count=int(auto_solve_result.get("attempts") or 0),
                duration_ms=int(auto_solve_result.get("durationMs") or 0),
                screenshot_path=str(auto_solve_result.get("screenshotPath") or ""),
                engine="Playwright",
            )
            # 更新 failure_reason + finished_at
            try:
                async with async_session() as db:
                    await db.execute(
                        text(
                            "UPDATE xianyu_captcha_solve_record "
                            "SET failure_reason = :fr, finished_at = NOW() WHERE id = :rid"
                        ),
                        {"fr": failure_reason, "rid": solve_record_id},
                    )
                    await db.commit()
            except Exception as e:
                log_service_failure(logger, e, operation="update_failure_reason", level=logging.WARNING)
            await broadcast_captcha_solve(
                tenant_id, account_id, account_name,
                status="fail", result="slider_fail",
                reason=error_msg,
                record_id=solve_record_id,
            )

    # 2026-08-02 新增：记录代理来源到求解记录（用于统计住址IP vs 服务器IP的成功率）
    # proxy_source 由 crawler-service 返回，标识本次求解使用的代理类型
    # server_ip=服务器IP / residential_ip=住址IP / account_bound=账号绑定代理 / none/unknown=无代理
    # 2026-08-03 修复：添加 INFO 日志记录 proxySource 读取情况，便于排查 proxy_source 为空的问题
    proxy_source_value = (auto_solve_result.get("proxySource") or "unknown") if auto_solve_result else "unknown"
    logger.info(
        "proxy_source 写入检查 accountId=%d solveRecordId=%s proxySourceValue=%s autoSolveResultKeys=%s",
        account_id, solve_record_id, proxy_source_value,
        list(auto_solve_result.keys()) if auto_solve_result else "None",
    )
    # 2026-08-03 修复：即使 proxySource="unknown" 也写入数据库，便于统计哪些记录没有代理来源
    if solve_record_id and proxy_source_value:
        try:
            async with async_session() as db:
                await db.execute(
                    text(
                        "UPDATE xianyu_captcha_solve_record "
                        "SET proxy_source = :ps WHERE id = :rid AND COALESCE(proxy_source, '') = ''"
                    ),
                    {"ps": proxy_source_value, "rid": solve_record_id},
                )
                await db.commit()
                logger.info(
                    "proxy_source 已写入数据库 accountId=%d solveRecordId=%s proxySource=%s",
                    account_id, solve_record_id, proxy_source_value,
                )
        except Exception as e:
            log_service_failure(
                logger, e, operation="update_solve_record_proxy_source",
                tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
            )

    return {
        "detected": detected,
        "captchaUrl": captcha_url,
        "instructions": {
            "title": instructions.title,
            "steps": instructions.steps,
            "message": instructions.message,
            "autoSolveAvailable": instructions.auto_solve_available,
            "manualFallbackUrl": instructions.manual_fallback_url,
        },
        "autoSolveResult": auto_solve_result,
        "recovered": recovered,
        "failureReason": failure_reason,
    }
