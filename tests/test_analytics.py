"""Tests for src/absmon/analytics/*. Synthetic-frame unit tests plus one regression test
against the real pulled ABS-EE data (see tests/test_parsers.py for the fixture-based
parser tests this mirrors)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from absmon.analytics.rollrates import bucket_days, matrix, BUCKETS, STATES  # noqa: E402
from absmon.analytics.losscurves import loss_events  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FORD_ABSEE_DIR = REPO_ROOT / "data" / "parsed" / "absee" / "ford_credit_auto_owner_trust_2024-d"
PANEL_CSV = REPO_ROOT / "data" / "parsed" / "servicer_reports.csv"


def test_bucket_days_known_values():
    """0 -> current; 1-30 -> dq1_30; 31-60 -> dq31_60; 61-90 -> dq61_90; 91+ -> dq91p."""
    days = pd.Series([0, 1, 30, 31, 60, 61, 90, 91, 400])
    got = list(bucket_days(days))
    assert got == ["current", "dq1_30", "dq1_30", "dq31_60", "dq31_60",
                    "dq61_90", "dq61_90", "dq91p", "dq91p"], got


def test_matrix_rows_sum_to_one():
    """Every origin with at least one transition sums to 1 across destinations, both
    count-weighted and balance-weighted."""
    trans = pd.DataFrame({
        "asset_id": ["a", "b", "c", "d", "e", "f", "g"],
        "origin":   ["current", "current", "current", "dq1_30", "dq1_30", "dq31_60", "dq91p"],
        "dest":     ["current", "dq1_30", "paid_off", "current", "dq31_60", "charged_off", "paid_off"],
        "balance":  [1000, 200, 50, 300, 150, 400, 900],
    })
    m = matrix(trans)
    assert set(m["origin"].unique()) <= set(BUCKETS)
    assert set(m["dest"].unique()) == set(STATES)
    for origin in ("current", "dq1_30", "dq31_60", "dq91p"):
        sub = m[m["origin"] == origin]
        assert abs(sub["share_count"].sum() - 1.0) < 1e-9, (origin, sub["share_count"].sum())
        assert abs(sub["share_balance"].sum() - 1.0) < 1e-9, (origin, sub["share_balance"].sum())
    # An origin with zero transitions (dq61_90 here) must not silently read as "all current".
    empty = m[m["origin"] == "dq61_90"]
    assert (empty["n"] == 0).all() and empty["share_count"].isna().all()


def _month(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df


def test_loss_events_excludes_restated_amounts():
    """A loan already coded charged-off last month must not count its amount again this
    month, even if the servicer re-prints it (CarMax's behavior) — but a loan coded for
    the FIRST time this month must count, whether or not it was active before."""
    months = {
        "2024-01": _month([
            # x: charged off for the first time this month.
            dict(asset_id="x", period_end="2024-01-31", chargeoff_amount=1000.0,
                 recovery_amount=None, zero_balance_code="4"),
            # y: still active.
            dict(asset_id="y", period_end="2024-01-31", chargeoff_amount=None,
                 recovery_amount=None, zero_balance_code=None),
        ]),
        "2024-02": _month([
            # x: re-printed by the servicer with a recovery now attached — must be excluded.
            dict(asset_id="x", period_end="2024-02-28", chargeoff_amount=1000.0,
                 recovery_amount=200.0, zero_balance_code="4"),
            # y: charged off for the first time this month — must count.
            dict(asset_id="y", period_end="2024-02-28", chargeoff_amount=500.0,
                 recovery_amount=None, zero_balance_code="4"),
        ]),
    }
    ev = loss_events(months).set_index(["asset_id", "month"])

    jan_x = ev.loc[("x", pd.Period("2024-01", "M"))]
    assert jan_x["gross_loss"] == 1000.0
    assert jan_x["gross_loss_rereported"] == 0.0

    feb_x = ev.loc[("x", pd.Period("2024-02", "M"))]
    assert feb_x["gross_loss"] == 0.0, "re-stated amount on an already-coded loan must not recount"
    assert feb_x["gross_loss_rereported"] == 1000.0
    assert feb_x["recovery"] == 200.0, "recovery passes through regardless of the restatement flag"

    feb_y = ev.loc[("y", pd.Period("2024-02", "M"))]
    assert feb_y["gross_loss"] == 500.0, "first-time coding must count even though the loan existed before"
    assert feb_y["gross_loss_rereported"] == 0.0


def test_ford_gross_chargeoff_ties_to_10d():
    """Regression: Ford's ABS-EE gross charge-offs, summed over the pulled window under
    the previous-month rule, must tie to the 10-D servicer-report panel within 0.1% —
    Ford doesn't re-state (unlike CarMax), so this is the clean case."""
    if not FORD_ABSEE_DIR.exists() or not PANEL_CSV.exists():
        print("skip test_ford_gross_chargeoff_ties_to_10d: data/parsed/{absee,servicer_reports.csv} not present")
        return
    from absmon.analytics.rollrates import load_months

    months = load_months(FORD_ABSEE_DIR)
    ll_total = loss_events(months)["gross_loss"].sum()

    panel = pd.read_csv(PANEL_CSV, parse_dates=["report_date"])
    ford = panel[panel["trust_name"] == "Ford Credit Auto Owner Trust 2024-D"].copy()
    ford["period"] = ford["report_date"].dt.strftime("%Y-%m")
    td_total = ford.loc[ford["period"].isin(months), "gross_losses_period"].sum()

    rel_diff = abs(ll_total - td_total) / td_total
    assert rel_diff < 0.001, (
        f"loan-level ${ll_total:,.2f} vs 10-D ${td_total:,.2f} ({rel_diff:.4%} off, expected < 0.1%)")


if __name__ == "__main__":
    test_bucket_days_known_values()
    test_matrix_rows_sum_to_one()
    test_loss_events_excludes_restated_amounts()
    test_ford_gross_chargeoff_ties_to_10d()
    print("tests passed")
