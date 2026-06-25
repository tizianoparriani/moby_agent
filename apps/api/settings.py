from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    API_SECRET: str = "dev_secret_token"

    # MinIO / S3
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_ROOT_USER: str = "admin"
    MINIO_ROOT_PASSWORD: str = "adminadmin"
    MINIO_BUCKET: str = "docs"
    MINIO_REGION: str = "us-east-1"

    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "chunks"

    # Meilisearch
    MEILISEARCH_URL: str = "http://meilisearch:7700"
    MEILISEARCH_MASTER_KEY: str = "master_key_dev"
    MEILISEARCH_INDEX: str = "documents"

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024

    # Chunking (token-based; tokenizer is the embedding model's)
    CHUNK_TOKENS: int = 1000
    CHUNK_OVERLAP_TOKENS: int = 120

    # OCR fallback: a page whose extracted text is shorter than this (chars)
    # is treated as scanned and sent through OCR.
    OCR_MIN_CHARS: int = 200

    # Retrieval (hybrid vector + BM25 → reciprocal-rank fusion)
    RETRIEVAL_TOP_K: int = 50      # candidates fetched from each store
    FUSION_TOP_N: int = 10         # chunks kept after fusion (input to reranker when enabled)
    RRF_K: int = 60                # reciprocal-rank-fusion constant
    CONTEXT_MAX_TOKENS: int = 1400  # cap on assembled source context

    # Cross-encoder reranking (optional; set RERANKER_ENABLED=true to activate)
    RERANKER_ENABLED: bool = True
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_TOP_N: int = 5        # chunks kept after reranking

    # Super-user tier — higher limits for promoted users
    SUPERUSER_CLAUDE_MODEL: str = "claude-opus-4-8"
    SUPERUSER_MAX_ANSWER_TOKENS: int = 2048
    SUPERUSER_CONTEXT_MAX_TOKENS: int = 4000
    SUPERUSER_RERANKER_TOP_N: int = 5
    SUPERUSER_DAILY_QUERY_LIMIT: int = 20

    # Claude (answer generation)
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    MAX_ANSWER_TOKENS: int = 700
    # Enable adaptive thinking for harder analytical questions (adds latency).
    CLAUDE_THINKING: bool = False

    # Auth & user management
    JWT_SECRET: str = "change_me_in_production"
    JWT_EXPIRE_HOURS: int = 168  # 7 days
    DAILY_QUERY_LIMIT: int = 10
    # Admin account seeded on startup from these env vars (leave empty to skip).
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    # SQLite DB path (mounted as a Docker volume in production).
    DB_PATH: str = "/data/moby.db"
    # Donation URLs — shown to users when non-empty.
    DONATION_URL: str = ""
    KOFI_URL: str = ""


settings = Settings()
