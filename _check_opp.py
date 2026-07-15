"""快速检查 OpportunityPage 内容"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    token = open("_verify_token.txt", encoding="utf-8").read()
    page.goto("http://localhost:5174/", wait_until="networkidle", timeout=30000)
    page.evaluate(f"""() => {{
        localStorage.setItem('xya_token', '{token}');
        localStorage.setItem('xya_username', 'demo');
    }}""")
    page.goto("http://localhost:5174/#/opportunities", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3500)
    title = page.title()
    body_text = page.evaluate("() => document.body.innerText.slice(0, 500)")
    print("TITLE:", title)
    print("BODY (first 500 chars):")
    print(body_text)
    page.screenshot(path="_opp.png", full_page=True)
    print("Screenshot saved")
    browser.close()
