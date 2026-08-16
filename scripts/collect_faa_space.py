#!/usr/bin/env python3
"""Collect FAA commercial-space cumulative counts and official operational-data links."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

COUNTS_PAGE = "https://www.faa.gov/node/52196"
DATA_PAGE = "https://www.faa.gov/data_research"
TRANSITION_PAGE = "https://www.faa.gov/newsroom/faa-streamlines-commercial-space-license-approvals"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href is not None:
            self.links.append((" ".join(" ".join(self.parts).split()), self.href))
            self.href = None
            self.parts = []


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "space-launches/1.0 github.com/KAFKA2306/trahist"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def text(raw: bytes) -> str:
    html = raw.decode("utf-8", errors="replace")
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def parse_counts(raw: bytes) -> dict[str, int]:
    visible = text(raw)
    labels = {
        "licensed_launches": "Licensed Launches",
        "licensed_reentries": "Licensed Reentries",
        "permitted_experimental_launches": "Permitted (Experimental) Launches",
        "active_launch_licenses": "Active Launch Licenses",
    }
    result: dict[str, int] = {}
    for key, label in labels.items():
        before = re.search(rf"([0-9][0-9,]*)\s+{re.escape(label)}", visible, flags=re.I)
        after = re.search(rf"{re.escape(label)}\s+([0-9][0-9,]*)", visible, flags=re.I)
        match = before or after
        if not match:
            raise ValueError(f"FAA count not found: {label}")
        result[key] = int(match.group(1).replace(",", ""))
    return result


def discover_operational_links(raw: bytes) -> dict[str, str]:
    parser = LinkParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    wanted = {
        "recent_launch_data": "Recent Launch Data",
        "licensed_launches": "Licensed Launches",
        "licensed_reentries": "Licensed Reentries",
        "permitted_launches": "Permitted Launches",
    }
    result: dict[str, str] = {}
    for label, href in parser.links:
        for key, expected in wanted.items():
            if label.strip().lower() == expected.lower():
                result[key] = urljoin(DATA_PAGE, href)
    missing = set(wanted) - result.keys()
    if missing:
        raise ValueError(f"FAA operational-data links missing: {sorted(missing)}")
    return result


def collect() -> dict[str, object]:
    counts_raw = fetch(COUNTS_PAGE)
    data_raw = fetch(DATA_PAGE)
    transition_raw = fetch(TRANSITION_PAGE)
    return {
        "schema_version": 1,
        "publisher": "Federal Aviation Administration",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "cumulative_counts": parse_counts(counts_raw),
        "operational_data_links": discover_operational_links(data_raw),
        "sources": [
            {"url": COUNTS_PAGE, "sha256": hashlib.sha256(counts_raw).hexdigest()},
            {"url": DATA_PAGE, "sha256": hashlib.sha256(data_raw).hexdigest()},
            {"url": TRANSITION_PAGE, "sha256": hashlib.sha256(transition_raw).hexdigest()},
        ],
        "event_collection_status": "FAA Tableau operational tables discovered; per-launch rows are not treated as collected until a stable machine-readable export is verified.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/space/faa-commercial-space.json"))
    args = parser.parse_args()
    result = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
