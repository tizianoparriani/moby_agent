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


# Prepositions / honorifics stripped when extracting names. Note: "e" is intentionally
# absent — it acts as a conjunction between co-witnesses and must be kept.
_HONORIFICS = frozenset({
    "del", "dell", "della", "dei", "degli", "di",
    "dottor", "dottoressa", "dr", "dr.",
    "professor", "professoressa", "prof", "prof.",
    "generale", "ammiraglio", "prefetto", "comandante", "capitano",
    "tenente", "ten", "ten.", "colonnello", "col", "col.", "vice", "fregata",
    "ingegnere", "ingegner", "ing", "ing.",
    "avvocato", "avv", "avv.",
    "ministro", "viceministro", "onorevole", "on", "on.",
    "direttore", "vicedirettore", "dirigente",
    "già", "ex",
})

# Capitalized words that look like names but are actually institutions/roles.
_ROLE_NOUNS = frozenset({
    # Personal roles
    "Presidente", "Vicepresidente", "Senatore", "Senatori", "Deputato",
    "Onorevole", "Ministro", "Viceministro", "Generale", "Ammiraglio",
    "Prefetto", "Capitano", "Comandante", "Procuratore", "Magistrato",
    "Direttore", "Vicedirettore", "Dirigente", "Responsabile",
    # Institutions and departments
    "Commissione", "Associazione", "Istituto", "Fondazione", "Agenzia",
    "Direzione", "Servizio", "Servizi", "Ufficio", "Settore", "Autorità",
    "Sicurezza", "Ambiente", "Portuale", "Tribunale", "Procura",
    "Camera", "Senato", "Repubblica", "Governo", "Ministero",
    "Moby", "Prince", "Parlamentare", "Legislatura", "Inchiesta",
    # Generic Italian nouns often capitalized in organization/group names
    "Familiari", "Vittime", "Superstiti", "Equipaggio", "Onlus",
})

# Match the index entry that names who was heard.
# dell?[aio]? matches del/dell/della/dello without requiring a space before the next
# word, so "DELL’INGEGNER" (no gap after the apostrophe) is handled correctly.
_AUDIZIONE_LINE = re.compile(
    r"\bAudizione\s+(?:di|dell?[aio]?|dei|degli)\s*(.+)",
)
_AUDIZIONE_LINE_CI = re.compile(
    r"\bAudizione\s+(?:di|dell?[aio]?|dei|degli)\s*(.+)",
    re.IGNORECASE,
)


def _clean_name(raw: str) -> str:
    """Strip honorifics, prepositions, and role/institution words; keep name words."""
    words = raw.strip().split()
    keep = []
    for w in words:
        base = w.lower().rstrip(".,\"':;'«»")
        if base in _HONORIFICS:
            continue
        if w.rstrip(".,\":;'«»").title() in _ROLE_NOUNS:
            continue
        if w == "e" or w == "ed" or (w and w[0].isupper()):
            keep.append(w.rstrip(".,\":;'«»"))
    return " ".join(keep).strip()


def _first_name_cluster(raw: str) -> str:
    """Take the leading run of title-case words (up to 4) — stops at a lowercase word."""
    words = raw.strip().split()
    cluster: list[str] = []
    for w in words:
        if w.lower().rstrip(".,") in _HONORIFICS:
            continue
        if w and w[0].isupper():
            cluster.append(w.rstrip(".,\":;'«»"))
            if len(cluster) >= 4:
                break
        elif cluster:  # lowercase word after building a cluster → stop
            break
    return " ".join(cluster)


_ROMAN_NUM = re.compile(r"^[IVXLCDM]{2,}$")


def _is_person_name(candidate: str) -> bool:
    """True when candidate looks like 2–5 proper names with no role/institution nouns."""
    name_words = [w for w in candidate.split() if w not in ("e", "ed")]
    if not (2 <= len(name_words) <= 5):
        return False
    if any(w.title() in _ROLE_NOUNS for w in name_words):
        return False
    if any("." in w for w in name_words):  # entity abbreviations: S.p.A., s.r.l.
        return False
    if any(_ROMAN_NUM.match(w) for w in name_words):  # session ordinals: VII, IX
        return False
    return all(w[0].isupper() for w in name_words if w)


def _title_case_name(name: str) -> str:
    """Normalize ALL-CAPS names to title case."""
    return name.title() if name.isupper() else name


def _extract_witness(text: str) -> str | None:
    """Return the best witness-name string found in the first-page text, or None."""
    def _from_match(m: re.Match) -> str | None:
        raw_line = m.group(1)
        rest = text[m.end():]
        # After the match (.+ stops at \n), rest starts with "\n", so [0] is always
        # an empty string. We need [1] to get the actual continuation line.
        parts_after = rest.split("\n")
        next_line = parts_after[1].strip() if len(parts_after) > 1 else ""
        raw = raw_line + (" " + next_line if next_line else "")
        parts = raw.split(",", 1)
        before = parts[0].strip()
        after = parts[1].strip() if len(parts) > 1 else ""

        c = _clean_name(before)
        if _is_person_name(c):
            return _title_case_name(c)
        if after:
            c = _first_name_cluster(after)
            if _is_person_name(c):
                return _title_case_name(c)
        return None

    # Pass 1: mixed-case matches (index section — highest quality, iterate all).
    for m in _AUDIZIONE_LINE.finditer(text):
        result = _from_match(m)
        if result:
            return result

    # Pass 2: ALL-CAPS matches only (title block on page 0).
    for m in _AUDIZIONE_LINE_CI.finditer(text):
        if text[m.start():m.start() + 9].isupper():  # confirm ALL CAPS
            result = _from_match(m)
            if result:
                return result

    return None


def enrich_title_from_text(first_page_text: str, meta: DocMeta) -> DocMeta:
    """Return a new DocMeta with an improved title if a witness name can be found."""
    witness = _extract_witness(first_page_text)
    if not witness:
        return meta
    return DocMeta(
        doc_id=meta.doc_id,
        filename=meta.filename,
        title=f"Audizione di {witness}",
        act_type=meta.act_type or "audizione",
        date=meta.date,
    )


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
