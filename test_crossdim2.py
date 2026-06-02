# -*- coding: utf-8 -*-
"""Test cross-dimension selector updates main tables."""
import sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"

from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    def on_request(req):
        if "/api/v1/metrics/core" in req.url:
            qs = parse_qs(urlparse(req.url).query)
            dim = qs.get('dimension',['?'])[0]
            dept = qs.get('department',['(none)'])[0]
            ent = qs.get('entity',[''])[0] or '(none)'
            print(f"  REQ: dim={dim:15s} dept={dept:10s} entity={ent:10s}")

    page.on("request", on_request)

    def dismiss_modals():
        for _ in range(3):
            page.evaluate("""() => {
                document.querySelectorAll('vite-error-overlay, [data-vite-dev-overlay]').forEach(el => el.remove());
            }""")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    def safe_click(locator):
        dismiss_modals()
        try:
            locator.click(timeout=3000)
        except:
            locator.click(force=True, timeout=3000)
        page.wait_for_timeout(300)

    # Login
    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    dismiss_modals()

    # Step 1: Select department
    print("=== Step 1: department ===")
    selects = page.locator(".ant-select").all()
    safe_click(selects[3])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "Bmen" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Step 2: Select CBG
    print("=== Step 2: CBG ===")
    selects = page.locator(".ant-select").all()
    safe_click(selects[4])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Show initial table data
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"Table rows (before cross-dim): {len(rows)}")

    # Step 3: Select cross-dimension = customer
    print("\n=== Step 3: cross-dim = customer ===")
    selects = page.locator(".ant-select").all()
    print(f"Selects count: {len(selects)}")
    safe_click(selects[5])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "customer" in o.inner_text() or "客户" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(5000)
    dismiss_modals()

    # Check table data after cross-dimension
    rows2 = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"\nTable rows (after cross-dim=customer): {len(rows2)}")
    for i, row in enumerate(rows2[:5]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            val = cells[1].inner_text()[:25].replace(u'\xa0','').strip()
            rev = cells[2].inner_text()[:20].replace(u'\xa0','').strip()
            print(f"  [{i}] {val} | {rev}")

    # Concentration panel
    items = page.locator(".concentration-panel .ant-list-item").all()
    print(f"\nConcentration items: {len(items)}")

    # Tags
    tags = [t.inner_text().replace(u'\xa0','').strip() for t in page.locator(".ant-tag").all()]
    print(f"Tags: {tags}")

    browser.close()
