"""Cumulative net loss by loan age, grouped by origination vintage, from ABS-EE parquet.

Definitions.
  vintage        originationDate (MM/YYYY tag) binned to calendar quarter by default.
                 The tag is a static attribute, so it is taken from the first month a
                 loan is seen; Ford's post-charge-off recovery stubs carry no
                 originationDate at all and are joined to the vintage through that
                 static lookup on asset_id.
  age            whole months from origination month to the filing's period_end
                 (age 0 = origination month).
  gross loss     chargedoffPrincipalAmount (> 0) reported in a month in which the loan
                 was NOT already carrying a zeroBalanceCode the month before — i.e. the
                 month it transitions into a closed state (or while still open).
                 Amounts re-stated on a loan that was already coded last month are
                 dropped. Ford and Santander essentially never re-state, but CarMax
                 re-prints the charged-off principal on ~40% of its code-4 loans in
                 later months, which inflated raw gross losses to 1.41x the 10-D. The
                 rule keys on the previous month, not the loan's first-ever code, so a
                 loan reinstated after charge-off (code 4 -> active -> code 4 again:
                 145 at CarMax, 52 at Santander) counts again when it re-defaults —
                 that is how the 10-Ds count it (CarMax 2026-07: 146 first-time + 3
                 re-defaults = the certificate's "Defaulted Receivables 149").
                 Dating is by the zeroBalanceCode transition, not by
                 zeroBalanceEffectiveDate: CarMax first codes ~20% of loans a month
                 after their stated effective date, and the 10-D counts them in the
                 coded month.
                 Ford also puts chargedoffPrincipalAmount on code-1 (prepaid) exits —
                 payoff deficiencies — and its 10-D "realized loss" includes them, so
                 the rule keys on any code, not code 4 specifically.
  recovery       recoveredAmount, in the period received, at the loan's age then
                 (Ford reports occasional negative recoveries — reversals — which are
                 summed as-is). Only recoveries on loans whose charge-off is itself
                 inside the window count (zeroBalanceEffectiveDate on/after the first
                 filing month, or no such date at all). Recoveries trickling in on
                 loans charged off BEFORE the window have no matching gross loss here
                 and would push old vintages' cumulative net loss negative; they are
                 dropped and reported in the diagnostics instead.
  net loss       gross loss - recovery, cumulated by age within vintage.
  denominator    sum of originalLoanAmount over every loan of the vintage ever seen in
                 the window, so curves are % of original cohort balance and vintages are
                 comparable on the same footing.

Coverage caveats that the output carries as columns rather than hiding:
  * The window starts at the first ABS-EE filing we hold, not at origination. Losses
    before the window are invisible per loan (the 10-D gives only the pool total). For
    Ford the first filing is the closing month, so nothing post-cutoff is missing; CarMax
    and Santander lose the first ~6-7 months after cutoff (Santander's 10-D CNL was
    already 2.08% at the window start). `age_complete_from` is the age from which every
    loan in the vintage was inside the window, i.e. where the curve stops undercounting.
  * Securitized-pool vintage curves are survivorship-conditioned by construction: only
    loans performing at the cutoff date enter the pool, so pre-cutoff defaults never
    appear in any vintage.
  * Charge-off reversals (code 4 -> active again) are ignored; their amounts stay in the
    cumulative loss.
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd

from .rollrates import load_months


def static_attributes(months: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """asset_id -> origination_date, original_balance (first non-null across months)."""
    frames = [m[["asset_id", "origination_date", "original_balance", "zero_balance_date"]]
              for m in months.values()]
    s = pd.concat(frames, ignore_index=True)
    return (s.dropna(subset=["origination_date"])
             .groupby("asset_id", as_index=False)
             .first())  # first non-null per column


def loss_events(months: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per (loan, month): gross_loss under the previous-month rule, the excluded
    re-stated amount, and recovery. Shared by the curves and the 10-D reconciliation."""
    parts, prev_coded = [], pd.Index([])
    for label, m in months.items():  # oldest first
        e = m[["asset_id", "period_end", "chargeoff_amount", "recovery_amount"]].copy()
        amt = e["chargeoff_amount"].where(e["chargeoff_amount"] > 0, 0.0)
        restated = e["asset_id"].isin(prev_coded)
        e["gross_loss"] = amt.where(~restated, 0.0)
        e["gross_loss_rereported"] = amt.where(restated, 0.0)
        e["recovery"] = e["recovery_amount"].fillna(0.0)
        e["month"] = pd.Period(label, freq="M")
        parts.append(e)
        prev_coded = pd.Index(m.loc[m["zero_balance_code"].notna(), "asset_id"])
    return pd.concat(parts, ignore_index=True)


def age_months(period_end: pd.Series, origination: pd.Series) -> pd.Series:
    return ((period_end.dt.year - origination.dt.year) * 12
            + (period_end.dt.month - origination.dt.month)).astype("Int64")


def loss_curves(trust_dir: Path, trust: str, vintage_freq: str = "Q") -> tuple[pd.DataFrame, dict]:
    """(tidy curve, diagnostics) for one trust."""
    months = load_months(trust_dir)
    static = static_attributes(months)
    static["vintage"] = static["origination_date"].dt.to_period(vintage_freq).astype(str)

    ev = loss_events(months)
    ev = ev.merge(static[["asset_id", "origination_date", "vintage", "zero_balance_date"]],
                  on="asset_id", how="left")
    unmatched = ev["vintage"].isna()
    unmatched_gross_loss = float(ev.loc[unmatched, "gross_loss"].sum())
    ev = ev[~unmatched]
    window_start = min(m["period_end"].iloc[0] for m in months.values()).to_period("M").to_timestamp()
    pre_window_co = ev["zero_balance_date"].notna() & (ev["zero_balance_date"] < window_start)
    pre_window_recovery = float(ev.loc[pre_window_co, "recovery"].sum())
    ev.loc[pre_window_co, "recovery"] = 0.0
    ev["age"] = age_months(ev["period_end"], ev["origination_date"])

    cohort = (static.groupby("vintage")
                    .agg(n_loans=("asset_id", "size"), cohort_orig_balance=("original_balance", "sum")))
    # Age range over which every loan of the vintage was inside the window.
    first, last = min(months), max(months)
    pe_first = months[first]["period_end"].iloc[0]
    pe_last = months[last]["period_end"].iloc[0]
    static["age_at_first"] = age_months(pd.Series(pe_first, index=static.index), static["origination_date"])
    static["age_at_last"] = age_months(pd.Series(pe_last, index=static.index), static["origination_date"])
    cohort["age_complete_from"] = static.groupby("vintage")["age_at_first"].max()
    cohort["age_complete_to"] = static.groupby("vintage")["age_at_last"].min()

    by_age = (ev.groupby(["vintage", "age"])
                .agg(gross_loss=("gross_loss", "sum"), recovery=("recovery", "sum"),
                     n_chargeoffs=("gross_loss", lambda s: int((s > 0).sum())))
                .reset_index())
    # Fill every age from 0 to the cohort's max observed age so cumsum is dense.
    full = []
    for v, g in by_age.groupby("vintage"):
        ages = pd.Index(range(0, int(g["age"].max()) + 1), name="age")
        g = g.drop(columns="vintage").set_index("age").reindex(ages, fill_value=0).reset_index()
        g["vintage"] = v
        full.append(g)
    curve = pd.concat(full, ignore_index=True)
    curve = curve.sort_values(["vintage", "age"])
    curve["cum_gross_loss"] = curve.groupby("vintage")["gross_loss"].cumsum()
    curve["cum_recovery"] = curve.groupby("vintage")["recovery"].cumsum()
    curve["cum_net_loss"] = curve["cum_gross_loss"] - curve["cum_recovery"]
    curve = curve.merge(cohort.reset_index(), on="vintage", how="left")
    curve["cnl_pct_of_orig"] = curve["cum_net_loss"] / curve["cohort_orig_balance"]
    curve["gross_pct_of_orig"] = curve["cum_gross_loss"] / curve["cohort_orig_balance"]
    curve["age_complete"] = (curve["age"] >= curve["age_complete_from"]) & (curve["age"] <= curve["age_complete_to"])
    curve.insert(0, "trust", trust)

    diag = {
        "loans_seen": int(static.shape[0]),
        "origination_date_missing": int(pd.concat([m[["asset_id"]] for m in months.values()])["asset_id"].nunique() - static.shape[0]),
        "event_rows_unmatched_to_vintage": int(unmatched.sum()),
        "loans_charged_off_before_window": int(static["zero_balance_date"].lt(window_start).sum()),
        "pre_window_chargeoff_recoveries_excluded": pre_window_recovery,
        "rereported_chargeoffs_excluded": float(ev["gross_loss_rereported"].sum()),
        "unmatched_gross_loss": unmatched_gross_loss,
        "window": (first, last),
    }
    return curve, diag
