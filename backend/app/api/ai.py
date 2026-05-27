"""AI endpoints: chart recommendation, layout recommendation, and attribution analysis."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import decode_access_token, TokenPayload, get_current_user
from app.db.session import get_db
from app.models.core import AggDimensionSummary, AggPeriodSummary
from app.schemas.ai import (
    ChartRecommendRequest,
    ChartRecommendResponse,
    LayoutRecommendRequest,
    LayoutRecommendResponse,
    ChatRequest,
    ChatResponse,
    ChatContext,
    ChatReference,
)
from app.schemas.analysis import AnalysisRecommendationRequest
from app.services.chart_recommend import recommend_charts, recommend_layout
from app.config import settings

import re

router = APIRouter(prefix="/ai", tags=["ai"])


def get_optional_user(request: Request) -> TokenPayload | None:
    """Try to extract JWT user from Authorization header; return None if not authenticated."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return TokenPayload.model_validate(decode_access_token(auth_header.split(" ", 1)[1]))
    except Exception:
        return None


@router.post("/recommend/chart", response_model=APIResponse)
async def recommend_chart(
    body: ChartRecommendRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """AI-powered chart type recommendation based on data characteristics.

    Uses rule-based pre-screening followed by scoring to rank chart types
    by suitability for the given dataset.
    """
    result = await recommend_charts(body)
    return APIResponse.success(data=result.model_dump())


@router.post("/recommend/layout", response_model=APIResponse)
async def recommend_layout_endpoint(
    body: LayoutRecommendRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Recommend a grid layout for dashboard charts based on device type.

    Returns x/y/w/h positions for each chart in a responsive grid.
    """
    result = recommend_layout(body.chart_ids, body.device_type)
    return APIResponse.success(data=result)


async def _call_qwen_api(client: httpx.AsyncClient, settings, prompt: str) -> str | None:
    """Call Qwen API and return the answer text, or None on failure."""
    resp = await client.post(
        f"{settings.qwen_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.qwen_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.qwen_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
        },
    )
    if resp.status_code == 200:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    logger.warning(f"Qwen API returned status {resp.status_code}")
    return None


@router.post("/analyze", response_model=APIResponse)
async def ai_analyze(
    metric: str = Body(..., description="Metric name to analyze"),
    period: str = Body(..., description="Period to analyze"),
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_optional_user),
) -> APIResponse:
    """AI-style attribution analysis for a given metric and period.

    Compares current period vs previous period and returns analysis text,
    attribution factors, and recommendations based on FinancialData.
    """
    # Map metric_name to aggregated table column; fallback for unknown metrics.
    metric_col_map = {"revenue": AggDimensionSummary.revenue, "cost": AggDimensionSummary.cost, "gross_profit": AggDimensionSummary.gross_profit}
    metric_col = metric_col_map.get(metric)

    # Determine bgbu filter for department scoping (same pattern as drilldowns.py)
    if _user and _user.role != "admin" and _user.department:
        bgbu_filter = _user.department
    else:
        bgbu_filter = "ALL"

    if metric_col is not None:
        # Use aggregated dimension summary table (dim_type='customer' for customer-level aggregation)
        curr_stmt = select(
            AggDimensionSummary.dim_value.label("entity"),
            metric_col.label("value"),
        ).where(
            AggDimensionSummary.period == period,
            AggDimensionSummary.dim_type == "customer",
            AggDimensionSummary.bgbu == bgbu_filter,
            AggDimensionSummary.dim_value.isnot(None),
            AggDimensionSummary.dim_value != "",
        )
        curr_result = await db.execute(curr_stmt)
        curr_rows = curr_result.all()
    else:
        # Unknown metric: no data source available (financial_data table is empty)
        curr_rows = []

    # Compute previous period (try monthly - 1 month, or quarterly - 1 quarter)
    prev_period = period
    if len(period) == 7:  # monthly format YYYY-MM
        year, month = int(period[:4]), int(period[5:7])
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        prev_period = f"{year}-{month:02d}"
    elif len(period) == 6 and "-" in period:  # quarterly YYYY-QN
        year, q = int(period[:4]), int(period[5])
        q -= 1
        if q == 0:
            q = 4
            year -= 1
        prev_period = f"{year}-Q{q}"

    if metric_col is not None:
        # Use aggregated dimension summary table for previous period
        prev_stmt = select(
            AggDimensionSummary.dim_value.label("entity"),
            metric_col.label("value"),
        ).where(
            AggDimensionSummary.period == prev_period,
            AggDimensionSummary.dim_type == "customer",
            AggDimensionSummary.bgbu == bgbu_filter,
            AggDimensionSummary.dim_value.isnot(None),
            AggDimensionSummary.dim_value != "",
        )
        prev_result = await db.execute(prev_stmt)
        prev_rows = prev_result.all()
    else:
        # Unknown metric: no data source available (financial_data table is empty)
        prev_rows = []

    # Build maps
    curr_map = {r.entity: r.value for r in curr_rows}
    prev_map = {r.entity: r.value for r in prev_rows}
    all_entities = set(curr_map.keys()) | set(prev_map.keys())

    # Compute total values
    curr_total = sum(curr_map.values())
    prev_total = sum(prev_map.values()) if prev_map else 0
    total_change = ((curr_total - prev_total) / prev_total * 100) if prev_total else 0

    # Attribution by entity
    attribution = []
    for entity in sorted(all_entities):
        curr_val = curr_map.get(entity, 0)
        prev_val = prev_map.get(entity, 0)
        if prev_val:
            change = ((curr_val - prev_val) / prev_val) * 100
        elif curr_val:
            change = 100
        else:
            change = 0
        contribution = (curr_val - prev_val) / (curr_total - prev_total) * 100 if (curr_total - prev_total) != 0 else 0
        attribution.append({
            "factor": f"{entity}",
            "contribution": f"{change:+.1f}%",
            "abs_contribution": f"{contribution:+.1f}%",
        })

    # Sort by absolute contribution
    attribution.sort(key=lambda x: abs(float(x["abs_contribution"].rstrip("%+").rstrip("-"))), reverse=True)

    # Try AI-powered analysis if Qwen API is configured
    ai_analysis_text = None
    ai_recommendation = None
    if settings.qwen_api_key:
        try:
            import httpx
            prompt = (
                f"财务分析任务：分析 {metric} 指标在 {period} 期间的表现。\n\n"
                f"数据概览：\n"
                f"- 本期数值：{curr_total:.2f}\n"
                f"- 上期数值：{(prev_total if prev_total else 0):.2f}\n"
                f"- 变化幅度：{total_change:+.1f}%\n\n"
                f"各维度贡献（按影响排序）：\n"
            )
            for a in attribution[:5]:
                prompt += f"- {a['factor']}: 变化 {a['contribution']}，贡献 {a['abs_contribution']}\n"

            prompt += (
                f"\n请生成：\n"
                f"1. 一段2-3句的深度分析（中文），解释变化原因和业务含义\n"
                f"2. 一条具体建议（1句，中文）\n\n"
                f"格式：\nanalysis: <分析文本>\nrecommendation: <建议文本>"
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{settings.qwen_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.qwen_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.qwen_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 300,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    # Parse response with regex for flexibility
                    analysis_match = re.search(r"(?:analysis|分析)[\s:：]*(.+)", content, re.IGNORECASE)
                    rec_match = re.search(r"(?:recommendation|recommend|建议)[\s:：]*(.+)", content, re.IGNORECASE)
                    if analysis_match:
                        ai_analysis_text = analysis_match.group(1).strip()
                    if rec_match:
                        ai_recommendation = rec_match.group(1).strip()
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}", exc_info=True)

    # Fall back to rule-based if AI fails
    if not ai_analysis_text:
        direction = "增长" if total_change > 0 else "下降"
        analysis_parts = [f"{period} {metric} 较上期({prev_period}){direction} {abs(total_change):.2f}%，"]
        if attribution:
            top_driver = attribution[0]
            analysis_parts.append(f"主要由 {top_driver['factor']} 驱动，贡献 {top_driver['contribution']}。")
        ai_analysis_text = "".join(analysis_parts)

    if not ai_recommendation:
        if abs(total_change) > 10:
            ai_recommendation = f"建议关注 {metric} 变化趋势，环比变动达 {abs(total_change):.1f}%，需进一步分析原因。"
        elif attribution and float(attribution[0]['contribution'].rstrip('%+')) < 0:
            driver = attribution[0]['factor']
            ai_recommendation = f"建议关注 {driver} 情况，其对 {metric} 的下降贡献最大，建议检查相关业务因素。"
        else:
            ai_recommendation = f"{metric} 变化在正常范围内，建议持续监控。"

    return APIResponse.success(data={
        "metric": metric,
        "period": period,
        "analysis": ai_analysis_text,
        "attribution": attribution,
        "recommendation": ai_recommendation,
    })


# ── AI Chat / Smart Q&A ───────────────────────────────────────

logger = logging.getLogger(__name__)

_KNOWLEDGE_BASE_RULES = (
    "【业务规则知识库】\n"

    # ── 指标公式 ──
    "--- 核心指标公式 ---\n"
    "毛利率 = (收入 - 不含税成本) / 收入 × 100%\n"
    "毛利额 = 收入 - 不含税成本\n"
    "毛利率贡献度 = 某维度毛利额 / 总毛利额 × 100%\n"
    "收入贡献度 = 某维度收入 / 总收入 × 100%\n"
    "客户集中度 = 前三大客户收入 / 总收入 × 100%\n"
    "产品集中度 = 前三大产品线毛利 / 总毛利 × 100%\n"
    "亏损订单占比 = 毛利率为负的订单数 / 总订单数 × 100%\n"
    "亏损产品占比 = 毛利率为负的产品数 / 总产品数 × 100%\n"
    "高毛利订单占比 = 毛利率 > 40% 的订单数 / 总订单数 × 100%\n"
    "同比增长率 = (本期 - 去年同期) / 去年同期 × 100%\n"
    "毛利率变化拆解(每个维度)：结构影响 = (当期收入占比 - 基期收入占比) × 基期毛利率 / 100；毛利变化影响 = 当期收入占比 × (当期毛利率 - 基期毛利率) / 100；合计 = 结构影响 + 毛利变化影响\n"
    "收入/毛利额变动影响：各维度(当期值 - 基期值) / 总变化绝对值，累计贡献80%的为主要变动因素\n"

    # ── 异常阈值 ──
    "--- 异常检测阈值 ---\n"
    "毛利率 < 20%：一般异常，需纳入常规审视\n"
    "毛利率 < 10%：严重异常，必须立即启动下钻分析，排查定价失误、成本异常或特殊竞争性项目\n"
    "毛利率 > 60%：需分析确认是技术领先带来的溢价还是偶然性项目，判断成功模式是否可复制\n"
    "单一客户销售收入占比 > 10%：触发客户集中度风险预警\n"
    "前三大客户集中度 > 60%：客户集中度过高，需关注\n"
    "单一产品系列毛利贡献占比 > 40%：触发产品集中度风险预警\n"
    "前三大产品线毛利集中度 > 70%：产品集中度过高，需培育第二增长曲线\n"
    "高毛利订单阈值：毛利率 > 40% 的订单为优质高毛利订单\n"
    "亏损定义：毛利率为负的订单/产品为亏损\n"

    # ── 趋势规则 ──
    "--- 趋势分析规则 ---\n"
    "任一销售部门或产品事业部的收入或毛利额连续三个月实现环比正增长 → 上升趋势，需总结驱动因素\n"
    "同比分析：排除季节性影响，评估长期趋势和年度战略效果，必须对比相同自然月或季度\n"
    "环比分析：监控短期业务波动和月度执行异常，注意月末、季末冲量行为对数据的扰动\n"
    "累计分析：评估年度目标达成进度，若累计毛利率低于时间进度要求，为下半年定价调整或成本优化提供依据\n"

    # ── 下钻路径 ──
    "--- 下钻分析路径 ---\n"
    "第一层：公司整体层面，观察收入规模、毛利额及毛利率是否达成预期\n"
    "第二层：组织与时间维度下钻，定位异常部门或产品事业部\n"
    "第三层：客户与产品维度交叉分析，分析客户签约类型或物料成本大类×产品系列\n"
    "第四层：交易与项目维度根因定位，穿透至订单分类、项目名称、关键客户\n"
    "产品钻取路径：产品线(product_line) → 销售产品名称(sales_product_name)\n"

    # ── 可用的分析维度字段 ──
    "--- 数据维度说明（financial_data tags JSON字段）---\n"
    "组织维度：department(市场线:CBG/EBG/SBG/TBU), sales_department(销售部门), hr_department(HR部门), hr_dept_code\n"
    "产品维度：product_line(产品线), series(产品系列), product_category(产品大类), product_classification(产品分类), product_family(产品族), product_bu_name(产品事业部名称), product_bu_code(产品事业部代码), product_org(产品所属组织), product_bgbu(产品归属BGBU)\n"
    "销售产品维度：sales_product_code(销售产品代码), sales_product_name(销售产品名称), material_code(物料编码), material_desc(物料描述), material_cost_category(物料成本大类)\n"
    "成本分类维度：cost_class_1(一级成本分类), cost_class_2(二级成本分类), cost_class_3(三级成本分类), cost_category(成本大类)\n"
    "客户维度：customer(客户), ncc_customer_code(NCC客户编码), order_customer(订单客户), invoice_customer(开票客户简称), invoice_name(开票名称), final_customer(最终客户名称), superior_name(上级名称), contract_type(客户签约类型:直签/渠道)\n"
    "订单维度：order_id(订单编号), contract_no(合同编号), order_header_type(订单头类型), order_category(订单分类), sales_type(内销/外销)\n"
    "地理维度：province(省份), market_segment(细分市场), application_scenario(应用场合), project_name(项目名称)\n"
    "财务维度：currency(币种), exchange_rate(汇率), tax_rate(税率), order_qty(订单数量), unit_cost_ex_tax(不含税单位成本), unit_cost_incl_tax(含税单位成本)\n"
    "期间维度：period 支持 monthly(月度, YYYY-MM)、quarterly(季度, YYYY-Qn)、cumulative(年累计至所选月, YYYY-MM)、custom(自定义期间)\n"
    "比较类型：yoy(同比,上年同期), mom(环比,上月), cumulative(累计)\n"

    # ── 分析页面业务逻辑 ──
    "--- 总览驾驶舱 ---\n"
    "核心KPI：营业收入、营业成本、毛利额、毛利率+同比变化值\n"
    "趋势图：月度趋势(收入/成本/毛利额柱线+毛利率次坐标轴)\n"
    "智能洞察：基于KPI和阈值的规则化告警信息\n"

    "--- 变动分析 ---\n"
    "三大模块：收入变动、毛利额变动、毛利率变动，均对比基期(同期/上月)\n"
    "收入变动：当期收入/基期收入/变化比例 + 主要变动影响(各维度贡献累计80%的为主要因素)\n"
    "毛利额变动：当期毛利额/基期毛利额/变化比例 + 主要变动影响\n"
    "毛利率变动：当期毛利率/基期毛利率/变化值(pp) + 存续结构影响 + 存续毛利影响 + 新增影响 + 退出影响\n"
    "毛利率拆解规则：维度需区分存续/新增/退出；结构影响=(w1-w0)*g0，毛利影响=w1*(g1-g0)；新增/退出缺失毛利率时用整体毛利率补基准\n"
    "集中度排名：收入/毛利额/毛利率三个指标并行展示维度排名\n"

    "--- 部门分析 ---\n"
    "维度：department, 按销售部门(市场线)分析收入和毛利\n"
    "KPI：营业收入、毛利额、毛利率、亏损订单占比\n"
    "图表：收入分布饼图 + 部门收入毛利率对比( grouped-bar双轴)\n"
    "明细列：收入贡献度、毛利贡献度、负毛利订单数量、负毛利金额\n"

    "--- 产品分析 ---\n"
    "维度：product_line, 按产品线分析收入和毛利\n"
    "KPI：收入、毛利额、毛利率、亏损产品占比\n"
    "图表：产品收入排行(bar) + 产品线收入毛利对比(grouped-bar) + 毛利率分布(pie) + 收入毛利气泡图(scatter)\n"
    "钻取：点击产品线可下钻到sales_product_name层级，查看具体销售产品明细\n"
    "明细列：收入贡献度、毛利贡献度、负毛利产品数量、负毛利金额\n"

    "回答时必须引用上述规则，用阈值判断数据是否异常，给出下钻方向和业务建议。\n"
    "数据来源于financial_data表，每条记录包含metric_name(revenue/cost/gross_profit/profit_margin)和metric_value。\n"
)


async def _get_rules_for_question(question: str) -> str:
    """RAG retrieval: fetch relevant rules from Qdrant. Fallback to hardcoded."""
    # Skip RAG for very short or non-financial questions
    if len(question.strip()) < 3:
        return ""
    if not _is_financial_question(question):
        return ""

    try:
        from app.services.rule_retrieval import retrieve_rules
        rules_text = await retrieve_rules(question)
        if rules_text:
            return (
                f"【业务规则知识库】\n{rules_text}\n"
                f"回答时必须引用上述规则，用阈值判断数据是否异常，给出下钻方向。\n"
            )
    except Exception as e:
        logger.warning(f"Rule retrieval failed, using hardcoded rules: {e}")
    return _KNOWLEDGE_BASE_RULES


def _get_page_suggestions(
    kpis: dict,
    dept_items: list[dict],
    prod_items: list[dict],
    active_section: str,
    page_type: str | None = None,
    customer_items: list[dict] | None = None,
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


_REVENUE_KW = ("revenue", "营业收入", "sales")
_COST_KW = ("cost", "成本", "expense")
_PROFIT_KW = ("gross_profit", "毛利润", "gross profit")


def _safe_div(num: float, den: float) -> float | None:
    if not den:
        return None
    return num / den


def _build_bi_context(kpis: dict, dept_items: list[dict], prod_items: list[dict]) -> str:
    """Build a structured BI context string from dashboard data."""
    lines = ["当前 BI 页面数据上下文："]

    # Overview
    k = kpis
    lines.append(f"\n【总览】")
    lines.append(f"  营业收入：{(k.get('revenue') or 0):,.0f} 元")
    lines.append(f"  毛利额：{(k.get('gross_profit') or 0):,.0f} 元")
    lines.append(f"  毛利率：{(k.get('gross_margin') or 0):.2f}%")
    lines.append(f"  达成率：{(k.get('achievement_rate') or 0):.2f}%")
    lines.append(f"  收入环比：{(k.get('revenue_mom_growth') or 0):+.2f}%")
    lines.append(f"  毛利环比：{(k.get('profit_mom_growth') or 0):+.2f}%")

    # Department breakdown
    if dept_items:
        lines.append(f"\n【部门维度】（按收入排序，Top {min(len(dept_items), 5)}）")
        for item in dept_items[:5]:
            lines.append(
                f"  {item['dimension_value']}: 收入 {(item.get('revenue') or 0):,.0f}, "
                f"毛利 {(item.get('gross_profit') or 0):,.0f}, "
                f"毛利率 {(item.get('gross_margin') or 0):.2f}%"
            )

    # Product breakdown
    if prod_items:
        lines.append(f"\n【产品维度】（按毛利贡献排序，Top {min(len(prod_items), 5)}）")
        for item in prod_items[:5]:
            lines.append(
                f"  {item['dimension_value']}: 收入 {(item.get('revenue') or 0):,.0f}, "
                f"毛利 {(item.get('gross_profit') or 0):,.0f}, "
                f"毛利率 {(item.get('gross_margin') or 0):.2f}%, "
                f"贡献度 {(item.get('gross_margin_contribution') or 0):.2f}%"
            )

    return "\n".join(lines)


def _generate_rule_based_answer(question: str, kpis: dict, dept_items: list[dict], prod_items: list[dict], context: ChatContext | None) -> dict:
    """Generate a rule-based answer when AI model is not available."""
    q = question.lower()
    active_section = context.active_section if context else ""
    suggestions = _get_page_suggestions(kpis, dept_items, prod_items, active_section)

    # Summary questions
    if any(kw in q for kw in ["总结", "经营情况", "概况", "overall"]):
        rev = (kpis.get('revenue') or 0)
        gp = (kpis.get('gross_profit') or 0)
        gm = (kpis.get('gross_margin') or 0)
        ach = (kpis.get('achievement_rate') or 0)
        rev_growth = (kpis.get('revenue_mom_growth') or 0)
        answer = f"本期经营概况：营业收入 {rev:,.0f} 元（环比 {rev_growth:+.2f}%），毛利额 {gp:,.0f} 元，毛利率 {gm:.2f}%，达成率 {ach:.2f}%。"
        if 0 < gm < 20:
            answer += f"毛利率低于20%一般异常阈值，建议进一步分析。"
        elif 0 < gm < 10:
            answer += f"毛利率低于10%严重异常阈值，必须立即启动下钻分析。"
        elif gm > 60:
            answer += f"毛利率高于60%，需验证是技术溢价还是偶然性项目。"
        return {
            "answer": answer,
            "suggestions": suggestions,
            "references": [
                {"type": "metric", "label": "营业收入", "value": rev},
                {"type": "metric", "label": "毛利率", "value": gm},
            ],
        }

    # Gross margin questions
    if any(kw in q for kw in ["毛利率", "gross margin", "margin"]):
        gm = (kpis.get('gross_margin') or 0)
        rev_growth = (kpis.get('revenue_mom_growth') or 0)
        gp_growth = (kpis.get('profit_mom_growth') or 0)
        gm_alert = ""
        if 0 < gm < 10:
            gm_alert = f"（低于10%严重异常线，必须下钻分析）"
        elif 0 < gm < 20:
            gm_alert = f"（低于20%一般异常线，需常规审视）"
        elif gm > 60:
            gm_alert = f"（高于60%，需验证可持续性）"

        if dept_items:
            top_dept = dept_items[0]
            low_dept = min(dept_items, key=lambda x: x.get('gross_margin') or 100)
            return {
                "answer": f"当前整体毛利率 {gm:.2f}%{gm_alert}。收入环比 {rev_growth:+.2f}%，毛利环比 {gp_growth:+.2f}%。部门中 {top_dept['dimension_value']} 收入最高（{(top_dept.get('revenue') or 0):,.0f} 元），{low_dept['dimension_value']} 毛利率最低（{(low_dept.get('gross_margin') or 0):.2f}%）。",
                "suggestions": suggestions,
                "references": [
                    {"type": "metric", "label": "毛利率", "value": gm},
                    {"type": "dimension", "label": "最高收入部门", "value": top_dept['dimension_value']},
                ],
            }
        return {
            "answer": f"当前整体毛利率 {gm:.2f}%{gm_alert}。收入环比 {rev_growth:+.2f}%，毛利环比 {gp_growth:+.2f}%。暂无部门维度详细数据。",
            "suggestions": suggestions,
            "references": [{"type": "metric", "label": "毛利率", "value": gm}],
        }

    # Department contribution questions
    if any(kw in q for kw in ["部门", "department", "贡献", "最高"]):
        if dept_items:
            top = dept_items[0]
            return {
                "answer": f"收入最高的部门是 {top['dimension_value']}，收入 {(top.get('revenue') or 0):,.0f} 元，毛利率 {(top.get('gross_margin') or 0):.2f}%。",
                "suggestions": suggestions,
                "references": [
                    {"type": "dimension", "label": "最高收入部门", "value": top['dimension_value']},
                    {"type": "metric", "label": "部门收入", "value": (top.get('revenue') or 0)},
                ],
            }
        return {
            "answer": "当前暂无部门维度数据。请确认数据源中是否包含部门信息。",
            "suggestions": suggestions,
            "references": [],
        }

    # Product line risk questions
    if any(kw in q for kw in ["产品", "product", "风险", "最低"]):
        if prod_items:
            low = min(prod_items, key=lambda x: x.get('gross_margin') or 100)
            top_contrib = prod_items[0] if prod_items else None
            return {
                "answer": f"毛利率最低的产品线是 {low['dimension_value']}（{(low.get('gross_margin') or 0):.2f}%）。" +
                          (f"毛利贡献最高的产品线是 {top_contrib['dimension_value']}（贡献 {(top_contrib.get('gross_margin_contribution') or 0):.2f}%）。" if top_contrib else ""),
                "suggestions": suggestions,
                "references": [
                    {"type": "dimension", "label": "最低毛利率产品线", "value": low['dimension_value']},
                    {"type": "metric", "label": "最低毛利率", "value": (low.get('gross_margin') or 0)},
                ],
            }
        return {
            "answer": "当前暂无产品维度数据。请确认数据源中是否包含产品信息。",
            "suggestions": suggestions,
            "references": [],
        }

    # Default fallback
    return {
        "answer": f"关于'{question}'，当前页面数据显示：营业收入 {(kpis.get('revenue') or 0):,.0f} 元，毛利率 {(kpis.get('gross_margin') or 0):.2f}%。如需更深入分析，请使用推荐的常见问题。",
        "suggestions": suggestions,
        "references": [
            {"type": "metric", "label": "营业收入", "value": (kpis.get('revenue') or 0)},
            {"type": "metric", "label": "毛利率", "value": (kpis.get('gross_margin') or 0)},
        ],
    }


@router.post("/chat", response_model=APIResponse)
async def ai_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_optional_user),
) -> APIResponse:
    """AI-powered financial Q&A based on current dashboard context.

    Accepts a question with optional BI context (period, department, product).
    Returns an answer with references to dashboard metrics.
    Falls back to rule-based analysis if no AI model is configured.
    """
    # Handle __init__ or empty/whitespace request FIRST — no DB queries needed
    if not body.question or not body.question.strip() or body.question.strip() == "__init__":
        return APIResponse.success(data={
            "answer": "",
            "suggestions": ["本月收入与毛利概况", "收入同比分析", "部门收入拆解"],
            "references": [],
        })

    # Fetch dashboard data for context (use context filters)
    from app.api.dashboard import _build_kpis

    ctx = body.context
    t0 = time.time()
    kpis = await _build_kpis(
        db,
        period_compare_type=ctx.period_compare_type if ctx else None,
        period_dimension=ctx.period_dimension if ctx else None,
        period=ctx.period if ctx else None,
        period_start=ctx.period_start if ctx else None,
        period_end=ctx.period_end if ctx else None,
        department=ctx.department if ctx else None,
        product=ctx.product if ctx else None,
    )
    # Skip expensive breakdown query — prompt only needs summary KPIs + RAG rules
    dept_items, prod_items = [], []

    # Fetch customer breakdown for customer-focused pages
    customer_items = []
    active_section = body.context.active_section if body.context else ""
    page_type_hint = body.context.page_type if hasattr(body.context, 'page_type') and body.context.page_type else ""
    if active_section in ("customer", "overview") or page_type_hint == "customer":
        from app.db.session import async_session_factory
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

    db_elapsed = time.time() - t0

    t1 = time.time()
    bi_context = _build_bi_context(kpis, dept_items, prod_items)
    logger.info(f"AI chat DB queries took {db_elapsed:.2f}s")

    # ── Qwen timing ─────────────────────────────────────────────
    t_qwen_start = time.time()

    t1 = time.time()
    context_note = ""
    if body.context:
        parts = []
        if body.context.period:
            parts.append(f"期间：{body.context.period}")
        if body.context.department:
            parts.append(f"部门：{body.context.department}")
        if body.context.product:
            parts.append(f"产品线：{body.context.product}")
        if body.context.period_compare_type:
            type_map = {"yoy": "同比", "mom": "环比", "cumulative": "累计"}
            parts.append(f"对比方式：{type_map.get(body.context.period_compare_type, body.context.period_compare_type)}")
        if parts:
            context_note = f"\n\n当前筛选条件：{'，'.join(parts)}"

    # Try AI model if configured
    ai_answer = None
    if settings.qwen_api_key:
        try:
            rules_text = await _get_rules_for_question(body.question)
            import httpx
            history_text = ""
            if body.history:
                history_text = "\n对话历史：\n"
                for msg in body.history[-4:]:
                    history_text += f"{msg.role}: {msg.content}\n"

            # Build the BI data section — only include if user is asking about financial data
            is_financial_question = any(kw in body.question.lower() for kw in [
                "收入", "毛利", "成本", "利润", "毛利率", "部门", "产品", "客户",
                "订单", "经营", "指标", "增长", "环比", "同比", "累计",
                "营收", "达成", "集中度", "风险", "异常", "分析", "贡献",
                "总结", "概况", "走势", "趋势", "预测", "dso", "ito",
                "revenue", "profit", "margin", "department", "product",
                "经营情况", "下钻", "拆解", "影响", "结构"
            ])

            if is_financial_question:
                # Build concise data section with all available data
                data_lines = []
                k = kpis
                rev = k.get("revenue") or 0
                gp = k.get("gross_profit") or 0
                gm = k.get("gross_margin") or 0
                base_rev = k.get("base_revenue")
                base_gp = k.get("base_gross_profit")
                base_gm = k.get("base_gross_margin")
                rev_yoy = k.get("revenue_yoy_growth")
                gp_yoy = k.get("profit_yoy_growth")
                gm_yoy_change = k.get("gross_margin_yoy_change")

                data_lines.append(f"营业收入: {rev:,.0f}元, 毛利率: {gm:.2f}%, 毛利额: {gp:,.0f}元, 达成率: {(k.get('achievement_rate') or 0):.2f}%")
                data_lines.append(f"收入环比: {(k.get('revenue_mom_growth') or 0):+.2f}%, 毛利环比: {(k.get('profit_mom_growth') or 0):+.2f}%")
                if rev_yoy is not None:
                    data_lines.append(f"收入同比: {rev_yoy:+.2f}%, 毛利同比: {gp_yoy:+.2f}%")
                if base_rev is not None:
                    data_lines.append(f"基期收入: {base_rev:,.0f}元, 基期毛利额: {base_gp:,.0f}元, 基期毛利率: {base_gm:.2f}%")
                if gm_yoy_change is not None:
                    data_lines.append(f"毛利率同比变化: {gm_yoy_change:+.2f}个百分点")
                if dept_items:
                    data_lines.append("部门: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in dept_items[:5]))
                if prod_items:
                    data_lines.append("产品: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in prod_items[:5]))
                data_section = "当前数据: " + "。".join(data_lines) + "。"
                data_section += "\n注意：请基于以上数据进行分析，不要编造数据。如果数据充分请给出具体分析，如果数据不足请说明具体缺少哪些维度的数据，避免笼统地说'无明细数据'。"

                system_role = (
                    f"你是财务分析助手。基于以下数据和规则回答。\n\n"
                    f"{data_section}{context_note}\n\n{rules_text}"
                )
            else:
                system_role = (
                    f"你是财务分析助手。如果问题与财务无关，用自然语言直接回答。\n\n{rules_text}"
                )

            prompt = (
                f"{system_role}\n\n{history_text}用户问题：{body.question}\n\n"
                f"要求：\n"
                f"1. 必须基于提供的数据和规则回答，不得编造\n"
                f"2. 中文回答，简洁专业\n"
                f"3. 数据不足时明确说明\n"
                f"4. 使用中文数字标题分段（一、二、三…）\n"
                f"5. 每个标题下按行列出指标，每行不超过15字，格式：指标名：数值\n"
                f"6. 异常、原因、建议分别成段，不要把所有内容挤成一段\n"
            )

            async with httpx.AsyncClient(timeout=60.0) as client:
                ai_answer = await _call_qwen_api(client, settings, prompt)
            logger.info(f"Qwen API success in {time.time()-t_qwen_start:.2f}s")
        except Exception as e:
            logger.warning(f"Qwen fallback after {time.time()-t_qwen_start:.2f}s, error: {e}")

    # Fallback to rule-based (only for financial questions)
    if not ai_answer:
        result = _generate_rule_based_answer(body.question, kpis, dept_items, prod_items, body.context)
        # Enrich with customer_items in suggestions
        result["suggestions"] = _get_page_suggestions(kpis, dept_items, prod_items, active_section, customer_items=customer_items)
        return APIResponse.success(data=result)

    # Build dynamic suggestions and references for AI success path
    active_section = body.context.active_section if body.context else ""
    suggestions = _get_page_suggestions(kpis, dept_items, prod_items, active_section, customer_items=customer_items)
    references = [
        {"type": "metric", "label": "营业收入", "value": (kpis.get("revenue") or 0)},
        {"type": "metric", "label": "毛利率", "value": (kpis.get("gross_margin") or 0)},
    ]

    return APIResponse.success(data={
        "answer": ai_answer,
        "suggestions": suggestions,
        "references": references,
    })


def _is_financial_question(question: str) -> bool:
    """Check if the question is finance-related."""
    q = question.lower()
    return any(kw in q for kw in [
        "收入", "毛利", "成本", "利润", "毛利率", "部门", "产品", "客户",
        "订单", "经营", "指标", "增长", "环比", "同比", "累计",
        "营收", "达成", "集中度", "风险", "异常", "分析", "贡献",
        "总结", "概况", "走势", "趋势", "预测", "dso", "ito",
        "revenue", "profit", "margin", "department", "product",
        "经营情况", "下钻", "拆解", "影响", "结构"
    ])


def _build_chat_prompt(body: ChatRequest, kpis: dict, dept_items: list, prod_items: list) -> str:
    """Build a concise prompt for AI chat."""
    ctx = body.context
    context_note = ""
    if ctx:
        parts = []
        if ctx.period:
            parts.append(f"期间：{ctx.period}")
        if ctx.department:
            parts.append(f"部门：{ctx.department}")
        if ctx.product:
            parts.append(f"产品线：{ctx.product}")
        if ctx.period_compare_type:
            type_map = {"yoy": "同比", "mom": "环比", "cumulative": "累计"}
            parts.append(f"对比方式：{type_map.get(ctx.period_compare_type, ctx.period_compare_type)}")
        if parts:
            context_note = f"\n\n当前筛选条件：{'，'.join(parts)}"

    is_financial_question = _is_financial_question(body.question)

    if is_financial_question:
        # Build concise data section with all available data
        data_lines = []
        k = kpis
        rev = k.get("revenue") or 0
        gp = k.get("gross_profit") or 0
        gm = k.get("gross_margin") or 0
        base_rev = k.get("base_revenue")
        base_gp = k.get("base_gross_profit")
        base_gm = k.get("base_gross_margin")
        rev_yoy = k.get("revenue_yoy_growth")
        gp_yoy = k.get("profit_yoy_growth")
        gm_yoy_change = k.get("gross_margin_yoy_change")

        data_lines.append(f"营业收入: {rev:,.0f}元, 毛利率: {gm:.2f}%, 毛利额: {gp:,.0f}元, 达成率: {(k.get('achievement_rate') or 0):.2f}%")
        data_lines.append(f"收入环比: {(k.get('revenue_mom_growth') or 0):+.2f}%, 毛利环比: {(k.get('profit_mom_growth') or 0):+.2f}%")
        if rev_yoy is not None:
            data_lines.append(f"收入同比: {rev_yoy:+.2f}%, 毛利同比: {gp_yoy:+.2f}%")
        if base_rev is not None:
            data_lines.append(f"基期收入: {base_rev:,.0f}元, 基期毛利额: {base_gp:,.0f}元, 基期毛利率: {base_gm:.2f}%")
        if gm_yoy_change is not None:
            data_lines.append(f"毛利率同比变化: {gm_yoy_change:+.2f}个百分点")
        if dept_items:
            data_lines.append("部门: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in dept_items[:5]))
        if prod_items:
            data_lines.append("产品: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in prod_items[:5]))
        data_section = "当前数据: " + "。".join(data_lines) + "。"
        data_section += "\n注意：请基于以上数据进行分析，不要编造数据。如果数据充分请给出具体分析，如果数据不足请说明具体缺少哪些维度的数据，避免笼统地说'无明细数据'。"

        system_role = (
            f"你是财务分析助手。基于以下数据和规则回答。\n\n"
            f"{data_section}{context_note}"
        )
    else:
        system_role = f"你是财务分析助手。如果问题与财务无关，用自然语言直接回答。"

    history_text = ""
    if body.history:
        history_text = "对话历史：\n"
        for msg in body.history[-4:]:
            history_text += f"{msg.role}: {msg.content}\n"

    prompt = (
        f"{system_role}\n\n{history_text}用户问题：{body.question}\n\n"
        f"要求：\n"
        f"1. 必须基于提供的数据和规则回答，不得编造\n"
        f"2. 中文回答，简洁专业\n"
        f"3. 数据不足时明确说明\n"
        f"4. 使用中文数字标题分段（一、二、三…）\n"
        f"5. 每个标题下按行列出指标，每行不超过15字，格式：指标名：数值\n"
        f"6. 异常、原因、建议分别成段，不要把所有内容挤成一段\n"
    )
    return prompt


async def _stream_qwen_sse(prompt: str, model: str | None = None):
    """Yield SSE events from Qwen API streaming response."""
    import httpx
    model = model or settings.qwen_model
    headers = {
        "Authorization": f"Bearer {settings.qwen_api_key}",
        "Content-Type": "application/json",
    }
    body_json = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "stream": True,
    }
    # Disable thinking for models that support it
    if "qwen3" in model or "deepseek" in model:
        body_json["extra_body"] = {"enable_thinking": False}

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.qwen_base_url}/chat/completions",
            headers=headers,
            json=body_json,
        ) as resp:
            if resp.status_code != 200:
                error_text = await resp.aread()
                yield f"event: error\ndata: {error_text.decode()}\n\n"
                return

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    yield f"data: {{\"done\": true}}\n\n"
                    break
                # Some models (deepseek) send reasoning_content before content.
                # Forward reasoning as content so the frontend displays it immediately.
                try:
                    chunk = json.loads(data)
                    if chunk.get("choices") and chunk["choices"][0].get("delta"):
                        delta = chunk["choices"][0]["delta"]
                        if delta.get("content") is None and delta.get("reasoning_content"):
                            delta["content"] = delta.pop("reasoning_content")
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    # Forward raw if not parseable
                    yield f"data: {data}\n\n"


@router.post("/chat/stream")
async def ai_chat_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_optional_user),
):
    """Stream AI chat response via SSE."""
    # Handle empty/init requests FIRST — no DB queries needed
    if not body.question or not body.question.strip() or body.question.strip() == "__init__":
        suggestions_json = json.dumps(["本月收入与毛利概况", "收入同比分析", "部门收入拆解"])
        async def gen_init():
            yield f"data: {{\"suggestions\": {suggestions_json}, \"done\": true}}\n\n"
        return StreamingResponse(gen_init(), media_type="text/event-stream")

    from app.api.dashboard import _build_kpis
    ctx = body.context

    # Skip _build_kpis for non-financial questions — saves ~2s DB query
    if _is_financial_question(body.question):
        kpis = await _build_kpis(
            db,
            period_compare_type=ctx.period_compare_type if ctx else None,
            period_dimension=ctx.period_dimension if ctx else None,
            period=ctx.period if ctx else None,
            period_start=ctx.period_start if ctx else None,
            period_end=ctx.period_end if ctx else None,
            department=ctx.department if ctx else None,
            product=ctx.product if ctx else None,
        )
    else:
        kpis = {}
    # Skip expensive breakdown query — prompt only needs summary KPIs + RAG rules
    dept_items, prod_items = [], []

    # Fetch customer breakdown for customer pages in streaming
    customer_items_stream = []
    _stream_active = body.context.active_section if body.context else ""
    if _stream_active in ("customer", "overview"):
        from app.db.session import async_session_factory
        from app.services.metrics_service import MetricsService
        async with async_session_factory() as session:
            cust_r = await MetricsService.get_core_metrics(
                db=session,
                period=body.context.period if body.context else None,
                dimension="company",
                compare="mom",
                bgbu_filter="ALL",
                sections={"customer_breakdown"},
            )
            customer_items_stream = [b.model_dump() for b in cust_r.customer_breakdown]

    # Build prompt with RAG rules
    prompt = _build_chat_prompt(body, kpis, dept_items, prod_items)

    # Prepend rules via RAG
    rules_text = await _get_rules_for_question(body.question)
    if rules_text:
        prompt = f"{prompt}\n\n{rules_text}"

    # Use model from request if provided, otherwise default from settings
    model = getattr(body, 'model', None) or settings.qwen_model

    async def event_stream():
        full_answer = []
        async for chunk in _stream_qwen_sse(prompt, model):
            full_answer.append(chunk)
            yield chunk

        # After streaming, send suggestions and references as final event
        suggestions = _get_page_suggestions(kpis, dept_items, prod_items, body.context.active_section if body.context else "", customer_items=customer_items_stream)
        final = json.dumps({
            "suggestions": suggestions,
            "references": [
                {"type": "metric", "label": "营业收入", "value": (kpis.get("revenue") or 0)},
                {"type": "metric", "label": "毛利率", "value": (kpis.get("gross_margin") or 0)},
            ],
            "done": True,
        }, ensure_ascii=False)
        yield f"data: {final}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/analysis-recommendations", response_model=APIResponse)
async def get_analysis_recommendations(
    body: AnalysisRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload | None = Depends(get_optional_user),
) -> APIResponse:
    """Get page-specific analysis recommendations with metrics and anomaly alerts."""
    from app.api.dashboard import _build_kpis
    from app.db.session import async_session_factory
    from app.services.metrics_service import MetricsService

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


@router.get("/config", response_model=APIResponse)
async def get_ai_config():
    """Return available AI models for frontend selection."""
    models = [
        {"value": "deepseek-v4-flash", "label": "DeepSeek V4 Flash"},
        {"value": "gpt-4o-mini", "label": "GPT-4o Mini"},
        {"value": "qwen3.6-plus", "label": "Qwen 3.6 Plus"},
    ]
    return APIResponse.success(data={
        "current_model": settings.qwen_model,
        "available_models": models,
    })
