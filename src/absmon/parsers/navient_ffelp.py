"""Navient Student Loan Trust (FFELP) — 'Monthly Distribution Report' (EX-99.1, HTML/PDF).
Best-effort labels. FFELP reports have 'Prior Period / Current Period' style columns and
report status buckets (school/grace/deferment/forbearance/repayment) rather than 31-60 style.
"""
from .base import LabelMapParser, FieldSpec


class NavientFfelpParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"^pool balance", r"principal balance"], nth=0),
        FieldSpec("pool_balance_end",   [r"^pool balance", r"principal balance"], nth=1),
        FieldSpec("pool_factor",        [r"pool factor"], nth=1, kind="ratio"),
        FieldSpec("receivables_count_end", [r"number of loans"], nth=1, kind="count"),
        FieldSpec("collections_total",  [r"total (?:collections|receipts|available funds)"]),
        FieldSpec("collections_principal", [r"principal (?:collections|receipts)"]),
        FieldSpec("collections_interest",  [r"interest (?:collections|receipts)"]),
        FieldSpec("claims_paid_period",  [r"(?:guarantor|guarantee) claims? (?:paid|received)", r"claims paid"]),
        FieldSpec("gross_losses_period", [r"(?:gross )?defaults? (?:during|for) the period", r"defaulted loans"]),
        FieldSpec("net_losses_period",   [r"net losses(?! ratio)", r"uninsured losses", r"risk sharing"]),
        FieldSpec("cum_net_losses",      [r"cumulative (?:net )?losses(?! ratio| as)"]),
        FieldSpec("delinq_31_60",  [r"31\s*[-–]\s*60"]),
        FieldSpec("delinq_61_90",  [r"61\s*[-–]\s*90"]),
        FieldSpec("delinq_91_plus", [r"(?:91|over 90|91\+)"]),
        FieldSpec("delinq_total_ratio", [r"total delinquen\w+"], kind="ratio"),
        FieldSpec("forbearance_balance", [r"forbearance"]),
        FieldSpec("deferment_balance",   [r"deferment"]),
        FieldSpec("reserve_account_balance", [r"reserve account"]),
        FieldSpec("note_balance_total", [r"total notes?", r"total (?:principal )?balance of (?:the )?notes"], nth=1),
        FieldSpec("servicing_fee", [r"(?:primary )?servicing fee"]),
    ]
