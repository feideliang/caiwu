#!/bin/bash
# Run API tests
BASE="http://localhost:8000/api/v1"

echo "=== Login ==="
LOGIN_RESP=$(curl -s -X POST $BASE/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}')
echo "$LOGIN_RESP"
TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('access_token',''))")
echo "Token length: ${#TOKEN}"

echo ""
echo "=== Dashboard BFF ==="
curl -s -X POST $BASE/dashboard/bff -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"device_type":"web"}'

echo ""
echo "=== Transactions Anomalies ==="
curl -s "$BASE/transactions/anomalies" -H "Authorization: Bearer $TOKEN"

echo ""
echo "=== Drilldown Summary ==="
curl -s "$BASE/drilldowns/2026-03/summary" -H "Authorization: Bearer $TOKEN"

echo ""
echo "=== Drilldown Departments ==="
curl -s "$BASE/drilldowns/2026-03/departments" -H "Authorization: Bearer $TOKEN"