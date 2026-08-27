"""Ford Credit Auto Owner Trust — 'Monthly Investor Report' (EX-99, HTML).

LABELS BELOW ARE BEST-EFFORT AND UNVERIFIED against a live exhibit. After the first run,
open data/raw/edgar/<cik>/<acc>/<exhibit> and tune. Ford reports typically show
"Beginning of period / End of period" columns, hence nth=1 for end-of-period rows.
"""
from .base import LabelMapParser, FieldSpec


class FordAutoParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"^pool balance", r"receivables balance"], nth=0),
        FieldSpec("pool_balance_end",   [r"^pool balance", r"receivables balance"], nth=1),
        FieldSpec("pool_factor",        [r"pool factor"], kind="ratio"),
        FieldSpec("receivables_count_end", [r"number of receivables"], nth=1, kind="count"),
        FieldSpec("collections_total",  [r"total collections", r"^collections"]),
        FieldSpec("collections_principal", [r"principal collections", r"collections.*principal"]),
        FieldSpec("collections_interest",  [r"interest collections", r"collections.*interest"]),
        FieldSpec("gross_losses_period", [r"gross (?:credit )?losses", r"defaulted receivables"]),
        FieldSpec("recoveries_period",   [r"recoveries"]),
        FieldSpec("net_losses_period",   [r"net (?:credit )?losses(?! ratio| percentage)"]),
        FieldSpec("cum_net_losses",      [r"cumulative net (?:credit )?losses(?! ratio| percentage| as)"]),
        FieldSpec("cum_net_loss_ratio",  [r"cumulative net (?:credit )?loss(?:es)? (?:ratio|percentage|as a percent)"], kind="ratio"),
        FieldSpec("delinq_31_60",  [r"31\s*[-–]\s*60 days"]),
        FieldSpec("delinq_61_90",  [r"61\s*[-–]\s*90 days"]),
        FieldSpec("delinq_91_plus", [r"(?:91|over 90|91\+|121\+).*days"]),
        FieldSpec("delinq_total_ratio", [r"total delinquen\w+ (?:ratio|percentage)", r"delinquen\w+ (?:ratio|percentage)"], kind="ratio"),
        FieldSpec("reserve_account_balance", [r"reserve account (?:balance|ending)", r"reserve account"]),
        FieldSpec("note_balance_total", [r"total (?:note|notes|securities) (?:principal )?balance", r"total notes"], nth=1),
        FieldSpec("servicing_fee", [r"servicing fee"]),
    ]
