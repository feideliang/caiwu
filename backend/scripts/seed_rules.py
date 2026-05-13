"""Seed 24 knowledge rules into PG + Qdrant."""

from __future__ import annotations

import sys
import uuid

sys.path.insert(0, ".")

from app.db.session import sync_session_factory
from app.models.core import KnowledgeRule
from app.services.rule_store import ensure_collection, upsert_to_qdrant

SEED_RULES = [
    ("anomaly_gross_margin", "毛利率低于20%：触发一般异常警报，需纳入常规审视", "异常检测规则"),
    ("anomaly_gross_margin", "毛利率低于10%：触发严重异常警报，必须立即启动下钻分析，排查定价失误、成本异常或特殊竞争性项目", "异常检测规则"),
    ("anomaly_gross_margin", "毛利率高于60%：需分析确认是技术领先带来的溢价还是偶然性项目，判断成功模式是否可复制", "异常检测规则"),
    ("trend_detection", "任一销售部门或产品事业部的收入或毛利额连续三个月实现环比正增长，可初步定义为上升趋势，需总结其驱动因素", "增长趋势识别"),
    ("concentration_risk", "单一客户销售收入占比超过30%：触发客户集中度风险预警，提示开拓新客户", "结构风险预警"),
    ("concentration_risk", "单一产品系列毛利贡献占比超过40%：触发产品集中度风险预警，提示培育第二增长曲线", "结构风险预警"),
    ("drilldown_trigger", "公司级核心指标（如整体毛利率）出现超过预设阈值的异常波动时，必须强制启动标准下钻分析路径，直至定位到最小业务单元（如具体项目）", "下钻分析触发点"),
    ("drilldown_path", "下钻路径：公司 → 组织/时间 → 客户/产品 → 交易/项目", "四层穿透"),
    ("drilldown_L1", "第一层：公司整体层面，观察收入规模、毛利额及毛利率是否达成预期，判断处于健康增长、瓶颈或下滑通道", "四层穿透"),
    ("drilldown_L2", "第二层：组织与时间维度下钻，定位哪个销售部门或产品事业部在哪个时间周期为主要驱动因素", "四层穿透"),
    ("drilldown_L3", "第三层：客户与产品维度交叉分析，分析客户签约类型或物料成本大类×产品系列导致的利润变化", "四层穿透"),
    ("drilldown_L4", "第四层：交易与项目维度根因定位，穿透至具体订单分类、项目名称、关键客户", "四层穿透"),
    ("calculation", "毛利率 = (收入 - 不含税成本) / 收入 × 100%，衡量各维度最直接的赚钱能力", "核心指标体系"),
    ("calculation", "毛利额 = 收入 - 不含税成本，反映绝对盈利贡献", "核心指标体系"),
    ("calculation", "毛利率贡献度 = 某维度毛利额 / 总毛利额 × 100%，识别公司核心利润来源", "核心指标体系"),
    ("calculation", "客户集中度 = 前三大客户收入 / 总收入 × 100%，评估客户依赖风险", "核心指标体系"),
    ("calculation", "产品集中度 = 前三大产品线毛利 / 总毛利 × 100%，评估产品线风险", "核心指标体系"),
    ("calculation", "同比增长率 = (本期 - 去年同期) / 去年同期 × 100%，衡量长期发展动能", "核心指标体系"),
    ("calculation", "同比/环比增长影响度：结构影响 = (当期收入占比 - 基期收入占比) × 基期毛利率 / 100；毛利变化影响 = 当期收入占比 × (当期毛利率 - 基期毛利率) / 100；合计 = 结构影响 + 毛利变化影响。分析公司毛利率变化对应不同市场线/产品线的影响程度", "核心指标体系"),
    ("calculation", "高毛利订单占比 = 毛利率 > X% 的订单数 / 总订单数 × 100%，反映优质订单结构", "核心指标体系"),
    ("period_compare_yoy", "同比分析：排除季节性影响，评估业务的长期趋势和年度战略举措的真实效果，必须对比相同自然月或季度", "周期对比分析"),
    ("period_compare_mom", "环比分析：敏锐捕捉短期业务波动，及时发现月度执行层面的异常，特别注意月末、季末的业务冲量行为对数据的扰动", "周期对比分析"),
    ("period_compare_cum", "累计分析：计算当年截至当前累计收入、毛利与去年同期对比的累计增长率，评估目标达成进度", "周期对比分析"),
    ("report_structure", "标准分析报告包含四部分：总体业绩概览、多维下钻分析、根本原因总结、具体业务建议", "标准化报告输出"),
]


def seed_rules():
    """Insert or update seed rules in PG + Qdrant."""
    ensure_collection()

    with sync_session_factory() as session:
        # Check existing
        existing = {
            r.rule_text: r
            for r in session.query(KnowledgeRule).all()
        }

        count = 0
        for category, rule_text, source_section in SEED_RULES:
            if rule_text in existing:
                continue  # already exists

            point_id = str(uuid.uuid4())
            rule = KnowledgeRule(
                category=category,
                rule_text=rule_text,
                source_section=source_section,
                is_active=True,
                qdrant_point_id=point_id,
            )
            session.add(rule)
            session.flush()

            upsert_to_qdrant(point_id, rule_text, category, source_section, True)
            count += 1

        session.commit()

    print(f"Seeded {count} new rules ({len(SEED_RULES) - count} already existed)")


if __name__ == "__main__":
    seed_rules()
