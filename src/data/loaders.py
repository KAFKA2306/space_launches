#!/usr/bin/env python3

import logging
import re
from pathlib import Path

import pandas as pd

from src.config import Config

from ..utils.helpers import clean_numeric, read_csv_safe, standardize_date


class DataLoader:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.all_data = []

    def _finalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df.dropna(subset=["trade_date"])
        if not df.empty:
            df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def detect_file_type(self, filename):
        filename = filename.lower()

        if "tradehistory" in filename:
            if "(jp)" in filename:
                return "rakuten_jp"
            elif "(us)" in filename:
                return "rakuten_us"
            elif "(invst)" in filename:
                return "rakuten_investment"
            elif "(ch)" in filename:
                return "rakuten_ch"
        elif "savefile" in filename:
            return "sbi_domestic"
        elif "yakujo" in filename:
            return "sbi_foreign"
        elif "wise" in filename:
            return "wise"
        elif "monex" in filename:
            return "monex"
        elif "binance" in filename:
            return "binance"
        elif "assetbalance" in filename or "new_file" in filename:
            return "portfolio"

        return "unknown"

    def _standardize_columns(self, df, source_file):
        if df.empty:
            return df

        df = df.copy()
        df["trade_date"] = df["trade_date"].apply(standardize_date)
        df["settlement_date"] = df["settlement_date"].apply(standardize_date)

        numeric_columns = self.config.NUMERIC_COLUMNS
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric)

        if "transaction_type" in df.columns:

            def standardize_transaction_type(val):
                s = str(val).strip()
                if s in ["買付", "現物買", "再投資", "買"]:
                    return "buy"
                elif s in ["売付", "現物売", "売"]:
                    return "sell"
                return s.lower()

            df["transaction_type"] = df["transaction_type"].apply(standardize_transaction_type)

        if "currency" in df.columns:
            df["currency"] = df["currency"].apply(lambda x: str(x).strip().upper() if pd.notna(x) else "JPY")

        df["data_source"] = source_file

        return df

    def load_rakuten_jp_data(self, file_path):
        self.logger.info(f"Loading Rakuten JP data from {file_path}")

        df = read_csv_safe(file_path, encoding=self.config.DEFAULT_ENCODING)

        if df.empty:
            return df

        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get("rakuten_jp", {}))
        df["currency"] = "JPY"
        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_rakuten_us_data(self, file_path):
        self.logger.info(f"Loading Rakuten US data from {file_path}")

        df = read_csv_safe(file_path, encoding=self.config.DEFAULT_ENCODING)

        if df.empty:
            return df

        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get("rakuten_us", {}))
        df["currency"] = "USD"
        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_rakuten_investment_data(self, file_path):
        self.logger.info(f"Loading Rakuten investment data from {file_path}")

        df = read_csv_safe(file_path, encoding=self.config.DEFAULT_ENCODING)

        if df.empty:
            return df

        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get("rakuten_investment", {}))
        df["currency"] = df.get("currency", "JPY")
        if "security_code" not in df.columns:
            df["security_code"] = ""

        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_rakuten_ch_data(self, file_path):
        self.logger.info(f"Loading Rakuten CH data from {file_path}")

        df = read_csv_safe(file_path, encoding=self.config.DEFAULT_ENCODING)

        if df.empty:
            return df

        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get("rakuten_ch", {}))
        if "currency" not in df.columns:
            df["currency"] = "HKD"
        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_sbi_domestic_data(self, file_path):
        self.logger.info(f"Loading SBI domestic data from {file_path}")

        df = read_csv_safe(
            file_path, encoding=self.config.DEFAULT_ENCODING, skiprows=self.config.SBI_DOMESTIC_SKIP_ROWS
        )

        if df.empty:
            return df

        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get("sbi_domestic", {}))
        df["currency"] = "JPY"
        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_sbi_foreign_data(self, file_path):
        self.logger.info(f"Loading SBI foreign data from {file_path}")

        df = read_csv_safe(file_path, encoding=self.config.DEFAULT_ENCODING, skiprows=self.config.SBI_FOREIGN_SKIP_ROWS)

        if df.empty:
            return df

        df = df.rename(
            columns={
                "国内約定日": "trade_date",
                "国内受渡日": "settlement_date",
                "銘柄名": "security_name",
                "取引": "transaction_type",
                "約定数量": "quantity",
                "約定単価": "price",
                "受渡金額": "settlement_amount",
                "通貨": "currency",
                "預り区分": "account_type",
            }
        )

        if "security_name" in df.columns:
            # Improved regex to handle 1-5 chars, optional dot (e.g. BRK.B)
            # Use findall and filtering to avoid picking up "ADR", "Inc", etc.

            def extract_ticker(name):
                if not isinstance(name, str):
                    return ""
                # Find all potential matches
                matches = re.findall(self.config.TICKER_REGEX, name)
                if not matches:
                    return ""

                # Filter out common non-ticker words often found in names
                # Note: valid tickers can be 1-5 chars. "A" is valid (Agilent), "V" (Visa)
                # But "Inc" (3), "ADR" (3) are noise.
                blocklist = {
                    "ADR",
                    "ADS",
                    "INC",
                    "CORP",
                    "CO",
                    "LTD",
                    "PLC",
                    "KB",
                    "NV",
                    "SA",
                    "SE",
                    "AG",
                    "ETF",
                    "REIT",
                    "FUND",
                    "INDEX",
                    "CLASS",
                    "SERIES",
                }

                # Filter candidates - also avoid "A" if it appears to be "Class A" (hard to tell without context, but valid tickers usually at end)
                candidates = [m for m in matches if m.upper() not in blocklist]

                if not candidates:
                    return ""

                # SBI Foreign names usually end with the ticker or have it near the end
                # e.g. "Name ADR Ticker"
                return candidates[-1]

            df["security_code"] = df["security_name"].apply(extract_ticker)
        else:
            df["security_code"] = ""

        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_wise_data(self, file_path):
        """Load Wise transfer data - note: these are transfers, not stock trades."""
        self.logger.info(f"Loading Wise data from {file_path}")

        df = read_csv_safe(file_path, encoding="utf-8")

        if df.empty:
            return df

        # Wise files are transfer records, not stock trades
        # Only import if it looks like a stock transaction file
        if "stock" in file_path.name.lower():
            # Map columns for Wise stock transactions
            column_mapping = {
                "作成日": "trade_date",
                "完了日": "settlement_date",
                "送金額（手数料差し引き後）": "amount",
                "送金元通貨": "currency",
                "備考": "security_name",
            }
            df = df.rename(columns=column_mapping)

            # Wise stock files may contain asset transfers
            if "ID" in df.columns and df["ID"].str.contains("ASSETS", na=False).any():
                self.logger.info("Wise file contains asset transfer records")
                df["transaction_type"] = df.apply(
                    lambda row: "buy" if "WITHDRAWAL" not in str(row.get("ID", "")) else "sell", axis=1
                )
            else:
                self.logger.info("Wise file doesn't appear to contain tradable assets, skipping")
                return pd.DataFrame()

            df = self._standardize_columns(df, file_path.name)
            self.logger.info(f"Successfully loaded {len(df)} Wise stock records from {file_path.name}")
            return df
        else:
            self.logger.info(f"Skipping non-stock Wise file: {file_path.name}")
            return pd.DataFrame()

    def load_monex_data(self, file_path):
        """Load Monex broker trading data."""
        self.logger.info(f"Loading Monex data from {file_path}")

        # Monex files have a header row with creation date that needs to be skipped
        df = read_csv_safe(file_path, encoding="shift_jis", skiprows=1)

        if df.empty:
            return df

        # Map Monex columns to standard format
        column_mapping = {
            "約定日": "trade_date",
            "受渡日": "settlement_date",
            "口座": "account_type",
            "商品": "product_type",
            "取引": "transaction_type",
            "銘柄コード": "security_code",
            "銘柄名": "security_name",
            "数量（株/口）/返済数量": "quantity",
            "単価/返済約定単価": "price",
            "手数料": "commission",
            "税金(手数料消費税及び譲渡益税)": "tax",
            "受渡金額(円)": "settlement_amount",
        }
        df = df.rename(columns=column_mapping)

        # Filter out non-trade rows (like deposits)
        if "transaction_type" in df.columns:
            # Keep only actual trades (買付, 売付, etc.)
            valid_transactions = df["transaction_type"].notna() & df["transaction_type"].str.contains(
                "買付|売付|お買付|お売付", na=False
            )
            df = df[valid_transactions]

        # Filter out MRF (Money Reserve Fund) records - these are cash management, not investments
        if "security_name" in df.columns:
            mrf_mask = df["security_name"].str.contains("ＭＲＦ|MRF", na=False)
            if mrf_mask.any():
                self.logger.info(f"Filtering out {mrf_mask.sum()} MRF (Money Reserve Fund) records")
                df = df[~mrf_mask]

        # Ensure security_code is string
        if "security_code" in df.columns:
            df["security_code"] = df["security_code"].astype(str).replace("nan", "")
            # Fix float-string conversion issue (e.g. "8223.0" -> "8223")
            df["security_code"] = df["security_code"].apply(lambda x: x.replace(".0", "") if x.endswith(".0") else x)

        df["currency"] = "JPY"
        df = self._standardize_columns(df, file_path.name)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_binance_data(self, file_path):
        """Load Binance trading data from zip file containing xlsx."""
        import io
        import zipfile

        self.logger.info(f"Loading Binance data from {file_path}")

        try:
            with zipfile.ZipFile(file_path, "r") as z:
                xlsx_files = [f for f in z.namelist() if f.endswith(".xlsx")]
                if not xlsx_files:
                    self.logger.warning(f"No xlsx files found in {file_path}")
                    return pd.DataFrame()

                xlsx_name = xlsx_files[0]
                self.logger.info(f"Reading {xlsx_name} from zip")

                with z.open(xlsx_name) as f:
                    df = pd.read_excel(io.BytesIO(f.read()))

        except RuntimeError as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                self.logger.warning(f"Binance zip file is password-protected: {file_path}")
                return pd.DataFrame()
            raise
        except Exception as e:
            self.logger.error(f"Failed to read Binance zip: {e}")
            return pd.DataFrame()

        if df.empty:
            return df

        # Map Binance columns to standard format
        # Typical Binance columns: Time, Pair, Side, Price, Executed, Amount, Fee
        column_mapping = {
            "Time": "trade_date",
            "UTC_Time": "trade_date",
            "Date(UTC)": "trade_date",
            "Pair": "security_code",
            "Symbol": "security_code",
            "Side": "transaction_type",
            "Type": "transaction_type",
            "Operation": "transaction_type",
            "Price": "price",
            "Executed": "quantity",
            "Filled": "quantity",
            "Amount": "amount",
            "Total": "amount",
            "Fee": "commission",
            "Coin": "currency",
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        # Standardize transaction types
        if "transaction_type" in df.columns:
            df["transaction_type"] = df["transaction_type"].apply(
                lambda x: (
                    "buy"
                    if str(x).upper() in ["BUY", "DEPOSIT"]
                    else "sell"
                    if str(x).upper() in ["SELL", "WITHDRAW"]
                    else str(x).lower()
                )
            )

        df["data_source"] = file_path.name
        df = self._finalize_dataframe(df)

        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_portfolio_data(self, file_path):
        self.logger.info(f"Loading portfolio snapshot from {file_path}")

        try:
            if "assetbalance" in file_path.name.lower():
                return self._parse_assetbalance_file(file_path)
            elif "new_file" in file_path.name.lower():
                return self._parse_portfolio_listing_file(file_path)
        except Exception as e:
            self.logger.warning(f"Failed to load portfolio data from {file_path}: {e}")

        return pd.DataFrame()

    def _parse_assetbalance_file(self, file_path):
        portfolio_data = []
        try:
            with open(file_path, "r", encoding="shift_jis") as f:
                lines = f.readlines()

            in_holdings = False
            for i, line in enumerate(lines):
                if "保有商品" in line:
                    in_holdings = True
                    continue
                if in_holdings and "合計" in line:
                    break
                if in_holdings and len(line.split(",")) >= 10:
                    try:
                        fields = line.strip().split(",")
                        if len(fields) > 5 and fields[1] and fields[1] != "-":
                            portfolio_data.append(
                                {
                                    "security_code": fields[1],
                                    "security_name": fields[2] if len(fields) > 2 else "",
                                    "quantity": float(fields[4]) if len(fields) > 4 and fields[4] else 0,
                                    "data_source": file_path.name,
                                }
                            )
                    except Exception:
                        continue

            df = pd.DataFrame(portfolio_data)
            self.logger.info(f"Parsed {len(df)} holdings from assetbalance file")
            return df
        except Exception as e:
            self.logger.warning(f"Error parsing assetbalance file: {e}")
            return pd.DataFrame()

    def _parse_portfolio_listing_file(self, file_path):
        portfolio_data = []
        try:
            with open(file_path, "r", encoding="shift_jis") as f:
                lines = f.readlines()

            for line in lines:
                if len(line.split(",")) >= 8:
                    try:
                        fields = line.strip().split(",")
                        security_info = fields[0].strip()
                        if security_info and any(c.isdigit() for c in security_info):
                            if " " in security_info:
                                code, name = security_info.split(" ", 1)
                            else:
                                code, name = security_info, ""

                            portfolio_data.append(
                                {
                                    "security_code": code,
                                    "security_name": name,
                                    "quantity": float(fields[2]) if len(fields) > 2 and fields[2] else 0,
                                    "data_source": file_path.name,
                                }
                            )
                    except Exception:
                        continue

            df = pd.DataFrame(portfolio_data)
            self.logger.info(f"Parsed {len(df)} holdings from portfolio listing file")
            return df
        except Exception as e:
            self.logger.warning(f"Error parsing portfolio listing file: {e}")
            return pd.DataFrame()

    def _try_codes_style_processing(self, file_path):
        try:
            encodings = Config.get("fallback_encodings", ["shift_jis", "utf-8"])
            skiprows_options = [0, 5]

            for encoding in encodings:
                for skiprows in skiprows_options:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, skiprows=skiprows)
                        if not df.empty and len(df.columns) >= 5:
                            df["data_source"] = file_path.name
                            self.logger.info(
                                f"Successfully read {file_path.name} with encoding={encoding}, skiprows={skiprows}"
                            )
                            return df
                    except Exception:
                        continue

            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"CODES-style processing failed for {file_path}: {e}")
            return pd.DataFrame()

    def load_all_broker_data(self, data_dir):
        self.logger.info(f"Loading data from all brokers in {data_dir} (CODES-enhanced)")
        self.logger.info("Using direct file processing approach inspired by CODES/1concat.py...")

        all_trades_data = []
        # Find CSV files
        csv_files = list(Path(data_dir).rglob("*.csv"))
        # Also find zip files (for Binance)
        zip_files = list(Path(data_dir).rglob("*.zip"))
        all_files = csv_files + zip_files
        self.logger.info(f"Found {len(csv_files)} CSV files and {len(zip_files)} zip files")

        for data_file in all_files:
            try:
                file_type = self.detect_file_type(data_file.name)
                self.logger.info(f"Detected file type '{file_type}' for {data_file.name}")

                self.logger.info(f"Loading file: {data_file}")

                if file_type == "rakuten_jp":
                    df = self.load_rakuten_jp_data(data_file)
                elif file_type == "rakuten_us":
                    df = self.load_rakuten_us_data(data_file)
                elif file_type == "rakuten_investment":
                    df = self.load_rakuten_investment_data(data_file)
                elif file_type == "rakuten_ch":
                    df = self.load_rakuten_ch_data(data_file)
                elif file_type == "sbi_domestic":
                    df = self.load_sbi_domestic_data(data_file)
                elif file_type == "sbi_foreign":
                    df = self.load_sbi_foreign_data(data_file)
                elif file_type == "wise":
                    df = self.load_wise_data(data_file)
                elif file_type == "monex":
                    df = self.load_monex_data(data_file)
                elif file_type == "binance":
                    df = self.load_binance_data(data_file)
                elif file_type == "portfolio":
                    df = self.load_portfolio_data(data_file)
                else:
                    self.logger.info(f"Unknown file type for {data_file.name}, trying CODES-style direct processing")
                    df = self._try_codes_style_processing(data_file)

                if df is not None and not df.empty:
                    all_trades_data.append(df)

            except Exception as e:
                self.logger.error(f"Error loading {data_file}: {e}")
                continue

        if not all_trades_data:
            self.logger.error("No trading data loaded successfully")
            return None

        combined_df = pd.concat(all_trades_data, ignore_index=True)
        self.logger.info(f"Combined data: {len(combined_df)} total records")

        if combined_df.empty:
            return combined_df

        combined_df = combined_df.copy()
        combined_df["trade_date"] = pd.to_datetime(combined_df["trade_date"], errors="coerce")
        combined_df = combined_df.dropna(subset=["trade_date"])
        if not combined_df.empty:
            combined_df = combined_df.sort_values("trade_date").reset_index(drop=True)

        return combined_df
