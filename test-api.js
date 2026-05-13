const http = require('http');

function request(method, path, token, body) {
  return new Promise((resolve) => {
    const options = {
      hostname: 'localhost',
      port: 8000,
      path: '/api/v1' + path,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {})
      }
    };
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, body: data }); }
      });
    });
    req.on('error', () => resolve({ status: 0, body: null }));
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

(async () => {
  // Login
  const login = await request('POST', '/auth/login', null, { username: 'admin', password: 'admin123' });
  const token = login.body?.data?.access_token || '';
  console.log('Token:', token ? 'OK (' + token.substring(0, 20) + '...)' : 'MISSING');

  // Dashboard BFF
  const bff = await request('POST', '/dashboard/bff', token, { device_type: 'web' });
  const kpis = bff.body?.data?.kpis || {};
  console.log('Dashboard BFF: code=' + bff.status + ' revenue=' + kpis.revenue + ' gross_profit=' + kpis.gross_profit + ' trend_series=' + (kpis.trend_series?.length || 0));

  // Anomalies
  const anom = await request('GET', '/transactions/anomalies', token, null);
  console.log('Anomalies: code=' + anom.status + ' count=' + (anom.body?.data?.length || 0));

  // Drilldown summary
  const sum = await request('GET', '/drilldowns/2026-03/summary', token, null);
  console.log('Drilldown summary: code=' + sum.status + ' data=' + JSON.stringify(sum.body?.data));

  // Drilldown departments
  const depts = await request('GET', '/drilldowns/2026-03/departments', token, null);
  console.log('Drilldown departments: code=' + depts.status + ' count=' + (depts.body?.data?.length || 0));
})();