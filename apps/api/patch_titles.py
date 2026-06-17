"""One-shot script: enrich document titles in Qdrant + Meilisearch from PDF content.

Reads only the first page of each PDF (fast), extracts the witness name, and
patches the stored metadata without touching embeddings.

Usage (from repo root, with localhost env overrides):
    QDRANT_URL=http://localhost:6333 \
    MEILISEARCH_URL=http://localhost:7700 \
    conda run -n moby-agent python -m apps.api.patch_titles data/audizioni/*.pdf
"""
from __future__ import annotations

import sys

from apps.api.settings import settings
from apps.api.rag.metadata import enrich_title_from_text, meta_from_filename
from apps.api.rag.parse import parse_pdf
from apps.api.rag.store import patch_document_metadata


def patch(paths: list[str]) -> None:
    patched = skipped = failed = 0
    for path in paths:
        try:
            meta = meta_from_filename(path)
            pages = parse_pdf(path, ocr_min_chars=settings.OCR_MIN_CHARS, allow_ocr=False)
            # Use first 2 pages: cover letter + index (index sometimes starts on page 2).
            first_pages = "\n".join(p.text for p in pages[:2])
            enriched = enrich_title_from_text(first_pages, meta)

            if enriched.title == meta.title:
                print(f"  skip  {meta.filename}  →  {meta.title}")
                skipped += 1
                continue

            n = patch_document_metadata(meta.doc_id, enriched.title, enriched.act_type)
            print(f"  patch {meta.filename}  →  {enriched.title}  ({n} chunks)")
            patched += 1
        except Exception as exc:
            print(f"  ERROR {path}: {exc}")
            failed += 1

    print(f"\nDone: {patched} patched, {skipped} skipped, {failed} errors.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m apps.api.patch_titles <pdf...>")
        sys.exit(1)
    patch(sys.argv[1:])
