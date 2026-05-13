"""Tests for IMAP email reader service."""

from __future__ import annotations

import email
import imaplib
import json
import os
import tempfile
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.services.email_reader import (
    ALLOWED_EXTENSIONS,
    AttachmentInfo,
    EmailMessage,
    IMAPEmailReader,
    ProcessedUIDTracker,
)


# ── ProcessedUIDTracker tests ───────────────────────────────


class TestProcessedUIDTracker:

    def test_initial_empty(self, tmp_path):
        filepath = str(tmp_path / "uids.json")
        tracker = ProcessedUIDTracker(filepath=filepath)
        assert tracker.count == 0
        assert not tracker.is_processed("123")

    def test_mark_and_check(self, tmp_path):
        filepath = str(tmp_path / "uids.json")
        tracker = ProcessedUIDTracker(filepath=filepath)
        tracker.mark_processed("100")
        assert tracker.is_processed("100")
        assert not tracker.is_processed("200")
        assert tracker.count == 1

    def test_mark_many(self, tmp_path):
        filepath = str(tmp_path / "uids.json")
        tracker = ProcessedUIDTracker(filepath=filepath)
        tracker.mark_many(["1", "2", "3"])
        assert tracker.count == 3
        assert tracker.is_processed("1")
        assert tracker.is_processed("3")

    def test_persistence(self, tmp_path):
        filepath = str(tmp_path / "uids.json")
        tracker1 = ProcessedUIDTracker(filepath=filepath)
        tracker1.mark_many(["a", "b"])
        assert tracker1.count == 2

        tracker2 = ProcessedUIDTracker(filepath=filepath)
        assert tracker2.count == 2
        assert tracker2.is_processed("a")
        assert tracker2.is_processed("b")

    def test_clear(self, tmp_path):
        filepath = str(tmp_path / "uids.json")
        tracker = ProcessedUIDTracker(filepath=filepath)
        tracker.mark_many(["x", "y", "z"])
        tracker.clear()
        assert tracker.count == 0
        assert not tracker.is_processed("x")

    def test_corrupt_file(self, tmp_path):
        filepath = str(tmp_path / "uids.json")
        Path(filepath).write_text("not valid json", encoding="utf-8")
        tracker = ProcessedUIDTracker(filepath=filepath)
        assert tracker.count == 0

    def test_missing_file(self, tmp_path):
        filepath = str(tmp_path / "nonexistent" / "uids.json")
        tracker = ProcessedUIDTracker(filepath=filepath)
        assert tracker.count == 0


# ── IMAPEmailReader tests ───────────────────────────────────


class TestIMAPEmailReaderInit:

    def test_default_settings(self):
        reader = IMAPEmailReader(
            host="imap.example.com",
            port=993,
            user="test@example.com",
            password="secret",
        )
        assert reader.host == "imap.example.com"
        assert reader.port == 993
        assert reader.user == "test@example.com"
        assert reader.password == "secret"
        assert reader.use_xoauth2 is False

    def test_xoauth2_enabled(self):
        reader = IMAPEmailReader(
            host="imap.example.com",
            user="test@example.com",
            password="secret",
            use_xoauth2=True,
        )
        assert reader.use_xoauth2 is True

    def test_custom_filters(self):
        reader = IMAPEmailReader(
            host="imap.test.com",
            user="u@t.com",
            password="p",
            subject_keywords=["report"],
            from_whitelist=["finance@test.com"],
            max_attachment_size=10_000_000,
        )
        assert reader.subject_keywords == ["report"]
        assert reader.from_whitelist == ["finance@test.com"]
        assert reader.max_attachment_size == 10_000_000


class TestIMAPConnection:

    @patch("app.services.email_reader.imaplib.IMAP4_SSL")
    def test_connect_password_auth(self, mock_ssl_class):
        mock_conn = MagicMock()
        mock_ssl_class.return_value = mock_conn

        reader = IMAPEmailReader(
            host="imap.test.com", user="u", password="p", use_xoauth2=False
        )
        conn = reader.connect()

        mock_ssl_class.assert_called_once_with("imap.test.com", 993)
        mock_conn.login.assert_called_once_with("u", "p")
        mock_conn.select.assert_called_once_with("INBOX", readonly=False)
        assert conn is mock_conn

    @patch("app.services.email_reader.imaplib.IMAP4_SSL")
    def test_connect_reuses_connection(self, mock_ssl_class):
        mock_conn = MagicMock()
        mock_ssl_class.return_value = mock_conn

        reader = IMAPEmailReader(host="h", user="u", password="p")
        reader.connect()
        reader.connect()

        # Should only create one connection
        mock_ssl_class.assert_called_once()

    @patch("app.services.email_reader.imaplib.IMAP4_SSL")
    def test_connect_xoauth2_fallback(self, mock_ssl_class):
        mock_conn = MagicMock()
        mock_ssl_class.return_value = mock_conn
        # XOAUTH2 will raise NotImplementedError, should fall back to password
        mock_conn.authenticate.side_effect = NotImplementedError("no MSAL")

        reader = IMAPEmailReader(
            host="imap.test.com", user="u", password="p", use_xoauth2=True
        )
        conn = reader.connect()
        assert conn is mock_conn

    @patch("app.services.email_reader.imaplib.IMAP4_SSL")
    def test_disconnect(self, mock_ssl_class):
        mock_conn = MagicMock()
        mock_ssl_class.return_value = mock_conn

        reader = IMAPEmailReader(host="h", user="u", password="p")
        reader.connect()
        reader.disconnect()

        mock_conn.logout.assert_called_once()
        assert reader._conn is None

    def test_keepalive(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        reader._conn = MagicMock()
        reader.keepalive()
        reader._conn.noop.assert_called_once()

    def test_keepalive_stale_connection(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.noop.side_effect = imaplib.IMAP4.error("stale")
        reader._conn = mock_conn

        reader.keepalive()
        assert reader._conn is None

    def test_context_manager(self):
        with patch("app.services.email_reader.imaplib.IMAP4_SSL") as mock_ssl_class:
            mock_conn = MagicMock()
            mock_ssl_class.return_value = mock_conn

            with IMAPEmailReader(host="h", user="u", password="p") as reader:
                assert reader._conn is mock_conn
            mock_conn.logout.assert_called_once()


# ── Email search tests ──────────────────────────────────────


class TestEmailSearch:

    def test_search_default_criteria(self):
        reader = IMAPEmailReader(
            host="h", user="u", password="p",
            subject_keywords=["财务", "report"],
            from_whitelist=["finance@test.com"],
        )
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b"100 101 102"])
        reader._conn = mock_conn

        uids = reader.search(
            subject_keywords=["财务", "report"],
            from_whitelist=["finance@test.com"],
            has_attachment=True,
        )

        assert uids == ["100", "101", "102"]

    def test_search_no_results(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b""])
        reader._conn = mock_conn

        uids = reader.search()
        assert uids == []

    def test_search_failed(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("NO", [b""])
        reader._conn = mock_conn

        uids = reader.search()
        assert uids == []

    def test_search_with_date_filter(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b"50 51"])
        reader._conn = mock_conn

        uids = reader.search(since="01-Jan-2024")
        assert uids == ["50", "51"]

    def test_search_default_method(self):
        reader = IMAPEmailReader(
            host="h", user="u", password="p",
            subject_keywords=["report"],
        )
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b"1 2"])
        reader._conn = mock_conn

        uids = reader.search_default()
        assert uids == ["1", "2"]


# ── Email fetch and parse tests ─────────────────────────────


class TestEmailFetch:

    def test_fetch_email_success(self):
        # Build a real email message
        msg = MIMEText("Hello world")
        msg["Subject"] = "Test Email"
        msg["From"] = "sender@test.com"
        msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"
        raw = msg.as_bytes()

        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [(b"1 RFC822", raw)])
        reader._conn = mock_conn

        result = reader.fetch_email("1")
        assert result is not None
        assert result.uid == "1"
        assert result.subject == "Test Email"
        assert result.from_addr == "sender@test.com"
        assert len(result.attachments) == 0

    def test_fetch_email_failure(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("NO", [None])
        reader._conn = mock_conn

        result = reader.fetch_email("1")
        assert result is None

    def test_fetch_and_extract_with_attachment(self):
        msg = MIMEMultipart()
        msg["Subject"] = "Report"
        msg["From"] = "finance@test.com"
        msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"

        # Add fake xlsx attachment
        excel_data = b"PK\x03\x04fake_excel_data"
        part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        part.set_payload(excel_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="report.xlsx")
        msg.attach(part)

        raw = msg.as_bytes()

        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [(b"1 RFC822", raw)])
        reader._conn = mock_conn

        result = reader.fetch_and_extract("1")
        assert result is not None
        assert len(result.attachments) == 1
        assert result.attachments[0].filename == "report.xlsx"
        assert result.attachments[0].size == len(excel_data)

    def test_fetch_and_extract_skips_non_excel(self):
        msg = MIMEMultipart()
        msg["Subject"] = "Report"
        msg["From"] = "finance@test.com"
        msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"

        # Add a PDF attachment (should be skipped)
        pdf_data = b"%PDF-1.4 fake pdf"
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="report.pdf")
        msg.attach(part)

        raw = msg.as_bytes()

        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [(b"1 RFC822", raw)])
        reader._conn = mock_conn

        result = reader.fetch_and_extract("1")
        assert result is not None
        assert len(result.attachments) == 0  # PDF should be filtered out

    def test_fetch_and_extract_size_limit(self):
        msg = MIMEMultipart()
        msg["Subject"] = "Big Report"
        msg["From"] = "finance@test.com"
        msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"

        # Create a large attachment (exceeds 1 byte limit)
        large_data = b"x" * 1000
        part = MIMEBase("application", "vnd.ms-excel")
        part.set_payload(large_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="big.xls")
        msg.attach(part)

        raw = msg.as_bytes()

        reader = IMAPEmailReader(host="h", user="u", password="p", max_attachment_size=100)
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [(b"1 RFC822", raw)])
        reader._conn = mock_conn

        result = reader.fetch_and_extract("1")
        assert result is not None
        assert len(result.attachments) == 0  # Too large

    def test_fetch_and_extract_no_data(self):
        reader = IMAPEmailReader(host="h", user="u", password="p")
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [None])
        reader._conn = mock_conn

        result = reader.fetch_and_extract("1")
        assert result is None


# ── Batch fetch tests ───────────────────────────────────────


class TestBatchFetch:

    def test_fetch_new_emails_all_processed(self, uid_tracker):
        reader = IMAPEmailReader(host="h", user="u", password="p", uid_tracker=uid_tracker)
        uid_tracker.mark_many(["1", "2", "3"])

        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b"1 2 3"])
        reader._conn = mock_conn

        messages = reader.fetch_new_emails()
        assert len(messages) == 0

    def test_fetch_new_emails_with_unprocessed(self, uid_tracker):
        reader = IMAPEmailReader(host="h", user="u", password="p", uid_tracker=uid_tracker)

        msg = MIMEMultipart()
        msg["Subject"] = "Report"
        msg["From"] = "finance@test.com"
        msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"

        excel_data = b"PK\x03\x04fake"
        part = MIMEBase("application", "vnd.ms-excel")
        part.set_payload(excel_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="r.xlsx")
        msg.attach(part)

        raw = msg.as_bytes()

        mock_conn = MagicMock()
        mock_conn.uid.side_effect = [
            ("OK", [b"1"]),  # search
            ("OK", [(b"1 RFC822", raw)]),  # fetch
        ]
        reader._conn = mock_conn

        messages = reader.fetch_new_emails()
        assert len(messages) == 1
        assert len(messages[0].attachments) == 1

    def test_fetch_new_emails_empty_search(self, uid_tracker):
        reader = IMAPEmailReader(host="h", user="u", password="p", uid_tracker=uid_tracker)
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b""])
        reader._conn = mock_conn

        messages = reader.fetch_new_emails()
        assert messages == []


# ── Cleanup tests ───────────────────────────────────────────


class TestCleanup:

    def test_cleanup_temp_files(self):
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        assert os.path.exists(path)

        IMAPEmailReader.cleanup_temp_files([path])
        assert not os.path.exists(path)

    def test_cleanup_missing_file(self):
        # Should not raise
        IMAPEmailReader.cleanup_temp_files(["/nonexistent/file.xlsx"])

    def test_allowed_extensions(self):
        assert ".xlsx" in ALLOWED_EXTENSIONS
        assert ".xls" in ALLOWED_EXTENSIONS
        assert ".pdf" not in ALLOWED_EXTENSIONS
        assert ".csv" not in ALLOWED_EXTENSIONS
