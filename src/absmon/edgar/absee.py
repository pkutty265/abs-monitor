"""Form ABS-EE loan-level ingestion: EX-102 asset-data XML for auto trusts.

Tag names verified against a real CarMax 2024-1 EX-102 (accession 0002003263-26-000040,
July 2026 period, 243MB / 81,504 records) in the SEC auto-loan ABS-EE taxonomy
(xmlns http://www.sec.gov/edgar/document/absee/autoloan/assetdata): one <assets>
element per loan. Files keep reporting loans after payoff/charge-off — zeroBalanceCode
(1=prepaid/matured, 2=third-party sale, 3=repurchased, 4=charged-off) marks closed
loans, and applicability-gated tags (chargedoffPrincipalAmount, recoveredAmount,
remainingTermToMaturityNumber, ...) are simply absent when not relevant, so every
column here must tolerate missing tags.

Files run to hundreds of MB, so parse_ex102 streams via iterparse — never a full DOM.
"""
from __future__ import annotations
import io
import logging
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

from .client import EdgarClient
from .submissions import list_filings
from .filing_index import list_documents, fetch_document

# EX-102 tag -> output column. Focused surveillance set, not the full ~70-tag schema.
FIELD_MAP = {
    "assetNumber": "asset_id",
    "reportingPeriodEndingDate": "period_end",
    "reportingPeriodBeginningLoanBalanceAmount": "balance_begin",
    "reportingPeriodActualEndBalanceAmount": "balance_end",
    "originalLoanAmount": "original_balance",
    "reportingPeriodInterestRatePercentage": "interest_rate",
    "originalLoanTerm": "original_term",
    "remainingTermToMaturityNumber": "remaining_term",
    "currentDelinquencyStatus": "delinq_days",
    "zeroBalanceCode": "zero_balance_code",
    "chargedoffPrincipalAmount": "chargeoff_amount",
    "recoveredAmount": "recovery_amount",
    "reportingPeriodModificationIndicator": "modified",
    "modificationTypeCode": "modification_type",
    "vehicleNewUsedCode": "vehicle_new_used",
}
FLOAT_COLS = ["balance_begin", "balance_end", "original_balance", "interest_rate",
              "chargeoff_amount", "recovery_amount"]
INT_COLS = ["original_term", "remaining_term", "delinq_days", "vehicle_new_used"]
CHARGED_OFF_CODE = "4"


def list_absee_filings(client: EdgarClient, cik: int, since: date | None = None) -> pd.DataFrame:
    return list_filings(client, cik, form="ABS-EE", since=since)


def fetch_ex102(client: EdgarClient, cik: int, accession: str) -> Path:
    """Download the EX-102 exhibit of one ABS-EE filing into the disk cache and return
    its local path (these files are too large to pass around as bytes)."""
    docs = list_documents(client, cik, accession)
    ex = docs[docs["type"] == "EX-102"]
    if ex.empty:
        raise FileNotFoundError(f"no EX-102 in ABS-EE accession {accession}")
    doc = ex.iloc[0]
    fetch_document(client, cik, accession, doc)
    return client.cache_dir / "edgar" / str(cik) / accession.replace("-", "") / doc["filename"]


def parse_ex102(source: Path | str | bytes) -> pd.DataFrame:
    """Stream one EX-102 XML into a loan-level DataFrame (one row per <assets> record)."""
    stream = io.BytesIO(source) if isinstance(source, bytes) else str(source)
    rows = []
    for _, el in ET.iterparse(stream, events=("end",)):
        if el.tag.rsplit("}", 1)[-1] != "assets":
            continue
        row = {}
        for child in el:
            col = FIELD_MAP.get(child.tag.rsplit("}", 1)[-1])
            if col and child.text and child.text.strip():
                row[col] = child.text.strip()
        rows.append(row)
        el.clear()  # keep memory flat on multi-hundred-MB files

    df = pd.DataFrame(rows, columns=list(FIELD_MAP.values()))
    df["period_end"] = pd.to_datetime(df["period_end"], format="%m-%d-%Y", errors="coerce")
    for c in FLOAT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in INT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df["modified"] = df["modified"].map({"true": True, "false": False}).astype("boolean")
    # "ever" = the loan left the pool via charge-off (any period). "this_period" must check
    # > 0, not just presence: CarMax/Ford omit chargedoffPrincipalAmount unless applicable,
    # but Santander prints it as an explicit 0.00 on most rows (open or closed) — treating
    # notna() as the signal there would flag tens of thousands of untouched loans.
    df["charged_off_ever"] = df["zero_balance_code"] == CHARGED_OFF_CODE
    df["charged_off_this_period"] = df["chargeoff_amount"].fillna(0) > 0
    return df


def ingest_absee_trust(client: EdgarClient, cik: int, trust_slug: str, months: int = 24,
                       out_root: Path = Path("data/parsed/absee")) -> pd.DataFrame:
    """Download and parse every ABS-EE EX-102 for one trust in the window, writing one
    parquet per filing to {out_root}/{trust_slug}/{YYYY-MM}.parquet (actives and closed
    loans both included; filter on zero_balance_code downstream).

    Each raw XML is DELETED from the disk cache once its parquet is written: the XML
    cache would be 15-20GB of iCloud sync traffic, the parquet is the durable artifact,
    and any month can be re-fetched from EDGAR. Existing parquets are skipped without
    re-downloading, so interrupted runs resume cheaply. Returns a per-filing summary.
    """
    from dateutil.relativedelta import relativedelta

    since = date.today() - relativedelta(months=months)
    filings = list_absee_filings(client, cik, since=since)
    out_dir = out_root / trust_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for f in filings.itertuples(index=False):
        period = (pd.Timestamp(f.report_date).strftime("%Y-%m") if pd.notna(f.report_date)
                  else f.accession)
        out = out_dir / f"{period}.parquet"
        if out.exists():
            summary.append({"trust": trust_slug, "period": period, "accession": f.accession,
                            "status": "cached", "rows": None})
            continue
        try:
            xml_path = fetch_ex102(client, cik, f.accession)
        except FileNotFoundError as e:
            log.warning("%s %s: %s", trust_slug, f.accession, e)
            summary.append({"trust": trust_slug, "period": period, "accession": f.accession,
                            "status": "no-ex102", "rows": None})
            continue
        xml_mb = xml_path.stat().st_size / 1e6
        df = parse_ex102(xml_path)
        df.insert(0, "accession", f.accession)
        df.insert(0, "trust", trust_slug)
        df.to_parquet(out, index=False)
        xml_path.unlink()  # only after a successful parquet write
        log.info("%s %s -> %s (%d rows, %.1f MB xml deleted)",
                 trust_slug, f.accession, out.name, len(df), xml_mb)
        summary.append({"trust": trust_slug, "period": period, "accession": f.accession,
                        "status": "parsed", "rows": len(df)})
    return pd.DataFrame(summary)
