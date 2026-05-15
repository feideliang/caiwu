"""Core metrics service — aggregates revenue/cost/gross_profit from financial_data."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialData
from app.schemas.metrics import (
    BreakdownItem,
    CoreMetricsResponse,
    CoreMetricsSummary,
    DataQuality,
    TrendDataPoint,
)


_REVENUE_KW = ("revenue", "营业收入", "sales")
_COST_KW = ("cost", "成本", "expense", "不含税")
_PROFIT_KW = ("gross_profit", "毛利润", "毛利", "gross profit")


def _matches(metric_name: str, keywords: Iterable[str]) -> bool:
    if not metric_name:
        return False
    lower = metric_name.lower()
    return any(kw.lower() in lower for kw in keywords)


def _bucket(metric_name: str) -> str | None:
    if _matches(metric_name, _PROFIT_KW):
        return "gross_profit"
    if _matches(metric_name, _REVENUE_KW):
        return "revenue"
    if _matches(metric_name, _COST_KW):
        return "cost"
    return None


def _extract_dimension(row: FinancialData, dimension: str) -> str | None:
    tags = row.tags or {}
    if dimension == "company":
        return "company"
    if dimension == "department":
        return tags.get("department") or tags.get("sales_department") or tags.get("hr_department") or row.entity
    if dimension == "customer":
        return tags.get("customer") or tags.get("customer_name") or tags.get("superior_name")
    if dimension == "product_line":
        return tags.get("product_line") or tags.get("product") or tags.get("series")
    if dimension == "sales_product":
        return tags.get("sales_product_name") or tags.get("product") or tags.get("series")
    if dimension == "market_segment":
        return tags.get("market_segment") or tags.get("product_family")
    if dimension == "order_id":
        return tags.get("order_id") or tags.get("contract_no")
    if dimension == "project_name":
        return tags.get("project_name")
    if dimension == "region":
        return tags.get("region") or tags.get("province")
    return None


def _yoy_period(period: str) -> str | None:
    if not period:
        return None
    # Year-only period (e.g. "2026") → previous year
    if len(period) == 4 and period.isdigit():
        return f"{int(period) - 1}"
    if len(period) < 7:
        return None
    try:
        year = int(period[:4])
    except ValueError:
        return None
    return f"{year - 1}{period[4:]}"


def _safe_div(num: float, den: float) -> float | None:
    if not den:
        return None
    return num / den


def _round(value: float | None, ndigits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, ndigits)


def _format_period_label(period: str, period_dimension: str) -> str:
    """Format period label based on dimension for chart x-axis display."""
    if period_dimension == "yearly":
        # Show year only
        return period[:4] if "-" in period else period
    if period_dimension == "weekly":
        # Show as week number: "2026-03" → "W10" (approximate)
        if "-" in period:
            try:
                year, month = period.split("-")
                m = int(month)
                week_num = (m - 1) * 4 + 1
                return f"{year}-W{week_num}"
            except (ValueError, IndexError):
                pass
    # monthly: "2026-01" → "01月"
    if "-" in period:
        try:
            month = period.split("-")[1]
            return f"{int(month)}月"
        except (ValueError, IndexError):
            pass
    return period


class MetricsService:
    """Aggregate core financial metrics from financial_data table."""

    @staticmethod
    async def _list_periods(db: AsyncSession, limit: int = 24) -> list[str]:
        stmt = (
            select(FinancialData.period)
            .distinct()
            .order_by(desc(FinancialData.period))
            .limit(limit)
        )
        return [row[0] for row in (await db.execute(stmt)).all() if row[0]]

    @staticmethod
    async def get_core_metrics(
        db: AsyncSession,
        period: str | None = None,
        dimension: str = "company",
        entity: str | None = None,
        compare: str = "all",
        period_dimension: str = "monthly",
        high_margin_threshold: float = 40.0,
        product: str | None = None,
        department: str | None = None,
    ) -> CoreMetricsResponse:
        all_periods = await MetricsService._list_periods(db, limit=36)
        raw_period = period

        # Handle yearly mode: aggregate all months in the year
        is_yearly = period_dimension == "yearly" and period and len(period) == 4 and period.isdigit()
        # Handle weekly mode: use individual months as proxy for weeks
        is_weekly = period_dimension == "weekly"

        current_period = period or (all_periods[0] if all_periods else None)

        warnings: list[str] = []
        if not current_period:
            return CoreMetricsResponse(
                period=None,
                dimension=dimension,
                entity=entity,
                summary=CoreMetricsSummary(),
                breakdowns=[],
                customer_breakdown=[],
                trend_series=[],
                data_quality=DataQuality(
                    calculable=False,
                    missing_fields=["period"],
                    warnings=["no financial_data available"],
                ),
            )

        sorted_periods = sorted(all_periods)
        if is_yearly and raw_period:
            # For yearly: use all months in the year as trend
            trend_periods = [p for p in sorted_periods if p.startswith(f"{raw_period}-")]
        elif is_weekly and raw_period:
            # For weekly: use recent months, treat each as a "week period"
            idx = sorted_periods.index(raw_period) if raw_period in sorted_periods else len(sorted_periods) - 1
            trend_periods = sorted_periods[max(0, idx - 5):idx + 1]
        elif current_period in sorted_periods:
            idx = sorted_periods.index(current_period)
            trend_periods = sorted_periods[max(0, idx - 5):idx + 1]
        else:
            trend_periods = sorted_periods[-6:]

        yoy_curr = _yoy_period(current_period)
        # For yearly YoY, use previous year
        if is_yearly and raw_period:
            yoy_curr = str(int(raw_period) - 1)

        query_periods = set(trend_periods) | {current_period}
        for tp in trend_periods:
            yp = _yoy_period(tp)
            if yp:
                query_periods.add(yp)
        if yoy_curr:
            query_periods.add(yoy_curr)

        stmt = select(FinancialData).where(FinancialData.period.in_(list(query_periods)))
        rows = (await db.execute(stmt)).scalars().all()

        if entity and dimension != "company":
            rows = [r for r in rows if _extract_dimension(r, dimension) == entity]

        # period -> bucket -> sum
        period_bucket: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        # period -> dimension_value -> bucket -> sum
        period_dim_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # period -> department -> bucket -> sum (always tracked for market line)
        period_dept_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # period -> customer -> revenue
        period_customer_rev: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        # period -> product_line -> gross_profit
        period_product_gp: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        # period -> product_line -> {revenue, cost, gross_profit}
        period_product_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # period -> order_id -> {revenue, cost, gross_profit}
        period_order: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # period -> customer -> revenue (for customer_breakdown top 10)
        period_customer_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # direct sign customer metrics (contract_type == "直签")
        direct_sign_rev: float = 0.0
        direct_sign_gp: float = 0.0

        for row in rows:
            tags = row.tags or {}
            # Apply cross-dimension filters
            if product:
                row_product = tags.get("product_line") or tags.get("product") or tags.get("series")
                if row_product != product:
                    continue
            if department:
                row_dept = tags.get("department") or tags.get("sales_department") or row.entity
                if row_dept != department:
                    continue

            bucket = _bucket(row.metric_name)
            if bucket is None:
                continue
            p = row.period
            v = float(row.metric_value or 0.0)
            period_bucket[p][bucket] += v

            dim_value = _extract_dimension(row, dimension) if dimension != "company" else "company"
            if dim_value is not None:
                period_dim_bucket[p][dim_value][bucket] += v

            # Always track department dimension for market line computation
            dept_value = _extract_dimension(row, "department")
            if dept_value is not None:
                period_dept_bucket[p][dept_value][bucket] += v

            tags = row.tags or {}
            customer = tags.get("customer") or tags.get("customer_name")
            if customer:
                if bucket == "revenue":
                    period_customer_rev[p][customer] += v
                # Customer breakdown: collect revenue, cost, gross_profit per customer
                if bucket:
                    period_customer_bucket[p][customer][bucket] += v

            row_product = tags.get("product_line") or tags.get("product") or tags.get("series")
            if row_product and bucket in ("gross_profit", "revenue", "cost"):
                period_product_bucket[p][row_product][bucket] += v
                if bucket == "gross_profit":
                    period_product_gp[p][row_product] += v

            order_id = tags.get("order_id") or tags.get("contract_no")
            if order_id:
                period_order[p][order_id][bucket] += v

            # Direct sign customer: tags.contract_type == "直签"
            contract_type = tags.get("contract_type")
            if contract_type == "直签":
                match_period = (p.startswith(raw_period + "-") if is_yearly and raw_period else p == current_period)
                if match_period:
                    if bucket == "revenue":
                        direct_sign_rev += v
                    elif bucket == "gross_profit":
                        direct_sign_gp += v

        # For yearly mode: aggregate all months in the target year into a synthetic year key
        if is_yearly and raw_period:
            # Also aggregate YoY comparison year if applicable
            yoy_year = yoy_curr if yoy_curr and len(yoy_curr) == 4 and yoy_curr.isdigit() else None
            for agg_year in [raw_period, yoy_year]:
                if not agg_year:
                    continue
                for p in list(period_bucket.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for bucket_name, val in period_bucket[p].items():
                            period_bucket[agg_year][bucket_name] += val
                for p in list(period_dim_bucket.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for dim_val, bk in period_dim_bucket[p].items():
                            for bucket_name, val in bk.items():
                                period_dim_bucket[agg_year][dim_val][bucket_name] += val
                for p in list(period_customer_rev.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for cust, val in period_customer_rev[p].items():
                            period_customer_rev[agg_year][cust] += val
                for p in list(period_product_gp.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for prod, val in period_product_gp[p].items():
                            period_product_gp[agg_year][prod] += val
                for p in list(period_product_bucket.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for prod, bk in period_product_bucket[p].items():
                            for bucket_name, val in bk.items():
                                period_product_bucket[agg_year][prod][bucket_name] += val
                for p in list(period_order.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for oid, bk in period_order[p].items():
                            for bucket_name, val in bk.items():
                                period_order[agg_year][oid][bucket_name] += val
                for p in list(period_customer_bucket.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for cust, bk in period_customer_bucket[p].items():
                            for bucket_name, val in bk.items():
                                period_customer_bucket[agg_year][cust][bucket_name] += val
                for p in list(period_dept_bucket.keys()):
                    if p.startswith(f"{agg_year}-"):
                        for dept, bk in period_dept_bucket[p].items():
                            for bucket_name, val in bk.items():
                                period_dept_bucket[agg_year][dept][bucket_name] += val

        def _bucket_values(p: str) -> tuple[float | None, float | None, float | None]:
            buckets = period_bucket.get(p, {})
            rev = buckets.get("revenue")
            cost = buckets.get("cost")
            gp = buckets.get("gross_profit")
            if gp is None and rev is not None and cost is not None:
                gp = rev - cost
            return rev, cost, gp

        # ── Summary for current period ─────────────────────
        rev, cost, gp = _bucket_values(current_period)
        gm = _safe_div(gp, rev) * 100 if (gp is not None and rev) else None

        # YoY
        yoy_rev, yoy_cost, yoy_gp = _bucket_values(yoy_curr) if yoy_curr else (None, None, None)
        rev_yoy = (_safe_div(rev - yoy_rev, yoy_rev) * 100) if (rev is not None and yoy_rev) else None
        gp_yoy = (_safe_div(gp - yoy_gp, yoy_gp) * 100) if (gp is not None and yoy_gp) else None

        # MoM / comparison base period
        prev_period = trend_periods[-2] if len(trend_periods) >= 2 and trend_periods[-1] == current_period else None
        # For yearly mode, use YoY year as comparison base for margin_change_analysis
        compare_period = prev_period or (yoy_curr if is_yearly else None)
        prev_rev, prev_cost, prev_gp = _bucket_values(compare_period) if compare_period else (None, None, None)
        rev_mom = (_safe_div(rev - prev_rev, prev_rev) * 100) if (rev is not None and prev_rev) else None
        gp_mom = (_safe_div(gp - prev_gp, prev_gp) * 100) if (gp is not None and prev_gp) else None

        # Customer concentration top3 (revenue)
        cust_rev = period_customer_rev.get(current_period, {})
        cust_top3 = None
        if cust_rev and rev:
            top3_sum = sum(sorted(cust_rev.values(), reverse=True)[:3])
            cust_top3 = top3_sum / rev * 100

        # Top single customer revenue share
        cust_top1_share = None
        if cust_rev and rev:
            cust_top1_share = max(cust_rev.values()) / rev * 100

        # Product concentration top3 (gross_profit)
        prod_gp = period_product_gp.get(current_period, {})
        prod_top3 = None
        total_prod_gp = sum(prod_gp.values()) if prod_gp else 0.0
        if prod_gp and total_prod_gp:
            top3_sum = sum(sorted(prod_gp.values(), reverse=True)[:3])
            prod_top3 = top3_sum / total_prod_gp * 100

        # High margin order ratio
        orders = period_order.get(current_period, {})
        high_margin_ratio: float | None = None
        if orders:
            total_orders = 0
            high_orders = 0
            for oid, bk in orders.items():
                o_rev = bk.get("revenue")
                o_cost = bk.get("cost")
                o_gp = bk.get("gross_profit")
                if o_gp is None and o_rev is not None and o_cost is not None:
                    o_gp = o_rev - o_cost
                if o_rev:
                    total_orders += 1
                    o_margin = (o_gp / o_rev * 100) if o_gp is not None else None
                    if o_margin is not None and o_margin > high_margin_threshold:
                        high_orders += 1
            if total_orders > 0:
                high_margin_ratio = high_orders / total_orders * 100
        else:
            warnings.append("no order-level data; high_margin_order_ratio not calculable")

        missing_fields: list[str] = []
        if rev is None:
            missing_fields.append("revenue")
        if cost is None and gp is None:
            missing_fields.append("cost_or_gross_profit")

        summary = CoreMetricsSummary(
            revenue=_round(rev),
            tax_excluded_cost=_round(cost),
            gross_profit=_round(gp),
            gross_margin=_round(gm),
            gross_margin_contribution=100.0 if gp is not None else None,
            customer_concentration_top3=_round(cust_top3),
            product_concentration_top3=_round(prod_top3),
            top_customer_share=_round(cust_top1_share),
            high_margin_order_ratio=_round(high_margin_ratio),
            revenue_yoy_growth=_round(rev_yoy),
            gross_profit_yoy_growth=_round(gp_yoy),
            revenue_mom_growth=_round(rev_mom),
            gross_profit_mom_growth=_round(gp_mom),
        )

        # ── New analysis fields ────────────────────────────
        # Order count from tags.order_id
        order_ids = set()
        loss_orders = 0
        total_orders_with_gp = 0
        for oid, bk in orders.items():
            o_rev = bk.get("revenue")
            o_cost = bk.get("cost")
            o_gp = bk.get("gross_profit")
            if o_gp is None and o_rev is not None and o_cost is not None:
                o_gp = o_rev - o_cost
            if o_rev is not None:
                order_ids.add(oid)
                total_orders_with_gp += 1
                if o_gp is not None and o_gp < 0:
                    loss_orders += 1

        summary.order_count = len(order_ids) if order_ids else None
        summary.loss_ratio = round(loss_orders / total_orders_with_gp * 100, 2) if total_orders_with_gp else None

        # Achievement rate from target_revenue metric
        target_rev = None
        for row in rows:
            if row.period == current_period and _matches(row.metric_name, ("target_revenue", "目标收入")):
                target_rev = float(row.metric_value or 0.0)
        if target_rev and rev:
            summary.achievement_rate = round(rev / target_rev * 100, 2)

        # Core market line (top revenue department — always use dept dimension)
        if dept_buckets := period_dept_bucket.get(current_period, {}):
            top_dim = max(dept_buckets.items(), key=lambda x: x[1].get("revenue", 0))
            summary.core_market_line = str(top_dim[0])
            summary.core_market_line_revenue = _round(top_dim[1].get("revenue", 0))
            # Highest value market line (top gross_profit department)
            top_gp_dim = max(
                dept_buckets.items(),
                key=lambda x: (
                    x[1].get("gross_profit")
                    if x[1].get("gross_profit") is not None
                    else (x[1].get("revenue", 0) - x[1].get("cost", 0))
                ),
            )
            summary.highest_value_market_line = str(top_gp_dim[0])
            top_gp = top_gp_dim[1].get("gross_profit")
            if top_gp is None:
                top_gp = top_gp_dim[1].get("revenue", 0) - top_gp_dim[1].get("cost", 0)
            summary.highest_value_market_profit = _round(top_gp)

        # Direct sign customer metrics
        if direct_sign_rev:
            summary.direct_sign_revenue = _round(direct_sign_rev)
            summary.direct_sign_revenue_pct = _round(_safe_div(direct_sign_rev, rev) * 100 if rev else 0)
            summary.direct_sign_profit = _round(direct_sign_gp)
            summary.direct_sign_margin = _round(_safe_div(direct_sign_gp, direct_sign_rev) * 100)

        # Negative margin order metrics
        neg_margin_orders: list[tuple[float, float]] = []  # (revenue, gross_profit)
        for oid, bk in orders.items():
            o_rev = bk.get("revenue")
            o_cost = bk.get("cost")
            o_gp = bk.get("gross_profit")
            if o_gp is None and o_rev is not None and o_cost is not None:
                o_gp = o_rev - o_cost
            if o_rev is not None and o_gp is not None and o_gp < 0:
                neg_margin_orders.append((o_rev, o_gp))
        total_orders_count = len(orders)
        if total_orders_count:
            summary.negative_margin_order_ratio = _round(len(neg_margin_orders) / total_orders_count * 100)
            summary.negative_margin_order_amount = _round(sum(gp for _, gp in neg_margin_orders))

        # Negative margin product metrics
        all_products = set()
        neg_margin_products: list[float] = []  # gross_profit values
        for prod, bk in period_product_bucket.get(current_period, {}).items():
            all_products.add(prod)
            p_gp = bk.get("gross_profit")
            if p_gp is None:
                p_gp = (bk.get("revenue", 0) or 0) - (bk.get("cost", 0) or 0)
            if p_gp < 0:
                neg_margin_products.append(p_gp)
        if all_products:
            summary.negative_margin_product_ratio = _round(len(neg_margin_products) / len(all_products) * 100)
            summary.negative_margin_product_amount = _round(sum(neg_margin_products))

        # ── Per-dimension order counts ─────────────────────
        # Map order_id -> dimension_value, then count per dim
        period_orders_dim: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            match = (row.period == current_period) or (is_yearly and row.period.startswith(f"{current_period}-"))
            if not match:
                continue
            tags = row.tags or {}
            order_id = tags.get("order_id") or tags.get("contract_no")
            dim_value = _extract_dimension(row, dimension)
            if order_id and dim_value:
                period_orders_dim[dim_value].add(order_id)

        # ── Breakdowns for current period ────────────────────
        breakdowns: list[BreakdownItem] = []
        if dimension != "company":
            dim_buckets = period_dim_bucket.get(current_period, {})
            total_rev_for_contrib = sum(
                (b.get("revenue", 0) or 0) for b in dim_buckets.values()
            )
            total_gp_for_contrib = sum(
                (
                    b.get("gross_profit")
                    if b.get("gross_profit") is not None
                    else ((b.get("revenue", 0) - b.get("cost", 0)) if (b.get("revenue") is not None and b.get("cost") is not None) else 0)
                )
                for b in dim_buckets.values()
            )
            for dim_value, bk in dim_buckets.items():
                d_rev = bk.get("revenue")
                d_cost = bk.get("cost")
                d_gp = bk.get("gross_profit")
                if d_gp is None and d_rev is not None and d_cost is not None:
                    d_gp = d_rev - d_cost
                d_gm = (d_gp / d_rev * 100) if (d_gp is not None and d_rev) else None
                contrib = (d_gp / total_gp_for_contrib * 100) if (d_gp is not None and total_gp_for_contrib) else None
                rev_contrib = (d_rev / total_rev_for_contrib * 100) if (d_rev is not None and total_rev_for_contrib) else None
                d_missing: list[str] = []
                if d_rev is None:
                    d_missing.append("revenue")
                if d_cost is None and d_gp is None:
                    d_missing.append("cost_or_gross_profit")

                # Order count per dimension
                d_order_count = len(period_orders_dim.get(str(dim_value), set()))

                # Neg margin orders per dimension
                d_neg_orders = 0
                d_neg_amount = 0.0
                for oid in period_orders_dim.get(str(dim_value), set()):
                    o_bk = orders.get(oid, {})
                    o_gp = o_bk.get("gross_profit")
                    if o_gp is None:
                        o_gp = (o_bk.get("revenue", 0) or 0) - (o_bk.get("cost", 0) or 0)
                    if o_gp < 0:
                        d_neg_orders += 1
                        d_neg_amount += o_gp

                # Avg order value (万元)
                d_aov = (d_rev / d_order_count) if (d_rev is not None and d_order_count > 0) else None

                # YoY growth per dimension
                d_yoy_rev: float | None = None
                if yoy_curr and yoy_curr in period_dim_bucket:
                    yoy_bk = period_dim_bucket[yoy_curr].get(dim_value, {})
                    yoy_rev = yoy_bk.get("revenue")
                    if yoy_rev is not None and d_rev is not None:
                        d_yoy_rev = _safe_div(d_rev - yoy_rev, yoy_rev) * 100

                breakdowns.append(BreakdownItem(
                    dimension_value=str(dim_value),
                    revenue=_round(d_rev),
                    tax_excluded_cost=_round(d_cost),
                    gross_profit=_round(d_gp),
                    gross_margin=_round(d_gm),
                    revenue_contribution=_round(rev_contrib),
                    gross_margin_contribution=_round(contrib),
                    order_count=d_order_count if d_order_count else None,
                    avg_order_value=_round(d_aov),
                    neg_margin_order_count=d_neg_orders,
                    neg_margin_amount=_round(abs(d_neg_amount)) if d_neg_amount else 0,
                    revenue_yoy_growth=_round(d_yoy_rev),
                    calculable=(d_rev is not None and d_gp is not None),
                    missing_fields=d_missing,
                ))
            breakdowns.sort(key=lambda b: (b.revenue or 0), reverse=True)

        # ── Trend series ─────────────────────────────────────
        # Drill-down pattern: year→months, month→weeks, week→days
        trend: list[TrendDataPoint] = []

        if period_dimension == "yearly" and is_yearly:
            # Year → show each month as a trend point
            for i, tp in enumerate(trend_periods):
                t_rev, t_cost, t_gp = _bucket_values(tp)
                t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None

                tp_prev = trend_periods[i - 1] if i > 0 else None
                if tp_prev:
                    p_rev, _, p_gp = _bucket_values(tp_prev)
                else:
                    p_rev, p_gp = None, None
                t_rev_mom = (_safe_div(t_rev - p_rev, p_rev) * 100) if (t_rev is not None and p_rev) else None
                t_gp_mom = (_safe_div(t_gp - p_gp, p_gp) * 100) if (t_gp is not None and p_gp) else None

                tp_yoy = _yoy_period(tp)
                y_rev, _, y_gp = _bucket_values(tp_yoy) if tp_yoy else (None, None, None)
                t_rev_yoy = (_safe_div(t_rev - y_rev, y_rev) * 100) if (t_rev is not None and y_rev) else None
                t_gp_yoy = (_safe_div(t_gp - y_gp, y_gp) * 100) if (t_gp is not None and y_gp) else None

                month_num = int(tp.split("-")[1]) if "-" in tp else i + 1
                trend.append(TrendDataPoint(
                    period=f"{month_num}月",
                    revenue=_round(t_rev),
                    tax_excluded_cost=_round(t_cost),
                    gross_profit=_round(t_gp),
                    gross_margin=_round(t_gm),
                    revenue_mom_growth=_round(t_rev_mom),
                    revenue_yoy_growth=_round(t_rev_yoy),
                    gross_profit_mom_growth=_round(t_gp_mom),
                    gross_profit_yoy_growth=_round(t_gp_yoy),
                ))

        elif period_dimension == "monthly":
            # Month → split into 4 weeks (approximate from monthly total)
            t_rev, t_cost, t_gp = _bucket_values(current_period)
            t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
            for w in range(1, 5):
                w_rev = _round(t_rev / 4) if t_rev else None
                w_cost = _round(t_cost / 4) if t_cost else None
                w_gp = _round(t_gp / 4) if t_gp else None
                w_gm = _round(t_gm) if t_gm else None  # margin stays the same
                w_rev_mom = None  # no prior week data
                trend.append(TrendDataPoint(
                    period=f"第{w}周",
                    revenue=w_rev,
                    tax_excluded_cost=w_cost,
                    gross_profit=w_gp,
                    gross_margin=w_gm,
                    revenue_mom_growth=w_rev_mom,
                    revenue_yoy_growth=w_rev_mom,
                    gross_profit_mom_growth=w_rev_mom,
                    gross_profit_yoy_growth=w_rev_mom,
                ))

        elif period_dimension == "weekly":
            # Week → split into 7 days (approximate from monthly total / 4)
            t_rev, t_cost, t_gp = _bucket_values(current_period)
            t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
            day_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for d, label in enumerate(day_labels):
                d_rev = _round(t_rev / 28) if t_rev else None  # monthly total / 4 weeks / 7 days
                d_cost = _round(t_cost / 28) if t_cost else None
                d_gp = _round(t_gp / 28) if t_gp else None
                d_gm = _round(t_gm) if t_gm else None
                trend.append(TrendDataPoint(
                    period=label,
                    revenue=d_rev,
                    tax_excluded_cost=d_cost,
                    gross_profit=d_gp,
                    gross_margin=d_gm,
                    revenue_mom_growth=None,
                    revenue_yoy_growth=None,
                    gross_profit_mom_growth=None,
                    gross_profit_yoy_growth=None,
                ))

        else:
            # Default: monthly trend (recent 6 periods)
            for i, tp in enumerate(trend_periods):
                t_rev, t_cost, t_gp = _bucket_values(tp)
                t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None

                tp_prev = trend_periods[i - 1] if i > 0 else None
                if tp_prev:
                    p_rev, _, p_gp = _bucket_values(tp_prev)
                else:
                    p_rev, p_gp = None, None
                t_rev_mom = (_safe_div(t_rev - p_rev, p_rev) * 100) if (t_rev is not None and p_rev) else None
                t_gp_mom = (_safe_div(t_gp - p_gp, p_gp) * 100) if (t_gp is not None and p_gp) else None

                tp_yoy = _yoy_period(tp)
                y_rev, _, y_gp = _bucket_values(tp_yoy) if tp_yoy else (None, None, None)
                t_rev_yoy = (_safe_div(t_rev - y_rev, y_rev) * 100) if (t_rev is not None and y_rev) else None
                t_gp_yoy = (_safe_div(t_gp - y_gp, y_gp) * 100) if (t_gp is not None and y_gp) else None

                trend.append(TrendDataPoint(
                    period=_format_period_label(tp, period_dimension),
                    revenue=_round(t_rev),
                    tax_excluded_cost=_round(t_cost),
                    gross_profit=_round(t_gp),
                    gross_margin=_round(t_gm),
                    revenue_mom_growth=_round(t_rev_mom),
                    revenue_yoy_growth=_round(t_rev_yoy),
                    gross_profit_mom_growth=_round(t_gp_mom),
                    gross_profit_yoy_growth=_round(t_gp_yoy),
                ))

        calculable = rev is not None and gp is not None

        # ── Dimension trend series (for stacked area charts) ──
        dim_trend: list = []
        if dimension != "company":
            if period_dimension == "yearly" and is_yearly:
                # Year → months, per dimension
                for tp in trend_periods:
                    month_num = int(tp.split("-")[1]) if "-" in tp else 0
                    dim_bk = period_dim_bucket.get(tp, {})
                    for dim_value, bk in dim_bk.items():
                        t_rev = bk.get("revenue")
                        t_gp = bk.get("gross_profit")
                        t_cost = bk.get("cost")
                        if t_gp is None and t_rev is not None and t_cost is not None:
                            t_gp = t_rev - t_cost
                        t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
                        dim_trend.append({
                            "period": f"{month_num}月",
                            "dimension_value": str(dim_value),
                            "revenue": _round(t_rev),
                            "gross_profit": _round(t_gp),
                            "gross_margin": _round(t_gm),
                        })
            elif period_dimension == "monthly":
                # Month → 4 weeks, per dimension
                dim_bk = period_dim_bucket.get(current_period, {})
                for w in range(1, 5):
                    for dim_value, bk in dim_bk.items():
                        t_rev = bk.get("revenue")
                        t_gp = bk.get("gross_profit")
                        t_cost = bk.get("cost")
                        if t_gp is None and t_rev is not None and t_cost is not None:
                            t_gp = t_rev - t_cost
                        t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
                        dim_trend.append({
                            "period": f"第{w}周",
                            "dimension_value": str(dim_value),
                            "revenue": _round(t_rev / 4) if t_rev else None,
                            "gross_profit": _round(t_gp / 4) if t_gp else None,
                            "gross_margin": _round(t_gm),
                        })
            elif period_dimension == "weekly":
                # Week → 7 days, per dimension
                dim_bk = period_dim_bucket.get(current_period, {})
                day_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                for label in day_labels:
                    for dim_value, bk in dim_bk.items():
                        t_rev = bk.get("revenue")
                        t_gp = bk.get("gross_profit")
                        t_cost = bk.get("cost")
                        if t_gp is None and t_rev is not None and t_cost is not None:
                            t_gp = t_rev - t_cost
                        t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
                        dim_trend.append({
                            "period": label,
                            "dimension_value": str(dim_value),
                            "revenue": _round(t_rev / 28) if t_rev else None,
                            "gross_profit": _round(t_gp / 28) if t_gp else None,
                            "gross_margin": _round(t_gm),
                        })
            else:
                # Default: monthly trend periods
                for tp in trend_periods:
                    dim_bk = period_dim_bucket.get(tp, {})
                    for dim_value, bk in dim_bk.items():
                        t_rev = bk.get("revenue")
                        t_gp = bk.get("gross_profit")
                        t_cost = bk.get("cost")
                        if t_gp is None and t_rev is not None and t_cost is not None:
                            t_gp = t_rev - t_cost
                        t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
                        dim_trend.append({
                            "period": _format_period_label(tp, period_dimension),
                            "dimension_value": str(dim_value),
                            "revenue": _round(t_rev),
                            "gross_profit": _round(t_gp),
                            "gross_margin": _round(t_gm),
                        })
        # Consecutive growth periods (count backwards from current period)
        rev_consec = 0
        gp_consec = 0
        for pt in reversed(trend):
            rev_g = pt.revenue_mom_growth
            if rev_g is not None and rev_g > 0:
                rev_consec += 1
            else:
                break
        for pt in reversed(trend):
            gp_g = pt.gross_profit_mom_growth
            if gp_g is not None and gp_g > 0:
                gp_consec += 1
            else:
                break
        summary.revenue_consecutive_growth = rev_consec
        summary.gross_profit_consecutive_growth = gp_consec

        # ── Gross margin volatility (std dev of trend margins) ──
        gm_values = [pt.gross_margin for pt in trend if pt.gross_margin is not None]
        if len(gm_values) >= 2:
            avg = sum(gm_values) / len(gm_values)
            variance = sum((v - avg) ** 2 for v in gm_values) / len(gm_values)
            summary.gross_margin_volatility = round(variance ** 0.5, 2)

        # ── Margin change impact decomposition ─────────────
        # Compare current vs previous period by dimension
        if compare_period and dimension != "company":
            curr_dim = period_dim_bucket.get(current_period, {})
            prev_dim = period_dim_bucket.get(compare_period, {})
            curr_total_rev = sum(bk.get("revenue", 0) for bk in curr_dim.values())
            prev_total_rev = sum(bk.get("revenue", 0) for bk in prev_dim.values())
            margin_analysis = []
            all_dims = set(curr_dim.keys()) | set(prev_dim.keys())
            for dim_val in all_dims:
                c_bk = curr_dim.get(dim_val, {})
                p_bk = prev_dim.get(dim_val, {})
                c_rev = c_bk.get("revenue", 0) or 0
                c_gp = c_bk.get("gross_profit")
                if c_gp is None:
                    c_gp = (c_rev - (c_bk.get("cost", 0) or 0)) if c_rev else 0
                c_gm = (c_gp / c_rev * 100) if c_rev else 0
                c_share = (c_rev / curr_total_rev * 100) if curr_total_rev else 0

                p_rev = p_bk.get("revenue", 0) or 0
                p_gp = p_bk.get("gross_profit")
                if p_gp is None:
                    p_gp = (p_rev - (p_bk.get("cost", 0) or 0)) if p_rev else 0
                p_gm = (p_gp / p_rev * 100) if p_rev else 0
                p_share = (p_rev / prev_total_rev * 100) if prev_total_rev else 0

                # Impact: structure effect + margin effect
                share_change = c_share - p_share
                gm_change = c_gm - p_gm
                # Structure impact: (current_share - previous_share) * previous_gm
                structure_impact = (c_share - p_share) * p_gm / 100
                # Margin impact: current_share * (current_gm - previous_gm)
                margin_impact = c_share * (c_gm - p_gm) / 100
                total_impact = structure_impact + margin_impact

                margin_analysis.append({
                    "dimension_value": str(dim_val),
                    "current_revenue": round(c_rev, 2),
                    "current_share": round(c_share, 2),
                    "current_margin": round(c_gm, 2),
                    "previous_revenue": round(p_rev, 2),
                    "previous_share": round(p_share, 2),
                    "previous_margin": round(p_gm, 2),
                    "share_change": round(share_change, 2),
                    "margin_change": round(gm_change, 2),
                    "structure_impact": round(structure_impact, 4),
                    "margin_impact": round(margin_impact, 4),
                    "total_impact": round(total_impact, 4),
                })
            # Sort by total_impact absolute value
            margin_analysis.sort(key=lambda x: abs(x["total_impact"]), reverse=True)
            summary.margin_change_analysis = margin_analysis

        # ── Customer breakdown (Top 10 by revenue) ──────────────
        customer_breakdown: list[BreakdownItem] = []
        cust_buckets = period_customer_bucket.get(current_period, {})
        total_cust_rev = sum(bk.get("revenue", 0) for bk in cust_buckets.values())
        for cust_name, bk in sorted(
            cust_buckets.items(), key=lambda x: x[1].get("revenue", 0), reverse=True
        )[:10]:
            c_rev = bk.get("revenue")
            c_cost = bk.get("cost")
            c_gp = bk.get("gross_profit")
            if c_gp is None and c_rev is not None and c_cost is not None:
                c_gp = c_rev - c_cost
            c_gm = _safe_div(c_gp, c_rev) * 100 if (c_gp is not None and c_rev) else None
            c_contrib = _safe_div(c_gp, total_cust_rev) * 100 if (c_gp is not None and total_cust_rev) else None
            c_rev_contrib = _safe_div(c_rev, total_cust_rev) * 100 if (c_rev is not None and total_cust_rev) else None
            customer_breakdown.append(BreakdownItem(
                dimension_value=cust_name,
                revenue=_round(c_rev),
                tax_excluded_cost=_round(c_cost),
                gross_profit=_round(c_gp),
                gross_margin=_round(c_gm),
                revenue_contribution=_round(c_rev_contrib),
                gross_margin_contribution=_round(c_contrib),
                calculable=(c_rev is not None and c_gp is not None),
            ))

        return CoreMetricsResponse(
            period=current_period,
            dimension=dimension,
            entity=entity,
            summary=summary,
            breakdowns=breakdowns,
            customer_breakdown=customer_breakdown,
            trend_series=trend,
            dimension_trend_series=dim_trend,
            data_quality=DataQuality(
                calculable=calculable,
                missing_fields=missing_fields,
                warnings=warnings,
            ),
        )
