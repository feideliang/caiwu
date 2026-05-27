"""Knowledge rule CRUD + import API.

On create/update, triggers async sync to propagate rule config changes
to the rule engine cache.
"""

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
from app.services.rule_config import set_rule_config, invalidate_rule_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])


def _to_dict(r: KnowledgeRule) -> dict:
    return {
        "id": r.id,
        "category": r.category,
        "rule_text": r.rule_text,
        "source_section": r.source_section,
        "is_active": r.is_active,
        "rule_code": r.rule_code,
        "threshold": r.threshold,
        "severity": r.severity,
        "condition": r.condition,
        "is_executable": r.is_executable,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


async def _sync_rule_config(rule: KnowledgeRule) -> None:
    """Update Redis cache with this rule's config if it has a rule_code.

    Called automatically after create/update so the rule engine
    picks up changes without manual intervention.
    """
    if not rule.rule_code:
        return
    await set_rule_config(rule.rule_code, {
        "threshold": rule.threshold,
        "severity": rule.severity,
        "condition": rule.condition,
        "is_executable": rule.is_executable,
    })


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
    return APIResponse.success(data=[_to_dict(r) for r in rules])


@router.post("/", response_model=APIResponse)
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Create a new knowledge rule. Auto-syncs config to engine cache."""
    from app.services.rule_store import upsert_to_qdrant

    rule = KnowledgeRule(
        category=body.category,
        rule_text=body.rule_text,
        source_section=body.source_section,
        is_active=body.is_active,
        rule_code=body.rule_code,
        threshold=body.threshold,
        severity=body.severity,
        condition=body.condition,
        is_executable=body.is_executable,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    # Sync to Qdrant
    point_id = str(uuid.uuid4())
    rule.qdrant_point_id = point_id
    await db.commit()

    upsert_to_qdrant(point_id, body.rule_text, body.category,
                     body.source_section, body.is_active)

    # Sync to engine config cache
    await _sync_rule_config(rule)

    return APIResponse.success(data={"id": rule.id})


@router.put("/{rule_id}", response_model=APIResponse)
async def update_rule(
    rule_id: int,
    body: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Update a knowledge rule. Auto-syncs config to engine cache."""
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
    if body.rule_code is not None:
        rule.rule_code = body.rule_code
    if body.threshold is not None:
        rule.threshold = body.threshold
    if body.severity is not None:
        rule.severity = body.severity
    if body.condition is not None:
        rule.condition = body.condition
    if body.is_executable is not None:
        rule.is_executable = body.is_executable

    await db.commit()

    # Sync to Qdrant
    if rule.qdrant_point_id:
        upsert_to_qdrant(rule.qdrant_point_id, rule.rule_text,
                         rule.category, rule.source_section, rule.is_active)

    # Sync to engine config cache
    await _sync_rule_config(rule)

    return APIResponse.success(data={"id": rule.id})


@router.delete("/{rule_id}", response_model=APIResponse)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Delete a knowledge rule. Removes config from engine cache."""
    from app.services.rule_store import delete_from_qdrant

    rule = await db.get(KnowledgeRule, rule_id)
    if not rule:
        return APIResponse.fail(message="Rule not found")

    if rule.qdrant_point_id:
        delete_from_qdrant(rule.qdrant_point_id)

    # Remove from engine cache
    if rule.rule_code:
        await invalidate_rule_config(rule.rule_code)

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
    from app.services.rule_config import invalidate_all_rule_configs

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
            rule_code=item.rule_code,
            threshold=item.threshold,
            severity=item.severity,
            condition=item.condition,
            is_executable=item.is_executable,
        )
        db.add(rule)
        await db.flush()
        await db.refresh(rule)

        point_id = str(uuid.uuid4())
        rule.qdrant_point_id = point_id
        await db.commit()

        upsert_to_qdrant(point_id, item.rule_text, item.category,
                         item.source_section, item.is_active)

        # Sync each rule to engine cache
        if rule.rule_code:
            await _sync_rule_config(rule)

        imported.append(rule.id)

    return APIResponse.success(data={"imported_count": len(imported), "ids": imported})