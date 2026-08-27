"""Canonical servicer-report fields. Wide-format columns; all monetary values in USD, rates as decimals."""

ID_COLUMNS = [
    "trust_name", "cik", "issuer", "asset_class", "accession", "filing_date", "report_date",
    "collection_period_end", "distribution_date", "exhibit_filename", "exhibit_format", "parser",
]

# Canonical metric fields. Keep names asset-class agnostic; issuer parsers map their labels here.
METRIC_COLUMNS = [
    # Pool
    "pool_balance_begin", "pool_balance_end", "pool_factor", "receivables_count_end",
    # Cash
    "collections_total", "collections_principal", "collections_interest",
    # Losses
    "gross_losses_period", "recoveries_period", "net_losses_period",
    "cum_net_losses", "cum_net_loss_ratio",
    # Delinquency (balance-based, end of period)
    "delinq_31_60", "delinq_61_90", "delinq_91_plus", "delinq_total_ratio",
    # Student-loan specific (FFELP)
    "forbearance_balance", "deferment_balance", "claims_paid_period",
    # Structure
    "reserve_account_balance", "note_balance_total", "servicing_fee",
]

ALL_COLUMNS = ID_COLUMNS + METRIC_COLUMNS
