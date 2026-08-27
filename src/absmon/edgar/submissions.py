"""List filings for a CIK via the EDGAR submissions API (handles pagination files)."""
from __future__ import annotations
from datetime import date
from pathlib import Path

import pandas as pd

from .client import EdgarClient

SUBMISSIONS_URL = "https://data.sec.gov/submissions/{name}"


def _frame(recent: dict) -> pd.DataFrame:
    return pd.DataFrame({
        "accession": recent["accessionNumber"],
        "form": recent["form"],
        "filing_date": pd.to_datetime(recent["filingDate"]),
        "report_date": pd.to_datetime(recent.get("reportDate"), errors="coerce"),
        "primary_document": recent["primaryDocument"],
    })


def list_filings(client: EdgarClient, cik: int, form: str = "10-D", since: date | None = None) -> pd.DataFrame:
    """Return all filings of `form` for a CIK on/after `since`, newest first.

    Note: the submissions API only exposes ~1000 most recent filings inline; older ones live
    in `filings.files[]`. We fetch those too so 24-month windows are complete for old trusts.
    """
    cik10 = f"{int(cik):010d}"
    root = client.get_json(SUBMISSIONS_URL.format(name=f"CIK{cik10}.json"),
                           Path("submissions") / f"CIK{cik10}.json")
    frames = [_frame(root["filings"]["recent"])]
    for extra in root["filings"].get("files", []):
        # Skip pagination files entirely outside the window.
        if since and pd.to_datetime(extra["filingTo"]) < pd.Timestamp(since):
            continue
        page = client.get_json(SUBMISSIONS_URL.format(name=extra["name"]),
                               Path("submissions") / extra["name"])
        frames.append(_frame(page))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["form"] == form]
    if since:
        df = df[df["filing_date"] >= pd.Timestamp(since)]
    df = df.drop_duplicates("accession").sort_values("filing_date", ascending=False)
    df.insert(0, "cik", int(cik))
    df["entity_name"] = root.get("name")
    return df.reset_index(drop=True)
