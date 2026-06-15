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
    FUSION_TOP_N: int = 10         # chunks kept after fusion
    RRF_K: int = 60                # reciprocal-rank-fusion constant
    CONTEXT_MAX_TOKENS: int = 4000  # cap on assembled source context

    # Claude (answer generation)
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-8"  # switch to claude-sonnet-4-6 for lower cost
    MAX_ANSWER_TOKENS: int = 2048
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


settings = Settings()
