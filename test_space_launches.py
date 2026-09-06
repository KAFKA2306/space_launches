from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import space_launches as sl


class SpaceLaunchEvidenceTests(unittest.TestCase):
    def test_spacex_cms_parser_excludes_nonfinal_and_pre_2024(self) -> None:
        payload = [
            {"missionStatus":"final","launchDate":"2024-05-17","launchTime":"20:32:00","launchSite":"SLC-40, Florida","link":"sl-6-59","title":"Starlink Mission","missionType":"starlink","vehicle":"Falcon 9","returnSite":"Droneship"},
            {"missionStatus":"final","launchDate":"2023-12-01","launchTime":"00:00:00","launchSite":"SLC-40, Florida","link":"old","title":"Old","missionType":"starlink","vehicle":"Falcon 9","returnSite":"Droneship"},
            {"missionStatus":"upcoming","launchDate":"2026-09-01","launchTime":"00:00:00","launchSite":"SLC-40, Florida","link":"future","title":"Future","missionType":"starlink","vehicle":"Falcon 9","returnSite":None},
        ]
        source = {"source_id":"test","source_url":"https://content.spacex.com/test","sha256":"abc"}
        rows = sl.parse_spacex(json.dumps(payload).encode(), source, minimum=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mission_id"], "sl-6-59")
        self.assertEqual(rows[0]["launch_date"], "2024-05-17")
        self.assertEqual(rows[0]["vehicle"], "Falcon 9")
        self.assertEqual(rows[0]["mission_state"], "completed")

    def test_spacex_cms_parser_fails_on_missing_identity(self) -> None:
        payload = [{"missionStatus":"final","launchDate":"2024-05-17","link":"x","title":"X","vehicle":"Falcon 9"}]
        source = {"source_id":"test","source_url":"https://content.spacex.com/test","sha256":"abc"}
        with self.assertRaisesRegex(ValueError, "lacks identity"):
            sl.parse_spacex(json.dumps(payload).encode(), source, minimum=1)

    def test_rocketlab_parser_keeps_planned_separate(self) -> None:
        completed_rows = ''.join(
            f'<tr><td>M{i}</td><td>21 Mar 2024</td><td>Electron</td><td>C{i}</td><td>Launch Complex 2</td></tr>'
            for i in range(20)
        )
        raw = (f'<table>{completed_rows}<tr><td>Future</td><td>NET 2027</td><td>Electron</td><td>C</td><td>LC-1</td></tr></table>').encode()
        source = {"source_id":"test","source_url":"https://example.com","sha256":"abc"}
        completed, planned = sl.parse_rocketlab(raw, source)
        self.assertEqual(len(completed), 20)
        self.assertEqual(len(planned), 1)
        self.assertTrue(all(row["mission_state"] == "completed" for row in completed))
        self.assertEqual(planned[0]["mission_state"], "planned")

    def test_static_reuse_events_are_explicit(self) -> None:
        rows = json.loads(sl.REUSE_EVENTS.read_text(encoding="utf-8"))["records"]
        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            self.assertIn("outcome", row)
            self.assertIn("source_id", row)
            self.assertIn("event_type", row)
        spacex = next(row for row in rows if row["operator"] == "SpaceX")
        self.assertEqual(spacex["mission_id"], "sl-6-59")
        self.assertEqual(spacex["booster_flight_number"], 21)
        ns8 = next(row for row in rows if row["event_id"] == "blueorigin-ns8-ns7-vehicle-reflight")
        self.assertEqual(ns8["vehicle"], "New Shepard")
        self.assertEqual(ns8["previous_mission"], "NS-7")
        self.assertEqual(ns8["previous_event_date"], "2017-12-12")
        self.assertEqual(ns8["turnaround_days"], 138)
        ng2 = next(row for row in rows if row["event_id"] == "blueorigin-ng2-booster-landing")
        ng3 = next(row for row in rows if row["event_id"] == "blueorigin-ng3-never-tell-me-the-odds-reflight")
        self.assertEqual(ng2["booster_name"], "Never Tell Me The Odds")
        self.assertEqual(ng3["booster_name"], ng2["booster_name"])
        self.assertEqual(ng3["previous_mission"], "NG-2")
        self.assertEqual(ng3["previous_event_date"], ng2["event_date"])
        self.assertEqual(ng3["turnaround_days"], 157)
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
                "sources": [{"source_id":"x","evidence_path":"raw/objects/x.html","sha256":"wrong"}],
            }
            (root / "raw" / "latest-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                sl.verify_manifest(root)


if __name__ == "__main__":
    unittest.main()
