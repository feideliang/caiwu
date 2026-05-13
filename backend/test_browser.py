import asyncio
from playwright.async_api import async_playwright
import json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzc4NDkwMjI0LCJyb2xlIjoiYWRtaW4ifQ.gI30KWBtyWbVl5ZtfyVsxowAKhpVRUZZBTe6Kg_MqbY"
USER = json.dumps({"id":1,"username":"admin","email":"admin@test.com","role":"admin","is_active":True})

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1400, 'height': 900})
        await context.add_init_script(f"""
            localStorage.setItem('access_token', '{TOKEN}');
            localStorage.setItem('user', {USER});
        """)
        page = await context.new_page()

        print('Navigating to drilldown page...')
        await page.goto('http://localhost:3000/drilldown/2026-03', wait_until='domcontentloaded')
        await asyncio.sleep(5)

        # Step 1: Check L1
        print('\n=== L1 Check ===')
        l1_count = await page.locator('.drilldown-l1').count()
        print(f'L1 card visible: {l1_count > 0}')
        dept_rows = page.locator('.drilldown-l1 .ant-table-tbody .ant-table-row')
        dept_count = await dept_rows.count()
        print(f'Department rows: {dept_count}')
        if dept_count > 0:
            first_dept = await dept_rows.first.locator('td').first.inner_text()
            print(f'First dept: {first_dept}')

        await page.screenshot(path='screenshot_l1.png', full_page=True)
        print('Screenshot: screenshot_l1.png')

        if dept_count > 0:
            # Step 2: Click dept -> L2
            print('\n=== Step 2: Click department -> L2 ===')
            await dept_rows.first.click()
            await asyncio.sleep(2)

            l2_count = await page.locator('.drilldown-l2').count()
            print(f'L2 card visible: {l2_count > 0}')
            prod_rows = page.locator('.drilldown-l2 .ant-table-tbody .ant-table-row')
            prod_count = await prod_rows.count()
            print(f'Product rows: {prod_count}')
            if prod_count > 0:
                first_prod = await prod_rows.first.locator('td').first.inner_text()
                print(f'First product: {first_prod}')

            await page.screenshot(path='screenshot_l2.png', full_page=True)
            print('Screenshot: screenshot_l2.png')

            if prod_count > 0:
                # Step 3: Click product -> L3
                print('\n=== Step 3: Click product -> L3 ===')
                await prod_rows.first.click()
                await asyncio.sleep(2)

                l3_count = await page.locator('.drilldown-l3').count()
                print(f'L3 card visible: {l3_count > 0}')
                rec_rows = page.locator('.drilldown-l3 .ant-table-tbody .ant-table-row')
                rec_count = await rec_rows.count()
                print(f'Record rows: {rec_count}')

                await page.screenshot(path='screenshot_l3.png', full_page=True)
                print('Screenshot: screenshot_l3.png')

                if rec_count > 0:
                    # Step 4: Click record -> L4
                    print('\n=== Step 4: Click record -> L4 ===')
                    await rec_rows.first.click()
                    await asyncio.sleep(2)

                    l4_count = await page.locator('.drilldown-l4').count()
                    print(f'L4 card visible: {l4_count > 0}')
                    modal_count = await page.locator('.ant-modal').count()
                    print(f'Modal visible: {modal_count > 0}')

                    await page.screenshot(path='screenshot_l4.png', full_page=True)
                    print('Screenshot: screenshot_l4.png')

                    # Step 5: Breadcrumb back
                    print('\n=== Step 5: Breadcrumb back to L1 ===')
                    first_crumb = page.locator('.ant-breadcrumb a').first
                    crumb_count = await first_crumb.count()
                    print(f'Clickable breadcrumbs: {crumb_count}')
                    if crumb_count > 0:
                        await first_crumb.click()
                        await asyncio.sleep(1)
                        l1_after = await page.locator('.drilldown-l1').count()
                        print(f'Back to L1: {l1_after > 0}')

        print('\n=== ALL DONE ===')
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())
