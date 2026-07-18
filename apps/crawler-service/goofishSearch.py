"""
闲鱼商品关键词搜索（patchright + 真实 Chrome 反检测方案）

作为 Node crawler-service 的兜底搜索实现：当 Node Playwright 触发 Baxia 风控
（FAIL_SYS_USER_VALIDATE）时，由 Node 调用本脚本完成整个搜索流程。

为什么需要 Python 版本：
- Node Playwright 即使使用真实 Chrome channel + ignoreDefaultArgs=['--enable-automation']
  仍被 Baxia 识别为自动化，因为 CDP 协议痕迹（cdc_/__playwright__/Runtime.enable）无法清除。
- patchright 是 Playwright 的反检测分支，自动清理所有 CDP 痕迹，已验证不触发风控。

搜索场景的关键优化（与滑块求解场景的区别）：
- 不在首页预热导航（原 page.goto("https://www.goofish.com/") 耗时 1-5s 且可能触发风控）
- 不求解 Baxia 滑块（首页停留>5s 反而会触发更多风控）
- 直接 goto 搜索 URL，将关键词作为 query 参数：https://www.goofish.com/search?q={keyword}&page={n}
- 时间预算：goto 1-3s + 等 MTOP 响应 1-3s = 2-6s（远低于 Node 端 15s 超时）

CLI 协议（与 sliderSolve.py 一致）：
  --keyword      搜索关键词（必填）
  --page         页码（默认 1）
  --page-size    每页数量（默认 20）
  --cookie-file  Cookie 字符串文件路径（必填，Cookie 可能很长不走 CLI 参数）

输出：最后一行为 JSON 结果，供 Node 解析
  成功：{"ok": true, "items": [...], "total": N, "hasMore": bool, "searchMode": "python-patchright"}
  失败：{"ok": false, "error": "...", "items": []}
"""
import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Optional
from urllib.parse import quote

# 确保能 import 同目录下的 sliderSolve 模块
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# 复用 sliderSolve.py 的反检测基础设施（patchright 启动、Cookie 解析等）。
# 搜索场景不求解滑块，故不导入 detect_captcha_container / get_slider_info / human_like_drag / check_solved。
import sliderSolve  # noqa: E402
from sliderSolve import (  # noqa: E402
    async_playwright,
    _USING_PATCHRIGHT,
    STEALTH_INIT_SCRIPT,
    _ADVANCED_FINGERPRINT_SCRIPT,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    find_chrome_path,
    _resolve_profile_dir,
    prepare_profile_dir,
    parse_cookie_string,
    strip_risk_cookies,
    log,
)

# MTOP 搜索 API 标识，与 Node 端保持一致
SEARCH_API_MARKER = "mtop.taobao.idlemtopsearch.pc.search"

# 单次 MTOP 响应等待超时（秒），与 Node 端 6 秒一致。
# 搜索场景直接 goto 搜索 URL，patchright 反检测通常不触发风控，MTOP 响应 1-3s 内到达。
MTOP_WAIT_TIMEOUT = 6.0


def parse_mtop_search_response(json_obj: Any) -> list[dict]:
    """从 MTOP 搜索响应中提取商品列表（与 Node 端 parseMtopSearchResponse 逻辑一致）。

    响应结构：
      data.resultList[].data.item.main.exContent.{itemId,title,picUrl,price,userNickName,area}
      data.resultList[].data.item.main.clickParam.args.{price,item_id}
    """
    items: list[dict] = []
    if not isinstance(json_obj, dict):
        return items
    data = json_obj.get("data")
    if not isinstance(data, dict):
        return items
    result_list = data.get("resultList")
    if not isinstance(result_list, list):
        return items

    for entry in result_list:
        if not isinstance(entry, dict):
            continue
        entry_data = entry.get("data")
        if not isinstance(entry_data, dict):
            continue
        item = entry_data.get("item")
        if not isinstance(item, dict):
            continue
        main = item.get("main")
        if not isinstance(main, dict):
            continue
        ex = main.get("exContent")
        if not isinstance(ex, dict):
            continue
        click_param = main.get("clickParam")
        click_args = (click_param or {}).get("args") if isinstance(click_param, dict) else {}
        if not isinstance(click_args, dict):
            click_args = {}

        # itemId
        item_id = str(ex.get("itemId") or click_args.get("item_id") or click_args.get("id") or "").strip()

        # title
        title = str(ex.get("title") or "").strip()

        # picUrl
        pic_url = str(ex.get("picUrl") or "").strip()

        # price: 数组形式 [{text, type}, ...]，取 type="integer" 的 text
        price = ""
        price_val = ex.get("price")
        if isinstance(price_val, list):
            for p in price_val:
                if isinstance(p, dict) and p.get("type") == "integer" and p.get("text"):
                    price = str(p["text"]).strip()
                    break
            if not price:
                price = "".join(
                    str(p.get("text", "")) if isinstance(p, dict) else ""
                    for p in price_val
                ).strip()
        if not price and click_args.get("price"):
            price = str(click_args["price"]).strip()
        if not price and isinstance(price_val, str):
            price = price_val.strip()
        if not price and isinstance(price_val, (int, float)):
            price = str(price_val)

        # 卖家昵称
        user_nickname = str(ex.get("userNickName") or "").strip()

        # 地区
        area = str(ex.get("area") or "").strip()

        # itemUrl
        item_url = f"https://www.goofish.com/item?itemId={item_id}" if item_id else ""

        if item_id or title:
            items.append({
                "itemId": item_id,
                "title": title,
                "price": price,
                "imageUrl": pic_url,
                "itemUrl": item_url,
                "userNickName": user_nickname,
                "area": area,
            })

    return items


def parse_mtop_pagination(json_obj: Any) -> dict:
    """从 MTOP 响应中解析分页信息（与 Node 端 parseMtopPagination 一致）。"""
    if not isinstance(json_obj, dict):
        return {}
    data = json_obj.get("data")
    if not isinstance(data, dict):
        return {}
    page_info = data.get("pageInfo") if isinstance(data.get("pageInfo"), dict) else {}
    total_value = data.get("total", data.get("totalCount", data.get("totalMatchCount",
                 page_info.get("total", page_info.get("totalCount")))))
    has_more_value = data.get("hasMore", page_info.get("hasMore"))
    result = {}
    if isinstance(total_value, (int, float)) and total_value >= 0:
        result["total"] = int(total_value)
    if isinstance(has_more_value, bool):
        result["hasMore"] = has_more_value
    return result


def deduplicate_items(items: list[dict]) -> list[dict]:
    """按 itemId/itemUrl 去重（与 Node 端 deduplicateItems 一致）。"""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        if item.get("itemId"):
            key = f"id:{item['itemId']}"
        elif item.get("itemUrl"):
            key = f"url:{item['itemUrl']}"
        else:
            key = f"combo:{item.get('title','')}|{item.get('price','')}|{item.get('imageUrl','')}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def paginate(items: list[dict], page_size: int) -> list[dict]:
    """限制每页数量（与 Node 端 paginateCurrentCapturedPage 一致）。"""
    safe = max(1, min(page_size if isinstance(page_size, int) and page_size > 0 else 20, 50))
    return items[:safe]


async def search_with_patchright(
    keyword: str,
    page_num: int,
    page_size: int,
    cookie_str: str,
) -> dict:
    """使用 patchright + 真实 Chrome + 持久化 profile 执行搜索。

    流程（搜索场景不求解滑块，直接 goto 搜索 URL）：
    1. 启动 patchright（自动清理 CDP 痕迹）
    2. 注入 Cookie 保持登录态（在任何导航前完成，避免登录跳转）
    3. 监听 MTOP 搜索 API 响应
    4. 直接 goto 搜索 URL，patchright 反检测通常不触发风控
    5. 解析 MTOP 响应得到商品列表

    时间预算：goto 搜索页 1-3s + 等待 MTOP 响应 1-3s = 2-6s（远低于 Node 15s 超时）。
    """
    # URL-encode 关键词，避免空格/特殊字符破坏 URL（与 Node 端 encodeURIComponent 一致）
    encoded_keyword = quote(keyword.strip(), safe="")
    search_url = f"https://www.goofish.com/search?q={encoded_keyword}&page={page_num}"
    log(f"开始搜索: keyword={keyword}, page={page_num}, pageSize={page_size}, hasCookie={bool(cookie_str)}")

    chrome_path = find_chrome_path()
    if not chrome_path:
        return {"ok": False, "error": "未找到 Chrome 可执行文件", "items": []}

    # 使用持久化 profile（累积历史降低风控概率）
    user_data_dir = _resolve_profile_dir("persistent", cookie_str=cookie_str)
    log(f"profile_dir={user_data_dir}, chrome={chrome_path}, patchright={_USING_PATCHRIGHT}")

    async with async_playwright() as playwright:
        # === 启动浏览器（复用 sliderSolve.py 的 launch 模式） ===
        if _USING_PATCHRIGHT:
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                    "--lang=zh-CN",
                ],
            )
        else:
            # playwright 回退：保留原有反检测逻辑
            from sliderSolve import _chrome_stealth_args
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_default_args=["--enable-automation"],
                args=_chrome_stealth_args(),
            )

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

        try:
            # === 注入反检测脚本 ===
            # patchright 模式只注入高级指纹规避（CDP 痕迹由 patchright 自动清理）
            # playwright 模式注入完整 STEALTH_INIT_SCRIPT
            if _USING_PATCHRIGHT:
                await ctx.add_init_script(_ADVANCED_FINGERPRINT_SCRIPT)
                log("✓ patchright 模式：已注入高级指纹规避（WebGL/Canvas/Audio），CDP 痕迹由 patchright 自动清理")
            else:
                await ctx.add_init_script(STEALTH_INIT_SCRIPT)

            # === 注入 Cookie（在任何导航前完成） ===
            # 关键优化：不再预热首页（原 page.goto("https://www.goofish.com/") 耗时 1-5s 且可能触发登录跳转/风控）。
            # add_cookies 不需要先导航到目标域，只要 cookie 自带 domain 字段即可写入 cookie jar。
            # 搜索场景要求 5-10s 内完成，省去预热导航是关键提速点。
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            if cookie_str:
                # 清除风控相关 cookie（x5sectag/x5sec/tfstk 等），让服务器重新评估会话
                clean_cookie_str = strip_risk_cookies(cookie_str)
                cookies = parse_cookie_string(clean_cookie_str, ".goofish.com")
                cookies += parse_cookie_string(clean_cookie_str, "www.goofish.com")
                if cookies:
                    try:
                        await ctx.add_cookies(cookies)
                        log(f"已注入 {len(cookies)} 个 Cookie（导航前注入）")
                    except Exception as e:
                        log(f"注入 Cookie 失败: {e}")

            # === 执行搜索（不求解滑块，单次尝试） ===
            return await _do_search_with_retry(ctx, page, search_url, page_num, page_size, max_retries=0)

        finally:
            try:
                await ctx.close()
            except Exception:
                pass


async def _do_search_with_retry(
    ctx,
    page,
    search_url: str,
    page_num: int,
    page_size: int,
    max_retries: int = 0,
) -> dict:
    """执行搜索，单次尝试。搜索场景不求解滑块（首页停留>5s 会触发更多风控）。

    即便 MTOP 返回 FAIL_SYS_USER_VALIDATE + punish URL，也不再 goto punish URL 求解滑块，
    而是直接返回失败。Node 端会根据业务需要决定如何提示用户。
    保留 max_retries 参数仅为向后兼容，默认 0 表示单次尝试。
    """
    for attempt in range(max_retries + 1):
        # 设置 MTOP 响应监听
        mtop_event = asyncio.Event()
        mtop_result: dict[str, Any] = {}

        async def on_response(response):
            try:
                if mtop_event.is_set():
                    return
                req = response.request
                resource_type = req.resource_type
                if resource_type not in ("xhr", "fetch"):
                    return
                req_url = req.url or ""
                if SEARCH_API_MARKER not in req_url:
                    return
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type:
                    return

                try:
                    text = await response.text()
                except Exception:
                    return
                if not text or len(text) < 50 or len(text) > 2 * 1024 * 1024:
                    return

                try:
                    json_obj = json.loads(text)
                except Exception:
                    return

                # 检查 MTOP 状态
                ret = json_obj.get("ret")
                ret_msg = ""
                if isinstance(ret, list) and ret:
                    ret_msg = str(ret[0])
                elif ret is not None:
                    ret_msg = str(ret)

                if ret_msg and "SUCCESS" not in ret_msg:
                    # MTOP 返回非成功（如 Baxia 风控）。
                    # 搜索场景不求解滑块，仅记录 punishUrl 供日志诊断。
                    punish_url = None
                    if "FAIL_SYS_USER_VALIDATE" in ret_msg:
                        data_obj = json_obj.get("data")
                        if isinstance(data_obj, dict):
                            url_val = data_obj.get("url")
                            if isinstance(url_val, str) and "punish" in url_val:
                                punish_url = url_val
                    log(f"MTOP 搜索返回非成功: retMsg={ret_msg}"
                        f"{' (含 punish URL，搜索场景不求解滑块)' if punish_url else ''}")
                    mtop_result.clear()
                    mtop_result["ok"] = False
                    mtop_result["error"] = ret_msg
                    mtop_result["punishUrl"] = punish_url
                    mtop_event.set()
                    return

                # 成功响应
                parsed_items = parse_mtop_search_response(json_obj)
                pagination = parse_mtop_pagination(json_obj)
                if parsed_items:
                    mtop_result.clear()
                    mtop_result["ok"] = True
                    mtop_result["items"] = parsed_items
                    mtop_result["total"] = pagination.get("total")
                    mtop_result["hasMore"] = pagination.get("hasMore")
                    mtop_event.set()
                    log(f"MTOP API 拦截成功: 提取 {len(parsed_items)} 个商品")
                else:
                    log("MTOP API 响应解析到 0 个商品")
            except Exception as e:
                log(f"读取 MTOP 响应失败: {e}")

        page.on("response", on_response)

        try:
            # 跳转到搜索页（搜索场景直接 goto 搜索 URL，不在首页停留）
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                log(f"跳转搜索页失败: {e}")
                return {"ok": False, "error": f"跳转失败: {e}", "items": []}

            # 等待 MTOP 响应或超时
            try:
                await asyncio.wait_for(mtop_event.wait(), timeout=MTOP_WAIT_TIMEOUT)
            except asyncio.TimeoutError:
                log(f"等待 MTOP 响应超时 ({MTOP_WAIT_TIMEOUT}s)")
                mtop_result.clear()
                mtop_result["ok"] = False
                mtop_result["error"] = "timeout"
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

        # 若成功拿到商品，返回结果
        if mtop_result.get("ok") and mtop_result.get("items"):
            items = deduplicate_items(mtop_result["items"])
            paged_items = paginate(items, page_size)
            total = mtop_result.get("total")
            has_more = mtop_result.get("hasMore")
            if has_more is None:
                has_more = len(paged_items) > 0
            if total is None:
                total = (page_num - 1) * page_size + len(paged_items) + (1 if has_more else 0)
            log(f"搜索完成: 共 {len(items)} 个商品, 返回 {len(paged_items)} 个")
            return {
                "ok": True,
                "items": paged_items,
                "total": total,
                "hasMore": has_more,
                "searchMode": "python-patchright",
            }

        # 搜索场景不求解滑块：失败直接返回，由 Node 端决定如何处理。
        # 即便 punishUrl 存在也不再 goto punish URL（首页停留>5s 会触发更多风控）。
        return {
            "ok": False,
            "error": mtop_result.get("error", "no_items"),
            "items": [],
        }

    # 不应该到达这里
    return {"ok": False, "error": "max retries exceeded", "items": []}


def main() -> None:
    parser = argparse.ArgumentParser(description="闲鱼商品关键词搜索（patchright + 真实 Chrome）")
    parser.add_argument("--keyword", required=True, help="搜索关键词")
    parser.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    parser.add_argument("--page-size", type=int, default=20, help="每页数量（默认 20）")
    parser.add_argument("--cookie-file", required=True, help="Cookie 字符串文件路径")
    args = parser.parse_args()

    if not args.keyword.strip():
        result = {"ok": False, "error": "关键词不能为空", "items": []}
        print(json.dumps(result, ensure_ascii=False), flush=True)
        sys.exit(1)

    # 读取 Cookie 文件
    cookie_str = ""
    try:
        with open(args.cookie_file, "r", encoding="utf-8") as f:
            cookie_str = f.read().strip()
    except Exception as e:
        result = {"ok": False, "error": f"读取 Cookie 文件失败: {e}", "items": []}
        print(json.dumps(result, ensure_ascii=False), flush=True)
        sys.exit(1)

    try:
        result = asyncio.run(search_with_patchright(
            keyword=args.keyword,
            page_num=args.page,
            page_size=args.page_size,
            cookie_str=cookie_str,
        ))
    except Exception as e:
        log(f"搜索异常: {e}")
        result = {"ok": False, "error": f"搜索异常: {e}", "items": []}

    # 最后一行输出 JSON 结果（与 sliderSolve.py 协议一致）
    print(json.dumps(result, ensure_ascii=False), flush=True)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
