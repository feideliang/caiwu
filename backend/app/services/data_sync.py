"""Data sync service: UPSERT/FULL sync, batch tracking, cache invalidation, audit logging."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_delete_pattern
from app.models.core import (
    DataBatch,
    DataQualityLog,
    DataSource,
    DataSourceType,
    FinancialData,
    QualityStatus,
    SyncStatus,
)
from app.services.metrics_service import compute_bucket

logger = logging.getLogger(__name__)


class DataSyncService:
    """Synchronize parsed financial data into the database.

    Supports incremental UPSERT and FULL (truncate + reload) strategies,
    with batch tracking, error logging, and cache invalidation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def sync_incremental(
        self,
        df: pd.DataFrame,
        source_id: int | None = None,
        file_name: str | None = None,
        tags: dict | None = None,
    ) -> dict[str, Any]:
        """Incremental sync: find conflicts by period → batch DELETE → batch INSERT.

        Strategy:
        1. Collect unique periods from incoming data
        2. Find existing row IDs matching those periods
        3. Batch DELETE conflicting rows
        4. Batch INSERT all new data

        This is simpler and faster than row-by-row UPSERT.

        Args:
            df: Cleaned DataFrame to sync.
            source_id: Data source ID for tracking.
            file_name: Original file name.
            tags: Additional tags to attach to each row.

        Returns:
            Sync summary dict with counts and status.
        """
        if df.empty:
            return {
                "status": "skipped",
                "message": "Empty DataFrame, nothing to sync",
                "rows_upserted": 0,
                "rows_inserted": 0,
                "rows_deleted": 0,
            }

        # Create batch record
        batch = await self._create_batch(source_id, file_name)
        logger.info("Created sync batch %s (id=%d)", batch.batch_no, batch.id)

        # Collect unique periods from incoming data
        periods = sorted(df["period"].dropna().unique().tolist())
        if not periods:
            return {
                "status": "skipped",
                "message": "No valid periods in DataFrame",
                "rows_upserted": 0,
                "rows_inserted": 0,
                "rows_deleted": 0,
            }
        logger.info("Syncing %d periods: %s", len(periods), periods)

        errors: list[dict] = []
        records: list[dict] = []
        deleted: int = 0

        try:
            # Step 1: Find conflicting row IDs by period
            conflict_ids_stmt = (
                select(FinancialData.id)
                .where(FinancialData.period.in_(periods))
            )
            result = await self.db.execute(conflict_ids_stmt)
            conflict_ids = [row[0] for row in result.all()]
            deleted = len(conflict_ids)
            logger.info("Found %d conflicting rows for periods %s", deleted, periods)

            # Step 2: Batch DELETE conflicting rows
            if conflict_ids:
                delete_stmt = text(
                    "DELETE FROM financial_data WHERE id = ANY(:ids)"
                )
                await self.db.execute(delete_stmt, {"ids": conflict_ids})
                await self.db.flush()
                logger.info("Deleted %d conflicting rows", deleted)

            # Step 3: Batch INSERT all new data
            records = self._dataframe_to_records(df, batch.id, tags)
            if records:
                self.db.add_all([FinancialData(**r) for r in records])
                await self.db.flush()
                logger.info("Inserted %d new rows", len(records))

        except Exception as exc:
            errors.append({"error": str(exc)})
            logger.exception("Incremental sync failed: %s", exc)

        # Update batch status
        status = SyncStatus.FAILED if errors else SyncStatus.SUCCESS
        total = len(records) if not errors and records else 0
        await self._finalize_batch(batch.id, status, total)

        # Log quality issues
        if errors:
            await self._log_quality_issue(
                batch_id=batch.id,
                status=QualityStatus.FAILED,
                rule_name="sync_error",
                detail=f"Sync failed: {errors[0]['error']}",
                affected_rows=total,
            )

        # Invalidate cache on success
        if not errors:
            await self._invalidate_cache()

        # Audit log
        await self._audit_sync(
            batch_id=batch.id,
            action="incremental_sync",
            inserted=total,
            updated=0,  # No UPSERT, all are inserts after delete
            errors=len(errors),
        )

        return {
            "status": status.value,
            "batch_id": batch.id,
            "batch_no": batch.batch_no,
            "rows_deleted": deleted,
            "rows_inserted": total,
            "rows_upserted": total + deleted,
            "error_count": len(errors),
            "errors": errors[:100],
        }

    async def sync_full(
        self,
        df: pd.DataFrame,
        source_id: int | None = None,
        file_name: str | None = None,
        tags: dict | None = None,
    ) -> dict[str, Any]:
        """Full sync: truncate financial_data and reload.

        WARNING: This deletes ALL existing financial data.
        """
        if df.empty:
            return {
                "status": "skipped",
                "message": "Empty DataFrame, nothing to sync",
                "rows_loaded": 0,
            }

        # Create batch record
        batch = await self._create_batch(source_id, file_name)
        logger.info("Starting FULL sync batch %s (id=%d)", batch.batch_no, batch.id)

        try:
            # Truncate existing data
            await self.db.execute(text("TRUNCATE TABLE financial_data CASCADE"))
            await self.db.flush()
            logger.info("Truncated financial_data table")

            # Bulk insert
            records = self._dataframe_to_records(df, batch.id, tags)
            await self._bulk_insert(records)

            # Update batch
            await self._finalize_batch(batch.id, SyncStatus.SUCCESS, len(records))

            # Invalidate cache
            await self._invalidate_cache()

            # Audit
            await self._audit_sync(
                batch_id=batch.id,
                action="full_sync",
                inserted=len(records),
                updated=0,
                errors=0,
            )

            return {
                "status": "success",
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "rows_loaded": len(records),
            }

        except Exception as exc:
            await self._finalize_batch(batch.id, SyncStatus.FAILED, 0)
            await self._audit_sync(
                batch_id=batch.id,
                action="full_sync",
                inserted=0,
                updated=0,
                errors=1,
            )
            logger.exception("FULL sync failed: %s", exc)
            return {
                "status": "failed",
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "error": str(exc),
                "rows_loaded": 0,
            }

    # ── Internal helpers ───────────────────────────────────────

    async def _create_batch(
        self, source_id: int | None, file_name: str | None
    ) -> DataBatch:
        """Create a new DataBatch record."""
        batch_no = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        batch = DataBatch(
            source_id=source_id,
            batch_no=batch_no,
            status=SyncStatus.RUNNING,
            file_name=file_name,
        )
        self.db.add(batch)
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def _finalize_batch(
        self, batch_id: int, status: SyncStatus, record_count: int
    ) -> None:
        """Update batch with final status and count."""
        batch = await self.db.get(DataBatch, batch_id)
        if batch:
            batch.status = status
            batch.record_count = record_count
            batch.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.db.flush()

    async def _upsert_row(
        self, row: pd.Series, batch_id: int, tags: dict | None = None
    ) -> str:
        """UPSERT a single row into financial_data.

        Returns 'inserted' or 'updated'.
        Preserves per-row tags from DataFrame's "tags" column if present.
        """
        metric_name = str(row.get("metric_name", "")).strip()
        period = str(row.get("period", "")).strip()
        entity = str(row.get("entity", "")) or None

        if not metric_name or not period:
            raise ValueError("metric_name and period are required")

        metric_value = float(row.get("metric_value", 0.0))

        # Per-row tags from DataFrame, merged with global tags
        row_tags_raw = row.get("tags")
        row_tags: dict = {}
        if isinstance(row_tags_raw, dict):
            row_tags.update(row_tags_raw)
        elif isinstance(row_tags_raw, str):
            try:
                row_tags.update(json.loads(row_tags_raw))
            except (json.JSONDecodeError, ValueError):
                pass
        if tags:
            row_tags.update(tags)

        # Check if row already exists
        stmt = (
            select(FinancialData)
            .where(FinancialData.metric_name == metric_name)
            .where(FinancialData.period == period)
        )
        if entity:
            stmt = stmt.where(FinancialData.entity == entity)
        else:
            stmt = stmt.where(FinancialData.entity.is_(None))

        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.metric_value = metric_value
            existing.metric_unit = str(row.get("metric_unit", "")) or None
            existing.batch_id = batch_id
            existing.raw_row = dict(row) if not row.empty else None
            if row_tags:
                existing.tags = {**(existing.tags or {}), **row_tags}
            return "updated"
        else:
            # Insert new
            record = FinancialData(
                batch_id=batch_id,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=str(row.get("metric_unit", "")) or None,
                period=period,
                entity=entity,
                tags=row_tags if row_tags else None,
                raw_row=dict(row) if not row.empty else None,
                bucket=compute_bucket(metric_name),
            )
            self.db.add(record)
            return "inserted"

    async def _bulk_insert(self, records: list[dict]) -> None:
        """Bulk insert records into financial_data."""
        if not records:
            return

        # Use SQLAlchemy bulk insert
        self.db.add_all([FinancialData(**r) for r in records])
        await self.db.flush()

    @staticmethod
    def _dataframe_to_records(
        df: pd.DataFrame, batch_id: int, tags: dict | None = None
    ) -> list[dict]:
        """Convert DataFrame rows to FinancialData insert dicts.

        Preserves per-row tags from DataFrame's "tags" column if present,
        then merges the global `tags` parameter on top (per-row can override).
        """
        records: list[dict] = []
        has_tags_col = "tags" in df.columns
        for _, row in df.iterrows():
            metric_name = str(row.get("metric_name", "")).strip()
            period = str(row.get("period", "")).strip()
            if not metric_name or not period:
                continue

            # Per-row tags from DataFrame, then merge global tags
            row_tags = dict(row.get("tags", {})) if has_tags_col and isinstance(row.get("tags"), (dict, str)) else {}
            if isinstance(row_tags, str):
                try:
                    row_tags = json.loads(row_tags)
                except (json.JSONDecodeError, ValueError):
                    row_tags = {}
            if tags:
                row_tags.update(tags)  # global tags override baseline

            records.append({
                "batch_id": batch_id,
                "metric_name": metric_name,
                "metric_value": float(row.get("metric_value", 0.0)),
                "metric_unit": str(row.get("metric_unit", "")) or None,
                "period": period,
                "entity": str(row.get("entity", "")) or None,
                "tags": row_tags if row_tags else None,
                "raw_row": dict(row) if not row.empty else None,
                "bucket": compute_bucket(metric_name),
            })
        return records

    async def _invalidate_cache(self) -> None:
        """Invalidate all dashboard and query caches after sync."""
        try:
            await cache_delete_pattern("dao:*")
            await cache_delete_pattern("dashboard:*")
            await cache_delete_pattern("query:*")
            await cache_delete_pattern("metrics:*")
            logger.info("Cache invalidated after sync")
        except Exception as exc:
            logger.warning("Cache invalidation skipped: %s", exc)

    async def _audit_sync(
        self,
        batch_id: int,
        action: str,
        inserted: int,
        updated: int,
        errors: int,
    ) -> None:
        """Log sync operation to data_quality_log."""
        detail = (
            f"Sync {action}: batch_id={batch_id}, "
            f"inserted={inserted}, updated={updated}, errors={errors}"
        )
        quality_log = DataQualityLog(
            batch_id=batch_id,
            status=QualityStatus.FAILED if errors else QualityStatus.PASSED,
            rule_name=action,
            detail=detail,
            affected_rows=inserted + updated + errors,
        )
        self.db.add(quality_log)
        await self.db.flush()

    async def _log_quality_issue(
        self,
        batch_id: int | None,
        status: QualityStatus,
        rule_name: str,
        detail: str | None = None,
        affected_rows: int = 0,
    ) -> None:
        """Log a data quality issue."""
        log = DataQualityLog(
            batch_id=batch_id,
            status=status,
            rule_name=rule_name,
            detail=detail,
            affected_rows=affected_rows,
        )
        self.db.add(log)
        await self.db.flush()

    async def register_data_source(
        self,
        name: str,
        source_type: DataSourceType,
        connection_config: dict | None = None,
        priority: int = 0,
    ) -> DataSource:
        """Register or update a data source."""
        stmt = select(DataSource).where(DataSource.name == name)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.source_type = source_type
            existing.connection_config = connection_config
            existing.priority = priority
            existing.is_active = True
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        else:
            ds = DataSource(
                name=name,
                source_type=source_type,
                connection_config=connection_config,
                priority=priority,
            )
            self.db.add(ds)
            await self.db.flush()
            await self.db.refresh(ds)
            return ds

    async def mark_source_synced(self, source_id: int) -> None:
        """Update last_sync_at for a data source."""
        ds = await self.db.get(DataSource, source_id)
        if ds:
            ds.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.db.flush()
