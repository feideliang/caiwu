"""Screenshot the metrics page after selecting department=CBG to see all filter controls."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

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

    # Screenshot 1: initial page with all controls
    page.screenshot(path="D:\\workspace\\caiwu04\\screenshot_1_initial.png", full_page=False)

    # Step 1: Select department
    selects = page.locator(".ant-select").all()
    safe_click(selects[3])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "部门" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Screenshot 2: after selecting department dimension
    page.screenshot(path="D:\\workspace\\caiwu04\\screenshot_2_department.png", full_page=False)

    # Step 2: Select CBG
    selects = page.locator(".ant-select").all()
    safe_click(selects[4])
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)
    dismiss_modals()

    # Screenshot 3: after selecting CBG - show all controls visible now
    page.screenshot(path="D:\\workspace\\caiwu04\\screenshot_3_cbg.png", full_page=False)

    # List ALL interactive elements in the header area
    print("=== All interactive elements in header ===")
    elements = page.evaluate("""() => {
        const header = document.querySelector('.ant-page-header-extra') || document.querySelector('.analysis-header');
        if (!header) return 'no header found';
        const items = [];
        header.querySelectorAll('.ant-select, .ant-btn, .ant-tag, .ant-picker, input').forEach((el, i) => {
            const rect = el.getBoundingClientRect();
            items.push({
                index: i,
                tag: el.tagName,
                class: el.className.substring(0, 60),
                text: el.innerText?.substring(0, 30) || el.value || '',
                visible: rect.width > 0 && rect.height > 0,
                x: Math.round(rect.x),
                w: Math.round(rect.width)
            });
        });
        return items;
    }""")
    for e in elements:
        vis = "Y" if e.get("visible") else "N"
        print(f"  [{e['index']:2d}] {vis} x={e['x']:4d} w={e['w']:3d} {e['tag']:8s} {e['text'][:25]}")

    # Also check if there's a cross-dimension selector visible
    cross = page.locator(".ant-select").all()
    print(f"\nTotal .ant-select elements: {len(cross)}")
    for i, s in enumerate(cross):
        txt = s.inner_text()[:40]
        rect = s.bounding_box()
        vis = "Y" if rect and rect["width"] > 0 else "N"
        print(f"  [{i}] {vis} '{txt}'")

    browser.close()
