"""Check for locks blocking ALTER TABLE on income_margin_detail."""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='caiwu',
                        user='learnhouse', password='learnhouse')
cur = conn.cursor()

# Check for locks on the table
cur.execute("""
SELECT l.locktype, l.relation::regclass AS relname,
       l.mode, l.granted, l.pid,
       a.query_start, a.state, substring(a.query, 1, 100) AS query
FROM pg_locks l
JOIN pg_stat_activity a ON a.pid = l.pid
WHERE l.relation::regclass = 'income_margin_detail'::regclass
   OR l.locktype = 'relation'
ORDER BY l.granted, l.pid
""")
rows = cur.fetchall()
if rows:
    print("=== Locks on income_margin_detail ===")
    for r in rows:
        print(f"  PID={r[3]}, granted={r[4]}, mode={r[2]}, state={r[6]}")
        print(f"  Query: {r[7]}")
        print()
else:
    print("No locks found on the table.")

# Check PG version
cur.execute("SELECT version()")
print(f"PG version: {cur.fetchone()[0]}")

# Check table size
cur.execute("SELECT pg_size_pretty(pg_total_relation_size('income_margin_detail'))")
print(f"Table size: {cur.fetchone()[0]}")

cur.close()
conn.close()