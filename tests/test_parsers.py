"""Unit tests against real saved exhibits (see tests/fixtures/)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from absmon.parsers.base import parse_number, html_to_lines
from absmon.parsers.registry import get_parser


def test_parse_number():
    assert parse_number("$1,234.50") == 1234.5
    assert parse_number("(1,000)") == -1000
    assert parse_number("0.31%", "ratio") == 0.0031
    assert parse_number("0.6123", "ratio") == 0.6123
    assert parse_number("-") is None


def test_ford_real_exhibit():
    """Ford Credit AOT 2024-D, Sept 2025 collection period (accession 0002042453-25-000045)."""
    raw = (Path(__file__).parent / "fixtures" / "fcaot2024-d10xdinvestorrep.htm").read_bytes()
    res = get_parser("ford_auto").parse(html_to_lines(raw))
    v = res.values
    assert v["pool_balance_begin"] == 1_219_013_447.86
    assert v["pool_balance_end"] == 1_174_301_836.03
    assert v["pool_factor"] == 0.6975902  # end of period, matching pool_balance_end
    assert v["receivables_count_end"] == 34_708  # end column, not beginning 35,403
    assert v["collections_total"] == 49_106_986.35
    assert v["collections_principal"] == 44_010_468.31  # principal Sub Total incl. prepays/liquidations
    assert v["collections_interest"] == 5_096_518.04
    assert abs(v["collections_principal"] + v["collections_interest"] - v["collections_total"]) < 0.01
    assert v["gross_losses_period"] == 598_281.53  # dollar column, not the 88 receivable count
    assert v["recoveries_period"] == 11_114.10
    assert v["net_losses_period"] == 587_167.43
    assert abs(v["gross_losses_period"] - v["recoveries_period"] - v["net_losses_period"]) < 0.01
    assert v["cum_net_losses"] == 4_528_617.94
    assert abs(v["cum_net_loss_ratio"] - 0.002690) < 1e-9
    assert v["delinq_31_60"] == 9_623_320.69  # dollar balance, not the 0.82% or the 234 count
    assert v["delinq_61_90"] == 1_872_640.39
    assert v["delinq_91_plus"] == 812_566.65  # 91-120 (265,448.13) + Over 120 (547,118.52)
    assert abs(v["delinq_total_ratio"] - 0.0105) < 1e-9
    assert v["reserve_account_balance"] == 3_947_368.57  # Ending, not Beginning
    assert v["note_balance_total"] == 1_078_817_332.23  # end-of-period Total note balance
    assert v["servicing_fee"] == 1_015_844.54
    assert v["collection_period_end"] == "September 2025"
    assert v["distribution_date"] == "10/15/2025"
    assert not res.missing, res.missing


def test_carmax_real_exhibit():
    """CarMax AOT 2024-1, June 2025 distribution (accession 0002003263-25-000032)."""
    raw = (Path(__file__).parent / "fixtures" / "a2024-1ex991061625.htm").read_bytes()
    res = get_parser("carmax_auto").parse(html_to_lines(raw))
    v = res.values
    assert v["pool_balance_begin"] == 895_851_061.26
    assert v["pool_balance_end"] == 861_024_024.69
    assert v["pool_factor"] == 0.5453984  # aggregate Note Pool Factor, end of period
    assert v["receivables_count_end"] == 51_124
    assert v["collections_total"] == 41_733_403.22
    assert v["collections_principal"] == 33_366_523.51
    assert v["collections_interest"] == 8_366_879.71  # "Available Finance Charge Collections"
    assert v["collections_principal"] + v["collections_interest"] == v["collections_total"]
    assert v["gross_losses_period"] == 2_414_468.18  # dollar column, not the 121 loan count
    assert v["recoveries_period"] == 955_487.75
    assert v["net_losses_period"] == 1_458_980.43  # not the "(Ln 76 - Ln 77)" references
    assert v["cum_net_losses"] == 22_857_349.22
    assert abs(v["cum_net_loss_ratio"] - 0.014599) < 1e-9
    assert v["delinq_31_60"] == 26_821_453.72
    assert v["delinq_61_90"] == 12_244_951.03
    assert v["delinq_91_plus"] == 3_440_809.32  # 91-120 bucket; 121+ is charged off (zero)
    assert abs(v["delinq_total_ratio"] - 0.049368) < 1e-9
    assert v["reserve_account_balance"] == 3_914_142.67  # reconciliation Ending Balance
    assert v["note_balance_total"] == 845_367_454.01  # end-of-period "Note Balance (sum a - h)"
    assert v["servicing_fee"] == 746_542.55  # Monthly Servicing Fee dollar amount, not 0.15%
    assert v["collection_period_end"] == "05/31/25"
    assert v["distribution_date"] == "6/16/2025"
    assert not res.missing, res.missing


if __name__ == "__main__":
    test_parse_number()
    test_ford_real_exhibit()
    test_carmax_real_exhibit()
    print("tests passed")
