import asyncio
import httpx
import json
from playwright.async_api import async_playwright

async def main():
    # Login
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8001/api/v1/auth/login", json={"username":"admin","password":"admin123"})
        data = resp.json()
        data_obj = data.get("data", data)
        access_token = data_obj.get("access_token", "")
        user_obj = data_obj.get("user", {})
        print(f"Token: {access_token[:60]}...")

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
    context = await browser.new_context(viewport={"width": 1400, "height": 900})

    page = await context.new_page()

    # Navigate first, then check what's on the page
    await page.goto("http://localhost:3000/drilldown/2026-03", timeout=30000)
    await asyncio.sleep(5)

    # Check current localStorage keys
    keys = await page.evaluate("Object.keys(localStorage)")
    print(f"localStorage keys: {keys}")

    # Check token value
    token_val = await page.evaluate("localStorage.getItem('token')")
    print(f"localStorage token: {token_val}")

    # Set token manually via JS
    await page.evaluate(f"""() => {{
        localStorage.setItem('token', '{access_token}');
        localStorage.setItem('user', {json.dumps(user_obj)});
    }}""")
    token_after = await page.evaluate("localStorage.getItem('token')")
    print(f"Token after setting: {token_after[:60]}...")

    # Reload page
    await page.reload(timeout=30000)
    await asyncio.sleep(5)

    # Check page content
    body_text = await page.evaluate("document.body.innerText")
    print(f"\nPage body text (first 500 chars):")
    print(body_text[:500])

    # Check for all class names containing "drilldown" or "table"
    drilldown_classes = await page.evaluate("""() => {
        const els = document.querySelectorAll('[class*="drilldown"]');
        return els.map(e => e.className);
    }""")
    print(f"\nElements with 'drilldown' in class: {drilldown_classes}")

    table_classes = await page.evaluate("""() => {
        const els = document.querySelectorAll('.ant-table-tbody .ant-table-row');
        return els.length;
    }""")
    print(f"ant-table-row count: {table_classes}")

    # Check all top-level elements
    all_tags = await page.evaluate("""() => {
        const tags = {};
        document.querySelectorAll('body *').forEach(el => {
            tags[el.tagName] = (tags[el.tagName] || 0) + 1;
        });
        return tags;
    }""")
    print(f"\nElement tag counts: {all_tags}")

    # Screenshot
    await page.screenshot(path="C:/tmp/debug_page.png")
    print("\nScreenshot saved to C:/tmp/debug_page.png")

    await browser.close()
    await pw.stop()

asyncio.run(main())
