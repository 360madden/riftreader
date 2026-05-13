from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.chromalink_world_state_reference import main


class ChromaLinkWorldStateReferenceTests(unittest.TestCase):
    def write_preflight_summary(
        self,
        path: Path,
        *,
        status: str = "passed",
        pid: int = 79184,
        hwnd: str = "0xA90BFC",
        generated_at: str = "2026-05-13T01:00:00Z",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "kind": "x64dbg-target-preflight",
                    "generatedAtUtc": generated_at,
                    "status": status,
                    "selectedTarget": {
                        "processName": "rift_x64",
                        "pid": pid,
                        "hwndHex": hwnd,
                        "startTimeUtc": "2026-05-13T00:43:12.080812Z",
                        "moduleBaseAddressHex": "0x7FF796B50000",
                        "responding": True,
                    },
                    "debuggerProcessCount": 0,
                    "blockers": [],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )

    def write_world_state(
        self,
        path: Path,
        *,
        fresh: bool = True,
        stale: bool = False,
        healthy: bool = True,
        player_fresh: bool = True,
        player_stale: bool = False,
        player_available: bool = True,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "artifactKind": "riftreader-world-state",
                    "contract": {
                        "name": "chromalink-riftreader-world-state",
                        "schemaVersion": 1,
                    },
                    "ready": True,
                    "healthy": healthy,
                    "fresh": fresh,
                    "stale": stale,
                    "navigation": {
                        "playerPositionAvailable": player_available,
                    },
                    "player": {
                        "position": {
                            "x": 7455.6,
                            "y": 876.25,
                            "z": 3053.75,
                            "observedAtUtc": "2026-05-13T01:05:30Z",
                            "ageMs": 100.0,
                            "fresh": player_fresh,
                            "stale": player_stale,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_self_test_writes_reference_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "capture"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["processAttachOrMemoryReadStarted"])
            reference_path = Path(summary["artifacts"]["referenceJson"])
            self.assertTrue(reference_path.is_file())
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            self.assertEqual(reference["source"], "chromalink-riftreader-world-state")
            self.assertEqual(reference["processId"], 12345)
            self.assertEqual(reference["targetWindowHandle"], "0xABCDEF")
            self.assertEqual(reference["savedVariablesUse"], "none")
            self.assertFalse(reference["movementSent"])

    def test_fresh_world_state_with_latest_preflight_writes_currentpid_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            preflight = (
                temp_path
                / "scripts"
                / "captures"
                / "x64dbg-target-preflight-new"
                / "summary.json"
            )
            self.write_preflight_summary(preflight, generated_at="2026-05-13T02:00:00Z")
            world_state = temp_path / "world-state.json"
            self.write_world_state(world_state)
            out = temp_path / "capture"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(temp_path),
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        "latest",
                        "--world-state-file",
                        str(world_state),
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["preflight"]["resolvedFromAlias"], "latest")
            self.assertEqual(summary["target"]["pid"], 79184)
            self.assertEqual(summary["target"]["hwnd"], "0xA90BFC")
            reference_path = Path(summary["artifacts"]["referenceJson"])
            self.assertTrue(reference_path.name.startswith("rift-api-reference-currentpid-79184-"))
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            self.assertEqual(reference["coordinate"]["x"], 7455.6)
            self.assertEqual(reference["coordinate"]["capturedAtUtc"], "2026-05-13T01:05:30Z")
            self.assertTrue(reference["noCheatEngine"])

    def test_stale_world_state_blocks_and_does_not_write_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            world_state = temp_path / "world-state.json"
            self.write_world_state(
                world_state,
                healthy=False,
                player_fresh=False,
                player_stale=True,
                player_available=False,
            )
            out = temp_path / "capture"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--world-state-file",
                        str(world_state),
                        "--target-pid",
                        "79184",
                        "--target-hwnd",
                        "0xA90BFC",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("world-state-not-healthy", summary["blockers"])
            self.assertIn("world-state-player-position-not-fresh", summary["blockers"])
            self.assertIn("world-state-player-position-stale", summary["blockers"])
            self.assertIn("world-state-navigation-player-position-unavailable", summary["blockers"])
            self.assertIsNone(summary["artifacts"]["referenceJson"])


if __name__ == "__main__":
    unittest.main()
