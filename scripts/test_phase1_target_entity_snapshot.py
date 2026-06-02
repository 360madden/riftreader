import unittest

from scripts import phase1_target_entity_snapshot as phase1


class Phase1TargetEntitySnapshotTests(unittest.TestCase):
    def test_readerbridge_summary_extracts_post_flush_target(self):
        snapshot = {
            "SourceFile": "ReaderBridgeExport.lua",
            "LoadedAtUtc": "2026-06-02T00:00:00Z",
            "LastExportAt": 1.0,
            "LastReason": "save-begin",
            "ExportCount": 3,
            "Current": {
                "Status": "ready",
                "SourceMode": "DirectAPI",
                "SourceAddon": "RiftAPI",
                "Target": {
                    "Id": "u1",
                    "Name": "Atank",
                    "Level": 45,
                    "Relation": "friendly",
                    "Hp": 18208,
                    "HpMax": 18208,
                    "Coord": {"X": 7251.0, "Y": 821.0, "Z": 2987.0},
                },
                "Telemetry": {
                    "Capabilities": {"TargetAvailable": True},
                    "Context": {"TargetPresent": True, "TargetId": "u1"},
                },
                "TargetBuffLines": ["Track Fish"],
                "TargetDebuffLines": [],
            },
        }

        summary = phase1.summarize_readerbridge_snapshot(snapshot, "2026-06-02T00:00:01Z")

        self.assertTrue(summary["targetPresent"])
        self.assertTrue(summary["targetAvailable"])
        self.assertEqual(summary["savedVariablesClassification"], "post-flush-savedvariables")
        self.assertEqual(summary["target"]["name"], "Atank")
        self.assertEqual(summary["target"]["coord"]["x"], 7251.0)
        self.assertEqual(summary["targetBuffLines"], ["Track Fish"])

    def test_reader_family_blocker_extracts_family_id(self):
        text = "Unable to resolve a full current-target snapshot from family 'fam-CEC3708F'."

        blocker = phase1.reader_family_blocker(text)

        self.assertEqual(blocker, "target-current-family-resolution-failed:fam-CEC3708F")

    def test_self_test_entrypoint(self):
        self.assertEqual(phase1.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
