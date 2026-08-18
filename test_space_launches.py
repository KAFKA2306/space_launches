from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import space_launches as sl


class SpaceLaunchEvidenceTests(unittest.TestCase):
    def test_spacex_completed_table_parser_excludes_pre_2024(self) -> None:
        raw = b'''<table><tr><th>Title</th><th>Return Site</th><th>Date</th><th>Launch Site</th></tr>
        <tr><td>Recent Mission</td><td>ASDS</td><td>May 17, 2024</td><td>Florida</td></tr>
        <tr><td>Old Mission</td><td>ASDS</td><td>Dec 1, 2023</td><td>Florida</td></tr></table>'''
        source = {"source_id": "test", "source_url": "https://example.com", "sha256": "abc"}
        original = sl.START_DATE
        try:
            sl.START_DATE = sl.date(2024, 1, 1)
            with self.assertRaisesRegex(ValueError, "too few"):
                sl.parse_spacex(raw, source)
            rows = sl.parse_tables(raw)
            self.assertEqual(rows[1][0], "Recent Mission")
        finally:
            sl.START_DATE = original

    def test_rocketlab_parser_keeps_planned_separate(self) -> None:
        completed_rows = ''.join(
            f'<tr><td>M{i}</td><td>21 Mar 2024</td><td>Electron</td><td>C{i}</td><td>Launch Complex 2</td></tr>'
            for i in range(20)
        )
        raw = (f'<table>{completed_rows}<tr><td>Future</td><td>NET 2027</td><td>Electron</td><td>C</td><td>LC-1</td></tr></table>').encode()
        source = {"source_id": "test", "source_url": "https://example.com", "sha256": "abc"}
        completed, planned = sl.parse_rocketlab(raw, source)
        self.assertEqual(len(completed), 20)
        self.assertEqual(len(planned), 1)
        self.assertTrue(all(row["mission_state"] == "completed" for row in completed))
        self.assertEqual(planned[0]["mission_state"], "planned")

    def test_static_reuse_events_are_explicit(self) -> None:
        rows = json.loads(sl.REUSE_EVENTS.read_text(encoding="utf-8"))["records"]
        self.assertGreaterEqual(len(rows), 4)
        for row in rows:
            self.assertIn("outcome", row)
            self.assertIn("source_id", row)
            self.assertIn("event_type", row)
        self.assertTrue(any(row.get("booster_flight_number") == 21 for row in rows))
        self.assertTrue(any(row["outcome"] == "lost_during_descent" for row in rows))
        self.assertTrue(any(row["outcome"] == "landed" for row in rows))

    def test_authorizations_have_scope_without_invented_license_id(self) -> None:
        rows = json.loads(sl.AUTH_REGISTRY.read_text(encoding="utf-8"))["records"]
        sl.validate_authorizations(rows)
        self.assertGreaterEqual(len(rows), 5)
        for row in rows:
            self.assertNotIn("license_id", row)
            self.assertTrue(row["scope"])
            self.assertTrue(row["source_id"].startswith("faa-"))

    def test_manifest_hash_verification_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            obj = root / "raw" / "objects" / "x.html"
            obj.parent.mkdir(parents=True)
            obj.write_bytes(b"source")
            manifest = {
                "schema_version": 1,
                "retrieved_at": "2026-08-19T00:00:00+00:00",
                "sources": [{"source_id": "x", "evidence_path": "raw/objects/x.html", "sha256": "wrong"}],
            }
            (root / "raw" / "latest-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                sl.verify_manifest(root)


if __name__ == "__main__":
    unittest.main()
