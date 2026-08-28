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


def test_santander_real_exhibit():
    """Santander Drive ART 2024-1, March 2026 collection period (accession 0001193125-26-155322)."""
    raw = (Path(__file__).parent / "fixtures" / "d121531dex991.htm").read_bytes()
    res = get_parser("santander_drive").parse(html_to_lines(raw))
    v = res.values
    assert v["pool_balance_begin"] == 609_374_063.72
    assert v["pool_balance_end"] == 581_592_835.05
    assert v["pool_factor"] == 0.361318  # the {9} value, not the {8} cross-reference marker
    assert v["receivables_count_end"] == 29_686  # Current column, not Original/Previous
    assert v["collections_total"] == 33_325_729.60  # Total Available Funds
    assert v["collections_principal"] == 20_163_665.39
    assert v["collections_interest"] == 8_676_701.29
    assert v["gross_losses_period"] == 7_569_812.94  # dollar column, not the 416 unit count
    assert v["recoveries_period"] == 4_462_837.51  # Liquidation Proceeds, not the 2,921 units
    # net = defaulted (7,569,812.94) + cram downs (47,750.34) - liquidation proceeds (4,462,837.51)
    assert v["net_losses_period"] == 3_154_725.77
    assert v["cum_net_losses"] == 143_792_282.72  # end of period, not beginning 140,637,556.95
    assert abs(v["cum_net_loss_ratio"] - 0.0893) < 1e-9
    assert v["delinq_31_60"] == 65_935_356.77  # dollars, not the 3,076 units or 11.34%
    assert v["delinq_61_90"] == 36_964_894.43
    assert v["delinq_91_plus"] == 11_167_250.26  # 91-120 bucket; 121+ is charged off (zero)
    assert abs(v["delinq_31_60"] + v["delinq_61_90"] + v["delinq_91_plus"] - 114_067_501.46) < 0.01  # Total row
    assert abs(v["delinq_total_ratio"] - 0.1961) < 1e-9
    assert v["reserve_account_balance"] == 16_096_435.28
    assert v["note_balance_total"] == 460_997_853.56  # section V total, not a per-class figure
    assert v["servicing_fee"] == 1_523_435.16  # Total from the split-line Servicing Fee table
    assert v["collection_period_end"] == "03/31/2026"
    assert v["distribution_date"] == "04/15/2026"  # Payment Date, not Previous Payment Date 03/16
    assert not res.missing, res.missing


def test_navient_2014_5_real_exhibit():
    """Navient SLT 2014-5 (100% consolidation loans), June 2026 collection period
    (accession 0001140361-26-031595). Zero-loss month: Non-Reimbursable Losses is a
    '-' placeholder and must parse as 0, not fall through to the prior-month column."""
    raw = (Path(__file__).parent / "fixtures" / "ef20078669_ex99-1.htm").read_bytes()
    res = get_parser("navient_ffelp").parse(html_to_lines(raw))
    v = res.values
    assert v["pool_balance_begin"] == 42_318_388.06  # prior-month column, not original 156.2M
    assert v["pool_balance_end"] == 42_138_553.52
    assert v["pool_factor"] == 0.265845898  # current column, as published
    assert v["receivables_count_end"] == 1_791  # current, not prior-month 1,805
    assert v["collections_total"] == 315_485.90  # Total Available Funds
    assert v["collections_principal"] == 285_594.21
    assert v["collections_interest"] == 74_308.00
    assert v["claims_paid_period"] == 27_512.70  # Guarantor Principal 26,440.51 + Interest 1,072.19
    assert v["net_losses_period"] == 0.0  # '-' placeholder, not prior month's 8,521.02
    assert v["cum_net_losses"] == 780_131.01
    assert abs(v["cum_net_loss_ratio"] - 780_131.01 / 156_158_256.69) < 1e-6  # computed
    assert v["delinq_31_60"] == 1_645_549.59  # current $ column, not the 5.62% WAC
    assert v["delinq_61_90"] == 798_916.22
    assert v["delinq_91_plus"] == 2_577_936.26  # 91-120 (554,946.47) + >120 (2,022,989.79)
    assert abs(v["delinq_total_ratio"] - 0.119747) < 1e-6  # 11.97% of principal, per report %s
    assert v["deferment_balance"] == 1_471_781.22  # "INTERIM: DEFERMENT" row
    assert v["forbearance_balance"] == 4_147_099.62
    assert v["reserve_account_balance"] == 158_507.00  # Ending, not the at-issuance Specified
    assert v["note_balance_total"] == 39_421_738.22  # after-distribution column
    assert v["servicing_fee"] == 5_455.45  # waterfall Paid column, not remaining funds
    assert v["collection_period_end"] == "06/30/2026"
    assert v["distribution_date"] == "07/27/2026"
    assert not res.missing, res.missing


def test_navient_2015_3_real_exhibit():
    """Navient SLT 2015-3 (Stafford/PLUS pool), June 2026 collection period
    (accession 0001140361-26-031601). Has IN SCHOOL/GRACE buckets and a bare
    'DEFERMENT' label (no 'INTERIM:' prefix), unlike 2014-5."""
    raw = (Path(__file__).parent / "fixtures" / "ef20078676_ex99-1.htm").read_bytes()
    res = get_parser("navient_ffelp").parse(html_to_lines(raw))
    v = res.values
    assert v["pool_balance_begin"] == 196_524_922.05
    assert v["pool_balance_end"] == 194_652_490.48
    assert v["pool_factor"] == 0.258627815
    assert v["receivables_count_end"] == 17_897
    assert v["collections_total"] == 2_620_951.72
    assert v["collections_principal"] == 2_424_936.12
    assert v["collections_interest"] == 360_306.93
    assert v["claims_paid_period"] == 1_540_839.24  # 1,468,785.29 + 72,053.95
    assert v["net_losses_period"] == 35_426.11  # risk-share loss, real value this month
    assert v["cum_net_losses"] == 4_346_189.14  # current column: prior 4,310,763.03 + 35,426.11
    assert v["delinq_31_60"] == 7_143_903.61
    assert v["delinq_61_90"] == 4_520_219.33
    assert v["delinq_91_plus"] == 14_871_135.56  # 91-120 (4,832,961.95) + >120 (10,038,173.61)
    assert abs(v["delinq_total_ratio"] - 0.137757) < 1e-6
    assert v["deferment_balance"] == 7_388_061.15  # bare "DEFERMENT" row
    assert v["forbearance_balance"] == 33_213_588.74
    assert v["reserve_account_balance"] == 752_636.00
    assert v["note_balance_total"] == 191_735_528.70
    assert v["servicing_fee"] == 37_717.68
    assert v["collection_period_end"] == "06/30/2026"
    assert v["distribution_date"] == "07/27/2026"
    assert not res.missing, res.missing


if __name__ == "__main__":
    test_parse_number()
    test_ford_real_exhibit()
    test_carmax_real_exhibit()
    test_santander_real_exhibit()
    test_navient_2014_5_real_exhibit()
    test_navient_2015_3_real_exhibit()
    print("tests passed")
