from pathlib import Path
from typing import List

import pandas as pd
import yfinance as yf


class EarningsClient:
    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_earnings_dates(self, tickers: List[str]) -> Path:
        events = []
        for t in tickers:
            try:
                ed = yf.Ticker(t).get_earnings_dates(limit=24)
                if ed is not None and not ed.empty:
                    events.extend([{"symbol": t, "earnings_date": d} for d in ed.index])
            except Exception:
                continue

        df = pd.DataFrame(events) if events else pd.DataFrame(columns=["symbol", "earnings_date"])
        out = self.output_dir / "earnings_dates.csv"
        df.to_csv(out, index=False)
        return out
