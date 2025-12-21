"""Pipeline status tracking for TraHist.

Per design spec (Section 4): pipeline_status.csv records success/failure of each stage.
"""

import csv
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.config import Config


@dataclass
class PipelineStatus:
    """Status tracking for a single pipeline run."""

    mode: str = ""  # "fetch" or "run"
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = ""

    # Stage completion flags
    stage_raw_loaded: bool = False
    stage_resources_read: bool = False  # Per design spec: resources read successfully
    stage_unified_written: bool = False
    stage_market_updated: str = "skipped"  # ran / skipped / failed
    stage_holdings_computed: bool = False

    # Metrics
    unified_rows: int = 0
    unified_schema_ok: bool = False
    errors_count: int = 0

    def mark_complete(self):
        """Mark the pipeline run as complete."""
        self.finished_at = datetime.now().isoformat()

    def is_success(self) -> bool:
        """
        Check if the pipeline run was successful.
        Per design spec: fetch and run have different success criteria.
        """
        if self.errors_count > 0:
            return False

        if self.mode == "fetch":
            # fetch success: raw loaded + market update didn't fail
            return self.stage_raw_loaded and self.stage_market_updated in ("ran", "skipped")

        if self.mode == "run":
            # run success: raw + resources + unified all completed
            return self.stage_raw_loaded and self.stage_resources_read and self.stage_unified_written

        # Default: require everything (backward compatibility)
        return self.stage_raw_loaded and self.stage_unified_written and self.stage_market_updated != "failed"


def write_pipeline_status(status: PipelineStatus) -> Path:
    """
    Write pipeline status to CSV file.
    Per design spec: This file must exist for a run to be considered successful.
    """
    status_file = Config.UNIFIED_DATA_DIR / "pipeline_status.csv"

    # Ensure directory exists
    status_file.parent.mkdir(parents=True, exist_ok=True)

    # Write status as single-row CSV (overwrite mode)
    with open(status_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "mode",
                "run_id",
                "started_at",
                "finished_at",
                "stage_raw_loaded",
                "stage_resources_read",
                "stage_unified_written",
                "stage_market_updated",
                "stage_holdings_computed",
                "unified_rows",
                "unified_schema_ok",
                "errors_count",
            ]
        )
        writer.writerow(
            [
                status.mode,
                status.run_id,
                status.started_at,
                status.finished_at,
                status.stage_raw_loaded,
                status.stage_resources_read,
                status.stage_unified_written,
                status.stage_market_updated,
                status.stage_holdings_computed,
                status.unified_rows,
                status.unified_schema_ok,
                status.errors_count,
            ]
        )

    return status_file


def read_pipeline_status() -> PipelineStatus | None:
    """Read the latest pipeline status from CSV."""
    status_file = Config.UNIFIED_DATA_DIR / "pipeline_status.csv"

    if not status_file.exists():
        return None

    with open(status_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
        if not row:
            return None

        return PipelineStatus(
            run_id=row["run_id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            stage_raw_loaded=row["stage_raw_loaded"] == "True",
            stage_resources_read=row.get("stage_resources_read", "False") == "True",
            stage_unified_written=row["stage_unified_written"] == "True",
            stage_market_updated=row["stage_market_updated"],
            stage_holdings_computed=row["stage_holdings_computed"] == "True",
            unified_rows=int(row["unified_rows"]),
            unified_schema_ok=row["unified_schema_ok"] == "True",
            errors_count=int(row["errors_count"]),
        )
