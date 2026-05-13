# V4.0 Backend Development Plan — Detailed Implementation Guidance

**编制日期:** 2026-05-08
**编制人:** Backend Lead Engineer
**来源文档:** V4.0 Master Plan (`playful-reddy.md`), PM Remediation (`pm-remediation-tasklist-v3-1.md`), Existing Backend Plan

---

## Global Conventions (Apply to ALL tasks)

### Response Format (BE-016)
Every API endpoint MUST return this envelope:

```python
# app/schemas/common.py
from pydantic import BaseModel
from typing import Any, Generic, TypeVar

T = TypeVar("T")

class APIResponse(BaseModel):
    code: int = 0          # 0=success, non-zero=error code
    message: str = "success"
    data: Any = None
    trace_id: str = ""     # request tracing ID (uuid4 hex)

# Usage in routers:
# return APIResponse(code=0, data=result)
# return APIResponse(code=4001, message="Validation error", data=errors)
```

### Error Code Registry (BE-016)

```python
# app/core/error_codes.py
class ErrorCode:
    # Auth (4xxx)
    UNAUTHORIZED = 4001        # 未登录或token无效
    FORBIDDEN = 4003           # 无权限
    TOKEN_EXPIRED = 4004       # token过期
    INVALID_CREDENTIALS = 4005 # 用户名或密码错误

    # Validation (41xx)
    VALIDATION_ERROR = 4100
    MISSING_PARAM = 4101
    INVALID_PARAM = 4102
    DSL_PARSE_ERROR = 4103

    # Resource (42xx)
    NOT_FOUND = 4200
    ALREADY_EXISTS = 4201
    CONFLICT = 4202

    # Business (43xx)
    PREDICTION_REJECTED = 4300   # 预测被拒绝（数据不足/精度不够）
    REPORT_STATE_ERROR = 4301    # 报告状态不允许操作
    CACHE_MISS = 4302

    # Server (5xxx)
    INTERNAL_ERROR = 5000
    AI_SERVICE_ERROR = 5001
    DATABASE_ERROR = 5002
    CELERY_ERROR = 5003
    FILE_TOO_LARGE = 5004       # 413 equivalent

    @classmethod
    def message(cls, code: int) -> str:
        return {
            cls.UNAUTHORIZED: "Unauthorized",
            cls.FORBIDDEN: "Forbidden",
            cls.TOKEN_EXPIRED: "Token expired",
            # ... etc
        }.get(code, "Unknown error")
```

### Global Exception Handler (BE-016)

```python
# app/core/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse

class AppException(Exception):
    def __init__(self, code: int, message: str = None, data: Any = None):
        self.code = code
        self.message = message or ErrorCode.message(code)
        self.data = data

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=400 if exc.code < 5000 else 500,
        content=APIResponse(
            code=exc.code, message=exc.message, data=exc.data
        ).model_dump(),
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # NEVER leak stack traces in production
    return JSONResponse(
        status_code=500,
        content=APIResponse(
            code=5000, message="Internal server error"
        ).model_dump(),
    )
```

### Logging & Tracing

```python
# app/core/logging.py
import logging
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

class TraceIDFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True

def get_trace_id() -> str:
    return trace_id_var.get()

def set_trace_id(tid: str = None):
    trace_id_var.set(tid or uuid.uuid4().hex)
```

### Dependency Injection Patterns

```python
# app/api/deps.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.auth import decode_token, get_current_user

async def get_current_user_id(
    authorization: str = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalid")
    return payload["user_id"]

# Role-based guard
def require_role(roles: list[str]):
    async def role_checker(
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
    ):
        user = await get_current_user(db, user_id)
        if user.role.name not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return role_checker

# Usage: require_role(["admin", "analyst"]) for write ops
# Usage: require_role(["admin", "analyst", "viewer"]) for read ops
```

### Project Directory Structure

```
ai_bi_finance/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry
│   ├── config.py                   # Env var loading (BE-014)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py             # SQLAlchemy async engine + session
│   │   ├── cache.py                # Redis client (BE-008)
│   │   ├── celery_app.py           # Celery app config (BE-002)
│   │   ├── logging.py              # Logging + trace ID
│   │   ├── error_codes.py          # Error code registry (BE-016)
│   │   └── exceptions.py           # Global exception handlers (BE-016)
│   ├── models/                     # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py                 # Declarative base + mixins
│   │   ├── revenue_detail.py       # Existing (original 9 tables)
│   │   ├── metric_summary.py
│   │   ├── data_error_log.py
│   │   ├── sync_batch.py
│   │   ├── ai_analysis.py
│   │   ├── alert.py
│   │   ├── insight.py              # BE-009: new
│   │   ├── filter_view.py          # BE-009: new
│   │   ├── correlation.py          # BE-009 + BE-007: new
│   │   ├── prediction.py           # BE-009 + BE-003: new
│   │   ├── report_task.py          # BE-009 + BE-002: new
│   │   ├── audit_log.py            # BE-009 + BE-011: new
│   │   ├── user.py                 # BE-009 + BE-010: new
│   │   ├── role.py                 # BE-009 + BE-010: new
│   │   └── notification.py         # BE-009 + BE-012: new
│   ├── schemas/                    # Pydantic models
│   │   ├── __init__.py
│   │   ├── common.py               # APIResponse, Pagination
│   │   ├── auth.py                 # BE-001 (16, 17)
│   │   ├── insight.py              # BE-001 (3, 4)
│   │   ├── filter.py               # BE-001 (5, 7)
│   │   ├── query.py                # BE-001 (6)
│   │   ├── correlation.py          # BE-007
│   │   ├── drilldown.py            # BE-006
│   │   ├── report.py               # BE-002
│   │   ├── prediction.py           # BE-003
│   │   ├── transaction.py          # BE-004
│   │   ├── notification.py         # BE-012
│   │   ├── system.py               # BE-013
│   │   ├── datasource.py           # BE-015
│   │   ├── dashboard.py            # BE-008
│   │   └── ai_recommend.py         # BE-001 (1, 2)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # DI (DB session, auth, role)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py           # Aggregate all routers
│   │       ├── auth.py             # BE-001 (16, 17)
│   │       ├── ai_recommend.py     # BE-001 (1, 2)
│   │       ├── insights.py         # BE-001 (3, 4)
│   │       ├── filter.py           # BE-001 (5, 7)
│   │       ├── query.py            # BE-001 (6) + BE-008
│   │       ├── correlations.py     # BE-007
│   │       ├── drilldowns.py       # BE-006
│   │       ├── dashboard.py        # BE-008 (BFF layer)
│   │       ├── reports.py          # BE-002
│   │       ├── predictions.py      # BE-003
│   │       ├── transactions.py     # BE-004
│   │       ├── notifications.py    # BE-012
│   │       ├── system.py           # BE-013
│   │       ├── datasources.py      # BE-015
│   │       └── uploads.py          # BE-015
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email_reader.py         # Existing: IMAP
│   │   ├── excel_parser.py         # Existing: Excel parsing
│   │   ├── data_cleaner.py         # Existing: data cleaning
│   │   ├── sync_strategy.py        # Existing: sync logic
│   │   ├── metrics_engine.py       # Existing: KPI calculation
│   │   ├── precompute.py           # Existing: precompute tasks
│   │   ├── auth_service.py         # BE-010: JWT + RBAC
│   │   ├── insight_service.py      # BE-001: insights logic
│   │   ├── filter_service.py       # BE-001: filter views CRUD
│   │   ├── query_service.py        # BE-008: DSL query engine
│   │   ├── correlation_service.py  # BE-007: correlation engine
│   │   ├── drilldown_service.py    # BE-006: drilldown logic
│   │   ├── ai_service.py           # Existing + BE-001: LangChain + Qwen
│   │   ├── recommendation_service.py # BE-001: chart/layout recommendation
│   │   ├── report_service.py       # BE-002: report orchestration
│   │   ├── prediction_service.py   # BE-003 + BE-007: prediction engine
│   │   ├── notification_service.py # BE-012: notification CRUD
│   │   ├── audit_service.py        # BE-011: audit log writer
│   │   ├── freshness_service.py    # BE-013: data freshness
│   │   └── transaction_service.py  # BE-004: transaction analysis
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── report_tasks.py         # BE-002: Celery report generation
│   │   ├── prediction_tasks.py     # BE-003: Celery prediction
│   │   └── data_sync_tasks.py      # Existing: Celery sync tasks
│   └── repositories/               # Data access layer (BE-008 shared DAO)
│       ├── __init__.py
│       ├── base.py                 # BaseRepository with CRUD
│       ├── dashboard_repo.py       # Dashboard aggregation queries
│       ├── drilldown_repo.py       # Drilldown queries
│       └── query_repo.py           # Unified query DSL engine
├── migrations/                     # Alembic
│   ├── env.py
│   └── versions/
│       ├── 001_initial.py          # Original 9 tables
│       ├── 002_v3_new_tables.py    # 6 V3.0 tables (BE-009)
│       └── 003_v4_new_tables.py    # 4 V4.0 tables (BE-009)
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   │   ├── test_api_auth.py
│   │   ├── test_api_insights.py
│   │   ├── test_api_filter.py
│   │   ├── test_api_query.py
│   │   ├── test_api_correlations.py
│   │   ├── test_api_drilldowns.py
│   │   ├── test_api_dashboard.py
│   │   ├── test_api_reports.py
│   │   ├── test_api_predictions.py
│   │   ├── test_api_notifications.py
│   │   ├── test_api_system.py
│   │   ├── test_api_transactions.py
│   │   └── test_api_ai_recommend.py
│   └── performance/
├── scripts/
│   ├── cleanup_deprecated.py       # BE-005 script
│   └── seed_data.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## BE-001: P0 17 API Endpoints Implementation

### Priority: P0 | Depends on: AR-001

### API Contracts

#### 1. POST /api/v1/ai/recommend-chart — Chart Type Recommendation

```python
# app/schemas/ai_recommend.py
class ChartRecommendRequest(BaseModel):
    data_fields: list[str]       # e.g., ["revenue_amount", "company"]
    data_types: list[str]        # e.g., ["numeric", "categorical"]
    time_field: str | None = None
    device: str = "web"          # web / tablet / mobile

class ChartRecommendItem(BaseModel):
    chart_type: str              # bar / line / pie / scatter / table / heatmap
    score: float                 # 0.0 ~ 1.0
    reason: str                  # why this type fits
    fields_mapping: dict         # {x: "period", y: "revenue_amount"}

class ChartRecommendResponse(BaseModel):
    recommendations: list[ChartRecommendItem]

# Router: app/api/v1/ai_recommend.py
router = APIRouter(prefix="/api/v1/ai", tags=["AI Recommendation"])

@router.post("/recommend-chart")
async def recommend_chart(
    req: ChartRecommendRequest,
    user: User = Depends(require_role(["admin", "analyst", "viewer"])),
):
    # Rule-based pre-filter then AI re-ranking
    recommended = await recommendation_service.recommend_chart(req)
    return APIResponse(data=recommended)
```

#### 2. POST /api/v1/ai/recommend-layout — Layout Recommendation

```python
class LayoutRecommendRequest(BaseModel):
    charts: list[ChartRecommendItem]   # from recommend-chart
    device: str = "web"                # web / tablet / mobile

class LayoutRecommendResponse(BaseModel):
    layout: dict                       # grid layout config
    # {rows: [...], columns: 12, breakpoints: {lg, md, sm}}
```

#### 3. GET /api/v1/insights — Insight List

```python
# app/schemas/insight.py
class InsightOut(BaseModel):
    id: int
    type: str                    # anomaly / trend / benchmark / alert
    title: str
    content: str
    severity: str                # high / medium / low
    status: str                  # unread / read / processed / ignored
    related_metrics: dict | None
    created_at: datetime

class InsightListParams(BaseModel):
    type: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20

# GET /api/v1/insights?type=anomaly&status=unread&page=1&page_size=20
```

#### 4. POST /api/v1/insights/{id}/status — Insight Status Update

```python
class InsightStatusRequest(BaseModel):
    status: str  # read / processed / ignored

# POST /api/v1/insights/42/status {"status": "processed"}
```

#### 5. GET /api/v1/filter-options — Dynamic Filter Metadata

```python
# app/schemas/filter.py
class FilterOptionResponse(BaseModel):
    dimensions: list[FilterDimension]
    metrics: list[FilterMetric]
    time_range: TimeRange

class FilterDimension(BaseModel):
    field: str
    label: str
    type: str                    # categorical / date / numeric
    values: list[str | int] | None  # for categorical
    cascade: str | None = None   # parent field name for cascading

# GET /api/v1/filter-options
# Response:
# {
#   "dimensions": [
#     {"field": "company", "label": "公司", "type": "categorical", "values": ["锐捷网络", "其他"], "cascade": null},
#     {"field": "product_division", "label": "事业部", "type": "categorical", "values": [...], "cascade": "company"}
#   ],
#   "metrics": [...],
#   "time_range": {"min": "2024-01", "max": "2026-12"}
# }
```

#### 6. POST /api/v1/query — Unified Query DSL

```python
# app/schemas/query.py
class QueryRequest(BaseModel):
    dimensions: list[str]           # GROUP BY fields
    metrics: list[MetricExpr]       # aggregation expressions
    filters: list[FilterExpr] | None = None  # WHERE conditions
    order_by: list[OrderExpr] | None = None
    limit: int = 100
    offset: int = 0
    bypass_cache: bool = False      # force direct DB query

class MetricExpr(BaseModel):
    field: str
    agg: str = "sum"                # sum / avg / count / max / min / distinct_count
    alias: str | None = None

class FilterExpr(BaseModel):
    field: str
    op: str                         # eq / neq / gt / gte / lt / lte / in / between / like
    value: Any
    logic: str = "and"              # and / or (for combining with next filter)

class OrderExpr(BaseModel):
    field: str
    direction: str = "desc"          # asc / desc

class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    total: int                      # total count without pagination
    page: int
    page_size: int
```

#### 7. Filter Views CRUD (GET/POST/DELETE /api/v1/filter-views)

```python
class FilterViewCreate(BaseModel):
    name: str
    filter_condition: dict          # JSON serialized filter state

# GET /api/v1/filter-views → list user's saved views
# POST /api/v1/filter-views → create new
# DELETE /api/v1/filter-views/{id} → delete (owner only)
```

#### 16. POST /api/v1/auth/login — JWT Login

```python
# app/schemas/auth.py
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400        # 24 hours
    user: UserInfo

class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: str
    permissions: list[str]
```

#### 17. GET /api/v1/auth/me — Current User Info

```python
# Returns UserInfo (same as above, no token)
```

### File Structure

| File | Action |
|------|--------|
| `app/schemas/ai_recommend.py` | NEW: Chart/layout recommend schemas |
| `app/schemas/insight.py` | NEW: Insight schemas |
| `app/schemas/filter.py` | NEW: Filter schemas |
| `app/schemas/query.py` | NEW: Query DSL schemas |
| `app/schemas/auth.py` | NEW: Auth schemas |
| `app/api/v1/ai_recommend.py` | NEW: Chart/layout recommend routes |
| `app/api/v1/insights.py` | NEW: Insight routes |
| `app/api/v1/filter.py` | NEW: Filter routes |
| `app/api/v1/query.py` | NEW: Query routes |
| `app/api/v1/auth.py` | NEW: Auth routes |
| `app/services/recommendation_service.py` | NEW: Recommendation logic |
| `app/services/insight_service.py` | NEW: Insight logic |
| `app/services/filter_service.py` | NEW: Filter logic |
| `app/services/query_service.py` | NEW: Query engine |
| `app/services/auth_service.py` | NEW: Auth + JWT (share with BE-010) |
| `app/api/deps.py` | NEW: DI dependencies |

### Database Schema

See BE-009 for full DDL. This task uses:
- `insight` table (read/update status)
- `filter_view` table (CRUD)
- `users`/`roles` tables (auth, via BE-010)

### Service Logic

**Chart Recommendation Engine (recommendation_service.py):**

```python
RULE_BASED_MAP = {
    ("numeric", "categorical"): ["bar", "horizontal_bar"],
    ("numeric", "time"): ["line", "area"],
    ("numeric", "numeric"): ["scatter"],
    ("categorical", "categorical"): ["heatmap", "stacked_bar"],
    ("numeric",): ["pie", "donut"],
    ("categorical", "numeric", "categorical"): ["grouped_bar"],
}

async def recommend_chart(req: ChartRecommendRequest) -> ChartRecommendResponse:
    # Step 1: Rule-based pre-filter
    type_signature = tuple(sorted(set(req.data_types)))
    candidates = RULE_BASED_MAP.get(type_signature, ["table"])

    # Step 2: AI re-ranking (call Qwen with context)
    if len(candidates) > 1:
        ranked = await ai_rerank_charts(req.data_fields, candidates)
    else:
        ranked = [(c, 1.0) for c in candidates]

    # Step 3: Apply device-specific adjustments
    if req.device == "mobile":
        ranked = [r for r in ranked if r[0] not in ("heatmap", "scatter")]

    return ChartRecommendResponse(recommendations=[
        ChartRecommendItem(chart_type=ct, score=sc, reason=..., fields_mapping=...)
        for ct, sc in ranked[:3]
    ])
```

**Query DSL Engine (query_service.py):**

```python
from sqlalchemy import select, func, text

async def execute_query(db: AsyncSession, req: QueryRequest) -> QueryResponse:
    # Build SELECT columns
    select_cols = []
    for dim in req.dimensions:
        select_cols.append(getattr(RevenueDetail, dim))
    for me in req.metrics:
        agg_func = getattr(func, me.agg)
        col = agg_func(getattr(RevenueDetail, me.field))
        select_cols.append(col.label(me.alias or f"{me.agg}_{me.field}"))

    stmt = select(*select_cols)

    # Build WHERE filters
    if req.filters:
        conditions = []
        for f in req.filters:
            col = getattr(RevenueDetail, f.field)
            if f.op == "eq":
                conditions.append(col == f.value)
            elif f.op == "in":
                conditions.append(col.in_(f.value))
            elif f.op == "between":
                conditions.append(col.between(f.value[0], f.value[1]))
            elif f.op == "gte":
                conditions.append(col >= f.value)
            # ... etc
        stmt = stmt.where(*conditions)

    # GROUP BY
    if req.dimensions:
        stmt = stmt.group_by(*[getattr(RevenueDetail, d) for d in req.dimensions])

    # ORDER BY
    if req.order_by:
        for o in req.order_by:
            col = getattr(RevenueDetail, o.field)
            stmt = stmt.order_by(col.desc() if o.direction == "desc" else col.asc())

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    # Paginate
    stmt = stmt.offset(req.offset).limit(req.limit)
    result = await db.execute(stmt)
    rows = result.all()

    return QueryResponse(
        columns=[c.name for c in select_cols],
        rows=[list(r) for r in rows],
        total=total,
        page=(req.offset // req.limit) + 1,
        page_size=req.limit,
    )
```

### Caching Strategy

- Filter options: Redis `filter-options:{lang}`, TTL=600s, invalidate on data sync
- Query results: Redis `query:{sha256(req_json)}`, TTL=120s, bypass if `bypass_cache=True`
- Chart recommendations: Redis `chart-recommend:{sha256(req_json)}`, TTL=3600s

### Security

- All endpoints behind JWT auth (except `/auth/login`)
- `POST /api/v1/query`: input validation on `FilterExpr.op` — whitelist only
- `filter-views`: owner-only DELETE, check `user_id`
- `insights/{id}/status`: verify user has read access to this insight

### Testing Requirements

| Test | Type |
|------|------|
| Chart recommendation: rule-based match | unit |
| Chart recommendation: device filter | unit |
| Chart recommendation: AI rerank mock | integration |
| Insight list: pagination, filter by type/status | integration |
| Insight status: valid transitions only | integration |
| Insight status: 404 for non-existent | integration |
| Filter-options: returns correct dimensions | integration |
| Query DSL: all filter ops work | integration |
| Query DSL: SQL injection blocked | security (PM-014) |
| Filter views CRUD: owner isolation | integration |
| Auth login: valid credentials | integration |
| Auth login: wrong password returns 4005 | integration |
| Auth me: valid token returns user info | integration |
| Auth me: expired token returns 4004 | integration |

---

## BE-002: Report Async Task (Celery + State Machine)

### Priority: P0 (upgraded) | Depends on: AR-010, PM-006~009

### File Structure

| File | Action |
|------|--------|
| `app/models/report_task.py` | NEW: SQLAlchemy model |
| `app/schemas/report.py` | NEW: Pydantic schemas |
| `app/api/v1/reports.py` | NEW: Report API routes |
| `app/services/report_service.py` | NEW: Orchestration logic |
| `app/tasks/report_tasks.py` | NEW: Celery task definitions |
| `app/core/celery_app.py` | MODIFY: Add report queue |

### Database Schema

```python
# app/models/report_task.py
from app.models.base import Base
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Integer, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import enum

class ReportStatus(str, enum.Enum):
    PENDING = "pending"          # 等待执行
    COLLECTING_DATA = "collecting_data"  # 步骤1: 数据收集
    AI_ANALYZING = "ai_analyzing"       # 步骤2: AI分析
    DOCUMENT_GENERATING = "document_generating"  # 步骤3: 文档生成
    COMPLETED = "completed"      # 完成
    FAILED = "failed"            # 失败
    CANCELLING = "cancelling"    # 取消中
    CANCELLED = "cancelled"      # 已取消

class ReportTask(Base):
    __tablename__ = "report_task"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    report_type = Column(String(20), nullable=False)  # daily/weekly/monthly/quarterly
    date_range = Column(JSON, nullable=False)  # {"start": "2025-01", "end": "2025-03"}
    division = Column(String(100), nullable=True)
    title = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, default=ReportStatus.PENDING)
    current_step = Column(String(30), nullable=True)  # which step is active
    step_started_at = Column(DateTime(timezone=True), nullable=True)
    progress_detail = Column(Text, nullable=True)  # e.g., "收集到 3520 条记录"
    celery_task_id = Column(String(255), nullable=True)  # Celery task UUID
    retry_count = Column(Integer, nullable=False, default=0)
    parent_task_id = Column(BigInteger, ForeignKey("report_task.id"), nullable=True)
    result_data = Column(JSON, nullable=True)  # report content + metadata
    download_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_report_task_user_status", "user_id", "status"),
        Index("idx_report_task_created", "created_at"),
    )
```

### API Contracts

```python
# app/schemas/report.py
class ReportCreateRequest(BaseModel):
    report_type: str = "monthly"   # daily/weekly/monthly/quarterly
    date_range: DateRange
    division: str | None = None
    sections: list[str] = ["overview", "trend", "attribution", "alerts", "recommendations"]
    format: str = "markdown"       # markdown / html

class ReportTaskOut(BaseModel):
    id: int
    title: str
    report_type: str
    status: str
    current_step: str | None
    step_started_at: datetime | None
    progress_detail: str | None
    retry_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    download_url: str | None

    model_config = ConfigDict(from_attributes=True)

class ReportListParams(BaseModel):
    status: str | None = None
    page: int = 1
    page_size: int = 20

# POST /api/v1/reports  — create new report task
# GET /api/v1/reports    — list user's report tasks (paginated)
# GET /api/v1/reports/{id} — get single task detail
# POST /api/v1/reports/{id}/cancel — cancel a task
# POST /api/v1/reports/{id}/retry  — retry a failed task
# GET /api/v1/reports/{id}/download — download report file
```

### State Machine Logic

```python
VALID_TRANSITIONS = {
    ReportStatus.PENDING: [ReportStatus.COLLECTING_DATA, ReportStatus.CANCELLED],
    ReportStatus.COLLECTING_DATA: [ReportStatus.AI_ANALYZING, ReportStatus.FAILED, ReportStatus.CANCELLING],
    ReportStatus.AI_ANALYZING: [ReportStatus.DOCUMENT_GENERATING, ReportStatus.FAILED, ReportStatus.CANCELLING],
    ReportStatus.DOCUMENT_GENERATING: [ReportStatus.COMPLETED, ReportStatus.FAILED, ReportStatus.CANCELLING],
    ReportStatus.CANCELLING: [ReportStatus.CANCELLED, ReportStatus.COLLECTING_DATA],  # fallback
    ReportStatus.CANCELLED: [],        # terminal
    ReportStatus.COMPLETED: [],        # terminal
    ReportStatus.FAILED: [ReportStatus.PENDING],  # retry re-creates as PENDING
}

async def transition_report(db: AsyncSession, report_id: int, new_status: ReportStatus):
    report = await db.get(ReportTask, report_id)
    if report.status not in VALID_TRANSITIONS or new_status not in VALID_TRANSITIONS[report.status]:
        raise AppException(ErrorCode.REPORT_STATE_ERROR,
            f"Cannot transition from {report.status} to {new_status}")
    report.status = new_status
    if new_status in (ReportStatus.COLLECTING_DATA, ReportStatus.AI_ANALYZING, ReportStatus.DOCUMENT_GENERATING):
        report.current_step = new_status.value
        report.step_started_at = func.now()
    if new_status == ReportStatus.COMPLETED:
        report.completed_at = func.now()
    await db.commit()
```

### Celery Task Design

```python
# app/tasks/report_tasks.py
from app.core.celery_app import celery_app
from app.models.report_task import ReportStatus

@celery_app.task(bind=True, name="report.generate", queue="report_gen",
                 max_retries=3, default_retry_delay=30,
                 acks_late=True, reject_on_worker_lost=True)
def generate_report(self, report_id: int):
    """
    State machine step progression:
    1. COLLECTING_DATA → query DB, collect financial data
    2. AI_ANALYZING → call Qwen API for analysis
    3. DOCUMENT_GENERATING → assemble Word/PDF document
    4. COMPLETED → save result, notify user
    """
    # Step 1: Collect data
    transition_report_sync(report_id, ReportStatus.COLLECTING_DATA)
    try:
        data = collect_financial_data(report_id)
    except Exception as exc:
        transition_report_sync(report_id, ReportStatus.FAILED)
        raise self.retry(exc=exc)  # Celery auto-retry

    # Step 2: AI analysis
    transition_report_sync(report_id, ReportStatus.AI_ANALYZING)
    try:
        analysis = call_ai_analysis(data)
    except Exception as exc:
        transition_report_sync(report_id, ReportStatus.FAILED)
        raise self.retry(exc=exc)

    # Step 3: Generate document
    transition_report_sync(report_id, ReportStatus.DOCUMENT_GENERATING)
    try:
        document = assemble_document(data, analysis, report_id)
    except Exception as exc:
        transition_report_sync(report_id, ReportStatus.FAILED)
        raise self.retry(exc=exc)

    # Step 4: Complete
    save_result(report_id, document)
    transition_report_sync(report_id, ReportStatus.COMPLETED)
    # Create notification
    create_notification.delay(report_id, "report_completed")
```

### Cancel/Retry Logic

```python
# POST /api/v1/reports/{id}/cancel
async def cancel_report(report_id: int, db: AsyncSession):
    report = await db.get(ReportTask, report_id)
    if report.status not in (ReportStatus.PENDING, ReportStatus.COLLECTING_DATA,
                              ReportStatus.AI_ANALYZING, ReportStatus.DOCUMENT_GENERATING):
        raise AppException(ErrorCode.REPORT_STATE_ERROR, "Cannot cancel in current state")

    # Transition to CANCELLING
    await transition_report(db, report_id, ReportStatus.CANCELLING)

    # Revoke Celery task
    if report.celery_task_id:
        from celery.app.control import Control
        control = Control(app=celery_app)
        control.revoke(report.celery_task_id, terminate=True)

    # Set a timeout: if 30s no confirmation, revert
    # (Handled by a monitoring Celery beat task: check cancelling tasks >30s)
    await transition_report(db, report_id, ReportStatus.CANCELLED)

# POST /api/v1/reports/{id}/retry
async def retry_report(report_id: int, db: AsyncSession, user_id: int):
    report = await db.get(ReportTask, report_id)
    if report.status != ReportStatus.FAILED:
        raise AppException(ErrorCode.REPORT_STATE_ERROR, "Can only retry failed tasks")
    if report.retry_count >= 3:
        raise AppException(ErrorCode.REPORT_STATE_ERROR, "Max retries (3) reached")

    # Create new task with same params, parent_task_id pointing to old
    new_report = ReportTask(
        user_id=user_id,
        report_type=report.report_type,
        date_range=report.date_range,
        division=report.division,
        title=report.title,
        status=ReportStatus.PENDING,
        retry_count=0,
        parent_task_id=report.id,
    )
    db.add(new_report)
    await db.commit()

    # Launch new Celery task
    generate_report.delay(new_report.id)
    return new_report
```

### Caching Strategy

- Report task status is **not cached** (frontend polls every 5-10s, data is simple)
- Report download files: stored on disk/S3, served via streaming
- Generated report content: cached in Redis `report:{id}:content` TTL=3600s

### Async Task Design Summary

| Aspect | Decision |
|--------|----------|
| Queue | `report_gen` (concurrency: 2) |
| Retry policy | max_retries=3, default_retry_delay=30s, exponential backoff |
| Ack mode | acks_late=True, reject_on_worker_lost=True (task not lost on worker crash) |
| Time limit | soft=600s, hard=900s |
| State tracking | DB column `status` + `current_step` (not Celery result backend) |
| Cancel | Celery `revoke(terminate=True)` + DB state `cancelling` → `cancelled` |
| Notification on complete | `create_notification.delay()` — chained Celery task |

### Testing Requirements

| Test | Type |
|------|------|
| Report creation: creates DB record + enqueues Celery task | integration |
| State transitions: valid transitions succeed | unit |
| State transitions: invalid transitions raise error | unit |
| Cancel: pending task can be cancelled | integration |
| Cancel: running task transitions to cancelling | integration |
| Cancel: completed task cannot be cancelled | integration |
| Retry: failed task creates new task with parent_task_id | integration |
| Retry: max retries (3) blocks further retry | integration |
| Celery task: step progression (4 steps) | integration |
| Celery task: failure triggers retry | integration |
| Report list: pagination + status filter | integration |
| Step timeout: step > 5 min shows warning | unit |

---

## BE-003: Prediction API

### Priority: P0 (upgraded) | Depends on: AR-002

### File Structure

| File | Action |
|------|--------|
| `app/models/prediction.py` | NEW: SQLAlchemy model |
| `app/schemas/prediction.py` | NEW: Pydantic schemas |
| `app/api/v1/predictions.py` | NEW: API routes |
| `app/services/prediction_service.py` | NEW: Prediction engine |
| `app/tasks/prediction_tasks.py` | NEW: Celery tasks |

### Database Schema

```python
# app/models/prediction.py
class PredictionResult(Base):
    __tablename__ = "prediction_result"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    metric = Column(String(50), nullable=False)  # revenue / gross_profit / dso / etc.
    dimension = Column(JSON, nullable=True)       # filter dimensions {company, division}
    forecast_months = Column(Integer, nullable=False, default=3)
    confidence_level = Column(String(10), nullable=False, default="0.80")  # 80%

    # Prediction data
    historical_data = Column(JSON, nullable=False)   # past 12+ months data
    forecast_data = Column(JSON, nullable=False)     # [{period, value, lower, upper}]
    metrics_summary = Column(JSON, nullable=True)    # mape, mae, trend direction

    # Quality control
    data_months = Column(Integer, nullable=False)     # actual months of data used
    mape = Column(ARRAY(Float), nullable=True)        # MAPE per forecast point
    rejection_reason = Column(String(500), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="completed")  # completed / rejected / failed
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_prediction_metric_created", "metric", "created_at"),
    )
```

### API Contracts

```python
# app/schemas/prediction.py
class PredictionRequest(BaseModel):
    metric: str                    # revenue / gross_profit / gross_profit_rate / dso
    filters: FilterExpr | None = None
    forecast_months: int = 3       # 1~6
    confidence_level: float = 0.80 # 0.80 / 0.90 / 0.95

class PredictionResponse(BaseModel):
    id: int
    metric: str
    historical_data: list[DataPoint]   # [{period, value}]
    forecast_data: list[ForecastPoint] # [{period, value, lower_bound, upper_bound}]
    metrics: PredictionMetrics
    status: str                        # completed / rejected
    rejection_reason: str | None

class ForecastPoint(BaseModel):
    period: str                        # "2025-04"
    value: float
    lower_bound: float                 # confidence interval lower
    upper_bound: float                 # confidence interval upper

class PredictionMetrics(BaseModel):
    mape: float | None                 # Mean Absolute Percentage Error
    data_months: int
    trend: str                         # upward / downward / stable
    seasonality: bool

# POST /api/v1/predictions — create prediction
# GET /api/v1/predictions/{id} — get result
```

### Prediction Engine Logic (prediction_service.py)

```python
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing

class PredictionService:
    MIN_DATA_MONTHS = 12
    MAPE_QUALIFIED = 0.15      # MAPE < 15% → qualified
    MAPE_REJECT = 0.25         # MAPE > 25% → reject

    async def predict(self, req: PredictionRequest, db: AsyncSession) -> PredictionResponse:
        # Step 1: Fetch historical data (min 12 months)
        data = await self._fetch_historical(req.metric, req.filters, db)
        if len(data) < self.MIN_DATA_MONTHS:
            return PredictionResponse(
                status="rejected",
                rejection_reason=f"数据不足: 需要至少{self.MIN_DATA_MONTHS}个月数据, 当前{len(data)}个月",
                metrics=PredictionMetrics(mape=None, data_months=len(data), trend="unknown", seasonality=False),
            )

        # Step 2: Build time series
        values = np.array([d["value"] for d in sorted(data, key=lambda x: x["period"])])
        periods = [d["period"] for d in sorted(data, key=lambda x: x["period"])]

        # Step 3: Try Holt-Winters (if >= 2 full seasons) else simple exponential
        if len(values) >= 24:
            model = ExponentialSmoothing(values, seasonal_periods=12, trend="add", seasonal="add")
        else:
            model = ExponentialSmoothing(values, trend="add")

        fitted = model.fit()

        # Step 4: Forecast
        forecast = fitted.forecast(req.forecast_months)
        conf_int = self._calc_confidence_interval(fitted, forecast, req.confidence_level)

        # Step 5: Calculate MAPE (in-sample)
        residuals = fitted.resid
        mape = np.mean(np.abs(residuals / (values + 1e-10)))  # avoid div by zero

        # Step 6: Quality check
        if mape > self.MAPE_REJECT:
            return PredictionResponse(
                status="rejected",
                rejection_reason=f"预测精度不足: MAPE={mape:.1%}, 超过拒绝阈值{self.MAPE_REJECT:.0%}",
                metrics=PredictionMetrics(mape=mape, data_months=len(data), trend="unknown", seasonality=False),
            )

        # Step 7: Build result
        trend = self._detect_trend(forecast)
        forecast_points = [
            ForecastPoint(
                period=self._next_period(periods[-1], i+1),
                value=float(v),
                lower_bound=float(conf_int[i][0]),
                upper_bound=float(conf_int[i][1]),
            )
            for i, v in enumerate(forecast)
        ]

        return PredictionResponse(
            status="completed",
            historical_data=[DataPoint(period=p, value=float(v)) for p, v in zip(periods, values)],
            forecast_data=forecast_points,
            metrics=PredictionMetrics(
                mape=float(mape) if mape <= self.MAPE_QUALIFIED else None,
                data_months=len(data),
                trend=trend,
                seasonality=len(values) >= 24,
            ),
        )

    def _calc_confidence_interval(self, model, forecast, confidence_level):
        """Calculate prediction intervals based on residuals std"""
        z_scores = {0.80: 1.28, 0.90: 1.645, 0.95: 1.96}
        z = z_scores.get(confidence_level, 1.28)
        residuals_std = np.std(model.resid)
        return [(v - z * residuals_std, v + z * residuals_std) for v in forecast]
```

### Caching Strategy

- Prediction results: Redis `prediction:{sha256(req_json)}`, TTL=1800s (30min)
- Historical data query: use shared query_repo, no separate cache needed
- Invalidate on new data sync (clear all prediction caches)

### Security

- Same data access rules as query API (RBAC row-level filtering)
- Prediction store in `prediction_result` table tied to user_id
- Rejection reasons exposed to frontend for UX

### Testing Requirements

| Test | Type |
|------|------|
| Prediction: <12 months data → rejected | integration |
| Prediction: MAPE > 25% → rejected | integration |
| Prediction: MAPE < 15% → completed with metrics | integration |
| Prediction: 15% < MAPE < 25% → completed without MAPE | integration |
| Prediction: confidence intervals calculated correctly | unit |
| Prediction: trend detection (upward/downward/stable) | unit |
| Prediction: Holt-Winters vs simple selection | unit |
| Prediction: GET result by id | integration |
| Prediction: 404 for non-existent id | integration |
| Large data: 60+ months time series | performance |

---

## BE-004: Transaction Analysis 5 Endpoints (Phase 2)

### Priority: P1 | Depends on: AR-002

### API Contracts

```python
# app/schemas/transaction.py
# Route prefix: /api/v1/transactions

# GET /api/v1/transactions/contracts
# Params: year, company?, division?, page, page_size
# Returns: list of contracts with revenue/cost/gross_profit summary

# GET /api/v1/transactions/orders
# Params: year, company?, division?, page, page_size
# Returns: list of orders with item count, total amount

# GET /api/v1/transactions/projects
# Params: year, company?, division?, page, page_size
# Returns: list of projects with progress, financials

# GET /api/v1/transactions/anomalies
# Params: year, company?, division?, anomaly_type?, page, page_size
# Returns: flagged transactions with anomaly type and severity

# GET /api/v1/transactions/large-amounts
# Params: year, company?, division?, min_amount?, page, page_size
# Returns: high-value transactions sorted by amount
```

### Response Schemas

```python
class ContractSummary(BaseModel):
    contract_number: str
    company: str
    project_name: str
    total_revenue: float
    total_cost: float
    gross_profit: float
    gross_profit_rate: float
    order_count: int

class OrderSummary(BaseModel):
    order_number: str
    company: str
    contract_number: str
    order_type: str
    revenue: float
    cost: float
    gross_profit: float

class ProjectSummary(BaseModel):
    project_name: str
    company: str
    contract_count: int
    total_revenue: float
    total_cost: float
    gross_profit: float
    gross_profit_rate: float

class AnomalyItem(BaseModel):
    id: int
    record_id: int
    anomaly_type: str          # margin_drop / price_anomaly / volume_spike
    severity: str              # high / medium / low
    description: str
    value: float
    threshold: float
    created_at: datetime

class LargeAmountItem(BaseModel):
    id: int
    contract_number: str
    project_name: str
    company: str
    revenue_amount: float
    gross_profit_rate: float
    transaction_date: str
```

### File Structure

| File | Action |
|------|--------|
| `app/schemas/transaction.py` | NEW: Transaction schemas |
| `app/api/v1/transactions.py` | NEW: Transaction routes |
| `app/services/transaction_service.py` | NEW: Transaction analysis logic |

### Service Logic

All 5 endpoints query `revenue_detail` via the shared `query_repo` (BE-008). No new tables needed.

```python
# GET /api/v1/transactions/large-amounts
async def get_large_amounts(params, db):
    threshold = params.min_amount or calculate_dynamic_threshold(db)
    query = select(RevenueDetail).where(
        RevenueDetail.revenue_amount >= threshold,
        RevenueDetail.data_status == "active",
    )
    # Apply filters, order by revenue_amount DESC
    # Return paginated results

def calculate_dynamic_threshold(db) -> float:
    """Use top 5% cutoff as dynamic threshold"""
    result = db.execute(
        select(func.percentile_cont(0.95).within_group(
            RevenueDetail.revenue_amount
        ))
    )
    return result.scalar() or 1000000
```

### Caching Strategy

- Light caching: Redis `transactions:{type}:{sha256(params)}`, TTL=120s
- Cache invalidation on data sync

### Testing Requirements

| Test | Type |
|------|------|
| Contracts: grouped by contract, correct aggregation | integration |
| Orders: paginated, filtered by year | integration |
| Projects: grouped by project | integration |
| Anomalies: returns flagged records | integration |
| Large amounts: threshold applied correctly | integration |
| Large amounts: dynamic threshold calculation | unit |

---

## BE-005: Deprecated API Cleanup

### Priority: P0 | Depends on: AR-004

### Actions

```python
# 1. DELETE: app/api/v1/ai.py — remove attribution endpoint
#    Remove file entirely or remove specific route

# 2. DEPRECATE: POST /api/v1/ai/attribution → respond with 410 Gone + redirect header
#    Or simply remove the route registration

# 3. REDIRECT: GET /api/v1/drill-down → 301 to GET /api/v1/drilldowns/{...}
#    Cannot 301 directly (query params → path params) — return 410 with link

# 4. MARK INTERNAL: POST /api/v1/ai/qa → keep but remove from router registration
#    It can remain as an internal service method

# 5. KEEP: GET /api/v1/dashboard (repurposed as BFF)
#    KEEP: GET /api/v1/metrics (aggregation)
#    KEEP: DELETE /api/v1/cache/invalidate (ops)
```

### Script: `scripts/cleanup_deprecated.py`

```python
"""
Run: python -m scripts.cleanup_deprecated

This script:
1. Removes deprecated route registrations from app/api/v1/router.py
2. Adds 410 responses for removed endpoints
3. Updates tests that reference deprecated endpoints
4. Verifies no frontend code references old endpoints
"""
# ... implementation
```

### Testing Requirements

| Test | Type |
|------|------|
| Removed attribution returns 410 or 404 | integration |
| Old drill-down returns 410 | integration |
| Dashboard still works | integration |
| Metrics still works | integration |
| No frontend references to old paths | e2e |

---

## BE-006: Drill-down API Refactor to RESTful

### Priority: P0 | Depends on: AR-008

### API Contracts

```python
# app/schemas/drilldown.py

# GET /api/v1/drilldowns/{report_id}/summary
# → Company-level summary (was Level 1)
class DrillSummaryItem(BaseModel):
    company: str
    total_revenue: float
    total_cost: float
    gross_profit: float
    gross_profit_rate: float
    record_count: int
    drillable: bool = True

# GET /api/v1/drilldowns/{report_id}/departments?company=锐捷网络
# → Department-level breakdown (was Level 2)
class DrillDepartmentItem(BaseModel):
    department: str              # product_division
    revenue: float
    cost: float
    gross_profit: float
    gross_profit_rate: float
    revenue_share: float
    drillable: bool = True

# GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products?company=锐捷网络
# → Customer+Product level (was Level 3)
class DrillProductItem(BaseModel):
    customer_code: str
    customer_name: str | None
    product: str
    revenue: float
    cost: float
    gross_profit: float
    gross_profit_rate: float
    contribution_rate: float
    drillable: bool = True

# GET /api/v1/drilldowns/{report_id}/departments/{dept_id}/products/{product_id}/records
# → Transaction detail (was Level 4)
class DrillRecordItem(BaseModel):
    id: int
    contract_number: str
    order_number: str
    project_name: str
    customer_code: str
    revenue: float
    cost: float
    gross_profit: float
    gross_profit_rate: float

# GET /api/v1/drilldowns/records/{record_id}
# → Single record detail
class DrillRecordDetail(BaseModel):
    id: int
    batch_id: str
    company: str
    contract_number: str
    order_number: str
    project_name: str
    customer_code: str
    product_division: str
    revenue_year: int
    revenue_amount: float
    cost_amount: float
    gross_profit: float
    gross_profit_rate: float
    source_file: str | None
    created_at: datetime
```

### Router Structure

```python
# app/api/v1/drilldowns.py
router = APIRouter(prefix="/api/v1/drilldowns", tags=["Drill-down"])

@router.get("/{report_id}/summary")
async def drill_summary(report_id: int, year: int, db=Depends(get_db)):
    """Level 1: Company-level summary"""
    ...

@router.get("/{report_id}/departments")
async def drill_departments(report_id: int, company: str, year: int, db=Depends(get_db)):
    """Level 2: Department breakdown within a company"""
    ...

@router.get("/{report_id}/departments/{dept_id}/products")
async def drill_products(report_id: int, dept_id: str, company: str, year: int, db=Depends(get_db)):
    """Level 3: Customer+product within a department"""
    ...

@router.get("/{report_id}/departments/{dept_id}/products/{product_id}/records")
async def drill_records(report_id: int, product_id: str, company: str, year: int, page=1, page_size=20, db=Depends(get_db)):
    """Level 4: Transaction records"""
    ...

@router.get("/records/{record_id}")
async def drill_record_detail(record_id: int, db=Depends(get_db)):
    """Single record detail"""
    ...
```

### Service Logic

Each level performes a SELECT + GROUP BY on `revenue_detail` with progressively finer granularity:

- Level 1: GROUP BY company
- Level 2: GROUP BY company, product_division
- Level 3: GROUP BY company, product_division, ncc_customer_code
- Level 4: No GROUP BY, return individual records with LIMIT/OFFSET

All levels filter by `data_status = 'active'` and the specified `year`/`company`.

### Caching Strategy

- Drilldown results: Redis `drilldown:{report_id}:{level}:{composite_key}`, TTL=180s
- Cache invalidated on data sync (pattern delete: `drilldown:*`)

### Testing Requirements

| Test | Type |
|------|------|
| Level 1: returns company-level aggregation | integration |
| Level 2: filters by company correctly | integration |
| Level 3: returns customer+product data | integration |
| Level 4: paginated transaction records | integration |
| Record detail: correct single record | integration |
| Invalid report_id → 404 | integration |
| Missing required params → 422 | integration |

---

## BE-007: Correlation System (Replace Attribution)

### Priority: P0 | Depends on: AR-009

### Database Schema

```python
# app/models/correlation.py
class CorrelationResult(Base):
    __tablename__ = "correlation_result"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    metric_pair = Column(JSON, nullable=False)  # {"metric_a": "revenue", "metric_b": "cost"}
    dimension = Column(JSON, nullable=True)     # filter context
    coefficient = Column(Float, nullable=False)  # Pearson correlation coefficient
    p_value = Column(Float, nullable=True)
    strength = Column(String(20), nullable=False)  # strong / moderate / weak / none
    direction = Column(String(10), nullable=False)  # positive / negative
    ai_explanation = Column(Text, nullable=True)
    data_points = Column(Integer, nullable=False)  # number of data points used
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_correlation_user_created", "user_id", "created_at"),
    )

class CorrelationCalibration(Base):
    __tablename__ = "correlation_calibration"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    correlation_id = Column(BigInteger, ForeignKey("correlation_result.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    decision = Column(String(20), nullable=False)  # confirm / doubt / reject
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_calibration_correlation", "correlation_id"),
    )
```

### API Contracts

```python
# app/schemas/correlation.py

# POST /api/v1/correlations/analyze
class CorrelationAnalyzeRequest(BaseModel):
    metric_a: str           # e.g., "revenue"
    metric_b: str           # e.g., "cost"
    filters: FilterExpr | None = None
    use_ai: bool = True     # whether to include AI explanation

class CorrelationResultOut(BaseModel):
    id: int
    metric_pair: dict
    coefficient: float
    strength: str
    direction: str
    ai_explanation: str | None
    data_points: int
    calibrations: list[CalibrationOut]
    created_at: datetime

# GET /api/v1/correlations
# Params: page, page_size, metric_a?, metric_b?, strength?
# Returns: paginated list of CorrelationResultOut

# POST /api/v1/correlations/{id}/calibrate
class CalibrateRequest(BaseModel):
    decision: str   # confirm / doubt / reject
    comment: str | None = None

class CalibrationOut(BaseModel):
    id: int
    user_id: int
    decision: str
    comment: str | None
    created_at: datetime
```

### Service Logic

```python
# app/services/correlation_service.py
import numpy as np
from scipy import stats

class CorrelationService:
    async def analyze(self, req: CorrelationAnalyzeRequest, db: AsyncSession, user_id: int):
        # Step 1: Fetch data for both metrics
        data_a = await self._fetch_metric(req.metric_a, req.filters, db)
        data_b = await self._fetch_metric(req.metric_b, req.filters, db)

        # Step 2: Align by period
        aligned = self._align_by_period(data_a, data_b)
        if len(aligned) < 3:
            raise AppException(ErrorCode.VALIDATION_ERROR, "Insufficient data points for correlation")

        # Step 3: Calculate Pearson correlation
        vals_a = np.array([p["value"] for p in aligned])
        vals_b = np.array([p["value"] for p in aligned])
        coefficient, p_value = stats.pearsonr(vals_a, vals_b)

        # Step 4: Classify strength
        abs_coef = abs(coefficient)
        if abs_coef >= 0.7:
            strength = "strong"
        elif abs_coef >= 0.4:
            strength = "moderate"
        elif abs_coef >= 0.1:
            strength = "weak"
        else:
            strength = "none"

        direction = "positive" if coefficient >= 0 else "negative"

        # Step 5: AI explanation (optional)
        ai_explanation = None
        if req.use_ai:
            ai_explanation = await self._ai_explain(req.metric_a, req.metric_b, coefficient, strength, direction, aligned)

        # Step 6: Save result
        result = CorrelationResult(
            user_id=user_id,
            metric_pair={"metric_a": req.metric_a, "metric_b": req.metric_b},
            coefficient=coefficient,
            p_value=p_value,
            strength=strength,
            direction=direction,
            ai_explanation=ai_explanation,
            data_points=len(aligned),
        )
        db.add(result)
        await db.commit()
        return result
```

### Caching Strategy

- Correlation results: Redis `correlation:{sha256(req_json)}`, TTL=3600s (1h)
- Correlation list: not cached (paginated, user-specific)

### Testing Requirements

| Test | Type |
|------|------|
| Analyze: positive correlation correctly calculated | integration |
| Analyze: negative correlation detected | integration |
| Analyze: p-value calculation | unit |
| Analyze: strength classification (borders) | unit |
| Analyze: AI explanation included when use_ai=True | integration |
| Analyze: AI explanation skipped when use_ai=False | integration |
| List: paginated results | integration |
| Calibrate: confirm saves correctly | integration |
| Calibrate: reject saves correctly | integration |
| Calibrate: 404 for non-existent correlation | integration |

---

## BE-008: Dual Data Path (Dashboard BFF + Query API)

### Priority: P0 | Depends on: AR-007, PM-011

### File Structure

| File | Action |
|------|--------|
| `app/services/query_service.py` | NEW/MODIFY: unified query engine |
| `app/repositories/base.py` | NEW: BaseRepository |
| `app/repositories/dashboard_repo.py` | NEW: Dashboard aggregation queries |
| `app/repositories/query_repo.py` | NEW: Unified query repository |
| `app/core/cache.py` | MODIFY: Redis cache client |
| `app/api/v1/dashboard.py` | MODIFY: BFF layer (wrap multiple queries) |
| `app/api/v1/query.py` | MODIFY: Direct DB path |

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend                          │
├──────────────┬──────────────────────────────────────┤
│ Dashboard    │  Other Pages (Insight, Drill, etc.)  │
│ (first load) │  (any filter/refresh/drill action)   │
└──────┬───────┴──────────────┬───────────────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐    ┌──────────────────┐
│ Dashboard    │    │  Query API       │
│ BFF          │    │  POST /api/v1/   │
│ GET /api/v1/ │    │  query            │
│ dashboard    │    │                  │
└──────┬───────┘    └────────┬─────────┘
       │                     │
       ▼                     ▼
┌──────────────┐    ┌──────────────────┐
│ Redis Cache  │    │  Direct DB       │
│ TTL=300s     │    │  (no cache)      │
└──────┬───────┘    └────────┬─────────┘
       │                     │
       └─────────┬───────────┘
                 ▼
       ┌──────────────────┐
       │ Shared DAO/Repo  │
       │ (same queries)   │
       └──────────────────┘
```

### Cache Layer

```python
# app/core/cache.py
import json
import hashlib
import redis.asyncio as aioredis
from typing import Optional, Any

class RedisCache:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value: Any, ttl: int = 300):
        await self.redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern (e.g., 'dashboard:*')"""
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

    async def invalidate_on_sync(self):
        """Invalidate all data caches after a sync"""
        for pattern in ["dashboard:*", "drilldown:*", "query:*", "prediction:*"]:
            await self.delete_pattern(pattern)

cache = RedisCache(config.REDIS_URL)

# Cache key patterns
CACHE_KEYS = {
    "dashboard": "dashboard:{year}:{division}:{company}",
    "drilldown": "drilldown:{report_id}:{level}:{composite_hash}",
    "query": "query:{req_hash}",
    "prediction": "prediction:{req_hash}",
    "correlation": "correlation:{req_hash}",
    "filter_options": "filter-options:latest",
    "data_freshness": "data-freshness:latest",
}
```

### Dashboard BFF

```python
# app/api/v1/dashboard.py
@router.get("")
async def get_dashboard(
    year: int,
    division: str | None = None,
    company: str | None = None,
    bypass_cache: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "analyst", "viewer"])),
):
    cache_key = CACHE_KEYS["dashboard"].format(
        year=year, division=division or "all", company=company or "all"
    )

    # Return cached if available (unless bypass)
    if not bypass_cache:
        cached = await cache.get(cache_key)
        if cached:
            return APIResponse(data=cached)

    # BFF: aggregate multiple queries into one response
    overview = await dashboard_repo.get_overview(db, year, division, company)
    trend = await dashboard_repo.get_trend(db, year, division, company, granularity="month")
    by_division = await dashboard_repo.get_by_division(db, year, company)
    by_company = await dashboard_repo.get_by_company(db, year, division)
    top_customers = await dashboard_repo.get_top_customers(db, year, company, division, limit=10)

    result = {
        "overview": overview,
        "trend": trend,
        "by_division": by_division,
        "by_company": by_company,
        "top10_customers": top_customers,
    }

    # Cache result (only if not bypassed)
    if not bypass_cache:
        await cache.set(cache_key, result, ttl=config.DASHBOARD_CACHE_TTL)

    return APIResponse(data=result)
```

### Same-DAO Guarantee

```python
# app/repositories/dashboard_repo.py
# app/repositories/query_repo.py

# Both use the same SQLAlchemy models and raw SQL queries
# Example shared query:
@staticmethod
async def get_by_division(db, year, company=None):
    """Used by BOTH dashboard BFF and query API"""
    stmt = select(
        RevenueDetail.product_division,
        func.sum(RevenueDetail.revenue_amount).label("revenue"),
        func.sum(RevenueDetail.cost_amount).label("cost"),
        func.sum(RevenueDetail.gross_profit).label("gross_profit"),
        func.avg(RevenueDetail.gross_profit_rate).label("gross_profit_rate"),
    ).where(
        RevenueDetail.revenue_year == year,
        RevenueDetail.data_status == "active",
    )
    if company:
        stmt = stmt.where(RevenueDetail.company == company)
    stmt = stmt.group_by(RevenueDetail.product_division)
    return (await db.execute(stmt)).all()
```

### Cache Invalidation Triggers

| Event | Invalidation |
|-------|-------------|
| IMAP sync completes | Clear `dashboard:*`, `drilldown:*`, `query:*` |
| Manual refresh (`POST /api/v1/data-sync/refresh`) | Clear all data caches, bypass cache on next dashboard call |
| Excel upload | Same as IMAP sync |
| Data freshness check | Update `data_freshness` cache only |

### Testing Requirements

| Test | Type |
|------|------|
| Dashboard: returns aggregated data from cache | integration |
| Dashboard: bypass_cache forces fresh DB query | integration |
| Dashboard: cache TTL expires → next call re-caches | integration |
| Dashboard BFF and Query API return same data | integration (contract) |
| Redis down → dashboard falls back to DB | integration |
| Data sync → all caches invalidated | integration |
| Manual refresh bypasses cache | integration |

---

## BE-009: Database Migration Scripts

### Priority: P0 | Depends on: AR-005

### Migration Files

```python
# migrations/versions/002_v3_new_tables.py
"""Add 6 V3.0 tables: insight, filter_view, correlation_result, correlation_calibration, prediction_result, report_task"""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # --- insight ---
    op.create_table("insight",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="unread"),
        sa.Column("related_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_insight_type_status", "insight", ["type", "status"])
    op.create_index("idx_insight_created", "insight", ["created_at"])

    # --- filter_view ---
    op.create_table("filter_view",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("filter_condition", postgresql.JSONB(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_filter_view_user", "filter_view", ["user_id"])

    # --- correlation_result ---
    op.create_table("correlation_result",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_pair", postgresql.JSONB(), nullable=False),
        sa.Column("dimension", postgresql.JSONB(), nullable=True),
        sa.Column("coefficient", sa.Float(), nullable=False),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("strength", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("data_points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_correlation_user_created", "correlation_result", ["user_id", "created_at"])

    # --- correlation_calibration ---
    op.create_table("correlation_calibration",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("correlation_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_calibration_correlation", "correlation_calibration", ["correlation_id"])

    # --- prediction_result ---
    op.create_table("prediction_result",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("dimension", postgresql.JSONB(), nullable=True),
        sa.Column("forecast_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("confidence_level", sa.String(10), nullable=False, server_default="0.80"),
        sa.Column("historical_data", postgresql.JSONB(), nullable=False),
        sa.Column("forecast_data", postgresql.JSONB(), nullable=False),
        sa.Column("metrics_summary", postgresql.JSONB(), nullable=True),
        sa.Column("data_months", sa.Integer(), nullable=False),
        sa.Column("mape", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prediction_metric_created", "prediction_result", ["metric", "created_at"])

    # --- report_task ---
    op.create_table("report_task",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("date_range", postgresql.JSONB(), nullable=False),
        sa.Column("division", sa.String(100), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("sections", postgresql.JSONB(), nullable=True),
        sa.Column("output_format", sa.String(20), nullable=True, server_default="markdown"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.String(30), nullable=True),
        sa.Column("step_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_detail", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_task_id", sa.BigInteger(), nullable=True),
        sa.Column("result_data", postgresql.JSONB(), nullable=True),
        sa.Column("download_url", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_report_task_user_status", "report_task", ["user_id", "status"])
    op.create_index("idx_report_task_created", "report_task", ["created_at"])


# --- migrations/versions/003_v4_new_tables.py ---
"""Add 4 V4.0 tables: audit_log, notification, users, roles"""

revision = "003"
down_revision = "002"

def upgrade():
    # --- roles ---
    op.create_table("roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("permissions", postgresql.JSONB(), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Seed roles
    op.execute("""
        INSERT INTO roles (name, permissions, description) VALUES
        ('admin', '["read", "write", "delete", "manage_users", "export"]', '系统管理员'),
        ('analyst', '["read", "write", "export"]', '数据分析师'),
        ('viewer', '["read"]', '只读用户')
    """)

    # --- users ---
    op.create_table("users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_users_username", "users", ["username"], unique=True)

    # --- audit_log ---
    op.create_table("audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("before_value", postgresql.JSONB(), nullable=True),
        sa.Column("after_value", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_user", "audit_log", ["user_id", "created_at"])
    op.create_index("idx_audit_log_action", "audit_log", ["action", "created_at"])
    op.create_index("idx_audit_log_resource", "audit_log", ["resource", "resource_id"])

    # --- notification ---
    op.create_table("notification",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("related_resource", sa.String(100), nullable=True),
        sa.Column("related_id", sa.BigInteger(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notification_user_read", "notification", ["user_id", "is_read", "created_at"])
```

### Index Summary

| Table | Index | Purpose |
|-------|-------|---------|
| insight | (type, status) | Filter by type+status |
| insight | (created_at) | Sort by time |
| filter_view | (user_id) | User's views |
| correlation_result | (user_id, created_at) | User's history |
| correlation_calibration | (correlation_id) | Get calibrations for a result |
| prediction_result | (metric, created_at) | Metric history |
| report_task | (user_id, status) | Task list by user+status |
| report_task | (created_at) | Sort by time |
| audit_log | (user_id, created_at) | User audit trail |
| audit_log | (action, created_at) | Action-type lookup |
| audit_log | (resource, resource_id) | Resource lookup |
| notification | (user_id, is_read, created_at) | Unread notifications for user |

### Testing Requirements

| Test | Type |
|------|------|
| Migration 002: all 6 tables created | integration (db) |
| Migration 003: all 4 tables created | integration (db) |
| Migration: rollback 003 then 002 | integration (db) |
| Migration: seed roles data present | integration (db) |

---

## BE-010: RBAC Permission System

### Priority: P0 | Depends on: AR-013

### File Structure

| File | Action |
|------|--------|
| `app/models/user.py` | NEW: SQLAlchemy model |
| `app/models/role.py` | NEW: SQLAlchemy model |
| `app/services/auth_service.py` | NEW: JWT + password hashing |
| `app/api/v1/auth.py` | NEW: Login + me endpoints |

### Database Schema (see BE-009 migration)

### Service Logic

```python
# app/services/auth_service.py
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    SECRET_KEY = config.JWT_SECRET_KEY
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE = 86400  # 24h

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def create_token(self, user_id: int, role: str) -> dict:
        expire = datetime.utcnow() + timedelta(seconds=self.ACCESS_TOKEN_EXPIRE)
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return {"access_token": token, "token_type": "bearer", "expires_in": self.ACCESS_TOKEN_EXPIRE}

    def decode_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except JWTError:
            return None
```

### Permission Matrix

```python
RBAC_MATRIX = {
    "admin": {
        "read": True, "write": True, "delete": True,
        "manage_users": True, "export": True,
        "can_cancel_any_report": True,
        "can_view_audit_log": True,
    },
    "analyst": {
        "read": True, "write": True, "delete": False,
        "manage_users": False, "export": True,
        "can_cancel_any_report": False,  # can only cancel own
        "can_view_audit_log": False,
    },
    "viewer": {
        "read": True, "write": False, "delete": False,
        "manage_users": False, "export": False,
        "can_cancel_any_report": False,
        "can_view_audit_log": False,
    },
}

def check_permission(user: User, permission: str) -> bool:
    return RBAC_MATRIX.get(user.role.name, {}).get(permission, False)
```

### API Implementation

```python
# POST /api/v1/auth/login
async def login(req: LoginRequest, db: AsyncSession):
    user = await db.execute(
        select(User).where(User.username == req.username, User.is_active == True)
    )
    user = user.scalar_one_or_none()
    if not user or not auth_service.verify_password(req.password, user.password_hash):
        raise AppException(ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误")

    # Update last_login
    user.last_login = func.now()
    await db.commit()

    token_data = auth_service.create_token(user.id, user.role.name)
    return APIResponse(data={
        **token_data,
        "user": UserInfo(id=user.id, username=user.username, email=user.email,
                         role=user.role.name, permissions=RBAC_MATRIX[user.role.name]),
    })

# GET /api/v1/auth/me
async def me(user: User = Depends(require_role(["admin", "analyst", "viewer"]))):
    return APIResponse(data=UserInfo(
        id=user.id, username=user.username, email=user.email,
        role=user.role.name, permissions=RBAC_MATRIX[user.role.name],
    ))
```

### Middleware Integration

```python
# app/api/deps.py
async def get_current_user(
    authorization: str = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppException(ErrorCode.UNAUTHORIZED, "Missing or invalid token")
    token = authorization.split(" ", 1)[1]
    payload = auth_service.decode_token(token)
    if payload is None:
        raise AppException(ErrorCode.TOKEN_EXPIRED, "Token expired or invalid")
    user = await db.get(User, payload["user_id"])
    if not user or not user.is_active:
        raise AppException(ErrorCode.UNAUTHORIZED, "User not found or inactive")
    return user

def require_role(roles: list[str]):
    async def checker(current_user: User = Depends(get_current_user)):
        if current_user.role.name not in roles:
            raise AppException(ErrorCode.FORBIDDEN, f"Requires one of: {roles}")
        return current_user
    return checker

def require_permission(permission: str):
    async def checker(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user, permission):
            raise AppException(ErrorCode.FORBIDDEN, f"Requires permission: {permission}")
        return current_user
    return checker
```

### Testing Requirements

| Test | Type |
|------|------|
| Login: valid credentials → token | integration |
| Login: invalid password → 4005 | integration |
| Login: inactive user → rejected | integration |
| Me: valid token → user info | integration |
| Me: expired token → 4004 | integration |
| Role guard: admin can access admin endpoints | integration |
| Role guard: viewer cannot write | integration |
| Role guard: analyst can write but not delete | integration |
| Permission: export check by role | integration |
| Concurrent token refresh: old token invalidation | security |

---

## BE-011: Audit Log (audit_log table)

### Priority: P0 | Depends on: AR-013

### File Structure

| File | Action |
|------|--------|
| `app/models/audit_log.py` | NEW: SQLAlchemy model |
| `app/services/audit_service.py` | NEW: Audit log writer |

### Service Logic

```python
# app/services/audit_service.py
from app.models.audit_log import AuditLog
from app.core.logging import get_trace_id

class AuditService:
    AUDIT_ACTIONS = {
        "CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT",
        "CANCEL", "RETRY", "CALIBRATE", "EXPORT", "SYNC",
    }

    @staticmethod
    async def log(
        db: AsyncSession,
        user_id: int | None,
        action: str,
        resource: str,
        resource_id: str | None = None,
        before_value: dict | None = None,
        after_value: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        assert action in AuditService.AUDIT_ACTIONS, f"Invalid audit action: {action}"

        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id else None,
            before_value=before_value,
            after_value=after_value,
            ip_address=ip_address,
            user_agent=user_agent,
            trace_id=get_trace_id(),
        )
        db.add(log_entry)
        await db.commit()
```

### Integration Pattern (decorator-based)

```python
# app/core/audit_decorator.py
from functools import wraps
from app.services.audit_service import AuditService

def audit_log(action: str, resource: str):
    """Decorator to automatically log audit entries for write operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id, db from kwargs
            user = kwargs.get("user") or kwargs.get("current_user")
            db = kwargs.get("db") or kwargs.get("session")

            # Call the actual handler
            result = await func(*args, **kwargs)

            # Log AFTER successful operation
            user_id = user.id if user else None
            resource_id = str(kwargs.get("id", "")) if "id" in kwargs else None

            await AuditService.log(
                db=db, user_id=user_id, action=action,
                resource=resource, resource_id=resource_id,
                ip_address=kwargs.get("request").client.host if "request" in kwargs else None,
            )
            return result
        return wrapper
    return decorator

# Usage:
# @router.post("/api/v1/insights/{id}/status")
# @audit_log(action="UPDATE", resource="insight")
# async def update_insight_status(...):
```

### Write Operation Coverage

| Endpoint | Action | Resource |
|----------|--------|----------|
| POST /api/v1/auth/login | LOGIN | auth |
| POST /api/v1/insights/{id}/status | UPDATE | insight |
| POST /api/v1/filter-views | CREATE | filter_view |
| DELETE /api/v1/filter-views/{id} | DELETE | filter_view |
| POST /api/v1/correlations/{id}/calibrate | CALIBRATE | correlation |
| POST /api/v1/reports | CREATE | report |
| POST /api/v1/reports/{id}/cancel | CANCEL | report |
| POST /api/v1/reports/{id}/retry | RETRY | report |
| POST /api/v1/notifications/{id}/read | UPDATE | notification |
| POST /api/v1/data-sync/refresh | SYNC | data_sync |
| POST /api/v1/uploads/excel | CREATE | upload |

### Testing Requirements

| Test | Type |
|------|------|
| Write operation creates audit_log entry | integration |
| Audit log contains correct user_id, action, resource | integration |
| Audit log captures before/after values for UPDATE | integration |
| Read operations do NOT create audit log | integration |
| Audit log with null user_id for anonymous actions | integration |

---

## BE-012: Notification API

### Priority: P1 | Depends on: PM-005

### API Contracts

```python
# app/schemas/notification.py
class NotificationOut(BaseModel):
    id: int
    type: str                    # report_completed / report_failed / data_sync / system
    title: str
    content: str | None
    related_resource: str | None
    related_id: int | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None

# GET /api/v1/notifications?page=1&page_size=20&unread_only=false
# Response: {code: 0, data: {items: [...], total: 42, unread_count: 3}}

# POST /api/v1/notifications/{id}/read
# Response: {code: 0, message: "success"}

# POST /api/v1/notifications/read-all
# Response: {code: 0, message: "All marked as read"}
```

### Service Logic

```python
# app/services/notification_service.py
class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: int,
        type: str,
        title: str,
        content: str | None = None,
        related_resource: str | None = None,
        related_id: int | None = None,
    ):
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            related_resource=related_resource,
            related_id=related_id,
        )
        db.add(notif)
        await db.commit()

    @staticmethod
    async def get_notifications(
        db: AsyncSession, user_id: int, page: int = 1,
        page_size: int = 20, unread_only: bool = False,
    ):
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read == False)
        query = query.order_by(Notification.created_at.desc())

        total = await db.execute(select(func.count()).select_from(query.subquery()))
        total = total.scalar()
        unread_count = await db.execute(
            select(func.count()).where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        unread_count = unread_count.scalar()

        result = await db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "unread_count": unread_count,
        }
```

### Auto-creation on Report Complete

```python
# In report_tasks.py (after COMPLETED transition):
@celery_app.task(name="notification.create_report_notification")
def create_report_notification(report_id: int, event: str):
    """Chained task: creates notification after report completes/fails"""
    async with get_async_session() as db:
        report = await db.get(ReportTask, report_id)
        await NotificationService.create_notification(
            db=db,
            user_id=report.user_id,
            type=f"report_{event}",  # report_completed / report_failed
            title=f"报告{'生成完成' if event == 'completed' else '生成失败'}",
            content=f"{report.title or report.report_type} 报告已{'完成' if event == 'completed' else '失败'}",
            related_resource="report",
            related_id=report_id,
        )
```

### Testing Requirements

| Test | Type |
|------|------|
| List notifications: paginated, user-scoped | integration |
| List notifications: unread_only filter works | integration |
| List notifications: returns unread_count | integration |
| Mark read: updates is_read and read_at | integration |
| Mark read: 404 for non-existent | integration |
| Read all: marks all user's notifications as read | integration |
| Auto-create: report completion creates notification | integration |
| Auto-create: wrong user cannot see notification | security |

---

## BE-013: Data Freshness API

### Priority: P0 | Depends on: PM-012

### API Contracts

```python
# app/schemas/system.py
class DataFreshnessResponse(BaseModel):
    last_sync_time: datetime | None
    data_range: dict | None          # {"start": "2025-01", "end": "2025-12"}
    status: str                      # fresh / stale / error
    next_sync_at: datetime | None
    sync_history: list[SyncRecord] | None = None  # recent syncs

class SyncRecord(BaseModel):
    batch_id: str
    source: str
    total_rows: int
    valid_rows: int
    error_rows: int
    status: str
    started_at: datetime
    finished_at: datetime | None

# GET /api/v1/system/data-freshness
# Response:
# {
#   "code": 0,
#   "data": {
#     "last_sync_time": "2026-05-08T14:30:00Z",
#     "data_range": {"start": "2024-01", "end": "2026-04"},
#     "status": "fresh",
#     "next_sync_at": "2026-05-08T14:35:00Z",
#     "sync_history": [...]
#   }
# }

# POST /api/v1/data-sync/refresh
# Response: {code: 0, data: {message: "Sync triggered", batch_id: "..."}}
```

### Status Logic

```python
# app/services/freshness_service.py
from datetime import datetime, timedelta, timezone

FRESH_THRESHOLD_MINUTES = config.DATA_FRESHNESS_WARN_THRESHOLD  # default 30
STALE_THRESHOLD_MINUTES = config.DATA_FRESHNESS_ERROR_THRESHOLD # default 60

async def get_data_freshness(db: AsyncSession) -> DataFreshnessResponse:
    # Step 1: Get latest sync batch
    latest_sync = await db.execute(
        select(SyncBatch).order_by(SyncBatch.finished_at.desc()).limit(1)
    )
    latest_sync = latest_sync.scalar_one_or_none()

    if not latest_sync:
        return DataFreshnessResponse(status="error", last_sync_time=None, data_range=None)

    # Step 2: Determine status
    now = datetime.now(timezone.utc)
    elapsed = (now - latest_sync.finished_at).total_seconds() / 60

    if elapsed <= FRESH_THRESHOLD_MINUTES:
        status = "fresh"
    elif elapsed <= STALE_THRESHOLD_MINUTES:
        status = "stale"
    else:
        status = "error"

    # Step 3: Get data range from revenue_detail
    range_result = await db.execute(
        select(
            func.min(RevenueDetail.revenue_year).label("min_year"),
            func.max(RevenueDetail.revenue_year).label("max_year"),
        ).where(RevenueDetail.data_status == "active")
    )
    data_range_row = range_result.one()

    # Step 4: Get recent sync history
    history = await db.execute(
        select(SyncBatch).order_by(SyncBatch.finished_at.desc()).limit(5)
    )
    sync_history = [
        SyncRecord(
            batch_id=s.batch_id, source=s.source_type,
            total_rows=s.total_rows, valid_rows=s.valid_rows,
            error_rows=s.error_rows, status=s.status,
            started_at=s.started_at, finished_at=s.finished_at,
        )
        for s in history.scalars().all()
    ]

    return DataFreshnessResponse(
        last_sync_time=latest_sync.finished_at,
        data_range={"start": f"{data_range_row.min_year}-01", "end": f"{data_range_row.max_year}-12"},
        status=status,
        next_sync_at=latest_sync.finished_at + timedelta(minutes=5),
        sync_history=sync_history,
    )
```

### Caching

- Data freshness: Redis `data-freshness:latest`, TTL=60s (matches poll frequency)
- Invalidate on sync completion

### Testing Requirements

| Test | Type |
|------|------|
| No sync data → status=error | integration |
| Recent sync (<30min) → status=fresh | integration |
| Sync 30-60min ago → status=stale | integration |
| Sync >60min ago → status=error | integration |
| Data range reflects actual data | integration |
| Refresh triggers new sync | integration |
| Refresh cooldown (60s) enforced | integration |

---

## BE-014: Config Management MVP (Env Vars)

### Priority: P0 | Depends on: PM-010, AR-011

### File: app/config.py

```python
# app/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AI+BI 财务管报系统"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/ai_bi_finance"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_SECONDS: int = 86400

    # AI Service (Qwen)
    QWEN_API_KEY: str = ""        # MUST be set in .env, never hard-coded
    QWEN_MODEL: str = "qwen-max"
    QWEN_API_BASE: str = "https://ruijie.aiforce.cloud/api"

    # IMAP Email
    IMAP_HOST: str = ""
    IMAP_PORT: int = 993
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""       # App-specific password / OAuth2 token
    IMAP_POLL_INTERVAL: int = 300

    # Cache
    DASHBOARD_CACHE_TTL: int = 300     # seconds
    CACHE_PREFIX: str = "aibi:"

    # Data Freshness
    DATA_FRESHNESS_WARN_THRESHOLD: int = 30   # minutes
    DATA_FRESHNESS_ERROR_THRESHOLD: int = 60  # minutes

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

config = Settings()
```

### File: .env.example

```env
# ============================================
# AI+BI 财务管报系统 - Environment Configuration
# ============================================
# Copy this file to .env and fill in your values
# NEVER commit the actual .env file to git

# --- Application ---
DEBUG=false

# --- Database ---
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ai_bi_finance

# --- Redis ---
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# --- JWT ---
JWT_SECRET_KEY=<generate-a-random-64-char-hex-string>

# --- AI Service (Qwen) ---
QWEN_API_KEY=<your-qwen-api-key>
QWEN_MODEL=qwen-max
QWEN_API_BASE=https://ruijie.aiforce.cloud/api

# --- IMAP Email ---
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USER=finance_report@example.com
IMAP_PASSWORD=<app-specific-password>

# --- Cache ---
DASHBOARD_CACHE_TTL=300

# --- Data Freshness ---
DATA_FRESHNESS_WARN_THRESHOLD=30
DATA_FRESHNESS_ERROR_THRESHOLD=60

# --- File Upload ---
MAX_UPLOAD_SIZE_MB=10
```

### Security: API Key Protection

```python
# app/core/security_check.py
from app.config import config

def assert_api_keys_not_leaked():
    """Run at startup: verify API keys are not exposed to frontend"""
    # Check: no API key in templates, static files, or frontend code
    # (Implemented as a CI check, not runtime)
    pass

# In any API response: NEVER include QWEN_API_KEY in response data
# In any error message: mask API keys if accidentally included
```

### Testing Requirements

| Test | Type |
|------|------|
| Config loads from env vars | unit |
| Missing required env var → startup error | unit |
| API key not leaked in any response | security |
| .env.example contains all required vars | unit |
| Config defaults work when env not set | unit |

---

## BE-015: P2 APIs — Data Source/Quality/Upload (Phase 3)

### Priority: P2 | Depends on: AR-003

### API Contracts

```python
# app/schemas/datasource.py

# GET /api/v1/data-sources — list all data sources
# POST /api/v1/data-sources — create new data source
class DataSourceCreate(BaseModel):
    name: str
    source_type: str           # email_imap / excel_upload / manual
    config: dict               # connection config
    enabled: bool = True

# PUT /api/v1/data-sources/{id} — update
# DELETE /api/v1/data-sources/{id} — delete (soft)

# GET /api/v1/data-quality/summary
class DataQualitySummary(BaseModel):
    total_records: int
    valid_records: int
    error_records: int
    duplicate_records: int
    null_field_count: int
    last_check_time: datetime
    quality_score: float        # 0~100
    by_error_type: list[ErrorTypeCount]

# GET /api/v1/data-quality/errors?batch_id=&error_type=&page=1&page_size=20
class DataQualityError(BaseModel):
    id: int
    batch_id: str
    source_file: str
    error_type: str
    row_data: dict
    error_msg: str
    created_at: datetime

# POST /api/v1/uploads/excel
# Multipart form: file (max 10MB), sheet_name (optional)
class UploadResponse(BaseModel):
    batch_id: str
    source_file: str
    total_rows: int
    valid_rows: int
    error_rows: int
    sync_mode: str
    status: str
```

### Service Logic

```python
# app/services/upload_service.py
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

async def upload_excel(file: UploadFile, db: AsyncSession, user_id: int):
    # 1. Validate file size
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise AppException(ErrorCode.FILE_TOO_LARGE, f"File exceeds {MAX_UPLOAD_SIZE//1024//1024}MB limit")

    # 2. Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Only .xlsx and .xls files are accepted")

    # 3. Parse and clean
    df = parse_excel(contents)
    df = transform_dataframe(df)
    cleaned_df, error_df = clean_data(df)

    # 4. Create batch
    batch_id = f"upload-{uuid.uuid4().hex[:12]}"
    batch = SyncBatch(batch_id=batch_id, source_type="excel_upload",
                      source_file=file.filename, total_rows=len(df),
                      valid_rows=len(cleaned_df), error_rows=len(error_df),
                      sync_mode="incremental", status="processing")
    db.add(batch)

    # 5. Upsert data
    await sync_orchestrator.upsert(cleaned_df, batch_id)

    # 6. Record errors
    for _, row in error_df.iterrows():
        error_log = DataErrorLog(batch_id=batch_id, source_file=file.filename,
                                 error_type=row.get("error_type", "unknown"),
                                 row_data=row.to_dict(), error_msg="")
        db.add(error_log)

    # 7. Finalize batch
    batch.status = "success"
    batch.finished_at = func.now()
    await db.commit()

    # 8. Invalidate caches
    await cache.invalidate_on_sync()

    return UploadResponse(batch_id=batch_id, source_file=file.filename, ...)
```

### File Structure

| File | Action |
|------|--------|
| `app/schemas/datasource.py` | NEW: Data source schemas |
| `app/api/v1/datasources.py` | NEW: Data source CRUD routes |
| `app/api/v1/uploads.py` | NEW: Upload routes |
| `app/services/upload_service.py` | NEW: Upload logic |

### Testing Requirements

| Test | Type |
|------|------|
| List data sources: admin only | integration |
| Create data source: validates config | integration |
| Delete data source: soft delete | integration |
| Quality summary: correct counts | integration |
| Quality errors: filtered by batch_id | integration |
| Quality errors: paginated | integration |
| Upload: valid Excel processes correctly | integration |
| Upload: >10MB rejected | integration |
| Upload: non-Excel rejected | integration |
| Upload: creates error_log for bad rows | integration |

---

## BE-016: Unified Error Response Format

### Priority: P0 | No Deps

### File Structure

| File | Action |
|------|--------|
| `app/core/error_codes.py` | NEW: Error code registry |
| `app/core/exceptions.py` | NEW: Global exception handlers |
| `app/core/logging.py` | MODIFY: Add trace ID |

### Implementation (see Global Conventions at top of this doc)

All exception handlers are centralized in `app/core/exceptions.py`. Every API route returns `APIResponse` via the FastAPI `response_model` or the `return APIResponse(...)` pattern.

### Response Examples

```python
# Success:
# { "code": 0, "message": "success", "data": {...}, "trace_id": "a1b2c3d4" }

# Validation error:
# { "code": 4100, "message": "Validation error", "data": {"field": "year", "detail": "Field required"}, "trace_id": "e5f6g7h8" }

# Auth error:
# { "code": 4001, "message": "Unauthorized", "data": null, "trace_id": "i9j0k1l2" }

# Not found:
# { "code": 4200, "message": "Resource not found", "data": null, "trace_id": "m3n4o5p6" }

# Server error (production — no stack trace):
# { "code": 5000, "message": "Internal server error", "data": null, "trace_id": "q7r8s9t0" }
```

### Middleware for Trace ID

```python
# app/main.py
from app.core.logging import set_trace_id, get_trace_id
import uuid

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", uuid.uuid4().hex)
    set_trace_id(trace_id)
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response
```

### Validation Error Interceptor

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": e["loc"][-1], "detail": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=APIResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message="Validation error",
            data=errors,
            trace_id=get_trace_id(),
        ).model_dump(),
    )
```

### Testing Requirements

| Test | Type |
|------|------|
| All endpoints return {code, message, data} format | contract |
| Validation errors return 4100 code | integration |
| Auth errors return 4001 code | integration |
| Not found returns 4200 code | integration |
| Server errors do not leak stack trace | security |
| Trace ID present in all responses | integration |
| Trace ID flows from request header | integration |

---

## Dependency Graph (Backend Tasks)

```
BE-001 (P0 API) ──────────────────→ AR-001
BE-002 (Report Task) ─────────────→ AR-010, PM-006~009 → BE-010 (auth)
BE-003 (Prediction) ──────────────→ AR-002 → queries BE-008 repo
BE-004 (Transaction Analysis) ────→ AR-002 → BE-008 (shared DAO)
BE-005 (Deprecated Cleanup) ──────→ AR-004 → verify vs BE-006, BE-007
BE-006 (Drilldown Refactor) ──────→ AR-008 → BE-008 (DAO), BE-010 (auth)
BE-007 (Correlation System) ──────→ AR-009 → BE-010, BE-009 (tables)
BE-008 (Dual Data Path) ──────────→ AR-007, PM-011 → core infrastructure
BE-009 (DB Migrations) ───────────→ AR-005 → prerequisite for BE-002,003,007,010,011,012
BE-010 (RBAC) ────────────────────→ AR-013 → prerequisite for all auth-requiring endpoints
BE-011 (Audit Log) ───────────────→ AR-013 → BE-010 (user ref), BE-009 (table)
BE-012 (Notification API) ────────→ PM-005 → BE-010, BE-009
BE-013 (Data Freshness) ──────────→ PM-012 → BE-009 (sync_batch table exists)
BE-014 (Config MVP) ──────────────→ PM-010, AR-011 → no deps, foundational
BE-015 (P2 Data/Quality/Upload) ──→ AR-003 → BE-008 (DAO), BE-010
BE-016 (Error Format) ────────────→ no deps → foundational, apply to all routes
```

### Build Order Recommendation

```
Phase 1A — Foundation (no dependencies):
  BE-014 (Config) → BE-016 (Error format) → BE-009 (DB migrations) → BE-008 (Dual path + caching) → BE-010 (RBAC)

Phase 1B — Core P0 API + Data (depends on 1A):
  BE-001 → BE-006 → BE-007 → BE-011

Phase 1C — Async + Advanced Features (depends on 1B):
  BE-002 → BE-003 → BE-012 → BE-013

Phase 1D — Cleanup:
  BE-005

Phase 2 — P1 APIs:
  BE-004

Phase 3 — P2 APIs:
  BE-015
```
