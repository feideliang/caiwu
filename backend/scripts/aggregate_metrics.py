"""
聚合脚本: income_margin_detail → 3 张小聚合表
TRUNCATE + INSERT...SELECT，per-bgbu + 'ALL' 全局
"""
import asyncio
import time
import asyncpg

DSN = "postgresql://learnhouse:learnhouse@localhost:5432/caiwu"

DDL = """
CREATE TABLE IF NOT EXISTS agg_period_summary (
    period VARCHAR(10) NOT NULL,
    bgbu VARCHAR(64) NOT NULL DEFAULT 'ALL',
    revenue NUMERIC(20,2) DEFAULT 0,
    cost NUMERIC(20,2) DEFAULT 0,
    gross_profit NUMERIC(20,2) DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    direct_sign_revenue NUMERIC(20,2) DEFAULT 0,
    direct_sign_cost NUMERIC(20,2) DEFAULT 0,
    direct_sign_gp NUMERIC(20,2) DEFAULT 0,
    target_revenue NUMERIC(20,2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (period, bgbu)
);

CREATE TABLE IF NOT EXISTS agg_dimension_summary (
    period VARCHAR(10) NOT NULL,
    bgbu VARCHAR(64) NOT NULL DEFAULT 'ALL',
    dim_type VARCHAR(32) NOT NULL,
    dim_value VARCHAR(512) NOT NULL,
    revenue NUMERIC(20,2) DEFAULT 0,
    cost NUMERIC(20,2) DEFAULT 0,
    gross_profit NUMERIC(20,2) DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (period, bgbu, dim_type, dim_value)
);
CREATE INDEX IF NOT EXISTS idx_ads_period_dim ON agg_dimension_summary(period, dim_type);
CREATE INDEX IF NOT EXISTS idx_ads_dimtype_bgbu ON agg_dimension_summary(dim_type, bgbu, period);

CREATE TABLE IF NOT EXISTS agg_order_summary (
    period VARCHAR(10) NOT NULL,
    bgbu VARCHAR(64) NOT NULL DEFAULT 'ALL',
    order_id VARCHAR(128) NOT NULL,
    dim_dept VARCHAR(256),
    dim_product VARCHAR(128),
    revenue NUMERIC(20,2) DEFAULT 0,
    cost NUMERIC(20,2) DEFAULT 0,
    gross_profit NUMERIC(20,2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (period, bgbu, order_id)
);
CREATE INDEX IF NOT EXISTS idx_aos_period ON agg_order_summary(period);
CREATE INDEX IF NOT EXISTS idx_aos_period_bgbu ON agg_order_summary(period, bgbu);
"""

AGG_PERIOD = """
INSERT INTO agg_period_summary (period, bgbu, revenue, cost, gross_profit, order_count,
    direct_sign_revenue, direct_sign_cost, direct_sign_gp)
SELECT period, bgbu,
    COALESCE(SUM(revenue_amount), 0), COALESCE(SUM(cost_amount), 0),
    COALESCE(SUM(gross_profit_amount), 0),
    COUNT(DISTINCT COALESCE(order_id, contract_no)),
    COALESCE(SUM(revenue_amount) FILTER (WHERE superior_name IN (SELECT DISTINCT superior_name FROM income_margin_detail WHERE contract_type_merged = '直签' AND superior_name IS NOT NULL)), 0),
    COALESCE(SUM(cost_amount) FILTER (WHERE superior_name IN (SELECT DISTINCT superior_name FROM income_margin_detail WHERE contract_type_merged = '直签' AND superior_name IS NOT NULL)), 0),
    COALESCE(SUM(gross_profit_amount) FILTER (WHERE superior_name IN (SELECT DISTINCT superior_name FROM income_margin_detail WHERE contract_type_merged = '直签' AND superior_name IS NOT NULL)), 0)
FROM income_margin_detail WHERE bgbu IS NOT NULL
GROUP BY period, bgbu
UNION ALL
SELECT period, 'ALL',
    COALESCE(SUM(revenue_amount), 0), COALESCE(SUM(cost_amount), 0),
    COALESCE(SUM(gross_profit_amount), 0),
    COUNT(DISTINCT COALESCE(order_id, contract_no)),
    COALESCE(SUM(revenue_amount) FILTER (WHERE superior_name IN (SELECT DISTINCT superior_name FROM income_margin_detail WHERE contract_type_merged = '直签' AND superior_name IS NOT NULL)), 0),
    COALESCE(SUM(cost_amount) FILTER (WHERE superior_name IN (SELECT DISTINCT superior_name FROM income_margin_detail WHERE contract_type_merged = '直签' AND superior_name IS NOT NULL)), 0),
    COALESCE(SUM(gross_profit_amount) FILTER (WHERE superior_name IN (SELECT DISTINCT superior_name FROM income_margin_detail WHERE contract_type_merged = '直签' AND superior_name IS NOT NULL)), 0)
FROM income_margin_detail
GROUP BY period
"""

AGG_DIMENSION = """
INSERT INTO agg_dimension_summary (period, bgbu, dim_type, dim_value, revenue, cost, gross_profit, order_count)
SELECT period, bgbu, 'product_line', product_line,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE bgbu IS NOT NULL AND product_line IS NOT NULL
GROUP BY period, bgbu, product_line
UNION ALL
SELECT period, 'ALL', 'product_line', product_line,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE product_line IS NOT NULL
GROUP BY period, product_line
UNION ALL
SELECT period, bgbu, 'sales_product', sales_product_name,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE bgbu IS NOT NULL AND sales_product_name IS NOT NULL
GROUP BY period, bgbu, sales_product_name
UNION ALL
SELECT period, 'ALL', 'sales_product', sales_product_name,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE sales_product_name IS NOT NULL
GROUP BY period, sales_product_name
UNION ALL
SELECT period, bgbu, 'customer', superior_name,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE bgbu IS NOT NULL AND superior_name IS NOT NULL
GROUP BY period, bgbu, superior_name
UNION ALL
SELECT period, 'ALL', 'customer', superior_name,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE superior_name IS NOT NULL
GROUP BY period, superior_name
UNION ALL
SELECT period, bgbu, 'contract_type', contract_type_merged,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE bgbu IS NOT NULL AND contract_type_merged IS NOT NULL
GROUP BY period, bgbu, contract_type_merged
UNION ALL
SELECT period, 'ALL', 'contract_type', contract_type_merged,
    COALESCE(SUM(revenue_amount),0), COALESCE(SUM(cost_amount),0),
    COALESCE(SUM(gross_profit_amount),0),
    COUNT(DISTINCT COALESCE(order_id, contract_no))
FROM income_margin_detail WHERE contract_type_merged IS NOT NULL
GROUP BY period, contract_type_merged
"""

AGG_ORDER = """
INSERT INTO agg_order_summary (period, bgbu, order_id, dim_dept, dim_product, revenue, cost, gross_profit)
SELECT period, bgbu, COALESCE(order_id, contract_no),
    MAX(sales_department), MAX(product_line),
    COALESCE(SUM(revenue_amount), 0), COALESCE(SUM(cost_amount), 0),
    COALESCE(SUM(gross_profit_amount), 0)
FROM income_margin_detail
WHERE bgbu IS NOT NULL AND COALESCE(order_id, contract_no) IS NOT NULL
GROUP BY period, bgbu, COALESCE(order_id, contract_no)
UNION ALL
SELECT period, 'ALL', COALESCE(order_id, contract_no),
    MAX(sales_department), MAX(product_line),
    COALESCE(SUM(revenue_amount), 0), COALESCE(SUM(cost_amount), 0),
    COALESCE(SUM(gross_profit_amount), 0)
FROM income_margin_detail
WHERE COALESCE(order_id, contract_no) IS NOT NULL
GROUP BY period, COALESCE(order_id, contract_no)
"""


async def main():
    t0 = time.time()
    conn = await asyncpg.connect(DSN)

    # Create tables
    print("Creating tables...")
    await conn.execute(DDL)
    print("  Done")

    # Truncate
    print("Truncating...")
    await conn.execute("TRUNCATE agg_period_summary, agg_dimension_summary, agg_order_summary")
    print("  Done")

    # Aggregate
    print("Aggregating period_summary...")
    t1 = time.time()
    r = await conn.execute(AGG_PERIOD)
    print(f"  {r} [{time.time()-t1:.1f}s]")

    print("Aggregating dimension_summary...")
    t1 = time.time()
    r = await conn.execute(AGG_DIMENSION)
    print(f"  {r} [{time.time()-t1:.1f}s]")

    print("Aggregating order_summary...")
    t1 = time.time()
    r = await conn.execute(AGG_ORDER)
    print(f"  {r} [{time.time()-t1:.1f}s]")

    # Verify
    print("\n=== Verification ===")
    for t in ["agg_period_summary", "agg_dimension_summary", "agg_order_summary"]:
        cnt = await conn.fetchval(f"SELECT count(*) FROM {t}")
        all_cnt = await conn.fetchval(f"SELECT count(*) FROM {t} WHERE bgbu='ALL'")
        print(f"  {t}: {cnt:,} rows ({all_cnt} ALL)")

    # Check per-bgbu sums vs ALL for period_summary
    print("\n  Period revenue check (2026-03):")
    all_rev = await conn.fetchval(
        "SELECT revenue FROM agg_period_summary WHERE period='2026-03' AND bgbu='ALL'"
    )
    sum_rev = await conn.fetchval(
        "SELECT SUM(revenue) FROM agg_period_summary WHERE period='2026-03' AND bgbu!='ALL'"
    )
    print(f"    ALL={all_rev:,.2f}, SUM(per-bgbu)={sum_rev:,.2f}, match={abs(float(all_rev)-float(sum_rev))<1}")

    await conn.close()
    print(f"\nDone! [{time.time()-t0:.1f}s]")


if __name__ == "__main__":
    asyncio.run(main())
