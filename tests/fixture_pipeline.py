"""Deterministic, network-denied fixture replay for the production trade pipeline."""

from __future__ import annotations

import argparse
import logging
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from src.config import Config
from src.data.fetch.pipeline import create_unified_csv, load_and_process_trades

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "raw"
REQUIRED_TRADE_COLUMNS = {
    "trade_date",
    "security_code",
    "security_name",
    "transaction_type",
    "quantity",
    "price",
    "amount_jpy",
    "currency",
    "data_source",
}
STATUS_COLUMNS = ["stage", "status", "row_count", "network"]


class FixtureConfig:
    """Minimal production-compatible config rooted entirely in a temporary directory."""

    COLUMN_MAPPINGS = Config.COLUMN_MAPPINGS
    DEFAULT_ENCODING = "utf-8"
    FALLBACK_ENCODINGS = ["utf-8", "shift_jis"]
    NUMERIC_COLUMNS = [
        "quantity",
        "price",
        "settlement_amount",
        "commission",
        "tax",
        "amount",
        "exchange_rate",
    ]
    SBI_DOMESTIC_SKIP_ROWS = 0
    SBI_FOREIGN_SKIP_ROWS = 0
    FALLBACK_FOREX_RATES = {"USD": 150.0, "HKD": 19.0, "EUR": 165.0, "CNY": 21.0}
    FUND_INDICATORS = ["fund", "投資信託", "ファンド"]
    ETF_INDICATORS = ["ETF"]

    def __init__(self, root: Path):
        self.BASE_DIR = root
        self.DATA_DIR = root / "data"
        self.RAW_DATA_DIR = self.DATA_DIR / "raw"
        self.INTERIM_DIR = self.DATA_DIR / "interim"
        self.TRADES_DATA_DIR = self.INTERIM_DIR / "trades"
        self.UNIFIED_DATA_DIR = self.DATA_DIR / "unified"
        self.RESOURCES_DIR = root / "resources"
        self.MARKET_DATA_DIR = self.RESOURCES_DIR

    @staticmethod
    def get(key, default=None):
        values = {
            "fallback_encodings": FixtureConfig.FALLBACK_ENCODINGS,
            "fund_indicators": FixtureConfig.FUND_INDICATORS,
            "etf_indicators": FixtureConfig.ETF_INDICATORS,
        }
        return values.get(key, default)

    def ensure_directories(self):
        for path in (
            self.RAW_DATA_DIR,
            self.TRADES_DATA_DIR,
            self.UNIFIED_DATA_DIR,
            self.RESOURCES_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)


@contextmanager
def deny_network():
    """Fail immediately if the fixture replay attempts a socket connection."""

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def blocked(*_args, **_kwargs):
        raise AssertionError("fixture pipeline attempted network access")

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex


def run_fixture_pipeline(work_root: Path) -> tuple[Path, Path]:
    config = FixtureConfig(work_root)
    config.ensure_directories()
    for source in RAW_FIXTURE_DIR.glob("*"):
        if source.is_file():
            shutil.copy2(source, config.RAW_DATA_DIR / source.name)

    logger = logging.getLogger("fixture_pipeline")
    with deny_network():
        trades = load_and_process_trades(config, logger)
        if trades is None or trades.empty:
            raise AssertionError("fixture trade loader produced no rows")
        unified_path = create_unified_csv(config, logger)
        if unified_path is None:
            raise AssertionError("fixture unified conversion failed")

    unified = pd.read_csv(unified_path)
    missing = REQUIRED_TRADE_COLUMNS.difference(unified.columns)
    if missing:
        raise AssertionError(f"unified fixture missing required columns: {sorted(missing)}")
    if len(unified) != 3:
        raise AssertionError(f"expected 3 fixture trades, got {len(unified)}")
    if (unified["security_code"].astype(str) == "7203").sum() != 2:
        raise AssertionError("identical broker fills were unexpectedly deduplicated")
    if unified["currency"].unique().tolist() != ["JPY"]:
        raise AssertionError("fixture currency normalization is not deterministic JPY")

    status_path = config.UNIFIED_DATA_DIR / "pipeline_status.csv"
    status = pd.DataFrame(
        [
            {"stage": "load", "status": "success", "row_count": len(trades), "network": "denied"},
            {"stage": "unify", "status": "success", "row_count": len(unified), "network": "denied"},
        ],
        columns=STATUS_COLUMNS,
    )
    status.to_csv(status_path, index=False)
    return Path(unified_path), status_path


def _canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def update_expected(expected_dir: Path):
    expected_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trahist-fixture-") as tmp:
        unified, status = run_fixture_pipeline(Path(tmp))
        shutil.copy2(unified, expected_dir / "trades_unified.csv")
        shutil.copy2(status, expected_dir / "pipeline_status.csv")


def check_expected(expected_dir: Path):
    with tempfile.TemporaryDirectory(prefix="trahist-fixture-") as tmp:
        unified, status = run_fixture_pipeline(Path(tmp))
        pairs = [
            (expected_dir / "trades_unified.csv", unified),
            (expected_dir / "pipeline_status.csv", status),
        ]
        for expected, actual in pairs:
            if not expected.exists():
                raise AssertionError(f"missing expected fixture output: {expected}")
            if _canonical_bytes(expected) != _canonical_bytes(actual):
                raise AssertionError(
                    f"fixture output drifted: {expected.name}; run `task fixtures:update`, review, and commit the diff"
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "expected",
    )
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    if args.update:
        update_expected(args.expected)
    else:
        check_expected(args.expected)


if __name__ == "__main__":
    main()
