import json, urllib.request

# Login
login_data = json.dumps({"username": "admin", "password": "admin123"}).encode('utf-8')
req = urllib.request.Request(
    'http://localhost:8012/api/v1/auth/login',
    data=login_data,
    headers={'Content-Type': 'application/json; charset=utf-8'},
    method='POST'
)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode('utf-8'))['data']['access_token']

# Try filters endpoint to see available product values
for endpoint in ['/api/v1/filters/products', '/api/v1/filters', '/api/v1/dashboard/bff']:
    if endpoint == '/api/v1/dashboard/bff':
        # Try BFF without product filter to get breakdowns
        body = json.dumps({
            'period': '2026-04',
            'period_dimension': 'monthly',
            'period_compare_type': 'yoy',
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
                print('=== product_breakdown from BFF (no filter) ===')
                for item in data.get('data', {}).get('product_breakdown', []):
                    dv = item.get('dimension_value', '')
                    rev = item.get('revenue', 0)
                    print(f'  {dv}: revenue={rev}')
        except Exception as e:
            print(f'  {endpoint}: ERROR: {e}')
    else:
        req = urllib.request.Request(
            f'http://localhost:8012{endpoint}',
            headers={'Authorization': f'Bearer {token}'},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f'  {endpoint}: {json.dumps(data, ensure_ascii=False)[:300]}')
        except Exception as e:
            print(f'  {endpoint}: ERROR: {e}')
