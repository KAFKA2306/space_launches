import argparse
import os
import sys

import pandas as pd

from .core import StrategyEngine, load_earnings, load_ff5, run_ols

EARNINGS = "data/raw/earnings_dates.csv"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--strategy-csv", required=True)
    p.add_argument("--ff5-path", default="data/raw/ff5_factors.csv")
    p.add_argument("--output", default="ff5_report.csv")
    p.add_argument("--use-earnings", action="store_true")
    a = p.parse_args()

    for f in [a.ff5_path, a.strategy_csv] + ([EARNINGS] if a.use_earnings else []):
        if not os.path.exists(f):
            sys.exit(f"Missing: {f}. Run 'task fetch:m'.")

    ff5 = load_ff5(a.ff5_path)
    sdf = pd.read_csv(a.strategy_csv)
    sdf["date"] = pd.to_datetime(sdf["date"])
    sdf.set_index("date", inplace=True)
    sdf.index = sdf.index + pd.offsets.MonthEnd(0)

    eng = StrategyEngine()
    if a.use_earnings:
        ear = load_earnings(EARNINGS)
        assert not ear.empty
        sdf = pd.DataFrame(eng.filter_by_event(sdf, ear).mean(axis=1), columns=["strategy_return"])
    else:
        assert "strategy_return" in sdf.columns

    X, y, _ = eng.prepare(sdf, ff5)
    res = run_ols(X, y)

    cols = ["Alpha", "MKT", "SMB", "HML", "RMW", "CMA"]
    print(pd.DataFrame({"Coef": res["beta"], "t": res["t_stats"]}, index=cols).round(4))
    print(f"R2: {res['r2']:.4f}, N: {res['n']}")
    pd.DataFrame(
        {"Factor": cols, "Coef": res["beta"], "t": res["t_stats"], "SE": res["std_err"], "R2": res["r2"]}
    ).to_csv(a.output, index=False)


if __name__ == "__main__":
    main()
