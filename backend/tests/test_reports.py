"""Tests for the report generation service and Celery task."""

from __future__ import annotations

import pytest

from app.tasks.report_gen import REPORT_STEPS


class TestReportStateMachine:
    """Test the report generation state machine steps."""

    def test_steps_are_sequential(self):
        assert REPORT_STEPS == ["collecting_data", "ai_analyzing", "document_generating", "completed"]

    def test_steps_include_completion(self):
        assert "completed" in REPORT_STEPS

    def test_create_report_sets_pending_status(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _test():
            mock_db = AsyncMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()

            # Mock the Celery task dispatch
            mock_celery_result = MagicMock()
            mock_celery_result.id = "celery-task-id-123"

            mock_task = MagicMock()
            mock_task.delay = MagicMock(return_value=mock_celery_result)

            with patch("app.services.report_service.generate_report_task", mock_task):
                from app.services.report_service import ReportService
                report = await ReportService.create_report(
                    db=mock_db,
                    user_id=42,
                    report_type="monthly",
                    period="2024-01",
                    output_format="pdf",
                )

                assert report.status == "pending"
                assert report.current_step == "pending"
                assert report.user_id == 42
                assert report.report_type == "monthly"

        asyncio.run(_test())

    def test_cancel_report_only_running(self):
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _test():
            mock_db = AsyncMock()

            from app.services.report_service import ReportService
            from app.core.exceptions import BusinessError

            # Mock get_report to return a completed report
            with patch.object(ReportService, "get_report") as mock_get:
                mock_report = AsyncMock()
                mock_report.status = "completed"
                mock_get.return_value = mock_report

                with pytest.raises(BusinessError):
                    await ReportService.cancel_report(mock_db, report_id=1, user_id=42)

        asyncio.run(_test())

    def test_retry_report_only_failed(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _test():
            mock_db = AsyncMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.add = MagicMock()

            from app.services.report_service import ReportService
            from app.core.exceptions import BusinessError

            with patch.object(ReportService, "get_report") as mock_get:
                mock_report = AsyncMock()
                mock_report.status = "pending"
                mock_report.report_type = "monthly"
                mock_report.period = "2024-01"
                mock_report.output_format = "pdf"
                mock_report.params = None
                mock_report.retry_count = 0
                mock_get.return_value = mock_report

                with pytest.raises(BusinessError):
                    await ReportService.retry_report(mock_db, report_id=1, user_id=42)

        asyncio.run(_test())

    def test_retry_report_max_attempts(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _test():
            mock_db = AsyncMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.add = MagicMock()

            from app.services.report_service import ReportService
            from app.core.exceptions import ReportGenerationFailedError

            with patch.object(ReportService, "get_report") as mock_get:
                mock_report = AsyncMock()
                mock_report.status = "failed"
                mock_report.retry_count = 3
                mock_get.return_value = mock_report

                with pytest.raises(ReportGenerationFailedError):
                    await ReportService.retry_report(mock_db, report_id=1, user_id=42)

        asyncio.run(_test())


class TestReportFileGeneration:
    """Test the document generation placeholder."""

    def test_generate_document_creates_file(self):
        """Test that _generate_document produces a file at the expected path."""
        from app.tasks.report_gen import _generate_document

        analysis = {
            "report_id": 999,
            "statistics": {"revenue": {"mean": 1000, "min": 500, "max": 1500, "count": 12}},
            "summary": "Test summary",
        }

        file_path, file_name = _generate_document(999, analysis)

        assert file_path is not None
        assert file_name is not None
        assert ".txt" in file_name or ".docx" in file_name


class TestReportDataCollection:
    """Test the data collection step."""

    def test_analysis_computes_statistics(self):
        """Verify that the _ai_analyze step produces statistics."""
        from app.tasks.report_gen import _ai_analyze

        data = {
            "data_rows": [
                {"metric_name": "revenue", "metric_value": 100},
                {"metric_name": "revenue", "metric_value": 200},
                {"metric_name": "cost", "metric_value": 50},
            ],
        }

        analysis = _ai_analyze(1, data)

        assert "statistics" in analysis
        assert "revenue" in analysis["statistics"]
        assert analysis["statistics"]["revenue"]["mean"] == 150.0
        assert analysis["statistics"]["revenue"]["min"] == 100.0
        assert analysis["statistics"]["revenue"]["max"] == 200.0

    def test_analysis_handles_empty_data(self):
        """Verify _ai_analyze handles empty data gracefully."""
        from app.tasks.report_gen import _ai_analyze

        data = {"data_rows": []}
        analysis = _ai_analyze(1, data)

        assert "statistics" in analysis
        assert len(analysis["statistics"]) == 0
