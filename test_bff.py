import json, urllib.request, urllib.error

# Step 1: Login
login_data = json.dumps({"username": "admin", "password": "admin123"}).encode('utf-8')
req = urllib.request.Request(
    'http://localhost:8012/api/v1/auth/login',
    data=login_data,
    headers={'Content-Type': 'application/json; charset=utf-8'},
    method='POST'
)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode('utf-8'))['data']['access_token']
print(f"Token obtained: {token[:20]}...")

# Step 2: BFF with product filter
body = json.dumps({
    'period': '2026-04',
    'period_dimension': 'monthly',
    'period_compare_type': 'yoy',
    'product': 'SMB产品部',
    'bypass_cache': True
}).encode('utf-8')

req = urllib.request.Request(
    'http://localhost:8012/api/v1/dashboard/bff',
    data=body,
    headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {token}',
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f'HTTP Status: {resp.status}')
        print(f'Response code: {data.get("code")}, message: {data.get("message")}')

        kpis = data.get('data', {}).get('kpis', {})
        revenue = kpis.get('revenue', None)
        print()
        print(f'kpis.revenue value: {revenue}')
        print(f'kpis.revenue is non-null/non-zero: {revenue is not None and revenue != 0}')

        print()
        print('--- All KPI values ---')
        for k, v in kpis.items():
            if k == 'trend_series':
                print(f'  {k}: [{len(v)} items]')
            else:
                print(f'  {k}: {v}')

except urllib.error.HTTPError as e:
    print(f'HTTP Status: {e.code}')
    body_text = e.read().decode('utf-8')
    print(body_text)
