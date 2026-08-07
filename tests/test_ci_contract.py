from pathlib import Path

import pandas as pd

from src.data.loaders import DataLoader
from src.market.currency_converter import CurrencyConverter
from src.market.data_converter import DataConverter
from src.utils.helpers import clean_numeric


def test_task_test_is_non_destructive():
    taskfile = Path("Taskfile.yml").read_text(encoding="utf-8")
    test_section = taskfile.split("\n  test:\n", 1)[1].split("\n  ci:\n", 1)[0]

    assert "pytest" in test_section
    assert "--fix" not in test_section
    assert "--write" not in test_section


def test_task_lint_uses_check_modes_only():
    taskfile = Path("Taskfile.yml").read_text(encoding="utf-8")
    lint_section = taskfile.split("\n  lint:\n", 1)[1].split("\n  test:\n", 1)[0]

    assert "ruff check ." in lint_section
    assert "ruff format --check ." in lint_section
    assert "prettier@3.9.6 --check" in lint_section
    assert "--fix" not in lint_section
    assert "--write" not in lint_section


def test_japanese_numeric_normalization_fixture():
    assert clean_numeric("１００,０００円") == 100000.0
    assert clean_numeric("100,000(499)") == 100000.0


def test_loader_normalizes_order_and_preserves_duplicate_trade_rows():
    loader = DataLoader(config=None)
    source = pd.DataFrame(
        {
            "trade_date": ["2024-01-03", "invalid", "2024-01-02", "2024-01-02"],
            "security_code": ["AAPL", "BAD", "MSFT", "MSFT"],
            "quantity": [1, 1, 2, 2],
        }
    )

    result = loader._finalize_dataframe(source)

    assert result["trade_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-02",
        "2024-01-02",
        "2024-01-03",
    ]
    # Identical broker records must not be silently discarded: separate fills can be identical.
    assert (result["security_code"] == "MSFT").sum() == 2


def test_jpy_conversion_uses_fixture_exchange_rate():
    converter = CurrencyConverter(config=None)
    converter.forex_data = pd.DataFrame(
        {"USDJPY": [150.0]},
        index=pd.to_datetime(["2024-01-02"]),
    )

    price_jpy, amount_jpy, info = converter.convert_to_jpy_unified_price(
        {
            "security_name": "Apple Inc.",
            "security_code": "AAPL",
            "currency": "USD",
            "price": 10,
            "quantity": 2,
            "settlement_amount": 20,
            "trade_date": "2024-01-02",
        }
    )

    assert price_jpy == 1500.0
    assert amount_jpy == 3000.0
    assert info["exchange_rate"] == 150.0


def test_fund_mapping_exact_match_fixture():
    converter = object.__new__(DataConverter)
    converter.comprehensive_fund_dict = {
        "funds": {
            "Vanguard Total World Stock Index Fund": {
                "ticker": "VT",
                "aliases": [],
            }
        }
    }
    converter.security_mapping = {}

    assert converter._find_ticker_for_fund("Vanguard Total World Stock Index Fund") == "VT"


def test_unsafe_japanese_fund_to_us_etf_mapping_is_rejected():
    converter = object.__new__(DataConverter)
    converter.comprehensive_fund_dict = {
        "funds": {
            "eMAXIS Slim 米国株式": {
                "ticker": "VOO",
                "aliases": [],
            }
        }
    }
    converter.security_mapping = {}

    assert converter._find_ticker_for_fund("eMAXIS Slim 米国株式") is None
