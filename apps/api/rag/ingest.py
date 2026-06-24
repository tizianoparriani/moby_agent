"""Orchestrate ingestion: PDF -> pages -> chunks -> vectors -> stores.

This is the shared core used by both the CLI (apps/api/ingest_cli.py) and the
future POST /ingest endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.api.settings import settings
from . import store
from .chunk import chunk_pages
from .embed import embed_texts, get_token_counter
from .metadata import DocMeta, enrich_date_from_text, enrich_title_from_text, meta_from_filename
from .parse import parse_pdf


@dataclass
class IngestResult:
    doc_id: str
    filename: str
    n_pages: int
    n_ocr_pages: int
    n_chunks: int


def ingest_pdf(
    path: str,
    doc_id: str | None = None,
    allow_ocr: bool = True,
    ensure: bool = True,
) -> IngestResult:
    meta: DocMeta = meta_from_filename(path, doc_id=doc_id)

    pages = parse_pdf(
        path, ocr_min_chars=settings.OCR_MIN_CHARS, allow_ocr=allow_ocr
    )

    first_pages_text = "\n".join(p.text for p in pages[:2])
    meta = enrich_title_from_text(first_pages_text, meta)
    meta = enrich_date_from_text(first_pages_text, meta)

    chunks = chunk_pages(
        pages,
        meta,
        count_tokens=get_token_counter(),
        max_tokens=settings.CHUNK_TOKENS,
        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
    )

    if ensure:
        store.ensure_collections()
    # Idempotent: drop any prior version of this doc before inserting.
    store.delete_document(meta.doc_id)

    vectors = embed_texts([c.text for c in chunks])
    store.upsert_chunks(meta, chunks, vectors)

    return IngestResult(
        doc_id=meta.doc_id,
        filename=meta.filename,
        n_pages=len(pages),
        n_ocr_pages=sum(1 for p in pages if p.ocr),
        n_chunks=len(chunks),
    )
