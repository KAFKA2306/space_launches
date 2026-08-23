from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sanitize_external_evidence as see


class SanitizeExternalEvidenceTests(unittest.TestCase):
    def test_html_sanitizer_removes_executable_assets_and_credentials(self) -> None:
        key = b"AIza" + b"A" * 35
        raw = (
            b"<html><head><style>.x{display:none}</style>"
            b"<script src='https://maps.googleapis.com/maps/api/js?key=" + key + b"'></script>"
            b"</head><body><table><tr><td>Mission</td><td>21 Mar 2024</td>"
            b"<td>Electron</td><td>Customer</td><td>Launch Complex 2</td></tr></table>"
            b"</body></html>"
        )
        stored = see.sanitize_html(raw)
        self.assertNotIn(b"<script", stored.lower())
        self.assertNotIn(b"<style", stored.lower())
        self.assertFalse(see.contains_high_confidence_credential(stored))
        self.assertIn(b"Mission", stored)
        self.assertIn(b"Launch Complex 2", stored)

    def test_tree_sanitization_preserves_upstream_hash_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            objects = root / "raw" / "objects"
            manifests = root / "raw" / "manifests"
            objects.mkdir(parents=True)
            manifests.mkdir(parents=True)
            key = b"AIza" + b"B" * 35
            raw = b"<html><script>const k='" + key + b"'</script><table><tr><td>Evidence</td></tr></table></html>"
            digest = see.sha256(raw)
            source_path = objects / f"{digest}.html"
            source_path.write_bytes(raw)
            manifest = {
                "schema_version": 1,
                "retrieved_at": "2026-08-23T00:00:00+00:00",
                "sources": [{
                    "source_id": "example",
                    "publisher": "Example",
                    "source_url": "https://example.com",
                    "sha256": digest,
                    "size_bytes": len(raw),
                    "content_type": "text/html",
                    "evidence_path": source_path.relative_to(root).as_posix(),
                    "verification_mode": "live_fetched_primary",
                }],
            }
            payload = see.canonical_json(manifest)
            (root / "raw" / "latest-manifest.json").write_bytes(payload)
            (manifests / f"{see.sha256(payload)}.json").write_bytes(payload)

            first = see.sanitize_tree(root)
            source = first["sources"][0]
            self.assertEqual(source["upstream_sha256"], digest)
            self.assertEqual(source["upstream_size_bytes"], len(raw))
            self.assertEqual(source["storage_transform"], "strip_script_style_and_redact_credentials")
            stored_path = root / source["evidence_path"]
            self.assertTrue(stored_path.is_file())
            self.assertNotEqual(source["sha256"], digest)
            self.assertEqual(len(list(objects.iterdir())), 1)
            self.assertEqual(len(list(manifests.iterdir())), 1)
            see.check_tree(root)

            second = see.sanitize_tree(root)
            self.assertEqual(second, first)
            see.check_tree(root)

    def test_non_html_evidence_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            objects = root / "raw" / "objects"
            manifests = root / "raw" / "manifests"
            objects.mkdir(parents=True)
            manifests.mkdir(parents=True)
            raw = json.dumps({"missionStatus": "final"}).encode()
            digest = see.sha256(raw)
            path = objects / f"{digest}.json"
            path.write_bytes(raw)
            manifest = {
                "schema_version": 1,
                "retrieved_at": "2026-08-23T00:00:00+00:00",
                "sources": [{
                    "source_id": "json",
                    "publisher": "Example",
                    "source_url": "https://example.com/data.json",
                    "sha256": digest,
                    "size_bytes": len(raw),
                    "content_type": "application/json",
                    "evidence_path": path.relative_to(root).as_posix(),
                    "verification_mode": "live_fetched_primary",
                }],
            }
            payload = see.canonical_json(manifest)
            (root / "raw" / "latest-manifest.json").write_bytes(payload)
            (manifests / f"{see.sha256(payload)}.json").write_bytes(payload)
            updated = see.sanitize_tree(root)["sources"][0]
            self.assertEqual(updated["sha256"], digest)
            self.assertEqual(updated["storage_transform"], "none")
            self.assertEqual((root / updated["evidence_path"]).read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
