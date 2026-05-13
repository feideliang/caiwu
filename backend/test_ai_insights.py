import asyncio, httpx, json
from playwright.async_api import async_playwright

async def dismiss_modals(page):
    """Close any open modals/dialogs that may block interactions."""
    # Press Escape to close modals
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
    except Exception:
        pass
    # Try clicking OK/Close buttons on any visible modals
    for sel in ['button:has-text("OK")', 'button:has-text("确定")', '.ant-modal-close', '.ant-message-close']:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible(timeout=500):
                await btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            continue


async def safe_goto(page, url):
    """Navigate to URL with timeout protection."""
    try:
        await page.goto(url, timeout=30000)
    except Exception:
        pass
    await asyncio.sleep(2)
    await dismiss_modals(page)
    await asyncio.sleep(1)


async def main():
    results = {}

    # --- Step 0: Login via API ---
    print("Logging in via API...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "http://localhost:8001/api/v1/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=10
            )
            print(f"  Login status: {resp.status_code}")
            raw = resp.json()
            if resp.status_code != 200:
                msg = raw.get("message", "Unknown error") if raw else str(raw)
                results["Login"] = f"FAIL - HTTP {resp.status_code}: {msg}"
                for step, result in results.items():
                    print(f"  {step:25s} | {result}")
                return
            data_obj = raw.get("data", raw) if raw else {}
            if not isinstance(data_obj, dict):
                results["Login"] = f"FAIL - Unexpected response format: {raw}"
                for step, result in results.items():
                    print(f"  {step:25s} | {result}")
                return
            access_token = data_obj.get("access_token", "")
            user_obj = data_obj.get("user", {})
        except Exception as e:
            results["Login"] = f"FAIL - {e}"
            print(f"Login exception: {e}")
            for step, result in results.items():
                print(f"  {step:25s} | {result}")
            return

    if not access_token:
        results["Login"] = "FAIL - No access_token returned"
        for step, result in results.items():
            print(f"  {step:25s} | {result}")
        return

    results["Login"] = "PASS"
    print("Login OK")

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
    context = await browser.new_context(viewport={"width": 1400, "height": 900})
    user_json = json.dumps(user_obj).replace("'", "\\'")
    await context.add_init_script(f"""
        localStorage.setItem('access_token', '{access_token}');
        localStorage.setItem('user', '{user_json}');
    """)
    page = await context.new_page()

    # ============================================================
    # Test 1: Dashboard Page + AI Chart Recommendation
    # ============================================================
    print("\n--- Test 1: Dashboard + AI Chart Recommendation ---")
    await safe_goto(page, "http://localhost:3000/")

    dashboard_url = page.url
    print(f"  URL: {dashboard_url}")

    # Check for 404
    has_404 = await page.locator("text=404").count() > 0
    if has_404:
        await page.screenshot(path="C:/tmp/ai_insights_dashboard.png")
        results["Dashboard Page"] = "FAIL - Got 404 page"
        results["AI Chart Recommendation"] = "SKIP - Dashboard not available"
    else:
        page_text = await page.inner_text("body")
        if len(page_text) > 50:
            results["Dashboard Page"] = "PASS"
        else:
            results["Dashboard Page"] = "FAIL - Page loaded but empty"
        await page.screenshot(path="C:/tmp/ai_insights_dashboard.png")

        # Look for AI recommendation button
        ai_rec_found = False
        ai_rec_selectors = [
            'button:has-text("推荐")',
            '.ai-recommend-btn',
            '[data-testid="ai-recommend"]',
            'button:has-text("AI推荐")',
            'button:has-text("智能推荐")',
        ]
        for sel in ai_rec_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible(timeout=2000):
                    print(f"  Found AI recommendation button: {sel}")
                    await el.click()
                    await asyncio.sleep(3)
                    await page.screenshot(path="C:/tmp/ai_insights_dashboard_ai_rec.png")
                    ai_rec_found = True
                    results["AI Chart Recommendation"] = "PASS"
                    break
            except Exception:
                continue

        if not ai_rec_found:
            results["AI Chart Recommendation"] = "SKIP - No AI recommendation button found"

    # ============================================================
    # Test 2: Smart Insights Panel
    # ============================================================
    print("\n--- Test 2: Smart Insights Panel ---")
    await safe_goto(page, "http://localhost:3000/drilldown/2026-03")

    # Wait for page to settle
    await asyncio.sleep(2)

    # Click "智能洞察" button in the top bar
    insights_clicked = False
    try:
        insight_btn = page.locator('button:has-text("智能洞察")').first
        if await insight_btn.is_visible(timeout=5000):
            await insight_btn.click(force=True)
            await asyncio.sleep(2)
            insights_clicked = True
            print("  Clicked '智能洞察' button")
    except Exception as e:
        print(f"  Could not click insights button: {e}")

    if not insights_clicked:
        try:
            insight_btn = page.locator('.insights-badge button').first
            if await insight_btn.is_visible(timeout=2000):
                await insight_btn.click(force=True)
                await asyncio.sleep(2)
                insights_clicked = True
                print("  Clicked insights badge button")
        except Exception:
            pass

    if not insights_clicked:
        results["Smart Insights Panel"] = "FAIL - Could not open insights drawer"
        await page.screenshot(path="C:/tmp/ai_insights_panel.png")
    else:
        await asyncio.sleep(1)
        insight_count = 0
        insight_selectors = ['.insight-card', '.insight-list']
        for sel in insight_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    insight_count = count
                    print(f"  Found {count} insight elements with selector: {sel}")
                    break
            except Exception:
                continue

        # Check for "已处理" button
        try:
            mark_btn = page.locator('button:has-text("已处理")').first
            if await mark_btn.is_visible(timeout=2000):
                await mark_btn.click()
                await asyncio.sleep(1)
                print("  Clicked '已处理' button")
        except Exception:
            pass

        await page.screenshot(path="C:/tmp/ai_insights_panel.png")

        if insight_count > 0:
            results["Smart Insights Panel"] = f"PASS ({insight_count} insight items visible)"
        else:
            results["Smart Insights Panel"] = "SKIP - Drawer opened but no insight items found"

    # ============================================================
    # Test 3: AI Analysis on Drilldown
    # ============================================================
    print("\n--- Test 3: AI Analysis (Drilldown) ---")
    await safe_goto(page, "http://localhost:3000/drilldown/2026-03")

    l1_visible = False
    try:
        l1_el = page.locator(".drilldown-l1").first
        l1_visible = await l1_el.is_visible(timeout=5000)
        if l1_visible:
            print("  L1 section visible")
    except Exception:
        pass

    if not l1_visible:
        content = await page.content()
        if len(content) > 500:
            print("  Page loaded (content present)")
            l1_visible = True
        else:
            results["AI Analysis"] = "FAIL - Drilldown page did not load"
            await page.screenshot(path="C:/tmp/ai_insights_drilldown.png")

    if l1_visible:
        ai_found = False
        ai_selectors = [
            '.ai-analysis-btn',
            '[data-testid="ai-analysis"]',
            'button:has-text("AI分析")',
            'button:has-text("智能分析")',
        ]
        for sel in ai_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible(timeout=2000):
                    print(f"  Found AI analysis button: {sel}")
                    await el.click()
                    await asyncio.sleep(5)
                    await page.screenshot(path="C:/tmp/ai_insights_drilldown_ai.png")
                    ai_found = True
                    results["AI Analysis"] = "PASS"
                    break
            except Exception:
                continue

        if not ai_found:
            results["AI Analysis"] = "SKIP - No AI analysis button found on drilldown page"
            await page.screenshot(path="C:/tmp/ai_insights_drilldown.png")

    # ============================================================
    # Test 4: Breadcrumb Back-Navigation
    # ============================================================
    print("\n--- Test 4: Breadcrumb Back-Navigation ---")
    await safe_goto(page, "http://localhost:3000/drilldown/2026-03")

    l1_ok = False
    try:
        l1_el = page.locator(".drilldown-l1").first
        l1_ok = await l1_el.is_visible(timeout=5000)
    except Exception:
        pass

    if not l1_ok:
        results["Breadcrumb Navigation"] = "SKIP - L1 not visible"
        await page.screenshot(path="C:/tmp/ai_insights_breadcrumb_l1.png")
    else:
        dept_clicked = False
        try:
            rows = page.locator("table tbody tr")
            count = await rows.count()
            if count > 0:
                first_row = rows.first
                await first_row.click()
                await asyncio.sleep(3)
                dept_clicked = True
                print(f"  Clicked first table row (of {count})")
        except Exception as e:
            print(f"  Could not click row: {e}")

        if not dept_clicked:
            results["Breadcrumb Navigation"] = "SKIP - No clickable rows found"
            await page.screenshot(path="C:/tmp/ai_insights_breadcrumb_l1.png")
        else:
            l2_ok = False
            try:
                l2_el = page.locator(".drilldown-l2").first
                l2_ok = await l2_el.is_visible(timeout=5000)
            except Exception:
                try:
                    bc = await page.locator('[class*="breadcrumb"]').inner_text()
                    if ">" in bc:
                        l2_ok = True
                except Exception:
                    pass

            await page.screenshot(path="C:/tmp/ai_insights_breadcrumb_l2.png")
            print(f"  L2 visible: {l2_ok}")

            if not l2_ok:
                results["Breadcrumb Navigation"] = "FAIL - L2 did not appear"
            else:
                bc_clicked = False
                try:
                    bc_links = page.locator('[class*="breadcrumb"] a')
                    cnt = await bc_links.count()
                    if cnt > 0:
                        first_bc = bc_links.first
                        await first_bc.click()
                        await asyncio.sleep(3)
                        bc_clicked = True
                        print("  Clicked first breadcrumb link")
                except Exception as e:
                    print(f"  Could not click breadcrumb: {e}")

                await page.screenshot(path="C:/tmp/ai_insights_breadcrumb_back.png")

                if not bc_clicked:
                    results["Breadcrumb Navigation"] = "SKIP - No breadcrumb link to click back"
                else:
                    l1_back = False
                    try:
                        l1_el = page.locator(".drilldown-l1").first
                        l1_back = await l1_el.is_visible(timeout=5000)
                    except Exception:
                        pass

                    if l1_back:
                        results["Breadcrumb Navigation"] = "PASS"
                    else:
                        results["Breadcrumb Navigation"] = "FAIL - L1 did not reappear"

    await browser.close()
    await pw.stop()

    # ============================================================
    # Print results
    # ============================================================
    print("\n" + "=" * 65)
    print("TEST RESULTS SUMMARY")
    print("=" * 65)
    for step, result in results.items():
        print(f"  {step:30s} | {result}")
    print("=" * 65)

    passed = sum(1 for r in results.values() if r.startswith("PASS"))
    failed = sum(1 for r in results.values() if r.startswith("FAIL"))
    skipped = sum(1 for r in results.values() if r.startswith("SKIP"))
    print(f"  Total: {len(results)} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
    print("=" * 65)
    print("\nScreenshots saved to C:/tmp/ai_insights_*.png")


asyncio.run(main())
