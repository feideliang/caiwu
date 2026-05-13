"""Seed mock insight records for the Smart Insights panel."""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "caiwu")
DB_USER = os.getenv("DB_USER", "learnhouse")
DB_PASSWORD = os.getenv("DB_PASSWORD", "learnhouse")

DB_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

INSIGHTS = [
    {
        "title": "2026年3月营业收入异常波动",
        "insight_type": "anomaly",
        "content": "2026年3月营业收入较上月环比下降23.5%，显著高于正常波动范围（±10%）。其中SBG部门降幅最大，建议关注大客户订单变化。",
        "data_json": {
            "__status": "unread",
            "metric": "revenue",
            "period": "2026-03",
            "change_pct": -23.5,
            "threshold": 10,
            "department": "SBG",
            "drill_level": 2,
            "drill_type": "department",
            "drill_params": {"department_name": "SBG"},
        },
        "generated_by": "ai",
    },
    {
        "title": "运营成本连续两月上升趋势",
        "insight_type": "trend",
        "content": "自2026年1月以来，运营成本连续3个月环比上升，累计涨幅达8.7%。若不加以控制，预计Q2毛利率将受到进一步压缩。",
        "data_json": {
            "__status": "unread",
            "metric": "cost",
            "trend_direction": "up",
            "consecutive_months": 3,
            "total_increase_pct": 8.7,
        },
        "generated_by": "ai",
    },
    {
        "title": "华为与腾讯部门收入高度相关",
        "insight_type": "correlation",
        "content": "华为技术有限公司与腾讯科技有限公司的客户收入相关系数达0.87（p<0.01），两家客户收入变动趋势高度一致，可能存在共同的行业周期因素。",
        "data_json": {
            "__status": "unread",
            "entity_a": "华为技术有限公司",
            "entity_b": "腾讯科技有限公司",
            "correlation_coeff": 0.87,
            "p_value": 0.003,
            "drill_level": 2,
            "drill_type": "department",
            "drill_params": {"department_name": "华为技术有限公司"},
        },
        "generated_by": "ai",
    },
    {
        "title": "2026年3月财务月度总结",
        "insight_type": "summary",
        "content": "3月全公司实现营业收入1,536万元，毛利润540万元，毛利率34.83%。收入贡献最高的部门为SBG（136.5万元），其次为EBG（89.2万元）。整体经营情况稳健，但需关注成本上升趋势。",
        "data_json": {
            "__status": "unread",
            "period": "2026-03",
            "revenue": 15360000,
            "gross_profit": 5400000,
            "gross_margin_pct": 34.83,
            "top_department": "SBG",
            "drill_level": 1,
            "drill_type": "overview",
            "drill_params": {},
        },
        "generated_by": "ai",
    },
    {
        "title": "应收账款周转天数(DSO)偏高预警",
        "insight_type": "anomaly",
        "content": "当前DSO估算为68天，超出行业基准值45天约51%。主要受EBG部门部分大额订单回款延迟影响，建议加强应收账款催收管理。",
        "data_json": {
            "__status": "unread",
            "metric": "dso",
            "current_value": 68,
            "benchmark": 45,
            "deviation_pct": 51,
        },
        "generated_by": "ai",
    },
    {
        "title": "华南地区收入占比持续下降",
        "insight_type": "trend",
        "content": "华南地区收入占全公司比例从2025年Q4的32%降至2026年3月的18%，降幅明显。建议分析区域市场变化原因，评估是否需要调整区域策略。",
        "data_json": {
            "__status": "unread",
            "region": "华南",
            "previous_pct": 32,
            "current_pct": 18,
            "trend_direction": "down",
        },
        "generated_by": "ai",
    },
    {
        "title": "净利率低于行业均值",
        "insight_type": "summary",
        "content": "公司当前净利率约为18.2%，低于同行业可比公司均值（22.5%）。主要差距来自管理费用率偏高（12.3% vs 行业8.5%），建议优化费用结构。",
        "data_json": {
            "__status": "unread",
            "metric": "net_margin",
            "company_value": 18.2,
            "industry_benchmark": 22.5,
        },
        "generated_by": "ai",
    },
    {
        "title": "阿里巴巴集团大客户依赖风险",
        "insight_type": "correlation",
        "content": "阿里巴巴集团占全公司收入比例达34.6%，单一客户集中度过高。若该客户需求发生变化，将对整体营收产生重大影响。建议拓展客户多元化。",
        "data_json": {
            "__status": "unread",
            "customer": "阿里巴巴集团",
            "revenue_share_pct": 34.6,
            "risk_level": "high",
            "drill_level": 2,
            "drill_type": "department",
            "drill_params": {"department_name": "阿里巴巴集团"},
        },
        "generated_by": "ai",
    },
]


def main():
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        existing = conn.execute(text("SELECT count(*) FROM insight")).scalar()
        if existing and existing > 0:
            print(f"Insight records already exist ({existing} rows). Skipping.")
            return

        for ins in INSIGHTS:
            conn.execute(
                text("""
                    INSERT INTO insight (title, insight_type, content, data_json, generated_by, created_by, created_at, updated_at)
                    VALUES (:title, :insight_type, :content, :data_json, :generated_by, NULL, NOW(), NOW())
                """),
                {
                    "title": ins["title"],
                    "insight_type": ins["insight_type"],
                    "content": ins["content"],
                    "data_json": json.dumps(ins["data_json"], ensure_ascii=False),
                    "generated_by": ins["generated_by"],
                },
            )
        conn.commit()
        print(f"Seeded {len(INSIGHTS)} insight records successfully.")


if __name__ == "__main__":
    main()
