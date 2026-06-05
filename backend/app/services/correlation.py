"""Correlation analysis service: Pearson/Spearman calculation, p-value, AI explanation."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BusinessError
from app.models.core import AggPeriodSummary
from app.models.v3 import CorrelationCalibration, CorrelationResult


# ── Statistical functions ───────────────────────────────────

def pearson_correlation(x: list[float], y: list[float]) -> tuple[float, float, int]:
    """Calculate Pearson correlation coefficient and approximate p-value.

    Returns (coefficient, p_value, sample_size).
    """
    n = min(len(x), len(y))
    if n < 3:
        raise BusinessError("Need at least 3 paired observations for correlation")

    x = x[:n]
    y = y[:n]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if std_x == 0 or std_y == 0:
        return 0.0, 1.0, n

    r = cov / (std_x * std_y)
    r = max(-1.0, min(1.0, r))

    # p-value via t-distribution approximation
    t_stat = r * math.sqrt((n - 2) / (1 - r * r + 1e-10))
    p_value = _t_to_p_value(abs(t_stat), n - 2)

    return round(r, 6), round(p_value, 6), n


def spearman_correlation(x: list[float], y: list[float]) -> tuple[float, float, int]:
    """Calculate Spearman rank correlation coefficient and approximate p-value."""
    n = min(len(x), len(y))
    if n < 3:
        raise BusinessError("Need at least 3 paired observations for correlation")

    x = x[:n]
    y = y[:n]

    rank_x = _rank_data(x)
    rank_y = _rank_data(y)

    return pearson_correlation(rank_x, rank_y)


def _rank_data(values: list[float]) -> list[float]:
    """Convert values to ranks (average rank for ties)."""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _t_to_p_value(t: float, df: int) -> float:
    """Approximate two-tailed p-value from t-statistic using normal approximation.

    For large df, t converges to normal. For small df, use a rough approximation.
    """
    if df <= 0:
        return 1.0
    # Use normal approximation for simplicity
    # For more accurate results, use scipy.stats.t.sf in production
    z = t
    p = 2.0 * (1.0 - _normal_cdf(abs(z)))
    return max(0.0, min(1.0, p))


def _normal_cdf(x: float) -> float:
    """Approximate standard normal CDF using Abramowitz & Stegun formula."""
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)


def classify_strength(coefficient: float) -> str:
    """Classify correlation strength."""
    abs_r = abs(coefficient)
    if abs_r >= 0.7:
        return "强"
    elif abs_r >= 0.4:
        return "中"
    elif abs_r >= 0.1:
        return "弱"
    return "无"


# Mapping from metric names to AggPeriodSummary columns
_METRIC_COL_MAP = {
    "revenue": AggPeriodSummary.revenue,
    "cost": AggPeriodSummary.cost,
    "gross_profit": AggPeriodSummary.gross_profit,
}


async def _fetch_metric_values(
    db: AsyncSession,
    metric_name: str,
    period_start: str | None = None,
    period_end: str | None = None,
    department: str | None = None,
) -> list[tuple[str, float]]:
    """Fetch time-series values for a metric from agg_period_summary (preferred) or financial_data (fallback)."""
    agg_col = _METRIC_COL_MAP.get(metric_name)

    if agg_col is not None:
        # Use aggregated table
        bgbu = department or "ALL"
        if bgbu == "ALL":
            # Aggregate across all departments (no per-company "ALL" rows)
            stmt = (
                select(AggPeriodSummary.period, func.sum(agg_col))
                .where(AggPeriodSummary.bgbu != "ALL")
                .group_by(AggPeriodSummary.period)
            )
        else:
            stmt = select(AggPeriodSummary.period, agg_col).where(
                AggPeriodSummary.bgbu == bgbu
            )
        if period_start:
            stmt = stmt.where(AggPeriodSummary.period >= period_start)
        if period_end:
            stmt = stmt.where(AggPeriodSummary.period <= period_end)
        stmt = stmt.order_by(AggPeriodSummary.period)

        result = await db.execute(stmt)
        if department is None:
            return [(row[0], float(row[1] or 0)) for row in result.all()]
        return [(row[0], float(row[1] or 0)) for row in result.all()]

    # Unknown metric: no data source available (financial_data table is empty)
    return []


async def _ai_explain(
    metric_a: str,
    metric_b: str,
    coefficient: float,
    p_value: float | None,
    strength: str,
) -> str | None:
    """Generate AI explanation via Qwen API (or mock if not configured)."""
    if not settings.qwen_api_key:
        return _mock_explanation(metric_a, metric_b, coefficient, p_value, strength)

    try:
        import httpx

        prompt = (
            f"请用中文解释 {metric_a} 与 {metric_b} 的相关性。"
            f"相关系数为 {coefficient:.3f}，p值为 {p_value}，强度等级为「{strength}」。"
            f"请用一句话提供财务分析洞察。"
            f"重要：必须使用中文输出，不得出现任何英文。"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.qwen_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.qwen_api_key}", "Content-Type": "application/json"},
                json={
                    "model": settings.qwen_model,
                    "messages": [
                        {"role": "system", "content": "你是一位财务分析专家。你的所有输出必须使用中文。绝对禁止使用英文。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 200,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass

    return _mock_explanation(metric_a, metric_b, coefficient, p_value, strength)


def _mock_explanation(
    metric_a: str,
    metric_b: str,
    coefficient: float,
    p_value: float | None,
    strength: str,
) -> str:
    direction = "正相关" if coefficient > 0 else "负相关"
    significance = "统计显著" if (p_value is not None and p_value < 0.05) else "统计不显著"

    explanations = {
        "强": f"{metric_a} 与 {metric_b} 存在强{direction}（系数 {coefficient:.3f}）。"
                  f"该关系{significance}（p={p_value:.4f}）。建议进一步分析因果关系。",
        "中": f"{metric_a} 与 {metric_b} 存在中等{direction}（系数 {coefficient:.3f}）。"
                    f"该关系{significance}。值得持续监控趋势走向。",
        "弱": f"{metric_a} 与 {metric_b} 存在弱{direction}（系数 {coefficient:.3f}）。"
                f"这两个指标的线性关联有限。",
        "无": f"{metric_a} 与 {metric_b} 无明显相关性（系数 {coefficient:.3f}）。"
                f"这两个指标基本独立变动。",
    }
    return explanations.get(strength, "")


# ── Main analysis flow ──────────────────────────────────────

async def analyze_correlation(
    db: AsyncSession,
    metric_a: str,
    metric_b: str,
    method: str = "pearson",
    period_start: str | None = None,
    period_end: str | None = None,
    request_ai_explanation: bool = False,
    department: str | None = None,
) -> dict[str, Any]:
    """Run correlation analysis between two metrics and persist the result."""
    data_a = await _fetch_metric_values(db, metric_a, period_start, period_end, department)
    data_b = await _fetch_metric_values(db, metric_b, period_start, period_end, department)

    # Align on common periods
    periods_a = {p: v for p, v in data_a}
    common_periods = sorted(set(periods_a.keys()) & {p for p, _ in data_b})

    if len(common_periods) < 3:
        raise BusinessError(
            f"Insufficient overlapping data points ({len(common_periods)}). "
            f"Need at least 3 common periods for correlation analysis."
        )

    x = [periods_a[p] for p in common_periods]
    periods_b = {p: v for p, v in data_b}
    y = [periods_b[p] for p in common_periods]

    if method == "spearman":
        coefficient, p_value, sample_size = spearman_correlation(x, y)
    else:
        coefficient, p_value, sample_size = pearson_correlation(x, y)

    strength = classify_strength(coefficient)

    ai_explanation = None
    if request_ai_explanation:
        ai_explanation = await _ai_explain(metric_a, metric_b, coefficient, p_value, strength)

    # Persist result
    result = CorrelationResult(
        metric_a=metric_a,
        metric_b=metric_b,
        coefficient=coefficient,
        p_value=p_value,
        sample_size=sample_size,
        period_start=common_periods[0] if common_periods else None,
        period_end=common_periods[-1] if common_periods else None,
    )
    db.add(result)
    await db.flush()

    return {
        "id": result.id,
        "metric_a": metric_a,
        "metric_b": metric_b,
        "coefficient": coefficient,
        "p_value": p_value,
        "sample_size": sample_size,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "strength": strength,
        "ai_explanation": ai_explanation,
        "computed_at": result.computed_at,
    }
