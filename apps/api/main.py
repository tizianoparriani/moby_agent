from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from pydantic_settings import BaseSettings
import os, time, boto3, requests

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    API_SECRET: str = "dev_secret_token"

    MINIO_ENDPOINT: str = "[minio](http://minio:9000)"
    MINIO_ROOT_USER: str = "admin"
    MINIO_ROOT_PASSWORD: str = "adminadmin"
    MINIO_BUCKET: str = "docs"
    MINIO_REGION: str = "us-east-1"

    QDRANT_URL: str = "[qdrant](http://qdrant:6333)"
    MEILISEARCH_URL: str = "[meilisearch](http://meilisearch:7700)"
    MEILISEARCH_MASTER_KEY: str = "master_key_dev"

    CLAUDE_API_KEY: str = ""

settings = Settings()
app = FastAPI(title="MobyPrince RAG API")

def require_auth(auth: str | None):
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1]
    if token != settings.API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid token")

def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
        region_name=settings.MINIO_REGION,
    )

@app.get("/health")
def health():
    # Qdrant
    q_ok = False
    try:
        r = requests.get(f"{settings.QDRANT_URL}/healthz", timeout=2)
        q_ok = r.ok
    except Exception:
        q_ok = False

    # Meili
    m_ok = False
    try:
        r = requests.get(f"{settings.MEILISEARCH_URL}/health", timeout=2)
        m_ok = r.ok
    except Exception:
        m_ok = False

    # MinIO
    s3_ok = False
    try:
        s3 = s3_client()
        s3.list_buckets()
        s3_ok = True
    except Exception:
        s3_ok = False

    return {"env": settings.APP_ENV, "qdrant": q_ok, "meilisearch": m_ok, "minio": s3_ok}

@app.post("/ingest/test-upload")
def test_upload(auth: str | None = Header(None, alias="Authorization")):
    require_auth(auth)
    s3 = s3_client()
    key = "hello/healthcheck.txt"
    s3.put_object(Bucket=settings.MINIO_BUCKET, Key=key, Body=b"hello world")
    # presigned url
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return {"key": key, "presigned_url": url}

@app.get("/search")
def search(q: str = ""):
    # mock response structure
    return {"query": q, "results": []}

@app.post("/chat")
def chat(payload: dict, auth: str | None = Header(None, alias="Authorization")):
    require_auth(auth)
    query = payload.get("query", "")
    # mock: no LLM call yet
    return {"answer": f"(mock) Hai chiesto: {query}", "citations": []}
