import csv
import json
from pathlib import Path

import pytest

from src.onboarding_pack import OnboardingPackError, build_pack

TRADE_FIELDS = [
    "trade_date",
    "security_code",
    "security_name",
    "transaction_type",
    "quantity",
    "amount_jpy",
    "currency",
    "data_source",
]


def write_inputs(root: Path, rows: list[list[str]]) -> Path:
    unified = root / "unified"
    unified.mkdir()
    with (unified / "trades_unified.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(TRADE_FIELDS)
        writer.writerows(rows)
    with (unified / "pipeline_status.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stage", "status"])
        writer.writerow(["normalize", "success"])
    return unified


def load_fixture_cases() -> list[dict]:
    path = Path(__file__).parent / "fixtures" / "onboarding" / "cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("fixture", load_fixture_cases(), ids=lambda fixture: fixture["case_id"])
def test_three_anonymous_fixtures_generate_complete_pack(tmp_path: Path, fixture: dict) -> None:
    unified = write_inputs(tmp_path, fixture["trades"])
    case_dir = build_pack(case_id=fixture["case_id"], unified_dir=unified, output_root=tmp_path / "out")

    assert {path.name for path in case_dir.iterdir()} == {
        "trades_unified.csv",
        "holdings.csv",
        "portfolio_summary.html",
        "exceptions.csv",
        "pipeline_status.csv",
        "manifest.json",
    }
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["case_id"] == fixture["case_id"]
    assert manifest["raw_files_included"] is False
    assert manifest["limitations"] == [
        "DATA_QUALITY_ONLY",
        "NO_INVESTMENT_ADVICE",
        "NO_RETURN_FORECAST",
        "MARKET_VALUES_NOT_INFERRED",
    ]

    trades_text = (case_dir / "trades_unified.csv").read_text(encoding="utf-8")
    assert "data_source" not in trades_text.splitlines()[0]
    for row in fixture["trades"]:
        assert row[-1] not in trades_text
    assert "source_ref" in trades_text.splitlines()[0]

    for csv_name in ("trades_unified.csv", "holdings.csv", "exceptions.csv", "pipeline_status.csv"):
        with (case_dir / csv_name).open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                assert row["case_id"] == fixture["case_id"]


def test_unsupported_schema_fails_closed(tmp_path: Path) -> None:
    unified = tmp_path / "unified"
    unified.mkdir()
    (unified / "trades_unified.csv").write_text("trade_date,security_name\n2026-01-01,Fixture\n", encoding="utf-8")
    (unified / "pipeline_status.csv").write_text("stage,status\nnormalize,success\n", encoding="utf-8")

    with pytest.raises(OnboardingPackError, match="unsupported unified schema"):
        build_pack(case_id="case-schema-fail", unified_dir=unified, output_root=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_case_id_rejects_personal_or_path_like_names(tmp_path: Path) -> None:
    unified = write_inputs(
        tmp_path,
        [["2026-01-05", "7203", "Fixture Motors", "buy", "2", "5000", "JPY", "source.csv"]],
    )
    for invalid in ("Tanaka Taro", "../customer", "CASE-001", "customer@example.com"):
        with pytest.raises(OnboardingPackError, match="case_id"):
            build_pack(case_id=invalid, unified_dir=unified, output_root=tmp_path / "out")


def test_negative_inventory_is_explicit_exception_not_silent_drop(tmp_path: Path) -> None:
    unified = write_inputs(
        tmp_path,
        [["2026-01-05", "7203", "Fixture Motors", "sell", "2", "5000", "JPY", "source.csv"]],
    )
    case_dir = build_pack(case_id="case-negative-inventory", unified_dir=unified, output_root=tmp_path / "out")

    with (case_dir / "exceptions.csv").open("r", encoding="utf-8", newline="") as handle:
        exceptions = list(csv.DictReader(handle))
    assert [row["code"] for row in exceptions] == ["NEGATIVE_INVENTORY"]
    with (case_dir / "holdings.csv").open("r", encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle)) == []


def test_existing_delivery_directory_is_not_overwritten(tmp_path: Path) -> None:
    unified = write_inputs(
        tmp_path,
        [["2026-01-05", "7203", "Fixture Motors", "buy", "2", "5000", "JPY", "source.csv"]],
    )
    output = tmp_path / "out"
    build_pack(case_id="case-repeat-safe", unified_dir=unified, output_root=output)
    with pytest.raises(OnboardingPackError, match="already exists"):
        build_pack(case_id="case-repeat-safe", unified_dir=unified, output_root=output)
