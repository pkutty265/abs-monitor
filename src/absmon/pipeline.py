"""End-to-end: trusts.yaml -> 10-D filings -> servicer exhibits -> one DataFrame."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import yaml
from dateutil.relativedelta import relativedelta

from absmon import schema
from absmon.edgar.client import EdgarClient
from absmon.edgar.submissions import list_filings
from absmon.edgar.filing_index import list_documents, pick_servicer_report, fetch_document
from absmon.edgar.fts import resolve_cik
from absmon.parsers.base import to_lines
from absmon.parsers.registry import get_parser

log = logging.getLogger(__name__)


@dataclass
class Trust:
    name: str
    cik: int | None
    issuer: str
    asset_class: str
    parser: str


def load_trusts(path: str | Path = "config/trusts.yaml") -> list[Trust]:
    cfg = yaml.safe_load(Path(path).read_text())
    return [Trust(**t) for t in cfg["trusts"]]


def ingest_trust(client: EdgarClient, trust: Trust, since: date) -> tuple[list[dict], list[dict]]:
    """Returns (rows, evidence_rows) for one trust."""
    if trust.cik is None:
        trust.cik = resolve_cik(client, trust.name)
        if trust.cik is None:
            log.error("Could not resolve CIK for %s; skipping", trust.name)
            return [], []
        log.info("Resolved %s -> CIK %s", trust.name, trust.cik)

    filings = list_filings(client, trust.cik, form="10-D", since=since)
    log.info("%s: %d 10-D filings since %s", trust.name, len(filings), since)
    parser = get_parser(trust.parser)
    rows, evidence = [], []

    for f in filings.itertuples(index=False):
        docs = list_documents(client, trust.cik, f.accession)
        doc = pick_servicer_report(docs)
        if doc is None:
            # Fall back to the primary 10-D document (some filers inline the report).
            prim = docs[docs["filename"] == f.primary_document]
            if prim.empty:
                log.warning("%s %s: no EX-99 and no primary doc found", trust.name, f.accession)
                continue
            doc = prim.iloc[0]
        raw = fetch_document(client, trust.cik, f.accession, doc)
        lines, fmt = to_lines(raw, doc["filename"])
        res = parser.parse(lines)

        row = {
            "trust_name": trust.name, "cik": trust.cik, "issuer": trust.issuer,
            "asset_class": trust.asset_class, "accession": f.accession,
            "filing_date": f.filing_date, "report_date": f.report_date,
            "exhibit_filename": doc["filename"], "exhibit_format": fmt, "parser": trust.parser,
        }
        row.update(res.values)
        rows.append(row)
        for k, line in res.evidence.items():
            evidence.append({"trust_name": trust.name, "accession": f.accession, "field": k, "source_line": line})
        if res.missing:
            log.debug("%s %s missing: %s", trust.name, f.accession, res.missing)
    return rows, evidence


def ingest(trusts: list[Trust], months: int = 24, client: EdgarClient | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    client = client or EdgarClient()
    since = date.today() - relativedelta(months=months)
    all_rows, all_ev = [], []
    for t in trusts:
        try:
            r, e = ingest_trust(client, t, since)
            all_rows += r
            all_ev += e
        except Exception:  # keep going; one bad trust shouldn't kill the run
            log.exception("Failed on %s", t.name)

    df = pd.DataFrame(all_rows)
    for c in schema.ALL_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[schema.ALL_COLUMNS]
    for c in ("collection_period_end", "distribution_date"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in schema.METRIC_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values(["trust_name", "report_date"]).reset_index(drop=True)
    return df, pd.DataFrame(all_ev)


def coverage_report(df: pd.DataFrame) -> pd.DataFrame:
    """% of filings per trust where each metric was extracted. Use this to tune label maps."""
    if df.empty:
        return df
    return (df.groupby("trust_name")[schema.METRIC_COLUMNS]
              .apply(lambda g: g.notna().mean().round(2)).T)


def sanity_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Cheap cross-checks that catch mis-parsed rows (wrong column, unit, or label)."""
    out = df[["trust_name", "accession", "report_date"]].copy()
    out["pool_declines"] = df["pool_balance_end"] <= df["pool_balance_begin"]
    out["factor_in_range"] = df["pool_factor"].between(0, 1.0001)
    out["cnl_monotone"] = (df.sort_values("report_date").groupby("trust_name")["cum_net_losses"]
                             .diff().fillna(0) >= -1e-6).reindex(df.index)
    out["ratio_sane"] = df["cum_net_loss_ratio"].between(0, 0.5) | df["cum_net_loss_ratio"].isna()
    return out
