"""AI-related Pydantic schemas: chart recommendation and layout."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Chart Recommendation ────────────────────────────────────

class ChartRecommendRequest(BaseModel):
    data_description: dict = Field(
        description="Description of the dataset, e.g. "
        "{'columns': ['revenue', 'cost', 'month'], 'row_count': 120, "
        "'time_series': true, 'categories': ['product_a', 'product_b']}"
    )
    analysis_goal: str = Field(
        default="overview",
        description="Intent: overview / comparison / trend / distribution / composition / correlation",
    )
    top_k: int = Field(default=5, ge=1, le=20)
    device: str | None = Field(default=None, description="Target device type: web / tablet / mobile")


class ChartRecommendItem(BaseModel):
    chart_type: str
    priority: int
    score: float
    reason: str
    suggested_config: dict | None = None


class ChartRecommendResponse(BaseModel):
    recommendations: list[ChartRecommendItem]
    total_candidates: int


# ── Layout Recommendation ──────────────────────────────────

class LayoutRecommendRequest(BaseModel):
    chart_ids: list[int] = Field(min_length=1, max_length=50)
    device_type: str = Field(default="web", description="web / mobile / tablet")
    dashboard_id: int | None = None


class LayoutCell(BaseModel):
    chart_id: int
    x: int
    y: int
    w: int
    h: int


class LayoutRecommendResponse(BaseModel):
    device_type: str
    grid_cols: int
    grid_rows: int
    cells: list[LayoutCell]


# ── AI Chat / Smart Q&A ────────────────────────────────────

class ChatContext(BaseModel):
    """BI context passed with each chat request."""
    period: str | None = None
    department: str | None = None
    product: str | None = None
    period_compare_type: str | None = None
    active_section: str | None = None  # 'overview' | 'trend' | 'department' | 'product'


class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class ChatReference(BaseModel):
    type: str = "metric"  # 'metric' | 'dimension' | 'trend' | 'insight'
    label: str
    value: str | float | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: ChatContext | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


class ChatResponse(BaseModel):
    answer: str
    suggestions: list[str] = Field(default_factory=list)
    references: list[ChatReference] = Field(default_factory=list)
