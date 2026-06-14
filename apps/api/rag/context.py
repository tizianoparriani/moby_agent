"""Turn retrieved chunks into a token-bounded, citation-ready source context.

Steps: order by relevance → fill up to a token budget → merge chunks that are
contiguous within the same document (so adjacent passages read as one source
and the page range is continuous) → render each source with metadata Claude
cites against.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.api.settings import settings
from .embed import get_token_counter
from .retrieve import Retrieved


@dataclass
class Source:
    doc_id: str
    title: str
    date: str | None
    page_start: int
    page_end: int
    text: str


def _select_within_budget(chunks: list[Retrieved], max_tokens: int) -> list[Retrieved]:
    count = get_token_counter()
    selected: list[Retrieved] = []
    total = 0
    for ch in chunks:
        n = ch.payload.get("n_tokens") or count(ch.payload.get("text", ""))
        if selected and total + n > max_tokens:
            break
        selected.append(ch)
        total += n
    return selected


def _merge_contiguous(chunks: list[Retrieved]) -> list[Source]:
    """Merge chunks that are adjacent (by ordinal) within the same document."""
    by_doc: dict[str, list[Retrieved]] = {}
    for ch in chunks:
        by_doc.setdefault(ch.payload["doc_id"], []).append(ch)

    sources: list[Source] = []
    for doc_id, items in by_doc.items():
        items.sort(key=lambda c: c.payload.get("ordinal", 0))
        run: list[Retrieved] = []

        def flush(run: list[Retrieved]):
            if not run:
                return
            p0 = run[0].payload
            sources.append(
                Source(
                    doc_id=doc_id,
                    title=p0.get("title") or doc_id,
                    date=p0.get("date"),
                    page_start=min(r.payload["page_start"] for r in run),
                    page_end=max(r.payload["page_end"] for r in run),
                    text="\n\n".join(r.payload.get("text", "") for r in run),
                )
            )

        for ch in items:
            if run and ch.payload.get("ordinal", 0) == run[-1].payload.get("ordinal", 0) + 1:
                run.append(ch)
            else:
                flush(run)
                run = [ch]
        flush(run)
    return sources


def build_context(chunks: list[Retrieved]) -> list[Source]:
    selected = _select_within_budget(chunks, settings.CONTEXT_MAX_TOKENS)
    return _merge_contiguous(selected)


def render_sources(sources: list[Source]) -> str:
    """Format sources as a block Claude cites against."""
    blocks = []
    for s in sources:
        pages = f"p. {s.page_start}" if s.page_start == s.page_end else f"p. {s.page_start}-{s.page_end}"
        header = f"[DocID={s.doc_id}, Titolo={s.title}, Data={s.date or 'n/d'}, Pagine={pages}]"
        blocks.append(f'{header}\nTesto: """{s.text}"""')
    return "\n\n".join(blocks)
