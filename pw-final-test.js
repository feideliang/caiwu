const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const failedRequests = [];

  // Intercept all network responses
  page.on('response', response => {
    const status = response.status();
    const url = response.url();
    if (status >= 400) {
      failedRequests.push({
        method: response.request().method(),
        url,
        urlPath: new URL(url).pathname,
        status
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

  // Test 1: Dashboard page
  console.log('\n=== TEST 1: DASHBOARD PAGE ===');
  failedRequests.length = 0;
  await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  const dashboardErrors = failedRequests.filter(r => r.urlPath.includes('dashboard'));
  console.log(`Dashboard page - ${dashboardErrors.length} failed requests`);
  dashboardErrors.forEach(e => console.log(`  ${e.method} ${e.urlPath} -> ${e.status}`));

  // Check KPI values
  const kpiValues = await page.evaluate(() => {
    const cards = document.querySelectorAll('.ant-card');
    return Array.from(cards).map(c => c.innerText.substring(0, 100)).slice(0, 6);
  });
  console.log(`KPI cards found: ${kpiValues.length}`);
  kpiValues.forEach((c, i) => console.log(`  Card ${i}: ${c.replace(/\n/g, ' | ')}`));

  // Test 2: Drilldown page
  console.log('\n=== TEST 2: DRILLDOWN PAGE ===');
  failedRequests.length = 0;
  await page.goto('http://localhost:3000/drilldown/default', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  const drilldownErrors = failedRequests.filter(r => r.urlPath.includes('drilldown'));
  console.log(`Drilldown page - ${drilldownErrors.length} failed requests`);
  drilldownErrors.forEach(e => console.log(`  ${e.method} ${e.urlPath} -> ${e.status}`));

  // Check for 404 on specific URLs
  console.log('\n=== SPECIFIC URL CHECKS ===');
  const dashboardBffFailed = failedRequests.some(r => r.urlPath.includes('dashboard/bff'));
  const drilldownProductsFailed = failedRequests.some(r => r.urlPath.includes('drilldowns/default/products'));
  console.log(`POST /api/v1/dashboard/bff failed: ${dashboardBffFailed}`);
  console.log(`GET /api/v1/drilldowns/default/products failed: ${drilldownProductsFailed}`);

  // Test backend directly
  console.log('\n=== BACKEND API DIRECT TESTS ===');
  const backendToken = token;

  // Test dashboard/bff
  const dbRes = await fetch('http://localhost:8000/api/v1/dashboard/bff', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${backendToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ device_type: 'web' })
  });
  console.log(`POST /api/v1/dashboard/bff -> ${dbRes.status}`);
  if (dbRes.status === 200) {
    const dbData = await dbRes.json();
    console.log(`  KPIs: revenue=${dbData.data?.kpis?.revenue}, gross_profit=${dbData.data?.kpis?.gross_profit}`);
  }

  // Test drilldowns summary
  const drillRes = await fetch('http://localhost:8000/api/v1/drilldowns/2020-05/summary', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${backendToken}` }
  });
  console.log(`GET /api/v1/drilldowns/2020-05/summary -> ${drillRes.status}`);
  if (drillRes.status === 200) {
    const drillData = await drillRes.json();
    console.log(`  total_revenue=${drillData.data?.total_revenue}`);
  }

  // Test drilldowns departments
  const deptRes = await fetch('http://localhost:8000/api/v1/drilldowns/2020-05/departments', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${backendToken}` }
  });
  console.log(`GET /api/v1/drilldowns/2020-05/departments -> ${deptRes.status}`);

  // Check database metric names
  console.log('\n=== DATABASE CHECK ===');
  const dbCheck = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' })
  });
  const { Worker } = require('child_process');
  const { execSync } = require('child_process');
  try {
    const result = execSync('D:/workspace/caiwu04/.venv/Scripts/python.exe -c "import asyncio,asyncpg; asyncio.run((lambda: asyncpg.connect(\'postgresql://learnhouse:learnhouse@localhost:5432/caiwu\'))())"', { encoding: 'utf8' });
  } catch (e) {}

  // Summary
  console.log('\n=== FINAL SUMMARY ===');
  const allFailed = failedRequests.length;
  console.log(`Total failed requests (4xx/5xx): ${allFailed}`);
  if (allFailed > 0) {
    console.log('Failed requests:');
    failedRequests.forEach(r => console.log(`  ${r.method} ${r.urlPath} -> ${r.status}`));
  }

  const dashboardLayoutCount = await page.evaluate(async () => {
    // Check if there are any dashboard errors
    return 0;
  });

  await browser.close();
  process.exit(0);
})();
