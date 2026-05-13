"""Celery task: daily email poll — fetch the latest email's attachment and run the core pipeline."""

from __future__ import annotations

import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_db():
    """Synchronous SQLAlchemy session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


@celery_app.task(name="email_poll.poll_emails", queue="email_poll")
def poll_emails_task() -> dict:
    """Fetch the latest email with an Excel attachment and push it through the
    parse → clean → sync pipeline.

    Scheduled once per day via Celery beat.
    """
    from app.services.data_cleaner import DataCleaner
    from app.services.email_reader import IMAPEmailReader, ProcessedUIDTracker
    from app.services.excel_parser import ExcelParser

    uid_tracker = ProcessedUIDTracker()
    reader = IMAPEmailReader(uid_tracker=uid_tracker)
    parser = ExcelParser()
    cleaner = DataCleaner()

    total_rows = 0
    total_errors = 0
    results: list[dict] = []

    try:
        reader.connect()
        uids = reader.search_default()
        new_uids = [u for u in uids if not uid_tracker.is_processed(u)]

        if not new_uids:
            logger.info("No new emails to process")
            return {"status": "completed", "emails_processed": 0, "rows_synced": 0}

        # Latest email only — IMAP UIDs are monotonically increasing per mailbox.
        latest_uid = max(new_uids, key=lambda u: int(u) if u.isdigit() else 0)
        logger.info("Processing latest email UID=%s (of %d unprocessed)", latest_uid, len(new_uids))

        msg = reader.fetch_and_extract(latest_uid)
        if msg is None:
            return {"status": "failed", "reason": "fetch_failed", "uid": latest_uid}

        try:
            for attachment in msg.attachments:
                result = _process_attachment(attachment, parser, cleaner, msg)
                results.append(result)
                total_rows += result.get("rows_synced", 0)
                total_errors += result.get("errors", 0)
        finally:
            reader.cleanup_temp_files([a.temp_path for a in msg.attachments])
            uid_tracker.mark_processed(latest_uid)

    except Exception as exc:
        logger.exception("Email poll failed: %s", exc)
        return {"status": "failed", "error": str(exc)}
    finally:
        reader.disconnect()

    return {
        "status": "completed" if total_errors == 0 else "partial",
        "emails_processed": 1,
        "rows_synced": total_rows,
        "errors": total_errors,
        "results": results,
    }


def _process_attachment(attachment, parser, cleaner, msg) -> dict:
    """Parse → clean → sync a single Excel attachment (sync Celery context)."""
    logger.info(
        "Processing attachment %s (%d bytes) from UID=%s",
        attachment.filename, attachment.size, msg.uid,
    )

    parse_result = parser.parse(attachment.temp_path)
    if parse_result.dataframe.empty:
        return {
            "file": attachment.filename, "status": "skipped",
            "reason": "empty_data", "parse_errors": len(parse_result.errors),
        }

    clean_result = cleaner.clean(parse_result.dataframe)

    session = _get_sync_db()
    try:
        sync_result = _sync_incremental_sync(session, clean_result.dataframe, msg, attachment)
        session.commit()
        return {
            "file": attachment.filename,
            "status": sync_result.get("status", "unknown"),
            "rows_synced": sync_result.get("rows_upserted", 0),
            "errors": sync_result.get("error_count", 0),
        }
    except Exception as exc:
        session.rollback()
        logger.exception("Sync failed for %s: %s", attachment.filename, exc)
        return {"file": attachment.filename, "status": "failed", "error": str(exc)}
    finally:
        session.close()


def _sync_incremental_sync(session, df, msg, attachment) -> dict:
    """Synchronous incremental upsert — mirrors DataSyncService.sync_incremental."""
    import uuid
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.core import (
        DataBatch, DataQualityLog, FinancialData, QualityStatus, SyncStatus,
    )

    batch_no = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    batch = DataBatch(
        source_id=None, batch_no=batch_no, status=SyncStatus.RUNNING,
        file_name=attachment.filename,
    )
    session.add(batch)
    session.flush()

    tags = {
        "email_uid": msg.uid,
        "email_subject": msg.subject,
        "email_from": msg.from_addr,
    }

    inserted = updated = 0
    errors: list[dict] = []

    for idx, row in df.iterrows():
        try:
            metric_name = str(row.get("metric_name", "")).strip()
            period = str(row.get("period", "")).strip()
            if not metric_name or not period:
                continue

            metric_value = float(row.get("metric_value", 0.0))
            entity = str(row.get("entity", "")) or None
            metric_unit = str(row.get("metric_unit", "")) or None

            stmt = select(FinancialData).where(
                FinancialData.metric_name == metric_name,
                FinancialData.period == period,
            )
            stmt = stmt.where(FinancialData.entity == entity) if entity else stmt.where(FinancialData.entity.is_(None))
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                existing.metric_value = metric_value
                existing.metric_unit = metric_unit
                existing.batch_id = batch.id
                existing.raw_row = dict(row) if not row.empty else None
                existing.tags = tags
                updated += 1
            else:
                session.add(FinancialData(
                    batch_id=batch.id, metric_name=metric_name, metric_value=metric_value,
                    metric_unit=metric_unit, period=period, entity=entity, tags=tags,
                    raw_row=dict(row) if not row.empty else None,
                ))
                inserted += 1
        except Exception as exc:
            errors.append({"row": int(idx), "error": str(exc)})

    batch.status = SyncStatus.FAILED if errors else SyncStatus.SUCCESS
    batch.record_count = inserted + updated
    batch.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    if errors:
        session.add(DataQualityLog(
            batch_id=batch.id, status=QualityStatus.FAILED,
            rule_name="email_sync_error", detail=f"{len(errors)} rows failed",
            affected_rows=len(errors),
        ))

    return {
        "status": batch.status.value,
        "rows_upserted": inserted + updated,
        "rows_inserted": inserted,
        "rows_updated": updated,
        "error_count": len(errors),
    }
