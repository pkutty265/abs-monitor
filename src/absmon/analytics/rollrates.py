"""Month-over-month delinquency transition matrices from ABS-EE loan-level parquet.

States. Active loans are bucketed on currentDelinquencyStatus (days past due):
current (0), dq1_30, dq31_60, dq61_90, dq91p. Two absorbing exits come from
zeroBalanceCode: charged_off (code 4) and paid_off (codes 1 prepaid/matured, 2 sold to
a third party, 3 repurchased — all three leave the pool at par rather than as a credit
loss, so they are pooled). A loan that is active in month t and simply absent (or a bare
recovery stub) in t+1 is `vanished`.

Vanished loans, measured on the real data (v1 pull, 23/20/23 month-pairs):
  Ford      0 of 700k active-origin transitions — every exit is coded in its final month.
  CarMax    1 of 1.13M — closed loans are retained forever, nothing drops.
  Santander 89 of 960k — 93% carried balance_end == 0 in month t, i.e. payoffs the
            servicer dropped without ever printing a code 1.
At <= 0.01% the choice is immaterial; `vanished` is kept as an explicit destination
column (in the denominator, not folded into paid_off, not excluded) so it stays visible.
Fold it into paid_off if you prefer a closed state space.

Origins are active loans only, so charge-off reversals (code 4 in t, active in t+1:
145 at CarMax, 52 at Santander over the window) never enter the matrix; they are simply
new active origins from t+1 onward.

Denominators include paid_off: each row of the matrix sums to 1 over every destination,
including prepayment. Survival-conditional rates (what analysts often quote as
"roll rates") are share / (1 - share_paid_off) and are provided alongside.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

from absmon.edgar.absee import CHARGED_OFF_CODE

BUCKETS = ["current", "dq1_30", "dq31_60", "dq61_90", "dq91p"]
EXITS = ["charged_off", "paid_off"]
STATES = BUCKETS + EXITS + ["vanished"]
PAID_OFF_CODES = {"1", "2", "3"}

LOAD_COLS = ["asset_id", "period_end", "balance_end", "delinq_days", "zero_balance_code",
             "zero_balance_date", "chargeoff_amount", "recovery_amount", "origination_date",
             "original_balance"]


def load_months(trust_dir: Path, columns: list[str] = LOAD_COLS) -> dict[str, pd.DataFrame]:
    """{'YYYY-MM': frame} for every parquet in a trust directory, oldest first."""
    return {f.stem: pd.read_parquet(f, columns=columns)
            for f in sorted(Path(trust_dir).glob("*.parquet"))}


def bucket_days(days: pd.Series) -> pd.Series:
    d = pd.to_numeric(days, errors="coerce")
    return pd.cut(d, bins=[-np.inf, 0, 30, 60, 90, np.inf], labels=BUCKETS).astype(object)


def state_of(df: pd.DataFrame) -> pd.Series:
    """Per-record state for one month; None for bare stub records (no balance, no code)."""
    s = pd.Series(None, index=df.index, dtype=object)
    active = df["zero_balance_code"].isna() & df["balance_end"].notna()
    s[active] = bucket_days(df.loc[active, "delinq_days"])
    s[df["zero_balance_code"] == CHARGED_OFF_CODE] = "charged_off"
    s[df["zero_balance_code"].isin(PAID_OFF_CODES)] = "paid_off"
    return s


def transitions(prev: pd.DataFrame, curr: pd.DataFrame) -> pd.DataFrame:
    """One row per loan active in `prev`: origin state, destination state, origin balance."""
    p = prev.set_index("asset_id")
    ps = state_of(p)
    origin = ps[ps.isin(BUCKETS)]
    c = curr.set_index("asset_id")
    cs = state_of(c)
    dest = cs.reindex(origin.index)
    dest = dest.where(dest.notna(), "vanished")  # absent, or present only as a stub
    return pd.DataFrame({
        "asset_id": origin.index,
        "origin": origin.values,
        "dest": dest.values,
        "balance": p.loc[origin.index, "balance_end"].values,
    })


def matrix(trans: pd.DataFrame) -> pd.DataFrame:
    """Tidy origin x dest table with counts, balances, and both share versions."""
    g = trans.groupby(["origin", "dest"]).agg(n=("asset_id", "size"), balance=("balance", "sum"))
    idx = pd.MultiIndex.from_product([BUCKETS, STATES], names=["origin", "dest"])
    g = g.reindex(idx, fill_value=0).reset_index()
    tot = g.groupby("origin")[["n", "balance"]].transform("sum")
    g["share_count"] = g["n"] / tot["n"].replace(0, np.nan)
    g["share_balance"] = g["balance"] / tot["balance"].replace(0, np.nan)
    po = g[g["dest"] == "paid_off"].set_index("origin")
    g["share_count_survival"] = g["share_count"] / (1 - g["origin"].map(po["share_count"]))
    g["share_balance_survival"] = g["share_balance"] / (1 - g["origin"].map(po["share_balance"]))
    for c in ("share_count_survival", "share_balance_survival"):
        g.loc[g["dest"] == "paid_off", c] = np.nan
    return g


def roll_rates(trust_dir: Path, trust: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(monthly, pooled) tidy transition tables for one trust."""
    months = load_months(trust_dir)
    labels = list(months)
    monthly, all_trans = [], []
    for a, b in zip(labels, labels[1:]):
        t = transitions(months[a], months[b])
        all_trans.append(t)
        monthly.append(matrix(t).assign(period_from=a, period_to=b))
    monthly = pd.concat(monthly, ignore_index=True).assign(trust=trust)
    pooled = matrix(pd.concat(all_trans, ignore_index=True)).assign(trust=trust)
    cols = ["trust", "period_from", "period_to", "origin", "dest", "n", "balance",
            "share_count", "share_balance", "share_count_survival", "share_balance_survival"]
    return monthly[cols], pooled[[c for c in cols if c not in ("period_from", "period_to")]]


def pivot(tidy: pd.DataFrame, value: str = "share_balance") -> pd.DataFrame:
    return tidy.pivot(index="origin", columns="dest", values=value).reindex(index=BUCKETS, columns=STATES)
