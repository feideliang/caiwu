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

# Get BFF without filter to see department breakdown values
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

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    print('=== department_breakdown ===')
    for item in data.get('data', {}).get('department_breakdown', []):
        dv = item.get('dimension_value', '')
        rev = item.get('revenue', 0)
        print(f'  {dv}: revenue={rev}')
