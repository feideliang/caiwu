# -*- coding: utf-8 -*-
import sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.on("request", lambda req: (
        None if "/api/v1/metrics/core" not in req.url else
        print(f"  REQ: dim={parse_qs(urlparse(req.url).query).get('dimension',['?'])[0]:12s} dept={parse_qs(urlparse(req.url).query).get('department',['(none)'])[0]:8s} entity={parse_qs(urlparse(req.url).query).get('entity',[''])[0] or '(none)'}")
    ))

    def dm():
        for _ in range(3):
            page.evaluate("document.querySelectorAll('vite-error-overlay').forEach(e=>e.remove())")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    dm()

    # Department dimension
    print("=== Step 1: department ===")
    page.locator(".ant-select").nth(3).click(timeout=3000)
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "Bmen" in o.inner_text():
            o.click(force=True); break
    page.wait_for_timeout(3000)
    dm()

    # CBG entity
    print("=== Step 2: CBG ===")
    page.locator(".ant-select").nth(4).click(timeout=3000)
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click(force=True); break
    page.wait_for_timeout(3000)
    dm()

    # Read table before cross-dim
    r1 = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"Table rows before: {len(r1)}")

    # Cross-dim = customer via page.evaluate (reliable)
    print("\n=== Step 3: cross-dim = customer via JS ===")
    page.evaluate("""() => {
        const walk = (inst) => {
            if (!inst) return;
            if (inst.setupState && inst.setupState.crossDimension !== undefined) {
                inst.setupState.crossDimension.value = 'customer';
                return;
            }
            if (inst.subTree) { const r = walkVNode(inst.subTree); if (r) return; }
        };
        const walkVNode = (v) => {
            if (!v) return;
            if (v.component) {
                if (v.component.setupState && v.component.setupState.crossDimension !== undefined) {
                    v.component.setupState.crossDimension.value = 'customer';
                    return true;
                }
                const r = walk(v.component); if (r) return true;
            }
            if (v.children) {
                const arr = Array.isArray(v.children) ? v.children : [v.children];
                for (const c of arr) { if (walkVNode(c)) return true; }
            }
        };
        walkVNode(document.querySelector('#app').__vue_app__._instance);
    }""")
    page.wait_for_timeout(5000)
    dm()

    # Table after cross-dim
    r2 = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"Table rows after: {len(r2)}")
    for i, row in enumerate(r2[:5]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            val = cells[1].inner_text()[:25].replace(u'\xa0','').strip()
            rev = cells[2].inner_text()[:20].replace(u'\xa0','').strip()
            print(f"  [{i}] {val} | {rev}")

    # Concentration
    items = page.locator(".concentration-panel .ant-list-item").all()
    print(f"\nConcentration items: {len(items)}")
    tags = [t.inner_text().replace(u'\xa0','').strip() for t in page.locator(".ant-tag").all()]
    print(f"Tags: {tags}")

    browser.close()
