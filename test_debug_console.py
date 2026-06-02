"""Debug: capture console logs during dimension switch - proper Ant Design interaction."""
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

    def on_console(msg):
        text = msg.text
        if any(k in text for k in ['[watch1]', '[main watch]', '[deptScope', '[fetchMetrics]', '[loadEntityOptions]']):
            print(f"  CONSOLE: {text}")

    page.on("console", on_console)

    def dismiss_modals():
        for _ in range(3):
            page.evaluate("""() => {
                document.querySelectorAll('vite-error-overlay, [data-vite-dev-overlay]').forEach(el => el.remove());
                const s = document.querySelector('vite-error-overlay');
                if (s && s.shadowRoot) s.shadowRoot.innerHTML = '';
            }""")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    def select_option(select_index, option_text):
        """Click a select, then click an option by text."""
        dismiss_modals()
        selects = page.locator(".ant-select").all()
        selects[select_index].click()
        page.wait_for_timeout(500)
        # Find option in the dropdown (rendered in body portal)
        options = page.locator(".ant-select-item-option").all()
        for o in options:
            if option_text in o.inner_text():
                o.click()
                page.wait_for_timeout(300)
                return True
        print(f"  WARNING: option '{option_text}' not found in {len(options)} options")
        return False

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

    # Check initial selects
    selects = page.locator(".ant-select").all()
    print(f"Initial selects: {len(selects)}")
    for i, s in enumerate(selects):
        print(f"  [{i}] '{s.inner_text()[:30]}'")

    # Step 1: Select department
    print("\n=== Step 1: Select department ===")
    select_option(3, "部门")
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Check selects after dimension change
    selects = page.locator(".ant-select").all()
    print(f"Selects after dim change: {len(selects)}")
    for i, s in enumerate(selects):
        print(f"  [{i}] '{s.inner_text()[:30]}'")

    # Step 2: Select CBG
    print("\n=== Step 2: Select CBG ===")
    select_option(4, "CBG")
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Check state after CBG selection
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
        if (s) return {
            dim: s.dimension?.value,
            entity: s.selectedEntity?.value,
            deptScope: s.departmentScope?.value
        };
        return 'not found';
    }""")
    print(f"  State after CBG: {state}")

    # Step 3: Switch to product_line
    print("\n=== Step 3: Switch to product_line ===")
    select_option(3, "产品线")
    page.wait_for_timeout(5000)
    dismiss_modals()

    # Final state
    state2 = page.evaluate("""() => {
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
        if (s) return {
            dim: s.dimension?.value,
            entity: s.selectedEntity?.value,
            deptScope: s.departmentScope?.value
        };
        return 'not found';
    }""")
    print(f"  Final state: {state2}")

    # Check tags
    tags = [t.inner_text() for t in page.locator(".ant-tag").all()]
    print(f"  Tags: {tags}")

    # Check margin table
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"  Table rows: {len(rows)}")
    for i, row in enumerate(rows[:3]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            print(f"    [{i}] {[c.inner_text()[:20] for c in cells[1:4]]}")

    browser.close()
