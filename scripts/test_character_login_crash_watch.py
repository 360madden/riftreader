from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.character_login_crash_watch import main


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def current_truth(*, pid: int = 77728, hwnd: str = "0x8E13A6") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "target": {
            "processName": "rift_x64",
            "processId": pid,
            "targetWindowHandle": hwnd,
            "windowTitle": "RIFT",
            "processStartUtc": "2026-05-20T15:54:23Z",
        },
        "movementGate": {"allowed": False, "status": "blocked-target-not-in-world"},
    }


def current_proof(*, pid: int = 77728, hwnd: str = "0x8E13A6") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "mode": "current-proof-anchor-readback-pointer",
        "status": "blocked-target-not-in-world",
        "target": {"processName": "rift_x64", "processId": pid, "targetWindowHandle": hwnd},
        "latestValidation": {"movementAllowed": False},
    }


def readiness_packet(*, pid: int = 77728, hwnd: str = "0x8E13A6") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-login-readiness-packet",
        "status": "packet-ready",
        "target": {
            "processName": "rift_x64",
            "processId": pid,
            "windowHandle": hwnd,
            "windowTitle": "RIFT",
        },
        "automationReadiness": {
            "canPlanCharacterLogin": True,
            "canExecuteLiveActionsNow": False,
            "movementAllowed": False,
        },
    }


def observation(*, pid: int = 77728, hwnd: str = "0x8E13A6") -> dict[str, object]:
    return {
        "observations": [
            {
                "sampleIndex": 1,
                "status": "observed",
                "observedAtUtc": "2026-05-20T16:40:00Z",
                "windows": [
                    {
                        "processId": pid,
                        "windowHandle": hwnd,
                        "processName": "rift_x64",
                        "title": "RIFT",
                        "isVisible": True,
                        "isMinimized": False,
                        "clientSize": {"width": 640, "height": 360},
                    }
                ],
                "errors": [],
            }
        ]
    }


class CharacterLoginCrashWatchTests(unittest.TestCase):
    def write_fixture_files(self, root: Path, *, obs: dict[str, object] | None = None) -> dict[str, Path]:
        paths = {
            "truth": root / "truth.json",
            "proof": root / "proof.json",
            "readiness": root / "readiness.json",
            "observations": root / "observations.json",
        }
        write_json(paths["truth"], current_truth())
        write_json(paths["proof"], current_proof())
        write_json(paths["readiness"], readiness_packet())
        write_json(paths["observations"], obs or observation())
        return paths

    def run_watch(self, root: Path, paths: dict[str, Path]) -> tuple[int, dict[str, object]]:
        out = root / "out"
        args = [
            "--repo-root",
            str(root),
            "--current-truth",
            str(paths["truth"]),
            "--current-proof",
            str(paths["proof"]),
            "--readiness-packet",
            str(paths["readiness"]),
            "--observations-json",
            str(paths["observations"]),
            "--output-root",
            str(out),
            "--json",
        ]
        with redirect_stdout(StringIO()):
            code = main(args)
        summary = json.loads((out / "character-login-crash-watch-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_same_epoch_target_is_watch_ready_without_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(root)

            code, summary = self.run_watch(root, paths)

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "watch-ready")
            self.assertEqual(summary["watchStatus"], "target-present-same-epoch")
            self.assertEqual(summary["watchBlockers"], [])
            self.assertEqual(summary["resumeDecision"]["resumeAtState"], "refresh-character-select-readiness")
            self.assertFalse(summary["safety"]["mouseClickSent"])
            self.assertFalse(summary["safety"]["clientLaunchAttempted"])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertTrue(Path(summary["artifacts"]["observationsJsonl"]).is_file())

    def test_no_window_blocks_as_no_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(root, obs={"windows": []})

            code, summary = self.run_watch(root, paths)

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["watchStatus"], "blocked-no-client")
            self.assertIn("rift-client-not-running-or-window-not-visible", summary["watchBlockers"])
            self.assertEqual(summary["resumeDecision"]["resumeAtState"], "detect-client")

    def test_new_epoch_blocks_and_discards_old_pid_hwnd(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(root, obs=observation(pid=88888, hwnd="0xAA00BB"))

            code, summary = self.run_watch(root, paths)

            self.assertEqual(code, 2)
            self.assertEqual(summary["watchStatus"], "blocked-target-drift-new-epoch")
            self.assertIn("expected-target-not-found-new-client-epoch", summary["watchBlockers"])
            self.assertIn("do-not-reuse-old-PID-HWND", summary["resumeDecision"]["oldEpochReusePolicy"])

    def test_multiple_nonmatching_windows_blocks_until_exact_target_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(
                root,
                obs={
                    "windows": [
                        {
                            "processId": 111,
                            "windowHandle": "0x111",
                            "processName": "rift_x64",
                            "title": "RIFT",
                            "isVisible": True,
                        },
                        {
                            "processId": 222,
                            "windowHandle": "0x222",
                            "processName": "rift_x64",
                            "title": "RIFT",
                            "isVisible": True,
                        },
                    ]
                },
            )

            code, summary = self.run_watch(root, paths)

            self.assertEqual(code, 2)
            self.assertEqual(summary["watchStatus"], "blocked-multiple-rift-windows")
            self.assertIn("multiple-rift-windows-without-expected-target", summary["watchBlockers"])


if __name__ == "__main__":
    unittest.main()
