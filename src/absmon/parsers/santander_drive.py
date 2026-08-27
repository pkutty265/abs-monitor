"""Santander Drive Auto Receivables Trust — servicer report (often PDF). Best-effort labels."""
from .base import LabelMapParser, FieldSpec


class SantanderDriveParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"beginning.*pool balance", r"pool balance.*beginning", r"^pool balance"], nth=0),
        FieldSpec("pool_balance_end",   [r"ending.*pool balance", r"pool balance.*end", r"^pool balance"], nth=1),
        FieldSpec("pool_factor",        [r"pool factor"], kind="ratio"),
        FieldSpec("receivables_count_end", [r"number of (?:receivables|contracts|loans)"], kind="count"),
        FieldSpec("collections_total",  [r"total collections"]),
        FieldSpec("collections_principal", [r"principal collections"]),
        FieldSpec("collections_interest",  [r"interest collections"]),
        FieldSpec("gross_losses_period", [r"gross (?:losses|charge-?offs)"]),
        FieldSpec("recoveries_period",   [r"recoveries"]),
        FieldSpec("net_losses_period",   [r"net (?:losses|charge-?offs)(?! ratio| percentage)"]),
        FieldSpec("cum_net_losses",      [r"cumulative net (?:losses|charge-?offs)(?! ratio| percentage| as)"]),
        FieldSpec("cum_net_loss_ratio",  [r"cumulative net (?:loss|charge-?off)\w* (?:ratio|percentage|as a)"], kind="ratio"),
        FieldSpec("delinq_31_60",  [r"31\s*[-–]\s*60"]),
        FieldSpec("delinq_61_90",  [r"61\s*[-–]\s*90"]),
        FieldSpec("delinq_91_plus", [r"(?:91|over 90|91\+)"]),
        FieldSpec("delinq_total_ratio", [r"delinquen\w+ (?:ratio|percentage)"], kind="ratio"),
        FieldSpec("reserve_account_balance", [r"reserve account"]),
        FieldSpec("note_balance_total", [r"total.*notes?.*balance"], nth=1),
        FieldSpec("servicing_fee", [r"servicing fee"]),
    ]
