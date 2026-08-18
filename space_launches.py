from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
AUTH_REGISTRY = DATA_DIR / "authorization-registry.json"
BLUE_ORIGIN = DATA_DIR / "blue-origin-launches.json"
REUSE_EVENTS = DATA_DIR / "reuse-events.json"
DEFAULT_DATA_ROOT = DATA_DIR / "space-launches"
DEFAULT_API_DIR = ROOT / "api" / "v1" / "space-launches"
USER_AGENT = "KAFKA2306 space-launches evidence 137051370+KAFKA2306@users.noreply.github.com"
START_DATE = date(2024, 1, 1)

SOURCES = [
    {
        "source_id": "spacex-launches",
        "publisher": "SpaceX",
        "source_url": "https://content.spacex.com/api/spacex-website/launches-page-tiles",
        "required_markers": ["missionStatus", "launchDate", "launchSite", "Falcon 9"],
    },
    {
        "source_id": "rocketlab-launches",
        "publisher": "Rocket Lab",
        "source_url": "https://rocketlabcorp.com/missions/launches/",
        "required_markers": ["Completed Missions", "Electron", "Launch Complex 2"],
    },
    {
        "source_id": "faa-part450-transition",
        "publisher": "Federal Aviation Administration",
        "source_url": "https://www.faa.gov/newsroom/faa-streamlines-commercial-space-license-approvals",
        "required_markers": ["Blue Origin New Shepard", "SpaceX Falcon 9 / Falcon Heavy", "Rocket Lab Electron"],
    },
    {
        "source_id": "faa-general-statements",
        "publisher": "Federal Aviation Administration",
        "source_url": "https://www.faa.gov/newsroom/statements/general-statements",
        "required_markers": ["New Glenn", "valid for five years", "reusable New Glenn first stage"],
    },
    {
        "source_id": "spacex-starlink-2024-05-17",
        "publisher": "SpaceX",
        "source_url": "https://content.spacex.com/api/spacex-website/missions/sl-6-59",
        "required_markers": ["21st flight", "Falcon 9", "missionId"],
    },
    {
        "source_id": "rocketlab-four-of-a-kind",
        "publisher": "Rocket Lab",
        "source_url": "https://rocketlabcorp.com/updates/rocket-lab-successfully-launches-first-electron-mission-of-busy-2024-launch-schedule/",
        "required_markers": ["January 31, 2024", "successful splashdown", "first stage"],
    },
]


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_text(raw: bytes, content_type: str) -> str:
    text = raw.decode("utf-8", errors="replace")
    if content_type == "application/json" or text.lstrip().startswith(("{", "[")):
        return text
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def request_headers(url: str) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if "content.spacex.com" in url:
        headers.update({
            "Accept": "application/json",
            "Origin": "https://www.spacex.com",
            "Referer": "https://www.spacex.com/",
        })
    return headers


def fetch_source(source: dict[str, Any], data_root: Path) -> dict[str, Any]:
    request = urllib.request.Request(source["source_url"], headers=request_headers(source["source_url"]))
    raw = b""
    content_type = "application/octet-stream"
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(f"fetch {source['source_id']} attempt {attempt}/3", flush=True)
            with urllib.request.urlopen(request, timeout=35) as response:
                raw = response.read()
                content_type = response.headers.get_content_type()
            break
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    else:
        raise RuntimeError(f"primary source unavailable: {source['source_id']}") from last_error
    if len(raw) < 800:
        raise ValueError(f"primary source unexpectedly small: {source['source_id']}")
    text = source_text(raw, content_type).casefold()
    missing = [marker for marker in source["required_markers"] if marker.casefold() not in text]
    if missing:
        raise ValueError(f"source markers missing for {source['source_id']}: {missing}")
    digest = sha256(raw)
    objects = data_root / "raw" / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    if content_type == "application/json" or raw.lstrip().startswith((b"{", b"[")):
        suffix = ".json"
    elif content_type in {"text/html", "application/xhtml+xml"}:
        suffix = ".html"
    else:
        suffix = ".bin"
    path = objects / f"{digest}{suffix}"
    if not path.exists():
        path.write_bytes(raw)
    return {
        "source_id": source["source_id"],
        "publisher": source["publisher"],
        "source_url": source["source_url"],
        "sha256": digest,
        "size_bytes": len(raw),
        "content_type": content_type,
        "evidence_path": path.relative_to(data_root).as_posix(),
        "verification_mode": "live_fetched_primary",
    }


def collect(data_root: Path) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "sources": [fetch_source(source, data_root) for source in SOURCES],
    }
    payload = canonical_json(manifest)
    manifests = data_root / "raw" / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / f"{sha256(payload)}.json").write_bytes(payload)
    (data_root / "raw" / "latest-manifest.json").write_bytes(payload)
    return manifest


def verify_manifest(data_root: Path) -> dict[str, Any]:
    manifest = json.loads((data_root / "raw" / "latest-manifest.json").read_text(encoding="utf-8"))
    for source in manifest["sources"]:
        raw = (data_root / source["evidence_path"]).read_bytes()
        if sha256(raw) != source["sha256"]:
            raise ValueError(f"raw source hash mismatch: {source['source_id']}")
    return manifest


def parse_date(value: str) -> date | None:
    value = " ".join(value.replace(".", "").split())
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def parse_tables(raw: bytes) -> list[list[str]]:
    parser = TableRows()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return parser.rows


def parse_spacex(raw: bytes, source: dict[str, Any], minimum: int = 50) -> list[dict[str, Any]]:
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("SpaceX launch tiles must be a JSON list")
    records: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict) or row.get("missionStatus") != "final":
            continue
        launch_date = parse_date(str(row.get("launchDate") or ""))
        if launch_date is None or launch_date < START_DATE:
            continue
        mission_id = str(row.get("link") or "").strip()
        vehicle = str(row.get("vehicle") or "").strip()
        launch_site = str(row.get("launchSite") or "").strip()
        if not mission_id or not vehicle or not launch_site:
            raise ValueError(f"SpaceX final mission lacks identity fields: {row.get('id')}")
        records.append({
            "operator": "SpaceX",
            "mission_id": mission_id,
            "mission": str(row.get("title") or mission_id).strip(),
            "mission_type": row.get("missionType"),
            "launch_date": launch_date.isoformat(),
            "launch_time": row.get("launchTime"),
            "vehicle": vehicle,
            "launch_site": launch_site,
            "return_site": row.get("returnSite"),
            "mission_state": "completed",
            "source_id": source["source_id"],
            "source_url": source["source_url"],
            "source_sha256": source["sha256"],
            "source_verification_mode": "live_fetched_primary",
        })
    if len(records) < minimum:
        raise ValueError(f"SpaceX parser found too few 2024+ completed missions: {len(records)}")
    if len({row["mission_id"] for row in records}) != len(records):
        raise ValueError("SpaceX 2024+ mission_id is not unique")
    return records


def parse_rocketlab(raw: bytes, source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    completed: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    rows = parse_tables(raw)
    for row in rows:
        if len(row) < 5:
            continue
        parsed = parse_date(row[1])
        record = {
            "operator": "Rocket Lab",
            "mission": row[0],
            "vehicle": row[2],
            "customer": row[3],
            "launch_site": row[4],
            "source_id": source["source_id"],
            "source_url": source["source_url"],
            "source_sha256": source["sha256"],
            "source_verification_mode": "live_fetched_primary",
        }
        if parsed is not None and parsed >= START_DATE:
            completed.append({**record, "launch_date": parsed.isoformat(), "mission_state": "completed"})
        elif parsed is None and any(token in row[1].casefold() for token in ("net", "2026", "2027", "undisclosed")):
            upcoming.append({**record, "planned_date_text": row[1], "mission_state": "planned"})
    if len(completed) < 20:
        raise ValueError(f"Rocket Lab parser found too few 2024+ completed missions: {len(completed)}")
    return completed, upcoming


def blue_origin_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = BLUE_ORIGIN.read_bytes()
    doc = json.loads(raw)
    source = doc["source"]
    records = doc["records"]
    if source.get("verification_mode") != "reviewed_primary_url" or not str(source.get("source_url", "")).startswith("https://www.blueorigin.com/"):
        raise ValueError("Blue Origin reviewed source contract is invalid")
    if len(records) < 15 or len({row["mission"] for row in records}) != len(records):
        raise ValueError("Blue Origin reviewed mission ledger is incomplete or duplicated")
    for row in records:
        if row["launch_date"] < START_DATE.isoformat() or row.get("jurisdiction") != "US":
            raise ValueError(f"Blue Origin reviewed mission is outside contract: {row}")
    evidence_sha = sha256(raw)
    out = [
        {
            **row,
            "operator": "Blue Origin",
            "mission_state": "completed",
            "source_id": "blueorigin-missions-reviewed",
            "source_url": source["source_url"],
            "source_reviewed_at": source["reviewed_at"],
            "source_verification_mode": source["verification_mode"],
            "live_fetch_status": source["live_fetch_status"],
            "source_evidence_path": "data/blue-origin-launches.json",
            "source_evidence_sha256": evidence_sha,
        }
        for row in records
    ]
    reviewed_source = {
        "source_id": "blueorigin-missions-reviewed",
        **source,
        "evidence_path": "data/blue-origin-launches.json",
        "evidence_sha256": evidence_sha,
    }
    return out, reviewed_source


def enrich_static(records: list[dict[str, Any]], source_map: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out = []
    reviewed_sources = []
    reviewed_evidence_sha = sha256(REUSE_EVENTS.read_bytes())
    for row in records:
        source = source_map.get(row["source_id"])
        if source is not None:
            out.append({
                **row,
                "source_url": source["source_url"],
                "source_sha256": source["sha256"],
                "source_verification_mode": "live_fetched_primary",
            })
            continue
        required = {"source_url", "source_reviewed_at", "source_verification_mode", "live_fetch_status"}
        if not required <= row.keys() or not str(row["source_url"]).startswith("https://www.blueorigin.com/"):
            raise ValueError(f"reviewed static source contract is incomplete: {row.get('source_id')}")
        enriched = {
            **row,
            "source_evidence_path": "data/reuse-events.json",
            "source_evidence_sha256": reviewed_evidence_sha,
        }
        out.append(enriched)
        reviewed_sources.append({
            "source_id": row["source_id"],
            "publisher": "Blue Origin",
            "source_url": row["source_url"],
            "reviewed_at": row["source_reviewed_at"],
            "verification_mode": row["source_verification_mode"],
            "live_fetch_status": row["live_fetch_status"],
            "evidence_path": "data/reuse-events.json",
            "evidence_sha256": reviewed_evidence_sha,
        })
    return out, reviewed_sources


def validate_authorizations(rows: list[dict[str, Any]]) -> None:
    required = {"operator", "vehicle_program", "authorization_type", "effective_at", "scope", "source_id"}
    for row in rows:
        if not required <= row.keys():
            raise ValueError(f"authorization record incomplete: {row}")
    if {row["operator"] for row in rows} < {"SpaceX", "Blue Origin", "Rocket Lab"}:
        raise ValueError("authorization registry lacks one of the required operators")


def validate_reuse_against_launches(reuse: list[dict[str, Any]], launches: list[dict[str, Any]]) -> None:
    spacex_by_id = {
        row.get("mission_id"): row
        for row in launches
        if row.get("operator") == "SpaceX" and row.get("mission_id")
    }
    for row in reuse:
        if row.get("operator") == "SpaceX" and row.get("mission_id"):
            launch = spacex_by_id.get(row["mission_id"])
            if launch is None:
                raise ValueError(f"reuse event lacks matching SpaceX launch: {row['mission_id']}")
            if launch["launch_date"] != row["event_date"]:
                raise ValueError(f"reuse event date differs from SpaceX mission tile: {row['mission_id']}")


def build_api(manifest: dict[str, Any], data_root: Path, api_dir: Path) -> dict[str, Any]:
    source_map = {row["source_id"]: row for row in manifest["sources"]}
    raw_by_id = {
        row["source_id"]: (data_root / row["evidence_path"]).read_bytes()
        for row in manifest["sources"]
    }
    spacex = parse_spacex(raw_by_id["spacex-launches"], source_map["spacex-launches"])
    rocketlab, planned = parse_rocketlab(raw_by_id["rocketlab-launches"], source_map["rocketlab-launches"])
    blue, blue_reviewed_source = blue_origin_records()
    completed = sorted(spacex + rocketlab + blue, key=lambda row: (row["launch_date"], row["operator"], row["mission"]))

    authorizations_raw = json.loads(AUTH_REGISTRY.read_text(encoding="utf-8"))["records"]
    validate_authorizations(authorizations_raw)
    authorizations, auth_reviewed = enrich_static(authorizations_raw, source_map)
    if auth_reviewed:
        raise ValueError("FAA authorizations must remain live-fetched primary evidence")
    reuse_raw = json.loads(REUSE_EVENTS.read_text(encoding="utf-8"))["records"]
    reuse, reuse_reviewed_sources = enrich_static(reuse_raw, source_map)
    validate_reuse_against_launches(reuse, completed)

    reviewed_sources = [blue_reviewed_source, *reuse_reviewed_sources]
    provenance = {**manifest, "reviewed_sources": reviewed_sources}
    by_month = Counter(row["launch_date"][:7] for row in completed)
    by_operator = Counter(row["operator"] for row in completed)
    us_launches = [
        row
        for row in completed
        if row.get("jurisdiction") == "US"
        or any(
            token in str(row.get("launch_site", ""))
            for token in ("Florida", "California", "Texas", "Launch Complex 2", "Cape Canaveral", "Kennedy", "Vandenberg")
        )
    ]
    coverage = {
        "completed_launch_count": len(completed),
        "completed_2024_plus": len(completed),
        "operator_count": len(by_operator),
        "operator_counts": dict(sorted(by_operator.items())),
        "us_launch_count": len(us_launches),
        "planned_rocketlab_count": len(planned),
        "authorization_record_count": len(authorizations),
        "reuse_event_count": len(reuse),
        "first_launch_date": completed[0]["launch_date"],
        "last_launch_date": completed[-1]["launch_date"],
        "live_primary_source_count": len(manifest["sources"]),
        "reviewed_primary_source_count": len(reviewed_sources),
        "primary_source_count": len(manifest["sources"]) + len(reviewed_sources),
    }
    api_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "launches.json": {"schema_version": 1, "records": completed},
        "planned.json": {"schema_version": 1, "records": planned},
        "authorizations.json": {"schema_version": 1, "records": authorizations},
        "reuse-events.json": {"schema_version": 1, "records": reuse},
        "monthly-cadence.json": {"schema_version": 1, "records": [{"month": month, "launch_count": count} for month, count in sorted(by_month.items())]},
        "provenance.json": provenance,
    }
    for name, payload in outputs.items():
        (api_dir / name).write_bytes(canonical_json(payload))
    index = {
        "schema_version": 1,
        "dataset": "Reusable launch primary evidence",
        "retrieved_at": manifest["retrieved_at"],
        "coverage": coverage,
        "source_limitations": [
            "Blue Origin primary pages return HTTP 429 to GitHub-hosted runners as of 2026-08-19; Blue Origin launch/reuse records are explicitly marked reviewed_primary_url and backed by committed evidence hashes rather than mislabeled as live fetched.",
        ],
        "views": {name.removesuffix(".json").replace("-", "_"): name for name in outputs},
        "rules": [
            "completed and planned missions are separate tables",
            "launch cadence is derived only from completed mission dates",
            "reuse/recovery outcomes are recorded only when explicitly stated by an operator or regulator",
            "authorization records describe the evidenced program/license scope and do not invent per-flight license identifiers",
            "live-fetched and reviewed-primary evidence modes are never conflated",
        ],
    }
    (api_dir / "index.json").write_bytes(canonical_json(index))
    print(json.dumps(coverage, sort_keys=True))
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--api-dir", type=Path, default=DEFAULT_API_DIR)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    manifest = verify_manifest(args.data_root) if args.offline else collect(args.data_root)
    build_api(manifest, args.data_root, args.api_dir)


if __name__ == "__main__":
    main()
