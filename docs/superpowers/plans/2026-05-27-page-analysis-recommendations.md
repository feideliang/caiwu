# 页面级智能分析推荐系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每个财务分析页面（Dashboard、趋势、部门、产品、客户、核心指标等）提供页面专属的智能分析推荐指标和问题建议，使 AI 助手能根据当前页面的数据上下文生成有针对性的分析建议。

**Architecture:** 在 `ai.py` 中扩展现有的 `_get_page_suggestions` 函数，新增一个 `POST /ai/analysis-recommendations` 端点，根据页面类型、当前数据、异常规则返回结构化的分析推荐（推荐指标 + 推荐问题 + 异常提示）。前端每个分析页面在 `FinancialAssistantPanel` 初始化时调用该端点获取推荐。

**Tech Stack:** FastAPI (Python), Vue 3 + TypeScript, SQLAlchemy async, SSE streaming

---

## File Structure

| Action | File Path | Responsibility |
|---|---|---|
| Modify | `backend/app/api/ai.py` | Expand `_get_page_suggestions`, add new endpoint `POST /ai/analysis-recommendations` |
| Create | `backend/app/schemas/analysis.py` | Schema for `AnalysisRecommendationRequest`, `AnalysisRecommendationResponse`, `MetricRecommendation`, `AnomalyAlert` |
| Modify | `backend/app/api/insights.py` | Reuse insight rule engine for cross-page anomaly detection |
| Modify | `frontend/src/api/ai.ts` | Add `getAnalysisRecommendations` API function |
| Modify | `frontend/src/types/analysis.ts` | TypeScript types for analysis recommendations |
| Modify | `frontend/src/components/ai/FinancialAssistantPanel.vue` | Support structured recommendations display (not just plain suggestions) |
| Modify | `frontend/src/views/DashboardPage.vue` | Pass richer context to assistant |
| Modify | `frontend/src/views/TrendAnalysisPage.vue` | Pass richer context + consume recommendations |
| Modify | `frontend/src/views/DepartmentAnalysisPage.vue` | Pass richer context + consume recommendations |
| Modify | `frontend/src/views/ProductAnalysisPage.vue` | Pass richer context + consume recommendations |
| Modify | `frontend/src/views/CustomerAnalysisPage.vue` | Pass richer context + consume recommendations |
| Modify | `frontend/src/views/CoreMetricsPage.vue` | Pass richer context + consume recommendations |

---

## Task 1: Backend Schema — Analysis Recommendation Types

**Files:**
- Create: `backend/app/schemas/analysis.py`

- [ ] **Step 1: Create schema file with request/response types**

```python
"""Schemas for per-page analysis recommendations."""

from pydantic import BaseModel, Field


class AnalysisRecommendationRequest(BaseModel):
    """Request for page-specific analysis recommendations."""
    page_type: str = Field(description="Page type: dashboard/trend/department/product/customer/core_metrics/insights/prediction")
    period: str | None = None
    period_compare_type: str | None = None  # yoy/mom/cumulative
    period_dimension: str | None = None  # monthly/quarterly/cumulative
    department: str | None = None
    product: str | None = None
    customer: str | None = None


class MetricRecommendation(BaseModel):
    """A single metric recommendation for the current page."""
    metric_name: str  # e.g., "毛利率", "收入同比", "客户集中度"
    metric_key: str  # e.g., "gross_margin", "revenue_yoy", "customer_concentration"
    description: str  # What this metric means
    current_value: float | None = None
    benchmark: float | None = None  # Reference value or threshold
    status: str = "normal"  # "normal" | "warning" | "critical"
    recommendation: str = ""  # Actionable suggestion based on current value


class AnomalyAlert(BaseModel):
    """Anomaly detected in current page data."""
    metric: str
    severity: str  # "low" | "medium" | "high"
    message: str  # Human-readable description
    value: float | None = None
    threshold: float | None = None


class AnalysisRecommendationResponse(BaseModel):
    """Response containing page-specific analysis recommendations."""
    page_type: str
    summary: str  # One-line summary of current page analysis focus
    metrics: list[MetricRecommendation] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    anomalies: list[AnomalyAlert] = Field(default_factory=list)
    drill_down_path: list[str] = Field(default_factory=list)  # Suggested next steps
```

- [ ] **Step 2: Verify schema imports correctly**

Run: `cd backend && python -c "from app.schemas.analysis import AnalysisRecommendationRequest, AnalysisRecommendationResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Register schemas in `__init__.py`**

Modify: `backend/app/schemas/__init__.py` (if exists) or skip if not used.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/analysis.py
git commit -m "feat: add analysis recommendation request/response schemas"
```

---

## Task 2: Backend — Expand `_get_page_suggestions` and Add Recommendation Engine

**Files:**
- Modify: `backend/app/api/ai.py` (lines 397-458, expand `_get_page_suggestions` and add `build_analysis_recommendations`)

- [ ] **Step 1: Expand `_get_page_suggestions` to cover all page types**

Replace the current `_get_page_suggestions` function (lines 397-458) with:

```python
def _get_page_suggestions(
    kpis: dict,
    dept_items: list[dict],
    prod_items: list[dict],
    active_section: str,
    page_type: str | None = None,  # NEW
    customer_items: list[dict] | None = None,  # NEW
) -> list[str]:
    """Generate page-specific suggested questions based on current KPI data."""
    gm = (kpis.get("gross_margin") or 0)
    top_cust_share = kpis.get("top_customer_share", 0)
    rev_consec = kpis.get("revenue_consecutive_growth", 0)
    gp_consec = kpis.get("gross_profit_consecutive_growth", 0)
    cust_top10 = kpis.get("customer_concentration_top10", 0)
    neg_margin_ratio = kpis.get("negative_margin_order_ratio", 0)
    rev_yoy = kpis.get("revenue_yoy_growth")
    gp_yoy = kpis.get("profit_yoy_growth")

    # Map page_type to active_section if not provided
    section = active_section or _page_type_to_section(page_type)

    base: list[str] = []

    if section == "overview":
        base = ["总结本月经营情况", "毛利率是否正常", "哪些指标出现异常"]
    elif section == "metrics":
        base = ["核心指标达标情况如何", "毛利率变化的结构和率影响拆解", "客户集中度风险如何"]
    elif section == "department":
        base = ["哪个部门贡献最高", "各部门增长趋势如何"]
        if dept_items:
            low_dept = min(dept_items, key=lambda x: x.get("gross_margin") or 100)
            base[0:0] = [f"{low_dept['dimension_value']}毛利率为何偏低"]
    elif section == "product":
        base = ["哪个产品线风险最大", "产品毛利率变化原因"]
        if prod_items:
            neg_prods = [p for p in prod_items if (p.get("gross_margin") or 100) < 0]
            if neg_prods:
                base.append(f"为什么{neg_prods[0]['dimension_value']}毛利为负")
    elif section == "customer":
        base = ["客户集中度风险如何", "高价值客户有哪些特征"]
        if customer_items:
            top_cust = customer_items[0] if customer_items else None
            if top_cust and (top_cust.get("revenue_contribution") or 0) > 20:
                base.append(f"{top_cust['dimension_value']}收入占比过高如何应对")
    elif section == "trend":
        base = ["收入趋势是否可持续", "环比波动是否异常"]
        if rev_yoy is not None and rev_yoy < 0:
            base.append("收入同比为何下滑")
    elif section == "prediction":
        base = ["未来3月收入预测", "现金流风险如何"]
    elif section == "insights":
        base = ["本月有哪些异常告警", "有哪些优化机会"]
    elif section == "transaction":
        base = ["本月有哪些大额异常订单", "合同执行情况如何"]
    else:
        base = ["总结本月经营情况", "毛利率变化原因", "哪个部门贡献最高"]

    # Data-conditioned additions (page-agnostic)
    if gm and 0 < gm < 20 and "毛利率偏低原因分析" not in base:
        base.append("毛利率偏低原因分析")
    if top_cust_share and top_cust_share > 10 and "客户集中度风险" not in base:
        base.append("客户集中度风险如何应对")
    if (rev_consec or 0) >= 3 and "连续增长趋势总结" not in base:
        base.append("连续增长趋势总结")
    if (gp_consec or 0) >= 3 and "毛利增长驱动力是什么" not in base:
        base.append("毛利增长驱动力是什么")
    if neg_margin_ratio and neg_margin_ratio > 10 and "负毛利订单" not in base:
        base.append("负毛利订单为何这么多")

    return base[:5]


def _page_type_to_section(page_type: str | None) -> str:
    """Map frontend page_type to active_section for suggestion logic."""
    mapping = {
        "dashboard": "overview",
        "core_metrics": "metrics",
        "trend": "trend",
        "department": "department",
        "product": "product",
        "customer": "customer",
        "prediction": "prediction",
        "insights": "insights",
        "transaction": "transaction",
    }
    return mapping.get(page_type or "", "overview")
```

- [ ] **Step 2: Update all existing callers of `_get_page_suggestions` to pass `page_type`**

The existing callers (lines 514, 764, 968) already pass `active_section`. No changes needed for backward compatibility — `page_type` is an optional new parameter.

- [ ] **Step 3: Add the new `build_analysis_recommendations` function**

Add after `_get_page_suggestions` in `ai.py`:

```python
def build_analysis_recommendations(
    kpis: dict,
    dept_items: list[dict],
    prod_items: list[dict],
    customer_items: list[dict],
    page_type: str,
    period: str | None = None,
) -> dict:
    """Build structured analysis recommendations for a specific page.

    Returns a dict matching AnalysisRecommendationResponse fields.
    """
    from app.schemas.analysis import (
        AnalysisRecommendationResponse,
        MetricRecommendation,
        AnomalyAlert,
    )

    gm = kpis.get("gross_margin") or 0
    rev = kpis.get("revenue") or 0
    gp = kpis.get("gross_profit") or 0
    rev_yoy = kpis.get("revenue_yoy_growth")
    gp_yoy = kpis.get("profit_yoy_growth")
    cust_top10 = kpis.get("customer_concentration_top10") or 0
    neg_margin_ratio = kpis.get("negative_margin_order_ratio") or 0
    high_margin_ratio = kpis.get("high_margin_order_ratio")

    metrics: list[MetricRecommendation] = []
    anomalies: list[AnomalyAlert] = []
    suggested_questions: list[str] = []
    drill_down_path: list[str] = []

    # ── Page-specific metric recommendations ──
    if page_type == "dashboard":
        metrics = [
            MetricRecommendation(
                metric_name="营业收入", metric_key="revenue",
                description="本期总收入", current_value=rev / 1e4 if rev else None,
                recommendation="关注收入规模及同比变化"
            ),
            MetricRecommendation(
                metric_name="毛利率", metric_key="gross_margin",
                description="毛利占收入比", current_value=gm,
                benchmark=25.0,
                status="critical" if 0 < gm < 10 else ("warning" if 0 < gm < 20 else "normal"),
                recommendation="毛利率低于20%需重点关注" if 0 < gm < 20 else "毛利率处于正常水平"
            ),
            MetricRecommendation(
                metric_name="客户集中度Top10", metric_key="customer_concentration_top10",
                description="前10大客户收入占比", current_value=cust_top10,
                benchmark=50.0,
                status="warning" if cust_top10 > 60 else "normal",
                recommendation="客户集中度偏高，建议关注风险" if cust_top10 > 60 else "客户分布健康"
            ),
        ]
        drill_down_path = ["趋势分析", "部门分析", "产品分析"]

    elif page_type == "trend":
        metrics = [
            MetricRecommendation(
                metric_name="收入同比", metric_key="revenue_yoy_growth",
                description="收入同比增长率", current_value=rev_yoy,
                status="warning" if rev_yoy is not None and rev_yoy < 0 else "normal",
                recommendation="收入同比下滑需深入分析" if rev_yoy is not None and rev_yoy < 0 else "收入增长趋势良好"
            ),
            MetricRecommendation(
                metric_name="毛利额同比", metric_key="profit_yoy_growth",
                description="毛利额同比增长率", current_value=gp_yoy,
                recommendation="毛利增长与收入增长是否匹配"
            ),
            MetricRecommendation(
                metric_name="毛利率变动", metric_key="gross_margin_yoy_change",
                description="毛利率同比变化(百分点)",
                current_value=kpis.get("gross_margin_yoy_change"),
                recommendation="关注毛利率持续下滑趋势"
            ),
        ]
        drill_down_path = ["部门维度趋势", "产品维度趋势"]

    elif page_type == "department":
        top_dept = dept_items[0] if dept_items else None
        metrics = [
            MetricRecommendation(
                metric_name="部门收入贡献", metric_key="department_revenue",
                description="各部门收入拆解",
                recommendation="关注收入贡献最高的部门"
            ),
            MetricRecommendation(
                metric_name="负毛利部门", metric_key="negative_margin_department",
                description="是否存在负毛利部门",
                status="warning" if any((d.get("gross_margin") or 100) < 0 for d in dept_items) else "normal",
                recommendation="有部门毛利为负需立即关注"
            ),
        ]
        if dept_items:
            for d in dept_items[:3]:
                if (d.get("gross_margin") or 100) < 0:
                    suggested_questions.append(f"为什么{d['dimension_value']}毛利为负")
        drill_down_path = ["客户维度", "产品维度"]

    elif page_type == "product":
        metrics = [
            MetricRecommendation(
                metric_name="产品线毛利率", metric_key="product_gross_margin",
                description="各产品线盈利能力",
                recommendation="关注低毛利产品线"
            ),
            MetricRecommendation(
                metric_name="负毛利产品占比", metric_key="negative_margin_product_ratio",
                description="负毛利产品数量占比",
                current_value=kpis.get("negative_margin_product_ratio"),
                status="warning" if (kpis.get("negative_margin_product_ratio") or 0) > 10 else "normal",
            ),
        ]
        if prod_items:
            for p in prod_items[:3]:
                if (p.get("gross_margin") or 100) < 0:
                    suggested_questions.append(f"为什么{p['dimension_value']}毛利为负")
        drill_down_path = ["销售产品下钻", "客户维度"]

    elif page_type == "customer":
        metrics = [
            MetricRecommendation(
                metric_name="客户集中度", metric_key="customer_concentration",
                description="客户收入集中度",
                current_value=cust_top10,
                benchmark=50.0,
                status="warning" if cust_top10 > 60 else "normal",
            ),
            MetricRecommendation(
                metric_name="单客户最高占比", metric_key="top_customer_share",
                description="单一最大客户收入占比",
                current_value=kpis.get("top_customer_share"),
                benchmark=30.0,
                status="critical" if (kpis.get("top_customer_share") or 0) > 30 else "normal",
            ),
        ]
        if customer_items and customer_items[0].get("revenue_contribution", 0) > 20:
            suggested_questions.append(f"{customer_items[0]['dimension_value']}占比过高是否有风险")
        drill_down_path = ["销售产品维度", "合同类型"]

    elif page_type == "core_metrics":
        metrics = [
            MetricRecommendation(
                metric_name="高毛利订单占比", metric_key="high_margin_order_ratio",
                description="毛利率>40%的订单比例",
                current_value=high_margin_ratio,
                benchmark=50.0,
                recommendation="高毛利订单占比反映业务质量"
            ),
            MetricRecommendation(
                metric_name="负毛利订单占比", metric_key="negative_margin_order_ratio",
                description="毛利为负的订单比例",
                current_value=neg_margin_ratio,
                status="warning" if neg_margin_ratio > 10 else "normal",
            ),
        ]
        drill_down_path = ["交易明细", "异常订单"]

    elif page_type == "insights":
        metrics = [
            MetricRecommendation(
                metric_name="异常告警", metric_key="anomaly_alerts",
                description="系统检测到的异常指标",
                recommendation="查看并处理所有未读告警"
            ),
        ]
        drill_down_path = ["关联分析", "交易分析"]

    elif page_type == "prediction":
        metrics = [
            MetricRecommendation(
                metric_name="收入预测", metric_key="revenue_prediction",
                description="未来3个月收入预测",
                recommendation="关注预测与实际偏差"
            ),
            MetricRecommendation(
                metric_name="DSO预测", metric_key="dso_prediction",
                description="应收账款周转天数预测",
                recommendation="DSO上升预示回款风险"
            ),
        ]
        drill_down_path = ["历史预测准确性", "影响因子"]

    # ── Anomaly detection (applies to all pages) ──
    if 0 < gm < 10:
        anomalies.append(AnomalyAlert(
            metric="毛利率", severity="high",
            message=f"毛利率仅{gm:.1f}%，低于10%严重异常阈值，需立即下钻分析",
            value=gm, threshold=10.0
        ))
    elif 0 < gm < 20:
        anomalies.append(AnomalyAlert(
            metric="毛利率", severity="medium",
            message=f"毛利率{gm:.1f}%，低于20%预警线，建议关注",
            value=gm, threshold=20.0
        ))
    if rev_yoy is not None and rev_yoy < -10:
        anomalies.append(AnomalyAlert(
            metric="收入同比", severity="high",
            message=f"收入同比下降{abs(rev_yoy):.1f}%，降幅较大",
            value=rev_yoy, threshold=-10.0
        ))
    if neg_margin_ratio > 15:
        anomalies.append(AnomalyAlert(
            metric="负毛利订单占比", severity="medium",
            message=f"负毛利订单占比{neg_margin_ratio:.1f}%，比例偏高",
            value=neg_margin_ratio, threshold=15.0
        ))

    # ── Suggested questions ──
    if not suggested_questions:
        suggested_questions = _get_page_suggestions(
            kpis, dept_items, prod_items, "", page_type=page_type
        )

    # ── Summary ──
    if anomalies:
        summary = f"检测到 {len(anomalies)} 项异常，建议优先处理"
    elif gm > 30:
        summary = "整体盈利能力良好，可关注增长机会"
    elif rev_yoy is not None and rev_yoy > 10:
        summary = "收入增长良好，建议分析增长驱动因素"
    else:
        summary = "建议关注核心指标变化趋势"

    return {
        "page_type": page_type,
        "summary": summary,
        "metrics": [m.model_dump() for m in metrics],
        "suggested_questions": suggested_questions[:5],
        "anomalies": [a.model_dump() for a in anomalies],
        "drill_down_path": drill_down_path,
    }
```

- [ ] **Step 4: Add the new API endpoint**

Add to `backend/app/api/ai.py` after the existing chat/stream endpoints:

```python
@router.post("/analysis-recommendations", response_model=APIResponse)
async def get_analysis_recommendations(
    body: "AnalysisRecommendationRequest",
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_optional_user),
) -> APIResponse:
    """Get page-specific analysis recommendations with metrics and anomaly alerts."""
    from app.api.dashboard import _build_kpis

    bgbu_filter = "ALL"
    if user and user.role != "admin" and user.department:
        bgbu_filter = user.department

    # Fetch current KPI data
    dept_param = body.department if body.department else None
    prod_param = body.product if body.product else None

    kpis = await _build_kpis(
        db,
        period_compare_type=body.period_compare_type,
        period_dimension=body.period_dimension,
        period=body.period,
        department=dept_param,
        product=prod_param,
    )

    # Fetch department breakdown if needed
    dept_items = []
    if body.page_type in ("department", "dashboard", "core_metrics"):
        from app.services.metrics_service import MetricsService
        async with async_session_factory() as session:
            result = await MetricsService.get_core_metrics(
                db=session,
                period=body.period,
                dimension="department",
                compare="mom",
                period_dimension=body.period_dimension or "monthly",
                bgbu_filter=bgbu_filter,
                sections={"breakdowns"},
            )
            dept_items = [b.model_dump() for b in result.breakdowns]

    # Fetch product breakdown
    prod_items = []
    if body.page_type in ("product", "dashboard", "core_metrics"):
        from app.services.metrics_service import MetricsService
        async with async_session_factory() as session:
            result = await MetricsService.get_core_metrics(
                db=session,
                period=body.period,
                dimension="product_line",
                compare="mom",
                period_dimension=body.period_dimension or "monthly",
                product=prod_param,
                bgbu_filter=bgbu_filter,
                sections={"breakdowns"},
            )
            prod_items = [b.model_dump() for b in result.breakdowns]

    # Fetch customer breakdown
    customer_items = []
    if body.page_type in ("customer", "dashboard"):
        from app.services.metrics_service import MetricsService
        async with async_session_factory() as session:
            result = await MetricsService.get_core_metrics(
                db=session,
                period=body.period,
                dimension="company",
                compare="mom",
                period_dimension=body.period_dimension or "monthly",
                bgbu_filter=bgbu_filter,
                sections={"customer_breakdown"},
            )
            customer_items = [b.model_dump() for b in result.customer_breakdown]

    recommendations = build_analysis_recommendations(
        kpis=kpis,
        dept_items=dept_items,
        prod_items=prod_items,
        customer_items=customer_items,
        page_type=body.page_type,
        period=body.period,
    )

    return APIResponse.success(data=recommendations)
```

- [ ] **Step 5: Add missing imports**

At the top of `ai.py`, ensure these imports exist:

```python
from app.db.session import get_db, async_session_factory
```

Add to imports if not present:
```python
from app.schemas.analysis import AnalysisRecommendationRequest
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ai.py backend/app/schemas/analysis.py
git commit -m "feat: add page-specific analysis recommendation endpoint and engine"
```

---

## Task 3: Backend — Add Customer Breakdown Support to `_get_page_suggestions` Caller

**Files:**
- Modify: `backend/app/api/ai.py` (update `_build_kpis` callers in chat/chat-stream to also fetch customer items)

- [ ] **Step 1: Update non-streaming chat to fetch customer items**

In the `ai_chat` function (line ~630), after `dept_items, prod_items = [], []`, add customer fetch when `active_section == "customer"` or `page_type == "customer"`:

```python
    # Also fetch customer breakdown for customer-focused pages
    customer_items = []
    active_section = body.context.active_section if body.context else ""
    if active_section in ("customer", "overview"):
        from app.services.metrics_service import MetricsService
        async with async_session_factory() as session:
            cust_result = await MetricsService.get_core_metrics(
                db=session,
                period=body.context.period if body.context else None,
                dimension="company",
                compare="mom",
                bgbu_filter="ALL",
                sections={"customer_breakdown"},
            )
            customer_items = [b.model_dump() for b in cust_result.customer_breakdown]
```

Then pass `customer_items` to `_get_page_suggestions`:
```python
    suggestions = _get_page_suggestions(kpis, dept_items, prod_items, active_section, customer_items=customer_items)
```

- [ ] **Step 2: Update streaming chat endpoint similarly**

In `ai_chat_stream` (line ~968), add the same customer fetch before calling `_get_page_suggestions`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/ai.py
git commit -m "feat: include customer breakdown in AI chat suggestions"
```

---

## Task 4: Frontend — API Function and TypeScript Types

**Files:**
- Create: `frontend/src/types/analysis.ts`
- Modify: `frontend/src/api/ai.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/analysis.ts

export interface MetricRecommendation {
  metric_name: string;
  metric_key: string;
  description: string;
  current_value?: number;
  benchmark?: number;
  status: 'normal' | 'warning' | 'critical';
  recommendation: string;
}

export interface AnomalyAlert {
  metric: string;
  severity: 'low' | 'medium' | 'high';
  message: string;
  value?: number;
  threshold?: number;
}

export interface AnalysisRecommendations {
  page_type: string;
  summary: string;
  metrics: MetricRecommendation[];
  suggested_questions: string[];
  anomalies: AnomalyAlert[];
  drill_down_path: string[];
}

export interface AnalysisRecommendationRequest {
  page_type: string;
  period?: string;
  period_compare_type?: string;
  period_dimension?: string;
  department?: string;
  product?: string;
  customer?: string;
}
```

- [ ] **Step 2: Add API function to ai.ts**

Add to `frontend/src/api/ai.ts`:

```typescript
import type { AnalysisRecommendationRequest, AnalysisRecommendations } from '@/types/analysis';

export async function getAnalysisRecommendations(
  data: AnalysisRecommendationRequest,
) {
  return api.post<APIResponse<AnalysisRecommendations>>(
    '/ai/analysis-recommendations',
    data,
  );
}
```

(Use the existing `api` client already imported in ai.ts)

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors related to new types

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/analysis.ts frontend/src/api/ai.ts
git commit -m "feat: add analysis recommendation API client and TypeScript types"
```

---

## Task 5: Frontend — Enhance FinancialAssistantPanel to Display Recommendations

**Files:**
- Modify: `frontend/src/components/ai/FinancialAssistantPanel.vue`

- [ ] **Step 1: Add recommendations prop and display**

Add to `FinancialAssistantPanel.vue` props:

```typescript
const props = defineProps<{
  context?: ChatContext;
  recommendations?: {
    metrics: MetricRecommendation[];
    anomalies: AnomalyAlert[];
    suggested_questions: string[];
    summary: string;
  };
}>();
```

- [ ] **Step 2: Add recommendations display section**

Add to template (before the suggestions buttons, after messages):

```vue
<!-- Analysis Recommendations -->
<div v-if="recommendations && messages.length === 0" class="recommendations">
  <div v-if="recommendations.summary" class="rec-summary">
    {{ recommendations.summary }}
  </div>

  <!-- Anomaly Alerts -->
  <div v-if="recommendations.anomalies.length" class="rec-anomalies">
    <a-alert
      v-for="(alert, idx) in recommendations.anomalies"
      :key="idx"
      :type="alert.severity === 'high' ? 'error' : alert.severity === 'medium' ? 'warning' : 'info'"
      :message="alert.message"
      size="small"
      closable
      style="margin-bottom: 6px"
    />
  </div>

  <!-- Key Metrics -->
  <div v-if="recommendations.metrics.length" class="rec-metrics">
    <div
      v-for="(m, idx) in recommendations.metrics"
      :key="idx"
      class="rec-metric"
      :class="m.status"
    >
      <span class="metric-name">{{ m.metric_name }}</span>
      <span class="metric-value" v-if="m.current_value !== undefined">
        {{ formatMetricValue(m) }}
      </span>
      <span class="metric-rec">{{ m.recommendation }}</span>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add helper function**

```typescript
import type { MetricRecommendation, AnomalyAlert } from '@/types/analysis';

function formatMetricValue(m: MetricRecommendation): string {
  if (m.metric_key.includes('margin') || m.metric_key.includes('concentration') || m.metric_key.includes('ratio')) {
    return m.current_value != null ? `${m.current_value.toFixed(1)}%` : '--';
  }
  if (m.current_value != null && m.current_value > 10000) {
    return `${(m.current_value / 10000).toFixed(1)}亿`;
  }
  return m.current_value != null ? m.current_value.toFixed(0) : '--';
}
```

- [ ] **Step 4: Add styles**

```less
.recommendations {
  padding: 8px 0;
}

.rec-summary {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.rec-anomalies {
  margin-bottom: 8px;
}

.rec-metrics {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rec-metric {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #f9f9f9;
  font-size: 12px;

  &.critical {
    background: #fff2f0;
    border: 1px solid #ffccc7;
  }

  &.warning {
    background: #fffbe6;
    border: 1px solid #ffe58f;
  }

  &.normal {
    background: #f6ffed;
    border: 1px solid #b7eb8f;
  }
}

.metric-name {
  font-weight: 600;
  color: #333;
}

.metric-value {
  color: #1677ff;
  font-weight: 500;
}

.metric-rec {
  color: #666;
  margin-left: auto;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ai/FinancialAssistantPanel.vue
git commit -m "feat: display structured analysis recommendations in assistant panel"
```

---

## Task 6: Frontend — Wire Up Recommendations to Each Analysis Page

**Files:**
- Modify: `frontend/src/views/DashboardPage.vue`
- Modify: `frontend/src/views/TrendAnalysisPage.vue`
- Modify: `frontend/src/views/DepartmentAnalysisPage.vue`
- Modify: `frontend/src/views/ProductAnalysisPage.vue`
- Modify: `frontend/src/views/CustomerAnalysisPage.vue`
- Modify: `frontend/src/views/CoreMetricsPage.vue`

Each page follows the same pattern:
1. Import `getAnalysisRecommendations` and types
2. Add `recommendations` ref and fetch on mount / filter change
3. Pass `recommendations` prop to `FinancialAssistantPanel`

- [ ] **Step 1: DashboardPage.vue**

Add imports:
```typescript
import { getAnalysisRecommendations } from '@/api/ai';
import type { AnalysisRecommendations } from '@/types/analysis';
```

Add state and fetch:
```typescript
const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'dashboard',
      period: selectedPeriod.value,
      period_compare_type: 'yoy',
    });
    recommendations.value = data.data;
  } catch { /* non-critical */ }
}
```

Pass to assistant:
```vue
<FinancialAssistantPanel
  :context="assistantContext"
  :recommendations="recommendations"
/>
```

Call `loadRecommendations()` in `onMounted` and after filter changes.

- [ ] **Step 2: TrendAnalysisPage.vue**

```typescript
const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'trend',
      period: period.value,
      period_compare_type: compareBase.value,
      period_dimension: periodDimension.value,
    });
    recommendations.value = data.data;
  } catch {}
}
```

```vue
<FinancialAssistantPanel
  :context="assistantContext"
  :recommendations="recommendations"
/>
```

- [ ] **Step 3: DepartmentAnalysisPage.vue**

```typescript
const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'department',
      period: period.value,
      period_compare_type: compareBase.value,
      department: selectedDepartment.value,
    });
    recommendations.value = data.data;
  } catch {}
}
```

- [ ] **Step 4: ProductAnalysisPage.vue**

```typescript
const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'product',
      period: period.value,
      period_compare_type: compareBase.value,
      product: selectedProduct.value,
    });
    recommendations.value = data.data;
  } catch {}
}
```

- [ ] **Step 5: CustomerAnalysisPage.vue**

```typescript
const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'customer',
      period: period.value,
      period_compare_type: compareBase.value,
    });
    recommendations.value = data.data;
  } catch {}
}
```

- [ ] **Step 6: CoreMetricsPage.vue**

```typescript
const recommendations = ref<AnalysisRecommendations | null>(null);

async function loadRecommendations() {
  try {
    const { data } = await getAnalysisRecommendations({
      page_type: 'core_metrics',
      period: period.value,
      period_compare_type: compareBase.value,
    });
    recommendations.value = data.data;
  } catch {}
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/DashboardPage.vue frontend/src/views/TrendAnalysisPage.vue frontend/src/views/DepartmentAnalysisPage.vue frontend/src/views/ProductAnalysisPage.vue frontend/src/views/CustomerAnalysisPage.vue frontend/src/views/CoreMetricsPage.vue
git commit -m "feat: wire analysis recommendations to all analysis pages"
```

---

## Task 7: Test and Verify End-to-End

- [ ] **Step 1: Start backend and verify new endpoint**

```bash
curl -X POST http://127.0.0.1:8001/api/v1/ai/analysis-recommendations \
  -H "Content-Type: application/json" \
  -d '{"page_type": "dashboard", "period": "2026-04"}'
```
Expected: 200 OK with JSON containing `page_type`, `summary`, `metrics`, `suggested_questions`, `anomalies`, `drill_down_path`

- [ ] **Step 2: Test each page type**

```bash
for page in dashboard trend department product customer core_metrics; do
  echo "=== $page ==="
  curl -s -X POST http://127.0.0.1:8001/api/v1/ai/analysis-recommendations \
    -H "Content-Type: application/json" \
    -d "{\"page_type\": \"$page\", \"period\": \"2026-04\"}" | python -c "
import sys, json
d = json.load(sys.stdin).get('data', {})
print(f'  summary: {d.get(\"summary\")}')
print(f'  metrics: {len(d.get(\"metrics\", []))}')
print(f'  questions: {d.get(\"suggested_questions\")}')
print(f'  anomalies: {len(d.get(\"anomalies\", []))}')
"
done
```

- [ ] **Step 3: Start frontend dev server and verify UI**

```bash
cd frontend && npm run dev
```

Navigate to each analysis page and verify:
- FinancialAssistantPanel shows structured recommendations (metrics with status colors, anomaly alerts)
- Suggested questions are page-specific
- Drill-down path is shown

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: polish analysis recommendation UI and edge cases"
```
