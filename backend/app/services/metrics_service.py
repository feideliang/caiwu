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
    MarginChangeItem,
    MarginChangeSummary,
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
    if period_dimension == "quarterly" and "-Q" in period:
        return period
    if period_dimension == "cumulative" and "-" in period:
        try:
            month = int(period.split("-")[1])
            return f"{month}月累计"
        except (ValueError, IndexError):
            pass
    if "-" in period:
        try:
            month = period.split("-")[1]
            return f"{int(month)}月"
        except (ValueError, IndexError):
            pass
    return period


def _normalize_period_dimension(period_dimension: str | None) -> str:
    if period_dimension == "weekly":
        return "quarterly"
    if period_dimension == "yearly":
        return "cumulative"
    return period_dimension or "monthly"


def _parse_month(period: str | None) -> tuple[int, int] | None:
    if not period or len(period) < 7 or "-" not in period:
        return None
    try:
        year, month = period.split("-")
        return int(year), int(month)
    except (ValueError, IndexError):
        return None


def _quarter_key(period: str | None) -> str | None:
    parsed = _parse_month(period)
    if not parsed:
        return period
    year, month = parsed
    return f"{year}-Q{((month - 1) // 3) + 1}"


def _quarter_end_period(period: str | None) -> str | None:
    if not period or "-Q" not in period:
        return period
    try:
        year, quarter = period.split("-Q")
        return f"{year}-{int(quarter) * 3:02d}"
    except (ValueError, IndexError):
        return None


def _previous_month(period: str | None) -> str | None:
    parsed = _parse_month(period)
    if not parsed:
        return None
    year, month = parsed
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _previous_quarter(period: str | None) -> str | None:
    if not period or "-Q" not in period:
        return None
    try:
        year, quarter = period.split("-Q")
        year_num = int(year)
        quarter_num = int(quarter)
    except ValueError:
        return None
    if quarter_num == 1:
        return f"{year_num - 1}-Q4"
    return f"{year_num}-Q{quarter_num - 1}"


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
        compare_period: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        high_margin_threshold: float = 40.0,
        product: str | None = None,
        department: str | None = None,
        customer: str | None = None,
    ) -> CoreMetricsResponse:
        all_periods = await MetricsService._list_periods(db, limit=36)
        period_dimension = _normalize_period_dimension(period_dimension)
        sorted_periods = sorted(all_periods)

        latest_period = sorted_periods[-1] if sorted_periods else None
        if period_dimension == "quarterly":
            current_period = period or _quarter_key(latest_period)
        elif period_dimension == "custom":
            current_period = f"{period_start or ''}~{period_end or ''}" if period_start and period_end else None
        else:
            current_period = period or latest_period

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

        def _period_members(period_key: str | None) -> list[str]:
            if not period_key:
                return []
            if period_dimension == "monthly":
                return [period_key] if period_key in sorted_periods else []
            if period_dimension == "quarterly":
                quarter_end = _quarter_end_period(period_key)
                quarter_start = _previous_month(_previous_month(quarter_end)) if quarter_end else None
                if not quarter_end or not quarter_start:
                    return []
                return [p for p in sorted_periods if quarter_start <= p <= quarter_end]
            if period_dimension == "cumulative":
                year_prefix = period_key[:4]
                return [p for p in sorted_periods if p.startswith(f"{year_prefix}-") and p <= period_key]
            if period_dimension == "custom":
                if not period_start or not period_end:
                    return []
                return [p for p in sorted_periods if period_start <= p <= period_end]
            return []

        def _trend_keys() -> list[str]:
            if period_dimension == "quarterly":
                quarter_keys = sorted({_quarter_key(p) for p in sorted_periods if _quarter_key(p)})
                if current_period in quarter_keys:
                    idx = quarter_keys.index(current_period)
                    return quarter_keys[max(0, idx - 5):idx + 1]
                return quarter_keys[-6:]
            if period_dimension == "cumulative":
                year_prefix = current_period[:4]
                return [p for p in sorted_periods if p.startswith(f"{year_prefix}-") and p <= current_period]
            if period_dimension == "custom":
                return _period_members(current_period)
            if current_period in sorted_periods:
                idx = sorted_periods.index(current_period)
                return sorted_periods[max(0, idx - 5):idx + 1]
            return sorted_periods[-6:]

        trend_periods = _trend_keys()

        if period_dimension == "quarterly":
            yoy_curr = None
            if current_period and "-Q" in current_period:
                year, quarter = current_period.split("-Q")
                yoy_curr = f"{int(year) - 1}-Q{quarter}"
        elif period_dimension == "custom":
            yoy_curr = None
        else:
            yoy_curr = _yoy_period(current_period)

        if compare_period:
            resolved_compare_period = compare_period
        elif compare == "yoy":
            resolved_compare_period = yoy_curr
        elif compare == "mom":
            resolved_compare_period = _previous_quarter(current_period) if period_dimension == "quarterly" else _previous_month(current_period)
        else:
            resolved_compare_period = _previous_quarter(current_period) if period_dimension == "quarterly" else _previous_month(current_period)

        query_periods = set()
        for period_key in trend_periods + [current_period, resolved_compare_period, yoy_curr]:
            query_periods.update(_period_members(period_key))
        for tp in trend_periods:
            if period_dimension == "quarterly":
                if tp and "-Q" in tp:
                    year, quarter = tp.split("-Q")
                    query_periods.update(_period_members(f"{int(year) - 1}-Q{quarter}"))
                    query_periods.update(_period_members(_previous_quarter(tp)))
            elif period_dimension != "custom":
                query_periods.update(_period_members(_yoy_period(tp)))
                query_periods.update(_period_members(_previous_month(tp)))

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
            if customer:
                row_customer = tags.get("customer") or tags.get("customer_name") or tags.get("superior_name")
                if row_customer != customer:
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

        def _sum_bucket_values(buckets_by_period: dict[str, dict[str, float]], periods: list[str]) -> dict[str, float]:
            aggregated: dict[str, float] = defaultdict(float)
            for month in periods:
                for bucket_name, value in buckets_by_period.get(month, {}).items():
                    aggregated[bucket_name] += value
            return dict(aggregated)

        def _sum_nested_bucket_values(
            buckets_by_period: dict[str, dict[str, dict[str, float]]],
            periods: list[str],
        ) -> dict[str, dict[str, float]]:
            aggregated: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for month in periods:
                for group, bucket_values in buckets_by_period.get(month, {}).items():
                    for bucket_name, value in bucket_values.items():
                        aggregated[group][bucket_name] += value
            return {group: dict(values) for group, values in aggregated.items()}

        def _sum_scalar_groups(
            buckets_by_period: dict[str, dict[str, float]],
            periods: list[str],
        ) -> dict[str, float]:
            aggregated: dict[str, float] = defaultdict(float)
            for month in periods:
                for key, value in buckets_by_period.get(month, {}).items():
                    aggregated[key] += value
            return dict(aggregated)

        def _bucket_values(p: str | None) -> tuple[float | None, float | None, float | None]:
            buckets = _sum_bucket_values(period_bucket, _period_members(p))
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
        prev_rev, prev_cost, prev_gp = _bucket_values(resolved_compare_period) if resolved_compare_period else (None, None, None)
        rev_mom = (_safe_div(rev - prev_rev, prev_rev) * 100) if (rev is not None and prev_rev) else None
        gp_mom = (_safe_div(gp - prev_gp, prev_gp) * 100) if (gp is not None and prev_gp) else None

        current_members = _period_members(current_period)
        current_dim_buckets = _sum_nested_bucket_values(period_dim_bucket, current_members)
        current_dept_buckets = _sum_nested_bucket_values(period_dept_bucket, current_members)
        current_customer_rev = _sum_scalar_groups(period_customer_rev, current_members)
        current_product_gp = _sum_scalar_groups(period_product_gp, current_members)
        current_product_buckets = _sum_nested_bucket_values(period_product_bucket, current_members)
        current_order_buckets = _sum_nested_bucket_values(period_order, current_members)
        current_customer_buckets = _sum_nested_bucket_values(period_customer_bucket, current_members)

        # Customer concentration top3 (revenue)
        cust_rev = current_customer_rev
        cust_top3 = None
        if cust_rev and rev:
            top3_sum = sum(sorted(cust_rev.values(), reverse=True)[:3])
            cust_top3 = top3_sum / rev * 100

        # Top single customer revenue share
        cust_top1_share = None
        if cust_rev and rev:
            cust_top1_share = max(cust_rev.values()) / rev * 100

        # Product concentration top3 (gross_profit)
        prod_gp = current_product_gp
        prod_top3 = None
        total_prod_gp = sum(prod_gp.values()) if prod_gp else 0.0
        if prod_gp and total_prod_gp:
            top3_sum = sum(sorted(prod_gp.values(), reverse=True)[:3])
            prod_top3 = top3_sum / total_prod_gp * 100

        # High margin order ratio
        orders = current_order_buckets
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
        target_rev = 0.0
        for row in rows:
            if row.period in current_members and _matches(row.metric_name, ("target_revenue", "目标收入")):
                target_rev += float(row.metric_value or 0.0)
        if target_rev and rev:
            summary.achievement_rate = round(rev / target_rev * 100, 2)

        # Core market line (top revenue department — always use dept dimension)
        if current_dept_buckets:
            top_dim = max(current_dept_buckets.items(), key=lambda x: x[1].get("revenue", 0))
            summary.core_market_line = str(top_dim[0])
            summary.core_market_line_revenue = _round(top_dim[1].get("revenue", 0))
            top_gp_dim = max(
                current_dept_buckets.items(),
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
        direct_sign_rev = 0.0
        direct_sign_gp = 0.0
        for row in rows:
            if row.period not in current_members:
                continue
            tags = row.tags or {}
            if tags.get("contract_type") != "直签":
                continue
            bucket = _bucket(row.metric_name)
            if bucket == "revenue":
                direct_sign_rev += float(row.metric_value or 0.0)
            elif bucket == "gross_profit":
                direct_sign_gp += float(row.metric_value or 0.0)
            elif bucket == "cost":
                direct_sign_gp -= float(row.metric_value or 0.0)
        if direct_sign_rev:
            summary.direct_sign_revenue = _round(direct_sign_rev)
            summary.direct_sign_revenue_pct = _round(_safe_div(direct_sign_rev, rev) * 100 if rev else 0)
            summary.direct_sign_profit = _round(direct_sign_gp)
            summary.direct_sign_margin = _round(_safe_div(direct_sign_gp, direct_sign_rev) * 100)

        # Negative margin order metrics
        neg_margin_orders: list[tuple[float, float]] = []
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
            summary.negative_margin_order_amount = _round(sum(gross_profit for _, gross_profit in neg_margin_orders))

        # Negative margin product metrics
        neg_margin_products: list[float] = []
        for prod, bk in current_product_buckets.items():
            p_gp = bk.get("gross_profit")
            if p_gp is None:
                p_gp = (bk.get("revenue", 0) or 0) - (bk.get("cost", 0) or 0)
            if p_gp < 0:
                neg_margin_products.append(p_gp)
        if current_product_buckets:
            summary.negative_margin_product_ratio = _round(len(neg_margin_products) / len(current_product_buckets) * 100)
            summary.negative_margin_product_amount = _round(sum(neg_margin_products))

        # ── Per-dimension order counts ─────────────────────
        period_orders_dim: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            if row.period not in current_members:
                continue
            tags = row.tags or {}
            order_id = tags.get("order_id") or tags.get("contract_no")
            dim_value = _extract_dimension(row, dimension)
            if order_id and dim_value:
                period_orders_dim[str(dim_value)].add(order_id)

        # ── Breakdowns for current period ────────────────────
        breakdowns: list[BreakdownItem] = []
        if dimension != "company":
            dim_buckets = current_dim_buckets
            yoy_dim_buckets = _sum_nested_bucket_values(period_dim_bucket, _period_members(yoy_curr)) if yoy_curr else {}
            total_rev_for_contrib = sum((b.get("revenue", 0) or 0) for b in dim_buckets.values())
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

                d_order_count = len(period_orders_dim.get(str(dim_value), set()))
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

                d_aov = (d_rev / d_order_count) if (d_rev is not None and d_order_count > 0) else None

                d_yoy_rev: float | None = None
                yoy_bk = yoy_dim_buckets.get(dim_value, {})
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

        def _previous_trend_key(period_key: str) -> str | None:
            if period_dimension == "quarterly":
                return _previous_quarter(period_key)
            if period_dimension == "custom":
                return None
            return _previous_month(period_key)

        def _yoy_trend_key(period_key: str) -> str | None:
            if period_dimension == "quarterly" and "-Q" in period_key:
                year, quarter = period_key.split("-Q")
                return f"{int(year) - 1}-Q{quarter}"
            if period_dimension == "custom":
                return None
            return _yoy_period(period_key)

        # ── Trend series ─────────────────────────────────────
        trend: list[TrendDataPoint] = []
        for tp in trend_periods:
            t_rev, t_cost, t_gp = _bucket_values(tp)
            t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None

            tp_prev = _previous_trend_key(tp)
            p_rev, _, p_gp = _bucket_values(tp_prev) if tp_prev else (None, None, None)
            t_rev_mom = (_safe_div(t_rev - p_rev, p_rev) * 100) if (t_rev is not None and p_rev) else None
            t_gp_mom = (_safe_div(t_gp - p_gp, p_gp) * 100) if (t_gp is not None and p_gp) else None

            tp_yoy = _yoy_trend_key(tp)
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
        dim_trend: list[dict] = []
        if dimension != "company":
            for tp in trend_periods:
                dim_bk = _sum_nested_bucket_values(period_dim_bucket, _period_members(tp))
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

        rev_consec = 0
        gp_consec = 0
        for pt in reversed(trend):
            if pt.revenue_mom_growth is not None and pt.revenue_mom_growth > 0:
                rev_consec += 1
            else:
                break
        for pt in reversed(trend):
            if pt.gross_profit_mom_growth is not None and pt.gross_profit_mom_growth > 0:
                gp_consec += 1
            else:
                break
        summary.revenue_consecutive_growth = rev_consec
        summary.gross_profit_consecutive_growth = gp_consec

        gm_values = [pt.gross_margin for pt in trend if pt.gross_margin is not None]
        if len(gm_values) >= 2:
            avg = sum(gm_values) / len(gm_values)
            variance = sum((v - avg) ** 2 for v in gm_values) / len(gm_values)
            summary.gross_margin_volatility = round(variance ** 0.5, 2)

        # ── Margin change impact decomposition ─────────────
        if resolved_compare_period and dimension != "company":
            prev_dim = _sum_nested_bucket_values(period_dim_bucket, _period_members(resolved_compare_period))
            curr_dim = current_dim_buckets
            curr_total_rev = sum((bk.get("revenue", 0) or 0) for bk in curr_dim.values())
            prev_total_rev = sum((bk.get("revenue", 0) or 0) for bk in prev_dim.values())
            current_overall_margin = (gp / rev * 100) if (gp is not None and rev) else 0.0
            base_overall_margin = (prev_gp / prev_rev * 100) if (prev_gp is not None and prev_rev) else 0.0
            margin_analysis: list[MarginChangeItem] = []
            margin_summary = MarginChangeSummary(
                continuing_structure_impact=0.0,
                continuing_margin_impact=0.0,
                new_impact=0.0,
                exit_impact=0.0,
            )
            all_dims = set(curr_dim.keys()) | set(prev_dim.keys())
            for dim_val in all_dims:
                c_bk = curr_dim.get(dim_val, {})
                p_bk = prev_dim.get(dim_val, {})
                c_rev = c_bk.get("revenue", 0) or 0
                c_gp = c_bk.get("gross_profit")
                if c_gp is None:
                    c_gp = (c_rev - (c_bk.get("cost", 0) or 0)) if c_rev else 0
                p_rev = p_bk.get("revenue", 0) or 0
                p_gp = p_bk.get("gross_profit")
                if p_gp is None:
                    p_gp = (p_rev - (p_bk.get("cost", 0) or 0)) if p_rev else 0

                category = "continuing"
                if p_rev <= 0 < c_rev:
                    category = "new"
                elif c_rev <= 0 < p_rev:
                    category = "exit"

                c_share = (c_rev / curr_total_rev * 100) if curr_total_rev else 0
                p_share = (p_rev / prev_total_rev * 100) if prev_total_rev else 0
                c_gm = (c_gp / c_rev * 100) if c_rev else current_overall_margin
                p_gm = (p_gp / p_rev * 100) if p_rev else base_overall_margin

                share_change = c_share - p_share
                gm_change = c_gm - p_gm
                structure_impact = (c_share - p_share) * (c_gm - base_overall_margin) / 100
                margin_impact = p_share * (c_gm - p_gm) / 100
                total_impact = structure_impact + margin_impact

                if category == "continuing":
                    margin_summary.continuing_structure_impact = (margin_summary.continuing_structure_impact or 0) + structure_impact
                    margin_summary.continuing_margin_impact = (margin_summary.continuing_margin_impact or 0) + margin_impact
                elif category == "new":
                    margin_summary.new_impact = (margin_summary.new_impact or 0) + total_impact
                else:
                    margin_summary.exit_impact = (margin_summary.exit_impact or 0) + total_impact

                margin_analysis.append(MarginChangeItem(
                    dimension_value=str(dim_val),
                    category=category,
                    current_revenue=round(c_rev, 2),
                    current_share=round(c_share, 2),
                    current_margin=round(c_gm, 2),
                    base_revenue=round(p_rev, 2),
                    base_share=round(p_share, 2),
                    base_margin=round(p_gm, 2),
                    share_change=round(share_change, 2),
                    margin_change=round(gm_change, 2),
                    structure_impact=round(structure_impact, 4),
                    margin_impact=round(margin_impact, 4),
                    total_impact=round(total_impact, 4),
                ))

            margin_analysis.sort(key=lambda item: abs(item.total_impact or 0), reverse=True)
            summary.margin_change_analysis = margin_analysis
            summary.margin_change_summary = MarginChangeSummary(
                continuing_structure_impact=_round(margin_summary.continuing_structure_impact, 4),
                continuing_margin_impact=_round(margin_summary.continuing_margin_impact, 4),
                new_impact=_round(margin_summary.new_impact, 4),
                exit_impact=_round(margin_summary.exit_impact, 4),
            )

        # ── Customer breakdown (Top 10 by revenue) ──────────────
        customer_breakdown: list[BreakdownItem] = []
        total_cust_rev = sum((bk.get("revenue", 0) or 0) for bk in current_customer_buckets.values())
        for cust_name, bk in sorted(
            current_customer_buckets.items(), key=lambda x: x[1].get("revenue", 0), reverse=True
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
