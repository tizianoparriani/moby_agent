"""Cross-encoder reranking: rescore retrieved chunks against the actual query.

After hybrid RRF retrieval, a cross-encoder reads (query, chunk_text) pairs and
produces relevance scores that are more accurate than the bi-encoder + BM25
scores used for initial retrieval.  The model is lazy-loaded and cached for the
process lifetime, mirroring the embedder pattern in embed.py.
"""
from __future__ import annotations

from functools import lru_cache

from apps.api.settings import settings
from .retrieve import Retrieved


@lru_cache(maxsize=1)
def _cross_encoder():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.RERANKER_MODEL, device="cpu")


def rerank(query: str, chunks: list[Retrieved], top_n: int | None = None) -> list[Retrieved]:
    """Return chunks re-ordered by cross-encoder relevance, keeping top_n."""
    if not chunks:
        return chunks
    top_n = top_n or settings.RERANKER_TOP_N
    model = _cross_encoder()
    pairs = [(query, ch.payload.get("text", "")) for ch in chunks]
    scores = model.predict(pairs)
    reranked = sorted(
        zip(scores, chunks),
        key=lambda sc: sc[0],
        reverse=True,
    )
    return [Retrieved(chunk_id=ch.chunk_id, score=float(s), payload=ch.payload)
            for s, ch in reranked[:top_n]]
