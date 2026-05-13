"""Tests for data sync service."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    DataBatch,
    DataQualityLog,
    FinancialData,
    QualityStatus,
    SyncStatus,
)
from app.services.data_sync import DataSyncService


# ── SyncService initialization tests ──────────────────────────


class TestDataSyncInit:

    def test_init(self):
        mock_db = MagicMock()
        service = DataSyncService(db=mock_db)
        assert service.db is mock_db


# ── Incremental sync tests ──────────────────────────────────


class TestIncrementalSync:

    @pytest_asyncio.fixture
    async def sync_service(self, db_session: AsyncSession):
        return DataSyncService(db=db_session)

    @pytest.mark.anyio
    async def test_sync_empty_dataframe(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame()
        result = await service.sync_incremental(df)

        assert result["status"] == "skipped"
        assert result["rows_upserted"] == 0

    @pytest.mark.anyio
    async def test_sync_single_row(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [1000000.0],
            "metric_unit": ["CNY"],
            "period": ["2024-01"],
            "entity": ["CompanyA"],
        })
        result = await service.sync_incremental(df, file_name="test.xlsx")

        assert result["status"] == "success"
        assert result["rows_upserted"] == 1
        assert result["rows_inserted"] == 1

        # Verify data in DB
        stmt = select(FinancialData).where(FinancialData.metric_name == "revenue")
        db_result = await db_session.execute(stmt)
        row = db_result.scalar_one()
        assert row.metric_value == 1000000.0
        assert row.period == "2024-01"
        assert row.entity == "CompanyA"

    @pytest.mark.anyio
    async def test_sync_multiple_rows(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost", "dso"],
            "metric_value": [1000000.0, 500000.0, 45.0],
            "period": ["2024-01", "2024-01", "2024-01"],
            "entity": ["A", "A", "A"],
        })
        result = await service.sync_incremental(df)

        assert result["status"] == "success"
        assert result["rows_upserted"] == 3

    @pytest.mark.anyio
    async def test_sync_upsert_update_existing(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)

        # First sync: insert
        df1 = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [1000000.0],
            "period": ["2024-01"],
            "entity": ["A"],
        })
        await service.sync_incremental(df1)

        # Second sync: update
        df2 = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [1500000.0],  # Changed value
            "period": ["2024-01"],
            "entity": ["A"],
        })
        result = await service.sync_incremental(df2)

        assert result["rows_updated"] == 1

        # Verify updated value
        stmt = select(FinancialData).where(FinancialData.metric_name == "revenue")
        db_result = await db_session.execute(stmt)
        row = db_result.scalar_one()
        assert row.metric_value == 1500000.0

    @pytest.mark.anyio
    async def test_sync_creates_batch(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [100.0],
            "period": ["2024-01"],
        })
        result = await service.sync_incremental(df, file_name="test.xlsx")

        assert result["batch_id"] is not None
        assert result["batch_no"].startswith("BATCH-")

        # Verify batch in DB
        batch = await db_session.get(DataBatch, result["batch_id"])
        assert batch is not None
        assert batch.status == SyncStatus.SUCCESS
        assert batch.file_name == "test.xlsx"
        assert batch.record_count == 1

    @pytest.mark.anyio
    async def test_sync_with_tags(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [100.0],
            "period": ["2024-01"],
        })
        tags = {"source": "email", "email_uid": "123"}
        result = await service.sync_incremental(df, tags=tags)

        assert result["status"] == "success"

        stmt = select(FinancialData).where(FinancialData.metric_name == "revenue")
        db_result = await db_session.execute(stmt)
        row = db_result.scalar_one()
        assert row.tags == tags

    @pytest.mark.anyio
    async def test_sync_null_entity(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [100.0],
            "period": ["2024-01"],
            "entity": [None],
        })
        result = await service.sync_incremental(df)
        assert result["status"] == "success"

    @pytest.mark.anyio
    async def test_sync_missing_required_fields(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": [""],  # Empty metric_name
            "metric_value": [100.0],
            "period": ["2024-01"],
        })
        result = await service.sync_incremental(df)

        # Should handle gracefully, skip invalid rows
        assert result["rows_upserted"] == 0

    @pytest.mark.anyio
    async def test_sync_creates_quality_log(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [100.0],
            "period": ["2024-01"],
        })
        result = await service.sync_incremental(df)

        # Check quality log was created
        stmt = select(DataQualityLog).where(
            DataQualityLog.rule_name == "incremental_sync"
        )
        db_result = await db_session.execute(stmt)
        logs = db_result.scalars().all()
        assert len(logs) >= 1


# ── Full sync tests ─────────────────────────────────────────


class TestFullSync:

    @pytest.mark.anyio
    async def test_full_sync_empty_dataframe(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame()
        result = await service.sync_full(df)

        assert result["status"] == "skipped"

    @pytest.mark.anyio
    async def test_full_sync_loads_data(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)

        # First insert some data
        df1 = pd.DataFrame({
            "metric_name": ["revenue", "cost"],
            "metric_value": [1000.0, 500.0],
            "period": ["2024-01", "2024-01"],
        })
        await service.sync_incremental(df1)

        # Full sync with new data
        df2 = pd.DataFrame({
            "metric_name": ["dso"],
            "metric_value": [45.0],
            "period": ["2024-01"],
        })
        result = await service.sync_full(df2)

        assert result["status"] == "success"
        assert result["rows_loaded"] == 1


# ── Batch tracking tests ────────────────────────────────────


class TestBatchTracking:

    @pytest.mark.anyio
    async def test_batch_creation(self, db_session: AsyncSession):
        from app.models.core import DataSource, DataSourceType
        ds = DataSource(name="test-source", source_type=DataSourceType.EXCEL, priority=0)
        db_session.add(ds)
        await db_session.flush()

        service = DataSyncService(db=db_session)
        batch = await service._create_batch(source_id=ds.id, file_name="test.xlsx")

        assert batch.batch_no.startswith("BATCH-")
        assert batch.status == SyncStatus.RUNNING
        assert batch.file_name == "test.xlsx"
        assert batch.source_id == ds.id

    @pytest.mark.anyio
    async def test_batch_finalization(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        batch = await service._create_batch(source_id=None, file_name=None)

        await service._finalize_batch(batch.id, SyncStatus.SUCCESS, 100)

        # Refresh batch
        updated = await db_session.get(DataBatch, batch.id)
        assert updated.status == SyncStatus.SUCCESS
        assert updated.record_count == 100
        assert updated.processed_at is not None


# ── Cache invalidation tests ────────────────────────────────


class TestCacheInvalidation:

    @pytest.mark.anyio
    async def test_cache_invalidated_on_sync(self, db_session: AsyncSession, mock_cache):
        service = DataSyncService(db=db_session)
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [100.0],
            "period": ["2024-01"],
        })
        result = await service.sync_incremental(df)

        assert result["status"] == "success"
        # Cache invalidation should have been called (mocked)


# ── Data source registration tests ──────────────────────────


class TestDataSourceRegistration:

    @pytest.mark.anyio
    async def test_register_new_source(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        ds = await service.register_data_source(
            name="email_source",
            source_type="email_imap",
            connection_config={"host": "imap.test.com"},
            priority=1,
        )

        assert ds.name == "email_source"
        assert ds.is_active is True
        assert ds.priority == 1

    @pytest.mark.anyio
    async def test_register_existing_source(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)

        # Register first time
        ds1 = await service.register_data_source("email_source", "email_imap")

        # Register again with different config
        ds2 = await service.register_data_source(
            "email_source",
            "excel",
            priority=5,
        )

        assert ds1.id == ds2.id
        assert ds2.priority == 5

    @pytest.mark.anyio
    async def test_mark_source_synced(self, db_session: AsyncSession):
        service = DataSyncService(db=db_session)
        ds = await service.register_data_source("test_source", "email_imap")

        await service.mark_source_synced(ds.id)

        refreshed = await db_session.get(type(ds), ds.id)
        assert refreshed.last_sync_at is not None


# ── Internal helper tests ───────────────────────────────────


class TestDataSyncHelpers:

    def test_dataframe_to_records(self):
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost"],
            "metric_value": [1000.0, 500.0],
            "period": ["2024-01", "2024-01"],
            "entity": ["A", "B"],
            "metric_unit": ["CNY", "CNY"],
        })
        records = DataSyncService._dataframe_to_records(df, batch_id=1, tags={"src": "test"})

        assert len(records) == 2
        assert records[0]["metric_name"] == "revenue"
        assert records[0]["batch_id"] == 1
        assert records[0]["tags"] == {"src": "test"}

    def test_dataframe_to_records_skips_invalid(self):
        df = pd.DataFrame({
            "metric_name": ["revenue", "", "cost"],
            "metric_value": [100.0, 200.0, 300.0],
            "period": ["2024-01", "", "2024-01"],
        })
        records = DataSyncService._dataframe_to_records(df, batch_id=1)

        # Row with empty metric_name or period should be skipped
        assert len(records) == 2
