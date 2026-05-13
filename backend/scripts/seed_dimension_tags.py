"""Backfill FinancialData.tags with full business dimensions.

Task #8 (P1.2): ensure every row in financial_data carries the four canonical
dimensions used by metrics_service / insight_rule_service:
  - customer
  - product_line
  - bu
  - region
And add the missing `project_name` dimension to support project-level drilldowns.

Strategy:
  1. NULL-tags rows  → derive deterministic dimensions from id + entity + period.
  2. transaction_record rows → merge in product_line / department / bu / project_name
     (they already have customer / region / contract_no).
  3. p0_metrics rows → merge in project_name (already have everything else).

Idempotent: re-running will overwrite only the dimension keys this script owns,
preserving any other tag keys.
"""

import os
import sys
import json
import random
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_URL = (
    f"postgresql+psycopg://"
    f"{os.getenv('DB_USER','learnhouse')}:{os.getenv('DB_PASSWORD','learnhouse')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}"
    f"/{os.getenv('DB_NAME','caiwu')}"
)

CUSTOMERS = [
    "华为科技", "阿里云", "腾讯", "中国移动", "字节跳动",
    "百度", "京东", "美团", "小米科技", "网易",
    "平安科技", "招商银行", "中国电信", "国家电网", "中石化",
]
PRODUCT_LINES = [
    "企业网络", "无线产品", "数据中心交换机", "安全产品",
    "云服务", "软件订阅", "运维服务",
]
REGIONS = ["华东", "华南", "华北", "西南", "海外"]
PROJECTS = [
    "数智化转型一期", "数据中心扩容", "园区WiFi升级", "云原生迁移",
    "安全合规建设", "运营商专网", "海外节点部署", "智慧政务",
    "金融骨干网", "教育云项目",
]

DEPT_TO_BU = {
    "CBG": "消费者BG",
    "EBG": "企业BG",
    "SBG": "运营商BG",
    "TBU": "技术BU",
    "企业网络产品事业部": "企业BG",
    "企业无线产品事业部": "企业BG",
    "运营商事业部": "运营商BG",
    "海外业务部": "海外BG",
    "战略和业务发展部": "战略BU",
    "服务与软件事业部": "服务BU",
}
DEPARTMENTS = list(DEPT_TO_BU.keys())


def pick(seq, seed_str: str):
    """Deterministic choice from seq based on seed_str."""
    h = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16)
    return seq[h % len(seq)]


def bu_for(department: str | None) -> str:
    if not department:
        return "企业BG"
    return DEPT_TO_BU.get(department, "企业BG")


def derive_dims(row_id: int, entity: str | None, period: str, metric_name: str) -> dict:
    base = f"{row_id}|{entity or ''}|{period}|{metric_name}"
    department = entity if entity in DEPT_TO_BU else pick(DEPARTMENTS, base + "|dept")
    return {
        "customer": pick(CUSTOMERS, base + "|cust"),
        "customer_name": pick(CUSTOMERS, base + "|cust"),
        "product_line": pick(PRODUCT_LINES, base + "|prod"),
        "product": pick(PRODUCT_LINES, base + "|prod"),
        "region": pick(REGIONS, base + "|reg"),
        "project_name": pick(PROJECTS, base + "|proj"),
        "department": department,
        "bu": bu_for(department),
    }


def backfill_null_tags(conn) -> int:
    rows = conn.execute(text(
        "SELECT id, entity, period, metric_name FROM financial_data WHERE tags IS NULL"
    )).fetchall()
    if not rows:
        return 0
    updates = []
    for rid, entity, period, mname in rows:
        dims = derive_dims(rid, entity, period, mname)
        updates.append({"id": rid, "tags": json.dumps(dims, ensure_ascii=False)})
    # Chunked update
    CHUNK = 1000
    for i in range(0, len(updates), CHUNK):
        conn.execute(
            text("UPDATE financial_data SET tags = CAST(:tags AS JSON) WHERE id = :id"),
            updates[i:i + CHUNK],
        )
    return len(updates)


def enrich_existing_tags(conn) -> int:
    """For rows that already have tags but miss product_line / project_name / bu / department,
    merge in the missing keys deterministically.
    """
    rows = conn.execute(text(
        "SELECT id, entity, period, metric_name, tags FROM financial_data WHERE tags IS NOT NULL"
    )).fetchall()
    if not rows:
        return 0

    updates = []
    for rid, entity, period, mname, tags in rows:
        if not isinstance(tags, dict):
            try:
                tags = json.loads(tags) if isinstance(tags, str) else {}
            except Exception:
                tags = {}
        before = dict(tags)
        dims = derive_dims(rid, entity, period, mname)

        for k in ("customer", "product_line", "bu", "region", "project_name", "department"):
            if not tags.get(k):
                tags[k] = dims[k]
        if not tags.get("customer_name") and tags.get("customer"):
            tags["customer_name"] = tags["customer"]
        if not tags.get("product") and tags.get("product_line"):
            tags["product"] = tags["product_line"]

        if tags != before:
            updates.append({"id": rid, "tags": json.dumps(tags, ensure_ascii=False)})

    CHUNK = 1000
    for i in range(0, len(updates), CHUNK):
        conn.execute(
            text("UPDATE financial_data SET tags = CAST(:tags AS JSON) WHERE id = :id"),
            updates[i:i + CHUNK],
        )
    return len(updates)


def main():
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        n_null = backfill_null_tags(conn)
        print(f"Backfilled tags on {n_null} previously NULL rows.", flush=True)
        n_enrich = enrich_existing_tags(conn)
        print(f"Enriched tags on {n_enrich} existing-tag rows.", flush=True)

    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT
              count(*) FILTER (WHERE tags IS NULL) AS null_tags,
              count(*) FILTER (WHERE tags->>'customer' IS NOT NULL) AS with_customer,
              count(*) FILTER (WHERE tags->>'product_line' IS NOT NULL) AS with_product_line,
              count(*) FILTER (WHERE tags->>'bu' IS NOT NULL) AS with_bu,
              count(*) FILTER (WHERE tags->>'region' IS NOT NULL) AS with_region,
              count(*) FILTER (WHERE tags->>'project_name' IS NOT NULL) AS with_project,
              count(*) AS total
            FROM financial_data
        """)).fetchone()
        print("\nFinal dimension coverage:")
        print(f"  total rows         : {r.total}")
        print(f"  tags IS NULL       : {r.null_tags}")
        print(f"  tags.customer      : {r.with_customer}")
        print(f"  tags.product_line  : {r.with_product_line}")
        print(f"  tags.bu            : {r.with_bu}")
        print(f"  tags.region        : {r.with_region}")
        print(f"  tags.project_name  : {r.with_project}")

    engine.dispose()


if __name__ == "__main__":
    main()
