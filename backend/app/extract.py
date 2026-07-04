"""PDF text extraction for the synthetic dataset.

The demo PDFs are clean text with `label   value` lines. We extract via pypdf
(pdftotext-style) and parse known labels into structured fields. Real scans
would need OCR; that is out of scope for the demo (see spec honest flags).
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

from pypdf import PdfReader

# label (lowercased, punctuation-insensitive) -> canonical field name
_PASSPORT_LABELS = {
    "full name": "name",
    "nationality": "nationality",
    "date of birth": "dob",
    "place of birth": "pob",
    "passport no": "passport_no",
    "passport no synthetic": "passport_no",
    "date of issue": "passport_issue",
    "date of expiry": "passport_expiry",
    "issuing authority": "issuing_authority",
    "role in entity": "role",
}
_POA_LABELS = {
    "document holder": "name",
    "residential address": "address",
    "evidence type": "poa_source",
    "document date": "poa_date",
}

_INLINE_RE = re.compile(r"^\s*(?P<label>[A-Za-z][A-Za-z .()/-]+?)\s{2,}(?P<value>\S.*?)\s*$")
_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# Known labels across the dataset, used to detect a label line when the value
# is on the following line (pypdf output puts them on separate lines).
_ALL_LABELS = {
    "full name", "nationality", "date of birth", "place of birth", "passport no",
    "passport no synthetic", "date of issue", "date of expiry", "issuing authority",
    "role in entity", "document holder", "residential address", "evidence type",
    "document date",
}


def read_text(path: str | Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", label.lower())).strip()


def parse_label_values(text: str) -> dict[str, str]:
    """Extract label->value pairs. Handles two layouts:
      (a) inline `label   value` on one line (pdftotext -layout style)
      (b) label line followed by its value line (pypdf style)."""
    out: dict[str, str] = {}
    lines = [ln.strip() for ln in text.splitlines()]

    # (a) inline pairs
    for ln in lines:
        m = _INLINE_RE.match(ln)
        if m:
            label = _norm_label(m.group("label"))
            value = m.group("value").strip()
            if label and value and label not in out:
                out[label] = value

    # (b) label-line / value-line pairs
    non_empty = [ln for ln in lines if ln]
    for i, ln in enumerate(non_empty[:-1]):
        label = _norm_label(ln)
        if label in _ALL_LABELS and label not in out:
            candidate = non_empty[i + 1].strip()
            # value must not itself be a known label
            if candidate and _norm_label(candidate) not in _ALL_LABELS:
                out[label] = candidate
    return out


def _parse_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    m = _DATE_RE.search(value)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _map(pairs: dict[str, str], labels: dict[str, str]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for raw_label, value in pairs.items():
        canon = labels.get(raw_label)
        if canon and canon not in fields:
            fields[canon] = value
    for dk in ("dob", "passport_issue", "passport_expiry", "poa_date"):
        if dk in fields:
            fields[dk] = _parse_date(fields[dk])
    return fields


def extract_fields(path: str | Path, doc_key: str) -> dict[str, Any]:
    """Return structured fields for a document. Passport (U01/U03) and PoA
    (U02/U04) get typed fields; everything else returns generic label/value."""
    text = read_text(path)
    pairs = parse_label_values(text)
    key = doc_key.upper()
    if key in {"U01", "U03"}:  # passport documents
        fields = _map(pairs, _PASSPORT_LABELS)
        fields["_kind"] = "passport"
    elif key in {"U02", "U04"}:  # proof of address
        fields = _map(pairs, _POA_LABELS)
        fields["_kind"] = "poa"
    else:
        fields = dict(pairs)
        fields["_kind"] = "generic"
        fields["_has_signature"] = bool(re.search(r"sign|signature|signed", text, re.I))
    return fields


def to_date(value: Optional[str]) -> Optional[date]:
    d = _parse_date(value)
    if not d:
        return None
    y, m, dd = d.split("-")
    return date(int(y), int(m), int(dd))
