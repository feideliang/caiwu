"""
从 income_margin_detail 大宽表同步维度表（幂等）。

使用 INSERT ... ON CONFLICT (DO UPDATE) 实现 upsert 语义。
可独立运行，也可被 Celery 任务调用。

用法:
  python scripts/sync_dimensions.py                    # 同步全部
  python scripts/sync_dimensions.py --dry-run          # 仅预览
  python scripts/sync_dimensions.py --table customer   # 仅同步指定表
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── SQL upsert statements ──────────────────────────────────────

# Each dimension: GROUP BY business key → MIN/MAX for attributes → ON CONFLICT upsert

UPSERT_CUSTOMER = """
INSERT INTO dim_customer (
    customer_name, ncc_customer_code, invoice_customer, invoice_name,
    final_customer, superior_name, contract_type, contract_type_merged,
    customer_supplied_original, customer_supplied_other, province,
    first_seen_period, last_seen_period
)
SELECT
    w.invoice_customer AS customer_name,
    MIN(w.ncc_customer_code) AS ncc_customer_code,
    MIN(w.invoice_customer) AS invoice_customer,
    MIN(w.invoice_name) AS invoice_name,
    MIN(w.final_customer) AS final_customer,
    MIN(w.superior_name) AS superior_name,
    MIN(w.contract_type) AS contract_type,
    MIN(w.contract_type_merged) AS contract_type_merged,
    MIN(w.customer_supplied_original) AS customer_supplied_original,
    MIN(w.customer_supplied_other) AS customer_supplied_other,
    MIN(w.province) AS province,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.invoice_customer IS NOT NULL
GROUP BY w.invoice_customer
ON CONFLICT (customer_name) DO UPDATE SET
    ncc_customer_code        = EXCLUDED.ncc_customer_code,
    invoice_customer         = EXCLUDED.invoice_customer,
    invoice_name             = EXCLUDED.invoice_name,
    final_customer           = EXCLUDED.final_customer,
    superior_name            = EXCLUDED.superior_name,
    contract_type            = EXCLUDED.contract_type,
    contract_type_merged     = EXCLUDED.contract_type_merged,
    customer_supplied_original = EXCLUDED.customer_supplied_original,
    customer_supplied_other  = EXCLUDED.customer_supplied_other,
    province                 = EXCLUDED.province,
    first_seen_period        = LEAST(dim_customer.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_customer.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

UPSERT_PRODUCT = """
INSERT INTO dim_product (
    product_code, product_name, category, classification,
    bu_code, bu_name, bgbu, org, series, product_bgbu, family,
    material_code, material_desc, material_cost_category,
    first_seen_period, last_seen_period
)
SELECT
    w.sales_product_code AS product_code,
    MIN(w.sales_product_name) AS product_name,
    MIN(w.product_category) AS category,
    MIN(w.product_classification) AS classification,
    MIN(w.product_bu_code) AS bu_code,
    MIN(w.product_bu_name) AS bu_name,
    MIN(w.product_bgbu) AS bgbu,
    MIN(w.product_org) AS org,
    MIN(w.series) AS series,
    MIN(w.product_bgbu) AS product_bgbu,
    MIN(w.product_family) AS family,
    MIN(w.material_code) AS material_code,
    MIN(w.material_desc) AS material_desc,
    MIN(w.material_cost_category) AS material_cost_category,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.sales_product_code IS NOT NULL
GROUP BY w.sales_product_code
ON CONFLICT (product_code) DO UPDATE SET
    product_name             = EXCLUDED.product_name,
    category                 = EXCLUDED.category,
    classification           = EXCLUDED.classification,
    bu_code                  = EXCLUDED.bu_code,
    bu_name                  = EXCLUDED.bu_name,
    bgbu                     = EXCLUDED.bgbu,
    org                      = EXCLUDED.org,
    series                   = EXCLUDED.series,
    product_bgbu             = EXCLUDED.product_bgbu,
    family                   = EXCLUDED.family,
    material_code            = EXCLUDED.material_code,
    material_desc            = EXCLUDED.material_desc,
    material_cost_category   = EXCLUDED.material_cost_category,
    first_seen_period        = LEAST(dim_product.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_product.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

UPSERT_ORGANIZATION = """
INSERT INTO dim_organization (
    entity_name, company, hr_dept_code, hr_department,
    sales_department, bgbu, business_type, region,
    first_seen_period, last_seen_period
)
SELECT
    w.entity AS entity_name,
    MIN(w.company) AS company,
    MIN(w.hr_dept_code) AS hr_dept_code,
    MIN(w.hr_department) AS hr_department,
    MIN(w.sales_department) AS sales_department,
    MIN(w.bgbu) AS bgbu,
    MIN(w.business_type) AS business_type,
    MIN(w.region) AS region,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.entity IS NOT NULL
GROUP BY w.entity
ON CONFLICT (entity_name) DO UPDATE SET
    company                  = EXCLUDED.company,
    hr_dept_code             = EXCLUDED.hr_dept_code,
    hr_department            = EXCLUDED.hr_department,
    sales_department         = EXCLUDED.sales_department,
    bgbu                     = EXCLUDED.bgbu,
    business_type            = EXCLUDED.business_type,
    region                   = EXCLUDED.region,
    first_seen_period        = LEAST(dim_organization.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_organization.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

UPSERT_PROJECT = """
INSERT INTO dim_project (
    project_name, application_scenario, summary_name,
    first_seen_period, last_seen_period
)
SELECT
    w.project_name,
    MIN(w.application_scenario) AS application_scenario,
    MIN(w.summary_name) AS summary_name,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.project_name IS NOT NULL
GROUP BY w.project_name
ON CONFLICT (project_name) DO UPDATE SET
    application_scenario     = EXCLUDED.application_scenario,
    summary_name             = EXCLUDED.summary_name,
    first_seen_period        = LEAST(dim_project.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_project.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

COUNT_CUSTOMER     = "SELECT COUNT(*) FROM dim_customer;"
COUNT_PRODUCT      = "SELECT COUNT(*) FROM dim_product;"
COUNT_ORGANIZATION = "SELECT COUNT(*) FROM dim_organization;"
COUNT_PROJECT      = "SELECT COUNT(*) FROM dim_project;"

SYNC_TABLES = {
    "customer":     (UPSERT_CUSTOMER,     COUNT_CUSTOMER,     "dim_customer"),
    "product":      (UPSERT_PRODUCT,      COUNT_PRODUCT,      "dim_product"),
    "organization": (UPSERT_ORGANIZATION, COUNT_ORGANIZATION, "dim_organization"),
    "project":      (UPSERT_PROJECT,      COUNT_PROJECT,      "dim_project"),
}


# ── Helpers ─────────────────────────────────────────────────────

DRY_RUN_SQL = {
    "customer":     "SELECT COUNT(DISTINCT invoice_customer) FROM income_margin_detail WHERE invoice_customer IS NOT NULL",
    "product":      "SELECT COUNT(DISTINCT sales_product_code) FROM income_margin_detail WHERE sales_product_code IS NOT NULL",
    "organization": "SELECT COUNT(DISTINCT entity) FROM income_margin_detail WHERE entity IS NOT NULL",
    "project":      "SELECT COUNT(DISTINCT project_name) FROM income_margin_detail WHERE project_name IS NOT NULL",
}


# ── Main ───────────────────────────────────────────────────────

async def sync(table: str | None = None, dry_run: bool = False) -> dict:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://learnhouse:learnhouse@localhost:5432/caiwu",
    )
    conn = await asyncpg.connect(database_url)
    t0 = time.time()

    try:
        tables_to_sync = {table: SYNC_TABLES[table]} if table else SYNC_TABLES
        results = {}

        for tbl, (upsert_sql, count_sql, display_name) in tables_to_sync.items():
            print(f"Syncing {display_name}...")
            t1 = time.time()

            if dry_run:
                src_count = await conn.fetchval(DRY_RUN_SQL[tbl])
                print(f"  Would sync ~{src_count:,} unique records  [{time.time() - t1:.0f}s]")
                results[tbl] = {"status": "dry_run", "source_count": src_count}
            else:
                await conn.execute(upsert_sql)
                after = await conn.fetchval(count_sql)
                print(f"  Upserted, now {after:,} records  [{time.time() - t1:.0f}s]")
                results[tbl] = {"status": "synced", "count": after}

        print(f"\nTotal time: {time.time() - t0:.0f}s")
        return results

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Sync dimension tables from income_margin_detail wide table"
    )
    parser.add_argument("--table", choices=list(SYNC_TABLES.keys()), help="Sync only one table")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    result = asyncio.run(sync(table=args.table, dry_run=args.dry_run))
    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()