"""Hybrid retrieval: vector (Qdrant) + BM25 (Meilisearch) → reciprocal-rank fusion.

Both stores hold the same chunks keyed by `chunk_id`, so we fuse their ranked
lists by chunk_id with RRF (score = Σ 1/(k + rank)). This avoids having to
calibrate Qdrant cosine scores against Meili's BM25 scores — only ranks matter.
"""
from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
import meilisearch

from apps.api.settings import settings
from .embed import embed_query


@dataclass
class Retrieved:
    chunk_id: str
    score: float       # fused RRF score
    payload: dict      # text + metadata (doc_id, title, date, page_start/end, ...)


def _vector_hits(query: str, k: int) -> list[dict]:
    qc = QdrantClient(url=settings.QDRANT_URL)
    vec = embed_query(query)
    res = qc.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vec,
        limit=k,
        with_payload=True,
    )
    return [p.payload for p in res.points]


def _bm25_hits(query: str, k: int) -> list[dict]:
    mc = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    res = mc.index(settings.MEILISEARCH_INDEX).search(query, {"limit": k})
    return res.get("hits", [])


def _rrf(ranked_lists: list[list[dict]], k: int) -> dict[str, float]:
    """Reciprocal-rank fusion keyed by chunk_id."""
    scores: dict[str, float] = {}
    for hits in ranked_lists:
        for rank, payload in enumerate(hits):
            cid = payload.get("chunk_id")
            if cid is None:
                continue
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def retrieve(query: str, top_n: int | None = None) -> list[Retrieved]:
    """Return the top-N chunks for a query, fused across both stores."""
    if not query.strip():
        return []
    top_n = top_n or settings.FUSION_TOP_N
    k = settings.RETRIEVAL_TOP_K

    vec_hits = _vector_hits(query, k)
    bm25_hits = _bm25_hits(query, k)

    # Keep the richest payload seen for each chunk_id (Qdrant and Meili payloads
    # are identical here, but be defensive and prefer whichever has 'text').
    payloads: dict[str, dict] = {}
    for hits in (vec_hits, bm25_hits):
        for p in hits:
            cid = p.get("chunk_id")
            if cid and (cid not in payloads or not payloads[cid].get("text")):
                payloads[cid] = p

    fused = _rrf([vec_hits, bm25_hits], settings.RRF_K)
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [Retrieved(chunk_id=cid, score=score, payload=payloads[cid]) for cid, score in ranked]
