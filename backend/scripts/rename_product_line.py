import psycopg2
import sys

def check_and_alter():
    conn = psycopg2.connect(host='localhost', port=5432, dbname='caiwu',
                            user='learnhouse', password='learnhouse')
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 60000")  # 60s timeout

    cur.execute("""SELECT column_name FROM information_schema.columns
        WHERE table_name='income_margin_detail'
        AND column_name IN ('product_bgbu','product_bgbu')
        ORDER BY column_name""")
    cols = [r[0] for r in cur.fetchall()]
    print(f"Found columns: {cols}")

    if 'product_bgbu' in cols:
        print("Dropping product_bgbu...")
        cur.execute("ALTER TABLE income_margin_detail DROP COLUMN product_bgbu")
        print("  done")
    if 'product_bgbu' in cols:
        print("Renaming product_bgbu -> product_bgbu...")
        cur.execute("ALTER TABLE income_margin_detail RENAME COLUMN product_bgbu TO product_bgbu")
        print("  done")

    conn.commit()

    cur.execute("""SELECT column_name, character_maximum_length
        FROM information_schema.columns
        WHERE table_name='income_margin_detail' AND column_name='product_bgbu'""")
    r = cur.fetchone()
    print(f"Verified: {r}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_and_alter()