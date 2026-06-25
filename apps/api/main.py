import json
from contextlib import asynccontextmanager

import boto3
import requests
from fastapi import Depends, FastAPI, HTTPException

from apps.api.auth import (
    create_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from apps.api.db import (
    consume_invite_code,
    count_today_queries,
    create_invite_code,
    create_user,
    get_all_usage,
    get_invite_codes,
    get_user_by_username,
    get_user_history,
    get_user_token_usage,
    init_db,
    save_query,
    set_superuser,
    upsert_admin,
)
from apps.api.pricing import query_cost_usd
from apps.api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD:
        upsert_admin(settings.ADMIN_USERNAME, hash_password(settings.ADMIN_PASSWORD))
    yield


app = FastAPI(title="MobyPrince RAG API", lifespan=lifespan)


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
        region_name=settings.MINIO_REGION,
    )


def _daily_limit(user: dict) -> int:
    return settings.SUPERUSER_DAILY_QUERY_LIMIT if user.get("is_superuser") else settings.DAILY_QUERY_LIMIT


def _check_quota(user: dict) -> None:
    limit = _daily_limit(user)
    used = count_today_queries(user["id"])
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Limite giornaliero raggiunto ({limit} query/giorno)",
        )


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    q_ok = False
    try:
        r = requests.get(f"{settings.QDRANT_URL}/healthz", timeout=2)
        q_ok = r.ok
    except Exception:
        pass

    m_ok = False
    try:
        r = requests.get(f"{settings.MEILISEARCH_URL}/health", timeout=2)
        m_ok = r.ok
    except Exception:
        pass

    s3_ok = False
    try:
        s3_client().list_buckets()
        s3_ok = True
    except Exception:
        pass

    return {"env": settings.APP_ENV, "qdrant": q_ok, "meilisearch": m_ok, "minio": s3_ok}


# ── auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/register")
def register(payload: dict):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    code = (payload.get("invite_code") or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username e password obbligatori")
    if not code:
        raise HTTPException(status_code=400, detail="Codice invito obbligatorio")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username troppo corto (minimo 3 caratteri)")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password troppo corta (minimo 6 caratteri)")
    user = create_user(username, hash_password(password))
    if not user:
        raise HTTPException(status_code=409, detail="Username già in uso")
    if not consume_invite_code(code, user["id"]):
        # roll back the created user by deleting it
        from apps.api.db import _conn
        with _conn() as con:
            con.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        raise HTTPException(status_code=400, detail="Codice invito non valido o già utilizzato")
    return {"token": create_token(username), "username": username, "is_admin": bool(user["is_admin"]), "is_superuser": bool(user.get("is_superuser"))}


@app.post("/auth/login")
def login(payload: dict):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    return {
        "token": create_token(username),
        "username": username,
        "is_admin": bool(user["is_admin"]),
        "is_superuser": bool(user.get("is_superuser")),
    }


# ── user ──────────────────────────────────────────────────────────────────────

@app.get("/me/history")
def my_history(user: dict = Depends(get_current_user)):
    return {"history": get_user_history(user["id"])}


@app.get("/me/quota")
def my_quota(user: dict = Depends(get_current_user)):
    used = count_today_queries(user["id"])
    rows = get_user_token_usage(user["id"])
    total_cost = sum(
        query_cost_usd(r["model"] or "", r["input_tokens"] or 0, r["output_tokens"] or 0)
        for r in rows
    )
    limit = _daily_limit(user)
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "total_cost_usd": round(total_cost, 6),
        "donation_url": settings.DONATION_URL,
        "kofi_url": settings.KOFI_URL,
    }


# ── admin ─────────────────────────────────────────────────────────────────────

@app.get("/admin/usage")
def admin_usage(user: dict = Depends(require_admin)):
    rows = get_all_usage()
    for r in rows:
        token_rows = get_user_token_usage(r.pop("id"))
        r["total_cost_usd"] = round(
            sum(query_cost_usd(t["model"] or "", t["input_tokens"] or 0, t["output_tokens"] or 0) for t in token_rows),
            4,
        )
        r.pop("total_input_tokens", None)
        r.pop("total_output_tokens", None)
    return {"users": rows, "daily_limit": settings.DAILY_QUERY_LIMIT}


@app.post("/admin/invites")
def create_invite(user: dict = Depends(require_admin)):
    code = create_invite_code(user["id"])
    return {"code": code}


@app.get("/admin/invites")
def list_invites(user: dict = Depends(require_admin)):
    return {"invites": get_invite_codes(user["id"])}


@app.post("/admin/users/{username}/superuser")
def toggle_superuser(username: str, payload: dict, _: dict = Depends(require_admin)):
    value = bool(payload.get("value", True))
    if not set_superuser(username, value):
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"username": username, "is_superuser": value}


# ── RAG ───────────────────────────────────────────────────────────────────────

@app.get("/search")
def search(q: str = "", user: dict = Depends(get_current_user)):
    _check_quota(user)
    from apps.api.rag.retrieve import retrieve

    hits = retrieve(q)
    save_query(user["id"], "search", q)
    return {
        "query": q,
        "results": [
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
        ],
    }


@app.post("/chat")
def chat(payload: dict, user: dict = Depends(get_current_user)):
    _check_quota(user)
    from apps.api.rag.answer import answer_query

    query = payload.get("query", "")
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query vuota")
    is_super = bool(user.get("is_superuser"))
    model = settings.SUPERUSER_CLAUDE_MODEL if is_super else settings.CLAUDE_MODEL
    result = answer_query(
        query,
        model=model,
        max_answer_tokens=settings.SUPERUSER_MAX_ANSWER_TOKENS if is_super else None,
        context_max_tokens=settings.SUPERUSER_CONTEXT_MAX_TOKENS if is_super else None,
        reranker_top_n=settings.SUPERUSER_RERANKER_TOP_N if is_super else None,
    )
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
    save_query(
        user["id"], "chat", query, result.answer, json.dumps(citations),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        model=model,
    )
    cost = query_cost_usd(settings.CLAUDE_MODEL, result.input_tokens, result.output_tokens)
    return {"answer": result.answer, "citations": citations, "query_cost_usd": round(cost, 6)}


# ── storage ───────────────────────────────────────────────────────────────────

@app.post("/ingest/test-upload")
def test_upload(user: dict = Depends(require_admin)):
    s3 = s3_client()
    key = "hello/healthcheck.txt"
    s3.put_object(Bucket=settings.MINIO_BUCKET, Key=key, Body=b"hello world")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return {"key": key, "presigned_url": url}
