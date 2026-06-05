"""
从 income_margin_detail 大宽表同步数据到 financial_data（EAV 格式）。

每行宽表记录 → 4 条 financial_data metric：revenue / cost / gross_profit / profit_margin。
维度字段存入 tags JSON。

幂等：按 period 删除对应期间 financial_data 后再插入。

用法:
  python scripts/sync_wide_to_eav.py              # 执行同步
  python scripts/sync_wide_to_eav.py --dry-run    # 仅预览
  python scripts/sync_wide_to_eav.py --limit 100  # 仅同步前 N 行（测试用）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── Tag dimensions ──────────────────────────────────────────────

# wide-table columns that should be stored as dimension tags in financial_data
TAG_COLUMNS: dict[str, str] = {
    # Order Info
    "order_register_date": "order_register_date",
    "revenue_confirm_date": "revenue_confirm_date",
    "order_id": "order_id",
    "contract_no": "contract_no",
    "order_category": "order_category",
    "order_header_type": "order_header_type",
    "order_customer": "order_customer",
    "sequence_no": "sequence_no",
    "order_qty": "order_qty",

    # Company / HR
    "company": "company",
    "hr_dept_code": "hr_dept_code",
    "hr_department": "hr_department",
    "sales_department": "sales_department",
    "sales_person_code": "sales_person_code",
    "sales_person": "sales_person",

    # Product Hierarchy
    "product_category": "product_category",
    "product_classification": "product_classification",
    "product_bu_code": "product_bu_code",
    "product_bu_name": "product_bu_name",
    "product_bgbu": "product_line",
    "product_org": "product_org",
    "series": "series",
    "product_family": "product_family",
    "sales_product_code": "sales_product_code",
    "sales_product_name": "sales_product_name",
    "material_code": "material_code",
    "material_desc": "material_desc",
    "material_cost_category": "material_cost_category",

    # Cost Classification
    "cost_class_1": "cost_class_1",
    "cost_class_2": "cost_class_2",
    "cost_class_3": "cost_class_3",
    "cost_category": "cost_category",

    # Customer
    "ncc_customer_code": "ncc_customer_code",
    "customer": "customer",
    "invoice_customer": "invoice_customer",
    "invoice_name": "invoice_name",
    "final_customer": "final_customer",
    "superior_name": "superior_name",
    "contract_type": "contract_type",
    "contract_type_merged": "contract_type_merged",
    "customer_supplied_original": "customer_supplied_original",
    "customer_supplied_other": "customer_supplied_other",

    # Geography / Market
    "province": "province",
    "market_segment": "market_segment",
    "region": "region",
    "bgbu": "bgbu",
    "business_type": "business_type",

    # Project / Application
    "project_name": "project_name",
    "application_scenario": "application_scenario",
    "summary_name": "summary_name",

    # Invoice
    "invoice_status": "invoice_status",
    "invoice_customer_short": "invoice_customer_short",

    # Currency / Exchange
    "currency": "currency",
    "exchange_rate_local": "exchange_rate_local",
    "exchange_rate_rmb": "exchange_rate_rmb",
    "tax_rate": "tax_rate",

    # Financial (auxiliary)
    "revenue_amount_local": "revenue_amount_local",
    "revenue_amount_original": "revenue_amount_original",
    "revenue_qty": "revenue_qty",
    "unit_cost_ex_tax": "unit_cost_ex_tax",
    "unit_cost_incl_tax": "unit_cost_incl_tax",
    "cost_incl_tax": "cost_incl_tax",
    "gross_profit_incl_tax": "gross_profit_incl_tax",
    "sales_amount_incl_tax_local": "sales_amount_incl_tax_local",
    "sales_amount_incl_tax_rmb": "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original": "sales_amount_incl_tax_original",
    "tax_amount_local": "tax_amount_local",
    "sales_type": "sales_type",
    "revenue_year": "revenue_year",
    "revenue_month": "revenue_month",
    "order_amount": "order_amount",
}

from app.services.metrics_service import compute_bucket

TARGET_PERIODS: list[str] | None = None  # None = all periods
BATCH_SIZE = 50_000
FETCH_SIZE = 10_000  # how many wide-table rows to fetch per iteration


# ── Database operations ────────────────────────────────────────

async def delete_target_metrics(conn) -> int:
    """Delete financial_data rows for TARGET_PERIODS."""
    result = await conn.execute(
        "DELETE FROM financial_data WHERE period = ANY($1::varchar[])",
        TARGET_PERIODS,
    )
    parts = result.split()
    return int(parts[1]) if len(parts) == 2 and parts[0] == "DELETE" else 0


async def verify_data(conn):
    """Post-sync verification."""
    count = await conn.fetchval("SELECT COUNT(*) FROM financial_data")
    print(f"  Total rows in financial_data: {count:,}")

    periods = await conn.fetch(
        "SELECT period, COUNT(*) AS cnt FROM financial_data "
        "WHERE metric_name = 'revenue' GROUP BY period ORDER BY period",
    )
    print(f"  Revenue rows by period ({len(periods)}):")
    for p in periods:
        print(f"    {p['period']}: {p['cnt']:,}")

    metrics = await conn.fetch(
        "SELECT metric_name, COUNT(*), ROUND(SUM(metric_value)::numeric, 2) AS total "
        "FROM financial_data WHERE period LIKE '2025-%' "
        "GROUP BY metric_name ORDER BY metric_name",
    )
    print(f"  2025 metrics summary:")
    for m in metrics:
        print(f"    {m['metric_name']}: count={m['count']:,}, sum={m['total']:,.2f}")

    # Check wide table ↔ EAV consistency
    wide_revenue = await conn.fetchval(
        "SELECT SUM(revenue_amount) FROM income_margin_detail WHERE period LIKE '2025-%'",
    )
    eav_revenue = await conn.fetchval(
        "SELECT SUM(metric_value) FROM financial_data "
        "WHERE period LIKE '2025-%' AND metric_name = 'revenue'",
    )
    print(f"  Wide table revenue sum: {wide_revenue:,.2f}" if wide_revenue else "  Wide table revenue: NULL")
    print(f"  EAV revenue sum:        {eav_revenue:,.2f}" if eav_revenue else "  EAV revenue: NULL")

    for yr in ("2024", "2026"):
        c = await conn.fetchval(
            "SELECT COUNT(*) FROM financial_data WHERE period LIKE $1", f"{yr}-%"
        )
        print(f"  {yr} data preserved: {c:,} rows")


# ── Main ───────────────────────────────────────────────────────

async def sync(dry_run: bool = False, limit: int | None = None) -> dict:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://learnhouse:learnhouse@localhost:5432/caiwu",
    )
    conn = await asyncpg.connect(database_url)
    t0 = time.time()

    try:
        # ── 1. Fetch wide-table rows ──
        query = """
            SELECT * FROM income_margin_detail
            WHERE period = ANY($1::varchar[])
            ORDER BY id
        """
        # For limit in dry-run mode, use a subquery with LIMIT
        if limit:
            query = f"""
                SELECT * FROM income_margin_detail
                WHERE id IN (
                    SELECT id FROM income_margin_detail
                    WHERE period = ANY($1::varchar[])
                    ORDER BY id
                    LIMIT {limit}
                )
                ORDER BY id
            """
        rows = await conn.fetch(query, TARGET_PERIODS)
        print(f"Fetched {len(rows):,} wide-table rows  [{time.time() - t0:.0f}s]")

        if not rows:
            print("No data to sync!")
            return {"status": "empty"}

        # ── 2. Build metric records ──
        all_metrics: list[tuple] = []
        skipped = 0
        period_counts: dict[str, int] = defaultdict(int)

        for row in rows:
            period = row["period"]
            entity = row["entity"]

            revenue = float(row["revenue_amount"] or 0)
            cost = float(row["cost_amount"] or 0)

            gp = float(row["gross_profit_amount"] or 0)
            if gp == 0 and revenue != 0:
                gp = revenue - cost

            margin = float(row["gross_margin_pct"] or 0)
            if margin == 0 and revenue > 0:
                margin = (gp / revenue) * 100

            # Build tags from TAG_COLUMNS
            tags = {}
            for eng_col, tag_key in TAG_COLUMNS.items():
                val = row.get(eng_col)
                if val is not None and val != "":
                    if isinstance(val, (int, float)):
                        tags[tag_key] = val
                    else:
                        s = str(val).strip()
                        if s:
                            tags[tag_key] = s

            tags_json = json.dumps(tags, ensure_ascii=False)

            # Build raw_row for traceability
            raw_row = json.dumps({"wide_id": row["id"]}, ensure_ascii=False)

            all_metrics.extend([
                ("revenue",       round(revenue, 2), "CNY", period, entity, tags_json, raw_row),
                ("cost",          round(cost, 2),    "CNY", period, entity, tags_json, raw_row),
                ("gross_profit",  round(gp, 2),      "CNY", period, entity, tags_json, raw_row),
                ("profit_margin", round(margin, 2),  "%",   period, entity, tags_json, raw_row),
            ])
            period_counts[period] += 1

        elapsed = time.time() - t0
        print(f"Built {len(all_metrics):,} metric records from {len(rows):,} wide rows  [{elapsed:.0f}s]")
        print(f"Periods: {sorted(period_counts.keys())}")

        if dry_run:
            print("\n=== DRY RUN — no database changes ===")
            return {"status": "dry_run", "wide_rows": len(rows), "metrics": len(all_metrics)}

        if not all_metrics:
            print("No records to insert!")
            return {"status": "error", "message": "No records"}

        # ── 3. Delete existing metrics ──
        print(f"\nDeleting existing financial_data for {TARGET_PERIODS[0]} ~ {TARGET_PERIODS[-1]}...")
        t1 = time.time()
        deleted = await delete_target_metrics(conn)
        print(f"Deleted {deleted:,} rows  [{time.time() - t1:.0f}s]")

        # ── 4. Batch insert ──
        print(f"Inserting {len(all_metrics):,} metrics in batches of {BATCH_SIZE:,}...")
        total = 0
        t2 = time.time()
        for i in range(0, len(all_metrics), BATCH_SIZE):
            batch = all_metrics[i: i + BATCH_SIZE]
            await conn.copy_records_to_table(
                "financial_data",
                columns=["metric_name", "metric_value", "metric_unit", "period", "entity", "tags", "raw_row"],
                records=batch,
            )
            total += len(batch)
            print(f"  Inserted {total:,}/{len(all_metrics):,}  [{time.time() - t2:.0f}s]")

        # ── 5. Verify ──
        print(f"\n=== Verification ===")
        await verify_data(conn)

    finally:
        await conn.close()

    total_elapsed = time.time() - t0
    print(f"\nDone! {len(all_metrics):,} metrics from {len(rows):,} wide rows  [{total_elapsed:.0f}s]")
    return {"status": "success", "metrics": len(all_metrics), "wide_rows": len(rows)}


def main():
    parser = argparse.ArgumentParser(
        description="Sync income_margin_detail wide table to financial_data EAV"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--limit", type=int, default=None, help="Limit wide-table rows for testing")
    args = parser.parse_args()

    result = asyncio.run(sync(dry_run=args.dry_run, limit=args.limit))
    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()