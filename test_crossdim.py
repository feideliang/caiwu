"""Test cross-dimension selector updates main tables."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    def on_request(req):
        if "/api/v1/metrics/core" in req.url:
            qs = parse_qs(urlparse(req.url).query)
            print(f"  REQ: dim={qs.get('dimension',[''])[0]:15s} dept={qs.get('department',['(none)'])[0]:10s} entity={qs.get('entity',[''])[0]:10s}")

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
    print("=== Step 1: 部门 ===")
    page.locator(".ant-select").nth(3).click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "部门" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Step 2: Select CBG
    print("=== Step 2: CBG ===")
    page.locator(".ant-select").nth(4).click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Show initial table data (CBG level - no cross dimension)
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"Table rows (before cross-dim): {len(rows)}")
    for i, row in enumerate(rows[:3]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            val = cells[1].inner_text()[:25] if len(cells) > 1 else ""
            rev = cells[2].inner_text()[:20] if len(cells) > 2 else ""
            print(f"  [{i}] {val} | {rev}")

    # Step 3: Select cross-dimension = customer
    print("\n=== Step 3: 交叉维度 = 客户 ===")
    selects = page.locator(".ant-select").all()
    print(f"Selects count: {len(selects)}")
    for i, s in enumerate(selects):
        print(f"  [{i}] '{s.inner_text()[:30]}'")
    
    # The cross-dimension selector should be at index 5
    safe_click(selects[5])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "客户" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(5000)
    dismiss_modals()

    # Check table data after cross-dimension selection
    rows2 = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"\nTable rows (after cross-dim=customer): {len(rows2)}")
    for i, row in enumerate(rows2[:5]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            val = cells[1].inner_text()[:25]
            rev = cells[2].inner_text()[:20]
            print(f"  [{i}] {val} | {rev}")

    # Check concentration panel
    print("\n=== Concentration panel ===")
    list_items = page.locator(".concentration-panel .ant-list-item").all()
    print(f"List items: {len(list_items)}")
    
    # Check page state
    state = page.evaluate("""() => {
        const walk = (inst) => {
            if (!inst) return null;
            if (inst.setupState && inst.setupState.dimension !== undefined) return inst.setupState;
            if (inst.subTree) { const r = walkVNode(inst.subTree); if (r) return r; }
            return null;
        };
        const walkVNode = (v) => {
            if (!v) return null;
            if (v.component) {
                if (v.component.setupState && v.component.setupState.dimension !== undefined) return v.component.setupState;
                const r = walk(v.component); if (r) return r;
            }
            if (v.children) {
                const arr = Array.isArray(v.children) ? v.children : [v.children];
                for (const c of arr) { const r = walkVNode(c); if (r) return r; }
            }
            return null;
        };
        const s = walk(document.querySelector('#app').__vue_app__._instance);
        if (s) return { dim: s.dimension?.value, cross: s.crossDimension?.value, deptScope: s.departmentScope?.value };
        return 'not found';
    }""")
    print(f"\nState: {state}")

    # Tags
    tags = [t.inner_text() for t in page.locator(".ant-tag").all()]
    print(f"Tags: {tags}")

    browser.close()
