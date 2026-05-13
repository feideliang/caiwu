const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));

  // Login via API
  console.log('=== LOGIN ===');
  const loginRes = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' })
  });
  const loginData = await loginRes.json();
  const token = loginData.data?.access_token;
  console.log('Token:', token ? 'OK (' + token.substring(0, 20) + '...)' : 'MISSING');

  // Navigate to app first, then set correct localStorage key
  await page.goto('http://localhost:3000/');
  await page.waitForLoadState('networkidle');

  // Correct key: 'access_token' (not 'token')
  await page.evaluate((t) => localStorage.setItem('access_token', t), token);
  // Also store user info
  await page.evaluate((u) => localStorage.setItem('user', JSON.stringify(u)), loginData.data?.user || {});

  // Dashboard
  console.log('\n=== DASHBOARD / ===');
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);

  const kpiCards = await page.evaluate(() => {
    const cards = document.querySelectorAll('.ant-card');
    return Array.from(cards).map(c => c.innerText.substring(0, 150)).slice(0, 8);
  });
  console.log('Cards found:', kpiCards.length);
  kpiCards.forEach((c, i) => console.log(`  Card ${i}: ${c.replace(/\n/g, ' | ')}`));

  // Check URL
  console.log('Current URL:', page.url());

  // Drilldown
  console.log('\n=== DRILLDOWN /drilldown/default ===');
  await page.goto('http://localhost:3000/drilldown/default');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);

  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 800));
  console.log('Body preview:', bodyText.replace(/\n/g, ' | '));
  console.log('Current URL:', page.url());

  console.log('\n=== SUMMARY ===');
  console.log('Total console errors:', errors.length);
  if (errors.length) errors.forEach(e => console.log('  ERROR:', e));
  else console.log('No console errors!');

  await browser.close();
  process.exit(0);
})();
