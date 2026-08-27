"""Text extraction + generic label-map parser.

Strategy: convert the exhibit (HTML or PDF) to lines of text, then for each canonical field
search a list of issuer-specific regex label patterns and take the first numeric token that
follows the label on the same line (optionally the Nth number, to handle
"Beginning / Ending" multi-column rows). This is deliberately dumb and transparent: every
extracted value can be traced to a line of source text, which matters for auditability.
"""
from __future__ import annotations
import io
import re
from dataclasses import dataclass, field
from typing import Iterable

from bs4 import BeautifulSoup

NUM_RE = re.compile(r"\(?-?\$?\s?\d[\d,]*\.?\d*\s?%?\)?")


@dataclass
class FieldSpec:
    """How to find one canonical field in one issuer's report."""
    field: str
    labels: list[str]            # regex patterns, tried in order (case-insensitive)
    nth: int = 0                 # which number after the label (0=first)
    kind: str = "money"          # money | count | ratio | pct  (pct => divide by 100)
    section: str | None = None   # optional regex; only search lines after this heading


@dataclass
class ParseResult:
    values: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)   # field -> source line
    missing: list = field(default_factory=list)


# ---------- text extraction ----------

def html_to_lines(raw: bytes) -> list[str]:
    soup = BeautifulSoup(raw, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    # Emit table rows as single lines with cells tab-joined; this keeps label+value together.
    lines: list[str] = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append("\t".join(cells))
        tr.decompose()
    lines.extend(l.strip() for l in soup.get_text("\n").splitlines() if l.strip())
    return [re.sub(r"\s+", " ", l.replace("\xa0", " ")) for l in lines]


def pdf_to_lines(raw: bytes) -> list[str]:
    import pdfplumber
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            # Try table extraction first; rows keep label/value adjacency better than raw text.
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [str(c).strip() for c in row if c and str(c).strip()]
                    if cells:
                        lines.append("\t".join(cells))
            txt = page.extract_text(layout=True) or ""
            lines.extend(l.strip() for l in txt.splitlines() if l.strip())
    return [re.sub(r"\s+", " ", l) for l in lines]


def to_lines(raw: bytes, filename: str) -> tuple[list[str], str]:
    head = raw[:8].lower()
    if head.startswith(b"%pdf") or filename.lower().endswith(".pdf"):
        return pdf_to_lines(raw), "pdf"
    return html_to_lines(raw), "html"


# ---------- number parsing ----------

def parse_number(tok: str, kind: str = "money") -> float | None:
    s = tok.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").replace(" ", "")
    is_pct = s.endswith("%")
    s = s.rstrip("%")
    if s in ("", "-", "."):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if neg:
        v = -v
    if kind == "pct" or (kind == "ratio" and is_pct):
        v = v / 100.0
    return v


def numbers_in(line: str) -> list[str]:
    toks = []
    for m in NUM_RE.finditer(line):
        t = m.group(0)
        # Drop bare footnote markers / column indices like "(1)" and lone years-ish ints inside labels.
        if not re.search(r"\d", t) or re.fullmatch(r"\(\d\)", t.strip()):
            continue
        # Drop cross-references to other line items, not values: "(Ln 76 - Ln 77)", "(Ln1 - Ln2)".
        if re.search(r"\b(?:ln|line)\s*$", line[: m.start()], re.I):
            continue
        # Same for lettered item references like "(17d + 18d)" or "(Ln 74e / Ln 5)".
        if m.end() < len(line) and line[m.end()].isalpha():
            continue
        toks.append(t)
    return toks


# ---------- label-map parser ----------

class LabelMapParser:
    specs: list[FieldSpec] = []
    date_patterns: dict[str, str] = {
        "collection_period_end": r"(?:collection|monthly)\s+period.*?(?:through|to|-|–|ending)\s*(\w+ \d{1,2},? \d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
        "distribution_date": r"(?:distribution|payment)\s+date[:\s]+(\w+ \d{1,2},? \d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
    }

    def parse(self, lines: Iterable[str]) -> ParseResult:
        lines = list(lines)
        res = ParseResult()
        for spec in self.specs:
            hit = self._find(lines, spec)
            if hit is None:
                res.missing.append(spec.field)
            else:
                res.values[spec.field], res.evidence[spec.field] = hit
        for name, pat in self.date_patterns.items():
            for l in lines[:80]:  # dates live in the header
                m = re.search(pat, l, re.I)
                if m:
                    res.values[name] = m.group(1)
                    break
        return res

    def _find(self, lines: list[str], spec: FieldSpec):
        start = 0
        if spec.section:
            for i, l in enumerate(lines):
                if re.search(spec.section, l, re.I):
                    start = i
                    break
        for pat in spec.labels:
            rx = re.compile(pat, re.I)
            for l in lines[start:]:
                m = rx.search(l)
                if not m:
                    continue
                nums = numbers_in(l[m.end():])
                if len(nums) > spec.nth:
                    v = parse_number(nums[spec.nth], spec.kind)
                    if v is not None:
                        return v, l
        return None
