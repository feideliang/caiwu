"""Seed knowledge rules into PG + Qdrant.

Expanded coverage: metric formulas, anomaly thresholds, concentration risks,
trend analysis, drill-down paths, analysis dimension fields, and per-page logic.

Each rule now includes structured fields (rule_code, threshold, severity, condition)
so the rule engine can read thresholds dynamically instead of hardcoding them.
"""

from __future__ import annotations

import sys
import uuid

sys.path.insert(0, ".")

from app.db.session import sync_session_factory
from app.models.core import KnowledgeRule
from app.services.rule_store import ensure_collection, upsert_to_qdrant

# (category, rule_text, source_section, rule_code, threshold, severity, condition, is_executable)
SEED_RULES = [
    # ── 核心指标公式 ──
    ("calculation", "毛利率 = (收入 - 不含税成本) / 收入 × 100%，衡量各维度最直接的赚钱能力", "核心指标体系", None, None, None, None, False),
    ("calculation", "毛利额 = 收入 - 不含税成本，反映绝对盈利贡献", "核心指标体系", None, None, None, None, False),
    ("calculation", "毛利率贡献度 = 某维度毛利额 / 总毛利额 × 100%，识别公司核心利润来源", "核心指标体系", None, None, None, None, False),
    ("calculation", "收入贡献度 = 某维度收入 / 总收入 × 100%", "核心指标体系", None, None, None, None, False),
    ("calculation", "客户集中度 = 前三大客户收入 / 总收入 × 100%，评估客户依赖风险", "核心指标体系", None, None, None, None, False),
    ("calculation", "产品集中度 = 前三大产品线毛利 / 总毛利 × 100%，评估产品线风险", "核心指标体系", None, None, None, None, False),
    ("calculation", "亏损订单占比 = 毛利率为负的订单数 / 总订单数 × 100%", "核心指标体系", None, None, None, None, False),
    ("calculation", "亏损产品占比 = 毛利率为负的产品数 / 总产品数 × 100%", "核心指标体系", None, None, None, None, False),
    ("calculation", "高毛利订单占比 = 毛利率 > 40% 的订单数 / 总订单数 × 100%，优质订单结构指标", "核心指标体系", None, None, None, None, False),
    ("calculation", "同比增长率 = (本期 - 去年同期) / 去年同期 × 100%，衡量长期发展动能", "核心指标体系", None, None, None, None, False),
    ("calculation", "毛利率变化拆解(每个维度)：结构影响 = (当期收入占比 - 基期收入占比) × 基期毛利率 / 100；毛利变化影响 = 当期收入占比 × (当期毛利率 - 基期毛利率) / 100；合计 = 结构影响 + 毛利变化影响", "核心指标体系", None, None, None, None, False),
    ("calculation", "收入/毛利额变动影响拆解：各维度(当期值 - 基期值) / 总变化绝对值，累计贡献80%的为主要变动因素", "核心指标体系", None, None, None, None, False),

    # ── 异常检测阈值 ──
    ("anomaly_gross_margin", "毛利率低于20%：触发一般异常警报，需纳入常规审视", "异常检测规则", "GROSS_MARGIN_LOW", 20, "medium", "gm < 20", True),
    ("anomaly_gross_margin", "毛利率低于10%：触发严重异常警报，必须立即启动下钻分析，排查定价失误、成本异常或特殊竞争性项目", "异常检测规则", "GROSS_MARGIN_SEVERE_LOW", 10, "high", "gm < 10", True),
    ("anomaly_gross_margin", "毛利率高于60%：需分析确认是技术领先带来的溢价还是偶然性项目，判断成功模式是否可复制", "异常检测规则", "GROSS_MARGIN_HIGH", 60, "medium", "gm > 60", True),

    # ── 集中度风险（含双重阈值） ──
    ("concentration_risk", "单一客户销售收入占比超过10%：触发客户集中度风险预警，提示开拓新客户", "结构风险预警", "CUSTOMER_CONCENTRATION", 10, "high", "share > 10", True),
    ("concentration_risk", "前三大客户集中度 > 60%：客户集中度过高，需关注客户依赖风险", "结构风险预警", "CUSTOMER_CONCENTRATION_TOP3", 60, "high", "top3 > 60", True),
    ("concentration_risk", "单一产品系列毛利贡献占比超过40%：触发产品集中度风险预警，提示培育第二增长曲线", "结构风险预警", "PRODUCT_CONCENTRATION", 40, "high", "share > 40", True),
    ("concentration_risk", "前三大产品线毛利集中度 > 70%：产品集中度过高，需警惕产品线单一风险", "结构风险预警", "PRODUCT_CONCENTRATION_TOP3", 70, "high", "top3 > 70", True),

    # ── 趋势分析 ──
    ("trend_detection", "任一销售部门或产品事业部的收入或毛利额连续三个月实现环比正增长，可初步定义为上升趋势，需总结其驱动因素", "增长趋势识别", None, None, None, None, False),
    ("trend_yoy", "同比分析：排除季节性影响，评估业务的长期趋势和年度战略举措的真实效果，必须对比相同自然月或季度", "周期对比分析", None, None, None, None, False),
    ("trend_mom", "环比分析：敏锐捕捉短期业务波动，及时发现月度执行层面的异常，特别注意月末、季末的业务冲量行为对数据的扰动", "周期对比分析", None, None, None, None, False),
    ("trend_cumulative", "累计分析：计算当年截至当前累计收入、毛利与去年同期对比的累计增长率，评估目标达成进度", "周期对比分析", None, None, None, None, False),

    # ── 下钻路径 ──
    ("drilldown_trigger", "公司级核心指标（如整体毛利率）出现超过预设阈值的异常波动时，必须强制启动标准下钻分析路径，直至定位到最小业务单元（如具体项目）", "下钻分析触发点", None, None, None, None, False),
    ("drilldown_path", "下钻路径：公司 → 组织/时间 → 客户/产品 → 交易/项目", "四层穿透", None, None, None, None, False),
    ("drilldown_L1", "第一层：公司整体层面，观察收入规模、毛利额及毛利率是否达成预期，判断处于健康增长、瓶颈或下滑通道", "四层穿透", None, None, None, None, False),
    ("drilldown_L2", "第二层：组织与时间维度下钻，定位哪个销售部门或产品事业部在哪个时间周期为主要驱动因素", "四层穿透", None, None, None, None, False),
    ("drilldown_L3", "第三层：客户与产品维度交叉分析，分析客户签约类型或物料成本大类×产品系列导致的利润变化", "四层穿透", None, None, None, None, False),
    ("drilldown_L4", "第四层：交易与项目维度根因定位，穿透至具体订单分类、项目名称、关键客户", "四层穿透", None, None, None, None, False),
    ("drilldown_product", "产品钻取路径：产品线(product_line) → 销售产品名称(sales_product_name)，查看具体销售产品明细", "钻取路径", None, None, None, None, False),

    # ── 数据维度说明 ──
    ("dimension_org", "组织维度字段：department(市场线:CBG/EBG/SBG/TBU), sales_department(销售部门), hr_department(HR部门), hr_dept_code(HR部门编码)", "数据维度", None, None, None, None, False),
    ("dimension_product", "产品维度字段：product_line(产品线), series(产品系列), product_category(产品大类), product_classification(产品分类), product_family(产品族), product_bu_name(产品事业部名称), product_bu_code(产品事业部代码), product_org(产品所属组织), product_bgbu(产品归属BGBU)", "数据维度", None, None, None, None, False),
    ("dimension_sales_product", "销售产品维度字段：sales_product_code(销售产品代码), sales_product_name(销售产品名称), material_code(物料编码), material_desc(物料描述), material_cost_category(物料成本大类)", "数据维度", None, None, None, None, False),
    ("dimension_cost", "成本分类维度字段：cost_class_1(一级成本分类), cost_class_2(二级成本分类), cost_class_3(三级成本分类), cost_category(成本大类)", "数据维度", None, None, None, None, False),
    ("dimension_customer", "客户维度字段：customer(客户), ncc_customer_code(NCC客户编码), order_customer(订单客户), invoice_customer(开票客户简称), invoice_name(开票名称), final_customer(最终客户名称), superior_name(上级名称), contract_type(客户签约类型:直签/渠道)", "数据维度", None, None, None, None, False),
    ("dimension_order", "订单维度字段：order_id(订单编号), contract_no(合同编号), order_header_type(订单头类型), order_category(订单分类), sales_type(内销/外销)", "数据维度", None, None, None, None, False),
    ("dimension_geo", "地理与市场维度字段：province(省份), market_segment(细分市场), application_scenario(应用场合), project_name(项目名称)", "数据维度", None, None, None, None, False),
    ("dimension_fin", "财务维度字段：currency(币种), exchange_rate(汇率), tax_rate(税率), order_qty(订单数量), unit_cost_ex_tax(不含税单位成本), unit_cost_incl_tax(含税单位成本)", "数据维度", None, None, None, None, False),
    ("dimension_period", "期间维度：period(YYYY-MM格式), 支持月度/季度/年累计/自定义期间四种维度。比较类型：yoy(同比), mom(环比), cumulative(累计)", "数据维度", None, None, None, None, False),

    # ── 分析页面逻辑 ──
    ("page_overview", "总览驾驶舱核心KPI：营业收入、营业成本、毛利额、毛利率及同比变化。趋势图为月度趋势，含收入/成本/毛利额柱线和毛利率次坐标轴", "页面分析逻辑", None, None, None, None, False),
    ("page_change", "变动分析三大模块：收入变动(当期/基期/变化比例+主要变动影响)、毛利额变动、毛利率变动(当期/基期/变化值pp+结构影响+毛利影响)。主要变动因素为累计贡献80%的维度", "页面分析逻辑", None, None, None, None, False),
    ("page_change_concentration", "变动分析-集中度排名：收入/毛利额/毛利率三个指标并行展示各维度排名", "页面分析逻辑", None, None, None, None, False),
    ("page_dept", "部门分析维度：department(市场线)。KPI：营业收入/毛利额/毛利率/亏损订单占比。明细列：收入贡献度/毛利贡献度/负毛利订单数量/负毛利金额", "页面分析逻辑", None, None, None, None, False),
    ("page_product", "产品分析维度：product_line(产品线)。KPI：收入/毛利额/毛利率/亏损产品占比。支持钻取到sales_product_name层级查看销售产品明细。明细列：收入贡献度/毛利贡献度/负毛利产品数量/负毛利金额", "页面分析逻辑", None, None, None, None, False),

    # ── 报告输出 ──
    ("report_structure", "标准分析报告包含四部分：总体业绩概览、多维下钻分析、根本原因总结、具体业务建议", "标准化报告输出", None, None, None, None, False),
    ("report_suggestion", "业务建议示例：销售资源倾斜(投向高贡献部门)、定价策略调整(低毛利率订单)、产品战略优化(高增长产品加大投入)、客户关系管理(直签高价值客户)", "标准化报告输出", None, None, None, None, False),
]


def seed_rules():
    """Insert or update seed rules in PG + Qdrant."""
    ensure_collection()

    with sync_session_factory() as session:
        # Build lookup by rule_code (preferred) or rule_text
        existing_by_code: dict[str, KnowledgeRule] = {}
        existing_by_text: dict[str, KnowledgeRule] = {}
        for r in session.query(KnowledgeRule).all():
            if r.rule_code:
                existing_by_code[r.rule_code] = r
            existing_by_text[r.rule_text] = r

        count = 0
        for (
            category, rule_text, source_section,
            rule_code, threshold, severity, condition, is_executable,
        ) in SEED_RULES:
            # Dedup by rule_code first, then by rule_text
            existing = None
            if rule_code and rule_code in existing_by_code:
                existing = existing_by_code[rule_code]
            elif rule_text in existing_by_text:
                existing = existing_by_text[rule_text]

            if existing:
                # Update structured fields on existing rule
                changed = False
                if rule_code and existing.rule_code != rule_code:
                    existing.rule_code = rule_code; changed = True
                if threshold is not None and existing.threshold != threshold:
                    existing.threshold = threshold; changed = True
                if severity and existing.severity != severity:
                    existing.severity = severity; changed = True
                if condition and existing.condition != condition:
                    existing.condition = condition; changed = True
                if existing.is_executable != is_executable:
                    existing.is_executable = is_executable; changed = True
                if changed:
                    session.flush()
                continue

            point_id = str(uuid.uuid4())
            rule = KnowledgeRule(
                category=category,
                rule_text=rule_text,
                source_section=source_section,
                is_active=True,
                qdrant_point_id=point_id,
                rule_code=rule_code,
                threshold=threshold,
                severity=severity,
                condition=condition,
                is_executable=is_executable,
            )
            session.add(rule)
            session.flush()

            upsert_to_qdrant(point_id, rule_text, category, source_section, True)
            count += 1

        session.commit()
        if rule_code:
            from app.services.rule_config import set_rule_config as sync_redis

        print(f"Seeded {count} new rules ({len(SEED_RULES)} total)")


if __name__ == "__main__":
    seed_rules()