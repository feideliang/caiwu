"""Tests for the data freshness service."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


class TestDataFreshness:
    """Test data freshness status determination."""

    def test_fresh_status(self):
        """Last sync within 30 minutes -> fresh."""
        import asyncio

        async def _test():
            mock_db = AsyncMock()
            now = datetime.now(timezone.utc)

            # Mock sync job query result
            sync_row = MagicMock()
            sync_row.__getitem__ = lambda self, idx: now - timedelta(minutes=10) if idx == 0 else None

            batch_row = MagicMock()
            batch_row.__getitem__ = lambda self, idx: None

            call_count = [0]

            async def mock_execute(stmt):
                call_count[0] += 1
                result = MagicMock()
                if call_count[0] == 1:
                    result.first.return_value = (now - timedelta(minutes=10), None)
                elif call_count[0] == 2:
                    result.first.return_value = None
                else:
                    result.first.return_value = None
                return result

            mock_db.execute = mock_execute

            from app.services.freshness import _compute_freshness
            result = await _compute_freshness(mock_db)
            assert result["status"] == "fresh"

        asyncio.run(_test())

    def test_stale_status(self):
        """Last sync 30-60 minutes ago -> stale."""
        import asyncio

        async def _test():
            mock_db = AsyncMock()
            now = datetime.now(timezone.utc)

            async def mock_execute(stmt):
                result = MagicMock()
                result.first.return_value = (now - timedelta(minutes=45), None)
                return result

            mock_db.execute = mock_execute

            from app.services.freshness import _compute_freshness
            result = await _compute_freshness(mock_db)
            assert result["status"] == "stale"

        asyncio.run(_test())

    def test_error_status(self):
        """Last sync >60 minutes ago -> error."""
        import asyncio

        async def _test():
            mock_db = AsyncMock()
            now = datetime.now(timezone.utc)

            async def mock_execute(stmt):
                result = MagicMock()
                result.first.return_value = (now - timedelta(minutes=120), None)
                return result

            mock_db.execute = mock_execute

            from app.services.freshness import _compute_freshness
            result = await _compute_freshness(mock_db)
            assert result["status"] == "error"

        asyncio.run(_test())

    def test_no_sync_history_is_error(self):
        """No sync history -> error."""
        import asyncio

        async def _test():
            mock_db = AsyncMock()

            async def mock_execute(stmt):
                result = MagicMock()
                result.first.return_value = None
                return result

            mock_db.execute = mock_execute

            from app.services.freshness import _compute_freshness
            result = await _compute_freshness(mock_db)
            assert result["status"] == "error"

        asyncio.run(_test())

    def test_response_includes_all_fields(self):
        """Freshness response includes all expected fields."""
        import asyncio

        async def _test():
            mock_db = AsyncMock()
            now = datetime.now(timezone.utc)

            async def mock_execute(stmt):
                result = MagicMock()
                result.first.return_value = (now - timedelta(minutes=10), None)
                return result

            mock_db.execute = mock_execute

            from app.services.freshness import _compute_freshness
            result = await _compute_freshness(mock_db)

            assert "last_sync_time" in result
            assert "status" in result
            assert result["status"] == "fresh"
            assert "next_sync_at" in result

        asyncio.run(_test())

    def test_cache_integration_with_mock(self):
        """When cache has data, it should return cached value."""
        import asyncio

        async def _test():
            with patch("app.services.freshness.cache_get") as mock_get, \
                 patch("app.services.freshness.cache_set") as mock_set:

                mock_get.return_value = {"status": "fresh", "cached": True}

                from app.services.freshness import get_data_freshness
                result = await get_data_freshness(AsyncMock())

                assert result["status"] == "fresh"
                assert result.get("cached") is True
                # Should not call _compute_freshness (no DB call)
                mock_set.assert_not_called()

        asyncio.run(_test())
