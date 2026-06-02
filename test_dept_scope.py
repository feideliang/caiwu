"""Test departmentScope persistence across dimension switches using Playwright."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)

    api_calls = []
    page.on("request", lambda req: api_calls.append(req.url) if "/metrics/core" in req.url else None)

    # Step 1: set dimension to department via Vue component internals
    print("=== Step 1: dimension = department ===")
    page.evaluate("""() => {
        const walk = (inst) => {
            if (!inst) return null;
            if (inst.setupState && inst.setupState.dimension) return inst.setupState;
            if (inst.subTree) { const r = walkVNode(inst.subTree); if (r) return r; }
            return null;
        };
        const walkVNode = (v) => {
            if (!v) return null;
            if (v.component) {
                if (v.component.setupState && v.component.setupState.dimension) return v.component.setupState;
                const r = walk(v.component); if (r) return r;
            }
            if (v.children) {
                const arr = Array.isArray(v.children) ? v.children : [v.children];
                for (const c of arr) { const r = walkVNode(c); if (r) return r; }
            }
            return null;
        };
        const s = walk(document.querySelector('#app').__vue_app__._instance);
        if (s) { s.dimension.value = 'department'; }
    }""")
    page.wait_for_timeout(3000)
    print(f"  API calls: {len(api_calls)}")
    for u in api_calls:
        print(f"    {u}")
    api_calls.clear()

    # Step 2: set entity to CBG
    print("\n=== Step 2: entity = CBG ===")
    page.evaluate("""() => {
        const walk = (inst) => {
            if (!inst) return null;
            if (inst.setupState && inst.setupState.selectedEntity) return inst.setupState;
            if (inst.subTree) { const r = walkVNode(inst.subTree); if (r) return r; }
            return null;
        };
        const walkVNode = (v) => {
            if (!v) return null;
            if (v.component) {
                if (v.component.setupState && v.component.setupState.selectedEntity) return v.component.setupState;
                const r = walk(v.component); if (r) return r;
            }
            if (v.children) {
                const arr = Array.isArray(v.children) ? v.children : [v.children];
                for (const c of arr) { const r = walkVNode(c); if (r) return r; }
            }
            return null;
        };
        const s = walk(document.querySelector('#app').__vue_app__._instance);
        if (s) { s.selectedEntity.value = 'CBG'; }
    }""")
    page.wait_for_timeout(5000)
    print(f"  API calls: {len(api_calls)}")
    for u in api_calls:
        print(f"    {u}")
        if "department=" in u:
            print("      *** has department= ***")
    api_calls.clear()

    # Check orange tag
    tags = page.evaluate("""() => Array.from(document.querySelectorAll('.ant-tag')).map(t => t.textContent.trim())""")
    print(f"  Tags: {tags}")

    # Step 3: switch dimension to customer via Vue
    print("\n=== Step 3: dimension = customer ===")
    page.evaluate("""() => {
        const walk = (inst) => {
            if (!inst) return null;
            if (inst.setupState && inst.setupState.dimension) return inst.setupState;
            if (inst.subTree) { const r = walkVNode(inst.subTree); if (r) return r; }
            return null;
        };
        const walkVNode = (v) => {
            if (!v) return null;
            if (v.component) {
                if (v.component.setupState && v.component.setupState.dimension) return v.component.setupState;
                const r = walk(v.component); if (r) return r;
            }
            if (v.children) {
                const arr = Array.isArray(v.children) ? v.children : [v.children];
                for (const c of arr) { const r = walkVNode(c); if (r) return r; }
            }
            return null;
        };
        const s = walk(document.querySelector('#app').__vue_app__._instance);
        if (s) { s.dimension.value = 'customer'; }
    }""")
    page.wait_for_timeout(5000)
    print(f"  API calls: {len(api_calls)}")
    for u in api_calls:
        print(f"    {u}")
        if "department=" in u:
            print("      *** has department= ***")

    tags = page.evaluate("""() => Array.from(document.querySelectorAll('.ant-tag')).map(t => t.textContent.trim())""")
    print(f"  Tags: {tags}")

    # Table data
    table = page.evaluate("""() => {
        const rows = document.querySelectorAll('.ant-table tbody tr');
        for (const tr of rows) {
            const cells = tr.querySelectorAll('td');
            if (cells.length > 1 && cells[1].textContent.trim()) {
                return Array.from(cells).slice(1,3).map(c => c.textContent.trim()).join(' | ');
            }
        }
        return 'no data';
    }""")
    print(f"  Table first item: {table}")

    browser.close()