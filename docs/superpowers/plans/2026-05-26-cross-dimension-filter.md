# Cross-Dimension Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the user selects a value in the Product Line (5th box) or Market Line (4th box) filter, add a cross-dimension selector that shows how another dimension (department/product/customer) breaks down within the selected filter. Charts below update accordingly.

**Architecture:** A new backend endpoint `/dashboard/cross-analysis` queries `agg_order_summary` (which has `dim_dept`, `dim_product`, and — after ETL extension — `dim_customer`) grouped by the chosen cross-dimension. The frontend adds a conditional cross-dimension type selector in the filter bar and a bar chart component that fetches from the new endpoint.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Vue 3, Ant Design Vue, ECharts

---

## Scenario Walkthrough

1. User selects Market Line = CBG → cross-dimension type selector appears with options: Product, Customer
2. User picks "Customer" → bar chart shows top customers within CBG by revenue/cost/gross_profit
3. User additionally selects Product Line = X → cross-dimension options narrow to: Customer only (department and product already filtered)
4. User switches cross-dimension type to "Product" (when only Market Line selected) → bar chart shows product lines within CBG

## File Structure

| File | Role |
|------|------|
| `backend/scripts/aggregate_metrics.py` | ETL — add `dim_customer` column to `agg_order_summary` |
| `backend/app/models/core.py` | SQLAlchemy model — add `dim_customer` field |
| `backend/app/schemas/query.py` | Request/response schemas for cross-analysis |
| `backend/app/services/cross_analysis.py` | **New** — cross-dimension query service |
| `backend/app/api/dashboard.py` | New `/dashboard/cross-analysis` endpoint |
| `backend/app/api/filters.py` | Extend filter-options for cross-dimension scoping |
| `frontend/src/api/dashboard.ts` | API client functions |
| `frontend/src/api/filters.ts` | Extend filter-options call |
| `frontend/src/views/DashboardPage.vue` | Add cross-dimension selectors to filter bar |
| `frontend/src/components/dashboard/CrossAnalysisChart.vue` | **New** — bar chart component |
| `frontend/src/components/dashboard/FinancialOverview.vue` | Accept cross-dimension props, render chart |

---

### Task 1: Extend `agg_order_summary` with `dim_customer`

**Files:**
- Modify: `backend/scripts/aggregate_metrics.py:41-53` (DDL), `139-156` (AGG_ORDER SQL)
- Modify: `backend/app/models/core.py:348-363` (AggOrderSummary model)

- [ ] **Step 1: ALTER TABLE via migration SQL**

Run directly against the database (or add to `aggregate_metrics.py` DDL section):

```sql
ALTER TABLE agg_order_summary
ADD COLUMN IF NOT EXISTS dim_customer VARCHAR(256);
```

- [ ] **Step 2: Update DDL in `aggregate_metrics.py`**

In the DDL string at line 41-52, add `dim_customer` to the CREATE TABLE:

```python
# In DDL string, after line 45 (dim_product VARCHAR(128)):
dim_customer VARCHAR(256),
```

- [ ] **Step 3: Update AGG_ORDER ETL SQL**

Replace lines 139-156 of `aggregate_metrics.py`:

```python
AGG_ORDER = """
INSERT INTO agg_order_summary (period, bgbu, order_id, dim_dept, dim_product, dim_customer, revenue, cost, gross_profit)
SELECT period, bgbu, COALESCE(order_id, contract_no),
    MAX(sales_department), MAX(product_bgbu), MAX(superior_name),
    COALESCE(SUM(revenue_amount), 0), COALESCE(SUM(cost_amount), 0),
    COALESCE(SUM(gross_profit_amount), 0)
FROM income_margin_detail
WHERE bgbu IS NOT NULL AND COALESCE(order_id, contract_no) IS NOT NULL
GROUP BY period, bgbu, COALESCE(order_id, contract_no)
UNION ALL
SELECT period, 'ALL', COALESCE(order_id, contract_no),
    MAX(sales_department), MAX(product_bgbu), MAX(superior_name),
    COALESCE(SUM(revenue_amount), 0), COALESCE(SUM(cost_amount), 0),
    COALESCE(SUM(gross_profit_amount), 0)
FROM income_margin_detail
WHERE COALESCE(order_id, contract_no) IS NOT NULL
GROUP BY period, COALESCE(order_id, contract_no)
"""
```

- [ ] **Step 4: Update SQLAlchemy model**

In `backend/app/models/core.py`, add to `AggOrderSummary` class (after `dim_product`):

```python
dim_customer: Mapped[str | None] = mapped_column(String(256), nullable=True)
```

- [ ] **Step 5: Run ETL to populate new column**

```bash
cd D:/workspace/caiwu04/backend
python scripts/aggregate_metrics.py
```

- [ ] **Step 6: Verify data**

```sql
SELECT COUNT(*), COUNT(dim_customer) FROM agg_order_summary;
```

Expected: `dim_customer` populated for most/all rows.

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/aggregate_metrics.py backend/app/models/core.py
git commit -m "feat: add dim_customer to agg_order_summary for cross-dimension analysis"
```

---

### Task 2: Backend — Cross-Analysis Schemas

**Files:**
- Modify: `backend/app/schemas/query.py`

- [ ] **Step 1: Add request/response models**

Append to `backend/app/schemas/query.py`:

```python
# ── Cross-Dimension Analysis ──────────────────────────────────

class CrossAnalysisRequest(BaseModel):
    cross_dimension: str  # department | product | customer
    department: str | None = None
    product: str | None = None
    period: str | None = None
    period_start: str | None = None
    period_end: str | None = None


class CrossAnalysisItem(BaseModel):
    dimension_value: str
    revenue: float = 0
    cost: float = 0
    gross_profit: float = 0
    order_count: int = 0


class CrossAnalysisResponse(BaseModel):
    cross_dimension: str
    items: list[CrossAnalysisItem]
    total: int
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/query.py
git commit -m "feat: add cross-analysis request/response schemas"
```

---

### Task 3: Backend — Cross-Analysis Service

**Files:**
- Create: `backend/app/services/cross_analysis.py`

- [ ] **Step 1: Create the service**

```python
"""Cross-dimension analysis service — queries agg_order_summary."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import AggOrderSummary

# Maps cross_dimension param → agg_order_summary column
_CROSS_DIM_COL = {
    "department": AggOrderSummary.dim_dept,
    "product": AggOrderSummary.dim_product,
    "customer": AggOrderSummary.dim_customer,
}


async def get_cross_analysis(
    db: AsyncSession,
    cross_dimension: str,
    department: str | None = None,
    product: str | None = None,
    period: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    bgbu_filter: str = "ALL",
    limit: int = 20,
) -> list[dict]:
    """Return top-N dimension values with revenue/cost/gp from agg_order_summary."""
    col = _CROSS_DIM_COL.get(cross_dimension)
    if col is None:
        return []

    stmt = (
        select(
            col.label("dim_value"),
            func.sum(AggOrderSummary.revenue).label("revenue"),
            func.sum(AggOrderSummary.cost).label("cost"),
            func.sum(AggOrderSummary.gross_profit).label("gross_profit"),
            func.count().label("order_count"),
        )
        .where(col.isnot(None), col != "")
    )

    # Scope by bgbu (department access control)
    if bgbu_filter and bgbu_filter != "ALL":
        stmt = stmt.where(AggOrderSummary.bgbu == bgbu_filter)

    # Primary filter: department (maps to dim_dept on order level)
    if department:
        stmt = stmt.where(AggOrderSummary.dim_dept == department)

    # Primary filter: product (maps to dim_product on order level)
    if product:
        stmt = stmt.where(AggOrderSummary.dim_product == product)

    # Period filters
    if period:
        stmt = stmt.where(AggOrderSummary.period == period)
    if period_start:
        stmt = stmt.where(AggOrderSummary.period >= period_start)
    if period_end:
        stmt = stmt.where(AggOrderSummary.period <= period_end)

    stmt = (
        stmt.group_by(col)
        .order_by(func.sum(AggOrderSummary.revenue).desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [
        {
            "dimension_value": r.dim_value or "Unknown",
            "revenue": float(r.revenue or 0),
            "cost": float(r.cost or 0),
            "gross_profit": float(r.gross_profit or 0),
            "order_count": int(r.order_count or 0),
        }
        for r in result.all()
    ]
```

- [ ] **Step 2: Verify import**

```bash
cd D:/workspace/caiwu04/backend
python -c "from app.services.cross_analysis import get_cross_analysis; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/cross_analysis.py
git commit -m "feat: add cross-analysis service using agg_order_summary"
```

---

### Task 4: Backend — Cross-Analysis API Endpoint

**Files:**
- Modify: `backend/app/api/dashboard.py`

- [ ] **Step 1: Add imports**

At the top of `dashboard.py`, add:

```python
from app.schemas.query import CrossAnalysisRequest, CrossAnalysisResponse, CrossAnalysisItem
from app.services.cross_analysis import get_cross_analysis
```

- [ ] **Step 2: Add endpoint**

Append to `dashboard.py` (after the existing `/insights` endpoint):

```python
@router.post("/cross-analysis", response_model=APIResponse)
async def cross_analysis(
    body: CrossAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Cross-dimension breakdown: how department/product/customer metrics
    look within a selected primary filter (department or product)."""
    if not body.department and not body.product:
        return APIResponse.success(data={"cross_dimension": body.cross_dimension, "items": [], "total": 0})

    bgbu_filter = (user.department if (user.role != "admin" and user.department) else "ALL")

    items = await get_cross_analysis(
        db=db,
        cross_dimension=body.cross_dimension,
        department=body.department,
        product=body.product,
        period=body.period,
        period_start=body.period_start,
        period_end=body.period_end,
        bgbu_filter=bgbu_filter,
    )

    return APIResponse.success(data={
        "cross_dimension": body.cross_dimension,
        "items": items,
        "total": len(items),
    })
```

- [ ] **Step 3: Verify import**

```bash
cd D:/workspace/caiwu04/backend
python -c "from app.api.dashboard import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/dashboard.py
git commit -m "feat: add POST /dashboard/cross-analysis endpoint"
```

---

### Task 5: Backend — Extend Filter Options for Cross-Dimension

**Files:**
- Modify: `backend/app/api/filters.py`

- [ ] **Step 1: Add `AggOrderSummary` import**

In `filters.py` line 22, add `AggOrderSummary`:

```python
from app.models.core import AggDimensionSummary, AggOrderSummary, AggPeriodSummary
```

- [ ] **Step 2: Add cross-dimension query params to `get_filter_options`**

Add new query params to the function signature (after line 49):

```python
    scope_product: str | None = Query(None, description="Scope values by product (cross-dimension)"),
    scope_department: str | None = Query(None, description="Scope values by department (cross-dimension)"),
```

- [ ] **Step 3: Add cross-dimension scoped query logic**

Before the existing `if dimension in ("department", "product", ...)` block (around line 104), add:

```python
        # Cross-dimension scoped queries: use agg_order_summary
        if dimension in ("department", "product", "customer") and (scope_product or scope_department):
            col_map_order = {
                "department": AggOrderSummary.dim_dept,
                "product": AggOrderSummary.dim_product,
                "customer": AggOrderSummary.dim_customer,
            }
            col = col_map_order.get(dimension)
            if col is not None:
                stmt = select(col).where(col.isnot(None), col != "").distinct()
                if scope_product:
                    stmt = stmt.where(AggOrderSummary.dim_product == scope_product)
                if scope_department:
                    stmt = stmt.where(AggOrderSummary.dim_dept == scope_department)
                bgbu = (user.department if (user.role != "admin" and user.department) else "ALL")
                if bgbu != "ALL":
                    stmt = stmt.where(AggOrderSummary.bgbu == bgbu)
                stmt = stmt.order_by(col)
                if prefix:
                    stmt = stmt.where(col.like(f"{prefix}%"))
                result = await db.execute(stmt)
                options = [str(r[0]) for r in result.all() if r[0]]
                return APIResponse.success(data={"dimension": dimension, "options": options, "total": len(options)})
```

- [ ] **Step 4: Verify import**

```bash
cd D:/workspace/caiwu04/backend
python -c "from app.api.filters import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/filters.py
git commit -m "feat: extend filter-options with cross-dimension scoping via agg_order_summary"
```

---

### Task 6: Frontend — API Client Functions

**Files:**
- Modify: `frontend/src/api/dashboard.ts`
- Modify: `frontend/src/api/filters.ts`

- [ ] **Step 1: Add types and function to `dashboard.ts`**

Append to `frontend/src/api/dashboard.ts`:

```typescript
// ── Cross-Dimension Analysis ─────────────────────────────────

export interface CrossAnalysisParams {
  cross_dimension: 'department' | 'product' | 'customer';
  department?: string;
  product?: string;
  period?: string;
  period_start?: string;
  period_end?: string;
}

export interface CrossAnalysisItem {
  dimension_value: string;
  revenue: number;
  cost: number;
  gross_profit: number;
  order_count: number;
}

export interface CrossAnalysisData {
  cross_dimension: string;
  items: CrossAnalysisItem[];
  total: number;
}

export function queryCrossAnalysis(data: CrossAnalysisParams) {
  return post<CrossAnalysisData>('/dashboard/cross-analysis', data);
}
```

- [ ] **Step 2: Verify `filters.ts` already supports generic query params**

Read `frontend/src/api/filters.ts` to confirm `getFilterOptions` accepts arbitrary params. If it only accepts `dimension` and `prefix`, extend the signature:

```typescript
// In filters.ts, update getFilterOptions to support scope params
export function getFilterOptions(params: {
  dimension?: string;
  prefix?: string;
  scope_product?: string;
  scope_department?: string;
}) {
  return get('/filter-options', { params });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/dashboard.ts frontend/src/api/filters.ts
git commit -m "feat: add cross-analysis API client and scoped filter-options"
```

---

### Task 7: Frontend — Cross-Dimension Filter UI

**Files:**
- Modify: `frontend/src/views/DashboardPage.vue`

- [ ] **Step 1: Add cross-dimension state refs**

After line 76 (`const productOptions = ...`), add:

```typescript
// Cross-dimension filter state
const crossDimension = ref<string | undefined>();
const crossDimensionOptions = ref<Array<{ label: string; value: string }>>([]);
```

- [ ] **Step 2: Compute available cross-dimension options**

After the cross-dimension refs, add a computed property:

```typescript
const crossDimensionAvailable = computed(() => {
  const opts: Array<{ label: string; value: string }> = [];
  if (!selectedMarketLine.value) {
    opts.push({ label: '按部门', value: 'department' });
  }
  if (!selectedProduct.value) {
    opts.push({ label: '按产品', value: 'product' });
  }
  opts.push({ label: '按客户', value: 'customer' });
  return opts;
});

// Show cross-dimension selector when market line or product is selected
const showCrossDimension = computed(() => {
  return !!(selectedMarketLine.value || selectedProduct.value);
});
```

- [ ] **Step 3: Add watch to reset cross-dimension when primary filters change**

After the existing watches, add:

```typescript
watch([selectedMarketLine, selectedProduct], () => {
  // Reset cross-dimension if it's no longer valid
  const available = crossDimensionAvailable.value.map(o => o.value);
  if (crossDimension.value && !available.includes(crossDimension.value)) {
    crossDimension.value = undefined;
  }
});
```

- [ ] **Step 4: Add cross-dimension selector to template**

In the template, after the Product Line `<a-select>` (line 31), add:

```vue
        <template v-if="showCrossDimension">
          <a-divider type="vertical" />
          <a-select
            v-model:value="crossDimension"
            :options="crossDimensionAvailable"
            style="width: 140px"
            placeholder="交叉分析"
            allow-clear
          />
        </template>
```

- [ ] **Step 5: Pass cross-dimension props to FinancialOverview**

Update the `<FinancialOverview>` component call (around line 36-43):

```vue
      <FinancialOverview
        :period="period"
        :period-dimension="periodDimension"
        :period-start="periodStart"
        :period-end="periodEnd"
        :department="selectedMarketLine"
        :product="selectedProduct"
        :cross-dimension="crossDimension"
      />
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/DashboardPage.vue
git commit -m "feat: add cross-dimension selector to dashboard filter bar"
```

---

### Task 8: Frontend — Cross-Analysis Chart Component

**Files:**
- Create: `frontend/src/components/dashboard/CrossAnalysisChart.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <div class="cross-analysis-chart">
    <a-divider orientation="left">交叉分析 — {{ dimensionLabel }}</a-divider>
    <div v-if="loading" class="chart-loading">
      <a-spin />
    </div>
    <div v-else-if="!items.length" class="chart-empty">
      <a-empty description="暂无交叉分析数据" />
    </div>
    <div v-else ref="chartRef" style="width: 100%; height: 400px;" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import * as echarts from 'echarts';
import { queryCrossAnalysis, type CrossAnalysisItem } from '@/api/dashboard';

const props = defineProps<{
  crossDimension?: string;
  department?: string;
  product?: string;
  period?: string;
  periodStart?: string;
  periodEnd?: string;
}>();

const dimensionLabel = computed(() => {
  const map: Record<string, string> = { department: '按部门', product: '按产品', customer: '按客户' };
  return map[props.crossDimension || ''] || '交叉分析';
});

const loading = ref(false);
const items = ref<CrossAnalysisItem[]>([]);
const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

async function fetchData() {
  if (!props.crossDimension || (!props.department && !props.product)) {
    items.value = [];
    return;
  }
  loading.value = true;
  try {
    const { data } = await queryCrossAnalysis({
      cross_dimension: props.crossDimension as 'department' | 'product' | 'customer',
      department: props.department,
      product: props.product,
      period: props.period,
      period_start: props.periodStart,
      period_end: props.periodEnd,
    });
    items.value = data.data.items;
    await nextTick();
    renderChart();
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function renderChart() {
  if (!chartRef.value || !items.value.length) return;
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }
  const labels = items.value.map(i => i.dimension_value);
  const revenues = items.value.map(i => i.revenue);
  const costs = items.value.map(i => i.cost);
  const profits = items.value.map(i => i.gross_profit);

  chartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['收入', '成本', '毛利'] },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { rotate: labels.length > 8 ? 30 : 0, fontSize: 11 },
    },
    yAxis: { type: 'value' },
    series: [
      { name: '收入', type: 'bar', data: revenues, itemStyle: { color: '#1890ff' } },
      { name: '成本', type: 'bar', data: costs, itemStyle: { color: '#ff7a45' } },
      { name: '毛利', type: 'bar', data: profits, itemStyle: { color: '#52c41a' } },
    ],
  });
}

watch(
  () => [props.crossDimension, props.department, props.product, props.period, props.periodStart, props.periodEnd],
  fetchData,
);

onMounted(() => {
  fetchData();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
});

function handleResize() {
  chartInstance?.resize();
}
</script>

<style scoped>
.cross-analysis-chart {
  margin-top: 16px;
}
.chart-loading,
.chart-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/dashboard/CrossAnalysisChart.vue
git commit -m "feat: add CrossAnalysisChart component with ECharts bar chart"
```

---

### Task 9: Frontend — Integrate Chart into FinancialOverview

**Files:**
- Modify: `frontend/src/components/dashboard/FinancialOverview.vue`

- [ ] **Step 1: Import CrossAnalysisChart**

Add import after the existing component imports (around line 66):

```typescript
import CrossAnalysisChart from './CrossAnalysisChart.vue';
```

- [ ] **Step 2: Add `crossDimension` prop**

Update the props interface (around line 72-80):

```typescript
const props = defineProps<{
  period?: string;
  periodCompareType?: 'yoy' | 'mom' | 'cumulative';
  periodDimension?: string;
  periodStart?: string;
  periodEnd?: string;
  department?: string;
  product?: string;
  crossDimension?: string;
}>();
```

- [ ] **Step 3: Add CrossAnalysisChart to template**

After the trends chart section (around line 46, before the Insights divider), add:

```vue
    <!-- Cross-Dimension Analysis -->
    <CrossAnalysisChart
      v-if="crossDimension"
      :cross-dimension="crossDimension"
      :department="department"
      :product="product"
      :period="period"
      :period-start="periodStart"
      :period-end="periodEnd"
    />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/FinancialOverview.vue
git commit -m "feat: integrate CrossAnalysisChart into FinancialOverview"
```

---

## Verification

1. **Backend unit test**: Start the server, POST to `/dashboard/cross-analysis` with `cross_dimension=customer, product=<any product>` — should return top customers for that product
2. **Filter options test**: GET `/filter-options?dimension=customer&scope_product=<product>` — should return only customers who bought that product
3. **Frontend E2E**: Open dashboard, select Product Line = any value → cross-dimension selector appears → select "按客户" → bar chart renders with customer breakdown
4. **Edge case**: Select both Market Line + Product Line → only "按客户" option available → chart shows customers within that dept+product combination
5. **Performance**: Cross-analysis query on `agg_order_summary` (229k rows) with `WHERE dim_product=X GROUP BY dim_customer` should complete in <500ms
