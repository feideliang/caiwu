"""Check if margin analysis table and concentration panel render data after dimension switch."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    api_calls = []

    def on_request(req):
        if "/api/v1/metrics/core" in req.url:
            qs = parse_qs(urlparse(req.url).query)
            dim = qs.get("dimension", ["?"])[0]
            dept = qs.get("department", ["(none)"])[0]
            entity = qs.get("entity", ["(none)"])[0]
            api_calls.append(f"dim={dim} dept={dept} entity={entity}")

    page.on("request", on_request)

    # Login
    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)

    # Navigate to metrics
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)

    # Step 1: Select department dimension
    print("=== Step 1: Select department ===")
    api_calls.clear()
    selects = page.locator(".ant-select").all()
    selects[3].click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "部门" in o.inner_text():
            o.click()
            break
    page.wait_for_timeout(3000)

    # Step 2: Select CBG entity
    print("=== Step 2: Select CBG ===")
    api_calls.clear()
    selects = page.locator(".ant-select").all()
    selects[4].click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click()
            break
    page.wait_for_timeout(3000)

    # Step 3: Switch to product_line
    print("\n=== Step 3: Switch to product_line ===")
    api_calls.clear()
    selects = page.locator(".ant-select").all()
    selects[3].click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "产品线" in o.inner_text():
            o.click()
            break
    page.wait_for_timeout(5000)

    print("API calls:")
    for c in api_calls:
        print(f"  {c}")

    # Check margin change analysis table rows
    print("\n=== Margin change analysis table ===")
    tbody = page.locator(".ant-table-tbody").first
    rows = tbody.locator("tr").all()
    print(f"Rows: {len(rows)}")
    for i, row in enumerate(rows[:6]):
        cells = row.locator("td").all()
        texts = [c.inner_text()[:30] for c in cells]
        print(f"  {texts}")

    # Tags
    tags = [t.inner_text() for t in page.locator(".ant-tag").all()]
    print(f"Tags: {tags}")

    # Concentration panel
    print("\n=== Concentration panel titles ===")
    for el in page.locator(".ant-card-head-title").all():
        txt = el.inner_text()
        if "集中度" in txt or "Top" in txt:
            print(f"  {txt}")

    browser.close()
