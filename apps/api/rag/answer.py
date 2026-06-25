"""Generate a cited answer with Claude, grounded only in the retrieved sources.

The full RAG turn: retrieve → build context → call Claude. The system prompt
constrains Claude to answer exclusively from the supplied sources, always cite
[Titolo, anno, p. X-Y], flag conflicts, and say so when evidence is insufficient.
"""
from __future__ import annotations

from dataclasses import dataclass

import anthropic

from apps.api.settings import settings
from .context import Source, build_context, render_sources
from .retrieve import retrieve

SYSTEM_PROMPT = """Sei un assistente esperto del caso Moby Prince. Rispondi ESCLUSIVAMENTE usando le fonti fornite (estratti di atti e documenti del caso).

Regole obbligatorie:
- Cita SEMPRE le fonti nel formato [Titolo, anno, p. X-Y] subito dopo l'affermazione che sostengono.
- Non speculare e non usare conoscenze esterne alle fonti.
- Se le fonti sono in conflitto, elenca esplicitamente i punti di divergenza.
- Se le fonti non contengono evidenze sufficienti per rispondere, dillo chiaramente e suggerisci cosa cercare.

Formato della risposta:
1. Risposta sintetica e accurata.
2. Punti chiave (elenco puntato).
3. Fonti citate con le pagine."""


@dataclass
class Answer:
    answer: str
    sources: list[Source]  # the sources passed to Claude (for citations / deep-links)
    input_tokens: int = 0
    output_tokens: int = 0


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)


def _build_user_message(query: str, sources_block: str) -> str:
    return (
        f"Domanda: {query}\n\n"
        f"Fonti (estratti con metadati):\n{sources_block}\n\n"
        "Rispondi seguendo le regole e il formato indicati."
    )


def answer_query(
    query: str,
    max_answer_tokens: int | None = None,
    context_max_tokens: int | None = None,
    reranker_top_n: int | None = None,
    model: str | None = None,
) -> Answer:
    chunks = retrieve(query, reranker_top_n=reranker_top_n)
    sources = build_context(chunks, max_tokens=context_max_tokens)

    if not sources:
        return Answer(
            answer="Non ho trovato fonti pertinenti nei documenti indicizzati per "
            "rispondere a questa domanda.",
            sources=[],
        )

    kwargs: dict = {
        "model": model or settings.CLAUDE_MODEL,
        "max_tokens": max_answer_tokens or settings.MAX_ANSWER_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _build_user_message(query, render_sources(sources))}],
    }
    if settings.CLAUDE_THINKING:
        kwargs["thinking"] = {"type": "adaptive"}

    resp = _client().messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if b.type == "text")
    return Answer(
        answer=text,
        sources=sources,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )
