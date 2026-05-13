"""Tests for the chart recommendation service."""

from __future__ import annotations

import pytest

from app.services.chart_recommend import recommend_charts, recommend_layout
from app.schemas.ai import ChartRecommendRequest


class TestRecommendCharts:
    """Test chart recommendation scoring logic."""

    def _make_request(self, data_description: dict, goal: str = "overview", top_k: int = 5) -> ChartRecommendRequest:
        return ChartRecommendRequest(
            data_description=data_description,
            analysis_goal=goal,
            top_k=top_k,
        )

    def test_line_chart_for_time_series(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "month"],
                "row_count": 12,
                "time_series": True,
                "categories": [],
                "numeric_columns": 1,
            },
            goal="trend",
        )
        result = recommend_charts(req)
        types = [r.chart_type for r in result.recommendations]
        assert "line" in types
        # Line should be top for time series + trend
        assert result.recommendations[0].chart_type in ("line", "area")

    def test_bar_chart_for_comparison(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "dept"],
                "row_count": 10,
                "time_series": False,
                "categories": ["dept_a", "dept_b", "dept_c"],
                "numeric_columns": 1,
            },
            goal="comparison",
        )
        result = recommend_charts(req)
        types = [r.chart_type for r in result.recommendations]
        assert "bar" in types

    def test_pie_chart_few_categories(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "category"],
                "row_count": 5,
                "time_series": False,
                "categories": ["a", "b", "c"],
                "numeric_columns": 1,
            },
            goal="composition",
        )
        result = recommend_charts(req)
        types = [r.chart_type for r in result.recommendations]
        assert "pie" in types
        pie_item = next(r for r in result.recommendations if r.chart_type == "pie")
        assert pie_item.score > 0.5  # high score for few categories

    def test_pie_chart_too_many_categories(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "category"],
                "row_count": 50,
                "time_series": False,
                "categories": [f"cat_{i}" for i in range(20)],
                "numeric_columns": 1,
            },
            goal="composition",
        )
        result = recommend_charts(req)
        pie_item = next((r for r in result.recommendations if r.chart_type == "pie"), None)
        if pie_item:
            assert pie_item.score < 0.5  # penalized for many slices

    def test_scatter_for_correlation(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "cost", "month"],
                "row_count": 24,
                "time_series": False,
                "categories": [],
                "numeric_columns": 2,
            },
            goal="correlation",
        )
        result = recommend_charts(req)
        types = [r.chart_type for r in result.recommendations]
        assert "scatter" in types

    def test_non_time_series_excludes_line(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "dept"],
                "row_count": 5,
                "time_series": False,
                "categories": ["a", "b"],
                "numeric_columns": 1,
            },
            goal="overview",
        )
        result = recommend_charts(req)
        types = [r.chart_type for r in result.recommendations]
        assert "line" not in types
        assert "area" not in types

    def test_top_k_limits_results(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "month"],
                "row_count": 12,
                "time_series": True,
                "categories": [],
                "numeric_columns": 1,
            },
            goal="trend",
            top_k=2,
        )
        result = recommend_charts(req)
        assert len(result.recommendations) <= 2

    def test_scores_are_bounded(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "month"],
                "row_count": 12,
                "time_series": True,
                "categories": ["a", "b"],
                "numeric_columns": 2,
            },
            goal="overview",
        )
        result = recommend_charts(req)
        for item in result.recommendations:
            assert 0 < item.score <= 1.0

    def test_priority_is_sequential(self):
        req = self._make_request(
            data_description={
                "columns": ["revenue", "month"],
                "row_count": 12,
                "time_series": True,
                "categories": [],
                "numeric_columns": 1,
            },
            goal="trend",
        )
        result = recommend_charts(req)
        for i, item in enumerate(result.recommendations):
            assert item.priority == i + 1


class TestRecommendLayout:
    """Test layout recommendation logic."""

    def test_web_layout_single_chart(self):
        result = recommend_layout([1], "web")
        assert result["device_type"] == "web"
        assert result["grid_cols"] == 12
        assert len(result["cells"]) == 1

    def test_web_layout_two_charts(self):
        result = recommend_layout([1, 2], "web")
        assert len(result["cells"]) == 2
        # Should be side-by-side
        assert result["cells"][0]["x"] == 0
        assert result["cells"][1]["x"] == 6

    def test_mobile_layout_stacks(self):
        result = recommend_layout([1, 2], "mobile")
        assert result["grid_cols"] == 4
        # Mobile should stack vertically
        assert result["cells"][0]["y"] < result["cells"][1]["y"]

    def test_fallback_for_unknown_count(self):
        result = recommend_layout(list(range(1, 11)), "web")
        assert len(result["cells"]) == 10
        assert result["grid_cols"] == 12

    def test_device_type_fallback(self):
        result = recommend_layout([1], "unknown_device")
        assert result["grid_cols"] == 12  # falls back to web

    def test_cell_has_required_fields(self):
        result = recommend_layout([1, 2, 3], "web")
        for cell in result["cells"]:
            assert "chart_id" in cell
            assert "x" in cell
            assert "y" in cell
            assert "w" in cell
            assert "h" in cell
