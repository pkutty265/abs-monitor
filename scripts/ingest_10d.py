#!/usr/bin/env python
"""Pull the last N months of 10-D filings for the configured trusts and parse servicer fields.

Usage:
  export SEC_USER_AGENT="Your Name your@email.com"
  python scripts/ingest_10d.py --months 24 --out data/parsed/servicer_reports.parquet
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from absmon.pipeline import load_trusts, ingest, coverage_report, sanity_checks  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/trusts.yaml")
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--out", default="data/parsed/servicer_reports.parquet")
    ap.add_argument("--only", nargs="*", help="substring filter on trust name")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    trusts = load_trusts(args.config)
    if args.only:
        trusts = [t for t in trusts if any(s.lower() in t.name.lower() for s in args.only)]

    df, evidence = ingest(trusts, months=args.months)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    df.to_csv(out.with_suffix(".csv"), index=False)
    evidence.to_csv(out.with_name(out.stem + "_evidence.csv"), index=False)

    pd.set_option("display.width", 200, "display.max_columns", 50)
    print(f"\n{len(df)} filing-rows across {df['trust_name'].nunique()} trusts -> {out}")
    print("\n=== Parse coverage (share of filings with field extracted) ===")
    print(coverage_report(df))
    checks = sanity_checks(df)
    flagged = checks[~checks[["pool_declines", "factor_in_range", "cnl_monotone", "ratio_sane"]].all(axis=1)]
    print(f"\n=== Sanity checks: {len(flagged)} rows flagged ===")
    if not flagged.empty:
        print(flagged.head(20))


if __name__ == "__main__":
    main()
