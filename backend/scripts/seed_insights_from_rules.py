"""Seed rule-based insights from actual financial_data using InsightRuleService.

Deletes old mock insights (generated_by='ai') and generates fresh insights
based on real data rules (毛利率异常, 趋势, 客户/产品集中度等).

Usage:
    cd backend && python scripts/seed_insights_from_rules.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Must configure settings before importing app modules
os.environ.setdefault("APP_ENV", "development")


async def main():
    """Main async entry point."""
    # Import app modules after environment is configured
    from app.db.session import async_session_factory
    from app.services.metrics_service import MetricsService
    from app.services.insight_rule_service import InsightRuleService
    from app.models.v3 import Insight
    from sqlalchemy import select, delete, func

    async with async_session_factory() as db:
        # ── 1. Generate insights from rules with actual data ──
        print("Fetching core metrics for company dimension...")
        metrics = await MetricsService.get_core_metrics(db=db, dimension="company")

        print("Fetching core metrics for customer dimension...")
        customer_metrics = await MetricsService.get_core_metrics(
            db=db, dimension="customer"
        )

        print("Fetching core metrics for product_line dimension...")
        product_metrics = await MetricsService.get_core_metrics(
            db=db, dimension="product_line"
        )

        print("Generating rule-based insights...")
        rule_items = InsightRuleService.generate_insights(
            metrics,
            customer_breakdowns=customer_metrics.breakdowns,
            product_breakdowns=product_metrics.breakdowns,
        )

        print(f"\nGenerated {len(rule_items)} rule-based insights:")
        for item in rule_items:
            meta = item.get("data_json", {})
            print(
                f"  - [{item['type']}] {item['title']} "
                f"(severity={item['severity']}, "
                f"rule={meta.get('rule_code')}, "
                f"period={meta.get('period')})"
            )

        if not rule_items:
            print(
                "WARNING: No rule insights generated. "
                "Check if financial_data has sufficient data."
            )
            return

        # ── 2. Delete old mock insights ──
        old_count = await db.execute(
            select(func.count()).select_from(Insight).where(Insight.generated_by == "ai")
        )
        old_n = old_count.scalar_one()
        if old_n > 0:
            print(f"\nDeleting {old_n} old mock insights (generated_by='ai')...")
            await db.execute(delete(Insight).where(Insight.generated_by == "ai"))
            print("Old mock insights deleted.")

        # ── 3. Save new rule-based insights ──
        # Get existing rule insight keys to avoid duplicates
        existing_stmt = select(Insight).where(Insight.generated_by == "rule")
        existing_rows = (await db.execute(existing_stmt)).scalars().all()
        existing_keys: set[str] = set()
        for row in existing_rows:
            meta = row.data_json or {}
            key = f"{meta.get('rule_code')}:{meta.get('period')}:{meta.get('dimension')}:{meta.get('dimension_value')}"
            existing_keys.add(key)

        saved = 0
        skipped = 0
        for item in rule_items:
            meta = item.get("data_json", {})
            key = f"{meta.get('rule_code')}:{meta.get('period')}:{meta.get('dimension')}:{meta.get('dimension_value')}"
            if key in existing_keys:
                skipped += 1
                continue

            # _serialize_insight() reads severity/confidence/description/related_metric
            # from data_json, but _build_insight() puts them at the top level.
            # Merge them into data_json so the insight renders correctly from DB.
            meta = dict(item.get("data_json", {}))
            for key in ("severity", "confidence", "description", "related_metric"):
                if key in item and key not in meta:
                    meta[key] = item[key]

            insight = Insight(
                title=item["title"],
                insight_type=item["type"],
                content=item.get("description", ""),
                data_json=meta,
                generated_by="rule",
                created_by=None,
            )
            db.add(insight)
            saved += 1

        await db.flush()  # Assign IDs
        await db.commit()

        print(f"\nSaved {saved} new rule-based insights, skipped {skipped} duplicates.")

        # ── 4. Final summary ──
        total = await db.execute(
            select(func.count()).select_from(Insight)
        )
        print(f"\nTotal insight records in DB: {total.scalar_one()}")
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())