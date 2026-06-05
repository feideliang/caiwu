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

# Test with department="SMB产品部" (which uses bgbu_filter=SMB产品部, should work)
body = json.dumps({
    'period': '2026-04',
    'period_dimension': 'monthly',
    'period_compare_type': 'yoy',
    'department': 'SMB产品部',
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
        kpis = data.get('data', {}).get('kpis', {})
        print(f'department="SMB产品部" -> revenue={kpis.get("revenue")}')
except Exception as e:
    print(f'department="SMB产品部" -> ERROR: {e}')

# Now test product="SMB产品部" with department="SMB产品部" to see if it works with non-ALL bgbu
body2 = json.dumps({
    'period': '2026-04',
    'period_dimension': 'monthly',
    'period_compare_type': 'yoy',
    'product': 'SMB产品部',
    'department': 'SMB产品部',  # non-ALL bgbu_filter
    'bypass_cache': True
}).encode('utf-8')

req2 = urllib.request.Request(
    'http://localhost:8012/api/v1/dashboard/bff',
    data=body2,
    headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {token}',
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req2) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        kpis = data.get('data', {}).get('kpis', {})
        print(f'product="SMB产品部" + department="SMB产品部" -> revenue={kpis.get("revenue")}')
except Exception as e:
    print(f'product="SMB产品部" + department="SMB产品部" -> ERROR: {e}')
