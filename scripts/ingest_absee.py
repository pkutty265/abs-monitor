#!/usr/bin/env python
"""Pull ABS-EE EX-102 loan-level data for the auto trusts; one parquet per filing.

Usage:
  export SEC_USER_AGENT="Your Name your@email.com"
  python scripts/ingest_absee.py --months 24

Raw XMLs (150-250MB each) are deleted from the cache after each parquet is written;
existing parquets are skipped, so re-running resumes an interrupted pull.
"""
from __future__ import annotations
import argparse
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from absmon.edgar.client import EdgarClient  # noqa: E402
from absmon.edgar.absee import ingest_absee_trust  # noqa: E402
from absmon.pipeline import load_trusts  # noqa: E402


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "_", name.lower()).strip("_")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/trusts.yaml")
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--out", default="data/parsed/absee")
    ap.add_argument("--only", nargs="*", help="substring filter on trust name")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    trusts = [t for t in load_trusts(args.config) if t.asset_class.startswith("auto")]
    if args.only:
        trusts = [t for t in trusts if any(s.lower() in t.name.lower() for s in args.only)]

    client = EdgarClient()
    summaries = []
    for t in trusts:
        try:
            summaries.append(ingest_absee_trust(client, t.cik, slugify(t.name),
                                                months=args.months, out_root=Path(args.out)))
        except Exception:  # keep going; one bad trust shouldn't kill the run
            logging.exception("Failed on %s", t.name)

    if summaries:
        s = pd.concat(summaries, ignore_index=True)
        print("\n=== ABS-EE ingest summary ===")
        print(s.groupby(["trust", "status"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
