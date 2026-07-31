"""
移动端货源库全方位测试
使用移动端视口 + touch 事件
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, Page

BASE_URL = "http://localhost:5174"
SCREENSHOT_DIR = Path("g:/源码/xianyu-assistant-package-temp/tmp_test/screenshots/mobile")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

console_errors = []


def log(msg):
    print(f"[MOBILE-TEST] {msg}", flush=True)


async def shot(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    log(f"截图: {path.name}")


async def wait_idle(page):
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


async def main():
    async with async_playwright() as p:
        # iPhone 14 Pro 视口 + 触摸 + 移动端 UA
        iphone = p.devices["iPhone 14 Pro"]
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            **iphone,
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

        results = {}
        try:
            # 登录
            log("=== 移动端登录 ===")
            await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
            await wait_idle(page)

            auth = await page.evaluate("""
                async () => {
                    const resp = await fetch('/api/login/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: 'admin', password: '123456'})
                    });
                    const json = await resp.json();
                    const data = json.data || json;
                    const inner = data.data || data;
                    return {ok: resp.ok, token: inner.token || data.token};
                }
            """)
            if not auth.get("ok") or not auth.get("token"):
                log(f"❌ 登录失败: {auth}")
                return
            log(f"✅ 登录成功, token={auth['token'][:20]}...")

            await page.evaluate(f"""
                localStorage.setItem('xianyu_auth_token', '{auth["token"]}');
                localStorage.setItem('xianyu_username', 'admin');
            """)

            # 访问移动端货源库
            log("=== 访问移动端货源库 ===")
            await page.goto(f"{BASE_URL}/#/delivery-source-library", wait_until="domcontentloaded")
            await wait_idle(page)
            await page.wait_for_timeout(2000)
            await shot(page, "01_mobile_source_library")

            # 检查移动端货源卡片
            cards = page.locator('.m-dsl-source-card')
            card_count = await cards.count()
            log(f"移动端货源卡片数量: {card_count}")
            results["list_loaded"] = card_count > 0

            # 检查统计卡片
            stat_cards = page.locator('.m-dsl-stat-card')
            stat_count = await stat_cards.count()
            log(f"统计卡片数量: {stat_count}")

            # 检查新建按钮
            create_btn = page.locator('button:has-text("新建")').first
            create_btn_count = await create_btn.count()
            log(f"新建按钮数量: {create_btn_count}")

            if create_btn_count == 0:
                log("❌ 未找到新建按钮")
                await shot(page, "99_no_create_btn")
                return

            # 点击新建
            log("=== 点击新建 ===")
            await create_btn.click()
            await page.wait_for_timeout(1000)
            await shot(page, "02_mobile_create_form")

            # 填写标题（移动端 class 是 m-dsl-input）
            title_input = page.locator('input.m-dsl-input[placeholder="给用户和 AI 模型看的标题"]').first
            await title_input.wait_for(timeout=5000)
            await title_input.fill("移动端测试-多条正文")
            log("标题已填写")

            # 检查 segments
            segments = page.locator('.m-dsl-segment')
            initial_count = await segments.count()
            log(f"初始 segment 数量: {initial_count}")
            results["initial_segment"] = initial_count >= 1

            # 填写第一条文本
            first_textarea = page.locator('.m-dsl-segment textarea').first
            await first_textarea.fill("移动端第一条文本：感谢购买")
            log("第一条文本已填写")

            # 添加第二条
            add_btn = page.locator('button:has-text("增加一条对话")').first
            await add_btn.click()
            await page.wait_for_timeout(300)
            second_count = await segments.count()
            log(f"添加后 segment 数量: {second_count}")
            results["add_segment"] = second_count == 2

            # 第二条切图片
            second_image_btn = page.locator('.m-dsl-segment').nth(1).locator('button:has-text("图片")').first
            await second_image_btn.click()
            await page.wait_for_timeout(300)
            await shot(page, "03_mobile_two_segments")

            # 测试保存校验（图片无图）
            log("=== 测试移动端保存校验 ===")
            save_btn = page.locator('button:has-text("保存")').first
            await save_btn.click()
            await page.wait_for_timeout(800)
            await shot(page, "04_mobile_validation")

            # 检查 toast 提示
            toast = page.locator('.m-dsl-toast, .toast, [class*="toast"]')
            toast_count = await toast.count()
            log(f"toast 提示数量: {toast_count}")
            if toast_count > 0:
                toast_text = await toast.first.text_content()
                log(f"toast 内容: {toast_text}")
            results["validation"] = toast_count > 0 or await segments.count() == 2

            # 上传图片
            log("=== 上传图片 ===")
            test_image = Path("g:/源码/xianyu-assistant-package-temp/tmp_test/test_image.png")
            second_segment = page.locator('.m-dsl-segment').nth(1)
            file_input = second_segment.locator('input[type="file"]').first
            await file_input.set_input_files(str(test_image))
            await page.wait_for_timeout(2000)
            preview = second_segment.locator('.m-dsl-segment-image-preview')
            preview_count = await preview.count()
            log(f"图片预览数量: {preview_count}")
            results["image_upload"] = preview_count > 0
            await shot(page, "05_mobile_image_uploaded")

            # 保存
            log("=== 保存 ===")
            await save_btn.click()
            await page.wait_for_timeout(2500)
            await shot(page, "06_mobile_after_save")

            # 检查列表
            log("=== 验证列表 ===")
            await page.goto(f"{BASE_URL}/#/dashboard", wait_until="domcontentloaded")
            await page.wait_for_timeout(500)
            await page.goto(f"{BASE_URL}/#/delivery-source-library", wait_until="domcontentloaded")
            await wait_idle(page)
            await page.wait_for_timeout(2000)
            await shot(page, "07_mobile_list_after_save")

            test_source = page.locator('text="移动端测试-多条正文"')
            found = await test_source.count()
            log(f"在列表中找到测试货源: {found > 0}")
            results["in_list"] = found > 0

            # 编辑验证回显
            if found:
                log("=== 编辑验证回显 ===")
                edit_btn = page.locator('.m-dsl-source-card:has-text("移动端测试-多条正文") button:has-text("编辑")').first
                await edit_btn.click()
                await page.wait_for_timeout(1500)
                await shot(page, "08_mobile_edit_form")

                edit_segments = page.locator('.m-dsl-segment')
                edit_count = await edit_segments.count()
                log(f"编辑时 segment 数量: {edit_count}")
                results["edit_echo"] = edit_count >= 2

                if edit_count >= 2:
                    first_text = page.locator('.m-dsl-segment').nth(0).locator('textarea').first
                    if await first_text.count() > 0:
                        val = await first_text.input_value()
                        log(f"  第一条文本回显: {val!r}")
                    second = page.locator('.m-dsl-segment').nth(1)
                    second_preview = await second.locator('.m-dsl-segment-image-preview').count()
                    log(f"  第二条图片预览存在: {second_preview > 0}")

        except Exception as e:
            log(f"❌ 异常: {type(e).__name__}: {e}")
            await shot(page, "99_error")
            import traceback
            traceback.print_exc()
        finally:
            log("\n" + "="*60)
            log("移动端测试结果汇总")
            log("="*60)
            for k, v in results.items():
                status = "✅" if v else "❌"
                log(f"  {status} {k}: {v}")

            log("\n=== 控制台错误/警告 ===")
            if console_errors:
                for err in console_errors[:15]:
                    log(f"  {err}")
            else:
                log("  无")

            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
