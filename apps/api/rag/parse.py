"""PDF -> per-page normalized text.

Text-first: extract the embedded text layer with PyMuPDF. If a page yields
fewer than ``ocr_min_chars`` characters it is treated as scanned and, when
OCR is available, rendered to an image and passed through Tesseract (Italian).

OCR deps (pytesseract + the tesseract-ocr-ita binary) are imported lazily, so
the pipeline runs on corpora that don't need OCR without those installed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class Page:
    page_no: int  # 1-based
    text: str
    ocr: bool  # True if text came from OCR


def _normalize(text: str) -> str:
    # De-hyphenate words split across line breaks: "respon-\nsabilità" -> "responsabilità"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Collapse intra-line runs of spaces/tabs.
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines to a paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trim trailing spaces on each line.
    text = re.sub(r" +\n", "\n", text)
    return text.strip()


def _ocr_page(page: "fitz.Page") -> str:
    """Render a page to an image and OCR it in Italian. Raises if OCR unavailable."""
    import pytesseract  # lazy
    from PIL import Image  # lazy
    import io

    pix = page.get_pixmap(dpi=300)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="ita")


def parse_pdf(path: str, ocr_min_chars: int = 200, allow_ocr: bool = True) -> list[Page]:
    """Return one Page per PDF page with normalized text."""
    pages: list[Page] = []
    doc = fitz.open(path)
    try:
        for i in range(doc.page_count):
            page = doc[i]
            raw = page.get_text("text")
            used_ocr = False
            if len(raw.strip()) < ocr_min_chars and allow_ocr:
                try:
                    raw = _ocr_page(page)
                    used_ocr = True
                except Exception:
                    # OCR not installed or failed: keep whatever text we had.
                    used_ocr = False
            pages.append(Page(page_no=i + 1, text=_normalize(raw), ocr=used_ocr))
    finally:
        doc.close()
    return pages
