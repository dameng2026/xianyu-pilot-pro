"""
自动发货模块全方位浏览器测试 v2
策略：API 登录获取 token + 注入 localStorage，跳过验证码等前端校验
覆盖：
1. 登录 user-web（API 方式）
2. 货源库列表加载、统计卡片
3. 新建文本发货货源（多条正文 + 文本/图片互斥）
4. 表单校验（异常场景）
5. 保存并验证列表刷新
6. 编辑货源验证 segments 回显
7. 检查控制台错误与网络请求
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

BASE_URL = "http://localhost:5174"
API_BASE = "http://localhost:5174/api"
SCREENSHOT_DIR = Path("g:/源码/xianyu-assistant-package-temp/tmp_test/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

console_errors: list[str] = []
network_failures: list[str] = []
api_errors: list[str] = []


def log(msg: str):
    print(f"[TEST] {msg}", flush=True)


async def shot(page: Page, name: str):
    path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    log(f"截图: {path.name}")


async def wait_idle(page: Page):
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


async def api_login(page: Page) -> dict:
    """通过浏览器内 fetch 调用登录 API，返回 token + username"""
    log("=== 步骤 1: API 登录 ===")
    result = await page.evaluate("""
        async () => {
            try {
                const resp = await fetch('/api/login/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: 'admin', password: '123456' })
                });
                const json = await resp.json();
                return { ok: resp.ok, status: resp.status, data: json };
            } catch (e) {
                return { ok: false, error: String(e) };
            }
        }
    """)
    log(f"登录响应: status={result.get('status')}, ok={result.get('ok')}")
    if not result.get("ok"):
        log(f"❌ 登录失败: {json.dumps(result, ensure_ascii=False)[:500]}")
        return {}

    data = result.get("data", {})
    # 兼容 {code, msg, data: {token}} 或 {data: {token}} 或 {token}
    token = None
    if isinstance(data, dict):
        # Result 包装：{code:0, data:{token}}
        inner = data.get("data") if "data" in data else data
        if isinstance(inner, dict):
            token = inner.get("token") or inner.get("accessToken")
        if not token:
            token = data.get("token") or data.get("accessToken")

    if not token:
        log(f"❌ 未获取到 token，响应结构: {json.dumps(data, ensure_ascii=False)[:500]}")
        return {}

    log(f"✅ 获取 token: {token[:20]}...")
    return {"token": token, "username": "admin"}


async def inject_auth(page: Page, auth: dict):
    """注入 token 到 localStorage"""
    await page.evaluate(f"""
        localStorage.setItem('xianyu_auth_token', '{auth["token"]}');
        localStorage.setItem('xianyu_username', '{auth["username"]}');
    """)
    log("已注入 token 到 localStorage")


async def step_navigate_to_source_library(page: Page):
    log("=== 步骤 2: 访问货源库页面 ===")
    # 使用 hash 路由直接访问
    await page.goto(f"{BASE_URL}/#/delivery-source-library", wait_until="domcontentloaded")
    await wait_idle(page)
    await page.wait_for_timeout(2000)
    await shot(page, "04_source_library")

    # 检查统计卡片
    stat_cards = page.locator('.stat-card, .m-dsl-stat-card')
    count = await stat_cards.count()
    log(f"统计卡片数量: {count}")

    # 检查货源列表
    source_rows = page.locator('.source-table-card tbody tr, .m-dsl-source-card')
    row_count = await source_rows.count()
    log(f"货源列表行数: {row_count}")

    # 检查是否有"新增货源"按钮
    create_btn = page.locator('button:has-text("新增货源"), button:has-text("新建")')
    btn_count = await create_btn.count()
    log(f"新增货源按钮数量: {btn_count}")

    await shot(page, "05_source_library_loaded")
    return btn_count > 0 or count > 0


async def step_create_text_source_with_segments(page: Page):
    log("=== 步骤 3: 新建文本发货货源（多条正文） ===")
    # 点击新增货源按钮
    create_btn = page.locator('button:has-text("新增货源"), button:has-text("新建")').first
    await create_btn.wait_for(timeout=10000)
    await create_btn.click()
    await page.wait_for_timeout(800)
    await shot(page, "06_create_form_open")

    # 填写标题（精确匹配，避免命中搜索框 "搜索标题 / 正文 / 备注"）
    title_input = page.locator('input.field-input[placeholder="给用户和 AI 模型看的标题"]').first
    await title_input.wait_for(timeout=5000)
    await title_input.fill("测试-多条正文自动发货")
    log("标题已填写")

    # 确认是文本发货模式
    text_mode_radio = page.locator('input[type="radio"][value="text"]').first
    if await text_mode_radio.count() > 0:
        is_checked = await text_mode_radio.is_checked()
        if not is_checked:
            await text_mode_radio.check()
            await page.wait_for_timeout(300)
        log(f"文本模式 radio 状态: checked={await text_mode_radio.is_checked()}")

    # 检查 segments editor 是否显示
    segments_editor = page.locator('.segments-editor').first
    await segments_editor.wait_for(timeout=5000)
    log("✅ segments editor 已显示")

    # 检查初始 segment 数量
    initial_segments = page.locator('.segment-card')
    initial_count = await initial_segments.count()
    log(f"初始 segment 数量: {initial_count}")
    assert initial_count >= 1, f"初始 segment 数量异常: {initial_count}"

    # 在第一条 segment 填写文本
    first_textarea = page.locator('.segment-card textarea').first
    await first_textarea.fill("第一条文本：感谢您的购买，商品说明如下...")
    log("第一条文本已填写")

    # 点击"增加一条对话"
    add_btn = page.locator('button:has-text("增加一条对话")').first
    await add_btn.click()
    await page.wait_for_timeout(300)
    second_count = await initial_segments.count()
    log(f"添加后 segment 数量: {second_count}")
    assert second_count == 2, f"添加 segment 失败，期望 2，实际 {second_count}"

    # 第二条切换为图片类型
    second_image_btn = page.locator('.segment-card').nth(1).locator('button:has-text("图片")').first
    await second_image_btn.click()
    await page.wait_for_timeout(300)
    await shot(page, "07_two_segments_mixed")

    # 验证切换后第二条显示图片上传区域
    second_image_area = page.locator('.segment-card').nth(1).locator('.segment-image-upload, .segment-image-area')
    img_area_count = await second_image_area.count()
    img_area_visible = False
    if img_area_count > 0:
        img_area_visible = await second_image_area.first.is_visible()
    log(f"第二条图片上传区域可见: {img_area_visible} (count={img_area_count})")

    # 再添加第三条文本
    await add_btn.click()
    await page.wait_for_timeout(300)
    third_count = await initial_segments.count()
    log(f"再添加后 segment 数量: {third_count}")

    third_textarea = page.locator('.segment-card').nth(2).locator('textarea').first
    await third_textarea.fill("第三条文本：如有问题请联系客服，欢迎五星好评！")
    await shot(page, "08_three_segments")
    return True


async def step_test_validation_image_without_url(page: Page):
    """测试场景 A：图片类型但未上传图片，应被校验拦截"""
    log("=== 步骤 4: 测试互斥校验（图片类型无图） ===")
    save_btn = page.locator('button:has-text("保存"), button:has-text("确定")').first
    if await save_btn.count() == 0:
        save_btn = page.locator('.source-editor-panel button:has-text("保存")').first

    await save_btn.click()
    await page.wait_for_timeout(800)
    await shot(page, "09_validation_image_without_url")

    # 检查错误提示
    error_msg = page.locator('.global-notice.error, [class*="error-message"]')
    error_count = await error_msg.count()
    log(f"错误提示数量: {error_count}")
    if error_count > 0:
        for i in range(min(error_count, 3)):
            txt = await error_msg.nth(i).text_content()
            log(f"  错误提示[{i}]: {txt}")

    # 还应该能找到 segments editor（说明保存被拦截）
    editor_still_visible = await page.locator('.segments-editor').first.is_visible()
    log(f"编辑器仍可见（保存被拦截）: {editor_still_visible}")
    return editor_still_visible


async def step_upload_image_to_second_segment(page: Page):
    """为第二条 segment 上传测试图片"""
    log("=== 步骤 5: 上传图片到第二条 segment ===")
    test_image_path = Path("g:/源码/xianyu-assistant-package-temp/tmp_test/test_image.png")
    if not test_image_path.exists():
        # 生成最小 PNG
        import struct, zlib
        def create_minimal_png(path):
            width, height = 100, 100
            def chunk(chunk_type, data):
                c = chunk_type + data
                return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
            raw = b''
            for y in range(height):
                raw += b'\x00' + b'\x00\x66\xff' * width
            png = b'\x89PNG\r\n\x1a\n'
            png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            png += chunk(b'IDAT', zlib.compress(raw))
            png += chunk(b'IEND', b'')
            with open(path, 'wb') as f:
                f.write(png)
        create_minimal_png(test_image_path)
        log(f"测试图片已生成: {test_image_path}")

    second_segment = page.locator('.segment-card').nth(1)
    file_input = second_segment.locator('input[type="file"]').first
    await file_input.set_input_files(str(test_image_path))
    log("已选择测试图片")

    # 等待上传完成（最多 8 秒）
    for i in range(16):
        await page.wait_for_timeout(500)
        preview = second_segment.locator('.segment-image-preview')
        if await preview.count() > 0:
            log(f"✅ 图片上传成功，预览已显示（耗时 {(i+1)*0.5}s）")
            await shot(page, "10_image_uploaded")
            return True
        # 检查是否还在上传中
        uploading = second_segment.locator('button:has-text("上传中")')
        if await uploading.count() > 0:
            continue

    log("❌ 图片上传超时（8s），预览未显示")
    await shot(page, "10_image_upload_timeout")
    return False


async def step_save_source(page: Page):
    log("=== 步骤 6: 保存货源 ===")
    save_btn = page.locator('button:has-text("保存"), button:has-text("确定")').first
    await save_btn.click()
    await page.wait_for_timeout(2500)
    await shot(page, "11_after_save")

    # 检查成功提示
    success_msg = page.locator('.global-notice.success')
    success_count = await success_msg.count()
    log(f"成功提示数量: {success_count}")
    if success_count > 0:
        txt = await success_msg.first.text_content()
        log(f"  成功提示: {txt}")

    # 检查是否还在编辑状态
    editor_still_open = await page.locator('.source-editor-panel').count()
    log(f"编辑器仍打开: {editor_still_open > 0}")
    return success_count > 0


async def step_verify_in_list(page: Page):
    log("=== 步骤 7: 验证货源在列表中 ===")
    # 重新加载列表（强制刷新，避免 hash 路由 no-op）
    await page.goto(f"{BASE_URL}/#/dashboard", wait_until="domcontentloaded")
    await page.wait_for_timeout(500)
    await page.goto(f"{BASE_URL}/#/delivery-source-library", wait_until="domcontentloaded")
    await wait_idle(page)
    await page.wait_for_timeout(2500)

    # 清空搜索框（避免遗留关键词过滤）
    search_input = page.locator('.search-input, .m-dsl-search-input').first
    if await search_input.count() > 0:
        await search_input.fill('')
        await page.wait_for_timeout(300)
        # 触发刷新
        refresh_btn = page.locator('button:has-text("搜索"), .m-dsl-btn:has-text("搜索")').first
        if await refresh_btn.count() > 0:
            await refresh_btn.click()
            await page.wait_for_timeout(1500)

    await shot(page, "12_list_after_save")

    # 输出列表中实际显示的货源标题（帮助诊断）
    list_titles = page.locator('.source-table-card tbody tr .strong, .m-dsl-source-title')
    titles_count = await list_titles.count()
    log(f"列表中货源数量: {titles_count}")
    for i in range(min(titles_count, 10)):
        title = await list_titles.nth(i).text_content()
        log(f"  列表项[{i}]: {title!r}")

    test_source = page.locator('text="测试-多条正文自动发货"')
    found = await test_source.count()
    log(f"在列表中找到测试货源: {found > 0}")
    return found > 0


async def step_edit_and_verify_echo(page: Page):
    log("=== 步骤 8: 编辑货源验证 segments 回显 ===")
    edit_btn = page.locator('tr:has-text("测试-多条正文自动发货") button:has-text("编辑")').first
    if await edit_btn.count() == 0:
        # 点击行
        row = page.locator('tr:has-text("测试-多条正文自动发货")').first
        if await row.count() > 0:
            await row.click()
            await page.wait_for_timeout(800)
        edit_btn = page.locator('button:has-text("编辑")').first

    if await edit_btn.count() == 0:
        log("⚠ 未找到编辑按钮")
        return False

    await edit_btn.click()
    await page.wait_for_timeout(1500)
    await shot(page, "13_edit_form_open")

    # 验证 segments 回显
    segments = page.locator('.segment-card')
    seg_count = await segments.count()
    log(f"编辑时 segment 数量: {seg_count}")

    if seg_count >= 1:
        first_text = page.locator('.segment-card').nth(0).locator('textarea').first
        if await first_text.count() > 0:
            val = await first_text.input_value()
            log(f"  第一条文本回显: {val!r}")

    if seg_count >= 2:
        second = page.locator('.segment-card').nth(1)
        # 检查图片按钮是否激活
        second_image_active = await second.locator('button.segment-type-btn.active:has-text("图片")').count()
        second_preview = await second.locator('.segment-image-preview').count()
        log(f"  第二条图片类型激活: {second_image_active > 0}, 预览存在: {second_preview > 0}")

    if seg_count >= 3:
        third_text = page.locator('.segment-card').nth(2).locator('textarea').first
        if await third_text.count() > 0:
            val = await third_text.input_value()
            log(f"  第三条文本回显: {val!r}")

    return seg_count >= 2


async def step_test_delete_segment(page: Page):
    log("=== 步骤 9: 测试删除 segment ===")
    before_count = await page.locator('.segment-card').count()
    if before_count < 2:
        log(f"segment 数量不足（{before_count}），跳过删除测试")
        return False

    # 删除最后一条
    last_idx = before_count - 1
    last_remove = page.locator('.segment-card').nth(last_idx).locator('button:has-text("删除"), button.segment-remove-btn').first
    if await last_remove.count() == 0:
        log("⚠ 未找到删除按钮")
        return False

    await last_remove.click()
    await page.wait_for_timeout(500)
    after_count = await page.locator('.segment-card').count()
    log(f"删除前: {before_count}, 删除后: {after_count}")
    await shot(page, "14_after_delete_segment")
    return after_count == before_count - 1


async def step_test_switch_segment_type(page: Page):
    """测试切换 segment 类型时数据保留/清理"""
    log("=== 步骤 10: 测试切换 segment 类型 ===")
    # 把第一条从文本切到图片，再切回文本，检查 textarea 是否被清空
    first_segment = page.locator('.segment-card').first
    original_text = ""
    first_textarea = first_segment.locator('textarea').first
    if await first_textarea.count() > 0:
        original_text = await first_textarea.input_value()

    # 切到图片
    image_btn = first_segment.locator('button:has-text("图片")').first
    if await image_btn.count() > 0:
        await image_btn.click()
        await page.wait_for_timeout(300)
        # 应显示图片上传区域
        img_area = first_segment.locator('.segment-image-upload, .segment-image-area')
        img_area_count = await img_area.count()
        img_visible = await img_area.first.is_visible() if img_area_count > 0 else False
        log(f"切到图片后，图片上传区域可见: {img_visible}")

        # 切回文本
        text_btn = first_segment.locator('button:has-text("文本")').first
        if await text_btn.count() > 0:
            await text_btn.click()
            await page.wait_for_timeout(300)
            new_textarea = first_segment.locator('textarea').first
            if await new_textarea.count() > 0:
                new_text = await new_textarea.input_value()
                log(f"切回文本后，文本内容: {original_text!r} -> {new_text!r}")
                # 内容应被清空（互斥）
                if new_text == "":
                    log("✅ 切换类型后文本被清空（符合互斥预期）")
                else:
                    log("ℹ 切换类型后文本保留（可能符合设计）")
    await shot(page, "15_after_type_switch")
    return True


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )

        page = await context.new_page()
        page.on("console", lambda msg: (
            console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type in ("error", "warning") else None
        ))
        page.on("requestfailed", lambda req: network_failures.append(f"{req.method} {req.url} - {req.failure}"))

        test_results = {}
        try:
            # 先访问站点让 localStorage 可用
            await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
            await wait_idle(page)

            # API 登录
            auth = await api_login(page)
            if not auth:
                log("❌ 登录失败，终止测试")
                return
            await inject_auth(page, auth)

            # 重新访问页面（带 token）
            lib_loaded = await step_navigate_to_source_library(page)
            test_results["lib_loaded"] = lib_loaded
            if not lib_loaded:
                log("❌ 货源库未加载，终止后续测试")
                await shot(page, "99_lib_not_loaded")
                # 输出当前页面 HTML 片段帮助诊断
                html = await page.content()
                log(f"页面 HTML 长度: {len(html)}")
                log(f"页面 HTML 前 2000 字符: {html[:2000]}")
            else:
                test_results["create_form"] = await step_create_text_source_with_segments(page)
                test_results["validation_no_img"] = await step_test_validation_image_without_url(page)
                test_results["image_upload"] = await step_upload_image_to_second_segment(page)
                test_results["save"] = await step_save_source(page)
                test_results["in_list"] = await step_verify_in_list(page)
                test_results["edit_echo"] = await step_edit_and_verify_echo(page)
                test_results["delete_seg"] = await step_test_delete_segment(page)
                test_results["type_switch"] = await step_test_switch_segment_type(page)

        except Exception as e:
            log(f"❌ 测试异常: {type(e).__name__}: {e}")
            await shot(page, "99_error_state")
            import traceback
            traceback.print_exc()
        finally:
            # 控制台错误汇总
            log("\n" + "="*60)
            log("测试结果汇总")
            log("="*60)
            for k, v in test_results.items():
                status = "✅" if v else "❌"
                log(f"  {status} {k}: {v}")

            log("\n=== 控制台错误/警告（前 20 条）===")
            if console_errors:
                for err in console_errors[:20]:
                    log(f"  {err}")
            else:
                log("  无")

            log("\n=== 网络请求失败（前 10 条）===")
            if network_failures:
                for fail in network_failures[:10]:
                    log(f"  {fail}")
            else:
                log("  无")

            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
