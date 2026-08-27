"""CarMax Auto Owner Trust — 'Monthly Servicer's Certificate' (EX-99.1, HTML).

Labels verified against the real 2024-1 exhibit (tests/fixtures/a2024-1ex991061625.htm).
The certificate is a numbered list; loss and delinquency tables put a loan-count column
before the dollar column, hence nth=1 on those rows.
"""
from .base import LabelMapParser, FieldSpec


class CarMaxAutoParser(LabelMapParser):
    specs = [
        FieldSpec("pool_balance_begin", [r"pool balance on the close of the last day of the preceding collection period"]),
        FieldSpec("pool_balance_end",   [r"pool balance on the close of the last day of the related collection period"]),
        # Aggregate row is "i. Note Pool Factor <begin> <end>"; anchoring on "<letter>. "
        # keeps the per-class rows ("a. Class A-1 Note Pool Factor ...") from matching.
        FieldSpec("pool_factor", [r"^[a-z]\. note pool factor"], nth=1, kind="ratio"),
        FieldSpec("receivables_count_end", [r"total number of receivables outstanding", r"number of receivables"], kind="count"),
        FieldSpec("collections_total",  [r"total finance charge and principal collections"]),
        FieldSpec("collections_principal", [r"available principal collections"]),
        FieldSpec("collections_interest",  [r"available finance charge collections"]),
        FieldSpec("gross_losses_period", [r"defaulted receivables \(charge-?offs\)"], nth=1, section=r"^loss activity"),
        FieldSpec("recoveries_period",   [r"recoveries"], nth=1, section=r"^loss activity"),
        FieldSpec("net_losses_period",   [r"net losses(?! ratio| percentage| to)"], section=r"^loss activity"),
        FieldSpec("cum_net_losses",      [r"cumulative net losses(?! ratio| percentage| as| to)"], section=r"^cumulative loss activity"),
        FieldSpec("cum_net_loss_ratio",  [r"ratio of cumulative net losses"], kind="ratio"),
        FieldSpec("delinq_31_60",  [r"31\s*(?:to|[-–])\s*60 days past due"], nth=1),
        FieldSpec("delinq_61_90",  [r"61\s*(?:to|[-–])\s*90 days past due"], nth=1),
        # CarMax buckets 91-120 and 121+ separately; 121+ receivables are charged off and
        # reported as zero, so the 91-120 balance stands in for 91+.
        FieldSpec("delinq_91_plus", [r"91\s*(?:to|[-–])\s*120 days past due"], nth=1),
        FieldSpec("delinq_total_ratio", [r"delinquent loans as a percentage"], kind="ratio"),
        FieldSpec("reserve_account_balance", [r"ending balance"], section=r"^reserve account reconciliation"),
        FieldSpec("note_balance_total", [r"note balance \(sum"], nth=1),
        FieldSpec("servicing_fee", [r"monthly servicing fee"]),
    ]
