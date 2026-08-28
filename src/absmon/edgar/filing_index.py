"""Resolve the documents inside an accession folder and pick the servicer-report exhibit."""
from __future__ import annotations
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from .client import EdgarClient

ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/"


def accession_nodash(acc: str) -> str:
    return acc.replace("-", "")


def list_documents(client: EdgarClient, cik: int, accession: str) -> pd.DataFrame:
    """Parse the `<accession>-index.htm` page: Seq / Description / Document / Type / Size."""
    acc_nd = accession_nodash(accession)
    url = ARCHIVE.format(cik=cik, acc_nodash=acc_nd) + f"{accession}-index.htm"
    html = client.get_bytes(url, Path("edgar") / str(cik) / acc_nd / "index.htm")
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for table in soup.find_all("table", class_="tableFile"):
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            a = tds[2].find("a")
            href = a["href"] if a else ""
            # iXBRL viewer links look like /ix?doc=/Archives/...; unwrap them.
            m = re.search(r"doc=(/Archives/[^&]+)", href)
            if m:
                href = m.group(1)
            filename = href.rsplit("/", 1)[-1]
            # Multi-filer submissions (trust + depositor) embed the *depositor's* CIK in the
            # index page hrefs, and those paths can 404; the same file always resolves under
            # the CIK we queried, so rebuild the URL from it instead of trusting the href.
            rows.append({
                "seq": tds[0].get_text(strip=True),
                "description": tds[1].get_text(" ", strip=True),
                "filename": filename,
                "url": ARCHIVE.format(cik=cik, acc_nodash=acc_nd) + filename,
                "type": tds[3].get_text(strip=True).upper(),
                "size": tds[4].get_text(strip=True),
            })
    return pd.DataFrame(rows)


def pick_servicer_report(docs: pd.DataFrame) -> pd.Series | None:
    """Heuristic: the servicer/investor report is the EX-99* exhibit (prefer the largest one).

    Filers vary: EX-99, EX-99.1, EX-99.A. Some embed the report in the primary 10-D document
    itself (no exhibit) — caller should fall back to the primary doc in that case.
    """
    if docs.empty:
        return None
    ex = docs[docs["type"].str.startswith("EX-99")].copy()
    if ex.empty:
        return None
    ex["size_n"] = pd.to_numeric(ex["size"], errors="coerce").fillna(0)
    return ex.sort_values("size_n", ascending=False).iloc[0]


def fetch_document(client: EdgarClient, cik: int, accession: str, doc: pd.Series) -> bytes:
    acc_nd = accession_nodash(accession)
    return client.get_bytes(doc["url"], Path("edgar") / str(cik) / acc_nd / doc["filename"])
