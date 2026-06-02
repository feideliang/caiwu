"""Debug: check departmentScope value during dimension switch."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    def on_request(req):
        if "/api/v1/metrics/core" in req.url:
            qs = parse_qs(urlparse(req.url).query)
            print(f"  REQ: dim={qs.get('dimension',['?'])[0]} dept={qs.get('department',['(none)'])[0]} entity={qs.get('entity',['(none)'])[0]}")

    page.on("request", on_request)

    # Login
    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)

    def get_state():
        return page.evaluate("""() => {
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
            if (s) return { dim: s.dimension.value, entity: s.selectedEntity?.value, deptScope: s.departmentScope?.value };
            return null;
        }""")

    # Step 1: Select department
    print("=== Step 1: Select department ===")
    selects = page.locator(".ant-select").all()
    selects[3].click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "部门" in o.inner_text():
            o.click()
            break
    page.wait_for_timeout(3000)
    print(f"  State: {get_state()}")

    # Step 2: Select CBG
    print("=== Step 2: Select CBG ===")
    selects = page.locator(".ant-select").all()
    selects[4].click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click()
            break
    page.wait_for_timeout(3000)
    print(f"  State: {get_state()}")

    # Step 3: Switch to product_line
    print("=== Step 3: Switch to product_line ===")
    selects = page.locator(".ant-select").all()
    selects[3].click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "产品线" in o.inner_text():
            o.click()
            break
    page.wait_for_timeout(2000)
    print(f"  State: {get_state()}")

    # Step 4: Wait and check again
    page.wait_for_timeout(3000)
    print(f"  State after 3s: {get_state()}")

    browser.close()
