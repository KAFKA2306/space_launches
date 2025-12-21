import os
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


def load_ff5(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    req = {"date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf"}
    assert req.issubset(df.columns), f"Missing: {req - set(df.columns)}"
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.index = df.index + pd.offsets.MonthEnd(0)
    assert df.max().max() <= 1.0 and df.min().min() >= -1.0, "Expected decimal"
    return df


def load_earnings(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    assert {"symbol", "earnings_date"}.issubset(df.columns)
    df["earnings_date"] = pd.to_datetime(df["earnings_date"])
    return df


class StrategyEngine:
    def filter_by_event(self, ret: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
        mask = pd.DataFrame(False, index=ret.index, columns=ret.columns)
        ev["me"] = ev["earnings_date"].dt.to_period("M").dt.to_timestamp("M") + pd.offsets.MonthEnd(0)
        for _, r in ev[ev["symbol"].isin(ret.columns)].iterrows():
            if r["me"] in mask.index:
                mask.at[r["me"], r["symbol"]] = True
        return ret.where(mask)

    def prepare(self, strat: pd.DataFrame, ff5: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        assert "strategy_return" in strat.columns
        df = pd.concat([strat, ff5], axis=1, join="inner").dropna()
        assert not df.empty, "No overlapping data"
        y = (df["strategy_return"] - df["rf"]).values
        X = np.column_stack([np.ones(len(df)), df[["mkt_rf", "smb", "hml", "rmw", "cma"]].values])
        return X, y, df


def run_ols(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    n, k = X.shape
    assert n > k
    XTX = X.T @ X
    beta = np.linalg.solve(XTX, X.T @ y)
    resid = y - X @ beta
    mse = np.sum(resid**2) / (n - k)
    se = np.sqrt(np.diag(mse * np.linalg.pinv(XTX)))
    sst = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - (np.sum(resid**2) / sst) if sst else 0
    return {"beta": beta, "std_err": se, "t_stats": beta / se, "r2": r2, "n": n}
