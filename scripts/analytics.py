#!/usr/bin/env python
"""Loan-level analytics on the ABS-EE parquet: roll rates, vintage loss curves, and a
reconciliation of both against the 10-D servicer-report panel.

Usage:
  python scripts/analytics.py                # all auto trusts under data/parsed/absee/
  python scripts/analytics.py --only carmax  # substring filter on trust slug

Writes tidy CSVs to data/parsed/analytics/ and prints a readable summary.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from absmon.analytics.rollrates import roll_rates, pivot, BUCKETS, load_months, state_of  # noqa: E402
from absmon.analytics.losscurves import loss_curves, loss_events  # noqa: E402

TEN_D_NAMES = {  # parquet slug -> trust_name in servicer_reports.csv
    "carmax_auto_owner_trust_2024-1": "CarMax Auto Owner Trust 2024-1",
    "ford_credit_auto_owner_trust_2024-d": "Ford Credit Auto Owner Trust 2024-D",
    "santander_drive_auto_receivables_trust_2024-1": "Santander Drive Auto Receivables Trust 2024-1",
}


def reconcile(trust_dir: Path, trust: str, panel: pd.DataFrame) -> pd.DataFrame:
    """Loan-level monthly aggregates next to the 10-D figures for the same period."""
    months = load_months(trust_dir)
    ev = loss_events(months)
    by_month = ev.groupby(ev["month"].astype(str))[["gross_loss", "gross_loss_rereported", "recovery"]].sum()
    rows = []
    for period, m in months.items():
        st = state_of(m)
        active = st.isin(BUCKETS)
        bal = m["balance_end"].where(active, 0.0)
        rows.append({
            "period": period,
            "ll_active_balance": bal.sum(),
            "ll_active_loans": int(active.sum()),
            "ll_gross_chargeoff": by_month.loc[period, "gross_loss"],
            "ll_gross_rereported": by_month.loc[period, "gross_loss_rereported"],
            "ll_recovery": by_month.loc[period, "recovery"],
            "ll_dq31_60_pct": bal[st == "dq31_60"].sum() / bal.sum(),
            "ll_dq61_90_pct": bal[st == "dq61_90"].sum() / bal.sum(),
            "ll_dq91p_pct": bal[st == "dq91p"].sum() / bal.sum(),
            "ll_dq31p_pct": bal[st.isin(["dq31_60", "dq61_90", "dq91p"])].sum() / bal.sum(),
        })
    ll = pd.DataFrame(rows)
    td = panel[panel["trust_name"] == TEN_D_NAMES[trust]].copy()
    td["period"] = td["report_date"].dt.strftime("%Y-%m")
    td = td.set_index("period")
    ll = ll.set_index("period")
    out = ll.join(td[["pool_balance_end", "receivables_count_end", "gross_losses_period",
                      "recoveries_period", "delinq_31_60", "delinq_61_90", "delinq_91_plus",
                      "delinq_total_ratio"]], how="left")
    for b in ("31_60", "61_90", "91_plus"):
        out[f"td_dq{b}_pct"] = out[f"delinq_{b}"] / out["pool_balance_end"]
    out["td_dq31p_pct"] = out["delinq_total_ratio"]
    out.insert(0, "trust", trust)
    return out.reset_index()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--absee", default="data/parsed/absee")
    ap.add_argument("--panel", default="data/parsed/servicer_reports.csv")
    ap.add_argument("--out", default="data/parsed/analytics")
    ap.add_argument("--vintage-freq", default="Q", help="pandas period alias for vintage bins (Q, M, Y)")
    ap.add_argument("--only", nargs="*", help="substring filter on trust slug")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(args.panel, parse_dates=["report_date"])
    dirs = sorted(d for d in Path(args.absee).iterdir() if d.is_dir())
    if args.only:
        dirs = [d for d in dirs if any(s.lower() in d.name.lower() for s in args.only)]

    monthly_all, pooled_all, curves_all, recon_all = [], [], [], []
    pd.set_option("display.width", 220, "display.max_columns", 30)
    for d in dirs:
        trust = d.name
        monthly, pooled = roll_rates(d, trust)
        curve, diag = loss_curves(d, trust, vintage_freq=args.vintage_freq)
        recon = reconcile(d, trust, panel)
        monthly_all.append(monthly); pooled_all.append(pooled); curves_all.append(curve); recon_all.append(recon)

        print(f"\n{'=' * 100}\n{trust}   window {diag['window'][0]} .. {diag['window'][1]}\n{'=' * 100}")
        print(f"loans seen: {diag['loans_seen']:,}  |  missing originationDate: {diag['origination_date_missing']:,}"
              f"  |  event rows unmatched to a vintage: {diag['event_rows_unmatched_to_vintage']:,}"
              f" (gross loss ${diag['unmatched_gross_loss']:,.0f})")
        print(f"charged off before window: {diag['loans_charged_off_before_window']:,} loans; their in-window recoveries"
              f" excluded from curves: ${diag['pre_window_chargeoff_recoveries_excluded']:,.0f}")
        print(f"re-reported charge-off amounts on already-coded loans, excluded: ${diag['rereported_chargeoffs_excluded']:,.0f}")

        print("\n-- pooled transition matrix, balance-weighted (row = origin, % of origin balance) --")
        print((pivot(pooled, "share_balance") * 100).round(2).to_string())
        print("\n-- pooled transition matrix, count-weighted (%) --")
        print((pivot(pooled, "share_count") * 100).round(2).to_string())
        key = pooled.set_index(["origin", "dest"])["share_balance"]
        worse = {"current": "dq1_30", "dq1_30": "dq31_60", "dq31_60": "dq61_90", "dq61_90": "dq91p", "dq91p": "charged_off"}
        print("\n-- key monthly rates (balance-weighted) --")
        for o, dn in worse.items():
            cure = key.get((o, "current"), float("nan")) if o != "current" else float("nan")
            print(f"  {o:8s} -> {dn:12s} {key[(o, dn)] * 100:6.2f}%   "
                  f"-> paid_off {key[(o, 'paid_off')] * 100:5.2f}%   "
                  + (f"-> current (cure) {cure * 100:6.2f}%" if o != "current" else ""))

        print("\n-- vintage cumulative net loss, % of original cohort balance --")
        ages = [6, 12, 18, 24, 30, 36]
        coh_bal = curve.groupby("vintage")["cohort_orig_balance"].first()
        material = coh_bal[coh_bal >= 0.01 * coh_bal.sum()].index  # >= 1% of trust cohort balance
        c = curve[curve["age"].isin(ages) & curve["vintage"].isin(material)].copy()
        c["v"] = c["cnl_pct_of_orig"].mul(100).round(2).astype(str) + c["age_complete"].map({True: "", False: "*"})
        tab = c.pivot(index="vintage", columns="age", values="v")
        coh = curve.groupby("vintage")[["n_loans", "cohort_orig_balance", "age_complete_from", "age_complete_to"]].first()
        coh["cohort_orig_balance"] = (coh["cohort_orig_balance"] / 1e6).round(1)
        print(coh.loc[material].join(tab).rename(columns={"cohort_orig_balance": "orig_$M"}).to_string())
        print("   * = age not fully inside the window for every loan in the vintage (undercounted)")
        print(f"   (vintages under 1% of cohort balance omitted here; all {coh.shape[0]} are in losscurves.csv)")

        print("\n-- reconciliation to 10-D (ratio loan-level / 10-D; 1.00 = ties) --")
        r = recon.dropna(subset=["pool_balance_end"]).reset_index(drop=True)
        ratios = pd.DataFrame({
            "active balance": r["ll_active_balance"] / r["pool_balance_end"],
            "gross charge-offs": r["ll_gross_chargeoff"] / r["gross_losses_period"],
            "recoveries": r["ll_recovery"] / r["recoveries_period"],
            "net losses": (r["ll_gross_chargeoff"] - r["ll_recovery"]) / (r["gross_losses_period"] - r["recoveries_period"]),
            "dq31-60 %": r["ll_dq31_60_pct"] / r["td_dq31_60_pct"],
            "dq61-90 %": r["ll_dq61_90_pct"] / r["td_dq61_90_pct"],
            "dq91+ %": r["ll_dq91p_pct"] / r["td_dq91_plus_pct"],
            "dq31+ %": r["ll_dq31p_pct"] / r["td_dq31p_pct"],
        })
        print(ratios.describe().loc[["mean", "min", "max"]].round(3).to_string())
        print(f"  window totals  loan-level gross ${r['ll_gross_chargeoff'].sum():,.0f} / recov ${r['ll_recovery'].sum():,.0f}"
              f"   10-D gross ${r['gross_losses_period'].sum():,.0f} / recov ${r['recoveries_period'].sum():,.0f}")
        last = r.iloc[-1]
        print(f"  latest {last['period']}: loan-level dq31+ {last['ll_dq31p_pct'] * 100:.2f}% vs 10-D {last['td_dq31p_pct'] * 100:.2f}%"
              f" | gross CO ${last['ll_gross_chargeoff']:,.0f} vs ${last['gross_losses_period']:,.0f}"
              f" | recoveries ${last['ll_recovery']:,.0f} vs ${last['recoveries_period']:,.0f}")

    pd.concat(monthly_all).to_csv(out / "rollrates_monthly.csv", index=False)
    pd.concat(pooled_all).to_csv(out / "rollrates_pooled.csv", index=False)
    pd.concat(curves_all).to_csv(out / "losscurves.csv", index=False)
    pd.concat(recon_all).to_csv(out / "reconciliation_10d.csv", index=False)
    print(f"\nwrote rollrates_monthly.csv, rollrates_pooled.csv, losscurves.csv, reconciliation_10d.csv -> {out}/")


if __name__ == "__main__":
    main()
