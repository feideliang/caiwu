# -*- coding: utf-8 -*-
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    all_reqs = []
    page.on("request", lambda req: (
        all_reqs.append(parse_qs(urlparse(req.url).query))
        if "/api/v1/metrics/core" in req.url else None
    ))

    def dm():
        for _ in range(3):
            page.evaluate("document.querySelectorAll('vite-error-overlay,[data-vite-dev-overlay]').forEach(e=>e.remove())")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    def sc(locator):
        dm()
        try:
            locator.click(timeout=3000)
        except:
            locator.click(force=True, timeout=3000)
        page.wait_for_timeout(300)

    # Login (same as successful test)
    print("=== Login ===")
    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    inputs = page.locator("input").all()
    if len(inputs) >= 2:
        inputs[0].fill("admin")
        inputs[1].fill("admin123")
    sc(page.locator('button[type="submit"]'))
    page.wait_for_timeout(2000)
    print(f"  URL: {page.url}")

    if "login" in page.url:
        print("  Login failed, trying again...")
        page.fill("input", "admin")
        page.wait_for_timeout(300)
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        page.fill("input", "admin123")
        page.wait_for_timeout(200)
        page.locator("button[type='submit']").click(force=True)
        page.wait_for_timeout(3000)
        print(f"  URL: {page.url}")

    # Navigate to metrics
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    dm()
    print(f"  URL: {page.url}")
    if "login" in page.url:
        print("  STILL redirected - check login!")
        page.fill("input", "admin")
        page.keyboard.press("Tab")
        page.fill("input", "admin123")
        page.keyboard.press("Enter")
        page.wait_for_timeout(5000)
        print(f"  URL after retry: {page.url}")
        page.goto("http://127.0.0.1:3005/metrics")
        page.wait_for_timeout(8000)
        dm()
        print(f"  URL after goto metrics: {page.url}")

    all_reqs.clear()

    # Use select interactions (same as test_browser_flow)
    print("\n=== Step 1: dimension=department ===")
    selects = page.locator(".ant-select").all()
    sc(selects[3])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "Bmen" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dm()

    print("=== Step 2: CBG ===")
    selects = page.locator(".ant-select").all()
    sc(selects[4])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dm()

    print(f"  reqs: {len(all_reqs)}")
    for qs in all_reqs:
        print(f"    dim={qs.get('dimension',[''])[0]:12s} dept={qs.get('department',[''])[0]:8s} ent={qs.get('entity',[''])[0] or '-'}")

    print("\n=== Step 3: cross-dim=customer ===")
    all_reqs.clear()
    selects = page.locator(".ant-select").all()
    # Index 5 = cross-dimension selector (after: periodDim, period, compare, dim, entity)
    sc(selects[5])
    page.wait_for_timeout(500)
    found = False
    for o in page.locator(".ant-select-item-option").all():
        txt = o.inner_text()
        if "customer" in txt or "客户" in txt:
            try:
                o.click()
                found = True
                break
            except:
                o.click(force=True)
                found = True
                break
    if not found:
        print("  WARN: customer option not found, trying force on all options")
        for o in page.locator(".ant-select-item-option").all():
            print(f"    option: '{o.inner_text()[:15]}'")
    page.wait_for_timeout(5000)
    dm()
    print(f"  reqs: {len(all_reqs)}")
    for qs in all_reqs:
        print(f"    dim={qs.get('dimension',[''])[0]:12s} dept={qs.get('department',[''])[0]:8s} ent={qs.get('entity',[''])[0] or '-'}")

    # Table
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"\nTable rows: {len(rows)}")
    for i, row in enumerate(rows[:5]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            v0 = (cells[0].inner_text()[:15] if len(cells)>0 else '').replace('\xa0','').strip()
            v1 = (cells[1].inner_text()[:28] if len(cells)>1 else '').replace('\xa0','').strip()
            v2 = (cells[2].inner_text()[:15] if len(cells)>2 else '').replace('\xa0','').strip()
            print(f"  [{i}] {v0:10s} {v1:20s} {v2}")

    # Tags
    tags = [(t.inner_text() or '').replace('\xa0','').strip() for t in page.locator(".ant-tag").all()]
    print(f"Tags: {tags}")

    browser.close()
