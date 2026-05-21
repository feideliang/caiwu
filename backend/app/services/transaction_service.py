"""Transaction analysis service."""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialData


class TransactionService:

    async def get_contracts(
        self, db: AsyncSession, period: str | None = None,
        entity: str | None = None, page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(
            FinancialData.entity,
            FinancialData.period,
            func.sum(FinancialData.metric_value).label("total_value"),
            FinancialData.metric_name,
        ).where(
            FinancialData.metric_name.in_(["ar_amount", "ap_amount"]),
            FinancialData.entity.isnot(None),
            FinancialData.entity != "",
        )
        if period:
            stmt = stmt.where(FinancialData.period == period)
        if entity:
            stmt = stmt.where(FinancialData.entity == entity)
        if department:
            stmt = stmt.where(FinancialData.entity == department)
        stmt = stmt.group_by(FinancialData.entity, FinancialData.period, FinancialData.metric_name)

        result = await db.execute(stmt)
        rows = result.all()

        groups: dict = {}
        for r in rows:
            key = (r.entity, r.period)
            if key not in groups:
                groups[key] = {"entity": r.entity, "total_ar": 0, "total_ap": 0, "net_exposure": 0, "period": r.period}
            if r.metric_name == "ar_amount":
                groups[key]["total_ar"] = float(r.total_value or 0)
            else:
                groups[key]["total_ap"] = float(r.total_value or 0)

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
            FinancialData.period,
            FinancialData.metric_name,
            func.sum(FinancialData.metric_value).label("total_value"),
        ).where(
            FinancialData.metric_name.in_(["revenue", "cost"]),
        )
        if department:
            stmt = stmt.where(FinancialData.entity == department)
        if period_from:
            stmt = stmt.where(FinancialData.period >= period_from)
        if period_to:
            stmt = stmt.where(FinancialData.period <= period_to)
        stmt = stmt.group_by(FinancialData.period, FinancialData.metric_name)

        result = await db.execute(stmt)
        rows = result.all()

        groups: dict = {}
        for r in rows:
            if r.period not in groups:
                groups[r.period] = {"period": r.period, "revenue": 0, "cost": 0, "profit": 0}
            if r.metric_name == "revenue":
                groups[r.period]["revenue"] = float(r.total_value or 0)
            else:
                groups[r.period]["cost"] = float(r.total_value or 0)

        items = []
        for g in groups.values():
            g["profit"] = g["revenue"] - g["cost"]
            if min_value is not None and g["revenue"] < min_value:
                continue
            items.append(g)
        items.sort(key=lambda x: x["period"], reverse=True)

        total = len(items)
        offset = (page - 1) * page_size
        return items[offset: offset + page_size], total

    async def get_projects(
        self, db: AsyncSession, entity: str | None = None,
        page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(
            FinancialData.entity,
            FinancialData.metric_name,
            func.sum(FinancialData.metric_value).label("total_value"),
            func.min(FinancialData.period).label("period_start"),
            func.max(FinancialData.period).label("period_end"),
        ).where(
            FinancialData.metric_name.in_(["revenue", "cost"]),
            FinancialData.entity.isnot(None),
            FinancialData.entity != "",
        )
        if entity:
            stmt = stmt.where(FinancialData.entity == entity)
        if department:
            stmt = stmt.where(FinancialData.entity == department)
        stmt = stmt.group_by(FinancialData.entity, FinancialData.metric_name)

        result = await db.execute(stmt)
        rows = result.all()

        groups: dict = {}
        for r in rows:
            if r.entity not in groups:
                groups[r.entity] = {
                    "entity": r.entity, "total_revenue": 0, "total_cost": 0,
                    "profit_margin": 0, "period_span": f"{r.period_start} ~ {r.period_end}",
                }
            if r.metric_name == "revenue":
                groups[r.entity]["total_revenue"] = float(r.total_value or 0)
            else:
                groups[r.entity]["total_cost"] = float(r.total_value or 0)

        items = list(groups.values())
        for item in items:
            if item["total_revenue"] > 0:
                item["profit_margin"] = round((item["total_revenue"] - item["total_cost"]) / item["total_revenue"], 4)
        items.sort(key=lambda x: x["total_revenue"], reverse=True)

        total = len(items)
        offset = (page - 1) * page_size
        return items[offset: offset + page_size], total

    async def detect_anomalies(
        self, db: AsyncSession, threshold: float = 2.0,
        metric_names: str | None = None, period: str | None = None,
        department: str | None = None,
    ) -> list[dict]:
        stmt = select(
            FinancialData.metric_name,
            FinancialData.period,
            FinancialData.metric_value,
            FinancialData.entity,
        ).where(FinancialData.metric_value.isnot(None))
        if department:
            stmt = stmt.where(FinancialData.entity == department)
        if metric_names:
            names = [n.strip() for n in metric_names.split(",")]
            stmt = stmt.where(FinancialData.metric_name.in_(names))
        if period:
            stmt = stmt.where(FinancialData.period == period)

        result = await db.execute(stmt)
        rows = result.all()

        metric_groups = defaultdict(list)
        for r in rows:
            metric_groups[r.metric_name].append(r)

        anomalies = []
        for metric, items in metric_groups.items():
            values = [float(it.metric_value) for it in items]
            n = len(values)
            if n < 3:
                continue
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            stddev = sqrt(variance) if variance > 0 else 0
            if stddev == 0:
                continue

            for it in items:
                val = float(it.metric_value)
                sigma = abs(val - mean) / stddev
                if sigma >= threshold:
                    anomalies.append({
                        "metric_name": it.metric_name,
                        "period": it.period,
                        "value": val,
                        "expected_mean": round(mean, 4),
                        "sigma_distance": round(sigma, 2),
                        "entity": it.entity,
                    })

        # --- Additional anomaly checks ---
        # 1. Gross margin checks
        margin_stmt = select(
            FinancialData.period,
            func.sum(FinancialData.metric_value).label("revenue"),
        ).where(
            FinancialData.metric_name == "revenue",
            FinancialData.period.isnot(None),
        ).group_by(FinancialData.period)
        if department:
            margin_stmt = margin_stmt.where(FinancialData.entity == department)
        margin_result = await db.execute(margin_stmt)
        period_revenues = {r.period: float(r.revenue or 0) for r in margin_result.all()}

        cost_stmt = select(
            FinancialData.period,
            func.sum(FinancialData.metric_value).label("cost"),
        ).where(
            FinancialData.metric_name == "cost",
            FinancialData.period.isnot(None),
        ).group_by(FinancialData.period)
        if department:
            cost_stmt = cost_stmt.where(FinancialData.entity == department)
        cost_result = await db.execute(cost_stmt)
        period_costs = {r.period: float(r.cost or 0) for r in cost_result.all()}

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

        # 2. Consecutive growth check (3 consecutive periods of positive revenue growth)
        sorted_periods = sorted(period_revenues.keys())
        for i in range(len(sorted_periods) - 2):
            p1, p2, p3 = sorted_periods[i], sorted_periods[i + 1], sorted_periods[i + 2]
            r1, r2, r3 = period_revenues.get(p1, 0), period_revenues.get(p2, 0), period_revenues.get(p3, 0)
            if r1 > 0 and r2 > r1 and r3 > r2:
                anomalies.append({
                    "metric_name": "revenue",
                    "period": p3,
                    "value": round(r3, 2),
                    "alert_level": "info",
                    "message": f"连续3期收入正增长趋势: {p1}→{p2}→{p3}",
                })

        # 3. Customer concentration risk (any customer > 30% of total revenue)
        cust_stmt = select(
            FinancialData.entity,
            func.sum(FinancialData.metric_value).label("total"),
        ).where(
            FinancialData.metric_name == "revenue",
            FinancialData.entity.isnot(None),
            FinancialData.entity != "",
        ).group_by(FinancialData.entity)
        if department:
            cust_stmt = cust_stmt.where(FinancialData.entity == department)
        cust_result = await db.execute(cust_stmt)
        customer_totals = {r.entity: float(r.total or 0) for r in cust_result.all()}
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
                        "message": f"客户{cust}营收占比{ratio*100:.2f}% > 30%，集中度风险",
                    })

        anomalies.sort(key=lambda x: x.get("sigma_distance", 0), reverse=True)
        return anomalies

    async def get_large_amounts(
        self, db: AsyncSession, threshold: float = 1000000,
        page: int = 1, page_size: int = 20,
        department: str | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(
            FinancialData.metric_name, FinancialData.metric_value,
            FinancialData.period, FinancialData.entity,
        ).where(
            FinancialData.metric_value >= threshold,
        )
        if department:
            stmt = stmt.where(FinancialData.entity == department).order_by(FinancialData.metric_value.desc())

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(total_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await db.execute(stmt)

        items = [
            {"metric_name": r.metric_name, "metric_value": float(r.metric_value),
             "period": r.period, "entity": r.entity}
            for r in result.all()
        ]
        return items, total


transaction_service = TransactionService()
