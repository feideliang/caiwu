"""Core metrics service — reads pre-aggregated tables for dashboard metrics."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import and_, case, desc, func, literal, literal_column, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.models.core import (
    AggDimensionSummary,
    AggOrderSummary,
    AggPeriodSummary,
)
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


def compute_bucket(metric_name: str | None) -> str | None:
    """Compute bucket category from metric_name for pre-computed column."""
    if not metric_name:
        return None
    lower = metric_name.lower()
    # Check target_revenue first (more specific)
    if "target_revenue" in lower or "目标收入" in lower:
        return "target_revenue"
    # Check profit keywords
    if any(kw.lower() in lower for kw in _PROFIT_KW):
        return "gross_profit"
    # Check revenue keywords
    if any(kw.lower() in lower for kw in _REVENUE_KW):
        return "revenue"
    # Check cost keywords
    if any(kw.lower() in lower for kw in _COST_KW):
        return "cost"
    return None


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
        try:
            year, quarter = period.split("-Q")
            return f"{year}年Q{quarter}"
        except (ValueError, IndexError):
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
    """Aggregate core financial metrics from pre-aggregated tables."""

    @staticmethod
    async def _list_periods(db: AsyncSession, bgbu_filter: str = "ALL", limit: int = 24) -> list[str]:
        stmt = (
            select(AggPeriodSummary.period)
            .where(AggPeriodSummary.bgbu == bgbu_filter)
            .distinct()
            .order_by(desc(AggPeriodSummary.period))
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
        sections: set[str] | None = None,
        bgbu_filter: str = "ALL",
    ) -> CoreMetricsResponse:
        # ── department param overrides bgbu_filter ──
        if department:
            bgbu_filter = department

        # ── Cache check: data updates once per day, cache 24h ──
        _sections_key = ",".join(sorted(sections)) if sections else "all"
        _cache_key = f"metrics:core:v2:{period}:{dimension}:{compare}:{period_dimension}:{product}:{department}:{customer}:{bgbu_filter}:{_sections_key}"
        try:
            _cached = await cache_get(_cache_key)
            if _cached is not None:
                return CoreMetricsResponse(**_cached)
        except Exception:
            pass

        all_periods = await MetricsService._list_periods(db, bgbu_filter=bgbu_filter, limit=36)
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
                contract_type_breakdown=[],
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
        elif period_dimension == "cumulative":
            # For cumulative yoy: build cumulative period for previous year
            if current_period and len(current_period) >= 7:
                try:
                    year = int(current_period[:4])
                    month = current_period[4:]  # e.g. "-06"
                    yoy_curr = f"{year - 1}{month}"
                except ValueError:
                    yoy_curr = None
            else:
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

        # ── Read from pre-aggregated tables ──
        current_members = _period_members(current_period)
        detail_periods = set(current_members)
        if yoy_curr:
            detail_periods.update(_period_members(yoy_curr))

        # For cumulative: expand compare_period to YTD range (e.g. 2025-03 → 2025-01~2025-03)
        # _period_members already handles cumulative expansion via sorted_periods
        compare_members: list[str] = []
        if resolved_compare_period:
            compare_members = _period_members(resolved_compare_period)
            detail_periods.update(compare_members)

        mom_period = _previous_quarter(current_period) if period_dimension == "quarterly" else _previous_month(current_period)
        order_detail_periods = set(current_members)
        if yoy_curr:
            order_detail_periods.update(_period_members(yoy_curr))
        if mom_period:
            order_detail_periods.update(_period_members(mom_period))

        # ── Section flags: skip unneeded queries when caller only wants a subset ──
        _all = sections is None
        need_summary = _all or "summary" in sections
        need_breakdowns = _all or "breakdowns" in sections
        need_trend = _all or "trend_series" in sections
        need_customer_bd = _all or "customer_breakdown" in sections
        need_ct_bd = _all or "contract_type_breakdown" in sections
        need_dim_trend = _all or "dimension_trend_series" in sections
        need_margin_analysis = _all or "margin_analysis" in sections
        has_entity_filter = bool(product or customer)  # department handled via bgbu_filter

        _is_company_dim = dimension == "company"
        _is_dept_dim = dimension == "department"
        _is_customer_dim = dimension == "customer"
        _is_product_dim = dimension == "product_line"

        # ── 1. Period summary (replaces B1 + B6b + target_q + ds_q) ──
        period_bucket: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        period_order_counts: dict[str, int] = {}
        target_rev: float | None = None
        direct_sign_rev = 0.0
        direct_sign_gp = 0.0

        if need_summary or need_trend:
            ps_q = select(AggPeriodSummary).where(
                AggPeriodSummary.period.in_(list(query_periods)),
                AggPeriodSummary.bgbu == bgbu_filter,
            )
            ps_rows = (await db.execute(ps_q)).scalars().all()
            for row in ps_rows:
                p = row.period
                period_bucket[p]["revenue"] += float(row.revenue or 0)
                period_bucket[p]["cost"] += float(row.cost or 0)
                period_bucket[p]["gross_profit"] += float(row.gross_profit or 0)
                period_order_counts[p] = (period_order_counts.get(p, 0) + (row.order_count or 0))
                if p in current_members:
                    if need_summary:
                        target_rev = (target_rev or 0) + float(row.target_revenue or 0)
                        direct_sign_rev += float(row.direct_sign_revenue or 0)
                        direct_sign_gp += float(row.direct_sign_gp or 0)

        # ── 2. Dimension summary (replaces B2/B3/B4/B5/B7) ──
        # Map dimension parameter → dim_type in agg table
        _dim_type_map = {
            "product_line": "product_line",
            "sales_product": "sales_product",
            "customer": "customer",
            "contract_type": "contract_type",
        }

        # Main dimension breakdown
        period_dim_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        if not _is_company_dim and not _is_dept_dim:
            dim_type_key = _dim_type_map.get(dimension)
            if dim_type_key:
                dim_q = select(AggDimensionSummary).where(
                    AggDimensionSummary.period.in_(list(detail_periods)),
                    AggDimensionSummary.bgbu == bgbu_filter,
                    AggDimensionSummary.dim_type == dim_type_key,
                )
                if product and dimension == 'product_line':
                    dim_q = dim_q.where(AggDimensionSummary.dim_value == product)
                if customer and dimension == 'customer':
                    dim_q = dim_q.where(AggDimensionSummary.dim_value == customer)
                dim_rows = (await db.execute(dim_q)).scalars().all()
                for row in dim_rows:
                    period_dim_bucket[row.period][row.dim_value]["revenue"] += float(row.revenue or 0)
                    period_dim_bucket[row.period][row.dim_value]["cost"] += float(row.cost or 0)
                    period_dim_bucket[row.period][row.dim_value]["gross_profit"] += float(row.gross_profit or 0)

        # Department breakdown: from period_summary per-bgbu rows
        period_dept_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        if _is_dept_dim:
            # When dimension=department, populate period_dim_bucket from period_summary per-bgbu
            if bgbu_filter == "ALL":
                dept_dim_q = select(AggPeriodSummary).where(
                    AggPeriodSummary.period.in_(list(detail_periods)),
                    AggPeriodSummary.bgbu != "ALL",
                )
            else:
                dept_dim_q = select(AggPeriodSummary).where(
                    AggPeriodSummary.period.in_(list(detail_periods)),
                    AggPeriodSummary.bgbu == bgbu_filter,
                )
            dept_dim_rows = (await db.execute(dept_dim_q)).scalars().all()
            for row in dept_dim_rows:
                period_dim_bucket[row.period][row.bgbu]["revenue"] += float(row.revenue or 0)
                period_dim_bucket[row.period][row.bgbu]["cost"] += float(row.cost or 0)
                period_dim_bucket[row.period][row.bgbu]["gross_profit"] += float(row.gross_profit or 0)
                period_dept_bucket[row.period][row.bgbu]["revenue"] += float(row.revenue or 0)
                period_dept_bucket[row.period][row.bgbu]["cost"] += float(row.cost or 0)
                period_dept_bucket[row.period][row.bgbu]["gross_profit"] += float(row.gross_profit or 0)
        elif need_breakdowns:
            if bgbu_filter == "ALL":
                # Admin: get all per-department rows
                dept_q = select(AggPeriodSummary).where(
                    AggPeriodSummary.period.in_(list(detail_periods)),
                    AggPeriodSummary.bgbu != "ALL",
                )
            else:
                # Non-admin: just their department row
                dept_q = select(AggPeriodSummary).where(
                    AggPeriodSummary.period.in_(list(detail_periods)),
                    AggPeriodSummary.bgbu == bgbu_filter,
                )
            dept_rows = (await db.execute(dept_q)).scalars().all()
            for row in dept_rows:
                period_dept_bucket[row.period][row.bgbu]["revenue"] += float(row.revenue or 0)
                period_dept_bucket[row.period][row.bgbu]["cost"] += float(row.cost or 0)
                period_dept_bucket[row.period][row.bgbu]["gross_profit"] += float(row.gross_profit or 0)

        # Customer data — needed for concentration metrics, customer breakdown, or when dimension IS customer
        period_customer_rev: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        period_customer_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        if _is_customer_dim:
            for p, dim_bk in period_dim_bucket.items():
                for dv, bk in dim_bk.items():
                    for bkt, val in bk.items():
                        period_customer_bucket[p][dv][bkt] += val
                        if bkt == 'revenue':
                            period_customer_rev[p][dv] += val
        elif (need_customer_bd or need_summary) and not _is_customer_dim:
            total_q = (
                select(AggDimensionSummary.period, func.sum(AggDimensionSummary.revenue))
                .where(
                    AggDimensionSummary.period.in_(list(detail_periods)),
                    AggDimensionSummary.bgbu == bgbu_filter,
                    AggDimensionSummary.dim_type == "customer",
                )
                .group_by(AggDimensionSummary.period)
            )
            tq_rows = (await db.execute(total_q)).all()
            for period_val, total_rev in tq_rows:
                period_customer_rev[period_val]["__total__"] = float(total_rev or 0)

            # (2) Single query using ROW_NUMBER() window function for Top 30 per period
            # Push the rn <= 30 filter into SQL via subquery to avoid fetching all rows
            _CUST_LIMIT = 30
            from sqlalchemy import over, func as sql_func
            row_num = (
                sql_func.row_number()
                .over(
                    partition_by=AggDimensionSummary.period,
                    order_by=desc(AggDimensionSummary.revenue),
                )
                .label("rn")
            )
            # Subquery with window function
            cust_subq = (
                select(
                    AggDimensionSummary.period,
                    AggDimensionSummary.dim_value,
                    AggDimensionSummary.revenue,
                    AggDimensionSummary.cost,
                    AggDimensionSummary.gross_profit,
                    row_num,
                )
                .where(
                    AggDimensionSummary.period.in_(list(detail_periods)),
                    AggDimensionSummary.bgbu == bgbu_filter,
                    AggDimensionSummary.dim_type == "customer",
                )
            ).subquery()
            # Filter ranked results in SQL
            top_cust_q = select(cust_subq).where(cust_subq.c.rn <= _CUST_LIMIT)
            cust_rows = (await db.execute(top_cust_q)).all()
            for row in cust_rows:
                period_customer_bucket[row[0]][row[1]]["revenue"] += float(row[2] or 0)
                period_customer_bucket[row[0]][row[1]]["cost"] += float(row[3] or 0)
                period_customer_bucket[row[0]][row[1]]["gross_profit"] += float(row[4] or 0)
                period_customer_rev[row[0]][row[1]] += float(row[2] or 0)

        # Product data — needed for concentration metrics, product breakdown, or when dimension IS product
        # Skip for department dimension: concentration is company-level, product BD not relevant
        period_product_gp: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        period_product_rev: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        period_product_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        if _is_product_dim:
            # Bridge from period_dim_bucket when dimension IS product_line
            for p, dim_bk in period_dim_bucket.items():
                for dv, bk in dim_bk.items():
                    for bkt, val in bk.items():
                        period_product_bucket[p][dv][bkt] += val
                        if bkt == 'gross_profit':
                            period_product_gp[p][dv] += val
                        if bkt == 'revenue':
                            period_product_rev[p][dv] += val
        elif (need_breakdowns or need_summary) and not _is_product_dim:
            # Push GROUP BY to SQL: aggregate revenue/cost/gp per (period, product)
            prod_q = select(
                AggDimensionSummary.period,
                AggDimensionSummary.dim_value,
                func.sum(AggDimensionSummary.revenue).label("revenue"),
                func.sum(AggDimensionSummary.cost).label("cost"),
                func.sum(AggDimensionSummary.gross_profit).label("gross_profit"),
            ).where(
                AggDimensionSummary.period.in_(list(detail_periods)),
                AggDimensionSummary.bgbu == bgbu_filter,
                AggDimensionSummary.dim_type == "sales_product",
            ).group_by(
                AggDimensionSummary.period,
                AggDimensionSummary.dim_value,
            )
            prod_rows = (await db.execute(prod_q)).all()
            for row in prod_rows:
                period_product_bucket[row[0]][row[1]]["revenue"] += float(row[2] or 0)
                period_product_bucket[row[0]][row[1]]["cost"] += float(row[3] or 0)
                period_product_bucket[row[0]][row[1]]["gross_profit"] += float(row[4] or 0)
                period_product_gp[row[0]][row[1]] += float(row[4] or 0)
                period_product_rev[row[0]][row[1]] += float(row[2] or 0)

        # Contract type breakdown
        period_ct_bucket: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        if need_ct_bd:
            ct_q = select(AggDimensionSummary).where(
                AggDimensionSummary.period.in_(list(current_members)),
                AggDimensionSummary.bgbu == bgbu_filter,
                AggDimensionSummary.dim_type == "contract_type",
            )
            ct_rows = (await db.execute(ct_q)).scalars().all()
            for row in ct_rows:
                period_ct_bucket[row.period][row.dim_value]["revenue"] += float(row.revenue or 0)
                period_ct_bucket[row.period][row.dim_value]["cost"] += float(row.cost or 0)
                period_ct_bucket[row.period][row.dim_value]["gross_profit"] += float(row.gross_profit or 0)

        # ── 3. Order summary (replaces B6a + dim_q) ──
        # Aggregate in SQL by (period, order_id) to reduce rows from ~114K to ~30K
        period_order: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        ord_rows: list = []  # populated below for downstream per-dimension order counts
        if need_breakdowns or need_summary:
            ord_agg_q = select(
                AggOrderSummary.period,
                AggOrderSummary.order_id,
                func.sum(AggOrderSummary.revenue).label("revenue"),
                func.sum(AggOrderSummary.cost).label("cost"),
                func.sum(AggOrderSummary.gross_profit).label("gross_profit"),
            ).where(
                AggOrderSummary.period.in_(list(order_detail_periods)),
                AggOrderSummary.bgbu == bgbu_filter,
            ).group_by(
                AggOrderSummary.period,
                AggOrderSummary.order_id,
            )
            if product:
                ord_agg_q = ord_agg_q.where(AggOrderSummary.dim_product == product)
            ord_rows = (await db.execute(ord_agg_q)).all()
            for row in ord_rows:
                period_order[row[0]][row[1]]["revenue"] += float(row[2] or 0)
                period_order[row[0]][row[1]]["cost"] += float(row[3] or 0)
                period_order[row[0]][row[1]]["gross_profit"] += float(row[4] or 0)

        # Per-dimension order counts for breakdown
        period_orders_dim: dict[str, set[str]] = defaultdict(set)
        if need_breakdowns and not _is_company_dim and not _is_dept_dim:
            # Map orders to dimension values via dim_dept/dim_product or re-query
            dim_type_key = _dim_type_map.get(dimension)
            if dim_type_key and ord_rows:
                # Use dim_dept for department-linked orders, dim_product for product-linked
                # For customer/sales_product/contract_type, we use dim_summary order_count instead
                pass  # Will use order_count from agg_dimension_summary below
            elif _is_customer_dim or _is_product_dim:
                pass  # Use order_count from dimension summary
            # For department dimension, use period_summary rows
            if _is_dept_dim:
                pass  # Will use period_dept_bucket order counts

        # Populate dimension order counts + negative margin metrics from SQL
        # Replaces raw tuple fetch: previously fetched all (period, dim, order_id) tuples
        # and processed in Python; now uses COUNT(DISTINCT) + conditional aggregation.
        _dim_order_count: dict[str, int] = {}
        _dim_neg_orders: dict[str, int] = {}
        _dim_neg_amount: dict[str, float] = {}
        if need_breakdowns:
            if _is_dept_dim and bgbu_filter == "ALL":
                ord_dim_q = select(
                    AggOrderSummary.dim_dept,
                    func.count(func.distinct(AggOrderSummary.order_id)).label("order_count"),
                    func.count(func.distinct(case((AggOrderSummary.gross_profit < 0, AggOrderSummary.order_id)))).label("neg_order_count"),
                    func.sum(case((AggOrderSummary.gross_profit < 0, AggOrderSummary.gross_profit), else_=0)).label("neg_margin_amount"),
                ).where(
                    AggOrderSummary.period.in_(list(current_members)),
                    AggOrderSummary.bgbu == "ALL",
                    AggOrderSummary.dim_dept.isnot(None),
                ).group_by(AggOrderSummary.dim_dept)
                for dept, cnt, neg_cnt, neg_amt in (await db.execute(ord_dim_q)).all():
                    if dept:
                        _dim_order_count[str(dept)] = int(cnt)
                        _dim_neg_orders[str(dept)] = int(neg_cnt) if neg_cnt else 0
                        _dim_neg_amount[str(dept)] = float(neg_amt or 0)
            elif _is_product_dim:
                ord_dim_q = select(
                    AggOrderSummary.dim_product,
                    func.count(func.distinct(AggOrderSummary.order_id)).label("order_count"),
                    func.count(func.distinct(case((AggOrderSummary.gross_profit < 0, AggOrderSummary.order_id)))).label("neg_order_count"),
                    func.sum(case((AggOrderSummary.gross_profit < 0, AggOrderSummary.gross_profit), else_=0)).label("neg_margin_amount"),
                ).where(
                    AggOrderSummary.period.in_(list(current_members)),
                    AggOrderSummary.bgbu == bgbu_filter,
                    AggOrderSummary.dim_product.isnot(None),
                ).group_by(AggOrderSummary.dim_product)
                for prod, cnt, neg_cnt, neg_amt in (await db.execute(ord_dim_q)).all():
                    if prod:
                        _dim_order_count[str(prod)] = int(cnt)
                        _dim_neg_orders[str(prod)] = int(neg_cnt) if neg_cnt else 0
                        _dim_neg_amount[str(prod)] = float(neg_amt or 0)

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

        # ── Helper: aggregate from filtered dim buckets ──
        def _filtered_bucket_values(p: str | None) -> tuple[float | None, float | None, float | None]:
            """Sum revenue/cost/gp across all dimension values in period_dim_bucket for a period."""
            if not p:
                return None, None, None
            members = _period_members(p)
            if not members:
                return None, None, None
            total_rev = 0.0
            total_cost = 0.0
            total_gp = 0.0
            has_data = False
            for m in members:
                for bk in period_dim_bucket.get(m, {}).values():
                    r = bk.get('revenue')
                    c = bk.get('cost')
                    g = bk.get('gross_profit')
                    if r is not None:
                        total_rev += r
                        has_data = True
                    if c is not None:
                        total_cost += c
                    if g is not None:
                        total_gp += g
            if not has_data:
                return None, None, None
            if total_gp is None and total_rev is not None and total_cost is not None:
                total_gp = total_rev - total_cost
            return total_rev if total_rev else None, total_cost if total_cost else None, total_gp if total_gp else None


        # ── Summary for current period ─────────────────────
        has_entity_filter = product or customer
        if has_entity_filter:
            rev, cost, gp = _filtered_bucket_values(current_period)
        else:
            rev, cost, gp = _bucket_values(current_period)
        gm = _safe_div(gp, rev) * 100 if (gp is not None and rev) else None

        # YoY (_period_members already expands to YTD for cumulative periods)
        yoy_rev = yoy_cost = yoy_gp = None
        if has_entity_filter:
            if yoy_curr:
                yoy_rev, yoy_cost, yoy_gp = _filtered_bucket_values(yoy_curr)
        else:
            if yoy_curr:
                yoy_rev, yoy_cost, yoy_gp = _bucket_values(yoy_curr)
        rev_yoy = (_safe_div(rev - yoy_rev, yoy_rev) * 100) if (rev is not None and yoy_rev) else None
        cost_yoy = (_safe_div(cost - yoy_cost, yoy_cost) * 100) if (cost is not None and yoy_cost) else None
        gp_yoy = (_safe_div(gp - yoy_gp, yoy_gp) * 100) if (gp is not None and yoy_gp) else None

        # MoM (true previous month/quarter, independent of compare param)
        prev_rev = prev_cost = prev_gp = None
        mom_period = _previous_quarter(current_period) if period_dimension == "quarterly" else _previous_month(current_period)
        if mom_period:
            if has_entity_filter:
                prev_rev, prev_cost, prev_gp = _filtered_bucket_values(mom_period)
            else:
                prev_rev, prev_cost, prev_gp = _bucket_values(mom_period)
        rev_mom = (_safe_div(rev - prev_rev, prev_rev) * 100) if (rev is not None and prev_rev) else None
        gp_mom = (_safe_div(gp - prev_gp, prev_gp) * 100) if (gp is not None and prev_gp) else None
        # MoM gross margin change (pp)
        mom_gm = _safe_div(prev_gp, prev_rev) * 100 if (prev_gp is not None and prev_rev) else None
        gm_mom_change = _round(gm - mom_gm, 2) if (gm is not None and mom_gm is not None) else None

        # Gross margin YoY change (pp)
        yoy_gm = _safe_div(yoy_gp, yoy_rev) * 100 if (yoy_gp is not None and yoy_rev) else None
        gm_yoy_change = _round(gm - yoy_gm, 2) if (gm is not None and yoy_gm is not None) else None

        current_dim_buckets = _sum_nested_bucket_values(period_dim_bucket, current_members)
        current_dept_buckets = _sum_nested_bucket_values(period_dept_bucket, current_members)
        current_customer_rev = _sum_scalar_groups(period_customer_rev, current_members)
        current_product_gp = _sum_scalar_groups(period_product_gp, current_members)
        current_product_rev = _sum_scalar_groups(period_product_rev, current_members)
        current_product_buckets = _sum_nested_bucket_values(period_product_bucket, current_members)
        current_order_buckets = _sum_nested_bucket_values(period_order, current_members)
        current_customer_buckets = _sum_nested_bucket_values(period_customer_bucket, current_members)
        current_ct_buckets = _sum_nested_bucket_values(period_ct_bucket, current_members)

        # Customer concentration top3 (revenue)
        # Use __total__ key (from SQL SUM) as accurate denominator when Top-N optimization is active
        cust_rev = current_customer_rev
        total_cust_rev_for_ratio = cust_rev.pop("__total__", None)
        if total_cust_rev_for_ratio is None:
            total_cust_rev_for_ratio = sum(cust_rev.values()) if cust_rev else 0.0
        cust_top3 = None
        if cust_rev and total_cust_rev_for_ratio:
            top3_sum = sum(sorted(cust_rev.values(), reverse=True)[:3])
            cust_top3 = min(top3_sum / total_cust_rev_for_ratio * 100, 100.0)

        # Customer concentration top3 MoM change (pp)
        cust_top3_change = None
        if cust_top3 is not None and mom_period and prev_rev:
            mom_members = _period_members(mom_period)
            mom_cust = {}
            for m in mom_members:
                for dv, bk in period_dim_bucket.get(m, {}).items():
                    mom_cust[dv] = mom_cust.get(dv, 0) + (bk.get("revenue") or 0)
            if mom_cust:
                mom_total = sum(mom_cust.values())
                if mom_total:
                    mom_top3_sum = sum(sorted(mom_cust.values(), reverse=True)[:3])
                    mom_top3 = min(mom_top3_sum / mom_total * 100, 100.0)
                    cust_top3_change = _round(cust_top3 - mom_top3, 2)

        # Customer concentration top10 (revenue)
        cust_top10 = None
        if cust_rev and total_cust_rev_for_ratio:
            top10_sum = sum(sorted(cust_rev.values(), reverse=True)[:10])
            cust_top10 = min(top10_sum / total_cust_rev_for_ratio * 100, 100.0)

        # Top single customer revenue share
        cust_top1_share = None
        if cust_rev and total_cust_rev_for_ratio:
            cust_top1_share = min(max(cust_rev.values()) / total_cust_rev_for_ratio * 100, 100.0)

        # Product concentration top3 (gross_profit)
        # Use sum of all product gross_profits as denominator for consistency
        # Note: at company/dept level, not product-filtered
        prod_rev = current_product_rev
        prod_top3 = None
        total_prod_rev = sum(prod_rev.values()) if prod_rev else 0.0
        if prod_rev and total_prod_rev:
            top3_sum = sum(sorted(prod_rev.values(), reverse=True)[:3])
            prod_top3 = min(top3_sum / total_prod_rev * 100, 100.0)

        # Product concentration top10 (gross_profit)
        prod_top10 = None
        if prod_rev and total_prod_rev:
            top10_sum = sum(sorted(prod_rev.values(), reverse=True)[:10])
            prod_top10 = min(top10_sum / total_prod_rev * 100, 100.0)

        # ── Order metrics: single-pass consolidation (was 3 separate loops) ──
        # Computes: high_margin_ratio, order_count, loss_ratio,
        #           negative_margin_order_ratio/amount, neg_margin_orders list
        orders = current_order_buckets
        high_margin_ratio: float | None = None
        order_ids: set[str] = set()
        high_orders = 0
        loss_orders = 0
        total_orders_count = 0
        neg_margin_total = 0.0
        neg_margin_orders: list[tuple[float, float]] = []

        if orders:
            for oid, bk in orders.items():
                o_rev = bk.get("revenue")
                o_cost = bk.get("cost")
                o_gp = bk.get("gross_profit")
                if o_gp is None and o_rev is not None and o_cost is not None:
                    o_gp = o_rev - o_cost
                if o_rev is not None:
                    order_ids.add(oid)
                    total_orders_count += 1
                    if o_gp is not None:
                        o_margin = o_gp / o_rev * 100 if o_rev else None
                        if o_margin is not None and o_margin > high_margin_threshold:
                            high_orders += 1
                        if o_gp < 0:
                            loss_orders += 1
                            neg_margin_total += o_gp
                            neg_margin_orders.append((o_rev, o_gp))
            if total_orders_count > 0:
                high_margin_ratio = min(high_orders / total_orders_count * 100, 100.0)
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
            gross_margin_yoy_change=_round(gm_yoy_change),
            gross_margin_mom_change=_round(gm_mom_change),
            gross_margin_contribution=100.0 if gp is not None else None,
            customer_concentration_top3=_round(cust_top3),  # fix: removed hardcoded test
            customer_concentration_top3_change=_round(cust_top3_change),
            product_concentration_top3=_round(prod_top3),
            customer_concentration_top10=_round(cust_top10),
            product_concentration_top10=_round(prod_top10),
            top_customer_share=_round(cust_top1_share),
            high_margin_order_ratio=_round(high_margin_ratio),
            revenue_yoy_growth=_round(rev_yoy),
            cost_yoy_growth=_round(cost_yoy),
            gross_profit_yoy_growth=_round(gp_yoy),
            base_revenue=_round(yoy_rev) if yoy_rev is not None else 0.0,
            base_gross_profit=_round(yoy_gp) if yoy_gp is not None else 0.0,
            revenue_mom_growth=_round(rev_mom),
            gross_profit_mom_growth=_round(gp_mom),
        )

        # ── Order-based metrics (computed in single-pass loop above) ──
        summary.order_count = len(order_ids) if order_ids else None
        summary.loss_ratio = round(loss_orders / total_orders_count * 100, 2) if total_orders_count else None

        # ── Metrics only at company/dept scope (not product-filterable) ──
        if not has_entity_filter:
            # Achievement rate (target_rev from AggPeriodSummary)
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

            # Direct sign customer metrics (from AggPeriodSummary, not product-filterable)
            if direct_sign_rev:
                summary.direct_sign_revenue = _round(direct_sign_rev)
                summary.direct_sign_revenue_pct = _round(_safe_div(direct_sign_rev, rev) * 100 if rev else 0)
                summary.direct_sign_profit = _round(direct_sign_gp)
                summary.direct_sign_margin = _round(_safe_div(direct_sign_gp, direct_sign_rev) * 100) if direct_sign_gp is not None else None

        # Negative margin order metrics (computed in single-pass loop above)
        if total_orders_count:
            summary.negative_margin_order_ratio = _round(len(neg_margin_orders) / total_orders_count * 100)
            summary.negative_margin_order_amount = _round(neg_margin_total)

        # Negative margin order ratio YoY/MoM change (pp)
        if total_orders_count and summary.negative_margin_order_ratio is not None:
            cur = summary.negative_margin_order_ratio

            def _order_neg_ratio(bk: dict) -> float | None:
                if not bk:
                    return None
                neg = 0
                for _, ob in bk.items():
                    o_rev = ob.get("revenue")
                    o_cost = ob.get("cost")
                    o_gp = ob.get("gross_profit")
                    if o_gp is None and o_rev is not None and o_cost is not None:
                        o_gp = o_rev - o_cost
                    if o_rev is not None and o_gp is not None and o_gp < 0:
                        neg += 1
                return neg / len(bk) * 100

            if yoy_curr:
                yoy_orders = _sum_nested_bucket_values(period_order, _period_members(yoy_curr))
                yoy_r = _order_neg_ratio(yoy_orders)
                if yoy_r is not None:
                    summary.negative_margin_order_yoy_change = _round(cur - yoy_r, 2)
            if mom_period:
                mom_orders = _sum_nested_bucket_values(period_order, _period_members(mom_period))
                mom_r = _order_neg_ratio(mom_orders)
                if mom_r is not None:
                    summary.negative_margin_order_mom_change = _round(cur - mom_r, 2)

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

        # Negative margin product ratio YoY/MoM change (pp)
        if current_product_buckets and summary.negative_margin_product_ratio is not None:
            cur = summary.negative_margin_product_ratio
            if yoy_curr:
                yoy_buckets = _sum_nested_bucket_values(period_product_bucket, _period_members(yoy_curr))
                if yoy_buckets:
                    yoy_neg = 0
                    for _, bk in yoy_buckets.items():
                        p_gp = bk.get("gross_profit")
                        if p_gp is None:
                            p_gp = (bk.get("revenue", 0) or 0) - (bk.get("cost", 0) or 0)
                        if p_gp < 0:
                            yoy_neg += 1
                    summary.negative_margin_product_yoy_change = _round(cur - yoy_neg / len(yoy_buckets) * 100, 2)
            if mom_period:
                mom_buckets = _sum_nested_bucket_values(period_product_bucket, _period_members(mom_period))
                if mom_buckets:
                    mom_neg = 0
                    for _, bk in mom_buckets.items():
                        p_gp = bk.get("gross_profit")
                        if p_gp is None:
                            p_gp = (bk.get("revenue", 0) or 0) - (bk.get("cost", 0) or 0)
                        if p_gp < 0:
                            mom_neg += 1
                    summary.negative_margin_product_mom_change = _round(cur - mom_neg / len(mom_buckets) * 100, 2)


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

                # Order count: use SQL-computed count if available, otherwise fallback to set
                d_order_count = _dim_order_count.get(str(dim_value)) or len(period_orders_dim.get(str(dim_value), set()))
                # Negative margin orders: use SQL-computed values if available
                if str(dim_value) in _dim_neg_orders:
                    d_neg_orders = _dim_neg_orders[str(dim_value)]
                    d_neg_amount = _dim_neg_amount[str(dim_value)]
                else:
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
                d_yoy_rev = (_safe_div(d_rev - yoy_rev, yoy_rev) * 100) if (d_rev is not None and yoy_rev) else None

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
            if has_entity_filter:
                t_rev, t_cost, t_gp = _filtered_bucket_values(tp)
            else:
                t_rev, t_cost, t_gp = _bucket_values(tp)
            t_gm = (t_gp / t_rev * 100) if (t_gp is not None and t_rev) else None
            t_order_count = period_order_counts.get(tp, 0)

            tp_prev = _previous_trend_key(tp)
            if has_entity_filter:
                p_rev, _, p_gp = _filtered_bucket_values(tp_prev) if tp_prev else (None, None, None)
            else:
                p_rev, _, p_gp = _bucket_values(tp_prev) if tp_prev else (None, None, None)
            p_gm = (p_gp / p_rev * 100) if (p_gp is not None and p_rev) else None
            p_order_count = period_order_counts.get(tp_prev, 0) if tp_prev else None

            t_rev_mom = (_safe_div(t_rev - p_rev, p_rev) * 100) if (t_rev is not None and p_rev) else None
            t_gp_mom = (_safe_div(t_gp - p_gp, p_gp) * 100) if (t_gp is not None and p_gp) else None
            t_gm_mom = _round(t_gm - p_gm) if (t_gm is not None and p_gm is not None) else None
            t_order_mom = (_safe_div(t_order_count - p_order_count, p_order_count) * 100) if (t_order_count is not None and p_order_count) else None

            tp_yoy = _yoy_trend_key(tp)
            if has_entity_filter:
                y_rev, _, y_gp = _filtered_bucket_values(tp_yoy) if tp_yoy else (None, None, None)
            else:
                y_rev, _, y_gp = _bucket_values(tp_yoy) if tp_yoy else (None, None, None)
            y_gm = (y_gp / y_rev * 100) if (y_gp is not None and y_rev) else None
            y_order_count = period_order_counts.get(tp_yoy, 0) if tp_yoy else None

            t_rev_yoy = (_safe_div(t_rev - y_rev, y_rev) * 100) if (t_rev is not None and y_rev) else None
            t_gp_yoy = (_safe_div(t_gp - y_gp, y_gp) * 100) if (t_gp is not None and y_gp) else None
            t_gm_yoy = _round(t_gm - y_gm) if (t_gm is not None and y_gm is not None) else None
            t_order_yoy = (_safe_div(t_order_count - y_order_count, y_order_count) * 100) if (t_order_count is not None and y_order_count) else None

            trend.append(TrendDataPoint(
                period=_format_period_label(tp, period_dimension),
                revenue=_round(t_rev),
                cost=_round(t_cost),
                gross_profit=_round(t_gp),
                gross_margin=_round(t_gm),
                order_count=t_order_count or None,
                revenue_mom_growth=_round(t_rev_mom),
                revenue_yoy_growth=_round(t_rev_yoy),
                gross_profit_mom_growth=_round(t_gp_mom),
                gross_profit_yoy_growth=_round(t_gp_yoy),
                gross_margin_mom_growth=_round(t_gm_mom),
                gross_margin_yoy_growth=_round(t_gm_yoy),
                order_count_mom_growth=_round(t_order_mom),
                order_count_yoy_growth=_round(t_order_yoy),
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

        def _count_consecutive(trend_list, field_name: str) -> int:
            """Count the length of the most recent consecutive growth streak."""
            n = len(trend_list)
            last_positive_idx = -1
            for i in range(n - 1, -1, -1):
                val = getattr(trend_list[i], field_name)
                if val is not None and val > 0:
                    last_positive_idx = i
                    break
            if last_positive_idx == -1:
                return 0
            streak = 1
            for i in range(last_positive_idx - 1, -1, -1):
                val = getattr(trend_list[i], field_name)
                if val is not None and val > 0:
                    streak += 1
                else:
                    break
            return streak

        summary.revenue_consecutive_growth = _count_consecutive(trend, 'revenue_mom_growth')
        summary.gross_profit_consecutive_growth = _count_consecutive(trend, 'gross_profit_mom_growth')

        gm_values = [pt.gross_margin for pt in trend if pt.gross_margin is not None]
        if len(gm_values) >= 2:
            avg = sum(gm_values) / len(gm_values)
            variance = sum((v - avg) ** 2 for v in gm_values) / len(gm_values)
            summary.gross_margin_volatility = round(variance ** 0.5, 2)
            # Volatility MoM change: compare with volatility excluding latest period
            if len(gm_values) >= 3:
                prev_gm = gm_values[:-1]
                prev_avg = sum(prev_gm) / len(prev_gm)
                prev_var = sum((v - prev_avg) ** 2 for v in prev_gm) / len(prev_gm)
                prev_vol = round(prev_var ** 0.5, 2)
                summary.gross_margin_volatility_change = round(summary.gross_margin_volatility - prev_vol, 2)

        # ── Margin change impact decomposition ─────────────
        if compare_members and dimension != "company":
            prev_dim = _sum_nested_bucket_values(period_dim_bucket, compare_members)
            curr_dim = current_dim_buckets
            current_overall_margin = (gp / rev * 100) if (gp is not None and rev) else 0.0
            base_overall_margin = (prev_gp / prev_rev * 100) if (prev_gp is not None and prev_rev) else 0.0
            curr_total_rev = sum((bk.get("revenue", 0) or 0) for bk in curr_dim.values())
            prev_total_rev = sum((bk.get("revenue", 0) or 0) for bk in prev_dim.values())
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
                structure_impact = (c_share - p_share) * p_gm / 100 if p_gm is not None else 0.0
                margin_impact = c_share * (c_gm - p_gm) / 100 if (c_gm is not None and p_gm is not None) else 0.0
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

            # ── Compute MoM of impact factors ──
            # Find previous period of resolved_compare_period for MoM comparison
            prev_compare = _previous_quarter(resolved_compare_period) if period_dimension == "quarterly" else _previous_month(resolved_compare_period)
            prev_mom_summary = None
            if prev_compare:
                prev_dim_pp = _sum_nested_bucket_values(period_dim_bucket, _period_members(prev_compare))
                if prev_dim_pp:
                    prev_total_rev_pp = sum((bk.get("revenue", 0) or 0) for bk in prev_dim_pp.values())
                    prev_total_gp_pp = sum(
                        (bk.get("gross_profit") if bk.get("gross_profit") is not None
                         else ((bk.get("revenue", 0) or 0) - (bk.get("cost", 0) or 0)))
                        for bk in prev_dim_pp.values()
                    )
                    prev_overall_gm_pp = (prev_total_gp_pp / prev_total_rev_pp * 100) if prev_total_rev_pp and prev_total_gp_pp is not None else 0.0
                    prev_mom = MarginChangeSummary(
                        continuing_structure_impact=0.0,
                        continuing_margin_impact=0.0,
                        new_impact=0.0,
                        exit_impact=0.0,
                    )
                    prev_dims = set(curr_dim.keys()) | set(prev_dim_pp.keys())
                    for dv in prev_dims:
                        vc_bk = prev_dim_pp.get(dv, {})
                        vp_bk = prev_dim.get(dv, {})
                        vc_rev = vc_bk.get("revenue", 0) or 0
                        vc_gp = vc_bk.get("gross_profit")
                        if vc_gp is None:
                            vc_gp = (vc_rev - (vc_bk.get("cost", 0) or 0)) if vc_rev else 0
                        vp_rev = vp_bk.get("revenue", 0) or 0
                        vp_gp = vp_bk.get("gross_profit")
                        if vp_gp is None:
                            vp_gp = (vp_rev - (vp_bk.get("cost", 0) or 0)) if vp_rev else 0

                        v_category = "continuing"
                        if vp_rev <= 0 < vc_rev:
                            v_category = "new"
                        elif vc_rev <= 0 < vp_rev:
                            v_category = "exit"

                        vc_share = (vc_rev / prev_total_rev_pp * 100) if prev_total_rev_pp else 0
                        vp_share = (vp_rev / prev_total_rev_pp * 100) if prev_total_rev_pp else 0
                        vc_gm = (vc_gp / vc_rev * 100) if vc_rev else prev_overall_gm_pp
                        vp_gm = (vp_gp / vp_rev * 100) if vp_rev else prev_overall_gm_pp

                        v_structure = (vc_share - vp_share) * vp_gm / 100 if vp_gm is not None else 0.0
                        v_margin = vc_share * (vc_gm - vp_gm) / 100 if (vc_gm is not None and vp_gm is not None) else 0.0
                        v_total = v_structure + v_margin

                        if v_category == "continuing":
                            prev_mom.continuing_structure_impact = (prev_mom.continuing_structure_impact or 0) + v_structure
                            prev_mom.continuing_margin_impact = (prev_mom.continuing_margin_impact or 0) + v_margin
                        elif v_category == "new":
                            prev_mom.new_impact = (prev_mom.new_impact or 0) + v_total
                        else:
                            prev_mom.exit_impact = (prev_mom.exit_impact or 0) + v_total

                    prev_mom_summary = prev_mom

            summary.margin_change_summary = MarginChangeSummary(
                continuing_structure_impact=_round(margin_summary.continuing_structure_impact, 4),
                continuing_margin_impact=_round(margin_summary.continuing_margin_impact, 4),
                new_impact=_round(margin_summary.new_impact, 4),
                exit_impact=_round(margin_summary.exit_impact, 4),
                continuing_structure_impact_mom=_round(margin_summary.continuing_structure_impact - (prev_mom_summary.continuing_structure_impact if prev_mom_summary else 0), 4),
                continuing_margin_impact_mom=_round(margin_summary.continuing_margin_impact - (prev_mom_summary.continuing_margin_impact if prev_mom_summary else 0), 4),
                new_impact_mom=_round(margin_summary.new_impact - (prev_mom_summary.new_impact if prev_mom_summary else 0), 4),
                exit_impact_mom=_round(margin_summary.exit_impact - (prev_mom_summary.exit_impact if prev_mom_summary else 0), 4),
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

        # ── Contract type breakdown ───────────────────────────────
        contract_type_breakdown: list[BreakdownItem] = []
        total_ct_rev = sum((bk.get("revenue", 0) or 0) for bk in current_ct_buckets.values())
        for ct_name, bk in sorted(
            current_ct_buckets.items(), key=lambda x: x[1].get("revenue", 0), reverse=True
        ):
            c_rev = bk.get("revenue")
            c_cost = bk.get("cost")
            c_gp = bk.get("gross_profit")
            if c_gp is None and c_rev is not None and c_cost is not None:
                c_gp = c_rev - c_cost
            c_gm = _safe_div(c_gp, c_rev) * 100 if (c_gp is not None and c_rev) else None
            c_contrib = _safe_div(c_gp, total_ct_rev) * 100 if (c_gp is not None and total_ct_rev) else None
            c_rev_contrib = _safe_div(c_rev, total_ct_rev) * 100 if (c_rev is not None and total_ct_rev) else None
            contract_type_breakdown.append(BreakdownItem(
                dimension_value=ct_name,
                revenue=_round(c_rev),
                tax_excluded_cost=_round(c_cost),
                gross_profit=_round(c_gp),
                gross_margin=_round(c_gm),
                revenue_contribution=_round(c_rev_contrib),
                gross_margin_contribution=_round(c_contrib),
                calculable=(c_rev is not None and c_gp is not None),
            ))

        _response = CoreMetricsResponse(
            period=current_period,
            dimension=dimension,
            entity=entity,
            summary=summary,
            breakdowns=breakdowns,
            customer_breakdown=customer_breakdown,
            contract_type_breakdown=contract_type_breakdown,
            trend_series=trend,
            dimension_trend_series=dim_trend,
            data_quality=DataQuality(
                calculable=calculable,
                missing_fields=missing_fields,
                warnings=warnings,
            ),
        )

        # ── Cache the result for 24 hours (data updates ~once per day) ──
        try:
            await cache_set(_cache_key, _response.model_dump(mode="json"), ttl=86400)
        except Exception:
            pass

        return _response