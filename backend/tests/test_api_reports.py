"""Integration tests for reports API: create, cancel, retry."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.v3 import ReportTask


@pytest.mark.anyio
class TestReportsAPI:

    async def test_create_report(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/reports",
            json={
                "report_type": "monthly",
                "period": "2024-01",
                "output_format": "pdf",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "pending"

    async def test_create_report_with_params(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/reports",
            json={
                "report_type": "weekly",
                "period": "2024-Q1",
                "output_format": "word",
                "params": {"include_charts": True},
            },
        )
        assert resp.status_code == 201

    async def test_list_reports_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_list_reports_with_data(self, admin_client: AsyncClient, db_session: AsyncSession):
        # Create a report task
        from app.core.security import hash_password
        from app.models.v4 import Role, User

        role = Role(name="admin", display_name="Admin", permissions=["*"])
        db_session.add(role)
        await db_session.flush()

        # Get user from seeded_db equivalent
        resp = await admin_client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin", "password": "testpass123"},
        )
        # Note: test_admin might not exist in fresh db, but we use admin_client

    async def test_get_report(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Get a specific report by ID."""
        # Create first
        resp = await admin_client.post(
            "/api/v1/reports",
            json={"report_type": "daily", "period": "2024-01-01", "output_format": "pdf"},
        )
        report_id = resp.json()["data"]["id"]

        # Then get
        resp = await admin_client.get(f"/api/v1/reports/{report_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["id"] == report_id

    async def test_get_report_not_found(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/999999")
        assert resp.status_code == 404

    async def test_cancel_report(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Cancel a pending report."""
        resp = await admin_client.post(
            "/api/v1/reports",
            json={"report_type": "monthly", "period": "2024-02", "output_format": "pdf"},
        )
        report_id = resp.json()["data"]["id"]

        resp = await admin_client.post(f"/api/v1/reports/{report_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "cancelled"

    async def test_cancel_nonexistent_report(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/reports/999999/cancel")
        assert resp.status_code == 404

    async def test_retry_report(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Retry a failed report."""
        # Create and mark as failed
        task = ReportTask(
            user_id=1,
            report_type="monthly",
            period="2024-03",
            status="failed",
            current_step="failed",
            output_format="pdf",
            error_message="Test error",
        )
        db_session.add(task)
        await db_session.flush()
        await db_session.refresh(task)

        resp = await admin_client.post(f"/api/v1/reports/{task.id}/retry")
        # Should create a new child task
        assert resp.status_code in (200, 201)

    async def test_retry_nonexistent_report(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/reports/999999/retry")
        assert resp.status_code == 404

    async def test_list_reports_with_status_filter(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports?page=1&page_size=10&status=pending")
        assert resp.status_code == 200

    async def test_reports_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/reports",
            json={"report_type": "daily", "period": "2024-01", "output_format": "pdf"},
        )
        assert resp.status_code in (401, 403)
