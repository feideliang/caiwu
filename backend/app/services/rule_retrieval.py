"""RAG retrieval: embed question → Qdrant search → return matched rule texts."""

from __future__ import annotations

import time
from app.services.rule_store import get_qdrant_client, embed_text, ensure_collection


async def retrieve_rules(question: str, top_k: int = 5) -> str:
    """
    Embed the question, search Qdrant for matching rules,
    and return a formatted text block of matched rules.
    """
    t0 = time.time()
    ensure_collection()
    query_vector = await embed_text(question)
    print(f"[RAG] embed_text took {time.time()-t0:.2f}s", flush=True)

    if query_vector is None:
        return ""

    t1 = time.time()
    client = get_qdrant_client()
    hits = client.query_points(
        collection_name="knowledge_rules",
        query=query_vector,
        limit=top_k,
    ).points
    print(f"[RAG] qdrant search took {time.time()-t1:.3f}s, found {len(hits)} hits", flush=True)

    matched = [
        h.payload["rule_text"]
        for h in hits
        if h.payload and h.payload.get("is_active")
    ]
    return "\n".join(f"- {r}" for r in matched) if matched else ""
