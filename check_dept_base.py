import json
with open('/d/workspace/caiwu04/response_dept_base.json') as f:
    d = json.load(f)
s = d['data']['summary']
print('=== SUMMARY ===')
print('revenue:', s['revenue'])
print('base_revenue:', s['base_revenue'])
print()
print('=== BREAKDOWNS ===')
bds = d['data'].get('breakdowns', [])
if not bds:
    print('(empty - no breakdowns)')
else:
    for b in bds:
        print(b['dimension_value'], 'rev:', b['revenue'])
print()
print('=== COUNT ===')
print('total breakdowns:', len(bds))