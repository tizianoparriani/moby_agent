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

    CLAUDE_API_KEY: str = ""


settings = Settings()
