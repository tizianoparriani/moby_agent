"""Persist chunks to Qdrant (vectors) and Meilisearch (BM25/full-text).

Both stores are keyed by a stable point id derived from chunk_id, so
re-ingesting a document overwrites its chunks instead of duplicating them.
Deleting a document's existing chunks first keeps reindex idempotent even when
the new version has fewer chunks than the old one.
"""
from __future__ import annotations

import hashlib

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
import meilisearch

from apps.api.settings import settings
from .chunk import Chunk
from .metadata import DocMeta


def _point_id(chunk_id: str) -> str:
    # Qdrant point ids must be UUID or unsigned int; derive a deterministic UUID.
    h = hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _qdrant() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL)


def _meili():
    return meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)


def ensure_collections() -> None:
    """Create the Qdrant collection and Meili index/filters if missing."""
    qc = _qdrant()
    existing = {c.name for c in qc.get_collections().collections}
    if settings.QDRANT_COLLECTION not in existing:
        qc.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=qm.VectorParams(
                size=settings.EMBEDDING_DIM, distance=qm.Distance.COSINE
            ),
        )
    # Index doc_id so we can delete/filter a document's chunks quickly.
    try:
        qc.create_payload_index(
            settings.QDRANT_COLLECTION,
            field_name="doc_id",
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass  # already exists

    mc = _meili()
    try:
        mc.create_index(settings.MEILISEARCH_INDEX, {"primaryKey": "id"})
    except Exception:
        pass
    idx = mc.index(settings.MEILISEARCH_INDEX)
    idx.update_filterable_attributes(["doc_id", "act_type", "date", "page_start", "page_end"])
    idx.update_searchable_attributes(["text", "title"])


def delete_document(doc_id: str) -> None:
    """Remove all chunks of a document from both stores (idempotent reindex)."""
    _qdrant().delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]
            )
        ),
    )
    _meili().index(settings.MEILISEARCH_INDEX).delete_documents(
        filter=f'doc_id = "{doc_id}"'
    )


def patch_document_metadata(doc_id: str, title: str, act_type: str | None) -> int:
    """Update title/act_type for every chunk of doc_id without touching vectors.

    Returns the number of chunks patched.
    """
    qc = _qdrant()
    doc_filter = qm.Filter(
        must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]
    )
    qc.set_payload(
        collection_name=settings.QDRANT_COLLECTION,
        payload={"title": title, "act_type": act_type},
        points=qm.FilterSelector(filter=doc_filter),
    )

    mc = _meili().index(settings.MEILISEARCH_INDEX)
    result = mc.search("", {"filter": f'doc_id = "{doc_id}"', "limit": 5000,
                            "attributesToRetrieve": ["id"]})
    ids = [h["id"] for h in result["hits"]]
    if ids:
        mc.update_documents([{"id": pt_id, "title": title, "act_type": act_type}
                              for pt_id in ids])
    return len(ids)


def upsert_chunks(meta: DocMeta, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    if not chunks:
        return
    qc = _qdrant()
    points = []
    docs = []
    for ch, vec in zip(chunks, vectors):
        payload = {
            "doc_id": ch.doc_id,
            "chunk_id": ch.chunk_id,
            "ordinal": ch.ordinal,
            "text": ch.text,
            "page_start": ch.page_start,
            "page_end": ch.page_end,
            "title": meta.title,
            "act_type": meta.act_type,
            "date": meta.date,
            "filename": meta.filename,
        }
        points.append(
            qm.PointStruct(id=_point_id(ch.chunk_id), vector=vec, payload=payload)
        )
        docs.append({"id": _point_id(ch.chunk_id), **payload})

    qc.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    _meili().index(settings.MEILISEARCH_INDEX).add_documents(docs)
