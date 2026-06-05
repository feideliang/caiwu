"""Dashboard BFF endpoint — aggregates dashboard layout + chart data."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import cache_get, cache_set, DEFAULT_TTL
from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import TokenPayload, get_current_user
from app.db.session import get_db
from app.models.core import AggDimensionSummary, AggPeriodSummary, ChartConfig, DashboardLayout
from app.models.v3 import Insight
from app.schemas.query import DashboardBFFRequest, DashboardBFFResponse, ChartDataItem, KpiData, BreakdownItem
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _periods(db: AsyncSession, limit: int = 12, department: str | None = None, product: str | None = None, user: TokenPayload | None = None) -> list[str]:
    bgbu = (user.department if (user and user.role != "admin" and user.department) else "ALL")
    stmt = (
        select(AggPeriodSummary.period)
        .where(AggPeriodSummary.bgbu == bgbu)
        .distinct()
        .order_by(desc(AggPeriodSummary.period))
        .limit(limit)
    )
    return [row[0] for row in (await db.execute(stmt)).all() if row[0]]


# Keywords for each KPI bucket
_REVENUE_KW = ("revenue", "营业收入", "sales")
_COST_KW = ("cost", "成本", "expense")
_PROFIT_KW = ("gross_profit", "毛利润", "gross profit")
_TARGET_KW = ("target_revenue", "目标收入", "预算收入")


async def _build_kpis(
    db: AsyncSession,
    period_compare_type: str | None = None,
    period_dimension: str | None = None,
    period: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    department: str | None = None,
    product: str | None = None,
    customer: str | None = None,
    user: TokenPayload | None = None,
) -> dict:
    compare_mode = period_compare_type or "yoy"

    # Compute YoY period: subtract 1 year from the requested period string
    yoy_period = None
    if period and len(period) >= 7:
        try:
            year = int(period[:4])
            yoy_period = f"{year - 1}{period[4:]}"
        except ValueError:
            pass

    # Determine dimension based on active filters
    if product:
        dim = "product_bgbu"
    elif department:
        dim = "department"
    elif customer:
        dim = "customer"
    else:
        dim = "company"

    bgbu_filter = (user.department if (user and user.role != "admin" and user.department) else "ALL")

    # Sequential execution (shared db session cannot handle concurrent queries)
    current = await MetricsService.get_core_metrics(
        db=db,
        period=period,
        dimension=dim,
        compare=compare_mode,
        period_dimension=period_dimension or "monthly",
        period_start=period_start,
        period_end=period_end,
        product=product,
        department=department,
        customer=customer,
        bgbu_filter=bgbu_filter,
        sections={"summary", "trend_series"},
    )
    yoy = await MetricsService.get_core_metrics(
        db=db,
        period=yoy_period,
        dimension=dim,
        compare="yo",
        period_dimension=period_dimension or "monthly",
        period_start=period_start,
        period_end=period_end,
        product=product,
        department=department,
        customer=customer,
        bgbu_filter=bgbu_filter,
        sections={"summary", "trend_series"},
    )
    summary = current.summary
    yoy_summary = yoy.summary
    return {
        "revenue": round(summary.revenue or 0, 2),
        "cost": round(summary.tax_excluded_cost or 0, 2),
        "gross_profit": round(summary.gross_profit or 0, 2),
        "gross_margin": round(summary.gross_margin or 0, 2),
        "achievement_rate": round(summary.achievement_rate or 0, 2),
        "revenue_mom_growth": round(summary.revenue_mom_growth, 2) if summary.revenue_mom_growth is not None else None,
        "profit_mom_growth": round(summary.gross_profit_mom_growth, 2) if summary.gross_profit_mom_growth is not None else None,
        "cost_yoy_growth": round(summary.cost_yoy_growth, 2) if summary.cost_yoy_growth is not None else None,
        "revenue_yoy_growth": round(summary.revenue_yoy_growth, 2) if summary.revenue_yoy_growth is not None else None,
        "profit_yoy_growth": round(summary.gross_profit_yoy_growth, 2) if summary.gross_profit_yoy_growth is not None else None,
        "gross_margin_yoy_change": round((summary.gross_margin or 0) - (yoy_summary.gross_margin or 0), 2) if (summary.gross_margin is not None and yoy_summary.gross_margin is not None) else None,
        "base_revenue": round(yoy_summary.revenue or 0, 2),
        "base_gross_profit": round(yoy_summary.gross_profit or 0, 2),
        "base_gross_margin": round(yoy_summary.gross_margin or 0, 2),
        "base_achievement_rate": round(yoy_summary.achievement_rate or 0, 2),
        "revenue_cumulative": round(summary.revenue or 0, 2) if period_dimension == "cumulative" else 0.0,
        "profit_cumulative": round(summary.gross_profit or 0, 2) if period_dimension == "cumulative" else 0.0,
        "revenue_cumulative_growth": round(summary.revenue_yoy_growth, 2) if (period_dimension == "cumulative" and summary.revenue_yoy_growth is not None) else None,
        "profit_cumulative_growth": round(summary.gross_profit_yoy_growth, 2) if (period_dimension == "cumulative" and summary.gross_profit_yoy_growth is not None) else None,
        "revenue_consecutive_growth": (summary.revenue_consecutive_growth or 0) if period_dimension != "monthly" else None,
        "gross_profit_consecutive_growth": (summary.gross_profit_consecutive_growth or 0) if period_dimension != "monthly" else None,
        "customer_concentration_top10": round(summary.customer_concentration_top10 or 0, 2),
        "customer_concentration_top3": round(summary.customer_concentration_top3 or 0, 2),
        "top_customer_share": round(summary.top_customer_share or 0, 2),
        "high_margin_order_ratio": round(summary.high_margin_order_ratio or 0, 2),
        "negative_margin_order_ratio": round(summary.negative_margin_order_ratio or 0, 2),
        "trend_series": [point.model_dump() for point in current.trend_series],
    }


async def _build_dimension_breakdowns(
    db: AsyncSession,
    department: str | None = None,
    product: str | None = None,
    period_compare_type: str | None = None,
    period_dimension: str | None = None,
    period: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    user: TokenPayload | None = None,
) -> tuple[list[dict], list[dict]]:
    bgbu_filter = (user.department if (user and user.role != "admin" and user.department) else "ALL")

    # Sequential execution (shared db session cannot handle concurrent queries)
    dept_response = await MetricsService.get_core_metrics(
        db=db,
        period=period,
        dimension="department",
        compare=period_compare_type or "yoy",
        period_dimension=period_dimension or "monthly",
        period_start=period_start,
        period_end=period_end,
        product=product,
        department=department,
        bgbu_filter=bgbu_filter,
        sections={"breakdowns"},
    )
    prod_response = await MetricsService.get_core_metrics(
        db=db,
        period=period,
        dimension="product_bgbu",
        compare=period_compare_type or "yoy",
        period_dimension=period_dimension or "monthly",
        period_start=period_start,
        period_end=period_end,
        product=product,
        department=department,
        bgbu_filter=bgbu_filter,
        sections={"breakdowns"},
    )
    return (
        [item.model_dump() for item in dept_response.breakdowns],
        [item.model_dump() for item in prod_response.breakdowns],
    )


@router.post("/bff", response_model=APIResponse)
async def dashboard_bff(
    body: DashboardBFFRequest,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Fetch a complete dashboard with chart data, optimized for the target device."""
    dept_scope = user.department or ""
    cache_key = f"dashboard:bff:{body.dashboard_id or 'default'}:{body.device_type}:{body.period or ''}:{body.period_dimension or ''}:{body.department or ''}:{body.product or ''}:{dept_scope}"

    if not body.bypass_cache:
        try:
            cached = await cache_get(cache_key)
            if cached is not None:
                return APIResponse.success(data=cached)
        except Exception:
            pass

    try:
        return await _build_dashboard_response(body, db, cache_key, user)
    except Exception:
        raise


async def _build_dashboard_response(body, db: AsyncSession, cache_key: str, user: TokenPayload) -> APIResponse:
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
            bgbu_filter = (user.department if (user and user.role != "admin" and user.department) else "ALL")
            # Map chart metric keywords to agg column names
            _METRIC_TO_COL = {
                "revenue": "revenue", "营业收入": "revenue", "sales": "revenue",
                "cost": "cost", "成本": "cost", "expense": "cost",
                "gross_profit": "gross_profit", "毛利润": "gross_profit", "gross profit": "gross_profit",
                "target_revenue": "target_revenue", "目标收入": "target_revenue", "预算收入": "target_revenue",
            }

            agg_cols: list[str] = []
            for m in all_metric_names:
                col = _METRIC_TO_COL.get(m.lower())
                if col and col not in agg_cols:
                    agg_cols.append(col)

            all_rows: list[dict] = []

            # Determine the effective bgbu filter for chart data
            # When department filter is active, scope to that department
            # When product filter is active, read from dim_summary instead
            if body.department:
                eff_bgbu = body.department
            elif bgbu_filter != "ALL":
                eff_bgbu = bgbu_filter
            else:
                eff_bgbu = "ALL"

            if body.product:
                # Product filter: read from AggDimensionSummary with product_bgbu dim_type
                stmt_chart = (
                    select(AggDimensionSummary)
                    .where(
                        AggDimensionSummary.dim_type == "product_bgbu",
                        AggDimensionSummary.dim_value == body.product,
                    )
                )
                if body.period:
                    stmt_chart = stmt_chart.where(AggDimensionSummary.period == body.period)
                if body.department or bgbu_filter != "ALL":
                    stmt_chart = stmt_chart.where(AggDimensionSummary.bgbu == eff_bgbu)
                chart_rows = (await db.execute(stmt_chart)).scalars().all()
                for r in chart_rows:
                    for m in all_metric_names:
                        col = _METRIC_TO_COL.get(m.lower())
                        if col and hasattr(r, col):
                            val = getattr(r, col, 0) or 0
                            if val:
                                all_rows.append({"metric_name": m, "metric_value": val, "period": r.period, "entity": r.dim_value})
            else:
                # Company/department level: read from AggPeriodSummary
                stmt_chart = select(AggPeriodSummary).where(AggPeriodSummary.bgbu == eff_bgbu)
                if body.period:
                    stmt_chart = stmt_chart.where(AggPeriodSummary.period == body.period)
                chart_rows = (await db.execute(stmt_chart)).scalars().all()
                for r in chart_rows:
                    for m in all_metric_names:
                        col = _METRIC_TO_COL.get(m.lower())
                        if col and hasattr(r, col):
                            val = getattr(r, col, 0) or 0
                            if val:
                                all_rows.append({"metric_name": m, "metric_value": val, "period": r.period, "entity": r.bgbu})

            # Build lookup: metric_name -> list of {metric_name, metric_value, period, entity}
            metric_rows: dict[str, list[dict]] = {}
            for r in all_rows:
                metric_rows.setdefault(r["metric_name"], []).append(r)
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

    # Sequential execution of KPIs and dimension breakdowns (shared db session)
    kpis_result = await _build_kpis(
        db,
        body.period_compare_type,
        period_dimension=body.period_dimension,
        period=body.period,
        period_start=body.period_start,
        period_end=body.period_end,
        department=body.department,
        product=body.product,
        user=user,
    )
    dept_items, prod_items = await _build_dimension_breakdowns(
        db,
        department=body.department,
        product=body.product,
        period_compare_type=body.period_compare_type,
        period_dimension=body.period_dimension,
        period=body.period,
        period_start=body.period_start,
        period_end=body.period_end,
        user=user,
    )

    response_data = DashboardBFFResponse(
        dashboard_id=layout.id,
        dashboard_name=layout.name,
        device_type=body.device_type,
        kpis=KpiData(**kpis_result),
        charts=chart_data_items,
        layout=layout.layout_config,
        updated_at=datetime.now(timezone.utc).isoformat(),
        department_breakdown=dept_items,
        product_breakdown=prod_items,
    ).model_dump()

    try:
        await cache_set(cache_key, response_data, DEFAULT_TTL)
    except Exception:
        pass
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
