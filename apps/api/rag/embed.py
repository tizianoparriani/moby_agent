"""bge-m3 embeddings via sentence-transformers (CPU).

The model is loaded lazily and cached process-wide so importing this module is
cheap. ``get_token_counter`` exposes the model's tokenizer for chunk sizing so
chunk budgets match what the encoder actually sees.
"""
from __future__ import annotations

from functools import lru_cache

from apps.api.settings import settings


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")


def get_token_counter():
    """Return a fn counting tokens with the embedding model's tokenizer."""
    tok = _model().tokenizer

    def count(text: str) -> int:
        return len(tok.encode(text, add_special_tokens=False))

    return count


def embed_texts(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    """Embed a list of texts; returns normalized vectors (cosine-ready)."""
    if not texts:
        return []
    vecs = _model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 32,
        convert_to_numpy=True,
    )
    return vecs.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
