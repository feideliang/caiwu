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
        return tags.get("department") or row.entity
    if dimension == "customer":
        return tags.get("customer") or tags.get("customer_name")
    if dimension == "product_line":
        return tags.get("product_line") or tags.get("product") or tags.get("series")
    if dimension == "order_id":
        return tags.get("order_id") or tags.get("contract_no")
    if dimension == "project_name":
        return tags.get("project_name")
    if dimension == "region":
        return tags.get("region")
    return None


def _yoy_period(period: str) -> str | None:
    if not period or len(period) < 7:
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
        high_margin_threshold: float = 40.0,
    ) -> CoreMetricsResponse:
        all_periods = await MetricsService._list_periods(db, limit=24)
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
        if current_period in sorted_periods:
            idx = sorted_periods.index(current_period)
            trend_periods = sorted_periods[max(0, idx - 5):idx + 1]
        else:
            trend_periods = sorted_periods[-6:]

        yoy_curr = _yoy_period(current_period)
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
            bucket = _bucket(row.metric_name)
            if bucket is None:
                continue
            p = row.period
            v = float(row.metric_value or 0.0)
            period_bucket[p][bucket] += v

            dim_value = _extract_dimension(row, dimension) if dimension != "company" else "company"
            if dim_value is not None:
                period_dim_bucket[p][dim_value][bucket] += v

            tags = row.tags or {}
            customer = tags.get("customer") or tags.get("customer_name")
            if customer:
                if bucket == "revenue":
                    period_customer_rev[p][customer] += v
                # Customer breakdown: collect revenue, cost, gross_profit per customer
                if bucket:
                    period_customer_bucket[p][customer][bucket] += v

            product = tags.get("product_line") or tags.get("product") or tags.get("series")
            if product and bucket in ("gross_profit", "revenue", "cost"):
                period_product_bucket[p][product][bucket] += v
                if bucket == "gross_profit":
                    period_product_gp[p][product] += v

            order_id = tags.get("order_id") or tags.get("contract_no")
            if order_id:
                period_order[p][order_id][bucket] += v

            # Direct sign customer: tags.contract_type == "直签"
            contract_type = tags.get("contract_type")
            if contract_type == "直签" and p == current_period:
                if bucket == "revenue":
                    direct_sign_rev += v
                elif bucket == "gross_profit":
                    direct_sign_gp += v

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

        # MoM
        prev_period = trend_periods[-2] if len(trend_periods) >= 2 and trend_periods[-1] == current_period else None
        prev_rev, prev_cost, prev_gp = _bucket_values(prev_period) if prev_period else (None, None, None)
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

        # Core market line (top revenue department/product_line)
        if dim_buckets := period_dim_bucket.get(current_period, {}):
            top_dim = max(dim_buckets.items(), key=lambda x: x[1].get("revenue", 0))
            summary.core_market_line = str(top_dim[0])
            summary.core_market_line_revenue = _round(top_dim[1].get("revenue", 0))
            # Highest value market line (top gross_profit)
            top_gp_dim = max(
                dim_buckets.items(),
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
            if row.period != current_period:
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
                d_missing: list[str] = []
                if d_rev is None:
                    d_missing.append("revenue")
                if d_cost is None and d_gp is None:
                    d_missing.append("cost_or_gross_profit")

                # Order count per dimension
                d_order_count = len(period_orders_dim.get(str(dim_value), set()))

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
                    gross_margin_contribution=_round(contrib),
                    order_count=d_order_count if d_order_count else None,
                    avg_order_value=_round(d_aov),
                    revenue_yoy_growth=_round(d_yoy_rev),
                    calculable=(d_rev is not None and d_gp is not None),
                    missing_fields=d_missing,
                ))
            breakdowns.sort(key=lambda b: (b.revenue or 0), reverse=True)

        # ── Trend series ─────────────────────────────────────
        trend: list[TrendDataPoint] = []
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
                period=tp,
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
                        "period": tp,
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
        if prev_period and dimension != "company":
            curr_dim = period_dim_bucket.get(current_period, {})
            prev_dim = period_dim_bucket.get(prev_period, {})
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
            customer_breakdown.append(BreakdownItem(
                dimension_value=cust_name,
                revenue=_round(c_rev),
                tax_excluded_cost=_round(c_cost),
                gross_profit=_round(c_gp),
                gross_margin=_round(c_gm),
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
