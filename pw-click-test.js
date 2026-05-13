const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const failedRequests = [];
  const clickTargets = [];

  // Intercept all network responses
  page.on('response', response => {
    const status = response.status();
    if (status >= 400) {
      const url = response.url();
      const method = response.request().method();
      failedRequests.push({
        method,
        url,
        status,
        urlPath: new URL(url).pathname,
      });
    }
  });

  // Login via API
  console.log('=== LOGIN ===');
  const loginRes = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' })
  });
  const loginData = await loginRes.json();
  const token = loginData.data?.access_token;
  console.log('Token:', token ? 'OK' : 'MISSING');

  // Navigate to app
  await page.goto('http://localhost:3000/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  // Set auth
  await page.evaluate((t) => localStorage.setItem('access_token', t), token);
  await page.evaluate((u) => localStorage.setItem('user', JSON.stringify(u)), loginData.data?.user || {});

  console.log('\n=== COLLECTING CLICK TARGETS ===');

  // Find all clickable elements
  const clickables = await page.evaluate(() => {
    const elements = document.querySelectorAll('a, button, [role="button"], .ant-menu-item, .ant-menu-submenu, .ant-dropdown-menu-item, [class*="menu"], [class*="nav"]');
    const seen = new Set();
    const results = [];

    elements.forEach(el => {
      const text = el.innerText?.trim().substring(0, 50) || '';
      const href = el.href || '';
      const tag = el.tagName.toLowerCase();
      const className = el.className || '';
      const key = `${tag}-${text}-${href}`;
      if (!seen.has(key) && (text || href)) {
        seen.add(key);
        results.push({ text, href, tag, className: className.substring(0, 100) });
      }
    });
    return results;
  });

  console.log(`Found ${clickables.length} clickable elements:`);
  clickables.slice(0, 30).forEach((c, i) => {
    console.log(`  [${i}] ${c.tag.toUpperCase()}: "${c.text}" -> ${c.href}`);
    clickTargets.push(c);
  });

  console.log('\n=== CLICKING NAVIGATION ITEMS ===');

  // Go to homepage first
  await page.goto('http://localhost:3000/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  // Click sidebar menu items if they exist
  const menuItems = await page.$$('[class*="ant-menu-item"]');
  console.log(`Found ${menuItems.length} ant-menu-item elements`);

  for (let i = 0; i < Math.min(menuItems.length, 20); i++) {
    try {
      const text = await menuItems[i].innerText();
      console.log(`  Clicking menu item ${i}: "${text}"`);
      await menuItems[i].click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);
    } catch (e) {
      // skip
    }
  }

  // Try known routes
  const routes = [
    '/drilldown/default',
    '/drilldown',
    '/dashboard',
    '/reports',
    '/predictions',
    '/insights',
    '/filters',
    '/correlations',
    '/transactions',
    '/data-sources',
    '/data-quality',
    '/uploads',
    '/audit',
    '/system',
    '/notifications',
    '/ai',
  ];

  console.log('\n=== NAVIGATING TO KNOWN ROUTES ===');
  for (const route of routes) {
    const beforeCount = failedRequests.length;
    console.log(`\nNavigating to ${route}...`);
    try {
      await page.goto(`http://localhost:3000${route}`, { waitUntil: 'networkidle', timeout: 10000 });
      await page.waitForTimeout(2000);

      const title = await page.title();
      const url = page.url();
      console.log(`  URL: ${url}, Title: ${title}`);

      // Check for console errors on this page
      const pageErrors = [];
      page.on('pageerror', err => pageErrors.push(err.message));

      // Try clicking visible buttons on this page
      const buttons = await page.$$('button');
      for (const btn of buttons.slice(0, 5)) {
        try {
          const btnText = await btn.innerText();
          if (btnText && btnText.trim()) {
            await btn.click();
            await page.waitForTimeout(500);
          }
        } catch (e) {}
      }

      const newErrors = failedRequests.slice(beforeCount);
      if (newErrors.length > 0) {
        console.log(`  New failures on this page:`);
        newErrors.forEach(e => console.log(`    ${e.method} ${e.urlPath} -> ${e.status}`));
      }
    } catch (e) {
      console.log(`  Navigation error: ${e.message}`);
    }
  }

  console.log('\n=== SUMMARY ===');
  console.log(`Total failed requests (4xx/5xx): ${failedRequests.length}`);

  // Group by URL pattern
  const byUrl = {};
  failedRequests.forEach(r => {
    const key = `${r.method} ${r.urlPath}`;
    if (!byUrl[key]) byUrl[key] = [];
    byUrl[key].push(r.status);
  });

  console.log('\nFailed requests grouped by URL:');
  for (const [url, statuses] of Object.entries(byUrl)) {
    console.log(`  ${url}: [${statuses.join(', ')}]`);
  }

  console.log('\nAll failed requests:');
  failedRequests.forEach((r, i) => {
    console.log(`  [${i}] ${r.method} ${r.url} -> ${r.status}`);
  });

  await browser.close();
  process.exit(0);
})();
