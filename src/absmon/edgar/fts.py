"""Resolve an ABS trust name to a CIK via EDGAR full-text search (efts.sec.gov)."""
from __future__ import annotations
from urllib.parse import quote

from .client import EdgarClient

FTS = "https://efts.sec.gov/LATEST/search-index?q={q}&forms=10-D"


def resolve_cik(client: EdgarClient, trust_name: str) -> int | None:
    """Best-effort: exact-phrase search on 10-D filings, return the CIK whose display name
    matches the trust name most closely. Returns None if nothing plausible is found.
    """
    data = client.get_json(FTS.format(q=quote(f'"{trust_name}"')))
    target = trust_name.lower().replace(",", "")
    for hit in data.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        names = [n.lower() for n in src.get("display_names", [])]
        ciks = src.get("ciks", [])
        for n, c in zip(names, ciks):
            if target in n:
                return int(c)
    return None
