# 真实财务数据导入实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 superpowers:subagent-driven-development 按任务逐项实施。步骤使用 `- [ ]` 语法追踪。

**Goal:** 将 Excel 文件 `收入毛利明细数据for驾驶舱_202501-202509.xlsx`（71 列真实收入/毛利明细数据）映射到系统 `financial_data` 表，替换 2025 年 1-9 月期间的模拟数据，保留其他期间数据不变。

**Architecture:** 创建独立 Python 脚本 `backend/scripts/seed_real_data_2025.py`，使用 openpyxl 读取 Excel，按 MYSQL_COLUMN_MAP 将 71 列映射到 canonical 字段，每行源数据扩展为 4 行 metrics (revenue, cost, gross_profit, profit_margin)，维度字段存入 tags JSON，使用 asyncpg.copy_records_to_table 批量写入 PostgreSQL。

**Tech Stack:** Python 3, openpyxl, asyncpg, PostgreSQL

---

## 关键设计

### 数据更新策略：按期间删除再插入

不 TRUNCATE 整表（会丢失 2024/2026 模拟数据）。改为：
1. 识别目标期间 `2025-01` ~ `2025-09`
2. `DELETE FROM financial_data WHERE period = ANY(...)` 仅删除这 9 个月的数据
3. 批量插入真实数据

幂等：重新运行会先清空再插入，结果一致。

### Metric 扩展

每行 Excel 源数据 → 4 行 financial_data：

| metric_name | 源列 | metric_unit |
|---|---|---|
| `revenue` | `收入金额(人民币)` | CNY |
| `cost` | `不含税成本` | CNY |
| `gross_profit` | `不含税毛利` 或 `revenue - cost` | CNY |
| `profit_margin` | `毛利率` 或 `(gross_profit / revenue) * 100` | % |

### 维度标签 (tags JSON)

所有非财务列按 MYSQL_COLUMN_MAP 映射为 tag 键存入 tags JSON：
- `产品线` → `{"product_line": "..."}`
- `产品系列` → `{"series": "..."}`
- `客户` → `{"customer": "..."}`
- `订单编号` → `{"order_id": "..."}`
- `币种` → `{"currency": "..."}`
- 等 50+ tag 字段

### Entity 映射

优先使用 `销售BGBU` → entity，回退 `产品事业部名称`。

### Period 格式

从 `确认收入日期` 提取 YYYY-MM（字符串切片 `[:7]`），回退 `确认收入年` + `确认收入月`。

---

## 文件

- **创建:** `backend/scripts/seed_real_data_2025.py`
- **参考:** `backend/scripts/seed_from_xlsx.py` — asyncpg 批量插入模式
- **参考:** `backend/scripts/seed_from_mysql.py:39-129` — MYSQL_COLUMN_MAP 定义
- **参考:** `backend/app/models/core.py:43-57` — FinancialData 模型定义

---

## 实施任务

### Task 1: 创建导入脚本骨架

**文件:** `backend/scripts/seed_real_data_2025.py`

- [ ] **Step 1: 编写脚本头和导入**

文件开头：
```python
"""
从 Excel 导入真实收入/毛利明细数据到 financial_data 表。

幂等：仅替换 2025-01 ~ 2025-09 期间数据，保留其他期间不变。
用法:
  python scripts/seed_real_data_2025.py              # 执行导入
  python scripts/seed_real_data_2025.py --dry-run    # 仅预览，不写库
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import openpyxl
import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
```

- [ ] **Step 2: 定义 MYSQL_COLUMN_MAP 常量**

从 `backend/scripts/seed_from_mysql.py:39-129` 复制完整映射字典，添加额外映射：
```python
MYSQL_COLUMN_MAP = {
    # period / entity
    "确认收入日期": "period",
    "确认日期": "period",
    "期间": "period",
    "月份": "period",
    "period": "period",
    "date": "period",
    "销售BGBU": "entity",
    "BGBU": "entity",
    "销售组织": "entity",
    "公司": "entity",
    "部门": "entity",
    "entity": "entity",
    "company": "entity",
    # revenue / cost
    "收入金额": "revenue_amount",
    "收入金额(人民币)": "revenue_amount",
    "含税销售金额(人民币)": "revenue_amount",
    "不含税收入": "revenue_amount",
    "营业收入": "revenue_amount",
    "revenue": "revenue_amount",
    "不含税成本": "cost_amount",
    "成本金额": "cost_amount",
    "营业成本": "cost_amount",
    "cost": "cost_amount",
    # gross profit / margin
    "不含税毛利": "gross_profit_amount",
    "毛利率": "gross_margin_pct",
    # tag fields → stored in tags JSON
    "产品线": "tag:product_line",
    "产品系列": "tag:series",
    "产品大类": "tag:product_category",
    "产品分类": "tag:product_classification",
    "产品族(产品线说明)": "tag:product_family",
    "产品事业部名称": "tag:product_bu_name",
    "产品事业部代码": "tag:product_bu_code",
    "产品所属组织": "tag:product_org",
    "产品归属BGBU": "tag:product_bgbu",
    "销售产品代码": "tag:sales_product_code",
    "销售产品名称": "tag:sales_product_name",
    "物料编码": "tag:material_code",
    "物料描述": "tag:material_desc",
    "物料成本大类": "tag:material_cost_category",
    "一级成本分类": "tag:cost_class_1",
    "二级成本分类": "tag:cost_class_2",
    "三级成本分类": "tag:cost_class_3",
    "成本大类": "tag:cost_category",
    "客户": "tag:customer",
    "客户名称": "tag:customer",
    "NCC客户编码": "tag:ncc_customer_code",
    "订单客户": "tag:order_customer",
    "开票客户简称": "tag:invoice_customer",
    "开票名称": "tag:invoice_name",
    "最终客户名称": "tag:final_customer",
    "上级名称": "tag:superior_name",
    "客户签约类型": "tag:contract_type",
    "订单编号": "tag:order_id",
    "电子商务合同号": "tag:contract_no",
    "合同编号": "tag:contract_no",
    "订单头类型": "tag:order_header_type",
    "订单分类": "tag:order_category",
    "内销/外销": "tag:sales_type",
    "销售部门": "tag:sales_department",
    "HR部门编码": "tag:hr_dept_code",
    "HR部门名称": "tag:hr_department",
    "业务员名称": "tag:sales_person",
    "业务员工号": "tag:sales_person_code",
    "省份名称": "tag:province",
    "细分市场说明": "tag:market_segment",
    "应用场合名称": "tag:application_scenario",
    "项目名称": "tag:project_name",
    "序号": "tag:sequence_no",
    "确认收入年": "tag:revenue_year",
    "确认收入月": "tag:revenue_month",
    "订单登记日期": "tag:order_register_date",
    "币种": "tag:currency",
    "实际开(金税)票状态": "tag:invoice_status",
    "原币对本币的汇率": "tag:exchange_rate_local",
    "原币对人民币的汇率": "tag:exchange_rate_rmb",
    "税率": "tag:tax_rate",
    "订单数量": "tag:order_qty",
    "收入数量": "tag:revenue_qty",
    "订单金额": "tag:order_amount",
    "不含税单位成本": "tag:unit_cost_ex_tax",
    "含税单位成本": "tag:unit_cost_incl_tax",
    "含税成本": "tag:cost_incl_tax",
    "含税毛利": "tag:gross_profit_incl_tax",
    "含税销售金额(本币)": "tag:sales_amount_incl_tax_local",
    "含税销售金额(原币)": "tag:sales_amount_incl_tax_original",
    "收入金额(本币)": "tag:revenue_amount_local",
    "收入金额(原币)": "tag:revenue_amount_original",
    "税额(本币)": "tag:tax_amount_local",
    "市场线BGBU": "tag:bgbu",
    "主营/其他业务": "tag:business_type",
    "客供/逆售_原始": "tag:customer_supplied_original",
    "客供/逆售（其他业务）": "tag:customer_supplied_other",
    "客户签约类型(合并)": "tag:contract_type_merged",
    "成本分类": "tag:cost_category",
    "合计名称": "tag:summary_name",
}

TARGET_PERIODS = [f"2025-{m:02d}" for m in range(1, 10)]
BATCH_SIZE = 50_000
DEFAULT_XLSX_PATH = Path(r"D:\日志\05\21\收入毛利明细数据for驾驶舱_202501-202509.xlsx")
```

- [ ] **Step 3: 编写 build_col_index_map 函数**

```python
def build_col_index_map(headers: list) -> dict[int, str]:
    """将 Excel 列名（按位置）映射到 canonical 键名。"""
    col_map = {}
    unmatched = []
    for idx, header in enumerate(headers):
        header_str = str(header) if header is not None else ""
        if header_str in MYSQL_COLUMN_MAP:
            col_map[idx] = MYSQL_COLUMN_MAP[header_str]
        else:
            unmatched.append((idx, header_str))
    if unmatched:
        print(f"  Warning: {len(unmatched)} columns without mapping: {unmatched[:5]}...")
    return col_map
```

- [ ] **Step 4: 编写行的指标扩展逻辑**

```python
def expand_row_to_metrics(col_map: dict[int, str], vals: list, row_idx: int) -> list[tuple]:
    """将一行 Excel 数据转换为 4 条 financial_data 记录。"""

    def safe_float(v) -> float:
        if v is None:
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    # 提取各字段
    tags = {}
    raw = {}
    period = None
    entity = None
    revenue = None
    cost = None
    gross_profit = None
    margin_pct = None

    for idx, canonical_key in col_map.items():
        raw_val = vals[idx] if idx < len(vals) else None
        header_key = str(vals[idx])  # keep as string representation
        raw[str(canonical_key)] = str(raw_val) if raw_val is not None else None

        if canonical_key == "period":
            if raw_val:
                period = str(raw_val)[:7]  # YYYY-MM-DD → YYYY-MM
        elif canonical_key == "entity":
            if raw_val:
                entity = str(raw_val)
        elif canonical_key == "revenue_amount":
            revenue = safe_float(raw_val)
        elif canonical_key == "cost_amount":
            cost = safe_float(raw_val)
        elif canonical_key == "gross_profit_amount":
            gross_profit = safe_float(raw_val)
        elif canonical_key == "gross_margin_pct":
            margin_pct = safe_float(raw_val)
        elif canonical_key.startswith("tag:"):
            tag_key = canonical_key[4:]  # strip "tag:" prefix
            if raw_val is not None and str(raw_val).strip():
                tags[tag_key] = str(raw_val).strip()

    # 处理缺失值：使用回退策略
    if period is None:
        # 尝试从 revenue_year + revenue_month 组合
        rev_year = tags.get("revenue_year")
        rev_month = tags.get("revenue_month")
        if rev_year and rev_month:
            period = f"{rev_year}-{int(rev_month):02d}"

    if entity is None:
        entity = tags.get("product_bu_name", "UNKNOWN")

    # 计算衍生指标
    if gross_profit is None or gross_profit == 0.0:
        gross_profit = revenue - cost if (revenue is not None and cost is not None) else 0.0

    if margin_pct is None or margin_pct == 0.0:
        margin_pct = (gross_profit / revenue * 100) if (revenue and revenue > 0) else 0.0

    if revenue is None:
        revenue = 0.0
    if cost is None:
        cost = 0.0

    # 构建 raw_row — 保存原始单元格值的字典
    raw_row = {}
    for idx, canonical_key in col_map.items():
        raw_val = vals[idx] if idx < len(vals) else None
        raw_row[canonical_key] = str(raw_val) if raw_val is not None else None

    metrics = [
        ("revenue", round(revenue, 2), "CNY", period, entity, tags, raw_row),
        ("cost", round(cost, 2), "CNY", period, entity, tags, raw_row),
        ("gross_profit", round(gross_profit, 2), "CNY", period, entity, tags, raw_row),
        ("profit_margin", round(margin_pct, 2), "%", period, entity, tags, raw_row),
    ]
    return metrics
```

- [ ] **Step 5: 编写数据库操作函数**

```python
async def delete_target_periods(conn) -> int:
    """删除目标期间的所有数据，返回删除行数。"""
    result = await conn.execute(
        "DELETE FROM financial_data WHERE period = ANY($1)",
        TARGET_PERIODS,
    )
    # asyncpg returns "DELETE X"
    count = int(result.split()[1]) if result.startswith("DELETE") else 0
    return count


async def verify_data(conn):
    """导入后数据验证。"""
    count = await conn.fetchval("SELECT COUNT(*) FROM financial_data")
    print(f"\n  Total rows in financial_data: {count:,}")

    periods = await conn.fetch(
        "SELECT period, COUNT(*) as cnt FROM financial_data "
        "WHERE metric_name = 'revenue' "
        "GROUP BY period ORDER BY period"
    )
    print(f"  Revenue rows by period ({len(periods)} periods):")
    for p in periods:
        print(f"    {p['period']}: {p['cnt']:,}")

    metrics = await conn.fetch(
        "SELECT metric_name, COUNT(*), ROUND(SUM(metric_value)::numeric, 2) as total "
        "FROM financial_data WHERE period LIKE '2025-%' "
        "GROUP BY metric_name ORDER BY metric_name"
    )
    print(f"  2025 metrics summary:")
    for m in metrics:
        print(f"    {m['metric_name']}: count={m['count']:,}, sum={m['total']:,.2f}")

    # 验证 2024 和 2026 数据未被影响
    for yr in ['2024', '2026']:
        c = await conn.fetchval(
            "SELECT COUNT(*) FROM financial_data WHERE period LIKE $1",
            f"{yr}-%"
        )
        print(f"  {yr} data preserved: {c:,} rows")
```

- [ ] **Step 6: 编写主 seed 函数**

```python
async def seed(dry_run: bool = False, xlsx_path: str = None) -> dict:
    """主流程：读取 Excel → 映射 → (dry-run 预览) / (删除 + 写入 + 验证)。"""
    if xlsx_path is None:
        xlsx_path = str(DEFAULT_XLSX_PATH)

    print(f"Reading Excel: {xlsx_path}")
    if not os.path.exists(xlsx_path):
        print(f"ERROR: File not found: {xlsx_path}")
        return {"status": "error", "message": "File not found"}

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    print(f"Sheet: {ws.title}, rows={ws.max_row}, cols={ws.max_column}")

    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    print(f"Headers ({len(headers)} cols): {headers[:5]}...")

    col_map = build_col_index_map(headers)
    mapped_count = sum(1 for v in col_map.values() if not v.startswith("tag:"))
    tag_count = sum(1 for v in col_map.values() if v.startswith("tag:"))
    print(f"Column mapping: {mapped_count} field + {tag_count} tag mappings")

    # 遍历行处理
    all_records = []
    total_source_rows = 0
    skipped_rows = 0
    period_counts = defaultdict(int)

    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        vals = [cell.value for cell in row]

        metrics = expand_row_to_metrics(col_map, vals, row_idx)
        if not metrics:
            skipped_rows += 1
            continue

        # 按期间统计
        record_period = metrics[0][3]  # 从第一个 metric 取 period
        if record_period:
            period_counts[record_period] += 1

        all_records.extend(metrics)
        total_source_rows += 1

        if total_source_rows % 5000 == 0:
            print(f"  Processed {total_source_rows:,} source rows, {len(all_records):,} metric records...")

    wb.close()
    print(f"\nExcel summary: {total_source_rows:,} source rows, {skipped_rows} skipped, {len(all_records):,} metric records")
    print(f"Period coverage: {sorted(period_counts.keys())}")

    if dry_run:
        print("\n=== DRY RUN — No database changes ===")
        return {
            "status": "dry_run",
            "source_rows": total_source_rows,
            "metric_records": len(all_records),
            "periods": sorted(period_counts.keys()),
        }

    if not all_records:
        print("ERROR: No records to insert!")
        return {"status": "error", "message": "No records"}

    # 连接数据库
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://learnhouse:learnhouse@localhost:5432/caiwu",
    )
    conn = await asyncpg.connect(database_url)

    try:
        # 删除目标期间数据
        print(f"\nDeleting existing data for periods: {TARGET_PERIODS[0]} ~ {TARGET_PERIODS[-1]}...")
        deleted = await delete_target_periods(conn)
        print(f"Deleted {deleted:,} rows")

        # 批量插入
        print(f"Inserting {len(all_records):,} records in batches of {BATCH_SIZE:,}...")
        total_inserted = 0
        for i in range(0, len(all_records), BATCH_SIZE):
            batch = all_records[i: i + BATCH_SIZE]
            # Serialize JSON fields
            serialized_batch = []
            for rec in batch:
                serialized_batch.append((
                    rec[0],  # metric_name
                    rec[1],  # metric_value
                    rec[2],  # metric_unit
                    rec[3],  # period
                    rec[4],  # entity
                    json.dumps(rec[5], ensure_ascii=False) if rec[5] else None,  # tags
                    json.dumps(rec[6], ensure_ascii=False) if rec[6] else None,  # raw_row
                ))
            await conn.copy_records_to_table(
                "financial_data",
                columns=["metric_name", "metric_value", "metric_unit", "period", "entity", "tags", "raw_row"],
                records=serialized_batch,
            )
            total_inserted += len(batch)
            print(f"  Inserted {total_inserted:,}/{len(all_records):,}")

        # 验证
        print(f"\n=== Verification ===")
        await verify_data(conn)

    finally:
        await conn.close()

    print(f"\nDone! Imported {total_inserted:,} metric records from {total_source_rows:,} Excel rows.")
    return {"status": "success", "inserted": total_inserted, "source_rows": total_source_rows}
```

- [ ] **Step 7: 编写 main 入口**

```python
def main():
    parser = argparse.ArgumentParser(description="Import real financial data from Excel")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    parser.add_argument("--xlsx-path", default=None, help="Path to Excel file")
    args = parser.parse_args()

    result = asyncio.run(seed(dry_run=args.dry_run, xlsx_path=args.xlsx_path))
    print(f"\nResult: {json.dumps(result, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
```

### Task 2: Dry-run 测试

- [ ] **Step 1: 运行 dry-run 验证解析逻辑**

Run:
```bash
cd /d/workspace/caiwu04/backend && python scripts/seed_real_data_2025.py --dry-run
```

Expected output:
```
Reading Excel: D:\日志\05\21\收入毛利明细数据for驾驶舱_202501-202509.xlsx
Sheet: ..., rows=..., cols=71
Headers (71 cols): ...
Column mapping: ... field + ... tag mappings
Processed 5000 source rows...
Excel summary: ... source rows, ... metric records
Period coverage: ['2025-01', '2025-02', ..., '2025-09']
=== DRY RUN — No database changes ===
```

- [ ] **Step 2: 验证指标合理性**

检查 dry-run 输出的期间覆盖、记录数是否合理。确认 revenue/cost/gross_profit 值均为正数，毛利率在合理范围。

### Task 3: 正式导入

- [ ] **Step 1: 执行导入**

Run:
```bash
cd /d/workspace/caiwu04/backend && python scripts/seed_real_data_2025.py
```

Expected output:
```
Deleting existing data for periods: 2025-01 ~ 2025-09...
Deleted ... rows

Inserting ... records in batches...
  Inserted ...
Done! Imported ... metric records from ... Excel rows.

=== Verification ===
  Total rows in financial_data: ...
  Revenue rows by period (9 periods):
    2025-01: ...
    ...
  2025 metrics summary:
    revenue: count=..., sum=...
    cost: count=..., sum=...
    gross_profit: count=..., sum=...
    profit_margin: count=..., sum=...
  2024 data preserved: ... rows
  2026 data preserved: ... rows
```

- [ ] **Step 2: 验证幂等性**

再次运行相同命令，确认行数一致：
```
Deleted ... rows
Inserted ... records
```
两次插入总数应相同。

### Task 4: 端到端集成验证

- [ ] **Step 1: 重启后端服务**

如果后端未运行，先启动：
```bash
cd /d/workspace/caiwu04/backend && uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

- [ ] **Step 2: 验证 API 返回真实数据**

```bash
# 获取 token
TOKEN=$(curl -s -X POST http://localhost:8002/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 验证 Dashboard BFF（检查 KPI 值是否合理——不再为 0 或随机 mock 值）
curl -s "http://localhost:8002/api/v1/dashboard/bff" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_type":"web"}' | python -c "
import sys, json
d = json.load(sys.stdin)
kpis = d.get('data',{}).get('kpis',[])
for k in kpis[:6]:
    print(f'{k.get(\"label\",\"?\")}: {k.get(\"value\",\"?\")} {k.get(\"unit\",\"\")}')
"

# 验证 filter-options 返回正确期间（应包含 2025-01 ~ 2025-09）
curl -s "http://localhost:8002/api/v1/filter-options?dimension=period" \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
d = json.load(sys.stdin)
opts = d.get('data',{}).get('options',[])
print(f'Periods: {opts[:12]}')
"
```

- [ ] **Step 3: 检查 Dashboard 数据前后对比**

登录前端 http://localhost:3006，对比导入前后的 KPI 数值变化：
- 原 mock 数据：随机高斯分布值
- 新真实数据：应反映实际业务数值
- KPI card 显示的 revenue/cost/gross_profit 应显著变化

### Task 5: (可选) 数据导出脚本

如需备份现有数据或导出验证，可以使用：

```sql
-- 导出 2025 年数据
COPY (
  SELECT metric_name, metric_value, period, entity, tags
  FROM financial_data
  WHERE period LIKE '2025-%'
  ORDER BY period, entity, metric_name
) TO 'D:/workspace/caiwu04/backend/output/financial_data_2025_export.csv'
WITH CSV HEADER;
```

---

## 验证清单

- [ ] `--dry-run` 输出合理，期间覆盖 2025-01 ~ 2025-09
- [ ] 导入后 2024 年和 2026 年数据未被影响（保留原 mock 数据）
- [ ] 2025 年 9 个月的总 revenue 为正数且合理
- [ ] Dashboard BFF 返回的 KPI 值反映真实数据（非 mock 值）
- [ ] filter-options 中 period 维度显示 2025-01 ~ 2025-09
- [ ] 幂等性验证通过（重新运行结果一致）
- [ ] 前端可视化图表基于真实数据展示