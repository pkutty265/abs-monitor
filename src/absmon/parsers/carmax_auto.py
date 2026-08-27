"""CarMax Auto Owner Trust — 'Monthly Servicer's Certificate' (EX-99.1, HTML).
Best-effort labels; verify against first fetched exhibit."""
from .base import LabelMapParser, FieldSpec


class CarMaxAutoParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"pool balance.*beginning", r"beginning.*pool balance", r"^pool balance"], nth=0),
        FieldSpec("pool_balance_end",   [r"pool balance.*end", r"ending.*pool balance", r"^pool balance"], nth=1),
        FieldSpec("pool_factor",        [r"pool factor"], kind="ratio"),
        FieldSpec("receivables_count_end", [r"number of receivables.*end", r"number of receivables"], kind="count"),
        FieldSpec("collections_total",  [r"total collections", r"available funds"]),
        FieldSpec("collections_principal", [r"principal collections"]),
        FieldSpec("collections_interest",  [r"interest collections"]),
        FieldSpec("gross_losses_period", [r"gross losses", r"realized losses"]),
        FieldSpec("recoveries_period",   [r"recoveries"]),
        FieldSpec("net_losses_period",   [r"net losses(?! ratio| percentage)"]),
        FieldSpec("cum_net_losses",      [r"cumulative net losses(?! ratio| percentage| as)"]),
        FieldSpec("cum_net_loss_ratio",  [r"cumulative net loss(?:es)? (?:ratio|percentage|as a)"], kind="ratio"),
        FieldSpec("delinq_31_60",  [r"31\s*[-–]\s*60"]),
        FieldSpec("delinq_61_90",  [r"61\s*[-–]\s*90"]),
        FieldSpec("delinq_91_plus", [r"(?:91|over 90|91\+)"]),
        FieldSpec("delinq_total_ratio", [r"delinquen\w+ (?:ratio|percentage)"], kind="ratio"),
        FieldSpec("reserve_account_balance", [r"reserve account"]),
        FieldSpec("note_balance_total", [r"total.*(?:note|notes).*(?:balance|outstanding)"], nth=1),
        FieldSpec("servicing_fee", [r"servicing fee"]),
    ]
