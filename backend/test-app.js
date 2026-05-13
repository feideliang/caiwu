const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`[CONSOLE ERROR] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => {
    errors.push(`[PAGE ERROR] ${err.message}`);
  });

  let jwtToken = null;

  // 1. Login
  console.log('=== TEST 1: Login ===');
  try {
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Check if login form exists
    const usernameInput = page.locator('input[type="text"], input[name="username"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (await usernameInput.isVisible()) {
      await usernameInput.fill('admin');
      await passwordInput.fill('admin123');
      await page.locator('button[type="submit"], button:has-text("登录")').first().click();
      await page.waitForTimeout(3000);
    }

    // Try to capture JWT from localStorage or API
    const storage = await page.evaluate(() => {
      return {
        localStorage: { ...localStorage },
        sessionStorage: { ...sessionStorage }
      };
    });

    // Check for token in localStorage
    for (const key of Object.keys(storage.localStorage)) {
      if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth')) {
        jwtToken = storage.localStorage[key];
        console.log(`Found token in localStorage: ${key}`);
      }
    }

    console.log('Login page loaded');
  } catch (err) {
    console.log(`Login error: ${err.message}`);
  }

  // 2. Dashboard/Home page
  console.log('\n=== TEST 2: Dashboard/Home Page ===');
  try {
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    const title = await page.title();
    console.log(`Page title: ${title}`);

    // Check for KPI cards
    const kpiCards = await page.locator('[class*="card"], [class*="kpi"], [class*="metric"]').count();
    console.log(`Found ${kpiCards} potential KPI/metric cards`);

    // Check for charts
    const charts = await page.locator('[class*="chart"], [class*="echarts"], canvas').count();
    console.log(`Found ${charts} chart elements`);

    // Check visible error messages
    const errorElements = await page.locator('[class*="error"], .ant-result-title, [role="alert"]').allTextContents();
    if (errorElements.length > 0) {
      console.log(`Error elements found: ${errorElements.join(', ')}`);
    }

    if (errors.length > 0) {
      console.log(`Console errors: ${errors.join('; ')}`);
    } else {
      console.log('No console errors detected');
    }

    errors.length = 0; // Reset for next page
  } catch (err) {
    console.log(`Dashboard error: ${err.message}`);
  }

  // 3. Drilldown page
  console.log('\n=== TEST 3: Drilldown Page ===');
  try {
    await page.goto('http://localhost:3000/drilldown/default', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);

    const title = await page.title();
    console.log(`Page title: ${title}`);
    console.log(`URL: ${page.url()}`);

    // Check for tables or data grids
    const tables = await page.locator('table, [class*="table"], [class*="data"]').count();
    console.log(`Found ${tables} table/data elements`);

    if (errors.length > 0) {
      console.log(`Console errors: ${errors.join('; ')}`);
    } else {
      console.log('No console errors detected');
    }

    errors.length = 0;
  } catch (err) {
    console.log(`Drilldown error: ${err.message}`);
  }

  // 4. Check navigation items
  console.log('\n=== TEST 4: Navigation Items ===');
  try {
    // Go back to home first
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Find navigation links
    const navLinks = await page.locator('nav a, [class*="menu"] a, .ant-menu-item, header a').allTextContents();
    console.log(`Found nav links: ${navLinks.slice(0, 10).join(', ')}`);

    // Try to click on a few nav items if visible
    const navItems = page.locator('[class*="menu"] a, [role="menuitem"]');
    const count = await navItems.count();
    console.log(`Total nav items: ${count}`);

    if (count > 1) {
      // Click second nav item
      await navItems.nth(1).click();
      await page.waitForTimeout(2000);
      console.log(`Navigated to: ${page.url()}`);
    }

    if (errors.length > 0) {
      console.log(`Console errors: ${errors.join('; ')}`);
    } else {
      console.log('No console errors detected');
    }

    errors.length = 0;
  } catch (err) {
    console.log(`Navigation error: ${err.message}`);
  }

  // Final summary
  console.log('\n=== SUMMARY ===');
  console.log('All tests completed.');

  await browser.close();
})();