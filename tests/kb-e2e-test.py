"""
客服知识库 - 新建我的知识库弹窗 三种模式端到端测试
使用 Playwright 直接控制浏览器
"""
import os
import sys
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

# 截图保存目录
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "kb-e2e-screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 测试文件 URL（已放在 user-web/public 下）
TEST_FILE_URL = "http://localhost:5174/kb-test-files/test.docx"

# 前端地址
FRONTEND_URL = "http://localhost:5174/#/settings-kb"
LOGIN_URL = "http://localhost:5174/#/login"

# 后端地址
BACKEND_LOGIN_URL = "http://localhost:18080/api/login/login"

# 登录凭据
USERNAME = "admin"
PASSWORD = "123456"


def fetch_auth_token():
    """通过后端 API 登录获取 token"""
    try:
        data = json.dumps({"username": USERNAME, "password": PASSWORD}).encode("utf-8")
        req = urllib.request.Request(
            BACKEND_LOGIN_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            token = body.get("data", {}).get("token", "")
            if token:
                print(f"  获取到 token: {token[:30]}...")
                return token
            print(f"  登录响应无 token: {body}")
    except Exception as e:
        print(f"  获取 token 失败: {e}")
    return None


def screenshot(page, name):
    """截图并打印路径"""
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=False)
    print(f"  [截图] {path}")
    return path


def log_console_logs(page, label):
    """收集并打印 console 日志"""
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
    return logs


def close_existing_modal(page):
    """关闭已存在的模态框（如果有的话）"""
    try:
        overlay = page.locator(".kb-modal-overlay")
        if overlay.count() > 0 and overlay.first.is_visible():
            # 方法1：按 ESC
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            # 方法2：点击取消按钮
            cancel_btn = page.locator(".kb-modal-overlay button:has-text('取消')")
            if cancel_btn.count() > 0:
                cancel_btn.first.click()
                page.wait_for_timeout(500)
            # 方法3：点击关闭按钮
            close_btn = page.locator(".kb-modal-overlay .modal-close, .kb-modal-overlay .close-btn")
            if close_btn.count() > 0:
                close_btn.first.click()
                page.wait_for_timeout(500)
            # 方法4：JavaScript 强制关闭
            still_visible = page.locator(".kb-modal-overlay").count() > 0 and page.locator(".kb-modal-overlay").first.is_visible()
            if still_visible:
                page.evaluate("""() => {
                    const overlays = document.querySelectorAll('.kb-modal-overlay');
                    overlays.forEach(o => o.style.display = 'none');
                }""")
                page.wait_for_timeout(300)
                print("  [调试] 已强制隐藏已存在的模态框遮罩")
    except Exception as e:
        print(f"  [调试] 关闭已存在模态框时出错: {e}")


def diagnose_modal_state(page, label):
    """诊断模态框状态：打印 DOM 结构和可见性"""
    try:
        info = page.evaluate("""() => {
            const overlay = document.querySelector('.kb-modal-overlay');
            if (!overlay) return { found: false };
            const tabs = overlay.querySelectorAll('.kb-form-tab');
            const tabInfo = [];
            tabs.forEach((t, i) => {
                const rect = t.getBoundingClientRect();
                tabInfo.push({
                    index: i,
                    text: t.textContent.replace(/\\s+/g, ' ').trim(),
                    visible: rect.width > 0 && rect.height > 0,
                    classes: t.className,
                    rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                });
            });
            const overlayRect = overlay.getBoundingClientRect();
            return {
                found: true,
                overlayVisible: overlayRect.width > 0 && overlayRect.height > 0,
                overlayRect: { x: overlayRect.x, y: overlayRect.y, w: overlayRect.width, h: overlayRect.height },
                tabsCount: tabs.length,
                tabs: tabInfo,
                bodyText: overlay.innerText.substring(0, 300)
            };
        }""")
        print(f"  [诊断-{label}] 模态框状态: found={info.get('found')}, overlayVisible={info.get('overlayVisible')}")
        if info.get('tabs'):
            for t in info['tabs']:
                print(f"    Tab[{t['index']}]: visible={t['visible']}, text='{t['text']}', classes='{t['classes']}'")
        else:
            print(f"    无 .kb-form-tab 元素")
            print(f"    模态框文本: {info.get('bodyText', '')[:200]}")
        return info
    except Exception as e:
        print(f"  [诊断-{label}] 失败: {e}")
        return None


def test_file_upload_mode(page):
    """测试文件上传模式"""
    print("\n===== 测试 1：文件上传模式 =====")
    results = {"name": "文件上传模式", "steps": []}

    # 0. 先关闭已存在的模态框
    close_existing_modal(page)

    # 1. 打开新建知识库弹窗
    print("[步骤 1.1] 点击 + 新增我的知识库按钮")
    try:
        # 注意：不要点击 "我的知识库" tab，因为 button:has-text('我的知识库') 会同时匹配
        # "新增我的知识库" 按钮（DOM 中更靠前）和 "我的知识库" tab 按钮，导致误点。
        # "新增我的知识库" 按钮在 toolbar 中始终可见，无需切换 tab。
        # 使用 .btn-add 类精准定位新增按钮
        add_btn = page.locator(".btn-add")
        if add_btn.count() == 0:
            # 回退到文本匹配
            add_btn = page.locator("button.btn-add:has-text('新增')")
        add_btn.wait_for(state="visible", timeout=10000)
        add_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        # 使用 force=True 点击（与会话测试保持一致）
        add_btn.click(force=True)
        # 等待模态框遮罩出现
        page.wait_for_selector(".kb-modal-overlay", state="visible", timeout=8000)
        page.wait_for_timeout(800)
        screenshot(page, "01-modal-opened")
        diagnose_modal_state(page, "modal-opened")
        results["steps"].append({"step": "打开弹窗", "status": "PASS"})
        print("  弹窗已打开")
    except Exception as e:
        results["steps"].append({"step": "打开弹窗", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        screenshot(page, "01-modal-open-FAIL")
        return results

    # 2. 切换到文件上传 tab
    print("[步骤 1.2] 切换到文件上传 tab")
    try:
        # 等待表单 tabs 容器出现
        page.wait_for_selector(".kb-form-tabs", state="visible", timeout=8000)
        page.wait_for_timeout(500)
        # 使用与会话测试相同的方式：wait_for + click
        file_tab = page.locator("button.kb-form-tab:has-text('文件上传')")
        file_tab.wait_for(state="visible", timeout=8000)
        file_tab.click()
        page.wait_for_timeout(800)
        screenshot(page, "02-file-upload-tab")
        diagnose_modal_state(page, "file-tab-clicked")
        # 验证已切换：检查 file-dropzone 是否出现
        page.wait_for_selector(".file-dropzone", state="visible", timeout=5000)
        results["steps"].append({"step": "切换文件上传 tab", "status": "PASS"})
        print("  已切换到文件上传 tab")
    except Exception as e:
        results["steps"].append({"step": "切换文件上传 tab", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        screenshot(page, "02-file-upload-tab-FAIL")
        diagnose_modal_state(page, "file-tab-failed")
        return results

    # 3. 上传文件（通过 browser_evaluate 等价方式）
    print("[步骤 1.3] 上传 test.docx 文件")
    try:
        upload_result = page.evaluate("""async () => {
            const response = await fetch('http://localhost:5174/kb-test-files/test.docx');
            const blob = await response.blob();
            const file = new File([blob], '客服知识库_图书教材_测试.docx', {
                type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            });
            const input = document.querySelector('input[type="file"]');
            if (!input) return { error: '未找到 file input 元素' };
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return { success: true, fileName: file.name, fileSize: file.size };
        }""")
        print(f"  上传结果: {upload_result}")
        page.wait_for_timeout(1000)
        screenshot(page, "03-file-selected")
        if upload_result.get("success"):
            results["steps"].append({"step": "上传文件", "status": "PASS", "detail": upload_result})
            print("  文件已上传")
        else:
            results["steps"].append({"step": "上传文件", "status": "FAIL", "error": upload_result.get("error")})
            return results
    except Exception as e:
        results["steps"].append({"step": "上传文件", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 4. 点击 AI 提取问答按钮
    print("[步骤 1.4] 点击 AI 一键提取问答按钮")
    try:
        # 使用精准选择器：.extract-actions 内的 .btn-primary 按钮
        # 避免匹配到 tab 按钮（tab 按钮文本也含 "AI 提取问答"）
        extract_btn = page.locator(".extract-actions button.btn-primary")
        if extract_btn.count() == 0:
            # 回退：通过精确文本匹配（含 emoji 前缀）
            extract_btn = page.locator("button:has-text('🤖 AI 一键提取问答')")
        if extract_btn.count() == 0:
            # 再回退：取 .kb-form 下最后一个 btn-primary（排除 tab）
            extract_btn = page.locator(".kb-form button.btn-primary").last
        extract_btn.wait_for(state="visible", timeout=5000)
        extract_btn.click()
        print("  已点击提取按钮，等待 AI 处理...")
        # 等待 Q&A 预览表格出现（最长 120 秒）
        try:
            page.wait_for_selector(".qa-row, .qa-preview-table", state="visible", timeout=120000)
            page.wait_for_timeout(1000)
            screenshot(page, "04-ai-extract-result")
            # 统计提取的 Q&A 数量
            qa_count = page.locator(".qa-row").count()
            results["steps"].append({"step": "AI 提取问答", "status": "PASS", "qa_count": qa_count})
            print(f"  AI 提取完成，共 {qa_count} 条 Q&A")
        except Exception as wait_err:
            screenshot(page, "04-ai-extract-timeout")
            results["steps"].append({"step": "AI 提取问答", "status": "FAIL", "error": f"等待超时: {wait_err}"})
            print(f"  等待超时: {wait_err}")
            # 打印当前页面内容用于调试
            print("  当前 URL:", page.url)
            print("  页面标题:", page.title())
            return results
    except Exception as e:
        results["steps"].append({"step": "AI 提取问答", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 5. 填写分类与标签（文件模式使用 batch-form，无单独名称字段）
    print("[步骤 1.5] 填写分类与标签")
    try:
        # 文件模式的批量表单：parentCategory / childCategory / tags
        parent_input = page.locator("input[placeholder*='图书教材'], input[placeholder*='一级分类']").first
        if parent_input.count() == 0:
            # 回退：取 .batch-form 下第一个 input
            parent_input = page.locator(".batch-form input").first
        parent_input.wait_for(state="visible", timeout=5000)
        parent_input.fill("图书教材")
        page.wait_for_timeout(200)

        tags_input = page.locator("input[placeholder*='逗号分隔'], input[placeholder*='标签']").first
        if tags_input.count() == 0:
            tags_input = page.locator(".batch-form input").last
        tags_input.fill("正版,售后,E2E测试")
        page.wait_for_timeout(300)
        screenshot(page, "05-batch-form-filled")
        results["steps"].append({"step": "填写分类标签", "status": "PASS"})
        print("  分类与标签已填写")
    except Exception as e:
        results["steps"].append({"step": "填写分类标签", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 6. 点击保存按钮
    print("[步骤 1.6] 点击保存按钮")
    try:
        # 文件模式保存按钮文字为 "保存 X 条知识"
        save_btn = page.locator(".kb-modal-footer button.btn-primary")
        save_btn.wait_for(state="visible", timeout=5000)
        save_btn_text = save_btn.inner_text()
        print(f"  保存按钮文字: {save_btn_text}")
        # 检查按钮是否可用
        is_disabled = save_btn.evaluate("el => el.disabled")
        if is_disabled:
            print(f"  [警告] 保存按钮被禁用，可能没有可保存的条目")
            screenshot(page, "06-save-disabled")
            results["steps"].append({"step": "保存", "status": "FAIL", "error": "保存按钮被禁用"})
            return results
        save_btn.click()
        page.wait_for_timeout(3000)
        screenshot(page, "06-after-save")
        results["steps"].append({"step": "保存", "status": "PASS"})
        print("  保存已点击")
    except Exception as e:
        results["steps"].append({"step": "保存", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")

    return results


def test_conversation_mode(page):
    """测试会话提取模式"""
    print("\n===== 测试 2：会话提取模式 =====")
    results = {"name": "会话提取模式", "steps": []}

    # 0. 先关闭已存在的模态框
    close_existing_modal(page)

    # 1. 打开新建知识库弹窗
    print("[步骤 2.1] 点击 + 新增我的知识库按钮")
    try:
        add_btn = page.locator(".btn-add")
        if add_btn.count() == 0:
            add_btn = page.locator("button:has-text('新增我的知识库')")
        add_btn.wait_for(state="visible", timeout=10000)
        add_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        add_btn.click(force=True)
        page.wait_for_selector(".kb-modal-overlay", state="visible", timeout=8000)
        page.wait_for_timeout(800)
        screenshot(page, "07-conv-modal-open")
        results["steps"].append({"step": "打开弹窗", "status": "PASS"})
        print("  弹窗已打开")
    except Exception as e:
        results["steps"].append({"step": "打开弹窗", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 2. 切换到会话提取 tab
    print("[步骤 2.2] 切换到会话提取 tab")
    try:
        conv_tab = page.locator("button.kb-form-tab:has-text('会话提取')")
        conv_tab.wait_for(state="visible", timeout=5000)
        conv_tab.click()
        page.wait_for_timeout(500)
        screenshot(page, "08-conv-tab")
        results["steps"].append({"step": "切换会话提取 tab", "status": "PASS"})
        print("  已切换到会话提取 tab")
    except Exception as e:
        results["steps"].append({"step": "切换会话提取 tab", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 3. 选择小龙菜菜账号
    print("[步骤 2.3] 选择小龙菜菜账号 (ID=1)")
    try:
        account_select = page.locator("select.account-select")
        account_select.wait_for(state="visible", timeout=5000)
        account_select.select_option(value="1")
        page.wait_for_timeout(500)
        print("  已选择账号")
        results["steps"].append({"step": "选择账号", "status": "PASS"})
    except Exception as e:
        results["steps"].append({"step": "选择账号", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 4. 等待会话列表加载
    print("[步骤 2.4] 等待会话列表加载")
    try:
        page.wait_for_selector(".conv-row:not(.conv-row-head)", state="visible", timeout=30000)
        page.wait_for_timeout(1000)
        conv_count = page.locator(".conv-row:not(.conv-row-head)").count()
        screenshot(page, "09-conv-list")
        results["steps"].append({"step": "加载会话列表", "status": "PASS", "conv_count": conv_count})
        print(f"  会话列表已加载，共 {conv_count} 个会话")
    except Exception as e:
        screenshot(page, "09-conv-list-fail")
        results["steps"].append({"step": "加载会话列表", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 5. 选择前 2 个会话
    print("[步骤 2.5] 选择前 2 个会话")
    try:
        conv_rows = page.locator(".conv-row:not(.conv-row-head)")
        for i in range(min(2, conv_rows.count())):
            conv_rows.nth(i).click()
            page.wait_for_timeout(200)
        screenshot(page, "10-conv-selected")
        selected_count = page.locator(".conv-row.is-selected").count()
        results["steps"].append({"step": "选择会话", "status": "PASS", "selected": selected_count})
        print(f"  已选择 {selected_count} 个会话")
    except Exception as e:
        results["steps"].append({"step": "选择会话", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 6. 点击一键提取知识
    print("[步骤 2.6] 点击一键提取知识按钮")
    try:
        extract_btn = page.locator("button:has-text('一键提取知识')")
        extract_btn.wait_for(state="visible", timeout=5000)
        extract_btn.click()
        print("  已点击提取按钮，等待 AI 处理...")
        # 等待 Q&A 出现（最长 120 秒）
        try:
            page.wait_for_selector(".qa-row", state="visible", timeout=120000)
            page.wait_for_timeout(1000)
            qa_count = page.locator(".qa-row").count()
            screenshot(page, "11-conv-extract-result")
            results["steps"].append({"step": "AI 提取问答", "status": "PASS", "qa_count": qa_count})
            print(f"  AI 提取完成，共 {qa_count} 条 Q&A")
        except Exception as wait_err:
            screenshot(page, "11-conv-extract-timeout")
            results["steps"].append({"step": "AI 提取问答", "status": "FAIL", "error": f"等待超时: {wait_err}"})
            print(f"  等待超时: {wait_err}")
            return results
    except Exception as e:
        results["steps"].append({"step": "AI 提取问答", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 7. 填写名称并保存
    print("[步骤 2.7] 填写名称并保存")
    try:
        name_input = page.locator("input[placeholder*='名称'], input[placeholder*='知识库']")
        if name_input.count() == 0:
            name_input = page.locator(".kb-form input").first
        name_input.wait_for(state="visible", timeout=5000)
        name_input.fill("测试-会话提取模式-E2E")
        page.wait_for_timeout(300)

        save_btn = page.locator("button:has-text('保存')").last
        save_btn.wait_for(state="visible", timeout=5000)
        save_btn_text = save_btn.inner_text()
        print(f"  保存按钮文字: {save_btn_text}")
        save_btn.click()
        page.wait_for_timeout(3000)
        screenshot(page, "12-conv-after-save")
        results["steps"].append({"step": "保存", "status": "PASS"})
        print("  保存已点击")
    except Exception as e:
        results["steps"].append({"step": "保存", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")

    return results


def test_custom_mode(page):
    """测试自定义模式"""
    print("\n===== 测试 3：自定义模式 =====")
    results = {"name": "自定义模式", "steps": []}

    # 0. 先关闭已存在的模态框
    close_existing_modal(page)

    # 1. 打开新建知识库弹窗
    print("[步骤 3.1] 点击 + 新增我的知识库按钮")
    try:
        add_btn = page.locator(".btn-add")
        if add_btn.count() == 0:
            add_btn = page.locator("button:has-text('新增我的知识库')")
        add_btn.wait_for(state="visible", timeout=10000)
        add_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        add_btn.click(force=True)
        page.wait_for_selector(".kb-modal-overlay", state="visible", timeout=8000)
        page.wait_for_timeout(800)
        screenshot(page, "13-custom-modal-open")
        results["steps"].append({"step": "打开弹窗", "status": "PASS"})
        print("  弹窗已打开")
    except Exception as e:
        results["steps"].append({"step": "打开弹窗", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 2. 确认在自定义 tab（默认应该就是）
    print("[步骤 3.2] 确认自定义 tab")
    try:
        custom_tab = page.locator("button.kb-form-tab:has-text('自定义')")
        if custom_tab.count() > 0:
            # 检查是否已激活
            is_active = custom_tab.evaluate("el => el.classList.contains('active')")
            if not is_active:
                custom_tab.click()
                page.wait_for_timeout(300)
        screenshot(page, "14-custom-tab")
        results["steps"].append({"step": "确认自定义 tab", "status": "PASS"})
        print("  已在自定义 tab")
    except Exception as e:
        results["steps"].append({"step": "确认自定义 tab", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 3. 填写问题和回答
    print("[步骤 3.3] 填写问题和回答")
    try:
        # 找到问题输入框
        title_input = page.locator("input[placeholder*='问题'], textarea[placeholder*='问题']")
        if title_input.count() == 0:
            # 尝试更通用的选择器
            title_input = page.locator(".kb-form input, .kb-form textarea").first
        title_input.wait_for(state="visible", timeout=5000)
        title_input.fill("这本书是正版吗？")
        page.wait_for_timeout(200)

        # 找到回答输入框
        content_input = page.locator("textarea[placeholder*='回答'], textarea[placeholder*='答案']")
        if content_input.count() == 0:
            content_input = page.locator(".kb-form textarea").first
        content_input.wait_for(state="visible", timeout=5000)
        content_input.fill("是的，本店所售图书均为正版，支持专柜验货。")
        page.wait_for_timeout(200)

        screenshot(page, "15-custom-filled")
        results["steps"].append({"step": "填写问答", "status": "PASS"})
        print("  问题和回答已填写")
    except Exception as e:
        results["steps"].append({"step": "填写问答", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")
        return results

    # 4. 填写知识库名称并保存
    print("[步骤 3.4] 填写名称并保存")
    try:
        name_input = page.locator("input[placeholder*='名称'], input[placeholder*='知识库']")
        if name_input.count() == 0:
            name_input = page.locator(".kb-form input").last
        name_input.wait_for(state="visible", timeout=5000)
        name_input.fill("测试-自定义模式-E2E")
        page.wait_for_timeout(300)
        screenshot(page, "16-custom-name-filled")

        save_btn = page.locator("button:has-text('保存')").last
        save_btn.wait_for(state="visible", timeout=5000)
        save_btn.click()
        page.wait_for_timeout(3000)
        screenshot(page, "17-custom-after-save")
        results["steps"].append({"step": "保存", "status": "PASS"})
        print("  保存已点击")
    except Exception as e:
        results["steps"].append({"step": "保存", "status": "FAIL", "error": str(e)})
        print(f"  失败: {e}")

    return results


def main():
    print("=" * 60)
    print("客服知识库 - 新建我的知识库弹窗 三种模式端到端测试")
    print("=" * 60)
    print(f"截图保存目录: {SCREENSHOT_DIR}")
    print(f"前端地址: {FRONTEND_URL}")

    all_results = []

    with sync_playwright() as p:
        # 启动浏览器（headless 模式）
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN"
        )

        # 预设登录 token 到 localStorage（跳过登录流程）
        print("\n[准备] 获取登录 token...")
        token = fetch_auth_token()
        if token:
            # 先访问前端域名（让 localStorage 可写）
            page = context.new_page()
            page.goto("http://localhost:5174/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(500)
            # 注入 token 到 localStorage
            page.evaluate(f"""() => {{
                localStorage.setItem('xianyu_auth_token', '{token}');
                localStorage.setItem('xianyu_username', '{USERNAME}');
            }}""")
            print("  token 已注入 localStorage")
        else:
            print("  无法获取 token，将尝试通过 UI 登录")
            page = context.new_page()

        # 收集 console 日志
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # 收集网络请求
        failed_requests = []
        page.on("requestfailed", lambda req: failed_requests.append(f"FAILED: {req.url} - {req.failure}"))
        page.on("response", lambda resp: failed_requests.append(f"HTTP {resp.status}: {resp.url}") if resp.status >= 400 else None)

        try:
            # 1. 导航到知识库设置页
            print("\n[准备] 导航到知识库设置页...")
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            screenshot(page, "00-initial-page")
            print(f"  页面标题: {page.title()}")
            print(f"  当前 URL: {page.url}")

            # 检查是否需要登录
            if "login" in page.url.lower() or page.locator("input[placeholder*='账号'], input[placeholder*='用户名']").count() > 0:
                print("  需要登录，执行登录流程...")
                try:
                    # 用户名输入框
                    username_input = page.locator("input[placeholder*='账号'], input[placeholder*='用户名']").first
                    username_input.fill(USERNAME)
                    # 密码输入框
                    password_input = page.locator("input[type='password']").first
                    password_input.fill(PASSWORD)
                    page.wait_for_timeout(300)
                    # 使用精确匹配的登录按钮（type=submit）
                    login_btn = page.locator("button[type='submit']").first
                    login_btn.click()
                    page.wait_for_timeout(3000)
                    # 导航到知识库页面
                    page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    screenshot(page, "00b-after-login")
                    print("  登录完成")
                    print(f"  当前 URL: {page.url}")
                except Exception as e:
                    print(f"  登录失败: {e}")
                    import traceback
                    traceback.print_exc()

            # 2. 执行三种模式测试
            results_1 = test_file_upload_mode(page)
            all_results.append(results_1)

            # 关闭弹窗（如果还开着）
            try:
                close_btn = page.locator(".modal-close, button:has-text('取消')")
                if close_btn.count() > 0:
                    close_btn.first.click()
                    page.wait_for_timeout(500)
            except:
                pass

            results_2 = test_conversation_mode(page)
            all_results.append(results_2)

            try:
                close_btn = page.locator(".modal-close, button:has-text('取消')")
                if close_btn.count() > 0:
                    close_btn.first.click()
                    page.wait_for_timeout(500)
            except:
                pass

            results_3 = test_custom_mode(page)
            all_results.append(results_3)

        except Exception as e:
            print(f"\n[错误] 测试执行失败: {e}")
            import traceback
            traceback.print_exc()
            try:
                screenshot(page, "99-error")
            except:
                pass
        finally:
            # 打印 console 日志
            print("\n===== Console 日志（最后 20 条）=====")
            for log in console_logs[-20:]:
                print(f"  {log}")

            # 打印失败的请求
            if failed_requests:
                print("\n===== 失败的网络请求 =====")
                for req in failed_requests[-20:]:
                    print(f"  {req}")

            browser.close()

    # 输出测试报告
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)
    for result in all_results:
        print(f"\n【{result['name']}】")
        for step in result["steps"]:
            status_icon = "✓" if step["status"] == "PASS" else "✗"
            detail = ""
            for k, v in step.items():
                if k not in ["step", "status"]:
                    detail += f" {k}={v}"
            print(f"  {status_icon} {step['step']}: {step['status']}{detail}")

    # 保存测试报告 JSON
    report_path = os.path.join(SCREENSHOT_DIR, "test-report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"results": all_results, "console_logs": console_logs[-50:], "failed_requests": failed_requests[-20:]}, f, ensure_ascii=False, indent=2)
    print(f"\n测试报告已保存: {report_path}")
    print(f"截图目录: {SCREENSHOT_DIR}")


if __name__ == "__main__":
    main()
