"""Navient Student Loan Trust (FFELP) — 'Monthly Servicing Report' (EX-99.1, HTML).

Labels verified against the real 2014-5 and 2015-3 exhibits (same 9-page template;
tests/fixtures/ef20078669_ex99-1.htm, ef20078676_ex99-1.htm). Column layouts differ by
section: Deal Parameters rows read "<at-issuance> <prior month> <current month>" (hence
nth=1/2), Portfolio Characteristics status rows read "<WAC%> <#loans> <$> <%>" twice with
the CURRENT month first (hence nth=2 for dollars), and section IV rows are
"<current> <prior>".

FFELP loss mechanics: no gross-default line is published. Defaults surface as Guarantor
Principal/Interest receipts (claims paid to the trust at the ~97-98% guarantee rate),
CLAIMS IN PROCESS (filed, awaiting the guarantor), and Non-Reimbursable Losses (the
uninsured risk-share remainder) — so gross_losses_period/recoveries_period stay unmapped,
net_losses_period is the risk-share loss, and claims_paid_period sums the guarantor
receipts. A '-' in a value cell means zero, never "not reported" (the template always
prints the row), so the dash-aware lookups below return 0.0 instead of skipping to a
number from the wrong column or month.
"""
import re
from typing import Iterable

from .base import LabelMapParser, FieldSpec, ParseResult, numbers_in, parse_number

DASH_ONLY = re.compile(r"[\s\-–—]*$")


class NavientFfelpParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"^pool balance \$"], nth=1),
        FieldSpec("pool_balance_end",   [r"^pool balance \$"], nth=2),
        FieldSpec("_pool_balance_orig", [r"^pool balance \$"], nth=0),
        FieldSpec("pool_factor",        [r"^pool factor"], nth=1, kind="ratio"),
        FieldSpec("receivables_count_end", [r"^number of loans"], nth=2, kind="count"),
        FieldSpec("_principal_balance_end", [r"^principal balance \$"], nth=2),
        FieldSpec("collections_total",  [r"^total available funds"]),
        FieldSpec("collections_principal", [r"^total principal receipts"]),
        FieldSpec("collections_interest",  [r"^total interest receipts"]),
        FieldSpec("cum_net_losses",      [r"^cumulative non-reimbursable losses"]),
        FieldSpec("delinq_31_60",  [r"31\s*[-–]\s*60 days delinquent"], nth=2),
        FieldSpec("delinq_61_90",  [r"61\s*[-–]\s*90 days delinquent"], nth=2),
        # Navient splits 91-120 and >120 with real balances in both; parse() sums them.
        FieldSpec("_delinq_91_120",  [r"91\s*[-–]\s*120 days delinquent"], nth=2),
        FieldSpec("_delinq_over_120", [r">\s*120 days delinquent"], nth=2),
        # 2014-5 prints "INTERIM: DEFERMENT"; 2015-3 prints bare "DEFERMENT".
        FieldSpec("deferment_balance",   [r"^(?:interim: )?deferment"], nth=2),
        FieldSpec("forbearance_balance", [r"^forbearance"], nth=2),
        FieldSpec("reserve_account_balance", [r"^ending reserve account balance"]),
        # "Total Notes $ <before distribution> $ <after distribution>".
        FieldSpec("note_balance_total", [r"^total notes \$"], nth=1),
        # Waterfall row ("B Primary Servicing Fee <paid> <remaining>"); the letter prefix
        # keeps "Unpaid Primary Servicing Fees" from matching.
        FieldSpec("servicing_fee", [r"^[a-z] primary servicing fee"]),
    ]
    date_patterns = {
        "collection_period_end": r"collection period \d{1,2}/\d{1,2}/\d{4}\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{4})",
        "distribution_date": r"distribution date[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
    }

    @staticmethod
    def _value_or_zero(lines: list[str], pattern: str) -> tuple[float, str] | None:
        """First number after the label, or 0.0 when the cell is a bare '-' placeholder."""
        rx = re.compile(pattern, re.I)
        for l in lines:
            m = rx.search(l)
            if not m:
                continue
            nums = numbers_in(l[m.end():])
            if nums:
                v = parse_number(nums[0])
                if v is not None:
                    return v, l
            if DASH_ONLY.fullmatch(l[m.end():]):
                return 0.0, l
        return None

    def parse(self, lines: Iterable[str]) -> ParseResult:
        lines = list(lines)
        res = super().parse(lines)
        v, ev = res.values, res.evidence

        def take(field):
            res.missing = [m for m in res.missing if m != field]
            return v.pop(field, None), ev.pop(field, "")

        lo, lo_ev = take("_delinq_91_120")
        hi, hi_ev = take("_delinq_over_120")
        if lo is not None and hi is not None:
            v["delinq_91_plus"] = round(lo + hi, 2)
            ev["delinq_91_plus"] = f"{lo_ev} + {hi_ev}"
        else:
            res.missing.append("delinq_91_plus")

        # Current-period risk-share loss; '-' means a zero-loss month.
        hit = self._value_or_zero(lines, r"non-reimbursable losses during collection period")
        if hit:
            v["net_losses_period"], ev["net_losses_period"] = hit
        else:
            res.missing.append("net_losses_period")

        # Guarantor claim payments received by the trust (principal + interest).
        gp = self._value_or_zero(lines, r"^guarantor principal")
        gi = self._value_or_zero(lines, r"^guarantor interest")
        if gp or gi:
            v["claims_paid_period"] = round((gp[0] if gp else 0.0) + (gi[0] if gi else 0.0), 2)
            ev["claims_paid_period"] = " + ".join(h[1] for h in (gp, gi) if h)
        else:
            res.missing.append("claims_paid_period")

        # Ratios aren't published; derive them the way the report's own %s are quoted
        # (delinquency % of current principal balance, losses % of the original pool).
        principal_end, _ = take("_principal_balance_end")
        pool_orig, _ = take("_pool_balance_orig")
        buckets = [v.get("delinq_31_60"), v.get("delinq_61_90"), v.get("delinq_91_plus")]
        if principal_end and all(b is not None for b in buckets):
            v["delinq_total_ratio"] = round(sum(buckets) / principal_end, 6)
            ev["delinq_total_ratio"] = f"computed: (31-60 + 61-90 + 91+) / principal balance {principal_end:,.2f}"
        else:
            res.missing.append("delinq_total_ratio")
        if pool_orig and v.get("cum_net_losses") is not None:
            v["cum_net_loss_ratio"] = round(v["cum_net_losses"] / pool_orig, 6)
            ev["cum_net_loss_ratio"] = f"computed: cumulative non-reimbursable losses / original pool balance {pool_orig:,.2f}"
        else:
            res.missing.append("cum_net_loss_ratio")
        return res
