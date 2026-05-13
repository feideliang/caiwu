"""Drilldown endpoints: hierarchical financial data exploration.

Replaces old GET /api/v1/drill-down with RESTful paths:
- GET /drilldowns/{report_id}/summary
- GET /drilldowns/{report_id}/departments
- GET /drilldowns/{report_id}/departments/{dept_id}/products
- GET /drilldowns/{report_id}/departments/{dept_id}/products/{product_id}/records
- GET /drilldowns/records/{record_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import decode_access_token, TokenPayload, get_current_user
from app.db.session import get_db
from app.models.core import FinancialData

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


# Keywords for cost metric identification (matches dashboard.py)
_COST_KW = ("cost", "成本", "expense")
_REVENUE_KW = ("revenue", "营业收入", "sales")


def _cost_sum(period_data: dict, period: str | None) -> float | None:
    """Aggregate cost metrics for a period. Returns None if no cost data found."""
    if not period:
        return None
    data = period_data.get(period, {})
    for mname, val in data.items():
        for kw in _COST_KW:
            if kw.lower() in mname.lower():
                return float(val)
    return None


@router.get("/{report_id}/summary", response_model=APIResponse)
async def drilldown_summary(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Company-level summary: total revenue, cost, profit, margin, department count.

    The report_id maps to a period or batch context. Aggregated from financial_data.
    """
    # Use report_id as a period filter prefix (e.g., report_id=2024 -> "2024-%")
    # 'default' maps to all data (no period filter)
    period_prefix = None if report_id == "default" else report_id

    # Fetch period-grouped metrics in one query (avoids N+1 for revenue/cost by period)
    if period_prefix:
        stmt = (
            select(
                FinancialData.period,
                FinancialData.metric_name,
                func.sum(FinancialData.metric_value).label("total"),
            )
            .where(FinancialData.period.like(f"{period_prefix}%"))
            .group_by(FinancialData.period, FinancialData.metric_name)
        )
    else:
        stmt = (
            select(
                FinancialData.period,
                FinancialData.metric_name,
                func.sum(FinancialData.metric_value).label("total"),
            ).group_by(FinancialData.period, FinancialData.metric_name)
        )

    result = await db.execute(stmt)
    rows = result.all()

    # Build period-indexed lookup and aggregate totals
    period_data: dict[str, dict[str, float]] = {}
    all_metrics: dict[str, float] = {}
    for period, metric_name, total in rows:
        period_data.setdefault(period, {})[metric_name] = float(total)
        all_metrics[metric_name] = all_metrics.get(metric_name, 0.0) + float(total)

    def _sum_by_kw(metrics: dict[str, float], *keywords: str) -> float:
        for mname, val in metrics.items():
            for kw in keywords:
                if kw.lower() in mname.lower():
                    return val
        return 0.0

    total_revenue = _sum_by_kw(all_metrics, *_REVENUE_KW)
    total_cost_val = _sum_by_kw(all_metrics, *_COST_KW)
    dept_count = len(period_data)

    if total_cost_val == 0.0:
        total_cost_val = None  # signal: no real cost data

    total_cost = total_cost_val if total_cost_val is not None else 0.0
    total_profit = total_revenue - total_cost if total_cost_val is not None else None
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 and total_profit is not None else None

    return APIResponse.success(
        data={
            "report_id": report_id,
            "title": f"财务总览 - {report_id}",
            "level": 1,
            "breadcrumbs": [],
            "metrics": {
                "total_revenue": round(total_revenue, 2),
                "total_cost": round(total_cost, 2) if total_cost_val is not None else None,
                "total_profit": round(total_profit, 2) if total_profit is not None else None,
                "avg_margin": round(profit_margin, 2) if profit_margin is not None else None,
                "total_orders": dept_count,
                "cost_unavailable": total_cost_val is None,
            },
            "has_children": dept_count > 0,
        }
    )


@router.get("/{report_id}/departments", response_model=APIResponse)
async def drilldown_departments(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Department-level breakdown within a report period."""
    period_prefix = None if report_id == "default" else report_id

    if period_prefix:
        stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_value"),
            )
            .where(
                FinancialData.period.like(f"{period_prefix}%"),
                FinancialData.entity.isnot(None),
            )
            .group_by(FinancialData.entity)
            .order_by(func.sum(FinancialData.metric_value).desc())
        )
    else:
        stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_value"),
            )
            .where(FinancialData.entity.isnot(None))
            .group_by(FinancialData.entity)
            .order_by(func.sum(FinancialData.metric_value).desc())
        )

    result = await db.execute(stmt)
    rows = result.all()

    # Fetch real revenue and cost data per entity separately
    if period_prefix:
        cost_stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_cost"),
            )
            .where(
                FinancialData.period.like(f"{period_prefix}%"),
                FinancialData.entity.isnot(None),
                FinancialData.metric_name.in_(_COST_KW),
            )
            .group_by(FinancialData.entity)
        )
    else:
        cost_stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_cost"),
            )
            .where(FinancialData.entity.isnot(None))
            .group_by(FinancialData.entity)
        )
    cost_result = await db.execute(cost_stmt)
    cost_by_entity = {row[0]: float(row[1]) for row in cost_result.all()}

    # Fetch metric count per entity
    count_stmt = (
        select(
            FinancialData.entity,
            func.count().label("metric_count"),
        )
        .where(FinancialData.entity.isnot(None))
    )
    if period_prefix:
        count_stmt = count_stmt.where(FinancialData.period.like(f"{period_prefix}%"))
    count_stmt = count_stmt.group_by(FinancialData.entity)
    count_result = await db.execute(count_stmt)
    count_by_entity = {row[0]: row[1] for row in count_result.all()}

    departments = []
    for idx, row in enumerate(rows):
        revenue = row[1] or 0.0
        entity_name = row[0]
        real_cost = cost_by_entity.get(entity_name, 0.0)
        cost = real_cost if real_cost > 0 else None
        profit = (revenue - real_cost) if real_cost > 0 else None
        margin = ((revenue - real_cost) / revenue * 100) if revenue > 0 and real_cost > 0 else None

        departments.append({
            "id": idx + 1,
            "name": entity_name,
            "revenue": round(revenue, 2),
            "cost": round(real_cost, 2) if cost is not None else None,
            "gross_profit": round(profit, 2) if profit is not None else None,
            "margin": round(margin, 2) if margin is not None else None,
            "metric_count": count_by_entity.get(entity_name, 0),
            "cost_unavailable": cost is None,
        })

    return APIResponse.success(data=departments)


@router.get("/{report_id}/products", response_model=APIResponse)
async def drilldown_products_all(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Product-level breakdown: uses entity as product dimension (DB has no separate product column)."""
    period_prefix = None if report_id == "default" else report_id

    # Revenue per entity
    if period_prefix:
        rev_stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_revenue"),
            )
            .where(
                FinancialData.period.like(f"{period_prefix}%"),
                FinancialData.entity.isnot(None),
                FinancialData.metric_name.in_(_REVENUE_KW),
            )
            .group_by(FinancialData.entity)
            .order_by(func.sum(FinancialData.metric_value).desc())
        )
    else:
        rev_stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_revenue"),
            )
            .where(FinancialData.entity.isnot(None))
            .group_by(FinancialData.entity)
            .order_by(func.sum(FinancialData.metric_value).desc())
        )

    rev_result = await db.execute(rev_stmt)
    revenue_by_entity = {row[0]: float(row[1]) for row in rev_result.all()}

    # Cost per entity
    if period_prefix:
        cost_stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_cost"),
            )
            .where(
                FinancialData.period.like(f"{period_prefix}%"),
                FinancialData.entity.isnot(None),
                FinancialData.metric_name.in_(_COST_KW),
            )
            .group_by(FinancialData.entity)
        )
    else:
        cost_stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_cost"),
            )
            .where(FinancialData.entity.isnot(None))
            .group_by(FinancialData.entity)
        )
    cost_result = await db.execute(cost_stmt)
    cost_by_entity = {row[0]: float(row[1]) for row in cost_result.all()}

    products = []
    for idx, entity_name in enumerate(sorted(revenue_by_entity.keys())):
        revenue = revenue_by_entity[entity_name]
        real_cost = cost_by_entity.get(entity_name, 0.0)
        cost = real_cost if real_cost > 0 else None
        profit = (revenue - real_cost) if real_cost > 0 else None
        # Return ratio (0~1) consistent with departments endpoint
        margin = ((revenue - real_cost) / revenue) if revenue > 0 and real_cost > 0 else None

        products.append({
            "id": idx + 1,
            "name": entity_name,
            "category": "业务线",
            "revenue": round(revenue, 2),
            "cost": round(real_cost, 2) if cost is not None else None,
            "margin": round(margin, 4) if margin is not None else None,
            "sales_count": 0,
            "cost_unavailable": cost is None,
        })

    return APIResponse.success(data=products)


@router.get("/{report_id}/departments/{dept_id}/products", response_model=APIResponse)
async def drilldown_products_by_dept(
    report_id: str,
    dept_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Product-level breakdown within a department.

    Uses customer names from transaction_record tags as the product dimension,
    since the DB has no separate product column.
    """
    period_prefix = None if report_id == "default" else report_id

    # Get the department name by offset with stable ordering
    dept_name_stmt = (
        select(FinancialData.entity)
        .where(FinancialData.entity.isnot(None))
        .distinct()
        .order_by(FinancialData.entity)
        .offset(dept_id - 1)
        .limit(1)
    )
    if period_prefix:
        dept_name_stmt = dept_name_stmt.where(FinancialData.period.like(f"{period_prefix}%"))

    dept_result = await db.execute(dept_name_stmt)
    dept_name = dept_result.scalar_one_or_none()

    if dept_name is None:
        raise ResourceNotFoundError(f"Department {dept_id} not found in report {report_id}")

    # Aggregate revenue and cost by customer from transaction_record tags
    from sqlalchemy import text

    conditions = ["entity = :dept", "metric_name = 'transaction_record'"]
    params: dict = {"dept": dept_name}
    if period_prefix:
        conditions.append("period LIKE :period")
        params["period"] = f"{period_prefix}%"

    # Revenue by customer
    rev_sql = f"""
        SELECT tags->>'customer' AS customer,
               SUM(metric_value) AS total_revenue
        FROM financial_data
        WHERE {' AND '.join(conditions)}
        GROUP BY tags->>'customer'
        ORDER BY total_revenue DESC
    """
    rev_result = await db.execute(text(rev_sql), params)
    rev_rows = rev_result.all()

    # Cost by customer (proportional allocation since transaction_record is the only metric with customer tags)
    cost_sql = f"""
        SELECT tags->>'customer' AS customer,
               SUM(metric_value) AS total_cost
        FROM financial_data
        WHERE {' AND '.join(conditions)}
        GROUP BY tags->>'customer'
    """
    cost_result = await db.execute(text(cost_sql), params)
    cost_rows = cost_result.all()

    # For transaction records, revenue == cost (same metric_value).
    # We need to derive cost from the department's overall cost ratio.
    # Get department total revenue and cost
    dept_totals_sql = f"""
        SELECT
            SUM(CASE WHEN metric_name IN ('revenue', '营业收入', 'sales') THEN metric_value ELSE 0 END) AS total_rev,
            SUM(CASE WHEN metric_name IN ('cost', '成本', 'expense') THEN metric_value ELSE 0 END) AS total_cost
        FROM financial_data
        WHERE entity = :dept
        {'AND period LIKE :period' if period_prefix else ''}
    """
    dept_result2 = await db.execute(text(dept_totals_sql), params)
    dept_row = dept_result2.first()
    dept_total_rev = dept_row[0] if dept_row and dept_row[0] else 0
    dept_total_cost = dept_row[1] if dept_row and dept_row[1] else 0
    cost_ratio = dept_total_cost / dept_total_rev if dept_total_rev > 0 else 0

    products = []
    for idx, row in enumerate(rev_rows):
        customer = row[0] or "未知"
        revenue = float(row[1]) if row[1] else 0.0
        # Allocate cost proportionally
        allocated_cost = round(revenue * cost_ratio, 2) if cost_ratio > 0 else None
        cost = allocated_cost if allocated_cost and allocated_cost > 0 else None
        profit = (revenue - allocated_cost) if allocated_cost else None
        margin = (profit / revenue) if revenue > 0 and profit is not None else None

        products.append({
            "id": idx + 1,
            "name": customer,
            "category": "客户",
            "revenue": round(revenue, 2),
            "cost": cost,
            "margin": round(margin, 4) if margin is not None else None,
            "sales_count": 1,
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
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Flat records endpoint for frontend L2/L3/L4 compatibility.

    - L2 (level=2): returns department-level summary rows
    - L3 (level=3, no product filter): returns product-level summary rows
    - L4 (level=4, with product filter): returns detailed transaction records
    """
    period_prefix = None if report_id == "default" else report_id

    conditions = []
    if period_prefix:
        conditions.append(FinancialData.period.like(f"{period_prefix}%"))

    if level == 2:
        if department:
            conditions.append(FinancialData.entity == department)
        stmt = (
            select(
                FinancialData.entity,
                func.sum(FinancialData.metric_value).label("total_value"),
                func.count(FinancialData.id).label("record_count"),
            )
            .where(*conditions)
            .group_by(FinancialData.entity)
            .order_by(func.sum(FinancialData.metric_value).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        rows = result.all()
        items = [
            {
                "id": idx + 1,
                "level": 2,
                "title": row[0] or "未知部门",
                "fields": {"revenue": round(row[1] or 0, 2), "record_count": row[2] or 0},
                "children_count": row[2] or 0,
            }
            for idx, row in enumerate(rows)
        ]
        return APIResponse.success(data=items)

    if product:
        conditions.append(FinancialData.metric_name == product)
        stmt = (
            select(FinancialData)
            .where(*conditions)
            .order_by(FinancialData.period.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        items = [
            {
                "id": r.id,
                "level": 4,
                "title": f"{r.entity}/{r.metric_name}",
                "fields": {
                    "period": r.period,
                    "entity": r.entity,
                    "metric_name": r.metric_name,
                    "metric_value": r.metric_value,
                    "tags": r.tags,
                },
                "children_count": 0,
            }
            for r in rows
        ]
        count_stmt = select(func.count()).select_from(FinancialData).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()
        return APIResponse.success(
            data={
                "report_id": report_id,
                "records": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )

    # L3 product list: return customer breakdown from transaction_record tags
    from sqlalchemy import text

    tx_where = ["metric_name = 'transaction_record'"]
    tx_params: dict = {"page": page, "page_size": page_size}
    if period_prefix:
        tx_where.append("period LIKE :period")
        tx_params["period"] = f"{period_prefix}%"
    if department:
        tx_where.append("entity = :dept")
        tx_params["dept"] = department

    cust_sql = f"""
        SELECT tags->>'customer' AS customer, SUM(metric_value) AS total
        FROM financial_data
        WHERE {' AND '.join(tx_where)}
        GROUP BY tags->>'customer'
        ORDER BY total DESC
        LIMIT :page_size OFFSET :offset
    """
    tx_params["offset"] = (page - 1) * page_size
    cust_result = await db.execute(text(cust_sql), tx_params)
    cust_rows = cust_result.all()

    items = [
        {
            "id": idx + 1,
            "level": 3,
            "title": row[0] or "未知客户",
            "fields": {"revenue": round(float(row[1]), 2) if row[1] else 0},
            "children_count": 0,
        }
        for idx, row in enumerate(cust_rows)
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
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Transaction-level records for a specific product (customer) in a department."""
    period_prefix = None if report_id == "default" else report_id

    # Resolve department name with stable ordering
    dept_name_stmt = (
        select(FinancialData.entity)
        .where(FinancialData.entity.isnot(None))
        .distinct()
        .order_by(FinancialData.entity)
        .offset(dept_id - 1)
        .limit(1)
    )
    if period_prefix:
        dept_name_stmt = dept_name_stmt.where(FinancialData.period.like(f"{period_prefix}%"))
    dept_result = await db.execute(dept_name_stmt)
    dept_name = dept_result.scalar_one_or_none()

    if dept_name is None:
        raise ResourceNotFoundError(f"Department {dept_id} not found in report {report_id}")

    # Resolve product (customer) name: list customers ordered by revenue, pick by product_id offset
    from sqlalchemy import text

    cust_params: dict = {"dept": dept_name}
    cust_where = ["entity = :dept", "metric_name = 'transaction_record'"]
    if period_prefix:
        cust_where.append("period LIKE :period")
        cust_params["period"] = f"{period_prefix}%"

    cust_sql = f"""
        SELECT tags->>'customer' AS customer, SUM(metric_value) AS total
        FROM financial_data
        WHERE {' AND '.join(cust_where)}
        GROUP BY tags->>'customer'
        ORDER BY total DESC
        OFFSET :offset LIMIT 1
    """
    cust_params["offset"] = product_id - 1
    cust_result = await db.execute(text(cust_sql), cust_params)
    cust_row = cust_result.first()
    if cust_row is None:
        raise ResourceNotFoundError(f"Product {product_id} not found in department {dept_id}")

    customer_name = cust_row[0] or "未知"

    # Fetch transaction records for this department (tags contain customer info)
    record_where = ["entity = :dept", "metric_name = 'transaction_record'"]
    record_params: dict = {"dept": dept_name, "page": page, "page_size": page_size}
    if period_prefix:
        record_where.append("period LIKE :period")
        record_params["period"] = f"{period_prefix}%"

    # Count
    count_sql = f"""
        SELECT count(*) FROM financial_data
        WHERE {' AND '.join(record_where)}
    """
    count_result = await db.execute(text(count_sql), record_params)
    total = count_result.scalar_one()

    # Records
    records_sql = f"""
        SELECT id, period, entity, metric_name, metric_value, tags, created_at
        FROM financial_data
        WHERE {' AND '.join(record_where)}
        ORDER BY created_at DESC
        LIMIT :page_size OFFSET :offset
    """
    record_params["page_size"] = page_size
    record_params["offset"] = (page - 1) * page_size
    records_result = await db.execute(text(records_sql), record_params)

    records = []
    for r in records_result.all():
        tags = r[5] or {}
        records.append({
            "id": r[0],
            "title": f"{tags.get('transaction_no', f'TXN-{r[0]}')}",
            "children_count": 0,
            "fields": {
                "record_id": r[0],
                "period": r[1],
                "entity": r[2],
                "metric_name": r[3],
                "metric_value": r[4],
                "transaction_no": tags.get("transaction_no"),
                "date": tags.get("date"),
                "customer": tags.get("customer"),
                "contract_no": tags.get("contract_no"),
                "region": tags.get("region"),
                "status": tags.get("status"),
                "payment_terms": tags.get("payment_terms"),
                "invoice_status": tags.get("invoice_status"),
            },
        })

    return APIResponse.success(
        data={
            "report_id": report_id,
            "department": dept_name,
            "product": customer_name,
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
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Get a single financial data record by ID."""
    row = await db.get(FinancialData, record_id)
    if row is None:
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
