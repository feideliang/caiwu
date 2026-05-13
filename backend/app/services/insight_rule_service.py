"""Rule-based insight generation from CoreMetricsResponse."""

from __future__ import annotations

from app.schemas.metrics import CoreMetricsResponse


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


class InsightRuleService:
    """Generate rule-based insights from aggregated metrics."""

    @staticmethod
    def generate_insights(
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
            if gm < 10:
                insights.append(_build_insight(
                    rule_code="GROSS_MARGIN_SEVERE_LOW",
                    insight_type="anomaly",
                    title="毛利率严重偏低预警",
                    description=f"当前毛利率 {gm:.2f}% 低于 10% 阈值，存在严重盈利能力风险。",
                    severity="high",
                    related_metric="gross_margin",
                    metric_value=gm,
                    threshold=10,
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="gross_margin",
                ))
            elif gm < 20:
                insights.append(_build_insight(
                    rule_code="GROSS_MARGIN_LOW",
                    insight_type="anomaly",
                    title="毛利率偏低提示",
                    description=f"当前毛利率 {gm:.2f}% 低于 20% 阈值，建议关注成本结构。",
                    severity="medium",
                    related_metric="gross_margin",
                    metric_value=gm,
                    threshold=20,
                    period=period,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    drill_type="gross_margin",
                ))
            elif gm > 60:
                insights.append(_build_insight(
                    rule_code="GROSS_MARGIN_HIGH",
                    insight_type="review",
                    title="毛利率异常偏高复核",
                    description=f"当前毛利率 {gm:.2f}% 高于 60%，建议核对成本归集是否完整。",
                    severity="medium",
                    related_metric="gross_margin",
                    metric_value=gm,
                    threshold=60,
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
                    description=f"近 3 个月营业收入环比连续为正（{rev_moms[0]:.1f}%、{rev_moms[1]:.1f}%、{rev_moms[2]:.1f}%）。",
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
                    description=f"近 3 个月毛利润环比连续为正（{gp_moms[0]:.1f}%、{gp_moms[1]:.1f}%、{gp_moms[2]:.1f}%）。",
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
        # Check individual customer share > 30% when breakdowns provided
        total_rev = summary.revenue or 0
        if customer_breakdowns and total_rev:
            for b in customer_breakdowns:
                b_rev = getattr(b, "revenue", None) if not isinstance(b, dict) else b.get("revenue")
                b_name = getattr(b, "dimension_value", None) if not isinstance(b, dict) else b.get("dimension_value")
                if b_rev is None or not b_name:
                    continue
                share = b_rev / total_rev * 100
                if share > 30:
                    insights.append(_build_insight(
                        rule_code="CUSTOMER_CONCENTRATION",
                        insight_type="concentration",
                        title="客户集中度过高",
                        description=f"客户 {b_name} 营收占比 {share:.2f}%，超过 30% 阈值，存在客户集中度风险。",
                        severity="high",
                        related_metric="customer_concentration",
                        metric_value=share,
                        threshold=30,
                        period=period,
                        dimension="customer",
                        dimension_value=str(b_name),
                        drill_type="customer",
                    ))
                    break
        elif cust_top3 is not None and cust_top3 > 60:
            insights.append(_build_insight(
                rule_code="CUSTOMER_CONCENTRATION",
                insight_type="concentration",
                title="客户集中度过高",
                description=f"Top3 客户营收占比 {cust_top3:.2f}%，可能存在单一客户占比超 30% 的风险。",
                severity="high",
                related_metric="customer_concentration_top3",
                metric_value=cust_top3,
                threshold=30,
                period=period,
                dimension=dimension,
                dimension_value=dimension_value,
                drill_type="customer",
            ))

        prod_top3 = summary.product_concentration_top3
        # Check individual product_line gross_profit contribution > 40% when breakdowns provided
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
                if share > 40:
                    insights.append(_build_insight(
                        rule_code="PRODUCT_CONCENTRATION",
                        insight_type="concentration",
                        title="产品线集中度过高",
                        description=f"产品线 {b_name} 毛利贡献 {share:.2f}%，超过 40% 阈值，存在产品集中度风险。",
                        severity="high",
                        related_metric="product_concentration",
                        metric_value=share,
                        threshold=40,
                        period=period,
                        dimension="product_line",
                        dimension_value=str(b_name),
                        drill_type="product_line",
                    ))
                    break
        elif prod_top3 is not None and prod_top3 > 70:
            insights.append(_build_insight(
                rule_code="PRODUCT_CONCENTRATION",
                insight_type="concentration",
                title="产品线集中度过高",
                description=f"Top3 产品线毛利贡献 {prod_top3:.2f}%，可能存在单一产品线占比超 40% 的风险。",
                severity="high",
                related_metric="product_concentration_top3",
                metric_value=prod_top3,
                threshold=40,
                period=period,
                dimension=dimension,
                dimension_value=dimension_value,
                drill_type="product_line",
            ))

        return insights
