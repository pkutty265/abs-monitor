"""Unit tests on synthetic exhibit text. Replace fixtures with real saved exhibits after first run."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from absmon.parsers.base import parse_number, html_to_lines
from absmon.parsers.registry import get_parser

SYNTH_HTML = b"""
<html><body>
<p>Ford Credit Auto Owner Trust 2024-D Monthly Investor Report</p>
<p>Collection Period: June 1, 2026 through June 30, 2026</p>
<p>Distribution Date: July 15, 2026</p>
<table>
<tr><td></td><td>Beginning of Period</td><td>End of Period</td></tr>
<tr><td>Pool Balance</td><td>$812,345,678.90</td><td>$780,123,456.78</td></tr>
<tr><td>Number of Receivables</td><td>41,201</td><td>39,877</td></tr>
<tr><td>Pool Factor</td><td>0.6123</td><td>0.5880</td></tr>
<tr><td>Total Collections</td><td>$35,000,000.12</td></tr>
<tr><td>Principal Collections</td><td>$31,000,000.00</td></tr>
<tr><td>Interest Collections</td><td>$4,000,000.12</td></tr>
<tr><td>Gross Credit Losses</td><td>$1,250,000.00</td></tr>
<tr><td>Recoveries</td><td>$300,000.00</td></tr>
<tr><td>Net Credit Losses</td><td>$950,000.00</td></tr>
<tr><td>Cumulative Net Credit Losses</td><td>$4,100,000.00</td></tr>
<tr><td>Cumulative Net Credit Loss Ratio</td><td>0.31%</td></tr>
<tr><td>31-60 Days Delinquent</td><td>$9,000,000.00</td></tr>
<tr><td>61-90 Days Delinquent</td><td>$3,000,000.00</td></tr>
<tr><td>91+ Days Delinquent</td><td>$1,000,000.00</td></tr>
<tr><td>Total Delinquency Ratio</td><td>1.67%</td></tr>
<tr><td>Reserve Account Balance</td><td>$3,318,000.00</td></tr>
<tr><td>Total Notes Balance</td><td>$800,000,000.00</td><td>$768,000,000.00</td></tr>
<tr><td>Servicing Fee</td><td>$677,000.00</td></tr>
</table></body></html>
"""


def test_parse_number():
    assert parse_number("$1,234.50") == 1234.5
    assert parse_number("(1,000)") == -1000
    assert parse_number("0.31%", "ratio") == 0.0031
    assert parse_number("0.6123", "ratio") == 0.6123
    assert parse_number("-") is None


def test_ford_synthetic():
    lines = html_to_lines(SYNTH_HTML)
    res = get_parser("ford_auto").parse(lines)
    v = res.values
    assert v["pool_balance_begin"] == 812345678.90
    assert v["pool_balance_end"] == 780123456.78
    assert v["receivables_count_end"] == 39877
    assert v["pool_factor"] == 0.6123  # NOTE: nth=0 picks beginning; tune per issuer layout
    assert v["net_losses_period"] == 950000.0
    assert v["cum_net_losses"] == 4100000.0
    assert abs(v["cum_net_loss_ratio"] - 0.0031) < 1e-9
    assert v["delinq_91_plus"] == 1000000.0
    assert abs(v["delinq_total_ratio"] - 0.0167) < 1e-9
    assert v["collection_period_end"] == "June 30, 2026"
    assert v["distribution_date"] == "July 15, 2026"
    assert v["note_balance_total"] == 768000000.0
    assert not res.missing, res.missing


if __name__ == "__main__":
    test_parse_number()
    test_ford_synthetic()
    print("tests passed")
