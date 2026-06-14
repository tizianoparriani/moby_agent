"""Ingest PDFs into Qdrant + Meilisearch.

Usage (from repo root, with services up and the moby-agent env active):
    python -m apps.api.ingest_cli data/sample/*.pdf
    python -m apps.api.ingest_cli --no-ocr data/sample/Sentenza-1_31.10.1998.pdf

Requires QDRANT_URL / MEILISEARCH_URL reachable. When running on the host
against dockerized services, point those at localhost in .env (or export them).
"""
from __future__ import annotations

import argparse
import sys
import time

from apps.api.rag.ingest import ingest_pdf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest PDFs into the RAG stores.")
    ap.add_argument("paths", nargs="+", help="PDF file paths")
    ap.add_argument("--no-ocr", action="store_true", help="disable OCR fallback")
    args = ap.parse_args(argv)

    failures = 0
    for path in args.paths:
        t0 = time.time()
        try:
            res = ingest_pdf(path, allow_ocr=not args.no_ocr)
            dt = time.time() - t0
            print(
                f"OK  {res.filename}  doc_id={res.doc_id}  "
                f"pages={res.n_pages} (ocr={res.n_ocr_pages})  "
                f"chunks={res.n_chunks}  {dt:.1f}s"
            )
        except Exception as e:
            failures += 1
            print(f"ERR {path}: {e}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
