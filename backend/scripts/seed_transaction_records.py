"""Seed mock transaction-level records into financial_data for L3/L4 drill-down."""
import os
import sys
import json
import random
from datetime import date, timedelta

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

CUSTOMERS = [
    "华为技术有限公司", "腾讯科技有限公司", "阿里巴巴集团", "字节跳动", "美团",
    "京东集团", "百度在线", "小米科技", "网易公司", "滴滴出行",
    "平安科技", "招商银行", "中国电信", "中国移动", "中国银联",
    "国家电网", "中石化", "中石油", "中国中铁", "中国建筑",
]
REGIONS = ["华东", "华南", "华北", "西南", "华中"]
STATUSES = ["已付款", "待付款", "已开票", "部分付款"]
PAYMENT_TERMS = ["预付30%", "货到付款", "月结30天", "季度结算"]
INVOICE_STATUSES = ["已开票", "未开票", "部分开票"]


def random_date_in_range(rng: random.Random, start: date, end: date) -> str:
    delta_days = (end - start).days
    d = start + timedelta(days=rng.randint(0, delta_days))
    return d.isoformat()


def main():
    rng = random.Random(42)
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT count(*) FROM financial_data WHERE metric_name = 'transaction_record'")
        ).scalar()
        if existing and existing > 0:
            print(f"Transaction records already exist ({existing} rows). Skipping.")
            return

        entities = [
            row[0] for row in conn.execute(
                text("SELECT DISTINCT entity FROM financial_data WHERE entity IS NOT NULL ORDER BY entity")
            ).fetchall()
        ]
        print(f"Found {len(entities)} entities: {entities}")

        start_d = date(2026, 1, 1)
        end_d = date(2026, 6, 30)
        txn_counter = 1
        total_inserted = 0

        for entity in entities:
            n = rng.randint(10, 15)
            print(f"Entity {entity}: inserting {n} records...")
            for _ in range(n):
                tags = {
                    "transaction_no": f"TXN-202603-{txn_counter:04d}",
                    "date": random_date_in_range(rng, start_d, end_d),
                    "customer": rng.choice(CUSTOMERS),
                    "contract_no": f"CTR-2026-{rng.randint(1, 9999):04d}",
                    "region": rng.choice(REGIONS),
                    "status": rng.choice(STATUSES),
                    "payment_terms": rng.choice(PAYMENT_TERMS),
                    "invoice_status": rng.choice(INVOICE_STATUSES),
                }
                amount = round(rng.uniform(50000, 500000), 2)
                conn.execute(
                    text("""
                        INSERT INTO financial_data
                            (batch_id, metric_name, metric_value, metric_unit, period, entity, tags, raw_row)
                        VALUES
                            (NULL, 'transaction_record', :val, 'CNY', '2026-03', :entity, CAST(:tags AS JSON), NULL)
                    """),
                    {"val": amount, "entity": entity, "tags": json.dumps(tags, ensure_ascii=False)},
                )
                txn_counter += 1
                total_inserted += 1

        conn.commit()
        print(f"\nDone. Total transaction records inserted: {total_inserted}")

    engine.dispose()


if __name__ == "__main__":
    main()
