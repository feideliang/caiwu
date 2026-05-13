"""Report generation service — orchestrates task creation, cancellation, retry, and download."""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ReportGenerationFailedError, ResourceNotFoundError
from app.models.v3 import ReportTask
from app.tasks.report_gen import update_report_step

logger = logging.getLogger(__name__)

# Shared synchronous engine for background report generation.
_sync_engine = None


def _get_sync_engine():
    """Return a singleton synchronous SQLAlchemy engine."""
    global _sync_engine
    if _sync_engine is None:
        from app.config import settings

        _sync_engine = create_engine(
            settings.sync_database_url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    return _sync_engine


def _get_sync_db():
    """Return a synchronous SQLAlchemy session for use in report generation."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=_get_sync_engine())()


def _run_report_sync(report_id: int) -> None:
    """Run report generation in a background thread."""
    try:
        from app.tasks.report_gen import _collect_data, _ai_analyze, _generate_document

        print(f"[REPORT] Starting generation: id={report_id}", flush=True)
        logger.info("Running report generation in background: id=%d", report_id)

        # Step 1: Collecting data
        print(f"[REPORT] Step 1: collecting_data", flush=True)
        update_report_step(report_id, status="running", step="collecting_data")
        data = _collect_data(report_id)
        print(f"[REPORT] Collected {len(data.get('data_rows', []))} data rows", flush=True)

        # Step 2: AI analysis
        print(f"[REPORT] Step 2: ai_analyzing", flush=True)
        update_report_step(report_id, status="running", step="ai_analyzing")
        analysis = _ai_analyze(report_id, data)

        # Step 3: Generate document
        print(f"[REPORT] Step 3: document_generating", flush=True)
        update_report_step(report_id, status="running", step="document_generating")
        file_path, file_name = _generate_document(report_id, analysis)

        # Completed
        print(f"[REPORT] Marking completed", flush=True)
        update_report_step(report_id, status="completed", step="completed")

        # Persist file info
        session = _get_sync_db()
        try:
            from app.models.v3 import ReportTask as RT
            obj = session.query(RT).filter(RT.id == report_id).first()
            if obj:
                obj.file_path = file_path
                obj.file_name = file_name
                session.commit()
        finally:
            session.close()

        print(f"[REPORT] Completed: id={report_id} file={file_name}", flush=True)
        logger.info("Report generation completed: id=%d file=%s", report_id, file_name)
    except Exception as e:
        print(f"[REPORT] FAILED: id={report_id} error={e}", flush=True)
        logger.exception("Report generation failed: id=%d", report_id)
        # Mark as failed
        try:
            update_report_step(report_id, status="failed", step="failed")
            session = _get_sync_db()
            try:
                from app.models.v3 import ReportTask as RT
                obj = session.query(RT).filter(RT.id == report_id).first()
                if obj:
                    obj.error_message = str(e)
                    session.commit()
            finally:
                session.close()
        except Exception:
            pass


async def _run_report_in_background(report_id: int) -> None:
    """Run report generation in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_report_sync, report_id)


class ReportService:
    """Service for managing report generation tasks."""

    @staticmethod
    async def create_report(
        db: AsyncSession,
        user_id: int,
        report_type: str,
        period: str = "",
        output_format: str = "pdf",
        params: dict | None = None,
        parent_task_id: int | None = None,
    ) -> ReportTask:
        """Create a new report generation task. Returns immediately; generation runs in background."""

        task_id = str(uuid.uuid4())

        report = ReportTask(
            user_id=user_id,
            report_type=report_type,
            period=period,
            output_format=output_format,
            status="pending",
            current_step="pending",
            task_id=task_id,
            params=params,
            parent_task_id=parent_task_id,
            retry_count=0,
        )
        db.add(report)
        await db.flush()
        await db.refresh(report)

        # Commit so the row is visible to background thread
        await db.commit()

        # Kick off background generation
        report_id = report.id
        asyncio.create_task(_run_report_in_background(report_id))
        print(f"[REPORT] Background task dispatched: id={report_id}", flush=True)

        logger.info("Report task created: id=%s", report.id)
        return report

    @staticmethod
    async def list_reports(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        report_type: str | None = None,
    ) -> tuple[list[dict], int]:
        """List reports for a user with optional filters."""

        stmt = select(ReportTask).where(ReportTask.user_id == user_id)

        if status:
            stmt = stmt.where(ReportTask.status == status)
        if report_type:
            stmt = stmt.where(ReportTask.report_type == report_type)

        stmt = stmt.order_by(ReportTask.created_at.desc())

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginate
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        reports = result.scalars().all()

        items = [_to_dict(r) for r in reports]
        return items, total

    @staticmethod
    async def get_report(db: AsyncSession, report_id: int, user_id: int) -> ReportTask:
        """Get a single report by ID, scoped to user."""
        stmt = select(ReportTask).where(
            ReportTask.id == report_id,
            ReportTask.user_id == user_id,
        )
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            raise ResourceNotFoundError(f"Report {report_id} not found")
        return report

    @staticmethod
    async def cancel_report(db: AsyncSession, report_id: int, user_id: int) -> ReportTask:
        """Cancel a running report task."""
        report = await ReportService.get_report(db, report_id, user_id)

        if report.status not in ("pending", "running"):
            raise BusinessError(f"Cannot cancel report in '{report.status}' state")

        report.status = "failed"
        report.current_step = "failed"
        report.error_message = "Cancelled by user"
        report.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await db.refresh(report)

        logger.info("Report cancelled: id=%d", report_id)
        return report

    @staticmethod
    async def retry_report(db: AsyncSession, report_id: int, user_id: int) -> ReportTask:
        """Retry a failed report task."""
        report = await ReportService.get_report(db, report_id, user_id)

        if report.status != "failed":
            raise BusinessError(f"Can only retry failed reports; current status: '{report.status}'")

        if report.retry_count >= 3:
            raise ReportGenerationFailedError("Max retry attempts (3) exceeded")

        # Create a new child task
        task_id = str(uuid.uuid4())
        new_report = ReportTask(
            user_id=user_id,
            report_type=report.report_type,
            period=report.period,
            output_format=report.output_format,
            status="pending",
            current_step="pending",
            task_id=task_id,
            params=report.params,
            parent_task_id=report_id,
            retry_count=report.retry_count + 1,
        )
        db.add(new_report)
        await db.flush()
        await db.refresh(new_report)

        # Commit so the row is visible to background thread
        await db.commit()

        # Kick off background generation
        new_report_id = new_report.id
        asyncio.create_task(_run_report_in_background(new_report_id))

        logger.info("Report retried: original_id=%d new_id=%d", report_id, new_report.id)
        return new_report

    @staticmethod
    def get_file_path(report: ReportTask) -> tuple[str, str] | None:
        """Return (file_path, file_name) if the report has been generated."""
        if report.status != "completed" or not report.file_path:
            return None
        return report.file_path, report.file_name or "report"


def _to_dict(report: ReportTask) -> dict:
    return {
        "id": report.id,
        "user_id": report.user_id,
        "report_type": report.report_type,
        "status": report.status,
        "current_step": report.current_step,
        "period": report.period,
        "output_format": report.output_format,
        "file_path": report.file_path,
        "file_name": report.file_name,
        "error_message": report.error_message,
        "task_id": report.task_id,
        "celery_task_id": report.celery_task_id,
        "retry_count": report.retry_count,
        "parent_task_id": report.parent_task_id,
        "params": report.params,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }
