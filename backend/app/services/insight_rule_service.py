"""Rule-based insight generation from CoreMetricsResponse.

Thresholds are read dynamically from rule_config (Redis → DB → hardcoded fallback)
so that rule changes propagate without code deployment.
"""

from __future__ import annotations

from app.schemas.metrics import CoreMetricsResponse
from app.services.rule_config import get_rule_config, format_threshold_description


def _drill_params(metric: str, period: str | None, dimension: str, rule_code: str) -> dict:
    return {
        "metric": metric,
        "period": period,
        "dimension": "department" if dimension == "company" else dimension,
        "rule_code": rule_code,
    }


def _build_insight(
    rule_code: str,
    insight_type: str,
    title: str,
    description: str,
    severity: str,
    related_metric: str,
    metric_value: float | None,
    threshold: float | None,
    period: str | None,
    dimension: str,
    dimension_value: str,
    drill_type: str,
) -> dict:
    return {
        "id": f"rule:{rule_code}:{dimension_value}:{period}",
        "type": insight_type,
        "title": title,
        "description": description,
        "severity": severity,
        "confidence": 1.0,
        "status": "unread",
        "related_metric": related_metric,
        "data_json": {
            "source": "rules",
            "rule_code": rule_code,
            "period": period,
            "metric_name": related_metric,
            "metric_value": metric_value,
            "threshold": threshold,
            "dimension": dimension,
            "dimension_value": dimension_value,
            "drill_type": drill_type,
            "drill_level": 1,
            "drill_params": _drill_params(drill_type, period, dimension, rule_code),
        },
    }


# ── Dynamic threshold helpers ────────────────────────────────

_DEFAULT_ENGINE_RULES: dict[str, dict] = {
    "GROSS_MARGIN_SEVERE_LOW": {"threshold": 10, "severity": "high"},
    "GROSS_MARGIN_LOW": {"threshold": 20, "severity": "medium"},
    "GROSS_MARGIN_HIGH": {"threshold": 60, "severity": "medium"},
    "REVENUE_TREND_UP": {"threshold": 0, "severity": "low"},
    "GROSS_PROFIT_TREND_UP": {"threshold": 0, "severity": "low"},
    "CUSTOMER_CONCENTRATION": {"threshold": 10, "severity": "high"},
    "CUSTOMER_CONCENTRATION_TOP3": {"threshold": 60, "severity": "high"},
    "PRODUCT_CONCENTRATION": {"threshold": 40, "severity": "high"},
    "PRODUCT_CONCENTRATION_TOP3": {"threshold": 70, "severity": "high"},
}


async def _rule_cfg(rule_code: str) -> dict:
    """Get threshold + severity for a rule code.

    Uses get_rule_config (async Redis/DB) and falls back to engine defaults.
    """
    cfg = await get_rule_config(rule_code)
    if cfg:
        return cfg
    return _DEFAULT_ENGINE_RULES.get(rule_code, {"threshold": None, "severity": "medium"})


class InsightRuleService:
    """Generate rule-based insights from aggregated metrics."""

    @staticmethod
    async def generate_insights(
        metrics: CoreMetricsResponse,
        customer_breakdowns: list | None = None,
        product_breakdowns: list | None = None,
    ) -> list[dict]:
        insights: list[dict] = []
        period = metrics.period
        dimension = metrics.dimension or "company"
        dimension_value = metrics.entity or "company"
        summary = metrics.summary

        gm = summary.gross_margin
        if gm is not None:
            if gm < (await _rule_cfg("GROSS_MARGIN_SEVERE_LOW"))["threshold"]:
                cfg = await _rule_cfg("GROSS_MARGIN_SEVERE_LOW")
                insights.append(_build_insight(
                    rule_code="GROSS_MARGIN_SEVERE_LOW",
                    insight_type="anomaly",
                    title="毛利率严重偏低预警",
                    description=f"当前毛利率 {gm:.2f}%，{format_threshold_description('GROSS_MARGIN_SEVERE_LOW', cfg['threshold'])}，存在严重盈利能力风险。",
                    severity=cfg["severity"],
                    related_metric="gross_margin",
                    metric_value=gm,
                    threshold=cfg["threshold"],
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="gross_margin",
                ))
            elif gm < (await _rule_cfg("GROSS_MARGIN_LOW"))["threshold"]:
                cfg = await _rule_cfg("GROSS_MARGIN_LOW")
                insights.append(_build_insight(
                    rule_code="GROSS_MARGIN_LOW",
                    insight_type="anomaly",
                    title="毛利率偏低提示",
                    description=f"当前毛利率 {gm:.2f}%，{format_threshold_description('GROSS_MARGIN_LOW', cfg['threshold'])}，建议关注成本结构。",
                    severity=cfg["severity"],
                    related_metric="gross_margin",
                    metric_value=gm,
                    threshold=cfg["threshold"],
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="gross_margin",
                ))
            elif gm > (await _rule_cfg("GROSS_MARGIN_HIGH"))["threshold"]:
                cfg = await _rule_cfg("GROSS_MARGIN_HIGH")
                insights.append(_build_insight(
                    rule_code="GROSS_MARGIN_HIGH",
                    insight_type="review",
                    title="毛利率异常偏高复核",
                    description=f"当前毛利率 {gm:.2f}%，{format_threshold_description('GROSS_MARGIN_HIGH', cfg['threshold'])}，建议核对成本归集是否完整。",
                    severity=cfg["severity"],
                    related_metric="gross_margin",
                    metric_value=gm,
                    threshold=cfg["threshold"],
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="gross_margin",
                ))

        # Trend insights: 3 consecutive positive MoM
        trend = metrics.trend_series or []
        if len(trend) >= 3:
            last3 = trend[-3:]
            rev_moms = [t.revenue_mom_growth for t in last3]
            if all(v is not None and v > 0 for v in rev_moms):
                insights.append(_build_insight(
                    rule_code="REVENUE_TREND_UP",
                    insight_type="trend",
                    title="营业收入持续上升",
                    description=f"近 3 个月营业收入环比连续为正（{rev_moms[0]:.2f}%、{rev_moms[1]:.2f}%、{rev_moms[2]:.2f}%）。",
                    severity="low",
                    related_metric="revenue",
                    metric_value=rev_moms[-1],
                    threshold=0,
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="revenue",
                ))
            gp_moms = [t.gross_profit_mom_growth for t in last3]
            if all(v is not None and v > 0 for v in gp_moms):
                insights.append(_build_insight(
                    rule_code="GROSS_PROFIT_TREND_UP",
                    insight_type="trend",
                    title="毛利润持续上升",
                    description=f"近 3 个月毛利润环比连续为正（{gp_moms[0]:.2f}%、{gp_moms[1]:.2f}%、{gp_moms[2]:.2f}%）。",
                    severity="low",
                    related_metric="gross_profit",
                    metric_value=gp_moms[-1],
                    threshold=0,
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="gross_profit",
                ))

        cust_top3 = summary.customer_concentration_top3
        total_rev = summary.revenue or 0
        cust_cfg = await _rule_cfg("CUSTOMER_CONCENTRATION")
        cust_top3_cfg = await _rule_cfg("CUSTOMER_CONCENTRATION_TOP3")
        if customer_breakdowns and total_rev:
            for b in customer_breakdowns:
                b_rev = getattr(b, "revenue", None) if not isinstance(b, dict) else b.get("revenue")
                b_name = getattr(b, "dimension_value", None) if not isinstance(b, dict) else b.get("dimension_value")
                if b_rev is None or not b_name:
                    continue
                share = b_rev / total_rev * 100
                if share > cust_cfg["threshold"]:
                    insights.append(_build_insight(
                        rule_code="CUSTOMER_CONCENTRATION",
                        insight_type="concentration",
                        title="客户集中度过高",
                        description=f"客户 {b_name} 营收占比 {share:.2f}%，{format_threshold_description('CUSTOMER_CONCENTRATION', cust_cfg['threshold'])}，存在客户集中度风险。",
                        severity=cust_cfg["severity"],
                        related_metric="customer_concentration",
                        metric_value=share,
                        threshold=cust_cfg["threshold"],
                        period=period,
                        dimension="customer",
                        dimension_value=str(b_name),
                        drill_type="customer",
                    ))
                    break
        elif cust_top3 is not None and cust_top3 > cust_top3_cfg["threshold"]:
            insights.append(_build_insight(
                rule_code="CUSTOMER_CONCENTRATION",
                insight_type="concentration",
                title="客户集中度过高",
                description=f"Top3 客户营收占比 {cust_top3:.2f}%，可能存在单一客户占比超 {cust_top3_cfg['threshold']:.0f}% 的风险。",
                severity=cust_top3_cfg["severity"],
                related_metric="customer_concentration_top3",
                metric_value=cust_top3,
                threshold=cust_top3_cfg["threshold"],
                period=period,
                dimension=dimension,
                dimension_value=dimension_value,
                drill_type="customer",
            ))

        prod_top3 = summary.product_concentration_top3
        prod_cfg = await _rule_cfg("PRODUCT_CONCENTRATION")
        prod_top3_cfg = await _rule_cfg("PRODUCT_CONCENTRATION_TOP3")
        total_gp = sum(
            (getattr(b, "gross_profit", None) if not isinstance(b, dict) else b.get("gross_profit")) or 0
            for b in (product_breakdowns or [])
        )
        if product_breakdowns and total_gp:
            for b in product_breakdowns:
                b_gp = getattr(b, "gross_profit", None) if not isinstance(b, dict) else b.get("gross_profit")
                b_name = getattr(b, "dimension_value", None) if not isinstance(b, dict) else b.get("dimension_value")
                if b_gp is None or not b_name:
                    continue
                share = b_gp / total_gp * 100
                if share > prod_cfg["threshold"]:
                    insights.append(_build_insight(
                        rule_code="PRODUCT_CONCENTRATION",
                        insight_type="concentration",
                        title="产品线集中度过高",
                        description=f"产品线 {b_name} 毛利贡献 {share:.2f}%，{format_threshold_description('PRODUCT_CONCENTRATION', prod_cfg['threshold'])}，存在产品集中度风险。",
                        severity=prod_cfg["severity"],
                        related_metric="product_concentration",
                        metric_value=share,
                        threshold=prod_cfg["threshold"],
                        period=period,
                        dimension="product_bgbu",
                        dimension_value=str(b_name),
                        drill_type="product_bgbu",
                    ))
                    break
        elif prod_top3 is not None and prod_top3 > prod_top3_cfg["threshold"]:
            insights.append(_build_insight(
                rule_code="PRODUCT_CONCENTRATION",
                insight_type="concentration",
                title="产品线集中度过高",
                description=f"Top3 产品线毛利贡献 {prod_top3:.2f}%，可能存在单一产品线占比超 {prod_top3_cfg['threshold']:.0f}% 的风险。",
                severity=prod_top3_cfg["severity"],
                related_metric="product_concentration_top3",
                metric_value=prod_top3,
                threshold=prod_top3_cfg["threshold"],
                period=period,
                dimension=dimension,
                dimension_value=dimension_value,
                drill_type="product_bgbu",
            ))

        return insights