"""Santander Drive Auto Receivables Trust — 'Servicer's Certificate' (EX-99.1, HTML).

Labels verified against the real 2024-1 exhibits (tests/fixtures/d121531dex991.htm).
Every line item carries {N} cross-reference markers on both sides of the label
("{9} Pool Factor ({8}/ Original Pool Balance) {9} 0.361318") which parse as bare
integers, so parse() strips them before matching. Delinquency rows read
"<units> <dollars> <pct>", hence nth=1; Statistical Data rows read
"<original> <previous> <current>", hence nth=2.
"""
import re
from typing import Iterable

from .base import LabelMapParser, FieldSpec, ParseResult, numbers_in, parse_number

REF_RE = re.compile(r"\{[^{}]{1,6}\}")


class SantanderDriveParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"beginning of period aggregate principal balance"]),
        FieldSpec("pool_balance_end",   [r"end of period aggregate principal balance"]),
        FieldSpec("pool_factor",        [r"^pool factor"], kind="ratio"),
        FieldSpec("receivables_count_end", [r"^number of receivables"], nth=2, kind="count"),
        FieldSpec("collections_total",  [r"total available funds"]),
        FieldSpec("collections_principal", [r"principal payments received"]),
        FieldSpec("collections_interest",  [r"interest collected on receivables"]),
        # Loss-table rows are "<unit count> <dollars>", hence nth=1.
        FieldSpec("gross_losses_period", [r"receivables becoming defaulted receivables"], nth=1),
        FieldSpec("recoveries_period",   [r"liquidation proceeds collected during period"], nth=1),
        FieldSpec("net_losses_period",   [r"^net losses during period"]),
        FieldSpec("cum_net_losses",      [r"cumulative net losses since cut-?off date \(end of period\)"]),
        FieldSpec("cum_net_loss_ratio",  [r"cumulative net loss ratio"], kind="ratio"),
        FieldSpec("delinq_31_60",  [r"^31\s*[-–]\s*60 days"], nth=1),
        FieldSpec("delinq_61_90",  [r"^61\s*[-–]\s*90 days"], nth=1),
        # Receivables are charged off by 120 days past due; the 121+ row never carries a
        # dollar balance, so the 91-120 bucket stands in for 91+ (same convention as CarMax).
        FieldSpec("delinq_91_plus", [r"^91\s*[-–]\s*120 days"], nth=1),
        FieldSpec("delinq_total_ratio", [r"^total"], nth=2, kind="ratio", section=r"^vii\. delinquency"),
        FieldSpec("reserve_account_balance", [r"end of period reserve account balance"]),
        # Section II's row of the same name is per-class; section V has the single total.
        FieldSpec("note_balance_total", [r"^end of period note balance"], section=r"^v\. overcollateralization"),
    ]
    date_patterns = {
        "collection_period_end": r"collection period ending[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
        "distribution_date": r"^payment date[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
    }

    def parse(self, lines: Iterable[str]) -> ParseResult:
        lines = [re.sub(r"\s+", " ", REF_RE.sub(" ", l)).strip() for l in lines]
        res = super().parse(lines)
        # The Servicing Fee table splits label and value across lines ("Servicing Fee" /
        # "Calculated Fee Carryover Shortfall ... Total" / "<calculated> ... <total> <total>"),
        # so the same-line matcher can't see it; take the trailing Total from the value row.
        for i, l in enumerate(lines):
            if l.lower() == "servicing fee":
                for vl in lines[i + 1:i + 4]:
                    nums = numbers_in(vl)
                    if nums:
                        v = parse_number(nums[-1])
                        if v is not None:
                            res.values["servicing_fee"] = v
                            res.evidence["servicing_fee"] = f"{l} … {vl}"
                        break
                break
        if "servicing_fee" not in res.values:
            res.missing.append("servicing_fee")
        return res
