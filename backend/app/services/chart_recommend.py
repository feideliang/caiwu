"""Chart recommendation service — rule-based pre-screen + AI rerank."""

from __future__ import annotations

import math
from typing import Any

import httpx

from app.config import settings
from app.schemas.ai import ChartRecommendItem, ChartRecommendRequest, ChartRecommendResponse

# ── Rule-based candidate generation ─────────────────────────

# Each chart type has a scoring function based on data characteristics.
_CHART_RULES: dict[str, dict[str, Any]] = {
    "line": {
        "requires_time_series": True,
        "score_fn": "_score_line",
        "description": "Best for showing trends over time",
    },
    "bar": {
        "requires_time_series": False,
        "score_fn": "_score_bar",
        "description": "Best for categorical comparison",
    },
    "pie": {
        "requires_time_series": False,
        "score_fn": "_score_pie",
        "description": "Best for composition / part-of-whole",
    },
    # Chart types below require frontend components not yet implemented:
    # scatter, area, table, heatmap, kpi_card
}


async def recommend_charts(request: ChartRecommendRequest) -> ChartRecommendResponse:
    """Generate chart recommendations based on data characteristics.

    Strategy:
    1. Rule-based pre-screen: score each chart type 0..1 based on data fit.
    2. Apply analysis_goal boost.
    3. Use Qwen AI to rerank and generate better reasons (if API key configured).
    4. Return top_k sorted by final score.
    """
    desc = request.data_description
    columns = desc.get("columns", [])
    row_count = desc.get("row_count", 0)
    is_time_series = desc.get("time_series", False)
    categories = desc.get("categories", [])
    num_cols = desc.get("numeric_columns", 0)

    goal = request.analysis_goal

    scored: list[ChartRecommendItem] = []

    for chart_type, rules in _CHART_RULES.items():
        # Hard filter: time-series charts require time series data
        if rules.get("requires_time_series") and not is_time_series:
            continue

        score = _compute_score(chart_type, is_time_series, row_count, len(categories), num_cols, goal, len(columns))

        if score <= 0:
            continue

        scored.append(
            ChartRecommendItem(
                chart_type=chart_type,
                priority=len(scored) + 1,
                score=round(score, 4),
                reason=rules["description"],
                suggested_config=_suggested_config(chart_type, columns),
            )
        )

    # Sort by score descending
    scored.sort(key=lambda x: x.score, reverse=True)

    # Assign priority
    for i, item in enumerate(scored):
        item.priority = i + 1

    # Try AI enhancement if API key is configured
    if settings.qwen_api_key:
        try:
            ai_reason = await _ai_generate_recommendation(
                request.data_description, goal, scored[:3]
            )
            if ai_reason:
                # Enhance top recommendation with AI-generated reason
                if scored and ai_reason:
                    scored[0].reason = ai_reason
        except Exception:
            pass  # Fall back to rule-based

    top_k = scored[: request.top_k]

    return ChartRecommendResponse(
        recommendations=top_k,
        total_candidates=len(scored),
    )


async def _ai_generate_recommendation(
    data_description: dict,
    goal: str | None,
    top_charts: list[ChartRecommendItem],
) -> str | None:
    """Generate AI-powered chart recommendation reason via Qwen API."""
    if not settings.qwen_api_key:
        return None

    columns = data_description.get("columns", [])
    row_count = data_description.get("row_count", 0)
    is_time_series = data_description.get("time_series", False)
    categories = data_description.get("categories", [])

    chart_list = ", ".join([f"{c.chart_type}(score={c.score})" for c in top_charts]) if top_charts else "none"

    prompt = (
        f"You are a financial data visualization expert. Analyze this dataset and recommend the best chart type.\n\n"
        f"Dataset characteristics:\n"
        f"- Columns: {columns}\n"
        f"- Row count: {row_count}\n"
        f"- Time series: {is_time_series}\n"
        f"- Categories: {categories}\n"
        f"- Analysis goal: {goal or 'general overview'}\n\n"
        f"Top chart candidates (rule-based): {chart_list}\n\n"
        f"Based on the data characteristics and analysis goal, which chart type is most suitable? "
        f"Provide a brief reason (1-2 sentences) for the best recommendation in Chinese."
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.qwen_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.qwen_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.qwen_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass

    return None


def _compute_score(
    chart_type: str,
    is_time_series: bool,
    row_count: int,
    category_count: int,
    num_cols: int,
    goal: str,
    column_count: int = 0,
) -> float:
    score = 0.0

    if chart_type == "line":
        score = 0.6
        if is_time_series:
            score += 0.3
        if goal == "trend":
            score += 0.1
    elif chart_type == "bar":
        score = 0.5
        if category_count > 0 and category_count <= 20:
            score += 0.3
        elif category_count > 20:
            score += 0.1  # too many bars
        if goal in ("comparison", "overview"):
            score += 0.2
    elif chart_type == "pie":
        score = 0.3
        if 2 <= category_count <= 7:
            score += 0.4
        elif category_count > 7:
            score = 0.1  # too many slices
        if goal == "composition":
            score += 0.3
    elif chart_type == "scatter":
        score = 0.3
        if num_cols >= 2:
            score += 0.4
        if goal == "correlation":
            score += 0.3
    elif chart_type == "area":
        score = 0.4
        if is_time_series:
            score += 0.3
        if goal == "trend":
            score += 0.2
    elif chart_type == "table":
        score = 0.3
        if row_count <= 100:
            score += 0.3
        else:
            score += 0.1
    elif chart_type == "heatmap":
        score = 0.3
        if category_count > 3 and num_cols >= 2:
            score += 0.4
        if goal in ("comparison", "correlation"):
            score += 0.2
    elif chart_type == "kpi_card":
        score = 0.5
        if num_cols == 1 or (num_cols == 0 and column_count <= 3):
            score += 0.3
        if goal == "overview":
            score += 0.2

    return min(score, 1.0)


def _suggested_config(chart_type: str, columns: list[str]) -> dict:
    configs: dict[str, dict] = {
        "line": {"x_axis": "period", "y_axis": columns[0] if columns else None, "smooth": True},
        "bar": {"x_axis": "category", "y_axis": columns[0] if columns else None, "horizontal": False},
        "pie": {"value_field": columns[0] if columns else None, "name_field": "category"},
        "scatter": {"x_field": columns[0] if len(columns) > 0 else None, "y_field": columns[1] if len(columns) > 1 else None},
        "area": {"x_axis": "period", "y_axis": columns[0] if columns else None, "stacked": True},
        "table": {"columns": columns, "sortable": True, "pagination": True},
        "heatmap": {"x_field": "category", "y_field": "period", "value_field": columns[0] if columns else None},
        "kpi_card": {"value_field": columns[0] if columns else None, "trend_indicator": True},
    }
    return configs.get(chart_type, {})


# ── Layout Recommendation ──────────────────────────────────

_GRID_CONFIG: dict[str, dict] = {
    "web": {"cols": 12, "cell_height": 60},
    "tablet": {"cols": 8, "cell_height": 80},
    "mobile": {"cols": 4, "cell_height": 100},
}

# Predefined layout templates for different chart counts
_LAYOUT_TEMPLATES: dict[str, list[list[dict]]] = {
    "web": {
        1: [{"x": 0, "y": 0, "w": 12, "h": 8}],
        2: [{"x": 0, "y": 0, "w": 6, "h": 8}, {"x": 6, "y": 0, "w": 6, "h": 8}],
        3: [{"x": 0, "y": 0, "w": 8, "h": 8}, {"x": 8, "y": 0, "w": 4, "h": 4}, {"x": 8, "y": 4, "w": 4, "h": 4}],
        4: [{"x": 0, "y": 0, "w": 6, "h": 6}, {"x": 6, "y": 0, "w": 6, "h": 6}, {"x": 0, "y": 6, "w": 6, "h": 6}, {"x": 6, "y": 6, "w": 6, "h": 6}],
        6: [
            {"x": 0, "y": 0, "w": 4, "h": 6}, {"x": 4, "y": 0, "w": 4, "h": 6}, {"x": 8, "y": 0, "w": 4, "h": 6},
            {"x": 0, "y": 6, "w": 4, "h": 6}, {"x": 4, "y": 6, "w": 4, "h": 6}, {"x": 8, "y": 6, "w": 4, "h": 6},
        ],
    },
    "tablet": {
        1: [{"x": 0, "y": 0, "w": 8, "h": 8}],
        2: [{"x": 0, "y": 0, "w": 4, "h": 8}, {"x": 4, "y": 0, "w": 4, "h": 8}],
        4: [{"x": 0, "y": 0, "w": 4, "h": 6}, {"x": 4, "y": 0, "w": 4, "h": 6}, {"x": 0, "y": 6, "w": 4, "h": 6}, {"x": 4, "y": 6, "w": 4, "h": 6}],
    },
    "mobile": {
        1: [{"x": 0, "y": 0, "w": 4, "h": 8}],
        2: [{"x": 0, "y": 0, "w": 4, "h": 6}, {"x": 0, "y": 6, "w": 4, "h": 6}],
        3: [{"x": 0, "y": 0, "w": 4, "h": 6}, {"x": 0, "y": 6, "w": 4, "h": 6}, {"x": 0, "y": 12, "w": 4, "h": 6}],
    },
}


def recommend_layout(chart_ids: list[int], device_type: str) -> dict:
    """Recommend a grid layout for the given chart IDs and device type.

    Falls back to a stacked vertical layout if no template matches.
    """
    grid = _GRID_CONFIG.get(device_type, _GRID_CONFIG["web"])
    templates = _LAYOUT_TEMPLATES.get(device_type, _LAYOUT_TEMPLATES["web"])
    n = len(chart_ids)

    # Find best matching template
    template = templates.get(n)

    if template is None:
        # Generate a fallback: stack charts vertically, 2 per row on wider screens
        template = _generate_fallback_layout(n, grid["cols"])

    from app.schemas.ai import LayoutCell

    cells = [
        LayoutCell(chart_id=chart_ids[i], x=t["x"], y=t["y"], w=t["w"], h=t["h"])
        for i, t in enumerate(template)
    ]

    # Compute grid rows
    max_y_h = max(c.y + c.h for c in cells) if cells else 1

    return {
        "device_type": device_type,
        "grid_cols": grid["cols"],
        "grid_rows": max_y_h,
        "cells": [c.model_dump() for c in cells],
    }


def _generate_fallback_layout(n: int, cols: int) -> list[dict]:
    """Generate a simple 2-column grid layout."""
    per_row = max(2, cols // 2)
    cell_w = cols // per_row
    layout = []
    for i in range(n):
        row = i // per_row
        col = i % per_row
        layout.append({"x": col * cell_w, "y": row * 6, "w": cell_w, "h": 6})
    return layout
