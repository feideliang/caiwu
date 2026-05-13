"""Knowledge rule CRUD + import API."""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.core import KnowledgeRule
from app.schemas.system import RuleCreate, RuleUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/", response_model=APIResponse)
async def list_rules(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """List knowledge rules, optionally filtered by category."""
    stmt = select(KnowledgeRule).order_by(KnowledgeRule.id)
    if category:
        stmt = stmt.where(KnowledgeRule.category == category)
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return APIResponse.success(data=[
        {
            "id": r.id,
            "category": r.category,
            "rule_text": r.rule_text,
            "source_section": r.source_section,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rules
    ])


@router.post("/", response_model=APIResponse)
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Create a new knowledge rule."""
    from app.services.rule_store import upsert_to_qdrant

    rule = KnowledgeRule(
        category=body.category,
        rule_text=body.rule_text,
        source_section=body.source_section,
        is_active=body.is_active,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    # Sync to Qdrant (use sync session for embedding)
    point_id = str(uuid.uuid4())
    rule.qdrant_point_id = point_id
    await db.commit()

    upsert_to_qdrant(point_id, body.rule_text, body.category,
                     body.source_section, body.is_active)
    return APIResponse.success(data={"id": rule.id})


@router.put("/{rule_id}", response_model=APIResponse)
async def update_rule(
    rule_id: int,
    body: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Update a knowledge rule."""
    from app.services.rule_store import upsert_to_qdrant

    rule = await db.get(KnowledgeRule, rule_id)
    if not rule:
        return APIResponse.fail(message="Rule not found")

    if body.category is not None:
        rule.category = body.category
    if body.rule_text is not None:
        rule.rule_text = body.rule_text
    if body.source_section is not None:
        rule.source_section = body.source_section
    if body.is_active is not None:
        rule.is_active = body.is_active

    await db.commit()

    # Sync to Qdrant
    if rule.qdrant_point_id:
        upsert_to_qdrant(rule.qdrant_point_id, rule.rule_text,
                         rule.category, rule.source_section, rule.is_active)
    return APIResponse.success(data={"id": rule.id})


@router.delete("/{rule_id}", response_model=APIResponse)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Delete a knowledge rule."""
    from app.services.rule_store import delete_from_qdrant

    rule = await db.get(KnowledgeRule, rule_id)
    if not rule:
        return APIResponse.fail(message="Rule not found")

    if rule.qdrant_point_id:
        delete_from_qdrant(rule.qdrant_point_id)

    await db.delete(rule)
    await db.commit()
    return APIResponse.success(data={"id": rule_id})


@router.post("/import", response_model=APIResponse)
async def import_rules(
    rules: list[RuleCreate] = Body(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Batch import rules (JSON array). Clears existing rules first."""
    from app.services.rule_store import upsert_to_qdrant, get_qdrant_client, ensure_collection

    ensure_collection()
    client = get_qdrant_client()

    # Clear existing
    result = await db.execute(select(KnowledgeRule))
    existing = result.scalars().all()
    for r in existing:
        if r.qdrant_point_id:
            try:
                client.delete("knowledge_rules", points_selector=[r.qdrant_point_id])
            except Exception:
                pass
        await db.delete(r)
    await db.commit()

    # Insert new
    imported = []
    for item in rules:
        rule = KnowledgeRule(
            category=item.category,
            rule_text=item.rule_text,
            source_section=item.source_section,
            is_active=item.is_active,
        )
        db.add(rule)
        await db.flush()
        await db.refresh(rule)

        point_id = str(uuid.uuid4())
        rule.qdrant_point_id = point_id
        await db.commit()

        upsert_to_qdrant(point_id, item.rule_text, item.category,
                         item.source_section, item.is_active)
        imported.append(rule.id)

    return APIResponse.success(data={"imported_count": len(imported), "ids": imported})
