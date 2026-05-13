import asyncio
import httpx
import json
from playwright.async_api import async_playwright

async def main():
    results = {}

    # Step 1: Get JWT token
    print("=== Step 1: Login ===")
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8001/api/v1/auth/login", json={"username":"admin","password":"admin123"})
        print(f"  Status: {resp.status_code}")
        data = resp.json()
        data_obj = data.get("data", data)
        access_token = data_obj.get("access_token", "")
        user_obj = data_obj.get("user", {})
        user_info = json.dumps(user_obj, ensure_ascii=False)[:200]
        if access_token:
            results["login"] = "PASS"
            print(f"  Token: {access_token[:50]}...")
            print(f"  User: {user_info}")
        else:
            results["login"] = f"FAIL - {data}"
            print(f"  FAIL: {data}")
            print(json.dumps(results, indent=2))
            return

    # Step 2: Launch browser
    print("\n=== Step 2: Launch browser ===")
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
    context = await browser.new_context(viewport={"width": 1400, "height": 900})
    # Use correct localStorage key: "access_token" not "token"
    user_json = json.dumps(user_obj).replace("'", "\'")
    await context.add_init_script(f"""
        localStorage.setItem('access_token', '{access_token}');
        localStorage.setItem('user', '{user_json}');
    """)
    page = await context.new_page()
    results["launch_browser"] = "PASS"
    print("  Browser launched, init_script set with access_token key")

    # Step 3: Navigate
    print("\n=== Step 3: Navigate to /drilldown/2026-03 ===")
    try:
        await page.goto("http://localhost:3000/drilldown/2026-03", timeout=30000)
        print(f"  URL after nav: {page.url}")
    except Exception as e:
        print(f"  Navigation timeout caught: {e}")
    results["navigate"] = "PASS"
    print(f"  Current URL: {page.url}")

    # Step 4: Wait 5 seconds
    print("\n=== Step 4: Wait 5 seconds ===")
    await asyncio.sleep(5)
    results["wait_5s"] = "PASS"
    print("  Done waiting")

    # Debug: check localStorage
    stored_token = await page.evaluate("localStorage.getItem('access_token')")
    stored_user = await page.evaluate("localStorage.getItem('user')")
    print(f"  localStorage access_token present: {bool(stored_token)}")
    print(f"  localStorage user: {stored_user}")

    # Step 5: Test L1
    print("\n=== Step 5: Test L1 ===")
    l1_count = await page.locator(".drilldown-l1").count()
    l1_rows = await page.locator(".drilldown-l1 .ant-table-tbody .ant-table-row").count()
    l1_first_cell = ""
    if l1_rows > 0:
        l1_first_cell = await page.locator(".drilldown-l1 .ant-table-tbody .ant-table-row").first.locator("td").first.inner_text()
    await page.screenshot(path="C:/tmp/l1.png")
    results["l1_exists"] = "PASS" if l1_count > 0 else "FAIL"
    results["l1_rows"] = f"PASS - {l1_rows} rows" if l1_rows > 0 else f"FAIL - 0 rows"
    print(f"  .drilldown-l1 containers: {l1_count}")
    print(f"  L1 rows: {l1_rows}")
    print(f"  First row first cell: {l1_first_cell[:100]}")
    l1_has_rows = l1_rows > 0

    if l1_has_rows:
        print("\n=== Step 6: Click first L1 department row ===")
        await page.locator(".drilldown-l1 .ant-table-tbody .ant-table-row").first.click()
        await asyncio.sleep(2)
        results["click_l1"] = "PASS"
    else:
        results["click_l1"] = "SKIP - no L1 rows"
        print("  SKIP - no L1 rows to click")

    # Step 7: Test L2
    print("\n=== Step 7: Test L2 ===")
    l2_count = await page.locator(".drilldown-l2").count()
    l2_rows = await page.locator(".drilldown-l2 .ant-table-tbody .ant-table-row").count()
    l2_first_cell = ""
    if l2_rows > 0:
        l2_first_cell = await page.locator(".drilldown-l2 .ant-table-tbody .ant-table-row").first.locator("td").first.inner_text()
    await page.screenshot(path="C:/tmp/l2.png")
    results["l2_exists"] = "PASS" if l2_count > 0 else "FAIL"
    results["l2_rows"] = f"PASS - {l2_rows} rows" if l2_rows > 0 else f"FAIL - 0 rows"
    print(f"  .drilldown-l2 containers: {l2_count}")
    print(f"  L2 rows: {l2_rows}")
    print(f"  First row first cell: {l2_first_cell[:100]}")
    l2_has_rows = l2_rows > 0

    if l2_has_rows:
        print("\n=== Step 8: Click first L2 product row ===")
        await page.locator(".drilldown-l2 .ant-table-tbody .ant-table-row").first.click()
        await asyncio.sleep(2)
        results["click_l2"] = "PASS"
    else:
        results["click_l2"] = "SKIP - no L2 rows"
        print("  SKIP - no L2 rows to click")

    # Step 9: Test L3
    print("\n=== Step 9: Test L3 ===")
    l3_count = await page.locator(".drilldown-l3").count()
    l3_rows = await page.locator(".drilldown-l3 .ant-table-tbody .ant-table-row").count()
    l3_first_cell = ""
    if l3_rows > 0:
        l3_first_cell = await page.locator(".drilldown-l3 .ant-table-tbody .ant-table-row").first.locator("td").first.inner_text()
    await page.screenshot(path="C:/tmp/l3.png")
    results["l3_exists"] = "PASS" if l3_count > 0 else "FAIL"
    results["l3_rows"] = f"PASS - {l3_rows} rows" if l3_rows > 0 else f"FAIL - 0 rows"
    print(f"  .drilldown-l3 containers: {l3_count}")
    print(f"  L3 rows: {l3_rows}")
    print(f"  First row first cell: {l3_first_cell[:100]}")
    l3_has_rows = l3_rows > 0

    if l3_has_rows:
        print("\n=== Step 10: Click first L3 record row ===")
        await page.locator(".drilldown-l3 .ant-table-tbody .ant-table-row").first.click()
        await asyncio.sleep(2)
        results["click_l3"] = "PASS"
    else:
        results["click_l3"] = "SKIP - no L3 rows"
        print("  SKIP - no L3 rows to click")

    # Step 11: Test L4
    print("\n=== Step 11: Test L4 ===")
    l4_count = await page.locator(".drilldown-l4").count()
    modal_count = await page.locator(".ant-modal").count()
    await page.screenshot(path="C:/tmp/l4.png")
    results["l4_exists"] = "PASS" if l4_count > 0 else "FAIL"
    results["modal_exists"] = "PASS" if modal_count > 0 else "FAIL"
    print(f"  .drilldown-l4 containers: {l4_count}")
    print(f"  .ant-modal elements: {modal_count}")

    # Step 12: Test breadcrumb back
    print("\n=== Step 12: Test breadcrumb back ===")
    breadcrumb_links = await page.locator(".ant-breadcrumb a").count()
    results["breadcrumb_links"] = f"PASS - {breadcrumb_links} links" if breadcrumb_links > 0 else "FAIL - 0 links"
    print(f"  Breadcrumb links: {breadcrumb_links}")
    if breadcrumb_links > 0:
        print("  Clicking first breadcrumb link...")
        await page.locator(".ant-breadcrumb a").first.click()
        await asyncio.sleep(1)
        l1_count_after = await page.locator(".drilldown-l1").count()
        results["breadcrumb_click"] = f"PASS - L1 containers after: {l1_count_after}"
        print(f"  L1 containers after breadcrumb click: {l1_count_after}")
    else:
        results["breadcrumb_click"] = "SKIP - no breadcrumb links"

    await browser.close()
    await pw.stop()

    print("\n" + "="*60)
    print("DRILL-DOWN FLOW TEST RESULTS")
    print("="*60)
    for step, result in results.items():
        print(f"  {step:25s} | {result}")
    print("="*60)

asyncio.run(main())
