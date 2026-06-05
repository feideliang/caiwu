"""Transaction analysis service — uses aggregated tables instead of financial_data."""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import AggPeriodSummary, AggDimensionSummary, AggOrderSummary

# AR amount still needs financial_data since it is not in agg tables.
# Import only for the narrow AR-lookup used in get_contracts.
from app.models.core import FinancialData


class TransactionService:

    async def get_contracts(
        self, db: AsyncSession, period: str | None = None,
        entity: str | None = None, page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        # Revenue and cost per customer from agg_dimension_summary (dim_type='customer')
        stmt = select(
            AggDimensionSummary.dim_value,
            AggDimensionSummary.period,
            AggDimensionSummary.revenue,
            AggDimensionSummary.cost,
        ).where(
            AggDimensionSummary.dim_type == "customer",
        )
        if period:
            stmt = stmt.where(AggDimensionSummary.period == period)
        if entity:
            stmt = stmt.where(AggDimensionSummary.dim_value == entity)
        if department:
            stmt = stmt.where(AggDimensionSummary.bgbu == department)

        result = await db.execute(stmt)
        dim_rows = result.all()

        # For AR amounts, fall back to financial_data (not in agg tables)
        # NOTE: scoped by period/entity/department to avoid full table scan
        ar_stmt = select(
            FinancialData.entity,
            FinancialData.period,
            func.sum(FinancialData.metric_value).label("ar_value"),
        ).where(
            FinancialData.metric_name == "ar_amount",
            FinancialData.entity.isnot(None),
            FinancialData.entity != "",
            FinancialData.period.isnot(None),  # avoid NULL period scans
        )
        if period:
            ar_stmt = ar_stmt.where(FinancialData.period == period)
        if entity:
            ar_stmt = ar_stmt.where(FinancialData.entity == entity)
        if department:
            ar_stmt = ar_stmt.where(FinancialData.entity == department)
        ar_stmt = ar_stmt.group_by(FinancialData.entity, FinancialData.period)
        ar_result = await db.execute(ar_stmt)
        ar_rows = ar_result.all()

        # Group by (customer, period)
        groups: dict = {}
        for r in dim_rows:
            key = (r.dim_value, r.period)
            if key not in groups:
                groups[key] = {
                    "entity": r.dim_value,
                    "total_revenue": float(r.revenue or 0),
                    "total_cost": float(r.cost or 0),
                    "total_ar": 0,
                    "total_ap": 0,
                    "net_exposure": 0,
                    "period": r.period,
                }
            else:
                groups[key]["total_revenue"] += float(r.revenue or 0)
                groups[key]["total_cost"] += float(r.cost or 0)

        for r in ar_rows:
            key = (r.entity, r.period)
            if key not in groups:
                groups[key] = {
                    "entity": r.entity,
                    "total_revenue": 0,
                    "total_cost": 0,
                    "total_ar": 0,
                    "total_ap": 0,
                    "net_exposure": 0,
                    "period": r.period,
                }
            groups[key]["total_ar"] = float(r.ar_value or 0)

        items = []
        for g in groups.values():
            g["net_exposure"] = g["total_ar"] - g["total_ap"]
            items.append(g)
        items.sort(key=lambda x: x["period"], reverse=True)

        total = len(items)
        offset = (page - 1) * page_size
        return items[offset: offset + page_size], total

    async def get_orders(
        self, db: AsyncSession, period_from: str | None = None,
        period_to: str | None = None, min_value: float | None = None,
        page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(
            AggPeriodSummary.period,
            AggPeriodSummary.revenue,
            AggPeriodSummary.cost,
            AggPeriodSummary.order_count,
        )
        if department:
            stmt = stmt.where(AggPeriodSummary.bgbu == department)
        if period_from:
            stmt = stmt.where(AggPeriodSummary.period >= period_from)
        if period_to:
            stmt = stmt.where(AggPeriodSummary.period <= period_to)

        result = await db.execute(stmt)
        rows = result.all()

        items = []
        for r in rows:
            rev = float(r.revenue or 0)
            cost = float(r.cost or 0)
            if min_value is not None and rev < min_value:
                continue
            items.append({
                "period": r.period,
                "revenue": rev,
                "cost": cost,
                "profit": rev - cost,
                "order_count": r.order_count,
            })

        items.sort(key=lambda x: x["period"], reverse=True)
        total = len(items)
        offset = (page - 1) * page_size
        return items[offset: offset + page_size], total

    async def get_projects(
        self, db: AsyncSession, entity: str | None = None,
        page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        # Use agg_dimension_summary for product_bgbu and sales_product dimensions
        stmt = select(
            AggDimensionSummary.dim_value,
            AggDimensionSummary.dim_type,
            func.sum(AggDimensionSummary.revenue).label("total_revenue"),
            func.sum(AggDimensionSummary.cost).label("total_cost"),
            func.min(AggDimensionSummary.period).label("period_start"),
            func.max(AggDimensionSummary.period).label("period_end"),
        ).where(
            AggDimensionSummary.dim_type.in_(["product_bgbu", "sales_product"]),
        )
        if entity:
            stmt = stmt.where(AggDimensionSummary.dim_value == entity)
        if department:
            stmt = stmt.where(AggDimensionSummary.bgbu == department)
        stmt = stmt.group_by(AggDimensionSummary.dim_value, AggDimensionSummary.dim_type)

        result = await db.execute(stmt)
        rows = result.all()

        groups: dict = {}
        for r in rows:
            if r.dim_value not in groups:
                groups[r.dim_value] = {
                    "entity": r.dim_value,
                    "total_revenue": 0,
                    "total_cost": 0,
                    "profit_margin": 0,
                    "period_span": f"{r.period_start} ~ {r.period_end}",
                    "dim_type": r.dim_type,
                }
            groups[r.dim_value]["total_revenue"] += float(r.total_revenue or 0)
            groups[r.dim_value]["total_cost"] += float(r.total_cost or 0)

        items = list(groups.values())
        for item in items:
            if item["total_revenue"] > 0:
                item["profit_margin"] = round(
                    (item["total_revenue"] - item["total_cost"]) / item["total_revenue"], 4
                )
        items.sort(key=lambda x: x["total_revenue"], reverse=True)

        total = len(items)
        offset = (page - 1) * page_size
        return items[offset: offset + page_size], total

    async def detect_anomalies(
        self, db: AsyncSession, threshold: float = 2.0,
        metric_names: str | None = None, period: str | None = None,
        department: str | None = None,
    ) -> list[dict]:
        # Read aggregated period-level data (few hundred rows instead of 810k)
        stmt = select(
            AggPeriodSummary.period,
            AggPeriodSummary.revenue,
            AggPeriodSummary.cost,
            AggPeriodSummary.gross_profit,
        )
        if department:
            stmt = stmt.where(AggPeriodSummary.bgbu == department)
        if period:
            stmt = stmt.where(AggPeriodSummary.period == period)

        result = await db.execute(stmt)
        rows = result.all()

        anomalies = []

        # --- Statistical anomaly detection on aggregated revenue ---
        revenue_by_period = []
        for r in rows:
            val = float(r.revenue or 0)
            if val != 0:
                revenue_by_period.append((r.period, val))

        if len(revenue_by_period) >= 3:
            values = [v for _, v in revenue_by_period]
            n = len(values)
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            stddev = sqrt(variance) if variance > 0 else 0

            if stddev > 0:
                for prd, val in revenue_by_period:
                    sigma = abs(val - mean) / stddev
                    if sigma >= threshold:
                        anomalies.append({
                            "metric_name": "revenue",
                            "period": prd,
                            "value": val,
                            "expected_mean": round(mean, 4),
                            "sigma_distance": round(sigma, 2),
                            "entity": department or "ALL",
                        })

        # Also check cost anomalies
        cost_by_period = [(r.period, float(r.cost or 0)) for r in rows if r.cost]
        if len(cost_by_period) >= 3:
            values = [v for _, v in cost_by_period]
            n = len(values)
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            stddev = sqrt(variance) if variance > 0 else 0

            if stddev > 0:
                for prd, val in cost_by_period:
                    sigma = abs(val - mean) / stddev
                    if sigma >= threshold:
                        anomalies.append({
                            "metric_name": "cost",
                            "period": prd,
                            "value": val,
                            "expected_mean": round(mean, 4),
                            "sigma_distance": round(sigma, 2),
                            "entity": department or "ALL",
                        })

        # --- Gross margin checks (from agg data) ---
        period_revenues = {}
        period_costs = {}
        for r in rows:
            period_revenues[r.period] = float(r.revenue or 0)
            period_costs[r.period] = float(r.cost or 0)

        for prd in sorted(period_revenues.keys()):
            rev = period_revenues.get(prd, 0)
            cost = period_costs.get(prd, 0)
            if rev <= 0:
                continue
            profit = rev - cost
            gm = profit / rev * 100
            if gm < 10:
                anomalies.append({
                    "metric_name": "gross_margin",
                    "period": prd,
                    "value": round(gm, 2),
                    "alert_level": "red",
                    "message": f"毛利率{gm:.2f}% < 10%，严重预警",
                })
            elif gm < 20:
                anomalies.append({
                    "metric_name": "gross_margin",
                    "period": prd,
                    "value": round(gm, 2),
                    "alert_level": "yellow",
                    "message": f"毛利率{gm:.2f}% < 20%，关注预警",
                })
            elif gm > 60:
                anomalies.append({
                    "metric_name": "gross_margin",
                    "period": prd,
                    "value": round(gm, 2),
                    "alert_level": "review",
                    "message": f"毛利率{gm:.2f}% > 60%，需复核",
                })

        # --- Consecutive growth check ---
        sorted_periods = sorted(period_revenues.keys())
        for i in range(len(sorted_periods) - 2):
            p1, p2, p3 = sorted_periods[i], sorted_periods[i + 1], sorted_periods[i + 2]
            r1 = period_revenues.get(p1, 0)
            r2 = period_revenues.get(p2, 0)
            r3 = period_revenues.get(p3, 0)
            if r1 > 0 and r2 > r1 and r3 > r2:
                anomalies.append({
                    "metric_name": "revenue",
                    "period": p3,
                    "value": round(r3, 2),
                    "alert_level": "info",
                    "message": f"连续3期收入正增长趋势: {p1}->{p2}->{p3}",
                })

        # --- Customer concentration risk ---
        cust_stmt = select(
            AggDimensionSummary.dim_value,
            func.sum(AggDimensionSummary.revenue).label("total"),
        ).where(
            AggDimensionSummary.dim_type == "customer",
        )
        if department:
            cust_stmt = cust_stmt.where(AggDimensionSummary.bgbu == department)
        cust_stmt = cust_stmt.group_by(AggDimensionSummary.dim_value)
        cust_result = await db.execute(cust_stmt)
        customer_totals = {r.dim_value: float(r.total or 0) for r in cust_result.all()}
        total_revenue = sum(customer_totals.values())
        if total_revenue > 0:
            for cust, cust_rev in customer_totals.items():
                ratio = cust_rev / total_revenue
                if ratio > 0.30:
                    anomalies.append({
                        "metric_name": "revenue",
                        "period": "overall",
                        "value": round(cust_rev, 2),
                        "alert_level": "yellow",
                        "entity": cust,
                        "message": f"客户{cust}营收占比{ratio * 100:.2f}% > 30%，集中度风险",
                    })

        anomalies.sort(key=lambda x: x.get("sigma_distance", 0), reverse=True)
        return anomalies

    async def get_large_amounts(
        self, db: AsyncSession, threshold: float = 1000000,
        page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(
            AggOrderSummary.order_id,
            AggOrderSummary.period,
            AggOrderSummary.revenue,
            AggOrderSummary.cost,
            AggOrderSummary.gross_profit,
            AggOrderSummary.dim_dept,
            AggOrderSummary.dim_product,
        ).where(
            AggOrderSummary.revenue >= threshold,
        )
        if department:
            stmt = stmt.where(AggOrderSummary.bgbu == department)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(total_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AggOrderSummary.revenue.desc()).offset(offset).limit(page_size)
        result = await db.execute(stmt)

        items = [
            {
                "metric_name": "order_revenue",
                "metric_value": float(r.revenue or 0),
                "period": r.period,
                "entity": r.dim_dept or "",
                "order_id": r.order_id,
                "cost": float(r.cost or 0),
                "gross_profit": float(r.gross_profit or 0),
                "product": r.dim_product or "",
            }
            for r in result.all()
        ]
        return items, total


transaction_service = TransactionService()
