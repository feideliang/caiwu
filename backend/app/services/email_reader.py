"""IMAP email reader service: connect, search, fetch attachments, track processed UIDs."""

from __future__ import annotations

import email
import imaplib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Allowed attachment extensions
ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@dataclass
class AttachmentInfo:
    """Metadata about a single email attachment."""

    filename: str
    content_type: str
    size: int
    temp_path: str  # path to saved temp file


@dataclass
class EmailMessage:
    """Parsed email with attachments."""

    uid: str
    subject: str
    from_addr: str
    date: str
    attachments: list[AttachmentInfo] = field(default_factory=list)
    raw_headers: dict[str, str] = field(default_factory=dict)


class ProcessedUIDTracker:
    """Track processed email UIDs in a JSON file to avoid re-processing."""

    def __init__(self, filepath: str | None = None) -> None:
        self.filepath = filepath or settings.imap_processed_uids_file
        self._uids: set[str] = set()
        self._load()

    def _load(self) -> None:
        path = Path(self.filepath)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._uids = set(data.get("processed_uids", []))
            except (json.JSONDecodeError, OSError):
                self._uids = set()

    def _save(self) -> None:
        path = Path(self.filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"processed_uids": sorted(self._uids)}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_processed(self, uid: str) -> bool:
        return uid in self._uids

    def mark_processed(self, uid: str) -> None:
        self._uids.add(uid)
        self._save()

    def mark_many(self, uids: list[str]) -> None:
        self._uids.update(uids)
        self._save()

    def clear(self) -> None:
        self._uids.clear()
        self._save()

    @property
    def count(self) -> int:
        return len(self._uids)


class IMAPEmailReader:
    """IMAP client for fetching emails with Excel attachments.

    Supports SSL connections, XOAUTH2 authentication (with password fallback),
    subject/from/attachment filtering, and connection keepalive.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_xoauth2: bool | None = None,
        max_attachment_size: int | None = None,
        subject_keywords: list[str] | None = None,
        from_whitelist: list[str] | None = None,
        uid_tracker: ProcessedUIDTracker | None = None,
    ) -> None:
        self.host = host or settings.imap_host
        self.port = port or settings.imap_port
        self.user = user or settings.imap_user
        self.password = password or settings.imap_password
        self.use_xoauth2 = use_xoauth2 if use_xoauth2 is not None else settings.imap_use_xoauth2
        self.max_attachment_size = max_attachment_size or settings.imap_max_attachment_size
        self.subject_keywords = subject_keywords or settings.imap_subject_keywords
        self.from_whitelist = from_whitelist or settings.imap_from_whitelist
        self.uid_tracker = uid_tracker or ProcessedUIDTracker()
        self._conn: imaplib.IMAP4_SSL | None = None

    # ── Connection management ──────────────────────────────

    def connect(self) -> imaplib.IMAP4_SSL:
        """Establish IMAP SSL connection and login."""
        if self._conn is not None:
            try:
                self._conn.noop()
                return self._conn
            except Exception:
                self._conn = None

        logger.info("Connecting to IMAP server %s:%d as %s", self.host, self.port, self.user)
        conn = imaplib.IMAP4_SSL(self.host, self.port)

        if self.use_xoauth2:
            self._login_xoauth2(conn)
        else:
            conn.login(self.user, self.password)

        conn.select("INBOX", readonly=False)
        self._conn = conn
        logger.info("IMAP connection established")
        return conn

    def _login_xoauth2(self, conn: imaplib.IMAP4_SSL) -> None:
        """Authenticate using XOAUTH2 mechanism."""
        try:
            token = self._acquire_oauth2_token()
        except Exception:
            logger.warning("XOAUTH2 token acquisition failed, falling back to password auth")
            conn.login(self.user, self.password)
            return

        auth_string = f"user={self.user}\x01auth=Bearer {token}\x01\x01"
        conn.authenticate("XOAUTH2", lambda x: auth_string)  # type: ignore[arg-type]

    def _acquire_oauth2_token(self) -> str:
        """Acquire OAuth2 token via MSAL.

        In production, integrate with MSAL library.
        For now, this is a placeholder that raises NotImplementedError.
        """
        # Production implementation would use:
        # import msal
        # app = msal.ConfidentialClientApplication(...)
        # result = app.acquire_token_for_client(scopes=["https://outlook.office365.com/.default"])
        # return result["access_token"]
        raise NotImplementedError(
            "XOAUTH2 token acquisition requires MSAL. "
            "Set imap_use_xoauth2=False to use password auth."
        )

    def disconnect(self) -> None:
        """Close IMAP connection gracefully."""
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None
            logger.info("IMAP connection closed")

    def keepalive(self) -> None:
        """Send NOOP to keep the connection alive."""
        if self._conn:
            try:
                self._conn.noop()
                logger.debug("IMAP NOOP keepalive sent")
            except Exception as exc:
                logger.warning("IMAP NOOP failed, connection may be stale: %s", exc)
                self._conn = None

    # ── Search ─────────────────────────────────────────────

    def search(
        self,
        mailbox: str = "INBOX",
        subject_keywords: list[str] | None = None,
        from_whitelist: list[str] | None = None,
        has_attachment: bool = True,
        since: str | None = None,
    ) -> list[str]:
        """Search for email UIDs matching criteria.

        Args:
            mailbox: IMAP mailbox to search.
            subject_keywords: Filter by subject containing these keywords.
            from_whitelist: Filter by sender addresses.
            has_attachment: Only return emails with attachments.
            since: IMAP SINCE date filter (e.g. "01-Jan-2024").

        Returns:
            List of email UIDs as strings.
        """
        conn = self.connect()
        conn.select(mailbox, readonly=True)

        criteria: list[str] = []

        if has_attachment:
            criteria.append("HAS_ATTACHMENT")

        if since:
            criteria.append(f'SINCE "{since}"')

        if subject_keywords:
            for kw in subject_keywords:
                criteria.append(f'SUBJECT "{kw}"')

        if from_whitelist:
            from_criteria = " OR ".join(f'FROM "{addr}"' for addr in from_whitelist)
            if len(from_whitelist) > 1:
                criteria.append(f"({from_criteria})")
            else:
                criteria.append(f'FROM "{from_whitelist[0]}"')

        if not criteria:
            criteria.append("ALL")

        search_expr = " ".join(criteria)
        logger.debug("IMAP search: %s", search_expr)

        status, data = conn.uid("search", None, search_expr)
        if status != "OK":
            logger.warning("IMAP search failed: %s", status)
            return []

        uids = data[0].split() if data[0] else []
        return [uid.decode() for uid in uids]

    def search_default(self) -> list[str]:
        """Search using configured default filters."""
        return self.search(
            subject_keywords=self.subject_keywords or None,
            from_whitelist=self.from_whitelist or None,
            has_attachment=True,
        )

    # ── Fetch & Parse ──────────────────────────────────────

    def fetch_email(self, uid: str) -> EmailMessage | None:
        """Fetch and parse a single email by UID.

        Returns EmailMessage with parsed attachments, or None on failure.
        """
        conn = self.connect()
        status, data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data:
            logger.warning("Failed to fetch email UID %s", uid)
            return None

        raw_bytes = data[0][1] if isinstance(data[0], tuple) else None
        if raw_bytes is None:
            return None

        msg = email.message_from_bytes(raw_bytes)
        return self._parse_message(msg, uid)

    def fetch_and_extract(self, uid: str) -> EmailMessage | None:
        """Fetch email and save attachments to temp files.

        Only saves .xlsx/.xls files within the size limit.
        Returns EmailMessage with AttachmentInfo entries.
        """
        conn = self.connect()
        status, data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data:
            return None

        raw_bytes = data[0][1] if isinstance(data[0], tuple) else None
        if raw_bytes is None:
            return None

        msg = email.message_from_bytes(raw_bytes)
        return self._parse_message_with_attachments(msg, uid)

    def _parse_message(self, msg: email.message.Message, uid: str) -> EmailMessage:
        """Parse email headers without extracting attachments."""
        subject = msg.get("Subject", "")
        from_addr = msg.get("From", "")
        date = msg.get("Date", "")

        headers = {k: v for k, v in msg.items()}

        return EmailMessage(
            uid=uid,
            subject=subject,
            from_addr=from_addr,
            date=date,
            raw_headers=headers,
        )

    def _parse_message_with_attachments(
        self, msg: email.message.Message, uid: str
    ) -> EmailMessage:
        """Parse email and extract valid attachments to temp files."""
        subject = msg.get("Subject", "")
        from_addr = msg.get("From", "")
        date = msg.get("Date", "")
        headers = {k: v for k, v in msg.items()}
        attachments: list[AttachmentInfo] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" not in content_disposition:
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                self._process_attachment_part(part, filename, attachments)

        return EmailMessage(
            uid=uid,
            subject=subject,
            from_addr=from_addr,
            date=date,
            attachments=attachments,
            raw_headers=headers,
        )

    def _process_attachment_part(
        self,
        part: email.message.Message,
        filename: str,
        attachments: list[AttachmentInfo],
    ) -> None:
        """Process a single MIME attachment part."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            logger.debug("Skipping attachment %s: extension %s not allowed", filename, ext)
            return

        payload = part.get_payload(decode=True)
        if payload is None:
            return

        size = len(payload)
        if size > self.max_attachment_size:
            logger.warning(
                "Attachment %s exceeds size limit (%d > %d bytes)",
                filename,
                size,
                self.max_attachment_size,
            )
            return

        content_type = part.get_content_type()
        temp_path = self._save_to_temp(payload, filename)

        attachments.append(
            AttachmentInfo(
                filename=filename,
                content_type=content_type,
                size=size,
                temp_path=temp_path,
            )
        )
        logger.info("Extracted attachment: %s (%d bytes)", filename, size)

    @staticmethod
    def _save_to_temp(data: bytes, filename: str) -> str:
        """Save binary data to a temp file and return the path."""
        suffix = os.path.splitext(filename)[1]
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="email_attach_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except Exception:
            os.unlink(path)
            raise
        return path

    # ── Batch fetch ────────────────────────────────────────

    def fetch_new_emails(self) -> list[EmailMessage]:
        """Search for new (unprocessed) emails and fetch them with attachments.

        Returns list of EmailMessage objects with extracted attachments.
        """
        uids = self.search_default()
        if not uids:
            return []

        # Filter out already processed
        new_uids = [uid for uid in uids if not self.uid_tracker.is_processed(uid)]
        if not new_uids:
            logger.info("All %d found emails already processed", len(uids))
            return []

        logger.info("Fetching %d new emails from %d total", len(new_uids), len(uids))
        messages: list[EmailMessage] = []
        processed: list[str] = []

        for uid in new_uids:
            msg = self.fetch_and_extract(uid)
            if msg and msg.attachments:
                messages.append(msg)
                processed.append(uid)
            elif msg:
                # Email fetched but no valid attachments — still mark as processed
                messages.append(msg)
                processed.append(uid)

        if processed:
            self.uid_tracker.mark_many(processed)

        return messages

    # ── Cleanup ────────────────────────────────────────────

    @staticmethod
    def cleanup_temp_files(paths: list[str]) -> None:
        """Remove temp files created during attachment extraction."""
        for path in paths:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError as exc:
                logger.warning("Failed to remove temp file %s: %s", path, exc)

    def __enter__(self) -> "IMAPEmailReader":
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.disconnect()
