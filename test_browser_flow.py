"""Browser test: verify department filter persistence across dimension switches."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        api_calls = []

        def on_request(req):
            if "/api/v1/metrics/core" in req.url:
                qs = parse_qs(urlparse(req.url).query)
                dim = qs.get("dimension", ["?"])[0]
                dept = qs.get("department", ["(none)"])[0]
                entity = qs.get("entity", ["(none)"])[0]
                period = qs.get("period", ["(none)"])[0]
                pdim = qs.get("period_dimension", ["?"])[0]
                entry = f"metrics/core dim={dim} dept={dept} entity={entity} period={period} pdim={pdim}"
                api_calls.append(entry)
                print(f"  >> {entry}")

        def on_response(resp):
            if "metrics/core" in resp.url and resp.status == 200:
                try:
                    body = resp.json()
                    data = body.get("data", {})
                    s = data.get("summary", {}) if isinstance(data, dict) else {}
                    ma = s.get("margin_change_analysis") or []
                    rev = s.get("revenue")
                    margin = s.get("gross_margin")
                    print(f"  << revenue={rev}, margin={margin}, items={len(ma)}")
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        def dismiss_modals():
            """Remove any blocking modals/overlays."""
            for _ in range(3):
                page.evaluate("""() => {
                    document.querySelectorAll('vite-error-overlay, [data-vite-dev-overlay]').forEach(el => el.remove());
                    const s = document.querySelector('vite-error-overlay');
                    if (s && s.shadowRoot) s.shadowRoot.innerHTML = '';
                }""")
                page.keyboard.press("Escape")
                page.wait_for_timeout(200)

        def safe_click(locator):
            """Click with modal dismissal and force fallback."""
            dismiss_modals()
            try:
                locator.click(timeout=3000)
            except:
                locator.click(force=True, timeout=3000)
            page.wait_for_timeout(300)

        # Step 1: Login
        print("=== Step 1: Login ===")
        page.goto("http://127.0.0.1:3005/login")
        page.wait_for_timeout(1500)
        inputs = page.locator("input").all()
        if len(inputs) >= 2:
            inputs[0].fill("admin")
            inputs[1].fill("admin123")
        safe_click(page.locator('button[type="submit"]'))
        page.wait_for_timeout(2000)
        print(f"  URL: {page.url}")

        # Step 2: Navigate to /metrics
        print("\n=== Step 2: Navigate to /metrics ===")
        page.goto("http://127.0.0.1:3005/metrics")
        page.wait_for_timeout(8000)
        dismiss_modals()

        page.screenshot(path="/tmp/t2_page.png")

        selects = page.locator(".ant-select").all()
        print(f"  Found {len(selects)} .ant-select elements")
        for i, s in enumerate(selects):
            text = s.inner_text()[:30]
            print(f"    [{i}] '{text}'")

        # Step 3: Select dimension = department
        print("\n=== Step 3: Select dimension=department ===")
        api_calls.clear()
        safe_click(selects[3])
        page.wait_for_timeout(500)
        options = page.locator(".ant-select-item-option").all()
        for o in options:
            if "部门" in o.inner_text():
                o.click()
                break
        page.wait_for_timeout(4000)
        dismiss_modals()
        page.screenshot(path="/tmp/t3_dept.png")
        print(f"  API calls: {len(api_calls)}")
        for c in api_calls:
            print(f"    {c}")

        # Step 4: Select entity = CBG
        print("\n=== Step 4: Select entity=CBG ===")
        api_calls.clear()
        selects = page.locator(".ant-select").all()
        print(f"  Selects now: {len(selects)}")
        safe_click(selects[4])
        page.wait_for_timeout(500)
        options = page.locator(".ant-select-item-option").all()
        print(f"  Entity options ({len(options)}):")
        for j, o in enumerate(options):
            print(f"    [{j}] {o.inner_text()}")
        for o in options:
            if "CBG" in o.inner_text():
                o.click()
                break
        page.wait_for_timeout(5000)
        dismiss_modals()
        page.screenshot(path="/tmp/t4_cbg.png")
        print(f"  API calls: {len(api_calls)}")
        for c in api_calls:
            print(f"    {c}")
        cbg_calls = [c for c in api_calls if "dept=CBG" in c]
        print(f"  Calls with dept=CBG: {len(cbg_calls)}")

        # Check orange tag
        for t in page.locator(".ant-tag").all():
            txt = t.inner_text()
            if "部门" in txt or "CBG" in txt:
                print(f"  Orange tag: '{txt}'")

        # Step 5: Switch to product_line
        print("\n=== Step 5: Switch to product_line ===")
        api_calls.clear()
        selects = page.locator(".ant-select").all()
        safe_click(selects[3])
        page.wait_for_timeout(500)
        options = page.locator(".ant-select-item-option").all()
        for o in options:
            if "产品线" in o.inner_text():
                o.click()
                break
        page.wait_for_timeout(5000)
        dismiss_modals()
        page.screenshot(path="/tmp/t5_productline.png")
        print(f"  API calls: {len(api_calls)}")
        for c in api_calls:
            print(f"    {c}")
        metrics_calls = [c for c in api_calls if "metrics/core" in c]
        cbg_calls = [c for c in metrics_calls if "dept=CBG" in c]
        print(f"  metrics/core: {len(metrics_calls)}, dept=CBG: {len(cbg_calls)}")
        if cbg_calls and len(cbg_calls) == len(metrics_calls):
            print("  *** PASS ***")
        else:
            print("  *** FAIL ***")

        for t in page.locator(".ant-tag").all():
            txt = t.inner_text()
            if "部门" in txt or "CBG" in txt:
                print(f"  Orange tag: '{txt}'")

        # Step 6: Switch to customer
        print("\n=== Step 6: Switch to customer ===")
        api_calls.clear()
        selects = page.locator(".ant-select").all()
        safe_click(selects[3])
        page.wait_for_timeout(500)
        options = page.locator(".ant-select-item-option").all()
        for o in options:
            if "客户" in o.inner_text():
                o.click()
                break
        page.wait_for_timeout(5000)
        dismiss_modals()
        page.screenshot(path="/tmp/t6_customer.png")
        print(f"  API calls: {len(api_calls)}")
        for c in api_calls:
            print(f"    {c}")
        metrics_calls = [c for c in api_calls if "metrics/core" in c]
        cbg_calls = [c for c in metrics_calls if "dept=CBG" in c]
        print(f"  metrics/core: {len(metrics_calls)}, dept=CBG: {len(cbg_calls)}")
        if cbg_calls and len(cbg_calls) == len(metrics_calls):
            print("  *** PASS ***")
        else:
            print("  *** FAIL ***")

        browser.close()

run()
