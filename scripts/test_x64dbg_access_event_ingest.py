from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_access_event_ingest import main, synthetic_payload


class X64DbgAccessEventIngestTests(unittest.TestCase):
    def run_main(self, args: list[str]) -> int:
        with redirect_stdout(StringIO()):
            return main(args)

    def write_payload(self, temp: str, payload: dict) -> Path:
        path = Path(temp) / "events.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_self_test_writes_candidate_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "ingest"
            code = self.run_main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            candidate = json.loads((out / "x64dbg-coordinate-chain-candidate.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["counts"]["eventCount"], 3)
            self.assertEqual(summary["counts"]["candidateCount"], 1)
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["x64dbgCommandsExecuted"])
            self.assertFalse(summary["safety"]["processAttachOrMemoryReadStarted"])
            self.assertFalse(candidate["validation"]["movementProofEligible"])
            self.assertTrue(candidate["validation"]["multiPose"])
            self.assertIn("not-restart-validated", candidate["blockers"])

    def test_missing_events_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["events"] = []
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "blocked"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("no-access-events-recorded", summary["blockers"])
            self.assertIsNone(summary["artifacts"]["candidateJson"])

    def test_missing_target_identity_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["process"] = {"name": "rift_x64"}
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "blocked-target"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("missing-target-pid", summary["blockers"])
            self.assertIn("missing-target-hwnd", summary["blockers"])
            self.assertIn("missing-process-start-time-utc", summary["blockers"])

    def test_watch_window_must_cover_xyz_triplet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["watchWindow"]["sizeBytes"] = 4
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "blocked-watch"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("watch-size-must-cover-12-byte-xyz-triplet", summary["blockers"])

    def test_api_memory_delta_blocks_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["events"][0]["memoryNow"]["x"] += 100.0
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "blocked-delta"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json", "--max-delta", "1.0"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("api-now-vs-memory-now-delta-exceeded", summary["blockers"])
            self.assertIsNone(summary["artifacts"]["candidateJson"])

    def test_single_pose_emits_candidate_but_blocks_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["events"] = payload["events"][:1]
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "single-pose"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            candidate = json.loads((out / "x64dbg-coordinate-chain-candidate.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertIn("not-multi-pose-validated", candidate["blockers"])
            self.assertFalse(candidate["validation"]["multiPose"])
            self.assertFalse(candidate["validation"]["movementProofEligible"])

    def test_module_rva_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["events"][0]["instruction"]["rva"] = "0x999"
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "blocked-rva"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("instruction-rva-mismatch", summary["blockers"])

    def test_write_access_blocks_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = synthetic_payload()
            payload["events"][0]["access"] = "write"
            payload["events"][0]["instruction"]["access"] = "write"
            events_path = self.write_payload(temp, payload)
            out = Path(temp) / "blocked-write"
            code = self.run_main(["--events-json", str(events_path), "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("write-class-operation-present", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
