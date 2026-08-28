# abs-monitor

Consumer ABS surveillance pipeline: pull servicer reports from EDGAR (and, later,
issuer websites), normalize key performance fields into a single long-format
dataset, and build monitoring/analytics on top.

## Decisions & findings

I originally wanted private student loan ABS (SMB Private Education Loan Trust, Navient
refi) in the universe, but those deals are 144A and file no 10-Ds on EDGAR. The two
student loan slots are therefore Navient FFELP shelves, which do file. The private SL
gap stays open; the next data push is loan-level ABS-EE (EX-102) ingestion for the
auto trusts instead.

On all five trusts, the untuned label-map parsers produced plausible-but-wrong values
rather than blanks: line-reference numbers parsed as values (CarMax's "Ln 76" style,
Santander's "{9}" markers), weighted-average coupons grabbed instead of dollar balances,
prior-month columns instead of current, and at-issuance figures instead of period ones.
What caught this was never the coverage table — it was the evidence CSV tracing every
extracted value to its source line, plus arithmetic identity checks: principal + interest
= total collections, cumulative loss diffs = period losses, begin balance = prior end
balance.

delinq_91_plus needs a per-issuer judgment because charge-off timing differs. CarMax and
Santander charge off at 120 days, so their 121+ buckets are always zero and the 91-120
bucket stands in for 91+. Ford and Navient carry real balances past 120 days, so their
91-120 and over-120 rows are summed.

FFELP loss fields are deliberately mapped differently from auto because federal guarantors
absorb ~98% of defaults. Gross losses and recoveries stay unmapped — the reports don't
publish them, and post-claim recoveries belong to the guarantor. The meaningful fields are
guarantor claims paid (claims_paid_period) and the uninsured risk-share remainder
(net_losses_period / cum_net_losses), which run at roughly 0.5% of original pool after a
decade.

## Proposed repo structure

```
abs-monitor/
├── README.md
├── pyproject.toml
├── config/
│   └── trusts.yaml            # trust universe: CIK, issuer/shelf, asset class, parser key
├── src/absmon/
│   ├── __init__.py
│   ├── settings.py            # user-agent, paths, rate limits (env-driven)
│   ├── edgar/
│   │   ├── client.py          # rate-limited SEC HTTP session w/ disk cache
│   │   ├── submissions.py     # list filings by CIK (submissions API, paginated)
│   │   ├── filing_index.py    # resolve exhibits inside an accession folder
│   │   └── fts.py             # full-text-search helper to resolve trust name -> CIK
│   ├── parsers/
│   │   ├── base.py            # text extraction (HTML/PDF), number parsing, label-map parser
│   │   ├── registry.py        # parser_key -> parser class
│   │   ├── ford_auto.py       # issuer-specific label maps
│   │   ├── carmax_auto.py
│   │   ├── santander_drive.py
│   │   └── navient_ffelp.py
│   ├── schema.py              # canonical field list + dtypes
│   └── pipeline.py            # ingest(trusts, months) -> DataFrame (+parse coverage report)
├── scripts/
│   └── ingest_10d.py          # CLI entry: python scripts/ingest_10d.py --months 24
├── tests/
│   ├── fixtures/              # one saved exhibit per issuer (commit these!)
│   └── test_parsers.py
└── data/                      # gitignored
    ├── raw/                   # cached filings/exhibits (edgar/{cik}/{accession}/...)
    └── parsed/                # parquet outputs
```

Phase roadmap (proposed, revise as needed):
- **Phase 1 (this):** EDGAR 10-D ingestion, 5 trusts, label-map parsers, one DataFrame.
- **Phase 1b:** Reg AB II asset-level data (Form ABS-EE, EX-102 XML) for the auto
  trusts — fully structured, no label-guessing, enables loan-level roll rates
  (`scripts/ingest_absee.py`, one parquet per filing under `data/parsed/absee/`).
- **Deferred:** issuer-website adapter for private student loan ABS (144A, no 10-Ds).
- **Phase 2:** Normalization/QA (cross-checks, restatement handling), storage (parquet/duckdb).
- **Phase 3:** Analytics — CNL curves vs. vintage, delinquency roll rates, trigger proximity.
- **Phase 4:** Alerts / dashboard.

## Quickstart

```bash
pip install -e .
export SEC_USER_AGENT="Your Name your@email.com"   # SEC requires a real contact UA
python scripts/ingest_10d.py --months 24 --out data/parsed/servicer_reports.parquet
```

The first run prints a **parse-coverage report** (which canonical fields matched for
each trust). Expect gaps on the first pass: the label maps in `src/absmon/parsers/*.py`
are best-effort and must be tuned against the actual exhibit text, which is saved under
`data/raw/` for exactly this purpose.

Claude Code was used as a pair programmer throughout this project.
