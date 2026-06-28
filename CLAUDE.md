# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MobyPrince ("Moby Prince") is a RAG (retrieval-augmented generation) agent over the documents of the Moby Prince legal case — load PDFs, query them, get cited answers from Claude. **Ingestion is built** (PDF → parse/OCR → chunk → `bge-m3` embed → Qdrant + Meili); **retrieval and the real Claude `/chat` are not yet wired** — `/chat` and `/search` still return mocks. Comments and UI text are in Italian.

## Architecture

Two apps backed by three data services, all orchestrated via Docker Compose:

- **`apps/api`** — FastAPI backend. Owns all auth, storage, and the RAG pipeline.
  - `main.py` — HTTP endpoints: `GET /health` (pings the three stores), `POST /ingest/test-upload` (MinIO smoke test), `GET /search` (mock), `POST /chat` (still a mock answer; **no LLM call wired in yet**).
  - `settings.py` — the shared `pydantic-settings` `Settings` (imported by both `main.py` and the RAG package). Add config here, not inline.
  - `rag/` — the ingestion pipeline (built; retrieval + real `/chat` not yet wired):
    - `metadata.py` — derive `doc_id`/title/`act_type`/`date` from the filename (no guessing; unparsable fields stay `None`).
    - `parse.py` — PDF → per-page normalized text; **text-first with per-page OCR fallback** (lazy `pytesseract`+`tesseract-ocr-ita`, so it runs without OCR installed).
    - `chunk.py` — token-bounded chunks (default 1000 tok, 120 overlap) that **preserve page ranges** for citations; token counter is injected.
    - `embed.py` — `bge-m3` via `sentence-transformers` (CPU, 1024-dim, lazy-loaded/cached); also exposes the tokenizer as the chunk token-counter.
    - `store.py` — upsert to Qdrant + Meili, keyed by a deterministic point id from `chunk_id`; `delete_document` first makes reindex idempotent.
    - `ingest.py` — orchestrates parse → chunk → embed → store. Shared core for the CLI and the future `POST /ingest`.
  - `ingest_cli.py` — `python -m apps.api.ingest_cli <pdf...>` (the current way to ingest, ahead of the HTTP endpoint).
- **`apps/ui`** — Streamlit dev console (`app.py`) with three tabs (Status / Chat / Storage) that call the API. This is a developer tool, not the end-user UI.
- **Data services** (defined in `infra/compose/docker-compose.dev.yml`):
  - **Qdrant** (`:6333`) — vector store; collection `chunks`, vector size **1024** (matches `bge-m3`). `doc_id` is a keyword payload index for fast per-document delete/filter.
  - **Meilisearch** (`:7700`) — keyword/lexical index `documents` (the system is designed for hybrid search).
  - **MinIO** (`:9000` API, `:9001` console) — S3-compatible document storage, bucket `docs`.

### Conventions that span files

- **Config is environment-driven.** The API + RAG package read config via `apps/api/settings.py` (`pydantic-settings`); init scripts and the UI use `os.getenv`. All defaults assume the Docker network (service names as hostnames: `http://qdrant:6333`, `http://minio:9000`, etc.). **Running anything on the host (CLI, init scripts) requires overriding the `*_URL`/`*_ENDPOINT` vars to `localhost`** — env vars take precedence over `.env`, so export them inline. Do NOT change the hostnames in `.env` itself, since the `api`/`ui` containers rely on them.
- **Auth**: protected endpoints expect `Authorization: Bearer <API_SECRET>` and validate it in `require_auth()`. `API_SECRET` is shared between the API and the UI via `.env`.
- **`infra/init/*` scripts are idempotent bootstrap, run manually.** They create the Qdrant collection, Meili index, and MinIO bucket if missing. They are **not** part of `docker-compose.dev.yml`, so they must be run by hand after the services are up (or wired in later).

## Common commands

Host development uses the conda env `moby-agent` (`/home/parri/miniconda3/envs/moby-agent`), Python 3.13. Data stores run in Docker; the embedder + CLI run on the host.

```bash
# Bring up ONLY the data stores (api/ui images lag behind — don't build them yet)
docker compose --env-file .env -f infra/compose/docker-compose.dev.yml up -d qdrant meilisearch minio

# Bootstrap stores AFTER they're healthy (manual; not in compose). On the host,
# prefix with localhost overrides, e.g. QDRANT_URL=http://localhost:6333 ...
python infra/init/init_qdrant.py && python infra/init/init_meili.py && python infra/init/init_minio.py

# Ingest PDFs (host; export localhost *_URL/*_ENDPOINT first). --no-ocr disables OCR fallback.
python -m apps.api.ingest_cli data/*.pdf

# Run the API / UI locally (without Docker) — also need localhost overrides
uvicorn apps.api.main:app --reload --port 8000
streamlit run apps/ui/app.py
```

UI is exposed on `${UI_PORT}` (default 8501); API on 8000.

## Notes

- There is **no test framework, linter, or CI** configured.
- Corpus lives in `data/` (git-ignored), all Italian; mostly text-based PDFs, OCR is a fallback for older scanned docs.
- Copy `.env.example` to `.env` and set `CLAUDE_API_KEY` before bringing up the stack; Compose reads `.env` via `env_file` and `${VAR}` interpolation.
- When implementing the real `/chat` flow, use the Claude API conventions `claude-sonnet-4-6` with `anthropic-version: 2023-06-01` (a Claude connectivity check previously lived in `apps/api/test.py`, removed; recover from git history `4367ad2` if needed).
