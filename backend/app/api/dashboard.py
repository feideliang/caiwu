"""Dashboard BFF endpoint — aggregates dashboard layout + chart data."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import cache_get, cache_set, DEFAULT_TTL
from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.core import ChartConfig, DashboardLayout, FinancialData
from app.models.v3 import Insight
from app.schemas.query import DashboardBFFRequest, DashboardBFFResponse, ChartDataItem, KpiData, BreakdownItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _metric_filters(*keywords: str):
    return or_(*[FinancialData.metric_name.ilike(f"%{keyword}%") for keyword in keywords])


async def _periods(db: AsyncSession, limit: int = 12, department: str | None = None, product: str | None = None) -> list[str]:
    from sqlalchemy import text
    filters = []
    if department:
        filters.append(FinancialData.entity == department)
    if product:
        filters.append(text("tags->>'product_line' = :prod OR tags->>'product' = :prod OR tags->>'series' = :prod"))
    stmt = select(FinancialData.period).distinct().where(*filters).order_by(desc(FinancialData.period)).limit(limit)
    if product:
        stmt = stmt.params(prod=product)
    return [row[0] for row in (await db.execute(stmt)).all() if row[0]]


# Keywords for each KPI bucket
_REVENUE_KW = ("revenue", "营业收入", "sales")
_COST_KW = ("cost", "成本", "expense")
_PROFIT_KW = ("gross_profit", "毛利润", "gross profit")
_ACHIEVEMENT_KW = ("achievement_rate", "达成率")


async def _build_kpis(
    db: AsyncSession,
    period_compare_type: str | None = None,
    period_dimension: str | None = None,
    period: str | None = None,
    department: str | None = None,
    product: str | None = None,
) -> dict:
    # Build base filters
    base_filters = []
    if department:
        base_filters.append(FinancialData.entity == department)
    if product:
        from sqlalchemy import text
        product_filter = text(
            "(tags->>'product_line' = :prod OR tags->>'product' = :prod OR tags->>'series' = :prod)"
        ).bindparams(prod=product)
        base_filters.append(product_filter)

    trend_periods = await _periods(db, limit=24, department=department, product=product)

    # Determine current period based on period_dimension
    # cumulative mode: period is a year string like "2026"
    # monthly mode: period is a month string like "2026-03"
    if period_dimension == 'cumulative' and period and len(period) == 4:
        current_period = period
    else:
        current_period = period if period else (trend_periods[0] if trend_periods else None)

    # If explicit period not in trend_periods list, add it (skip for year-only periods)
    if period and period not in trend_periods and len(period) >= 7:
        trend_periods.insert(0, period)
    previous_period = trend_periods[1] if len(trend_periods) > 1 else None

    # Compute YoY period
    yoy_period = None
    if current_period and len(current_period) >= 7:
        # Format: "2026-03" or "2026-Q1"
        year = int(current_period[:4])
        rest = current_period[5:]
        yoy_period = f"{year - 1}-{rest}"
    elif current_period and len(current_period) == 4:
        # Year-only: YoY is previous year
        yoy_period = str(int(current_period) - 1)

    # Query all needed periods: current, previous, YoY, and all for cumulative YTD
    query_periods = set(trend_periods[:12])
    if yoy_period:
        query_periods.add(yoy_period)
    # For YTD cumulative, get all periods from year start
    if current_period and len(current_period) >= 4:
        year_prefix = current_period[:4]
        ytd_periods = [p for p in trend_periods if p and p.startswith(year_prefix)]
        query_periods.update(ytd_periods)
        # Last year's YTD
        ytd_periods_ly = [p for p in trend_periods if p and p.startswith(f"{int(year_prefix)-1}")]
        query_periods.update(ytd_periods_ly)

    query_periods_list = list(query_periods)

    # Batch query: sum all metric types for all needed periods in one query.
    all_metrics = {}
    if query_periods_list:
        stmt = (
            select(
                FinancialData.period,
                FinancialData.metric_name,
                func.coalesce(func.sum(FinancialData.metric_value), 0).label("total"),
            )
            .where(FinancialData.period.in_(query_periods_list), *base_filters)
            .group_by(FinancialData.period, FinancialData.metric_name)
        )
        rows = (await db.execute(stmt)).all()
        for period, metric_name, total in rows:
            all_metrics.setdefault(period, {})[metric_name] = float(total)

    def _sum(period: str | None, *keywords: str) -> float:
        if not period:
            return 0.0
        # Year-only period (e.g., "2026") → sum all months in that year
        if len(period) == 4 and period.isdigit():
            total = 0.0
            for p, pdata in all_metrics.items():
                if p.startswith(f"{period}-"):
                    for mname, val in pdata.items():
                        for kw in keywords:
                            if kw.lower() in mname.lower():
                                total += val
                                break
            return total
        period_data = all_metrics.get(period, {})
        for mname, val in period_data.items():
            for kw in keywords:
                if kw.lower() in mname.lower():
                    return val
        return 0.0

    # Current period
    revenue = _sum(current_period, *_REVENUE_KW)
    cost = _sum(current_period, *_COST_KW)
    gross_profit = revenue - cost if (revenue or cost) else _sum(current_period, *_PROFIT_KW)
    gross_margin = round((gross_profit / revenue * 100), 2) if revenue else 0.0
    achievement_rate = _sum(current_period, *_ACHIEVEMENT_KW)

    # MoM (month-over-month) - previous period
    prev_revenue = _sum(previous_period, *_REVENUE_KW) if previous_period else 0.0
    prev_profit = _sum(previous_period, *_PROFIT_KW) if previous_period else 0.0
    revenue_mom_growth = round(((revenue - prev_revenue) / prev_revenue * 100), 2) if prev_revenue else 0.0
    profit_mom_growth = round(((gross_profit - prev_profit) / prev_profit * 100), 2) if prev_profit else 0.0

    # YoY (year-over-year)
    yoy_revenue = _sum(yoy_period, *_REVENUE_KW) if yoy_period else 0.0
    yoy_cost = _sum(yoy_period, *_COST_KW) if yoy_period else 0.0
    yoy_profit = _sum(yoy_period, *_PROFIT_KW) if yoy_period else 0.0
    yoy_gross_margin = round((yoy_profit / yoy_revenue * 100), 2) if yoy_revenue else 0.0
    revenue_yoy_growth = round(((revenue - yoy_revenue) / yoy_revenue * 100), 2) if yoy_revenue else 0.0
    cost_yoy_growth = round(((cost - yoy_cost) / yoy_cost * 100), 2) if yoy_cost else 0.0
    profit_yoy_growth = round(((gross_profit - yoy_profit) / yoy_profit * 100), 2) if yoy_profit else 0.0
    gross_margin_yoy_change = round(gross_margin - yoy_gross_margin, 2) if yoy_revenue else 0.0

    # Cumulative YTD
    year_prefix = current_period[:4] if current_period else None
    ytd_periods = [p for p in all_metrics.keys() if p and p.startswith(year_prefix)] if year_prefix else []
    ytd_revenue = sum(_sum(p, *_REVENUE_KW) for p in ytd_periods)
    ytd_profit = sum((_sum(p, *_REVENUE_KW) - _sum(p, *_COST_KW)) for p in ytd_periods)

    ytd_periods_ly = [p for p in all_metrics.keys() if p and p.startswith(f"{int(year_prefix)-1}")] if year_prefix else []
    ytd_revenue_ly = sum(_sum(p, *_REVENUE_KW) for p in ytd_periods_ly)
    ytd_profit_ly = sum((_sum(p, *_REVENUE_KW) - _sum(p, *_COST_KW)) for p in ytd_periods_ly)

    revenue_cumulative_growth = round(((ytd_revenue - ytd_revenue_ly) / ytd_revenue_ly * 100), 2) if ytd_revenue_ly else 0.0
    profit_cumulative_growth = round(((ytd_profit - ytd_profit_ly) / ytd_profit_ly * 100), 2) if ytd_profit_ly else 0.0

    # Trend series: Jan of previous year to latest month (full year range)
    sorted_periods = sorted(trend_periods)
    if sorted_periods:
        latest = sorted_periods[-1]
        latest_year = int(latest[:4])
        start_year = latest_year - 1
        # Filter periods from Jan of previous year to latest
        trend_full = [p for p in sorted_periods if p >= f"{start_year}-01" and p <= latest]
    else:
        trend_full = []

    trend_series = []
    for tp in trend_full:
        tr = _sum(tp, *_REVENUE_KW)
        tc = _sum(tp, *_COST_KW)
        tg = tr - tc
        tm = round((tg / tr * 100), 2) if tr else 0.0
        trend_series.append({
            "period": tp,
            "revenue": round(tr, 2),
            "cost": round(tc, 2),
            "gross_profit": round(tg, 2),
            "gross_margin": tm,
        })

    return {
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin": gross_margin,
        "achievement_rate": round(achievement_rate, 2),
        "revenue_mom_growth": revenue_mom_growth,
        "profit_mom_growth": profit_mom_growth,
        "cost_yoy_growth": cost_yoy_growth,
        "revenue_yoy_growth": revenue_yoy_growth,
        "profit_yoy_growth": profit_yoy_growth,
        "gross_margin_yoy_change": gross_margin_yoy_change,
        "revenue_cumulative": round(ytd_revenue, 2),
        "profit_cumulative": round(ytd_profit, 2),
        "revenue_cumulative_growth": revenue_cumulative_growth,
        "profit_cumulative_growth": profit_cumulative_growth,
        "trend_series": trend_series,
    }


async def _build_dimension_breakdowns(
    db: AsyncSession,
    department: str | None = None,
    product: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Build department and product breakdowns from FinancialData.

    Returns (department_breakdown, product_breakdown).
    """
    all_periods = await _periods(db, limit=12, department=department, product=product)
    current_period = all_periods[0] if all_periods else None

    if not current_period:
        return [], []

    # Query all financial data for current period
    stmt = select(FinancialData).where(FinancialData.period == current_period)
    if department:
        stmt = stmt.where(FinancialData.entity == department)
    rows = (await db.execute(stmt)).scalars().all()

    # Aggregate by department (from tags.department or entity)
    dept_buckets: dict[str, dict[str, float]] = {}
    # Aggregate by product (from tags.product_line / product / series)
    prod_buckets: dict[str, dict[str, float]] = {}

    for row in rows:
        tags = row.tags or {}
        # Filter by product if specified
        if product:
            row_product = tags.get("product_line") or tags.get("product") or tags.get("series")
            if row_product != product:
                continue
        bucket_name: str | None = None
        if "revenue" in row.metric_name.lower() or "营业收入" in row.metric_name or "sales" in row.metric_name.lower():
            bucket_name = "revenue"
        elif "cost" in row.metric_name.lower() or "成本" in row.metric_name or "不含税" in row.metric_name:
            bucket_name = "cost"
        elif "gross_profit" in row.metric_name.lower() or "毛利润" in row.metric_name or "gross profit" in row.metric_name.lower():
            bucket_name = "gross_profit"

        if bucket_name is None:
            continue

        v = float(row.metric_value or 0.0)

        # Department dimension
        dept = tags.get("department") or row.entity
        if dept:
            dept_buckets.setdefault(dept, {"revenue": 0.0, "cost": 0.0, "gross_profit": 0.0})
            dept_buckets[dept][bucket_name] += v

        # Product dimension
        row_product = tags.get("product_line") or tags.get("product") or tags.get("series")
        if row_product:
            prod_buckets.setdefault(row_product, {"revenue": 0.0, "cost": 0.0, "gross_profit": 0.0})
            prod_buckets[row_product][bucket_name] += v

    # Build department breakdown
    total_gp_dept = sum(
        (b.get("gross_profit") or 0) if b.get("gross_profit") is not None
        else ((b.get("revenue", 0) - b.get("cost", 0)) if b.get("revenue") is not None and b.get("cost") is not None else 0)
        for b in dept_buckets.values()
    )
    dept_items: list[dict] = []
    for dim_value, bk in sorted(dept_buckets.items(), key=lambda x: x[1].get("revenue", 0), reverse=True):
        d_rev = bk.get("revenue")
        d_cost = bk.get("cost")
        d_gp = bk.get("gross_profit")
        if d_gp is None and d_rev is not None and d_cost is not None:
            d_gp = d_rev - d_cost
        d_gm = (d_gp / d_rev * 100) if (d_gp is not None and d_rev) else None
        contrib = (d_gp / total_gp_dept * 100) if (d_gp is not None and total_gp_dept) else None
        dept_items.append({
            "dimension_value": str(dim_value),
            "revenue": round(d_rev, 2) if d_rev is not None else None,
            "tax_excluded_cost": round(d_cost, 2) if d_cost is not None else None,
            "gross_profit": round(d_gp, 2) if d_gp is not None else None,
            "gross_margin": round(d_gm, 2) if d_gm is not None else None,
            "gross_margin_contribution": round(contrib, 2) if contrib is not None else None,
        })

    # Build product breakdown
    total_gp_prod = sum(
        (b.get("gross_profit") or 0) if b.get("gross_profit") is not None
        else ((b.get("revenue", 0) - b.get("cost", 0)) if b.get("revenue") is not None and b.get("cost") is not None else 0)
        for b in prod_buckets.values()
    )
    prod_items: list[dict] = []
    for dim_value, bk in sorted(prod_buckets.items(), key=lambda x: x[1].get("gross_profit", 0) or 0, reverse=True):
        d_rev = bk.get("revenue")
        d_cost = bk.get("cost")
        d_gp = bk.get("gross_profit")
        if d_gp is None and d_rev is not None and d_cost is not None:
            d_gp = d_rev - d_cost
        d_gm = (d_gp / d_rev * 100) if (d_gp is not None and d_rev) else None
        contrib = (d_gp / total_gp_prod * 100) if (d_gp is not None and total_gp_prod) else None
        prod_items.append({
            "dimension_value": str(dim_value),
            "revenue": round(d_rev, 2) if d_rev is not None else None,
            "tax_excluded_cost": round(d_cost, 2) if d_cost is not None else None,
            "gross_profit": round(d_gp, 2) if d_gp is not None else None,
            "gross_margin": round(d_gm, 2) if d_gm is not None else None,
            "gross_margin_contribution": round(contrib, 2) if contrib is not None else None,
        })

    return dept_items, prod_items


@router.post("/bff", response_model=APIResponse)
async def dashboard_bff(
    body: DashboardBFFRequest,
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_current_user),
) -> APIResponse:
    """Fetch a complete dashboard with chart data, optimized for the target device."""
    cache_key = f"dashboard:bff:{body.dashboard_id or 'default'}:{body.device_type}:{body.period or ''}:{body.period_dimension or ''}:{body.department or ''}:{body.product or ''}"

    if not body.bypass_cache:
        cached = await cache_get(cache_key)
        if cached is not None:
            return APIResponse.success(data=cached)

    # Load layout
    stmt = select(DashboardLayout).where(DashboardLayout.device_type == body.device_type)
    if body.dashboard_id:
        stmt = stmt.where(DashboardLayout.id == body.dashboard_id)
    result = await db.execute(stmt)
    layout = result.scalar_one_or_none()

    if layout is None:
        # Fall back to "web" default
        stmt = select(DashboardLayout).where(DashboardLayout.device_type == "web").limit(1)
        result = await db.execute(stmt)
        layout = result.scalar_one_or_none()

    if layout is None:
        raise ResourceNotFoundError("No dashboard layout found for this device type")

    chart_ids = layout.chart_ids or []

    # Load chart configs
    chart_configs: list[dict] = []
    if chart_ids:
        chart_result = await db.execute(select(ChartConfig).where(ChartConfig.id.in_(chart_ids)))
        chart_configs = [
            {
                "id": c.id,
                "name": c.name,
                "chart_type": c.chart_type,
                "config": c.config,
            }
            for c in chart_result.scalars().all()
        ]

    # Batch-load all chart data in a single query (replaces N queries, one per chart)
    all_chart_metrics: dict[int, list[dict]] = {cc["id"]: [] for cc in chart_configs}
    if chart_configs:
        all_metric_names: list[str] = []
        for cc in chart_configs:
            metrics = (cc.get("config") or {}).get("metrics", [])
            for m in metrics:
                if m not in all_metric_names:
                    all_metric_names.append(m)
        if all_metric_names:
            stmt = select(
                FinancialData.metric_name, FinancialData.metric_value, FinancialData.period,
                FinancialData.entity, FinancialData.tags,
            ).where(FinancialData.metric_name.in_(all_metric_names))
            # Apply period filter
            if body.period:
                stmt = stmt.where(FinancialData.period == body.period)
            # Apply department filter
            if body.department:
                stmt = stmt.where(FinancialData.entity == body.department)
            # Apply product filter
            if body.product:
                from sqlalchemy import text
                prod_filter = text("tags->>'product_line' = :prod OR tags->>'product' = :prod OR tags->>'series' = :prod")
                stmt = stmt.where(prod_filter).params(prod=body.product)
            stmt = stmt.order_by(FinancialData.period)
            rows = (await db.execute(stmt)).all()
            # Build lookup: metric_name -> list of {metric_name, metric_value, period}
            metric_rows: dict[str, list[dict]] = {}
            for r in rows:
                metric_rows.setdefault(r[0], []).append({"metric_name": r[0], "metric_value": r[1], "period": r[2]})
            # Assign to each chart config based on its metrics
            for cc in chart_configs:
                metrics = (cc.get("config") or {}).get("metrics", [])
                rows_for_cc = []
                for m in metrics:
                    rows_for_cc.extend(metric_rows.get(m, []))
                all_chart_metrics[cc["id"]] = rows_for_cc

    chart_data_items: list[ChartDataItem] = []
    for cc in chart_configs:
        chart_data_items.append(ChartDataItem(
            id=cc["id"],
            title=cc["name"],
            type=cc["chart_type"],
            data=all_chart_metrics[cc["id"]],
            options=cc.get("config"),
        ))

    dept_items, prod_items = await _build_dimension_breakdowns(db, department=body.department, product=body.product)

    response_data = DashboardBFFResponse(
        dashboard_id=layout.id,
        dashboard_name=layout.name,
        device_type=body.device_type,
        kpis=KpiData(**(await _build_kpis(db, body.period_compare_type, period_dimension=body.period_dimension, period=body.period, department=body.department, product=body.product))),
        charts=chart_data_items,
        layout=layout.layout_config,
        updated_at=datetime.now(timezone.utc).isoformat(),
        department_breakdown=dept_items,
        product_breakdown=prod_items,
    ).model_dump()

    await cache_set(cache_key, response_data, DEFAULT_TTL)
    return APIResponse.success(data=response_data)


@router.get("/insights", response_model=APIResponse)
async def list_insights(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    insight_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_current_user),
) -> APIResponse:
    """List AI-generated insights."""
    stmt = select(Insight)
    if insight_type:
        stmt = stmt.where(Insight.insight_type == insight_type)

    # Count
    count_stmt = select(func.count()).select_from(Insight)
    if insight_type:
        count_stmt = count_stmt.where(Insight.insight_type == insight_type)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(Insight.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    insights = [
        {
            "id": i.id,
            "title": i.title,
            "type": i.insight_type,
            "description": i.content,
            "severity": (i.data_json or {}).get("severity", "medium"),
            "status": (i.data_json or {}).get("status", "unread"),
            "confidence": (i.data_json or {}).get("confidence", 0.7),
            "data_json": i.data_json or {},
            "related_chart_id": i.source_chart_id,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in result.scalars().all()
    ]
    return APIResponse.success(data={"items": insights, "total": total, "page": page, "page_size": page_size})
