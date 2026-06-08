"""Drilldown endpoints: hierarchical financial data exploration.

Rewritten to use aggregated tables (agg_period_summary, agg_dimension_summary,
agg_order_summary) instead of direct financial_data queries.

Paths:
- GET /drilldowns/{report_id}/summary
- GET /drilldowns/{report_id}/departments
- GET /drilldowns/{report_id}/products
- GET /drilldowns/{report_id}/departments/{dept_id}/products
- GET /drilldowns/{report_id}/records
- GET /drilldowns/{report_id}/departments/{dept_id}/products/{product_id}/records
- GET /drilldowns/records/{record_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import decode_access_token, TokenPayload, get_current_user, get_data_scope_filter
from app.db.session import get_db
from app.models.core import AggDimensionSummary, AggOrderSummary, AggPeriodSummary, FinancialData

router = APIRouter(prefix="/drilldowns", tags=["drilldowns"])


def get_optional_user(request: Request) -> TokenPayload | None:
    """Try to extract JWT user from Authorization header; return None if not authenticated."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return TokenPayload.model_validate(decode_access_token(auth_header.split(" ", 1)[1]))
    except Exception:
        return None


def _get_bgbu_filter(user: TokenPayload | None) -> str:
    """Return the bgbu value to filter on: user's department for non-admin, or 'ALL' for admin."""
    if user and user.role != "admin" and user.department:
        return user.department
    return "ALL"


@router.get("/{report_id}/summary", response_model=APIResponse)
async def drilldown_summary(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Company-level summary: total revenue, cost, profit, margin, department count.

    Uses agg_period_summary for period-level summaries.
    """
    bgbu = _get_bgbu_filter(user)
    period_prefix = None if report_id == "default" else report_id

    stmt = select(
        AggPeriodSummary.period,
        func.sum(AggPeriodSummary.revenue).label("total_revenue"),
        func.sum(AggPeriodSummary.cost).label("total_cost"),
        func.sum(AggPeriodSummary.gross_profit).label("total_gp"),
        func.sum(AggPeriodSummary.order_count).label("total_orders"),
        func.sum(AggPeriodSummary.direct_sign_revenue).label("total_direct_rev"),
        func.sum(AggPeriodSummary.direct_sign_cost).label("total_direct_cost"),
        func.sum(AggPeriodSummary.direct_sign_gp).label("total_direct_gp"),
        func.sum(AggPeriodSummary.target_revenue).label("total_target"),
    ).where(AggPeriodSummary.bgbu == bgbu)

    if period_prefix:
        stmt = stmt.where(AggPeriodSummary.period.like(f"{period_prefix}%"))

    stmt = stmt.group_by(AggPeriodSummary.period)
    result = await db.execute(stmt)
    rows = result.all()

    total_revenue = 0.0
    total_cost = 0.0
    total_gp = 0.0
    total_orders = 0
    period_count = 0

    for row in rows:
        period_count += 1
        total_revenue += float(row.total_revenue or 0)
        total_cost += float(row.total_cost or 0)
        total_gp += float(row.total_gp or 0)
        total_orders += int(row.total_orders or 0)

    # If cost is zero across all periods, signal no cost data
    total_cost_val = total_cost if total_cost > 0 else None

    total_profit = (total_revenue - total_cost_val) if total_cost_val is not None else None
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 and total_profit is not None else None

    return APIResponse.success(
        data={
            "report_id": report_id,
            "title": f"财务总览 - {report_id}",
            "level": 1,
            "breadcrumbs": [],
            "metrics": {
                "total_revenue": round(total_revenue, 2),
                "total_cost": round(total_cost_val, 2) if total_cost_val is not None else None,
                "total_profit": round(total_profit, 2) if total_profit is not None else None,
                "avg_margin": round(profit_margin, 2) if profit_margin is not None else None,
                "total_orders": total_orders,
            },
            "has_children": period_count > 0,
        }
    )


@router.get("/{report_id}/departments", response_model=APIResponse)
async def drilldown_departments(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Department-level breakdown within a report period.

    Uses agg_period_summary WHERE bgbu != 'ALL' to get per-department revenue/cost.
    """
    period_prefix = None if report_id == "default" else report_id

    stmt = select(
        AggPeriodSummary.bgbu,
        func.sum(AggPeriodSummary.revenue).label("total_revenue"),
        func.sum(AggPeriodSummary.cost).label("total_cost"),
        func.sum(AggPeriodSummary.gross_profit).label("total_gp"),
        func.sum(AggPeriodSummary.order_count).label("total_orders"),
    ).where(
        AggPeriodSummary.bgbu != "ALL",
    )

    if period_prefix:
        stmt = stmt.where(AggPeriodSummary.period.like(f"{period_prefix}%"))

    # Apply user scope filter: non-admin users can only see their department
    user_bgbu = _get_bgbu_filter(user)
    if user_bgbu != "ALL":
        stmt = stmt.where(AggPeriodSummary.bgbu == user_bgbu)

    stmt = (
        stmt
        .group_by(AggPeriodSummary.bgbu)
        .order_by(func.sum(AggPeriodSummary.revenue).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    departments = []
    for idx, row in enumerate(rows):
        revenue = float(row.total_revenue or 0)
        cost_val = float(row.total_cost or 0)
        cost = cost_val if cost_val > 0 else None
        profit = (revenue - cost_val) if cost_val > 0 else None
        margin = ((revenue - cost_val) / revenue * 100) if revenue > 0 and cost_val > 0 else None

        departments.append({
            "id": idx + 1,
            "name": row.bgbu,
            "revenue": round(revenue, 2),
            "cost": round(cost_val, 2) if cost is not None else None,
            "gross_profit": round(profit, 2) if profit is not None else None,
            "margin": round(margin, 2) if margin is not None else None,
            "metric_count": int(row.total_orders or 0),
            "cost_unavailable": cost is None,
        })

    return APIResponse.success(data=departments)


@router.get("/{report_id}/products", response_model=APIResponse)
async def drilldown_products_all(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Product-level breakdown.

    Uses agg_dimension_summary WHERE dim_type='product_bgbu'.
    """
    period_prefix = None if report_id == "default" else report_id
    bgbu = _get_bgbu_filter(user)

    stmt = select(
        AggDimensionSummary.dim_value,
        func.sum(AggDimensionSummary.revenue).label("total_revenue"),
        func.sum(AggDimensionSummary.cost).label("total_cost"),
        func.sum(AggDimensionSummary.gross_profit).label("total_gp"),
        func.sum(AggDimensionSummary.order_count).label("total_orders"),
    ).where(
        AggDimensionSummary.bgbu == bgbu,
        AggDimensionSummary.dim_type == "product_bgbu",
    )

    if period_prefix:
        stmt = stmt.where(AggDimensionSummary.period.like(f"{period_prefix}%"))

    stmt = (
        stmt
        .group_by(AggDimensionSummary.dim_value)
        .order_by(func.sum(AggDimensionSummary.revenue).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    products = []
    for idx, row in enumerate(rows):
        revenue = float(row.total_revenue or 0)
        cost_val = float(row.total_cost or 0)
        cost = cost_val if cost_val > 0 else None
        profit = (revenue - cost_val) if cost_val > 0 else None
        # Return ratio (0~1) consistent with departments endpoint
        margin = ((revenue - cost_val) / revenue) if revenue > 0 and cost_val > 0 else None

        products.append({
            "id": idx + 1,
            "name": row.dim_value or "未知产品线",
            "category": "业务线",
            "revenue": round(revenue, 2),
            "cost": round(cost_val, 2) if cost is not None else None,
            "margin": round(margin, 4) if margin is not None else None,
            "sales_count": int(row.total_orders or 0),
            "cost_unavailable": cost is None,
        })

    return APIResponse.success(data=products)


@router.get("/{report_id}/departments/{dept_id}/products", response_model=APIResponse)
async def drilldown_products_by_dept(
    report_id: str,
    dept_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Product-level breakdown within a department.

    Uses agg_dimension_summary filtered by department (bgbu).
    For user-scaped access, dept_id must match the user's department index.
    """
    period_prefix = None if report_id == "default" else report_id

    # Resolve the department name by offset from the list of departments
    dept_stmt = (
        select(AggPeriodSummary.bgbu)
        .where(AggPeriodSummary.bgbu != "ALL")
        .distinct()
        .order_by(AggPeriodSummary.bgbu)
        .offset(dept_id - 1)
        .limit(1)
    )
    if period_prefix:
        dept_stmt = dept_stmt.where(AggPeriodSummary.period.like(f"{period_prefix}%"))

    dept_result = await db.execute(dept_stmt)
    dept_name = dept_result.scalar_one_or_none()

    if dept_name is None:
        raise ResourceNotFoundError(f"Department {dept_id} not found in report {report_id}")

    # Check user scope
    user_bgbu = _get_bgbu_filter(user)
    if user_bgbu != "ALL" and dept_name != user_bgbu:
        raise ResourceNotFoundError(f"Department {dept_id} not found in report {report_id}")

    # Get product breakdown from agg_dimension_summary
    stmt = select(
        AggDimensionSummary.dim_value,
        func.sum(AggDimensionSummary.revenue).label("total_revenue"),
        func.sum(AggDimensionSummary.cost).label("total_cost"),
        func.sum(AggDimensionSummary.gross_profit).label("total_gp"),
        func.sum(AggDimensionSummary.order_count).label("total_orders"),
    ).where(
        AggDimensionSummary.bgbu == dept_name,
        AggDimensionSummary.dim_type == "product_bgbu",
    )

    if period_prefix:
        stmt = stmt.where(AggDimensionSummary.period.like(f"{period_prefix}%"))

    stmt = (
        stmt
        .group_by(AggDimensionSummary.dim_value)
        .order_by(func.sum(AggDimensionSummary.revenue).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    products = []
    for idx, row in enumerate(rows):
        revenue = float(row.total_revenue or 0)
        cost_val = float(row.total_cost or 0)
        cost = cost_val if cost_val > 0 else None
        profit = (revenue - cost_val) if cost_val > 0 else None
        margin = ((revenue - cost_val) / revenue) if revenue > 0 and cost_val > 0 else None

        products.append({
            "id": idx + 1,
            "name": row.dim_value or "未知",
            "category": "产品线",
            "revenue": round(revenue, 2),
            "cost": round(cost_val, 2) if cost is not None else None,
            "margin": round(margin, 4) if margin is not None else None,
            "sales_count": int(row.total_orders or 0),
            "cost_unavailable": cost is None,
        })

    return APIResponse.success(data=products)


@router.get("/{report_id}/records", response_model=APIResponse)
async def drilldown_records_flat(
    report_id: str,
    level: int = Query(None, description="Drilldown level: 2=department, 3=product, 4=record"),
    department: str = Query(None, description="Department name filter"),
    product: str = Query(None, description="Product/metric name filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Flat records endpoint for frontend L2/L3/L4 compatibility.

    - L2 (level=2): returns department-level summary rows from agg_period_summary
    - L3 (level=3): returns product-level summary rows from agg_dimension_summary
    - L4 (level=4, with product filter): returns detailed order records from agg_order_summary
    """
    period_prefix = None if report_id == "default" else report_id
    user_bgbu = _get_bgbu_filter(user)

    if level == 2:
        # Department-level summary from agg_period_summary
        stmt = select(
            AggPeriodSummary.bgbu,
            func.sum(AggPeriodSummary.revenue).label("total_revenue"),
            func.sum(AggPeriodSummary.order_count).label("total_orders"),
        ).where(AggPeriodSummary.bgbu != "ALL")

        if period_prefix:
            stmt = stmt.where(AggPeriodSummary.period.like(f"{period_prefix}%"))

        if user_bgbu != "ALL":
            stmt = stmt.where(AggPeriodSummary.bgbu == user_bgbu)

        if department:
            stmt = stmt.where(AggPeriodSummary.bgbu == department)

        stmt = (
            stmt
            .group_by(AggPeriodSummary.bgbu)
            .order_by(func.sum(AggPeriodSummary.revenue).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(stmt)
        rows = result.all()

        items = [
            {
                "id": idx + 1,
                "level": 2,
                "title": row.bgbu or "未知部门",
                "fields": {
                    "revenue": round(float(row.total_revenue or 0), 2),
                    "record_count": int(row.total_orders or 0),
                },
                "children_count": int(row.total_orders or 0),
            }
            for idx, row in enumerate(rows)
        ]
        return APIResponse.success(data=items)

    if level == 4 and product:
        # Detailed order records from agg_order_summary
        stmt = select(
            AggOrderSummary.order_id,
            AggOrderSummary.period,
            AggOrderSummary.bgbu,
            AggOrderSummary.dim_dept,
            AggOrderSummary.dim_product,
            AggOrderSummary.revenue,
            AggOrderSummary.cost,
            AggOrderSummary.gross_profit,
        )

        if user_bgbu != "ALL":
            stmt = stmt.where(AggOrderSummary.bgbu == user_bgbu)

        if period_prefix:
            stmt = stmt.where(AggOrderSummary.period.like(f"{period_prefix}%"))

        if department:
            stmt = stmt.where(AggOrderSummary.bgbu == department)

        if product:
            stmt = stmt.where(AggOrderSummary.dim_product == product)

        count_stmt = select(func.count()).select_from(stmt.subquery())

        stmt = (
            stmt
            .order_by(AggOrderSummary.period.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(stmt)
        rows = result.all()

        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        items = [
            {
                "id": idx + 1,
                "level": 4,
                "title": f"{row.bgbu}/{row.dim_product or row.order_id}",
                "fields": {
                    "period": row.period,
                    "entity": row.bgbu,
                    "metric_name": row.dim_product or row.order_id,
                    "metric_value": float(row.revenue or 0),
                    "tags": {
                        "order_id": row.order_id,
                        "dim_dept": row.dim_dept,
                        "dim_product": row.dim_product,
                    },
                },
                "children_count": 0,
            }
            for idx, row in enumerate(rows)
        ]
        return APIResponse.success(
            data={
                "report_id": report_id,
                "records": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )

    # L3 product list: return product breakdown from agg_dimension_summary
    stmt = select(
        AggDimensionSummary.dim_value,
        func.sum(AggDimensionSummary.revenue).label("total_revenue"),
        func.sum(AggDimensionSummary.order_count).label("total_orders"),
    ).where(
        AggDimensionSummary.dim_type == "product_bgbu",
    )

    if period_prefix:
        stmt = stmt.where(AggDimensionSummary.period.like(f"{period_prefix}%"))

    if user_bgbu != "ALL":
        stmt = stmt.where(AggDimensionSummary.bgbu == user_bgbu)

    if department:
        stmt = stmt.where(AggDimensionSummary.bgbu == department)

    stmt = (
        stmt
        .group_by(AggDimensionSummary.dim_value)
        .order_by(func.sum(AggDimensionSummary.revenue).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(stmt)
    rows = result.all()

    items = [
        {
            "id": idx + 1,
            "level": 3,
            "title": row.dim_value or "未知产品线",
            "fields": {"revenue": round(float(row.total_revenue or 0), 2)},
            "children_count": int(row.total_orders or 0),
        }
        for idx, row in enumerate(rows)
    ]
    return APIResponse.success(data=items)


@router.get("/{report_id}/departments/{dept_id}/products/{product_id}/records", response_model=APIResponse)
async def drilldown_records(
    report_id: str,
    dept_id: int,
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Transaction-level records for a specific product in a department.

    Uses agg_order_summary filtered by dim_dept and dim_product.
    """
    period_prefix = None if report_id == "default" else report_id

    # Resolve department name by offset
    dept_name_stmt = (
        select(AggPeriodSummary.bgbu)
        .where(AggPeriodSummary.bgbu != "ALL")
        .distinct()
        .order_by(AggPeriodSummary.bgbu)
        .offset(dept_id - 1)
        .limit(1)
    )
    if period_prefix:
        dept_name_stmt = dept_name_stmt.where(AggPeriodSummary.period.like(f"{period_prefix}%"))

    dept_result = await db.execute(dept_name_stmt)
    dept_name = dept_result.scalar_one_or_none()

    if dept_name is None:
        raise ResourceNotFoundError(f"Department {dept_id} not found in report {report_id}")

    # Check user scope
    user_bgbu = _get_bgbu_filter(user)
    if user_bgbu != "ALL" and dept_name != user_bgbu:
        raise ResourceNotFoundError(f"Department {dept_id} not found in report {report_id}")

    # Resolve product name by offset from agg_dimension_summary
    cust_stmt = (
        select(AggDimensionSummary.dim_value)
        .where(
            AggDimensionSummary.bgbu == dept_name,
            AggDimensionSummary.dim_type == "product_bgbu",
        )
        .group_by(AggDimensionSummary.dim_value)
        .order_by(func.sum(AggDimensionSummary.revenue).desc())
        .offset(product_id - 1)
        .limit(1)
    )
    if period_prefix:
        cust_stmt = cust_stmt.where(AggDimensionSummary.period.like(f"{period_prefix}%"))

    cust_result = await db.execute(cust_stmt)
    product_name = cust_result.scalar_one_or_none()

    if product_name is None:
        raise ResourceNotFoundError(f"Product {product_id} not found in department {dept_id}")

    # Fetch order-level records from agg_order_summary
    record_stmt = select(AggOrderSummary).where(
        AggOrderSummary.bgbu == dept_name,
    )

    if period_prefix:
        record_stmt = record_stmt.where(AggOrderSummary.period.like(f"{period_prefix}%"))

    if user_bgbu != "ALL":
        record_stmt = record_stmt.where(AggOrderSummary.bgbu == user_bgbu)

    # Count
    count_where = [AggOrderSummary.bgbu == dept_name]
    if period_prefix:
        count_where.append(AggOrderSummary.period.like(f"{period_prefix}%"))
    count_stmt = select(func.count()).select_from(AggOrderSummary).where(*count_where)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Records with pagination
    rec_where = [AggOrderSummary.bgbu == dept_name]
    if period_prefix:
        rec_where.append(AggOrderSummary.period.like(f"{period_prefix}%"))

    record_stmt = (
        select(AggOrderSummary)
        .where(*rec_where)
        .order_by(AggOrderSummary.period.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    records_result = await db.execute(record_stmt)
    rows = records_result.scalars().all()

    records = []
    for r in rows:
        records.append({
            "id": r.order_id,
            "title": f"ORD-{r.order_id}",
            "children_count": 0,
            "fields": {
                "record_id": r.order_id,
                "period": r.period,
                "entity": r.bgbu,
                "metric_name": r.dim_product or r.order_id,
                "metric_value": float(r.revenue or 0),
                "transaction_no": r.order_id,
                "date": r.period,
                "customer": r.dim_dept,
                "contract_no": None,
                "region": None,
                "status": None,
                "payment_terms": None,
                "invoice_status": None,
            },
        })

    return APIResponse.success(
        data={
            "report_id": report_id,
            "department": dept_name,
            "product": product_name,
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/records/{record_id}", response_model=APIResponse)
async def drilldown_single_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Get a single financial data record by ID.

    Kept as-is: PK lookup on financial_data is fast.
    """
    row = await db.get(FinancialData, record_id)
    if row is None:
        raise ResourceNotFoundError(f"Record {record_id} not found")

    # Check department scope for non-admin
    if user and user.role != "admin" and user.department and row.entity != user.department:
        raise ResourceNotFoundError(f"Record {record_id} not found")

    return APIResponse.success(
        data={
            "record_id": row.id,
            "batch_id": row.batch_id,
            "metric_name": row.metric_name,
            "metric_value": row.metric_value,
            "metric_unit": row.metric_unit,
            "period": row.period,
            "entity": row.entity,
            "tags": row.tags,
            "raw_row": row.raw_row,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
    )
