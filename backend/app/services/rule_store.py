"""Qdrant local client + embedding utility for RAG rule retrieval."""

from __future__ import annotations

import httpx
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION = "knowledge_rules"

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Lazy-initialized local-file Qdrant client."""
    global _client
    if _client is None:
        _client = QdrantClient(path=settings.qdrant_path)
    return _client


def ensure_collection() -> None:
    """Create Qdrant collection if it doesn't exist."""
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            COLLECTION,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection '{COLLECTION}'")


async def embed_text(text: str) -> list[float] | None:
    """Embed text using the configured embedding model via Qwen API endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.qwen_base_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                json={"model": settings.embedding_model, "input": text},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["data"][0]["embedding"]
            logger.warning(f"Embedding API returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
    return None


def upsert_to_qdrant(point_id: str, rule_text: str, category: str,
                     source_section: str | None, is_active: bool) -> None:
    """Upsert a single rule into Qdrant (sync)."""
    import uuid
    if not point_id:
        point_id = str(uuid.uuid4())

    client = get_qdrant_client()
    vector_text = f"{category}: {rule_text}"

    # Use synchronous httpx for embedding (called from sync context)
    import httpx as httpx_sync
    try:
        with httpx_sync.Client(timeout=10.0) as hc:
            resp = hc.post(
                f"{settings.qwen_base_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                json={"model": settings.embedding_model, "input": vector_text},
            )
            if resp.status_code == 200:
                embedding = resp.json()["data"][0]["embedding"]
            else:
                logger.warning(f"Embedding API returned {resp.status_code}")
                return
    except Exception as e:
        logger.warning(f"Embedding failed during upsert: {e}")
        return

    client.upsert(
        COLLECTION,
        points=[PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "rule_text": rule_text,
                "category": category,
                "source_section": source_section or "",
                "is_active": is_active,
            },
        )],
    )


def delete_from_qdrant(point_id: str) -> None:
    """Delete a point from Qdrant."""
    client = get_qdrant_client()
    client.delete(COLLECTION, points_selector=[point_id])
