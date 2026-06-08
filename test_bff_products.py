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

# Test different product values
products = ["SMB产品部", "SMB", "企业产品部", "数据中心产品部", "网络产品部", "无线产品部", "安全产品部", "ALL"]
for p in products:
    body = json.dumps({
        'period': '2026-04',
        'period_dimension': 'monthly',
        'period_compare_type': 'yoy',
        'product': p,
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
            revenue = data.get('data', {}).get('kpis', {}).get('revenue', None)
            print(f'  product="{p}" -> revenue={revenue}')
    except Exception as e:
        print(f'  product="{p}" -> ERROR: {e}')
