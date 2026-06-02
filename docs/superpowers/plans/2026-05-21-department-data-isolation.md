# 全局按事业部权限过滤数据 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users from different business divisions (事业部) should only see their own division's financial data. Admin users bypass this restriction.

**Architecture:** Add `department` field to the User model, embed it in the JWT token at login time, then inject a `FinancialData.entity == user.department` WHERE clause into every data-querying endpoint. Backend-enforced — non-admin users cannot override their department filter even if they send a different `department` query parameter.

**Tech Stack:** FastAPI + SQLAlchemy async + JWT (python-jose) + Alembic + Vue 3 + Pinia

---

## File Structure

### Files to Create:
| File | Responsibility |
|------|---------------|
| `backend/migrations/versions/xxxx_add_user_department.py` | Alembic migration: add `department` column to `users` table |
| `docs/superpowers/plans/2026-05-21-department-data-isolation.md` | This plan |

### Files to Modify:
| File | Responsibility |
|------|---------------|
| `backend/app/models/v4.py` | Add `department` column to User model |
| `backend/app/schemas/auth.py` | Add `department` to UserRead/UserCreate/UserUpdate |
| `backend/app/core/security.py` | Add `department` to TokenPayload; add `get_data_scope_filter()` |
| `backend/app/api/auth.py` | Include department in login JWT + response; include in /auth/me |
| `backend/app/api/dashboard.py` | Inject department filter into 4 query paths |
| `backend/app/api/metrics.py` | Override department param for non-admin users |
| `backend/app/api/drilldowns.py` | Add `entity == user.department` to all 7 endpoints |
| `backend/app/api/filters.py` | Scoped filter-options to user's department |
| `backend/app/api/transactions.py` | Pass user context to transaction_service |
| `backend/app/services/transaction_service.py` | Accept + apply department filter |
| `backend/app/api/ai.py` | Add department filter to ai_analyze |
| `backend/app/api/query.py` | Add department filter to generic query |
| `backend/app/services/correlation.py` | Add department filter to `_fetch_metric_values` |
| `backend/app/tests/conftest.py` | Add department to seeded users; add non-admin fixtures |
| `backend/tests/test_api_dashboard.py` | Test department filtering |
| `frontend/src/store/auth.ts` | Add `department` and `isDeptRestricted` |
| `frontend/src/views/AdminPage.vue` | Add department field to user form |
| `frontend/src/views/CoreMetricsPage.vue` | Hide department selector for restricted users |
| `frontend/src/views/DepartmentAnalysisPage.vue` | Hide department selector for restricted users |
| `frontend/src/views/TrendAnalysisPage.vue` | Hide department selector for restricted users |
| `frontend/src/views/TransactionsPage.vue` | Hide entity selector for restricted users |

---

### Task 1: Add department column to User model

**Files:**
- Modify: `backend/app/models/v4.py`
- Test: N/A (ORM model change)

- [ ] **Step 1: Add `department` column to User model**

Replace the User class in `backend/app/models/v4.py`:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(256), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="users")
```

The single new line is `department: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)`.

---

### Task 2: Create Alembic migration

**Files:**
- Create: `backend/migrations/versions/xxxx_add_user_department.py`
- Test: N/A

- [ ] **Step 1: Generate empty migration**

Run: `cd backend && alembic revision -m "add_user_department"`

Expected output: `Generating migrations/versions/xxxx_add_user_department.py ... done`

- [ ] **Step 2: Write migration up/down**

Replace contents of the generated file:

```python
"""add user.department column

Revision ID: xxxx
Revises: a5a93b790558
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "xxxx"
down_revision = "a5a93b790558"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("department", sa.String(128), nullable=True))
    op.create_index("ix_users_department", "users", ["department"])


def downgrade() -> None:
    op.drop_index("ix_users_department", table_name="users")
    op.drop_column("users", "department")
```

- [ ] **Step 3: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade xxxx -> xxxx_add_user_department, "add user.department column"`
Verify: `alembic heads` shows this revision as current.

---

### Task 3: Update auth schemas

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Test: N/A (Pydantic model)

- [ ] **Step 1: Add department to UserRead**

```python
class UserRead(BaseModel):
    id: int
    username: str
    email: str | None
    role_name: str
    department: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Add department to UserCreate**

```python
class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str | None = None
    password: str = Field(min_length=6, max_length=128)
    role_id: int = 3
    department: str | None = None
```

- [ ] **Step 3: Add department to UserUpdate**

```python
class UserUpdate(BaseModel):
    email: str | None = None
    is_active: bool | None = None
    role_id: int | None = None
    department: str | None = None
```

---

### Task 4: Add department to JWT security utils

**Files:**
- Modify: `backend/app/core/security.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write test for get_data_scope_filter**

Add to `backend/tests/test_auth.py`:

```python
from app.core.security import get_data_scope_filter, TokenPayload
from app.models.core import FinancialData
from sqlalchemy import select


class TestDataScopeFilter:

    def test_admin_returns_true(self):
        admin = TokenPayload(sub="1", role="admin")
        result = get_data_scope_filter(admin)
        assert result is True

    def test_viewer_with_department_returns_filter(self):
        viewer = TokenPayload(sub="2", role="viewer", department="CBG")
        result = get_data_scope_filter(viewer)
        assert result is not True
        # Should be a SQLAlchemy BinaryExpression comparing entity == "CBG"
        from sqlalchemy.sql.elements import BinaryExpression
        assert isinstance(result, BinaryExpression)
        assert str(result.compile(compile_kwargs={"literal_binds": True})) == "financial_data.entity = 'CBG'"

    def test_viewer_without_department_returns_true(self):
        viewer = TokenPayload(sub="3", role="viewer", department=None)
        result = get_data_scope_filter(viewer)
        assert result is True
```

Run: `cd backend && python -m pytest tests/test_auth.py::TestDataScopeFilter -v`
Expected: FAIL — `get_data_scope_filter` not defined

- [ ] **Step 2: Add department to TokenPayload + implement get_data_scope_filter**

In `backend/app/core/security.py`, modify TokenPayload:

```python
class TokenPayload(BaseModel):
    sub: str
    exp: datetime | None = None
    role: str = "viewer"
    department: str | None = None
```

Add at end of file (before `apply_role_filter` if it exists, or after all classes):

```python
def get_data_scope_filter(user: TokenPayload, model=None):
    """Return a SQLAlchemy WHERE clause filtering by user's department.

    Admin users (and users without a department assignment) get no filter (True).
    Non-admin users are restricted to rows where ``model.entity == user.department``.
    """
    if user.role == "admin" or not user.department:
        return True
    if model is None:
        from app.models.core import FinancialData
        model = FinancialData
    return model.entity == user.department
```

- [ ] **Step 3: Re-run tests**

Run: `cd backend && python -m pytest tests/test_auth.py::TestDataScopeFilter -v`
Expected: PASS

---

### Task 5: Update auth login/me endpoints

**Files:**
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_api_auth.py`

- [ ] **Step 1: Write test for login returning department + me returning department**

Add to `backend/tests/test_api_auth.py` inside `TestAuthAPI`:

```python
async def test_login_returns_department(self, seeded_db: AsyncSession, client: AsyncClient):
    # seeded_db creates test_admin with no department (None)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_admin", "password": "testpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "department" in data["user"]
    # department is None for test_admin

async def test_me_returns_department(self, admin_client: AsyncClient):
    resp = await admin_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "department" in data
```

Run: `cd backend && python -m pytest tests/test_api_auth.py::TestAuthAPI::test_login_returns_department -v`
Expected: FAIL — department not in response

- [ ] **Step 2: Add department to login JWT + response**

In `backend/app/api/auth.py`, modify the login endpoint:

```python
token = create_access_token(
    subject=str(user.id),
    extra={"role": user.role.name if user.role else "viewer", "department": user.department},
)
return APIResponse.success(data={
    "access_token": token,
    "token_type": "bearer",
    "user": {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.name if user.role else "viewer",
        "department": user.department,
        "is_active": user.is_active,
    },
})
```

- [ ] **Step 3: Add department to /auth/me response**

Modify the `get_me` endpoint — add `department` to the response:

```python
data = UserRead(
    id=user.id,
    username=user.username,
    email=user.email,
    role_name=user.role.name if user.role else "viewer",
    department=user.department,
    is_active=user.is_active,
)
```

- [ ] **Step 4: Update list_users endpoint to include department**

```python
items = [
    UserRead(
        id=u.id,
        username=u.username,
        email=u.email,
        role_name=u.role.name if u.role else "viewer",
        department=u.department,
        is_active=u.is_active,
    ).model_dump()
    for u in users
]
```

- [ ] **Step 5: Update create_user to accept department**

Modify `create_user`:

```python
user = User(
    username=body.username,
    email=body.email,
    password_hash=hash_password(body.password),
    role_id=body.role_id,
    department=body.department,
)
```

- [ ] **Step 6: Re-run tests**

Run: `cd backend && python -m pytest tests/test_api_auth.py -v`
Expected: Both new tests PASS, all existing tests PASS

---

### Task 6: Update seeded_db fixture with department + non-admin fixtures

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add department to existing seeded user**

In `conftest.py`, modify the `seeded_db` fixture user creation:

```python
user = User(
    username="test_admin",
    email="admin@test.com",
    password_hash=hash_password("testpass123"),
    role_id=1,  # admin
    department=None,  # admin has no department restriction
)
db_session.add(user)
```

- [ ] **Step 2: Add non-admin seeded user fixtures**

After the `admin_client` fixture, add:

```python
@pytest_asyncio.fixture(scope="function")
async def analyst_cbg(seeded_db: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """seeded_db + an analyst user with department=CBG."""
    user = User(
        username="analyst_cbg",
        email="analyst_cbg@test.com",
        password_hash=hash_password("testpass123"),
        role_id=2,  # analyst
        department="CBG",
    )
    seeded_db.add(user)
    await seeded_db.flush()
    yield seeded_db


@pytest_asyncio.fixture(scope="function")
async def analyst_cbg_client(analyst_cbg: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with analyst_cbg JWT."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: analyst_cbg
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"username": "analyst_cbg", "password": "testpass123"},
            )
            token = resp.json()["data"]["access_token"]
            ac.headers["Authorization"] = f"Bearer {token}"
            yield ac
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def analyst_ebg_client(analyst_cbg: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with an EBG-department analyst JWT."""
    # Add EBG user
    user = User(
        username="analyst_ebg",
        email="analyst_ebg@test.com",
        password_hash=hash_password("testpass123"),
        role_id=2,
        department="EBG",
    )
    analyst_cbg.add(user)
    await analyst_cbg.flush()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: analyst_cbg
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"username": "analyst_ebg", "password": "testpass123"},
            )
            token = resp.json()["data"]["access_token"]
            ac.headers["Authorization"] = f"Bearer {token}"
            yield ac
    finally:
        app.dependency_overrides.clear()
```

---

### Task 7: Inject department filter into Dashboard BFF

**Files:**
- Modify: `backend/app/api/dashboard.py`
- Test: `backend/tests/test_api_dashboard.py`

- [ ] **Step 1: Write test for department-scoped dashboard**

Add to `backend/tests/test_api_dashboard.py`:

```python
class TestDashboardDeptFilter:

    async def _seed_financial_data(self, db_session: AsyncSession):
        """Seed sample FinancialData for two departments."""
        from app.models.core import FinancialData
        for entity in ["CBG", "EBG"]:
            for metric in ["revenue", "cost"]:
                db_session.add(FinancialData(
                    metric_name=metric,
                    metric_value=1000000.0 if metric == "revenue" else 600000.0,
                    period="2026-01",
                    entity=entity,
                ))
        await db_session.flush()

    async def test_cbg_user_sees_only_cbg_data(self, analyst_cbg, client: AsyncClient):
        db = analyst_cbg
        await self._seed_financial_data(db)
        # Manually set analyst_cbg_client headers
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"username": "analyst_cbg", "password": "testpass123"},
            )
            token = resp.json()["data"]["access_token"]
            ac.headers["Authorization"] = f"Bearer {token}"
            resp2 = await ac.post("/api/v1/dashboard/bff", json={"device_type": "web"})
            assert resp2.status_code == 200
            data = resp2.json()["data"]
            # CBG user should see CBG data in department breakdown
            depts = data.get("department_breakdown", [])
            for d in depts:
                assert d["dimension_value"] == "CBG"
```

Run: `cd backend && python -m pytest tests/test_api_dashboard.py::TestDashboardDeptFilter -v`
Expected: FAIL — department data not filtered

- [ ] **Step 2: Modify _build_kpis to accept user and apply department**

In `backend/app/api/dashboard.py`, modify `_build_kpis` signature to accept `user: TokenPayload`:

```python
async def _build_kpis(
    db: AsyncSession,
    user: TokenPayload | None = None,
    period_compare_type: str | None = None,
    ...
) -> dict:
```

Add after `compare_mode = ...`:
```python
    # Enforce department scope for non-admin users
    from app.core.security import get_data_scope_filter
    effective_dept = department
    if user and user.role != "admin" and user.department:
        effective_dept = user.department
```

Replace `department=department` with `department=effective_dept` in the `get_core_metrics` call.

Similarly modify `_build_dimension_breakdowns` to accept `user` and compute `effective_dept`.

- [ ] **Step 3: Pass user to _build_kpis and _build_dimension_breakdowns**

In `_build_dashboard_response`, add `user` parameter and pass through:

```python
async def _build_dashboard_response(body, db: AsyncSession, cache_key: str, user: TokenPayload) -> APIResponse:
    ...
    dept_items, prod_items = await _build_dimension_breakdowns(
        db, user=user, department=body.department, ...
    )
    ...
    kpis = await _build_kpis(db, user=user, department=body.department, ...)
```

- [ ] **Step 4: Add department filter to direct FinancialData queries**

In `_build_dashboard_response`, the direct chart data query (lines 220-235) needs the filter:

```python
    # Apply department scope for non-admin users
    from app.core.security import get_data_scope_filter
    scope_filter = get_data_scope_filter(user, FinancialData)
    if scope_filter is not True:
        stmt = stmt.where(scope_filter)
```

Similarly in `_periods` function, add the department filter.

- [ ] **Step 5: Pass user from route handler**

Modify the `dashboard_bff` endpoint:

```python
async def dashboard_bff(
    body: DashboardBFFRequest,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    ...
    cache_key = ...
    ...
    try:
        return await _build_dashboard_response(body, db, cache_key, user)
    except Exception:
        raise
```

- [ ] **Step 6: Re-run tests**

Run: `cd backend && python -m pytest tests/test_api_dashboard.py -v`
Expected: Tests pass

---

### Task 8: Inject department filter into Core Metrics API

**Files:**
- Modify: `backend/app/api/metrics.py`
- Test: `backend/tests/test_api_dashboard.py`

- [ ] **Step 1: Read metrics.py to find get_core_metrics endpoint**

Read `backend/app/api/metrics.py` to find the endpoint signature and how it passes `department` to `MetricsService.get_core_metrics`.

- [ ] **Step 2: Override department param for non-admin users**

After reading the endpoint, modify it to override `department` for non-admin users:

```python
@router.get("/core", response_model=APIResponse)
async def get_core_metrics(
    ...
    user: TokenPayload = Depends(get_current_user),
    ...
) -> APIResponse:
    # Enforce department scope
    effective_department = department
    if user.role != "admin" and user.department:
        effective_department = user.department
    ...
    result = await MetricsService.get_core_metrics(
        db=db,
        department=effective_department,
        ...
    )
```

---

### Task 9: Inject department filter into drilldown endpoints

**Files:**
- Modify: `backend/app/api/drilldowns.py`

- [ ] **Step 1: Create reusable helper for drilldown endpoints**

At the top of `drilldowns.py`, after imports:

```python
from app.core.security import get_data_scope_filter
```

- [ ] **Step 2: Add user department filter to each drilldown endpoint**

For `drilldown_summary`:
```python
async def drilldown_summary(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_optional_user),
) -> APIResponse:
    scope_filter = get_data_scope_filter(user, FinancialData)
    stmt = select(...).group_by(...)
    if scope_filter is not True:
        stmt = stmt.where(scope_filter)
```

Apply the same pattern to ALL 7 drilldown endpoints. Each endpoint that queries `FinancialData` needs:

1. Change `_user=Depends(get_optional_user)` to `user: TokenPayload | None = Depends(get_optional_user)` 
2. Add `scope_filter = get_data_scope_filter(user, FinancialData)`
3. For each `.where()` clause, add scope_filter if not True

For endpoints using raw SQL (e.g., `drilldown_products_by_dept` that uses `text()` SQL), add the department filter as an additional condition:
```python
if user and user.role != "admin" and user.department:
    conditions.append("entity = :department")
    params["department"] = user.department
```

---

### Task 10: Inject department filter into filter-options endpoint

**Files:**
- Modify: `backend/app/api/filters.py`

- [ ] **Step 1: Scope filter-options to user's department**

In `get_filter_options`, the user is already injected. For entity/department dimension queries, add the scope filter:

For direct column query (entity):
```python
if dimension in col_map:
    col = col_map[dimension]
    stmt = select(col).distinct().order_by(col)
    # Apply scope filter for non-admin
    from app.core.security import get_data_scope_filter
    scope_filter = get_data_scope_filter(user, FinancialData)
    if scope_filter is not True:
        stmt = stmt.where(scope_filter)
    if prefix:
        stmt = stmt.where(col.like(f"{prefix}%"))
```

For tag-based department query, add the entity filter to the raw SQL:
```python
for key in keys:
    sql = text(
        f"SELECT DISTINCT tags->>'{key}' FROM financial_data "
        f"WHERE tags IS NOT NULL AND tags->>'{key}' IS NOT NULL"
    )
    if user and user.role != "admin" and user.department:
        sql = text(
            f"SELECT DISTINCT tags->>'{key}' FROM financial_data "
            f"WHERE tags IS NOT NULL AND tags->>'{key}' IS NOT NULL "
            f"AND entity = :dept"
        )
    result = await db.execute(sql, {"dept": user.department} if (user and user.role != "admin" and user.department) else {})
```

---

### Task 11: Inject department filter into transactions

**Files:**
- Modify: `backend/app/api/transactions.py`
- Modify: `backend/app/services/transaction_service.py`

- [ ] **Step 1: Read transaction_service.py to find all query methods**

Read `backend/app/services/transaction_service.py` to understand all methods and their signatures.

- [ ] **Step 2: Add department parameter to transaction service methods**

For each method in transaction_service that queries FinancialData, add a `department: str | None = None` parameter and apply:

```python
if department:
    stmt = stmt.where(FinancialData.entity == department)
```

- [ ] **Step 3: Pass user department from API layer**

In `transactions.py`, for each endpoint, inject the user's department:

```python
async def get_contracts(
    ...
    user: TokenPayload = Depends(get_current_user),
    ...
) -> APIResponse:
    effective_entity = entity
    if user.role != "admin" and user.department:
        effective_entity = user.department
    items, total = await transaction_service.get_contracts(
        db, period, effective_entity, page, page_size
    )
```

---

### Task 12: Inject department filter into AI/Query/Correlation

**Files:**
- Modify: `backend/app/api/ai.py`
- Modify: `backend/app/api/query.py`
- Modify: `backend/app/services/correlation.py`

- [ ] **Step 1: Add department filter to ai.py `ai_analyze`**

In `backend/app/api/ai.py`, the `ai_analyze` function queries FinancialData at lines 112-121. Add:

```python
curr_stmt = select(
    FinancialData.metric_name,
    FinancialData.entity,
    func.sum(FinancialData.metric_value).label("value"),
).where(
    FinancialData.period == period,
    FinancialData.metric_name == metric,
    FinancialData.entity.isnot(None),
    FinancialData.entity != "",
)
# Apply department scope
if _user and _user.role != "admin" and _user.department:
    curr_stmt = curr_stmt.where(FinancialData.entity == _user.department)
    prev_stmt = prev_stmt.where(FinancialData.entity == _user.department)
```

- [ ] **Step 2: Add department filter to query.py**

Read and modify `backend/app/api/query.py` similarly.

- [ ] **Step 3: Add department filter to correlation.py**

Read and modify `backend/app/services/correlation.py` — `_fetch_metric_values` method.

---

### Task 13: Frontend — Auth store

**Files:**
- Modify: `frontend/src/store/auth.ts`

- [ ] **Step 1: Add department and isDeptRestricted**

```typescript
const department = computed(() => user.value?.department);
const isDeptRestricted = computed(() => !!user.value?.department && user.value?.role !== 'admin');

return { user, token, isLoggedIn, role, isAdmin, isAnalyst, isViewer, department, isDeptRestricted, login, fetchUser, logout, restoreFromStorage };
```

---

### Task 14: Frontend — AdminPage user management

**Files:**
- Modify: `frontend/src/views/AdminPage.vue`

- [ ] **Step 1: Add department field to user create/edit form**

In the admin page's user management tab, add department field:

```html
<a-form-item label="事业部" name="department">
  <a-input v-model:value="formState.department" placeholder="例如: CBG" />
</a-form-item>
```

Include `department` in the create/update API payload.

- [ ] **Step 2: Add department column to user table**

```html
<a-table-column title="事业部" data-index="department" key="department" />
```

---

### Task 15: Frontend — Hide department selectors for restricted users

**Files:**
- Modify: `frontend/src/views/CoreMetricsPage.vue`
- Modify: `frontend/src/views/DepartmentAnalysisPage.vue`
- Modify: `frontend/src/views/TrendAnalysisPage.vue`
- Modify: `frontend/src/views/TransactionsPage.vue`

- [ ] **Step 1: Add auth store import and conditional rendering**

Pattern for each view — import store, then wrap department selector:

```ts
import { useAuthStore } from '@/store/auth';
const authStore = useAuthStore();
```

In template:

```html
<a-select
  v-if="!authStore.isDeptRestricted"
  v-model:value="selectedDept"
  ...
/>
<a-tag v-else color="blue">{{ authStore.department }}</a-tag>
```

This shows the department tag for restricted users (so they know which department they're viewing) and hides the selector.

---

## Verification

1. **Unit tests:**
   - `cd backend && python -m pytest tests/test_auth.py::TestDataScopeFilter -v` — data scope filter logic
   - `cd backend && python -m pytest tests/test_api_auth.py -v` — login/me department fields

2. **Integration tests:**
   - `cd backend && python -m pytest tests/test_api_dashboard.py -v` — department-scoped dashboard
   - `cd backend && python -m pytest tests/ -v` — full test suite

3. **Manual verification:**
   - Login as admin → see all departments, selector enabled
   - Login as analyst with department=CBG → only CBG data, selector hidden, shows "CBG" tag
   - Login as analyst with department=EBG → only EBG data
   - Try accessing `/api/v1/metrics/core?department=EBG` with CBG token → still returns CBG data