"""Generate privacy-minimal IFA onboarding deliverables from unified TraHist data.

The generator consumes only the offline pipeline's normalized outputs. It never reads
or copies raw broker files, and it fails closed on unsupported schemas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
from collections import defaultdict
from pathlib import Path

CASE_ID_RE = re.compile(r"^case-[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$")
REQUIRED_TRADE_COLUMNS = {
    "trade_date",
    "security_name",
    "transaction_type",
    "quantity",
    "amount_jpy",
    "currency",
    "data_source",
}
DELIVERABLES = (
    "trades_unified.csv",
    "holdings.csv",
    "portfolio_summary.html",
    "exceptions.csv",
    "pipeline_status.csv",
    "manifest.json",
)


class OnboardingPackError(ValueError):
    """Raised when an onboarding pack cannot be generated safely."""


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise OnboardingPackError(f"required input missing: {path.name}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise OnboardingPackError(f"empty CSV schema: {path.name}")
        return list(reader.fieldnames), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _number(
    value: str,
    *,
    field: str,
    row_number: int,
    exceptions: list[dict[str, object]],
) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = math.nan
    if not math.isfinite(number):
        exceptions.append(
            {
                "row_number": row_number,
                "code": "INVALID_NUMERIC",
                "field": field,
                "detail": "value is not a finite numeric field",
            }
        )
        return None
    return number


def _source_ref(value: str) -> str:
    """Replace a possibly identifying broker filename with a stable opaque reference."""
    return "src-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _validate_case_id(case_id: str) -> None:
    if not CASE_ID_RE.fullmatch(case_id):
        raise OnboardingPackError(
            "case_id must be an anonymous slug like 'case-demo-001' (lowercase letters, digits, hyphens only)"
        )


def _sanitize_trades(
    case_id: str, fieldnames: list[str], rows: list[dict[str, str]]
) -> tuple[list[str], list[dict[str, object]]]:
    missing = sorted(REQUIRED_TRADE_COLUMNS - set(fieldnames))
    if missing:
        raise OnboardingPackError(f"unsupported unified schema; missing columns: {', '.join(missing)}")

    output_fields = [
        "case_id",
        *[name for name in fieldnames if name != "data_source"],
        "source_ref",
    ]
    sanitized: list[dict[str, object]] = []
    for row in rows:
        item: dict[str, object] = {"case_id": case_id}
        item.update({name: row.get(name, "") for name in fieldnames if name != "data_source"})
        item["source_ref"] = _source_ref(row.get("data_source", ""))
        sanitized.append(item)
    return output_fields, sanitized


def _build_holdings_and_exceptions(
    case_id: str, rows: list[dict[str, str]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    positions: dict[tuple[str, str], dict[str, float | str]] = defaultdict(
        lambda: {"quantity": 0.0, "cost_basis_jpy": 0.0, "currency": ""}
    )
    exceptions: list[dict[str, object]] = []

    for row_number, row in enumerate(rows, start=2):
        name = row.get("security_name", "").strip()
        tx_type = row.get("transaction_type", "").strip().lower()
        currency = row.get("currency", "").strip()
        symbol = (row.get("security_code") or row.get("original_security_code") or name).strip()

        missing_fields = [
            field
            for field in (
                "trade_date",
                "security_name",
                "transaction_type",
                "quantity",
                "amount_jpy",
                "currency",
            )
            if not row.get(field, "").strip()
        ]
        if missing_fields:
            exceptions.append(
                {
                    "row_number": row_number,
                    "code": "MISSING_REQUIRED_VALUE",
                    "field": ";".join(missing_fields),
                    "detail": "required normalized value is blank",
                }
            )
            continue

        quantity = _number(
            row["quantity"],
            field="quantity",
            row_number=row_number,
            exceptions=exceptions,
        )
        amount_jpy = _number(
            row["amount_jpy"],
            field="amount_jpy",
            row_number=row_number,
            exceptions=exceptions,
        )
        if quantity is None or amount_jpy is None:
            continue
        if quantity < 0 or amount_jpy < 0:
            exceptions.append(
                {
                    "row_number": row_number,
                    "code": "NEGATIVE_VALUE",
                    "field": "quantity/amount_jpy",
                    "detail": "normalized quantities and JPY amounts must be non-negative",
                }
            )
            continue

        key = (name, symbol)
        position = positions[key]
        position["currency"] = currency
        current_qty = float(position["quantity"])
        current_cost = float(position["cost_basis_jpy"])

        if tx_type == "buy":
            position["quantity"] = current_qty + quantity
            position["cost_basis_jpy"] = current_cost + amount_jpy
        elif tx_type == "sell":
            if quantity > current_qty:
                exceptions.append(
                    {
                        "row_number": row_number,
                        "code": "NEGATIVE_INVENTORY",
                        "field": "quantity",
                        "detail": ("sell quantity exceeds known inventory; holding was not silently clamped"),
                    }
                )
                continue
            average_cost = current_cost / current_qty if current_qty else 0.0
            position["quantity"] = current_qty - quantity
            position["cost_basis_jpy"] = max(0.0, current_cost - average_cost * quantity)
        else:
            exceptions.append(
                {
                    "row_number": row_number,
                    "code": "NON_POSITION_TRANSACTION",
                    "field": "transaction_type",
                    "detail": (
                        f"{tx_type or 'blank'} does not change holdings and remains present in trades_unified.csv"
                    ),
                }
            )

    holdings: list[dict[str, object]] = []
    for (name, symbol), position in sorted(positions.items()):
        quantity = float(position["quantity"])
        if quantity <= 0:
            continue
        cost = float(position["cost_basis_jpy"])
        holdings.append(
            {
                "case_id": case_id,
                "security_name": name,
                "symbol": symbol,
                "currency": position["currency"],
                "quantity": f"{quantity:.10g}",
                "cost_basis_jpy": f"{cost:.2f}",
                "average_cost_jpy": f"{(cost / quantity):.2f}",
                "valuation_status": "COST_BASIS_ONLY",
            }
        )

    return holdings, exceptions


def _pipeline_rows(
    case_id: str, fieldnames: list[str], rows: list[dict[str, str]]
) -> tuple[list[str], list[dict[str, object]]]:
    if not fieldnames:
        raise OnboardingPackError("unsupported pipeline status schema")
    output_fields = ["case_id", *fieldnames]
    return output_fields, [{"case_id": case_id, **row} for row in rows]


def _render_summary(
    case_id: str,
    trades: list[dict[str, str]],
    holdings: list[dict[str, object]],
    exceptions: list[dict[str, object]],
) -> str:
    total_cost = sum(float(row["cost_basis_jpy"]) for row in holdings)
    return f"""<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>TraHist onboarding summary</title></head>
<body>
<main data-case-id="{html.escape(case_id)}">
<h1>Portfolio onboarding summary</h1>
<dl>
<dt>Case ID</dt><dd>{html.escape(case_id)}</dd>
<dt>Normalized trades</dt><dd>{len(trades)}</dd>
<dt>Open holdings</dt><dd>{len(holdings)}</dd>
<dt>Cost basis (JPY)</dt><dd>{total_cost:.2f}</dd>
<dt>Exceptions requiring review</dt><dd>{len(exceptions)}</dd>
</dl>
<p><strong>Data-quality output only.</strong> This report does not provide investment advice, security recommendations, or future-return forecasts.</p>
<p>Market valuation is not inferred here. Holdings without an independently supplied current-value source are reported as <code>COST_BASIS_ONLY</code>.</p>
</main>
</body>
</html>
"""


def build_pack(*, case_id: str, unified_dir: Path, output_root: Path) -> Path:
    """Build one delivery directory from normalized, offline pipeline outputs."""
    _validate_case_id(case_id)
    if output_root.resolve() == unified_dir.resolve():
        raise OnboardingPackError("output_root must be separate from the unified input directory")

    trade_fields, trades = _read_csv(unified_dir / "trades_unified.csv")
    status_fields, status_rows = _read_csv(unified_dir / "pipeline_status.csv")
    if not trades:
        raise OnboardingPackError("trades_unified.csv contains no records")

    sanitized_fields, sanitized_trades = _sanitize_trades(case_id, trade_fields, trades)
    holdings, exceptions = _build_holdings_and_exceptions(case_id, trades)
    status_output_fields, status_output_rows = _pipeline_rows(case_id, status_fields, status_rows)

    case_dir = output_root / case_id
    if case_dir.exists():
        raise OnboardingPackError(f"delivery directory already exists: {case_dir}")
    case_dir.mkdir(parents=True)

    _write_csv(case_dir / "trades_unified.csv", sanitized_fields, sanitized_trades)
    _write_csv(
        case_dir / "holdings.csv",
        [
            "case_id",
            "security_name",
            "symbol",
            "currency",
            "quantity",
            "cost_basis_jpy",
            "average_cost_jpy",
            "valuation_status",
        ],
        holdings,
    )
    _write_csv(
        case_dir / "exceptions.csv",
        ["case_id", "row_number", "code", "field", "detail"],
        [{"case_id": case_id, **row} for row in exceptions],
    )
    _write_csv(case_dir / "pipeline_status.csv", status_output_fields, status_output_rows)
    (case_dir / "portfolio_summary.html").write_text(
        _render_summary(case_id, trades, holdings, exceptions), encoding="utf-8"
    )

    manifest = {
        "schema": "trahist.ifa-onboarding-pack.v1",
        "case_id": case_id,
        "input_boundary": ["trades_unified.csv", "pipeline_status.csv"],
        "raw_files_included": False,
        "delivery_files": list(DELIVERABLES[:-1]),
        "counts": {
            "trades": len(trades),
            "holdings": len(holdings),
            "exceptions": len(exceptions),
        },
        "limitations": [
            "DATA_QUALITY_ONLY",
            "NO_INVESTMENT_ADVICE",
            "NO_RETURN_FORECAST",
            "MARKET_VALUES_NOT_INFERRED",
        ],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return case_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an anonymous TraHist IFA onboarding delivery pack")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--unified-dir", type=Path, default=Path("data/unified"))
    parser.add_argument("--output-root", type=Path, default=Path("data/onboarding"))
    args = parser.parse_args()
    try:
        output = build_pack(
            case_id=args.case_id,
            unified_dir=args.unified_dir,
            output_root=args.output_root,
        )
    except OnboardingPackError as exc:
        parser.error(str(exc))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
