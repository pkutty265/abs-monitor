"""Ford Credit Auto Owner Trust — 'Monthly Investor Report' (EX-99, HTML).

Labels verified against the real 2024-D exhibit (tests/fixtures/fcaot2024-d10xdinvestorrep.htm).
Delinquency rows read "31-60 Days Delinquent <pct> % <count> $<balance>", hence nth=2;
the loss table puts a receivable count before the dollar column, hence nth=1 there.
"""
from typing import Iterable

from .base import LabelMapParser, FieldSpec, ParseResult


class FordAutoParser(LabelMapParser):
    specs = [
        # "Pool Balance $ <begin> $ <end>" under Pool Information.
        FieldSpec("pool_balance_begin", [r"^pool balance \$"], nth=0),
        FieldSpec("pool_balance_end",   [r"^pool balance \$"], nth=1),
        FieldSpec("pool_factor",        [r"^pool factor"], nth=1, kind="ratio"),
        FieldSpec("receivables_count_end", [r"number of receivables outstanding", r"number of receivables"], nth=1, kind="count"),
        FieldSpec("collections_total",  [r"^collections \$"]),
        # Principal bucket subtotal (scheduled + prepayments + liquidation proceeds + recoveries),
        # so that collections_principal + collections_interest == collections_total.
        FieldSpec("collections_principal", [r"^sub total"], section=r"^principal:"),
        FieldSpec("collections_interest",  [r"^interest collections"]),
        FieldSpec("gross_losses_period", [r"realized loss \(charge-?offs\)"], nth=1, section=r"current collection period loss"),
        FieldSpec("recoveries_period",   [r"\(recoveries\)", r"recoveries"], nth=1, section=r"current collection period loss"),
        FieldSpec("net_losses_period",   [r"net loss for current collection period"], section=r"current collection period loss"),
        FieldSpec("cum_net_losses",      [r"cumulative net loss for all collection periods"]),
        FieldSpec("cum_net_loss_ratio",  [r"ratio of cumulative net loss"], kind="ratio"),
        FieldSpec("delinq_31_60",  [r"31\s*[-–]\s*60 days delinquent"], nth=2),
        FieldSpec("delinq_61_90",  [r"61\s*[-–]\s*90 days delinquent"], nth=2),
        # Ford splits 91-120 and Over 120 into separate rows with real balances in both;
        # parse() sums them into delinq_91_plus below.
        FieldSpec("delinq_91_120",  [r"91\s*[-–]\s*120 days delinquent"], nth=2),
        FieldSpec("delinq_over_120", [r"over 120 days delinquent"], nth=2),
        FieldSpec("delinq_total_ratio", [r"total delinquent receivables"], kind="ratio"),
        FieldSpec("reserve_account_balance", [r"ending reserve account balance"]),
        # "Total $ <begin bal> <begin factor> $ <end bal> <end factor>" in the note balance table.
        FieldSpec("note_balance_total", [r"^total"], nth=2, section=r"balance note factor"),
        FieldSpec("servicing_fee", [r"^servicing fee"]),
    ]
    date_patterns = {
        "collection_period_end": r"collection period\s+(\w+ \d{4})",  # month-only, e.g. "September 2025"
        "distribution_date": r"payment date[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
    }

    def parse(self, lines: Iterable[str]) -> ParseResult:
        res = super().parse(lines)
        lo, hi = res.values.pop("delinq_91_120", None), res.values.pop("delinq_over_120", None)
        ev = [res.evidence.pop(k, "") for k in ("delinq_91_120", "delinq_over_120")]
        res.missing = [m for m in res.missing if m not in ("delinq_91_120", "delinq_over_120")]
        if lo is not None and hi is not None:
            res.values["delinq_91_plus"] = round(lo + hi, 2)
            res.evidence["delinq_91_plus"] = " + ".join(ev)
        else:
            res.missing.append("delinq_91_plus")
        return res
