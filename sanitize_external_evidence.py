from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

HTML_TYPES = {"text/html", "application/xhtml+xml"}
SCRIPT_STYLE_RE = re.compile(rb"(?is)<(?:script|style)\b.*?</(?:script|style)\s*>")
CREDENTIAL_PATTERNS: tuple[tuple[re.Pattern[bytes], bytes], ...] = (
    (re.compile(rb"AIza[0-9A-Za-z_-]{35}"), b"[REDACTED_GOOGLE_API_KEY]"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), b"[REDACTED_AWS_ACCESS_KEY]"),
    (re.compile(rb"gh[pousr]_[0-9A-Za-z_]{36,255}"), b"[REDACTED_GITHUB_TOKEN]"),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sanitize_html(raw: bytes) -> bytes:
    sanitized = SCRIPT_STYLE_RE.sub(b"", raw)
    for pattern, replacement in CREDENTIAL_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def contains_high_confidence_credential(raw: bytes) -> bool:
    return any(pattern.search(raw) is not None for pattern, _ in CREDENTIAL_PATTERNS)


def sanitize_source(source: dict[str, Any], data_root: Path) -> tuple[dict[str, Any], Path, Path]:
    current_path = data_root / source["evidence_path"]
    raw = current_path.read_bytes()
    if sha256(raw) != source["sha256"]:
        raise ValueError(f"source hash mismatch before sanitization: {source['source_id']}")

    content_type = str(source.get("content_type", ""))
    upstream_sha = str(source.get("upstream_sha256") or source["sha256"])
    upstream_size = int(source.get("upstream_size_bytes") or len(raw))
    stored = sanitize_html(raw) if content_type in HTML_TYPES else raw
    if contains_high_confidence_credential(stored):
        raise ValueError(f"credential-like token remains after sanitization: {source['source_id']}")

    stored_sha = sha256(stored)
    suffix = current_path.suffix
    object_dir = data_root / "raw" / "objects"
    target_path = object_dir / f"{stored_sha}{suffix}"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(stored)

    updated = {
        **source,
        "sha256": stored_sha,
        "size_bytes": len(stored),
        "evidence_path": target_path.relative_to(data_root).as_posix(),
        "upstream_sha256": upstream_sha,
        "upstream_size_bytes": upstream_size,
        "storage_transform": "strip_script_style_and_redact_credentials" if content_type in HTML_TYPES else "none",
    }
    return updated, current_path, target_path


def prune_unreferenced(data_root: Path, referenced: set[Path]) -> None:
    objects = data_root / "raw" / "objects"
    if objects.exists():
        for path in objects.iterdir():
            if path.is_file() and path not in referenced:
                path.unlink()


def write_manifest(data_root: Path, manifest: dict[str, Any]) -> None:
    payload = canonical_json(manifest)
    raw_root = data_root / "raw"
    manifests = raw_root / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    for path in manifests.glob("*.json"):
        path.unlink()
    manifest_path = manifests / f"{sha256(payload)}.json"
    manifest_path.write_bytes(payload)
    (raw_root / "latest-manifest.json").write_bytes(payload)


def sanitize_tree(data_root: Path) -> dict[str, Any]:
    latest = data_root / "raw" / "latest-manifest.json"
    manifest = json.loads(latest.read_text(encoding="utf-8"))
    updated_sources: list[dict[str, Any]] = []
    referenced: set[Path] = set()
    for source in manifest["sources"]:
        updated, _, target = sanitize_source(source, data_root)
        updated_sources.append(updated)
        referenced.add(target)
    manifest["sources"] = updated_sources
    write_manifest(data_root, manifest)
    prune_unreferenced(data_root, referenced)
    check_tree(data_root)
    return manifest


def check_tree(data_root: Path) -> None:
    manifest = json.loads((data_root / "raw" / "latest-manifest.json").read_text(encoding="utf-8"))
    referenced: set[Path] = set()
    for source in manifest["sources"]:
        path = data_root / source["evidence_path"]
        if not path.is_file():
            raise ValueError(f"missing stored evidence: {source['source_id']}")
        raw = path.read_bytes()
        if sha256(raw) != source["sha256"]:
            raise ValueError(f"stored evidence hash mismatch: {source['source_id']}")
        if contains_high_confidence_credential(raw):
            raise ValueError(f"credential-like token in stored evidence: {source['source_id']}")
        if str(source.get("content_type", "")) in HTML_TYPES and SCRIPT_STYLE_RE.search(raw):
            raise ValueError(f"script/style remains in stored HTML evidence: {source['source_id']}")
        referenced.add(path)

    objects = data_root / "raw" / "objects"
    actual = {path for path in objects.iterdir() if path.is_file()} if objects.exists() else set()
    if actual != referenced:
        raise ValueError("raw object store contains unreferenced evidence")

    payload = canonical_json(manifest)
    manifests = data_root / "raw" / "manifests"
    expected_manifest = manifests / f"{sha256(payload)}.json"
    actual_manifests = {path for path in manifests.glob("*.json")} if manifests.exists() else set()
    if actual_manifests != {expected_manifest} or expected_manifest.read_bytes() != payload:
        raise ValueError("manifest store is not canonical")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_tree(args.data_root)
    else:
        sanitize_tree(args.data_root)


if __name__ == "__main__":
    main()
