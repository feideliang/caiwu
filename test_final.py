"""Final verification: full flow with step-by-step API and rendering check."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    reqs = []
    def on_request(req):
        if "/api/v1/metrics/core" in req.url:
            qs = parse_qs(urlparse(req.url).query)
            reqs.append(qs)
            print(f"  >>> dim={qs.get('dimension',[''])[0]:15s} dept={qs.get('department',[''])[0]:10s} entity={qs.get('entity',[''])[0]:10s}")

    resp_data = {}
    def on_response(resp):
        if "/api/v1/metrics/core" in resp.url and resp.status == 200:
            try:
                j = resp.json()
                s = j.get("data",{}).get("summary",{})
                ma = s.get("margin_change_analysis",[])
                bd = j.get("data",{}).get("breakdowns",[])
                resp_data[resp.url[:120]] = {"margin_items": len(ma), "breakdowns": len(bd), "revenue": s.get("revenue")}
            except: pass

    page.on("request", on_request)
    page.on("response", on_response)

    # Login
    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    reqs.clear()
    resp_data.clear()

    # Step 1: 选择部门
    print("=== 1. 选择部门 ===")
    page.locator(".ant-select").nth(3).click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "部门" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)

    # Step 2: 选择 CBG
    print("=== 2. 选择 CBG ===")
    reqs.clear()
    page.locator(".ant-select").nth(4).click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "CBG" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(3000)

    # Step 3: 切换到产品线
    print("=== 3. 切换到产品线 ===")
    reqs.clear()
    page.locator(".ant-select").nth(3).click()
    page.wait_for_timeout(500)
    for o in page.locator(".ant-select-item-option").all():
        if "产品线" in o.inner_text():
            o.click(); break
    page.wait_for_timeout(5000)

    print(f"\n请求数: {len(reqs)}")
    for i, qs in enumerate(reqs):
        print(f"  [{i}] dept={qs.get('department',[''])[0]} dim={qs.get('dimension',[''])[0]} entity={qs.get('entity',[''])[0]}")

    # 检查页面表格
    print("\n=== 毛利率变动拆解明细表 ===")
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"行数: {len(rows)}")
    for i, row in enumerate(rows[:6]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            vals = [c.inner_text()[:20] for c in cells[1:4]]
            print(f"  {vals}")

    # 检查橙色标签
    tags = [t.inner_text() for t in page.locator(".ant-tag").all()]
    print(f"\n标签: {tags}")

    # 检查集中度面板
    titles = [el.inner_text() for el in page.locator(".ant-card-head-title").all() if "集中度" in el.inner_text() or "Top" in el.inner_text()]
    print(f"集中度面板: {titles}")

    # 截图
    page.screenshot(path="/tmp/final_check.png")
    browser.close()
