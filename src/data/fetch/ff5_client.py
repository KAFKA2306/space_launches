from datetime import datetime
from pathlib import Path

import pandas as pd
import pandas_datareader.data as web


class FF5Client:
    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_ff5_factors(self, start_date: datetime, end_date: datetime) -> Path:
        print("Downloading FF5 data...")
        ds = web.DataReader("F-F_Research_Data_5_Factors_2x3", "famafrench", start=start_date, end=end_date)
        df = ds[0] / 100.0
        df.rename(
            columns={"Mkt-RF": "mkt_rf", "SMB": "smb", "HML": "hml", "RMW": "rmw", "CMA": "cma", "RF": "rf"},
            inplace=True,
        )

        if isinstance(df.index, pd.PeriodIndex):
            df.index = df.index.to_timestamp(freq="M")
        df.index.name = "date"
        df = df[(df.index >= start_date) & (df.index <= end_date)]

        out = self.output_dir / "ff5_factors.csv"
        df.to_csv(out)
        return out
