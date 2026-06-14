"""Pack page text into token-bounded chunks that preserve page ranges.

Chunks are built from paragraph units so we never split mid-sentence unless a
single paragraph exceeds the budget. Each chunk records the page span it covers
(page_start..page_end) so answers can cite [Titolo, anno, p. X-Y].

``count_tokens`` is injected (the embedding model's tokenizer in production, a
cheap word-count approximation in tests) so this module has no heavy deps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .metadata import DocMeta
from .parse import Page

CountTokens = Callable[[str], int]


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str  # f"{doc_id}:{ordinal}"
    ordinal: int
    text: str
    page_start: int
    page_end: int
    n_tokens: int


@dataclass
class _Unit:
    text: str
    page: int


def approx_token_count(text: str) -> int:
    """Rough word/punctuation count; ~1.3x words ≈ tokens for IT text."""
    return max(1, int(len(text.split()) * 1.3))


def _split_into_units(pages: list[Page]) -> list[_Unit]:
    units: list[_Unit] = []
    for p in pages:
        if not p.text.strip():
            continue
        for para in re.split(r"\n\s*\n", p.text):
            para = para.strip()
            if para:
                units.append(_Unit(text=para, page=p.page_no))
    return units


def _split_long_unit(unit: _Unit, max_tokens: int, count: CountTokens) -> list[_Unit]:
    """Split a paragraph that alone exceeds the budget, on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", unit.text)
    out: list[_Unit] = []
    buf: list[str] = []
    for s in sentences:
        candidate = " ".join(buf + [s])
        if buf and count(candidate) > max_tokens:
            out.append(_Unit(text=" ".join(buf), page=unit.page))
            buf = [s]
        else:
            buf.append(s)
    if buf:
        out.append(_Unit(text=" ".join(buf), page=unit.page))
    return out


def chunk_pages(
    pages: list[Page],
    meta: DocMeta,
    count_tokens: CountTokens = approx_token_count,
    max_tokens: int = 1000,
    overlap_tokens: int = 120,
) -> list[Chunk]:
    units = _split_into_units(pages)

    # Pre-split any oversized paragraph.
    norm: list[_Unit] = []
    for u in units:
        if count_tokens(u.text) > max_tokens:
            norm.extend(_split_long_unit(u, max_tokens, count_tokens))
        else:
            norm.append(u)

    chunks: list[Chunk] = []
    cur: list[_Unit] = []
    cur_tokens = 0
    ordinal = 0

    def flush():
        nonlocal cur, cur_tokens, ordinal
        if not cur:
            return
        text = "\n\n".join(u.text for u in cur)
        chunks.append(
            Chunk(
                doc_id=meta.doc_id,
                chunk_id=f"{meta.doc_id}:{ordinal}",
                ordinal=ordinal,
                text=text,
                page_start=min(u.page for u in cur),
                page_end=max(u.page for u in cur),
                n_tokens=count_tokens(text),
            )
        )
        ordinal += 1

    for u in norm:
        ut = count_tokens(u.text)
        if cur and cur_tokens + ut > max_tokens:
            flush()
            # Build overlap tail from the end of the just-flushed chunk.
            tail: list[_Unit] = []
            t = 0
            for prev in reversed(cur):
                pt = count_tokens(prev.text)
                if t + pt > overlap_tokens:
                    break
                tail.insert(0, prev)
                t += pt
            cur = tail
            cur_tokens = t
        cur.append(u)
        cur_tokens += ut

    flush()
    return chunks
