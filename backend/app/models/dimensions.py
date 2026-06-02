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