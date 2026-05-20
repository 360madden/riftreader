from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rift_live_test.character_login_supervisor import build_supervisor_summary, parse_json_stdout


def envelope(key: str, payload: dict[str, object], *, exit_code: int = 0) -> dict[str, object]:
    return {
        "key": key,
        "label": key,
        "command": ["python", key],
        "cwd": ".",
        "exitCode": exit_code,
        "allowedExitCode": True,
        "ok": True,
        "stdoutPreview": "{}",
        "stderrPreview": "",
        "jsonParseError": None,
        "json": payload,
    }


def crash_watch(status: str = "watch-ready", watch_status: str = "target-present-same-epoch") -> dict[str, object]:
    return {
        "status": status,
        "watchStatus": watch_status,
        "expectedTarget": {"processName": "rift_x64", "processId": 77728, "windowHandle": "0x8E13A6"},
        "dataBlockers": [],
        "watchBlockers": [] if status == "watch-ready" else ["expected-target-not-found-new-client-epoch"],
        "resumeDecision": {"resumeAtState": "refresh-character-select-readiness", "recommendedAction": "refresh"},
        "artifacts": {"summaryJson": "crash-watch.json"},
    }


def readiness_packet(status: str = "packet-ready") -> dict[str, object]:
    return {
        "status": status,
        "target": {"processName": "rift_x64", "processId": 77728, "windowHandle": "0x8E13A6"},
        "selection": {"selectedCharacter": "ATANK", "targetCharacter": "ATANK", "selectedAlready": True},
        "playButton": {"clickPoint": [517, 343], "bbox": [476, 329, 558, 357]},
        "automationReadiness": {
            "canPlanCharacterLogin": status == "packet-ready",
            "expectedApprovalToken": "ENTER-WORLD:ATANK:77728:0x8E13A6",
        },
        "dataBlockers": [],
        "artifacts": {"summaryJson": "readiness.json"},
    }


def screen_state(status: str = "classified-character-select") -> dict[str, object]:
    classification = (
        "character-selection-not-in-world"
        if status == "classified-character-select"
        else "not-character-select-or-transition"
    )
    blockers = [] if status == "classified-character-select" else ["expected-character-select-but-classified:not-character-select-or-transition"]
    return {
        "status": status,
        "classification": classification,
        "confidence": 0.91 if status == "classified-character-select" else 0.12,
        "blockers": blockers,
        "warnings": [],
        "decision": {
            "characterSelectLandmarksPresent": status == "classified-character-select",
            "safeToUseCharacterSelectClickTargets": status == "classified-character-select",
            "canTreatAsInWorld": False,
        },
        "artifacts": {"summaryJson": "screen-state.json"},
    }


def executor_contract(status: str = "blocked") -> dict[str, object]:
    blockers = [] if status == "ready-for-executor" else ["explicit-world-entry-approval-token-missing-or-mismatched"]
    return {
        "status": status,
        "blockers": blockers,
        "expectedApprovalToken": "ENTER-WORLD:ATANK:77728:0x8E13A6",
        "executorContract": {"mayClickPlay": status == "ready-for-executor"},
        "artifacts": {"summaryJson": "contract.json"},
    }


def workflow_status() -> dict[str, object]:
    return {
        "status": "blocked",
        "liveTarget": {"artifactPidStale": False, "livePids": [77728]},
        "movementGate": {"allowed": False, "status": "blocked-target-not-in-world"},
        "artifacts": {},
    }


class CharacterLoginSupervisorTests(unittest.TestCase):
    def build(self, envelopes: list[dict[str, object]], *, approved: bool = False) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / "out"
            out.mkdir()
            return build_supervisor_summary(
                repo_root=root,
                output_root=out,
                target_character="ATANK",
                envelopes=envelopes,
                approval_token_provided=approved,
            )

    def test_blocks_on_missing_approval_without_live_actions(self) -> None:
        summary = self.build(
            [
                envelope("crash-watch", crash_watch()),
                envelope("screen-state", screen_state()),
                envelope("readiness-packet", readiness_packet()),
                envelope("executor-contract", executor_contract("blocked"), exit_code=2),
                envelope("workflow-status", workflow_status(), exit_code=1),
            ]
        )

        self.assertEqual(summary["status"], "blocked-approval-required")
        self.assertTrue(summary["supervisorDecision"]["canObserveSameEpoch"])
        self.assertTrue(summary["supervisorDecision"]["canPlanCharacterLogin"])
        self.assertEqual(summary["childStatuses"]["screenClassification"], "character-selection-not-in-world")
        self.assertFalse(summary["supervisorDecision"]["mayClickPlayInThisSupervisor"])
        self.assertFalse(summary["supervisorDecision"]["futureExecutorMayClickPlay"])
        self.assertFalse(summary["safety"]["mouseClickSent"])
        self.assertIn("executor-contract-not-ready:blocked", summary["executionBlockers"])
        manifest = summary["futureMcpActionManifest"]
        self.assertEqual(manifest["status"], "blocked")
        self.assertIn("supervisor-execution-blockers-present", manifest["blockers"])
        self.assertEqual(manifest["approval"]["token"], "ENTER-WORLD:ATANK:77728:0x8E13A6")
        self.assertEqual(manifest["playButton"]["clickPoint"], [517, 343])
        self.assertTrue(manifest["neverExecuteBySupervisor"])

    def test_ready_for_approved_executor_still_does_not_click(self) -> None:
        summary = self.build(
            [
                envelope("crash-watch", crash_watch()),
                envelope("screen-state", screen_state()),
                envelope("readiness-packet", readiness_packet()),
                envelope("executor-contract", executor_contract("ready-for-executor")),
                envelope("workflow-status", workflow_status(), exit_code=1),
            ],
            approved=True,
        )

        self.assertEqual(summary["status"], "ready-for-approved-executor")
        self.assertTrue(summary["supervisorDecision"]["futureExecutorMayClickPlay"])
        self.assertFalse(summary["supervisorDecision"]["mayClickPlayInThisSupervisor"])
        self.assertFalse(summary["safety"]["worldEntryClicked"])
        manifest = summary["futureMcpActionManifest"]
        self.assertEqual(manifest["status"], "ready-for-future-approved-executor")
        click_step = next(item for item in manifest["mcpToolSequence"] if item["step"] == "click-play-once")
        self.assertEqual(click_step["tool"], "mcp__rift_game__.click_client")
        self.assertEqual(click_step["arguments"], {"x": 517, "y": 343})
        self.assertEqual(click_step["requiredApprovalToken"], "ENTER-WORLD:ATANK:77728:0x8E13A6")
        wait_step = next(item for item in manifest["mcpToolSequence"] if item["step"] == "wait-for-world-transition")
        self.assertEqual(wait_step["tool"], "mcp__rift_game__.wait_for_frame_change")
        self.assertEqual(wait_step["arguments"]["timeoutMilliseconds"], 60000)
        self.assertIn("wait_for_frame_change reports changed=false", manifest["failClosedOn"])

    def test_crash_watch_drift_blocks_supervisor(self) -> None:
        summary = self.build(
            [
                envelope("crash-watch", crash_watch("blocked", "blocked-target-drift-new-epoch"), exit_code=2),
                envelope("screen-state", screen_state()),
                envelope("readiness-packet", readiness_packet()),
                envelope("executor-contract", executor_contract("blocked"), exit_code=2),
                envelope("workflow-status", workflow_status(), exit_code=1),
            ]
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("crash-watch-not-ready:blocked-target-drift-new-epoch", summary["dataBlockers"])
        self.assertFalse(summary["supervisorDecision"]["canObserveSameEpoch"])
        self.assertIn("same-target-epoch-not-observed", summary["futureMcpActionManifest"]["blockers"])

    def test_screen_state_blocks_supervisor(self) -> None:
        summary = self.build(
            [
                envelope("crash-watch", crash_watch()),
                envelope("screen-state", screen_state("classified-non-character-select")),
                envelope("readiness-packet", readiness_packet()),
                envelope("executor-contract", executor_contract("blocked"), exit_code=2),
                envelope("workflow-status", workflow_status(), exit_code=1),
            ]
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("screen-state-not-character-select:classified-non-character-select", summary["dataBlockers"])
        self.assertFalse(summary["supervisorDecision"]["canPlanCharacterLogin"])
        self.assertIn("supervisor-data-blockers-present", summary["futureMcpActionManifest"]["blockers"])

    def test_parse_json_stdout_tolerates_wrapped_json(self) -> None:
        parsed, error = parse_json_stdout("prefix\n{\"status\":\"ok\"}\n")

        self.assertIsNone(error)
        self.assertEqual(parsed["status"], "ok")


if __name__ == "__main__":
    unittest.main()
