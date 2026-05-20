from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.character_login_play_executor_gate import main


TOKEN = "ENTER-WORLD:ATANK:80072:0xD10C20"


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def supervisor() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-login-supervisor",
        "status": "blocked-approval-required",
        "generatedAtUtc": "2026-05-20T17:20:00Z",
        "dataBlockers": [],
        "executionBlockers": [
            "executor-contract-not-ready:blocked",
            "executor-contract:world-entry-not-permitted-by-source-environment",
            "executor-contract:explicit-world-entry-approval-token-missing-or-mismatched",
        ],
        "target": {
            "processName": "rift_x64",
            "processId": 80072,
            "windowHandle": "0xD10C20",
            "processStartUtc": "2026-05-20T16:54:54Z",
            "moduleBase": "0x7FF7B77A0000",
        },
        "supervisorDecision": {"expectedApprovalToken": TOKEN},
    }


def manifest(*, blockers: list[str] | None = None) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-future-mcp-character-login-action-manifest",
        "status": "blocked" if blockers else "ready-for-future-approved-executor",
        "blockers": blockers or [],
        "neverExecuteBySupervisor": True,
        "approval": {"required": True, "token": TOKEN, "oldTokensInvalidAfterCrashOrRelaunch": True},
        "target": {
            "processName": "rift_x64",
            "processId": 80072,
            "windowHandle": "0xD10C20",
            "windowTitle": "RIFT",
        },
        "playButton": {"clickPoint": [517, 343], "bbox": [476, 329, 558, 357], "coordinateSpace": "client", "maxClicks": 1},
        "mcpToolSequence": [
            {"step": "bind-exact-target", "tool": "mcp__rift_game__.find_game_window", "arguments": {"processId": 80072, "windowHandle": "0xD10C20"}},
            {"step": "capture-before-focus", "tool": "mcp__rift_game__.capture_game_window", "arguments": {}},
            {"step": "focus-for-click", "tool": "mcp__rift_game__.focus_game_window", "arguments": {}},
            {"step": "click-play-once", "tool": "mcp__rift_game__.click_client", "arguments": {"x": 517, "y": 343}, "requiredApprovalToken": TOKEN},
            {"step": "wait-for-world-transition", "tool": "mcp__rift_game__.wait_for_frame_change", "arguments": {"timeoutMilliseconds": 60000}},
            {"step": "capture-after-transition", "tool": "mcp__rift_game__.capture_game_window", "arguments": {}},
            {"step": "post-world-proof", "tool": "repo-proofonly-workflow", "arguments": {}},
        ],
        "failClosedOn": ["PID/HWND mismatch", "wait_for_frame_change reports changed=false"],
    }


def screen_state(status: str = "classified-character-select") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-login-screen-state",
        "status": status,
        "generatedAtUtc": "2026-05-20T17:20:01Z",
        "classification": "character-selection-not-in-world" if status == "classified-character-select" else "not-character-select-or-transition",
        "confidence": 0.97,
        "decision": {
            "safeToUseCharacterSelectClickTargets": status == "classified-character-select",
            "canTreatAsInWorld": False,
        },
    }


def current_truth() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "updatedAtUtc": "2026-05-20T17:20:02Z",
        "target": {"processName": "rift_x64", "processId": 80072, "targetWindowHandle": "0xD10C20"},
        "movementGate": {"allowed": False, "status": "blocked-target-not-in-world"},
    }


def current_proof() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "status": "blocked-target-not-in-world",
        "target": {"processName": "rift_x64", "processId": 80072, "targetWindowHandle": "0xD10C20"},
    }


class CharacterLoginPlayExecutorGateTests(unittest.TestCase):
    def write_inputs(self, root: Path, *, bad_screen: bool = False, manifest_blockers: list[str] | None = None) -> dict[str, Path]:
        paths = {
            "supervisor": root / "supervisor.json",
            "manifest": root / "manifest.json",
            "screen": root / "screen.json",
            "truth": root / "truth.json",
            "proof": root / "proof.json",
        }
        write_json(paths["supervisor"], supervisor())
        write_json(paths["manifest"], manifest(blockers=manifest_blockers))
        write_json(paths["screen"], screen_state("classified-non-character-select" if bad_screen else "classified-character-select"))
        write_json(paths["truth"], current_truth())
        write_json(paths["proof"], current_proof())
        return paths

    def run_gate(self, root: Path, paths: dict[str, Path], *extra: str) -> tuple[int, dict[str, object]]:
        out = root / "out"
        with redirect_stdout(StringIO()):
            code = main([
                "--repo-root",
                str(root),
                "--supervisor-summary",
                str(paths["supervisor"]),
                "--future-mcp-action-manifest",
                str(paths["manifest"]),
                "--screen-state-summary",
                str(paths["screen"]),
                "--current-truth",
                str(paths["truth"]),
                "--current-proof",
                str(paths["proof"]),
                "--max-artifact-age-seconds",
                "999999999",
                "--output-root",
                str(out),
                "--json",
                *extra,
            ])
        summary = json.loads((out / "character-login-play-executor-gate-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_missing_approval_blocks_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, manifest_blockers=["supervisor-execution-blockers-present"])

            code, summary = self.run_gate(root, paths)

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked-approval-required")
            self.assertIn("explicit-world-entry-approval-token-missing-or-mismatched", summary["executionBlockers"])
            self.assertFalse(summary["safety"]["mouseClickSent"])  # type: ignore[index]
            self.assertFalse(summary["mcpActionEnvelope"]["willExecuteLiveActions"])  # type: ignore[index]

    def test_matching_token_and_allow_flag_make_manual_mcp_packet_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, manifest_blockers=["supervisor-execution-blockers-present"])

            code, summary = self.run_gate(root, paths, "--approval-token", TOKEN, "--allow-world-entry")

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "ready-for-manual-mcp-executor")
            self.assertEqual(summary["mcpActionEnvelope"]["status"], "ready")  # type: ignore[index]
            self.assertFalse(summary["safety"]["worldEntryClicked"])  # type: ignore[index]

    def test_screen_state_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, bad_screen=True)

            code, summary = self.run_gate(root, paths, "--approval-token", TOKEN, "--allow-world-entry")

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked-data")
            self.assertIn("screen-state-not-character-select:classified-non-character-select", summary["blockers"])

    def test_unexpected_manifest_blocker_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, manifest_blockers=["same-target-epoch-not-observed"])

            code, summary = self.run_gate(root, paths, "--approval-token", TOKEN, "--allow-world-entry")

            self.assertEqual(code, 2)
            self.assertIn("manifest-unexpected-blocker:same-target-epoch-not-observed", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
