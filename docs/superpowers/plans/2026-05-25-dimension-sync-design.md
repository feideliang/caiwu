# 大宽表 → 维度表同步流程设计

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 `income_margin_detail` 大宽表抽取客户、产品、组织架构等维度表，设计幂等同步脚本 + Celery 定时任务，使其他表可以基于维度表做关联分析。

**Architecture:** 在 PostgreSQL 内创建 4 张维度表（DimCustomer/DimProduct/DimOrganization/DimProject），通过 `INSERT ... ON CONFLICT` (MERGE) 从宽表按业务键去重抽取。同步逻辑封装为独立 Python 脚本 + Celery 定时任务。

**Tech Stack:** SQLAlchemy ORM (模型定义) + asyncpg (同步脚本) + Celery (定时同步)

---

## 文件结构

| 文件 | 作用 |
|------|------|
| `backend/app/models/dimensions.py` | 4 个维度表 SQLAlchemy 模型 |
| `backend/app/models/__init__.py` | 导出新模型 |
| `backend/migrations/versions/d2_create_dimension_tables.py` | Alembic 迁移 |
| `backend/scripts/sync_dimensions.py` | 维度同步脚本（幂等） |
| `backend/app/tasks/dim_sync.py` | Celery 定时任务封装 |
| `backend/app/celery_app.py` | 注册 beat_schedule |

## 维度表设计

### DimCustomer (客户维度)

从宽表 customer 相关字段抽取唯一客户记录。

- 业务键: `customer` (客户名称)
- 同步逻辑: SELECT DISTINCT customer, ncc_customer_code, invoice_customer, invoice_name, final_customer, superior_name, contract_type, contract_type_merged, customer_supplied_original, customer_supplied_other, province FROM income_margin_detail WHERE customer IS NOT NULL

```sql
CREATE TABLE dim_customer (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(256) NOT NULL UNIQUE,  -- 业务键
    ncc_customer_code VARCHAR(64),
    invoice_customer VARCHAR(256),
    invoice_name VARCHAR(256),
    final_customer VARCHAR(256),
    superior_name VARCHAR(256),
    contract_type VARCHAR(64),
    contract_type_merged VARCHAR(64),
    customer_supplied_original VARCHAR(64),
    customer_supplied_other VARCHAR(64),
    province VARCHAR(64),
    first_seen_period VARCHAR(32),
    last_seen_period VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### DimProduct (产品维度)

从宽表 product 相关字段抽取唯一产品记录。

- 业务键: `sales_product_code` (销售产品代码) 或 `material_code`
- 同步逻辑: SELECT DISTINCT product_category, product_classification, product_bu_code, product_bu_name, product_bgbu, product_org, series, product_line, product_family, sales_product_code, sales_product_name, material_code, material_desc, material_cost_category FROM income_margin_detail WHERE sales_product_code IS NOT NULL

```sql
CREATE TABLE dim_product (
    id SERIAL PRIMARY KEY,
    product_code VARCHAR(128) NOT NULL UNIQUE,  -- 业务键 (sales_product_code)
    product_name VARCHAR(256),
    category VARCHAR(128),
    classification VARCHAR(128),
    bu_code VARCHAR(64),
    bu_name VARCHAR(256),
    bgbu VARCHAR(128),
    org VARCHAR(256),
    series VARCHAR(256),
    product_line VARCHAR(256),
    family VARCHAR(256),
    material_code VARCHAR(128),
    material_desc TEXT,
    material_cost_category VARCHAR(128),
    first_seen_period VARCHAR(32),
    last_seen_period VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### DimOrganization (组织架构维度)

从宽表 entity/company/hr 相关字段抽取唯一组织记录。

- 业务键: `entity` (销售BGBU/事业部)
- 同步逻辑: SELECT DISTINCT entity, company, hr_dept_code, hr_department, sales_department, bgbu, business_type, region FROM income_margin_detail WHERE entity IS NOT NULL

```sql
CREATE TABLE dim_organization (
    id SERIAL PRIMARY KEY,
    entity_name VARCHAR(128) NOT NULL UNIQUE,  -- 业务键
    company VARCHAR(128),
    hr_dept_code VARCHAR(64),
    hr_department VARCHAR(256),
    sales_department VARCHAR(256),
    bgbu VARCHAR(64),
    business_type VARCHAR(64),
    region VARCHAR(128),
    first_seen_period VARCHAR(32),
    last_seen_period VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### DimProject (项目/应用维度)

从宽表 project/application 字段抽取唯一项目记录。

- 业务键: `project_name`
- 同步逻辑: SELECT DISTINCT project_name, application_scenario, summary_name FROM income_margin_detail WHERE project_name IS NOT NULL

```sql
CREATE TABLE dim_project (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(256) NOT NULL UNIQUE,  -- 业务键
    application_scenario VARCHAR(256),
    summary_name VARCHAR(256),
    first_seen_period VARCHAR(32),
    last_seen_period VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

### Task 1: 创建维度表模型

**Files:**
- Create: `backend/app/models/dimensions.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 dimensions.py 模型文件**

```python
"""Dimension tables extracted from income_margin_detail wide table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


class DimCustomer(Base):
    __tablename__ = "dim_customer"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    ncc_customer_code: Mapped[str | None] = mapped_column(String(64))
    invoice_customer: Mapped[str | None] = mapped_column(String(256))
    invoice_name: Mapped[str | None] = mapped_column(String(256))
    final_customer: Mapped[str | None] = mapped_column(String(256))
    superior_name: Mapped[str | None] = mapped_column(String(256))
    contract_type: Mapped[str | None] = mapped_column(String(64))
    contract_type_merged: Mapped[str | None] = mapped_column(String(64))
    customer_supplied_original: Mapped[str | None] = mapped_column(String(64))
    customer_supplied_other: Mapped[str | None] = mapped_column(String(64))
    province: Mapped[str | None] = mapped_column(String(64))
    first_seen_period: Mapped[str | None] = mapped_column(String(32))
    last_seen_period: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DimProduct(Base):
    __tablename__ = "dim_product"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str | None] = mapped_column(String(128))
    classification: Mapped[str | None] = mapped_column(String(128))
    bu_code: Mapped[str | None] = mapped_column(String(64))
    bu_name: Mapped[str | None] = mapped_column(String(256))
    bgbu: Mapped[str | None] = mapped_column(String(128))
    org: Mapped[str | None] = mapped_column(String(256))
    series: Mapped[str | None] = mapped_column(String(256))
    product_line: Mapped[str | None] = mapped_column(String(256))
    family: Mapped[str | None] = mapped_column(String(256))
    material_code: Mapped[str | None] = mapped_column(String(128))
    material_desc: Mapped[str | None] = mapped_column(Text)
    material_cost_category: Mapped[str | None] = mapped_column(String(128))
    first_seen_period: Mapped[str | None] = mapped_column(String(32))
    last_seen_period: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DimOrganization(Base):
    __tablename__ = "dim_organization"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(128))
    hr_dept_code: Mapped[str | None] = mapped_column(String(64))
    hr_department: Mapped[str | None] = mapped_column(String(256))
    sales_department: Mapped[str | None] = mapped_column(String(256))
    bgbu: Mapped[str | None] = mapped_column(String(64))
    business_type: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(128))
    first_seen_period: Mapped[str | None] = mapped_column(String(32))
    last_seen_period: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DimProject(Base):
    __tablename__ = "dim_project"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    application_scenario: Mapped[str | None] = mapped_column(String(256))
    summary_name: Mapped[str | None] = mapped_column(String(256))
    first_seen_period: Mapped[str | None] = mapped_column(String(32))
    last_seen_period: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: 更新 models/__init__.py**

```python
from app.models.dimensions import DimCustomer, DimProduct, DimOrganization, DimProject
```

并添加到 `__all__`。

### Task 2: 创建 Alembic 迁移

**Files:**
- Create: `backend/migrations/versions/d2_create_dimension_tables.py`

- [ ] **Step 1: 创建迁移文件**

```python
"""create dimension tables (customer/product/org/project)

Revision ID: d2_create_dimension_tables
Revises: c1d69a6c233f
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "d2_create_dimension_tables"
down_revision = "c1d69a6c233f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DimCustomer
    op.create_table(
        "dim_customer",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("customer_name", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("ncc_customer_code", sa.String(64)),
        sa.Column("invoice_customer", sa.String(256)),
        sa.Column("invoice_name", sa.String(256)),
        sa.Column("final_customer", sa.String(256)),
        sa.Column("superior_name", sa.String(256)),
        sa.Column("contract_type", sa.String(64)),
        sa.Column("contract_type_merged", sa.String(64)),
        sa.Column("customer_supplied_original", sa.String(64)),
        sa.Column("customer_supplied_other", sa.String(64)),
        sa.Column("province", sa.String(64)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DimProduct
    op.create_table(
        "dim_product",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("product_name", sa.String(256)),
        sa.Column("category", sa.String(128)),
        sa.Column("classification", sa.String(128)),
        sa.Column("bu_code", sa.String(64)),
        sa.Column("bu_name", sa.String(256)),
        sa.Column("bgbu", sa.String(128)),
        sa.Column("org", sa.String(256)),
        sa.Column("series", sa.String(256)),
        sa.Column("product_line", sa.String(256)),
        sa.Column("family", sa.String(256)),
        sa.Column("material_code", sa.String(128)),
        sa.Column("material_desc", sa.Text),
        sa.Column("material_cost_category", sa.String(128)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DimOrganization
    op.create_table(
        "dim_organization",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_name", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("company", sa.String(128)),
        sa.Column("hr_dept_code", sa.String(64)),
        sa.Column("hr_department", sa.String(256)),
        sa.Column("sales_department", sa.String(256)),
        sa.Column("bgbu", sa.String(64)),
        sa.Column("business_type", sa.String(64)),
        sa.Column("region", sa.String(128)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DimProject
    op.create_table(
        "dim_project",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_name", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("application_scenario", sa.String(256)),
        sa.Column("summary_name", sa.String(256)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("dim_project")
    op.drop_table("dim_organization")
    op.drop_table("dim_product")
    op.drop_table("dim_customer")
```

- [ ] **Step 2: 运行迁移**

```bash
cd /d/workspace/caiwu04/backend && alembic -c migrations/alembic.ini upgrade head
```

Expected: 新表 dim_customer, dim_product, dim_organization, dim_project 创建成功。

### Task 3: 编写维度同步脚本

**Files:**
- Create: `backend/scripts/sync_dimensions.py`

- [ ] **Step 1: 创建同步脚本**

```python
"""
从 income_margin_detail 大宽表同步维度表（幂等）。

使用 INSERT ... ON CONFLICT (DO UPDATE) 实现 upsert 语义。
可独立运行，也可被 Celery 任务调用。

用法:
  python scripts/sync_dimensions.py              # 执行同步
  python scripts/sync_dimensions.py --dry-run    # 仅预览
  python scripts/sync_dimensions.py --table customer  # 仅同步指定维度
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── SQL definitions ─────────────────────────────────────────────

UPSERT_CUSTOMER = """
INSERT INTO dim_customer (
    customer_name, ncc_customer_code, invoice_customer, invoice_name,
    final_customer, superior_name, contract_type, contract_type_merged,
    customer_supplied_original, customer_supplied_other, province,
    first_seen_period, last_seen_period
)
SELECT
    w.customer AS customer_name,
    MIN(w.ncc_customer_code) AS ncc_customer_code,
    MIN(w.invoice_customer) AS invoice_customer,
    MIN(w.invoice_name) AS invoice_name,
    MIN(w.final_customer) AS final_customer,
    MIN(w.superior_name) AS superior_name,
    MIN(w.contract_type) AS contract_type,
    MIN(w.contract_type_merged) AS contract_type_merged,
    MIN(w.customer_supplied_original) AS customer_supplied_original,
    MIN(w.customer_supplied_other) AS customer_supplied_other,
    MIN(w.province) AS province,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.customer IS NOT NULL
GROUP BY w.customer
ON CONFLICT (customer_name) DO UPDATE SET
    ncc_customer_code        = EXCLUDED.ncc_customer_code,
    invoice_customer         = EXCLUDED.invoice_customer,
    invoice_name             = EXCLUDED.invoice_name,
    final_customer           = EXCLUDED.final_customer,
    superior_name            = EXCLUDED.superior_name,
    contract_type            = EXCLUDED.contract_type,
    contract_type_merged     = EXCLUDED.contract_type_merged,
    customer_supplied_original = EXCLUDED.customer_supplied_original,
    customer_supplied_other  = EXCLUDED.customer_supplied_other,
    province                 = EXCLUDED.province,
    first_seen_period        = LEAST(dim_customer.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_customer.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

COUNT_CUSTOMER = "SELECT COUNT(*) FROM dim_customer;"

UPSERT_PRODUCT = """
INSERT INTO dim_product (
    product_code, product_name, category, classification,
    bu_code, bu_name, bgbu, org, series, product_line, family,
    material_code, material_desc, material_cost_category,
    first_seen_period, last_seen_period
)
SELECT
    w.sales_product_code AS product_code,
    MIN(w.sales_product_name) AS product_name,
    MIN(w.product_category) AS category,
    MIN(w.product_classification) AS classification,
    MIN(w.product_bu_code) AS bu_code,
    MIN(w.product_bu_name) AS bu_name,
    MIN(w.product_bgbu) AS bgbu,
    MIN(w.product_org) AS org,
    MIN(w.series) AS series,
    MIN(w.product_line) AS product_line,
    MIN(w.product_family) AS family,
    MIN(w.material_code) AS material_code,
    MIN(w.material_desc) AS material_desc,
    MIN(w.material_cost_category) AS material_cost_category,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.sales_product_code IS NOT NULL
GROUP BY w.sales_product_code
ON CONFLICT (product_code) DO UPDATE SET
    product_name             = EXCLUDED.product_name,
    category                 = EXCLUDED.category,
    classification           = EXCLUDED.classification,
    bu_code                  = EXCLUDED.bu_code,
    bu_name                  = EXCLUDED.bu_name,
    bgbu                     = EXCLUDED.bgbu,
    org                      = EXCLUDED.org,
    series                   = EXCLUDED.series,
    product_line             = EXCLUDED.product_line,
    family                   = EXCLUDED.family,
    material_code            = EXCLUDED.material_code,
    material_desc            = EXCLUDED.material_desc,
    material_cost_category   = EXCLUDED.material_cost_category,
    first_seen_period        = LEAST(dim_product.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_product.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

COUNT_PRODUCT = "SELECT COUNT(*) FROM dim_product;"

UPSERT_ORGANIZATION = """
INSERT INTO dim_organization (
    entity_name, company, hr_dept_code, hr_department,
    sales_department, bgbu, business_type, region,
    first_seen_period, last_seen_period
)
SELECT
    w.entity AS entity_name,
    MIN(w.company) AS company,
    MIN(w.hr_dept_code) AS hr_dept_code,
    MIN(w.hr_department) AS hr_department,
    MIN(w.sales_department) AS sales_department,
    MIN(w.bgbu) AS bgbu,
    MIN(w.business_type) AS business_type,
    MIN(w.region) AS region,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.entity IS NOT NULL
GROUP BY w.entity
ON CONFLICT (entity_name) DO UPDATE SET
    company                  = EXCLUDED.company,
    hr_dept_code             = EXCLUDED.hr_dept_code,
    hr_department            = EXCLUDED.hr_department,
    sales_department         = EXCLUDED.sales_department,
    bgbu                     = EXCLUDED.bgbu,
    business_type            = EXCLUDED.business_type,
    region                   = EXCLUDED.region,
    first_seen_period        = LEAST(dim_organization.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_organization.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

COUNT_ORGANIZATION = "SELECT COUNT(*) FROM dim_organization;"

UPSERT_PROJECT = """
INSERT INTO dim_project (
    project_name, application_scenario, summary_name,
    first_seen_period, last_seen_period
)
SELECT
    w.project_name,
    MIN(w.application_scenario) AS application_scenario,
    MIN(w.summary_name) AS summary_name,
    MIN(w.period) AS first_seen_period,
    MAX(w.period) AS last_seen_period
FROM income_margin_detail w
WHERE w.project_name IS NOT NULL
GROUP BY w.project_name
ON CONFLICT (project_name) DO UPDATE SET
    application_scenario     = EXCLUDED.application_scenario,
    summary_name             = EXCLUDED.summary_name,
    first_seen_period        = LEAST(dim_project.first_seen_period, EXCLUDED.first_seen_period),
    last_seen_period         = GREATEST(dim_project.last_seen_period, EXCLUDED.last_seen_period),
    updated_at               = NOW();
"""

COUNT_PROJECT = "SELECT COUNT(*) FROM dim_project;"

SYNC_TABLES = {
    "customer":     (UPSERT_CUSTOMER,     COUNT_CUSTOMER,     "dim_customer"),
    "product":      (UPSERT_PRODUCT,      COUNT_PRODUCT,      "dim_product"),
    "organization": (UPSERT_ORGANIZATION, COUNT_ORGANIZATION, "dim_organization"),
    "project":      (UPSERT_PROJECT,      COUNT_PROJECT,      "dim_project"),
}


# ── Main ───────────────────────────────────────────────────────

async def sync(table: str | None = None, dry_run: bool = False) -> dict:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://learnhouse:learnhouse@localhost:5432/caiwu",
    )
    conn = await asyncpg.connect(database_url)
    t0 = time.time()

    try:
        tables_to_sync = {table: SYNC_TABLES[table]} if table else SYNC_TABLES
        results = {}

        for tbl, (upsert_sql, count_sql, display_name) in tables_to_sync.items():
            print(f"Syncing {display_name}...")
            t1 = time.time()

            if dry_run:
                # In dry-run mode, just count what would be synced
                src_count = await conn.fetchval(
                    "SELECT COUNT(DISTINCT w.customer) FROM income_margin_detail w WHERE w.customer IS NOT NULL"
                    if tbl == "customer" else
                    "SELECT COUNT(DISTINCT w.sales_product_code) FROM income_margin_detail w WHERE w.sales_product_code IS NOT NULL"
                    if tbl == "product" else
                    "SELECT COUNT(DISTINCT w.entity) FROM income_margin_detail w WHERE w.entity IS NOT NULL"
                    if tbl == "organization" else
                    "SELECT COUNT(DISTINCT w.project_name) FROM income_margin_detail w WHERE w.project_name IS NOT NULL"
                )
                print(f"  Would sync ~{src_count:,} unique records  [{time.time() - t1:.0f}s]")
                results[tbl] = {"status": "dry_run", "source_count": src_count}
            else:
                # Execute upsert
                status = await conn.execute(upsert_sql)
                after = await conn.fetchval(count_sql)
                print(f"  Upserted, now {after:,} records  [{time.time() - t1:.0f}s]")
                results[tbl] = {"status": "synced", "count": after}

        print(f"\nTotal time: {time.time() - t0:.0f}s")
        return results

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Sync dimension tables from income_margin_detail")
    parser.add_argument("--table", choices=list(SYNC_TABLES.keys()), help="Sync only one table")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    result = asyncio.run(sync(table=args.table, dry_run=args.dry_run))
    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行 dry-run**

```bash
cd /d/workspace/caiwu04/backend && python scripts/sync_dimensions.py --dry-run
```

Expected output:
```
Syncing dim_customer...
  Would sync ~xx,xxx unique records
Syncing dim_product...
  Would sync ~xx,xxx unique records
Syncing dim_organization...
  Would sync ~xxx unique records
Syncing dim_project...
  Would sync ~xx,xxx unique records
```

### Task 4: 执行维度同步

- [ ] **Step 1: 创建迁移表 + 运行同步**

```bash
cd /d/workspace/caiwu04/backend
alembic -c migrations/alembic.ini upgrade head
python scripts/sync_dimensions.py
```

Expected:
```
Syncing dim_customer...
  Upserted, now N records
Syncing dim_product...
  Upserted, now N records
Syncing dim_organization...
  Upserted, now N records
Syncing dim_project...
  Upserted, now N records
```

- [ ] **Step 2: 验证维度表数据**

```bash
python -c "
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.environ.get('DATABASE_URL', 'postgresql://learnhouse:learnhouse@localhost:5432/caiwu'))
    for tbl in ['dim_customer', 'dim_product', 'dim_organization', 'dim_project']:
        c = await conn.fetchval(f'SELECT COUNT(*) FROM {tbl}')
        print(f'{tbl}: {c:,} rows')
    await conn.close()
asyncio.run(check())
"
```

Expected: 每张表有合理数量的记录（非零）。

### Task 5: 创建 Celery 定时同步任务

**Files:**
- Create: `backend/app/tasks/dim_sync.py`
- Modify: `backend/app/celery_app.py`
- Modify: `backend/app/tasks/__init__.py`

- [ ] **Step 1: 创建 Celery 任务**

```python
"""Celery task: sync dimension tables from wide table."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_sync() -> dict:
    """Run all dimension syncs asynchronously."""
    import asyncpg
    from app.config import settings

    # Build sync URL (non-asyncpg variant for asyncpg usage)
    dsn = (
        f"postgresql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
    conn = await asyncpg.connect(dsn)

    try:
        from scripts.sync_dimensions import SYNC_TABLES

        results = {}
        for tbl, (upsert_sql, count_sql, display_name) in SYNC_TABLES.items():
            logger.info("Syncing %s...", display_name)
            await conn.execute(upsert_sql)
            count = await conn.fetchval(count_sql)
            results[tbl] = count
            logger.info("%s synced: %d records", display_name, count)

        return {"status": "ok", "counts": results}
    finally:
        await conn.close()


@celery_app.task(
    name="dim_sync.sync_all_dimensions",
    queue="data_sync",
    bind=True,
    acks_late=True,
    max_retries=2,
    default_retry_delay=30,
)
def sync_all_dimensions(self) -> dict:
    """Sync all dimension tables from income_margin_detail wide table."""
    logger.info("Starting dimension sync")
    try:
        result = asyncio.run(_run_sync())
        logger.info("Dimension sync complete: %s", result)
        return result
    except Exception as exc:
        logger.exception("Dimension sync failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
```

- [ ] **Step 2: 更新 tasks/__init__.py**

```python
from app.tasks.dim_sync import sync_all_dimensions  # noqa: F401
```

- [ ] **Step 3: 在 celery_app.py 注册定时调度**

在 `beat_schedule` 中添加每日同步：

```python
beat_schedule={
    # ... existing entries ...
    "daily-dimension-sync": {
        "task": "dim_sync.sync_all_dimensions",
        "schedule": crontab(hour=4, minute=0),  # daily at 04:00
    },
},
```

### Task 6: 端到端验证

- [ ] **Step 1: 重启 Celery worker**

```bash
cd /d/workspace/caiwu04/backend
celery -A app.celery_app worker -Q data_sync -l info --concurrency=1
```

- [ ] **Step 2: 手动触发同步任务**

```bash
cd /d/workspace/caiwu04/backend
python -c "
from app.celery_app import celery_app
from app.tasks.dim_sync import sync_all_dimensions
result = sync_all_dimensions.delay()
print('Task dispatched:', result.id)
"
```

- [ ] **Step 3: 验证维度表可被 API 查询**

```bash
# 验证维度表有数据
psql -U postgres -d caiwu -c "SELECT COUNT(*) FROM dim_customer;"
psql -U postgres -d caiwu -c "SELECT COUNT(*) FROM dim_product;"
psql -U postgres -d caiwu -c "SELECT COUNT(*) FROM dim_organization;"
psql -U postgres -d caiwu -c "SELECT COUNT(*) FROM dim_project;"
```

---

## 验证清单

- [ ] 4 张维度表通过 Alembic 迁移创建
- [ ] `sync_dimensions.py --dry-run` 输出合理（表非空）
- [ ] `sync_dimensions.py` 全量同步成功
- [ ] 维度表 upsert 幂等（重新运行结果一致）
- [ ] Celery 任务 `dim_sync.sync_all_dimensions` 可触发执行
- [ ] beat_schedule 配置了每日 04:00 自动同步