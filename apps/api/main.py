from fastapi import FastAPI, UploadFile, File, Header, HTTPException
import os, time, boto3, requests

from apps.api.settings import settings

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
    from apps.api.rag.retrieve import retrieve

    hits = retrieve(q)
    results = [
        {
            "doc_id": h.payload.get("doc_id"),
            "chunk_id": h.chunk_id,
            "title": h.payload.get("title"),
            "date": h.payload.get("date"),
            "page_start": h.payload.get("page_start"),
            "page_end": h.payload.get("page_end"),
            "score": round(h.score, 5),
            "text": h.payload.get("text", ""),
        }
        for h in hits
    ]
    return {"query": q, "results": results}

@app.post("/chat")
def chat(payload: dict, auth: str | None = Header(None, alias="Authorization")):
    require_auth(auth)
    from apps.api.rag.answer import answer_query

    query = payload.get("query", "")
    if not query.strip():
        raise HTTPException(status_code=400, detail="Missing query")
    result = answer_query(query)
    citations = [
        {
            "doc_id": s.doc_id,
            "title": s.title,
            "date": s.date,
            "page_start": s.page_start,
            "page_end": s.page_end,
        }
        for s in result.sources
    ]
    return {"answer": result.answer, "citations": citations}
