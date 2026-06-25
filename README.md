# Archivio Intelligente — Caso Moby Prince

A RAG (retrieval-augmented generation) agent over the documents of the **Moby Prince** legal case. Load PDFs, ask questions in Italian, get cited answers grounded in the source documents.

The Moby Prince ferry disaster (10 April 1991, 140 victims) generated decades of judicial proceedings, parliamentary commission hearings, and expert reports. This tool makes that archive searchable and queryable through natural language.

---

## How it works

1. **Ingest** — PDFs are parsed (text-first, OCR fallback for scanned pages), split into token-bounded chunks, embedded with `BAAI/bge-m3` (1024-dim), and stored in both Qdrant (vector) and Meilisearch (BM25/keyword).
2. **Retrieve** — at query time, both stores are searched in parallel, their ranked lists are fused with reciprocal-rank fusion (RRF), and the top candidates are re-scored by a `BAAI/bge-reranker-v2-m3` cross-encoder.
3. **Answer** — the top chunks are assembled into a token-budgeted context block with citations, then passed to Claude with an Italian-language system prompt that requires grounded, cited answers and flags conflicts or insufficient evidence.

Citations in answers include document title, parliamentary legislature (when applicable), date, and page range — e.g. `[Titolo=Audizione di Mario Rossi, Commissione Parlamentare=XIX Legislatura, Data=2024-04-09, Pagine=p. 3-5]`.

---

## Architecture

```
apps/
  api/         FastAPI backend (auth, ingestion pipeline, retrieval, answer generation)
  ui/          Streamlit developer console (Status / Chat / Storage tabs)
infra/
  compose/     Dockerfiles + docker-compose.dev.yml
  init/        One-time bootstrap scripts for Qdrant, Meilisearch, MinIO
data/          PDF corpus (git-ignored)
```

**Data services** (Docker):
| Service | Port | Purpose |
|---|---|---|
| Qdrant | 6333 | Vector store (`chunks` collection, 1024-dim cosine) |
| Meilisearch | 7700 | BM25 / keyword index |
| MinIO | 9000 / 9001 | S3-compatible document storage |

---

## Prerequisites

- Docker + Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)
- For local ingestion outside Docker: Python 3.13, conda env `moby-agent`

---

## Quick start (local)

```bash
# 1. Configure
cp .env.example .env
# Edit .env: set CLAUDE_API_KEY, change JWT_SECRET, ADMIN_USERNAME, ADMIN_PASSWORD

# 2. Start data services
docker compose -f infra/compose/docker-compose.dev.yml up -d qdrant meilisearch minio

# 3. Bootstrap stores (one-time, run after services are healthy)
QDRANT_URL=http://localhost:6333 \
MEILISEARCH_URL=http://localhost:7700 \
MINIO_ENDPOINT=http://localhost:9000 \
  python infra/init/init_qdrant.py && \
  python infra/init/init_meili.py && \
  python infra/init/init_minio.py

# 4. Ingest PDFs
QDRANT_URL=http://localhost:6333 \
MEILISEARCH_URL=http://localhost:7700 \
MINIO_ENDPOINT=http://localhost:9000 \
  python -m apps.api.ingest_cli data/*.pdf

# 5. Start API + UI
uvicorn apps.api.main:app --reload --port 8000
streamlit run apps/ui/app.py
```

> **Note:** localhost URL overrides are required when running the CLI or init scripts on the host, because `.env` uses Docker service hostnames (`http://qdrant:6333`, etc.) that only resolve inside the container network.

---

## Deploying to a VPS

These steps assume a Linux VPS with Docker installed and the repo cloned at `/opt/moby_agent`. Adjust paths and the SSH target (`root@95.217.128.58`) as needed.

### Full deploy (code + image changes)

```bash
# 0. Sync your local .env to the VPS
scp /home/parri/src/moby_agent/.env root@<vps-ip>:/opt/moby_agent/.env

# 1. Build images locally
docker compose -f infra/compose/docker-compose.dev.yml build api ui

# 2. Transfer images to VPS
docker save compose-api:latest compose-ui:latest \
  | gzip \
  | ssh root@<vps-ip> 'gunzip | docker load'

# 3. Push code changes to VPS
ssh root@<vps-ip> 'cd /opt/moby_agent && git pull'

# 4. Restart containers
ssh root@<vps-ip> 'cd /opt/moby_agent && \
  docker compose -f infra/compose/docker-compose.dev.yml --env-file .env up -d api ui'
```

### Re-ingest PDFs (after corpus or metadata changes)

```bash
# 5. Copy PDFs to VPS
scp data/*.pdf root@<vps-ip>:/opt/moby_agent/inbox/

# 6. Copy PDFs into the container and ingest
ssh root@<vps-ip> '
  docker cp /opt/moby_agent/inbox api:/tmp/inbox &&
  docker exec api sh -c "python -m apps.api.ingest_cli /tmp/inbox/*.pdf"
'
```

### Pre-warm the reranker (recommended after every restart)

The cross-encoder model (~1.1 GB) is downloaded on first use. Run this after restart to avoid a slow first user query:

```bash
# 7. Pre-warm
ssh root@<vps-ip> 'docker exec api python -c \
  "from apps.api.rag.rerank import _cross_encoder; _cross_encoder()"'
```

### .env changes only (no rebuild needed)

Settings like `FUSION_TOP_N`, `CONTEXT_MAX_TOKENS`, `MAX_ANSWER_TOKENS`, or `RERANKER_ENABLED` are read from `.env` at startup. To change them without rebuilding: update `.env` on the VPS and run step 4 (restart only).

---

## Configuration reference

Key variables in `.env` (see `.env.example` for full list):

| Variable | Default | Description |
|---|---|---|
| `CLAUDE_API_KEY` | — | Anthropic API key (required) |
| `CLAUDE_MODEL` | `claude-opus-4-8` | Claude model used for answer generation |
| `RERANKER_ENABLED` | `true` | Enable cross-encoder reranking |
| `FUSION_TOP_N` | `10` | Chunks kept after RRF fusion (input to reranker) |
| `RERANKER_TOP_N` | `5` | Chunks kept after reranking (sent to Claude) |
| `CONTEXT_MAX_TOKENS` | `4000` | Token budget for assembled source context |
| `MAX_ANSWER_TOKENS` | `2048` | Max tokens in Claude's answer |
| `DAILY_QUERY_LIMIT` | `10` | Per-user daily query limit |
| `ADMIN_USERNAME` | — | Admin account seeded on startup |
| `ADMIN_PASSWORD` | — | Admin account password |
| `JWT_SECRET` | — | Secret for JWT signing (change in production) |
| `DONATION_URL` | — | PayPal.me URL; shown to users when non-empty |
| `KOFI_URL` | — | Ko-fi URL; shown to users when non-empty |

---

## License

This project is released for research and educational purposes in connection with the Moby Prince parliamentary investigation.
