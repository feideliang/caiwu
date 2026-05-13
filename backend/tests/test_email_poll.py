"""Tests for the daily email poll Celery task."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPollEmailsTask:

    @patch("app.services.email_reader.IMAPEmailReader")
    @patch("app.services.email_reader.ProcessedUIDTracker")
    def test_no_new_emails(self, mock_tracker_class, mock_reader_class):
        """Empty inbox → 0 emails processed, status=completed."""
        mock_tracker = MagicMock()
        mock_tracker.is_processed.return_value = False
        mock_tracker_class.return_value = mock_tracker

        mock_reader = MagicMock()
        mock_reader.search_default.return_value = []
        mock_reader_class.return_value = mock_reader

        from app.tasks.email_poll import poll_emails_task
        result = poll_emails_task()

        assert result["status"] == "completed"
        assert result["emails_processed"] == 0
        assert result["rows_synced"] == 0

    @patch("app.services.email_reader.IMAPEmailReader")
    @patch("app.services.email_reader.ProcessedUIDTracker")
    def test_all_emails_already_processed(self, mock_tracker_class, mock_reader_class):
        """All returned UIDs are already in tracker → skip."""
        mock_tracker = MagicMock()
        mock_tracker.is_processed.return_value = True
        mock_tracker_class.return_value = mock_tracker

        mock_reader = MagicMock()
        mock_reader.search_default.return_value = ["1", "2"]
        mock_reader_class.return_value = mock_reader

        from app.tasks.email_poll import poll_emails_task
        result = poll_emails_task()

        assert result["status"] == "completed"
        assert result["emails_processed"] == 0

    @patch("app.services.email_reader.IMAPEmailReader")
    @patch("app.services.email_reader.ProcessedUIDTracker")
    def test_fetch_failure(self, mock_tracker_class, mock_reader_class):
        """fetch_and_extract returning None → status=failed."""
        mock_tracker = MagicMock()
        mock_tracker.is_processed.return_value = False
        mock_tracker_class.return_value = mock_tracker

        mock_reader = MagicMock()
        mock_reader.search_default.return_value = ["10"]
        mock_reader.fetch_and_extract.return_value = None
        mock_reader_class.return_value = mock_reader

        from app.tasks.email_poll import poll_emails_task
        result = poll_emails_task()

        assert result["status"] == "failed"
        assert result["reason"] == "fetch_failed"


class TestSyncIncrementalSync:

    def test_sync_data_signature(self):
        """Synchronous sync helper exists with expected signature."""
        from app.tasks.email_poll import _sync_incremental_sync
        import inspect
        sig = inspect.signature(_sync_incremental_sync)
        params = list(sig.parameters.keys())
        assert params == ["session", "df", "msg", "attachment"]


class TestBeatSchedule:

    def test_daily_beat_scheduled(self):
        """Celery beat schedule includes a daily email poll."""
        from app.celery_app import celery_app
        sched = celery_app.conf.beat_schedule
        assert "daily-email-poll" in sched
        assert sched["daily-email-poll"]["task"] == "email_poll.poll_emails"
