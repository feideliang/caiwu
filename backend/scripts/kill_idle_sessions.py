"""Terminate idle-in-transaction sessions blocking the ALTER TABLE."""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='caiwu',
                        user='learnhouse', password='learnhouse')
cur = conn.cursor()

# Find all idle-in-transaction sessions
cur.execute("""
SELECT pid, state, query_start, substring(query, 1, 80) AS query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY query_start
""")
rows = cur.fetchall()
print(f"Found {len(rows)} idle-in-transaction sessions:")
for r in rows:
    print(f"  PID={r[0]}, since={r[2]}: {r[3]}")

# Terminate them
for r in rows:
    pid = r[0]
    try:
        cur.execute(f"SELECT pg_terminate_backend({pid})")
        print(f"  Terminated PID {pid}")
    except Exception as e:
        print(f"  Failed to terminate PID {pid}: {e}")

conn.commit()
cur.close()
conn.close()
print("Done.")