"""Derive document metadata from the source filename.

The sample corpus encodes useful fields in the filename, e.g.:
  Sentenza-1_31.10.1998.pdf
  leg.19.stencomm.data20240409.U1.com80.audiz2.audizione.0001.pdf

We extract a stable doc_id, a human title, an act type and a date (ISO).
Anything we cannot parse is left as None rather than guessed.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass


# Act-type keywords -> normalized label. Order matters (first match wins).
_ACT_TYPES = [
    ("sentenza", "sentenza"),
    ("audizione", "audizione"),
    ("perizia", "perizia"),
    ("verbale", "verbale"),
    ("relazione", "relazione"),
    ("ordinanza", "ordinanza"),
    ("decreto", "decreto"),
    ("memoria", "memoria"),
]

# dd.mm.yyyy  /  dd-mm-yyyy  /  dd_mm_yyyy
_DATE_DMY = re.compile(r"(?<!\d)(\d{1,2})[._-](\d{1,2})[._-](\d{4})(?!\d)")
# data20240409  /  bare 20240409
_DATE_YMD = re.compile(r"(?:data)?(20\d{2})(\d{2})(\d{2})")


@dataclass
class DocMeta:
    doc_id: str
    filename: str
    title: str
    act_type: str | None
    date: str | None  # ISO yyyy-mm-dd

    def as_dict(self) -> dict:
        return asdict(self)


def _detect_act_type(name: str) -> str | None:
    low = name.lower()
    for needle, label in _ACT_TYPES:
        if needle in low:
            return label
    return None


def _detect_date(name: str) -> str | None:
    m = _DATE_DMY.search(name)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = _DATE_YMD.search(name)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _make_title(stem: str, act_type: str | None, date: str | None) -> str:
    """Best-effort readable title; falls back to the cleaned stem."""
    if act_type and date:
        return f"{act_type.capitalize()} del {date}"
    if act_type:
        return act_type.capitalize()
    # Replace separators with spaces, collapse whitespace.
    return re.sub(r"\s+", " ", re.sub(r"[._-]+", " ", stem)).strip()


def meta_from_filename(filename: str, doc_id: str | None = None) -> DocMeta:
    """Build DocMeta from a filename (path components are ignored)."""
    base = filename.rsplit("/", 1)[-1]
    stem = base[:-4] if base.lower().endswith(".pdf") else base
    act_type = _detect_act_type(stem)
    date = _detect_date(stem)
    # Stable doc_id: explicit override, else a short hash of the stem so the
    # same source file always maps to the same id (idempotent reindex).
    if doc_id is None:
        doc_id = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:16]
    return DocMeta(
        doc_id=doc_id,
        filename=base,
        title=_make_title(stem, act_type, date),
        act_type=act_type,
        date=date,
    )
