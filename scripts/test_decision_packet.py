from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import decision_packet  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "riftreader-tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "RiftReader Tests"], cwd=root, check=True)
    write_text(root / "agents.md", "# test\n")
    write_text(root / ".gitignore", ".riftreader-local/\n")
    write_json(
        root / "docs" / "recovery" / "current-truth.json",
        {
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xABC",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
                "inWorld": True,
                "live": True,
            },
            "bestCurrentCandidate": {
                "candidateId": "api-family-hit-000001",
                "addressHex": "0x2000",
                "candidateOnly": True,
                "promotionEligible": False,
                "status": "actor-like-current-pid-candidate-only",
            },
        },
    )
    write_json(
        root / "docs" / "recovery" / "current-proof-anchor-readback.json",
        {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:01:00Z",
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xABC",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
            "latestValidation": {"movementAllowed": True, "movementSent": False},
        },
    )
    subprocess.run(
        ["git", "add", "agents.md", ".gitignore", "docs/recovery/current-truth.json", "docs/recovery/current-proof-anchor-readback.json"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_empty_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "riftreader-tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "RiftReader Tests"], cwd=root, check=True)
    write_text(root / "agents.md", "# test\n")
    write_text(root / ".gitignore", ".riftreader-local/\n")
    subprocess.run(["git", "add", "agents.md", ".gitignore"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write_postupdate_global_container_summary(root: Path) -> Path:
    path = root / "scripts" / "captures" / "postupdate-global-container-coordinate-readback-fixture" / "summary.json"
    write_json(
        path,
        {
            "status": "candidate",
            "verdict": "global-container-coordinate-chain-current-readback-passed",
            "generatedAtUtc": "2026-06-02T21:35:11Z",
            "target": {
                "pid": 77152,
                "hwnd": "0x17A0DB2",
                "expectedProcessStartUtc": "2026-06-02T15:45:29.2617327Z",
                "moduleBase": "0x7FF7211C0000",
            },
            "bestReadback": {
                "chain": "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30",
                "coordinate": {"x": 7256.38916015625, "y": 821.4478149414062, "z": 2990.00537109375},
                "deltaVsReference": {"maxAbsDelta": 0.004628906250218279, "planarDelta": 0.004649756509549748},
                "globalRva": "0x32DD7E8",
                "parentOffset": "0x80",
                "coordinateOffset": "0x28",
                "sourceFunctionRva": "0xC38390",
                "sourceInstructionRva": "0xC3843B",
            },
            "polling": {
                "sampleCount": 5,
                "bestMatchingSampleCount": 5,
                "allSamplesMatchedReference": True,
                "stationaryDriftWithinLimit": True,
                "bestCoordinateDrift": {"maxAbsDelta": 0.0, "planarDelta": 0.0},
            },
            "blockers": [],
            "warnings": [],
            "safety": {"targetMemoryBytesRead": True, "targetMemoryBytesWritten": False},
        },
    )
    return path


def write_postupdate_yaw_facing_inventory_summary(root: Path, *, blockers: list[str] | None = None) -> Path:
    path = root / "scripts" / "captures" / "postupdate-owner-root-rediscovery-fixture" / "summary.json"
    write_json(
        path,
        {
            "status": "blocked",
            "verdict": "post-update-owner-root-rediscovery-needed",
            "generatedAtUtc": "2026-06-03T07:47:32Z",
            "topStaticCluster": {
                "functionStartRva": "0x3F8B0",
                "offsets": ["0x300", "0x304", "0x308", "0x30C", "0x310", "0x314", "0x320", "0x324", "0x328"],
                "examples": [
                    {"offset": "0x30C", "rva": "0x3FA41", "instruction": "mov dword ptr [rdi + 0x30c], r13d", "access": "write"},
                    {"offset": "0x304", "rva": "0x3FA33", "instruction": "mov dword ptr [rdi + 0x304], r13d", "access": "write"},
                ],
                "candidateOnly": True,
            },
            "staticAccessChain": {
                "status": "blocked",
                "verdict": "static-access-chain-found-orientation-root-only",
                "path": "scripts\\captures\\postupdate-static-access-chain-fixture\\summary.json",
                "candidateGlobalRoots": [
                    {
                        "globalRva": "0x335F508",
                        "rva": "0x3FCFD",
                        "access": "write",
                        "instruction": "mov qword ptr [rip + 0x331f804], rdi",
                    }
                ],
                "liveRootSamples": [
                    {
                        "rootRva": "0x335F508",
                        "rootPointer": "0x1D4BA2A6230",
                        "classification": "orientation-matrix-root-not-position-root",
                        "samples": {
                            "owner+0x300": [-0.016, 0.0, 0.999],
                            "owner+0x30C": [-13.59, 0.28, 0.95],
                        },
                    }
                ],
            },
            "blockers": blockers if blockers is not None else ["no-owner-root-hypothesis-yet"],
            "warnings": ["static-access-chain-root-orientation-only-not-position"],
        },
    )
    return path


def write_blocked_static_owner_summary(root: Path) -> Path:
    path = root / "scripts" / "captures" / "static-owner-coordinate-chain-readback-fixture" / "summary.json"
    write_json(
        path,
        {
            "generatedAtUtc": "2026-06-02T17:50:43Z",
            "status": "blocked",
            "verdict": "root-pointer-null",
            "target": {
                "processId": 77152,
                "targetWindowHandle": "0x17A0DB2",
                "expectedProcessStartUtc": "2026-06-02T15:45:29.2617327Z",
                "moduleBase": "0x7FF7211C0000",
            },
            "candidate": {
                "rootModule": "rift_x64.exe",
                "rootRva": "0x32EBC80",
                "rootAddress": "0x7FF7244ABC80",
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            },
            "reads": {
                "rootAddress": "0x7FF7244ABC80",
                "rootRva": "0x32EBC80",
                "rootPointer": "0x0",
            },
            "safety": {"targetMemoryBytesRead": True, "targetMemoryBytesWritten": False},
        },
    )
    return path


class DecisionPacketTests(unittest.TestCase):
    def test_clean_repo_without_live_target_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_empty_repo(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["targetEpoch"]["status"], "absent")
        self.assertIn("target-epoch-absent", packet["blockers"])
        self.assertEqual(packet["milestoneStatus"]["state"], "blocked-safe")

    def test_latest_postupdate_global_container_readback_is_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_empty_repo(root)
            write_postupdate_global_container_summary(root)
            write_postupdate_yaw_facing_inventory_summary(root)

            summary = decision_packet.summarize_latest_postupdate_global_container_readback(root)

        self.assertEqual(summary["status"], "candidate")
        self.assertEqual(summary["verdict"], "global-container-coordinate-chain-current-readback-passed")
        self.assertEqual(summary["chain"], "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30")
        self.assertTrue(summary["candidateOnly"])
        self.assertFalse(summary["promotionEligible"])
        self.assertFalse(summary["routeControlAuthorized"])
        self.assertEqual(summary["maxAbsDelta"], 0.004628906250218279)
        yaw_facing = summary["yawFacingCandidates"]
        self.assertEqual(yaw_facing["status"], "candidate")
        self.assertTrue(yaw_facing["candidateOnly"])
        self.assertFalse(yaw_facing["routeControlAuthorized"])
        self.assertEqual(yaw_facing["candidateRoots"][0]["globalRva"], "0x335F508")
        self.assertEqual(yaw_facing["candidateRoots"][0]["status"], "orientation-matrix-root-not-position-root")
        self.assertTrue(any(item["offset"] == "0x30C" for item in yaw_facing["fieldCandidates"]))
        self.assertIn("postupdate-yaw-facing-requires-current-readback-and-live-proof", yaw_facing["blockers"])

    def test_postupdate_candidate_changes_safe_next_action_when_old_root_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "updatedAtUtc": "2026-06-02T04:13:42Z",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 77152,
                        "targetWindowHandle": "0x17A0DB2",
                        "processStartUtc": "2026-06-02T15:45:29.2617327Z",
                        "moduleBase": "0x7FF7211C0000",
                        "inWorld": True,
                        "live": True,
                    },
                    "staticChainStatus": {
                        "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                        "promotionAllowed": True,
                        "primaryCandidate": {
                            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                            "rootModule": "rift_x64.exe",
                            "rootRva": "0x32EBC80",
                        },
                    },
                    "movementGate": {"allowed": True, "status": "historically-allowed"},
                },
            )
            write_blocked_static_owner_summary(root)
            write_postupdate_global_container_summary(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["targetEpoch"]["status"], "post-update-static-root-blocked")
        self.assertEqual(packet["safeNextAction"]["key"], "postupdate-global-container-coordinate-readback-refresh")
        self.assertEqual(packet["postUpdateRecovery"]["status"], "candidate")
        self.assertTrue(packet["postUpdateRecovery"]["candidateOnly"])
        self.assertFalse(packet["postUpdateRecovery"]["promotionEligible"])
        self.assertFalse(packet["postUpdateRecovery"]["routeControlAuthorized"])
        self.assertIn("latest-static-owner-readback-root-pointer-null", packet["blockers"])
        self.assertTrue(
            any(str(item).startswith("postupdate-coordinate-candidate-visible-not-promoted:") for item in packet["warnings"])
        )

    def test_later_target_mismatch_readback_does_not_hide_postupdate_root_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "updatedAtUtc": "2026-06-02T04:13:42Z",
                    "target": {"processId": 12664, "targetWindowHandle": "0x205146C", "inWorld": True, "live": True},
                    "staticChainStatus": {
                        "status": "promoted",
                        "promotionAllowed": True,
                        "primaryCandidate": {
                            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                            "rootRva": "0x32EBC80",
                        },
                    },
                },
            )
            write_blocked_static_owner_summary(root)
            write_json(
                root / "scripts" / "captures" / "static-owner-coordinate-chain-readback-newer-target-mismatch" / "summary.json",
                {
                    "generatedAtUtc": "2026-06-02T22:32:24Z",
                    "status": "blocked",
                    "verdict": "target-hwnd-pid-mismatch",
                    "target": {"processId": 12664, "targetWindowHandle": "0x205146C"},
                    "safety": {"targetMemoryBytesRead": False},
                },
            )
            write_postupdate_global_container_summary(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["targetEpoch"]["status"], "post-update-static-root-blocked")
        self.assertEqual(packet["staticOwnerReadback"]["verdict"], "root-pointer-null")
        self.assertEqual(
            packet["staticOwnerReadback"]["latestAttempt"]["verdict"],
            "target-hwnd-pid-mismatch",
        )
        self.assertIn("latest-static-owner-readback-root-pointer-null", packet["blockers"])

    def test_postupdate_target_identity_drift_refreshes_window_targets_before_rediscovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "updatedAtUtc": "2026-06-02T04:13:42Z",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 77152,
                        "targetWindowHandle": "0x17A0DB2",
                        "processStartUtc": "2026-06-02T15:45:29.2617327Z",
                        "moduleBase": "0x7FF7211C0000",
                        "inWorld": True,
                        "live": True,
                    },
                    "staticChainStatus": {
                        "status": "promoted",
                        "promotionAllowed": True,
                        "primaryCandidate": {
                            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                            "rootRva": "0x32EBC80",
                        },
                    },
                },
            )
            write_blocked_static_owner_summary(root)
            write_postupdate_yaw_facing_inventory_summary(
                root,
                blockers=["no-owner-root-hypothesis-yet", "pid-hwnd-mismatch", "process-start-mismatch"],
            )

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["targetEpoch"]["status"], "post-update-static-root-blocked")
        self.assertEqual(packet["safeNextAction"]["key"], "refresh-rift-window-target-discovery")
        self.assertEqual(packet["safeNextAction"]["command"], ["scripts\\get-rift-window-targets.cmd", "-Json"])
        self.assertIn("pid-hwnd-mismatch", packet["safeNextAction"]["why"])
        self.assertIn("process-start-mismatch", packet["safeNextAction"]["why"])
        self.assertIn(
            "pid-hwnd-mismatch",
            packet["postUpdateRecovery"]["yawFacingCandidates"]["blockers"],
        )
        self.assertIn("latest-static-owner-readback-root-pointer-null", packet["blockers"])

    def test_target_epoch_classifies_current_match(self) -> None:
        truth = {"target": {"processId": 1, "targetWindowHandle": "0x1", "inWorld": True}}
        proof = {"status": "current-target-proofonly-passed", "target": {"processId": 1, "targetWindowHandle": "0x1"}}

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "current")
        self.assertEqual(result["blockers"], [])

    def test_target_epoch_does_not_treat_proof_only_as_current_without_truth_target(self) -> None:
        proof = {
            "status": "current-target-proofonly-passed",
            "target": {"processId": 1, "targetWindowHandle": "0x1"},
        }

        result = decision_packet.classify_target_epoch({}, proof)

        self.assertEqual(result["status"], "in-world-unproven")
        self.assertIn("current-truth-target-missing", result["blockers"])
        self.assertNotEqual(result["status"], "current")

    def test_target_epoch_detects_pid_hwnd_process_and_module_drift(self) -> None:
        truth = {
            "target": {
                "processId": 2,
                "targetWindowHandle": "0x2",
                "processStartUtc": "2026-05-21T15:00:00Z",
                "moduleBase": "0x2000",
            }
        }
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:00:00Z",
            "target": {
                "processId": 1,
                "targetWindowHandle": "0x1",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
        }

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "stale")
        self.assertIn("target-epoch-pid-drift", result["blockers"])
        self.assertIn("target-epoch-hwnd-drift", result["blockers"])
        self.assertIn("target-epoch-process-start-drift", result["blockers"])
        self.assertIn("target-epoch-module-base-drift", result["blockers"])
        self.assertIn("proof-older-than-process-start", result["blockers"])

    def test_target_epoch_drift_scenarios_block_individually(self) -> None:
        base_truth_target = {
            "processId": 1,
            "targetWindowHandle": "0x1",
            "processStartUtc": "2026-05-21T14:00:00Z",
            "moduleBase": "0x1000",
            "inWorld": True,
        }
        base_proof_target = {
            "processId": 1,
            "targetWindowHandle": "0x1",
            "processStartUtc": "2026-05-21T14:00:00Z",
            "moduleBase": "0x1000",
        }
        cases = [
            ("processId", 2, "target-epoch-pid-drift"),
            ("targetWindowHandle", "0x2", "target-epoch-hwnd-drift"),
            ("processStartUtc", "2026-05-21T15:00:00Z", "target-epoch-process-start-drift"),
            ("moduleBase", "0x2000", "target-epoch-module-base-drift"),
        ]
        for field, value, blocker in cases:
            with self.subTest(field=field):
                truth_target = dict(base_truth_target)
                truth_target[field] = value
                result = decision_packet.classify_target_epoch(
                    {"target": truth_target},
                    {"status": "current-target-proofonly-passed", "target": base_proof_target},
                )

                self.assertEqual(result["status"], "stale")
                self.assertIn(blocker, result["blockers"])
                self.assertEqual(
                    result["staleAddressPolicy"],
                    "absolute heap addresses are historical hints only after PID/HWND/process-start/module-base drift",
                )

    def test_process_presence_is_not_proof(self) -> None:
        result = decision_packet.classify_target_epoch({"target": {"processId": 1, "live": True}}, {})

        self.assertEqual(result["processPresence"], "not-checked-process-presence-is-not-proof")
        self.assertIn(result["status"], {"in-world-unproven", "unknown"})

    def test_summarize_truth_blocks_stale_proof_freshness_for_movement(self) -> None:
        truth = {
            "movementGate": {
                "allowed": True,
                "status": "allowed-current-target-proofonly-passed-route-smoke-passed",
                "reason": "historically allowed",
            }
        }
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-27T07:00:00Z",
            "latestValidation": {
                "status": "valid",
                "movementAllowed": True,
                "movementSent": False,
                "generatedAtUtc": "2026-05-27T07:00:00Z",
            },
        }

        summary = decision_packet.summarize_truth(
            truth,
            proof,
            now=datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc),
        )

        movement_gate = summary["movementGate"]
        self.assertFalse(movement_gate["allowed"])
        self.assertEqual(movement_gate["status"], "blocked-proof-anchor-age-out-of-range")
        self.assertEqual(movement_gate["proofFreshness"]["ageSeconds"], 120)
        self.assertIn("proof-anchor-stale-for-movement:ageSeconds=120;maxAgeSeconds=60", movement_gate["blockers"])
        self.assertIn("same-target ProofOnly/proof-anchor refresh", movement_gate["reason"])

    def test_build_decision_packet_includes_stale_proof_movement_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "target": {
                        "processName": "rift_x64",
                        "processId": 100,
                        "targetWindowHandle": "0xABC",
                        "processStartUtc": "2026-05-27T07:00:00Z",
                        "moduleBase": "0x1000",
                        "inWorld": True,
                        "live": True,
                    },
                    "movementGate": {
                        "allowed": True,
                        "status": "allowed-current-target-proofonly-passed-route-smoke-passed",
                        "reason": "historically allowed",
                    },
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "current-target-proofonly-passed",
                    "lastUpdatedUtc": "2026-05-27T07:00:00Z",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 100,
                        "targetWindowHandle": "0xABC",
                        "processStartUtc": "2026-05-27T07:00:00Z",
                        "moduleBase": "0x1000",
                    },
                    "latestValidation": {
                        "status": "valid",
                        "movementAllowed": True,
                        "movementSent": False,
                        "generatedAtUtc": "2026-05-27T07:00:00Z",
                    },
                },
            )

            packet = decision_packet.build_decision_packet(
                root,
                now=datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc),
            )

        self.assertIn("proof-anchor-stale-for-movement:ageSeconds=120;maxAgeSeconds=60", packet["blockers"])
        self.assertEqual(packet["truth"]["movementGate"]["status"], "blocked-proof-anchor-age-out-of-range")

    def test_visible_rift_process_with_stale_proof_is_not_current_truth(self) -> None:
        truth = {
            "target": {
                "processName": "rift_x64",
                "processId": 200,
                "targetWindowHandle": "0xBEEF",
                "processStartUtc": "2026-05-21T15:00:00Z",
                "moduleBase": "0x2000",
                "inWorld": True,
                "live": True,
            }
        }
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:00:00Z",
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xCAFE",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
        }

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "stale")
        self.assertNotEqual(result["status"], "current")
        self.assertEqual(result["processPresence"], "not-checked-process-presence-is-not-proof")
        self.assertIn("target-epoch-pid-drift", result["blockers"])
        self.assertIn("target-epoch-hwnd-drift", result["blockers"])
        self.assertIn("target-epoch-process-start-drift", result["blockers"])
        self.assertIn("target-epoch-module-base-drift", result["blockers"])
        self.assertIn("proof-older-than-process-start", result["blockers"])
        self.assertEqual(
            result["staleAddressPolicy"],
            "absolute heap addresses are historical hints only after PID/HWND/process-start/module-base drift",
        )

    def test_promoted_static_resolver_supersedes_stale_proof_epoch(self) -> None:
        truth = {
            "target": {
                "processName": "rift_x64",
                "processId": 200,
                "targetWindowHandle": "0xBEEF",
                "processStartUtc": "2026-05-21T15:00:00Z",
                "moduleBase": "0x2000",
                "inWorld": True,
                "live": True,
            },
            "staticChainStatus": {
                "status": "promoted",
                "promotionAllowed": True,
                "primaryCandidate": {
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "rootModule": "rift_x64.exe",
                    "rootRva": "0x32EBC80",
                },
                "latestApiNowValidation": {"status": "passed"},
            },
        }
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:00:00Z",
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xCAFE",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
        }

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "current-static-resolver")
        self.assertEqual(result["blockers"], [])
        self.assertIn("proof-anchor-stale-superseded-by-promoted-static-resolver", result["warnings"])
        self.assertTrue(result["staticResolver"]["promoted"])
        self.assertEqual(result["staticResolver"]["rootRva"], "0x32EBC80")

    def test_newer_root_null_readback_blocks_promoted_static_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "updatedAtUtc": "2026-06-02T04:13:42Z",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 12664,
                        "targetWindowHandle": "0x205146C",
                        "processStartUtc": "2026-06-01T17:19:45Z",
                        "moduleBase": "0x7FF6EE5D0000",
                        "inWorld": True,
                        "live": True,
                    },
                    "staticChainStatus": {
                        "status": "promoted",
                        "promotionAllowed": True,
                        "primaryCandidate": {
                            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                            "rootModule": "rift_x64.exe",
                            "rootRva": "0x32EBC80",
                        },
                        "latestApiNowValidation": {"status": "passed"},
                    },
                },
            )
            write_json(
                root / "scripts" / "captures" / "static-owner-coordinate-chain-readback-20260602-175043-068641" / "summary.json",
                {
                    "mode": "static-owner-coordinate-resolver-readback",
                    "generatedAtUtc": "2026-06-02T17:50:43Z",
                    "status": "blocked",
                    "verdict": "root-pointer-null",
                    "target": {
                        "processId": 77152,
                        "targetWindowHandle": "0x17A0DB2",
                        "expectedProcessStartUtc": "2026-06-02T15:45:29Z",
                        "moduleBase": "0x7FF7211C0000",
                    },
                    "candidate": {"rootRva": "0x32EBC80", "rootAddress": "0x7FF7244ABC80"},
                    "reads": {"rootRva": "0x32EBC80", "rootAddress": "0x7FF7244ABC80", "rootPointer": "0x0"},
                    "safety": {"movementSent": False, "inputSent": False, "targetMemoryBytesWritten": False},
                },
            )

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["targetEpoch"]["status"], "post-update-static-root-blocked")
        self.assertIn("latest-static-owner-readback-root-pointer-null", packet["blockers"])
        self.assertTrue(packet["staticOwnerReadback"]["blocksCurrentStaticResolver"])
        self.assertEqual(packet["safeNextAction"]["key"], "postupdate-owner-root-rediscovery")
        self.assertFalse(packet["truth"]["movementGate"]["allowed"])
        self.assertEqual(packet["truth"]["movementGate"]["status"], "blocked-post-update-static-root-null")
        self.assertFalse(packet["truth"]["actorChain"]["staticResolver"]["usableForNavigation"])

    def test_unpromoted_static_resolver_does_not_supersede_stale_proof_epoch(self) -> None:
        truth = {
            "target": {
                "processName": "rift_x64",
                "processId": 200,
                "targetWindowHandle": "0xBEEF",
                "processStartUtc": "2026-05-21T15:00:00Z",
                "moduleBase": "0x2000",
                "inWorld": True,
                "live": True,
            },
            "staticChainStatus": {
                "status": "promotion-review-ready-not-promoted",
                "promotionAllowed": False,
                "primaryCandidate": {
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "rootRva": "0x32EBC80",
                },
            },
        }
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:00:00Z",
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xCAFE",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
        }

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "stale")
        self.assertIn("target-epoch-pid-drift", result["blockers"])
        self.assertFalse(result["staticResolver"]["promoted"])

    def test_unpromoted_static_resolver_routes_to_actor_chain_lane_despite_stale_proof(self) -> None:
        truth_summary = {
            "actorChain": {
                "status": "blocked",
                "staticResolver": {
                    "complete": True,
                    "promoted": False,
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                },
            }
        }
        target_epoch = {"status": "stale", "blockers": ["target-epoch-pid-drift"]}
        git_state = {"changedFiles": [], "dirty": False}

        lane = decision_packet.classify_lane(git_state, target_epoch, truth_summary)
        safe_next = decision_packet.build_safe_next_action(lane, target_epoch, git_state, truth_summary)

        self.assertEqual(lane, "actor-chain")
        self.assertEqual(safe_next["key"], "static-chain-promotion-readiness")
        self.assertEqual(safe_next["command"], ["python", ".\\scripts\\static_chain_promotion_readiness.py", "--json"])
        self.assertIn("fresh-reference gate", safe_next["why"])

    def test_actor_chain_candidate_only_blocks_promotion(self) -> None:
        result = decision_packet.summarize_truth(
            {
                "bestCurrentCandidate": {
                    "candidateId": "api-family-hit-000001",
                    "candidateOnly": True,
                    "promotionEligible": False,
                    "status": "actor-like-candidate-only",
                }
            },
            {"status": "current-target-proofonly-passed"},
        )

        actor = result["actorChain"]
        self.assertEqual(actor["status"], "candidate-only")
        self.assertFalse(actor["promotionAllowed"])
        self.assertIn("actor-chain-candidate-only", actor["blockers"])
        self.assertIn("no-static-resolver-promoted", actor["blockers"])

    def test_validation_plan_selects_decision_packet_checks_for_python_change(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "tools/riftreader_workflow/decision_packet.py"}]},
            "git",
        )
        labels = {item["label"] for item in plan["commands"]}

        self.assertIn("py-compile-decision-packet", labels)
        self.assertIn("decision-packet-tests", labels)
        self.assertIn("policy-lint-changed", labels)

    def test_validation_plan_selects_tool_catalog_checks_for_tool_catalog_change(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "tools/riftreader_workflow/tool_catalog.py"}]},
            "git",
        )
        labels = {item["label"] for item in plan["commands"]}

        self.assertIn("tool-catalog-tests", labels)
        self.assertIn("tool-catalog-self-test", labels)

    def test_validation_plan_selects_postupdate_seed_checks_for_seed_change(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "scripts/postupdate_root_signature_seed.py"}]},
            "proof-recovery",
        )
        labels = {item["label"] for item in plan["commands"]}

        self.assertIn("postupdate-root-signature-seed-tests", labels)
        self.assertIn("postupdate-root-signature-seed-self-test", labels)

    def test_validation_plan_selects_live_input_audit_checks_for_audit_change(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "scripts/live_input_surface_audit.py"}]},
            "git",
        )
        labels = {item["label"] for item in plan["commands"]}

        self.assertIn("live-input-surface-audit-tests", labels)

    def test_validation_plan_selects_retired_surface_policy_tests_for_policy_docs(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "docs/workflow/codex-agent-routing-policy.md"}]},
            "docs",
        )
        labels = {item["label"] for item in plan["commands"]}

        self.assertIn("retired-surface-policy-tests", labels)

    def test_validation_plan_compiles_changed_python_file(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "scripts/test_retired_surface_policy.py", "status": "??"}]},
            "git",
        )
        compile_commands = [item for item in plan["commands"] if item["label"] == "py-compile-decision-packet"]
        labels = {item["label"] for item in plan["commands"]}

        self.assertEqual(len(compile_commands), 1)
        self.assertIn("scripts/test_retired_surface_policy.py", compile_commands[0]["command"])
        self.assertIn("retired-surface-policy-tests", labels)

    def test_dirty_docs_only_lane_and_commit_plan_are_coherent(self) -> None:
        git_state = {"changedFiles": [{"path": "docs/workflow/example.md", "generated": False}], "dirty": True}

        self.assertEqual(decision_packet.classify_lane(git_state, {"status": "current"}, {}), "docs")
        commit_plan = decision_packet.build_commit_plan(git_state, [{"ok": True}])

        self.assertTrue(commit_plan["recommended"])
        self.assertEqual(commit_plan["pathCategories"], ["docs"])
        self.assertEqual(commit_plan["suggestedMessage"], "Update RiftReader workflow docs")
        self.assertEqual(commit_plan["stageCommand"], ["git", "add", "--", "docs/workflow/example.md"])

    def test_code_only_commit_plan_uses_helper_message_not_docs_message(self) -> None:
        commit_plan = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "tools/riftreader_workflow/operator_lite.py", "generated": False}]},
            [{"ok": True}],
        )

        self.assertTrue(commit_plan["recommended"])
        self.assertEqual(commit_plan["pathCategories"], ["code"])
        self.assertEqual(commit_plan["suggestedMessage"], "Update RiftReader workflow helpers")

    def test_commit_plan_quotes_stage_preview_paths_with_spaces(self) -> None:
        commit_plan = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "docs/workflow/example with space.md", "generated": False}]},
            [{"ok": True}],
        )

        self.assertTrue(commit_plan["recommended"])
        self.assertEqual(commit_plan["stageCommand"], ["git", "add", "--", "docs/workflow/example with space.md"])
        self.assertEqual(commit_plan["stageCommandPreview"], "git add -- 'docs/workflow/example with space.md'")

    def test_commit_plan_quotes_stage_preview_shell_metacharacters(self) -> None:
        commit_plan = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "docs/workflow/example&name.md", "generated": False}]},
            [{"ok": True}],
        )

        self.assertTrue(commit_plan["recommended"])
        self.assertEqual(commit_plan["stageCommandPreview"], "git add -- 'docs/workflow/example&name.md'")

    def test_commit_plan_excludes_generated_and_blocks_live_truth(self) -> None:
        generated = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "scripts/captures/run/summary.json", "generated": True}]}
        )
        live_truth = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "docs/recovery/current-truth.json", "generated": False}]}
        )

        self.assertFalse(generated["recommended"])
        self.assertEqual(generated["excludedGeneratedPaths"], ["scripts/captures/run/summary.json"])
        self.assertIsNone(generated["stageCommand"])
        self.assertFalse(live_truth["recommended"])
        self.assertEqual(live_truth["reason"], "live-truth-paths-require-main-agent-review")
        self.assertIsNone(live_truth["stageCommand"])

    def test_commit_plan_blocks_mixed_docs_code_and_generated_slice(self) -> None:
        mixed = decision_packet.build_commit_plan(
            {
                "changedFiles": [
                    {"path": "docs/workflow/example.md", "generated": False},
                    {"path": "tools/riftreader_workflow/decision_packet.py", "generated": False},
                    {"path": "scripts/captures/run/summary.json", "generated": True},
                ]
            },
            [{"ok": True}],
        )

        self.assertFalse(mixed["recommended"])
        self.assertEqual(mixed["reason"], "mixed-risk-worktree-split-required")
        self.assertEqual(mixed["pathCategories"], ["code", "docs"])
        self.assertEqual(mixed["excludedGeneratedPaths"], ["scripts/captures/run/summary.json"])

    def test_clean_branch_ahead_reports_commits_before_other_safe_work(self) -> None:
        safe_next = decision_packet.build_safe_next_action(
            "unknown",
            {"status": "current"},
            {"dirty": False, "ahead": 2},
            {"actorChain": {"status": "candidate-only"}},
        )

        self.assertEqual(safe_next["key"], "report-local-commits-ahead")
        self.assertEqual(safe_next["command"], ["git", "--no-pager", "status", "--short", "--branch"])

    def test_candidate_only_routes_to_ghidra_static_plan_before_more_actor_work(self) -> None:
        safe_next = decision_packet.build_safe_next_action(
            "actor-chain",
            {"status": "current"},
            {"dirty": False, "ahead": 0, "changedFiles": []},
            {"actorChain": {"status": "candidate-only"}},
        )

        self.assertEqual(safe_next["key"], "ghidra-static-plan-before-actor-chain-status")
        self.assertEqual(safe_next["command"], [".\\scripts\\riftreader-tool-catalog.cmd", "--ghidra-static-plan", "--json"])
        self.assertIn("offline Ghidra static lane", safe_next["why"])

    def test_post_validation_commit_ready_action_avoids_safe_check_loop(self) -> None:
        safe_next = decision_packet.build_post_validation_next_action(
            True,
            {
                "recommended": True,
                "explicitPaths": ["tools/riftreader_workflow/decision_packet.py"],
                "stageCommandPreview": "git add -- tools/riftreader_workflow/decision_packet.py",
            },
        )

        self.assertIsNotNone(safe_next)
        self.assertEqual(safe_next["key"], "commit-ready-explicit-paths")
        self.assertEqual(safe_next["command"], ["git", "--no-pager", "status", "--short", "--branch"])
        self.assertIn("instead of rerunning validations", safe_next["why"])

    def test_agent_plan_has_no_overlapping_write_paths(self) -> None:
        plan = decision_packet.build_agent_plan()

        self.assertEqual(decision_packet.validate_agent_plan(plan), [])
        for item in plan:
            self.assertIn(item["authority"], {"read", "write"})
            self.assertTrue(item["ownedPaths"])
            self.assertTrue(item["forbiddenPaths"])
            self.assertTrue(item["validation"])

    def test_agent_plan_validator_rejects_duplicate_owned_path(self) -> None:
        errors = decision_packet.validate_agent_plan(
            [
                {
                    "name": "one",
                    "authority": "write",
                    "ownedPaths": ["tools/example.py"],
                    "forbiddenPaths": [],
                    "risk": "low",
                    "validation": ["python -m py_compile tools/example.py"],
                },
                {
                    "name": "two",
                    "authority": "write",
                    "ownedPaths": [r"tools\example.py"],
                    "forbiddenPaths": [],
                    "risk": "low",
                    "validation": ["python -m py_compile tools/example.py"],
                },
            ]
        )

        self.assertEqual(errors, ["agent-plan-overlapping-owned-path:tools/example.py:one:two"])

    def test_agent_plan_validator_rejects_self_forbidden_owned_path_pattern(self) -> None:
        errors = decision_packet.validate_agent_plan(
            [
                {
                    "name": "docs",
                    "authority": "write",
                    "ownedPaths": ["docs/workflow/local-decision-control-plane-plan.md"],
                    "forbiddenPaths": ["docs/**"],
                    "risk": "low",
                    "validation": ["git --no-pager diff --check"],
                }
            ]
        )

        self.assertEqual(
            errors,
            [
                "agent-plan-owned-path-forbidden:docs/workflow/local-decision-control-plane-plan.md:docs:docs/**",
            ],
        )

    def test_agent_plan_validator_rejects_malformed_slice_contract(self) -> None:
        errors = decision_packet.validate_agent_plan(
            [
                {
                    "name": "bad-slice",
                    "authority": "admin",
                    "ownedPaths": [],
                    "forbiddenPaths": [],
                    "risk": "extreme",
                    "validation": [],
                }
            ]
        )

        self.assertEqual(
            errors,
            [
                "agent-plan-invalid-authority:bad-slice:admin",
                "agent-plan-invalid-risk:bad-slice:extreme",
                "agent-plan-empty-owned-paths:bad-slice",
                "agent-plan-empty-validation:bad-slice",
            ],
        )

    def test_agent_plan_validator_rejects_missing_required_fields(self) -> None:
        errors = decision_packet.validate_agent_plan([{"name": "partial"}])

        self.assertEqual(
            errors,
            [
                "agent-plan-missing-field:partial:authority",
                "agent-plan-missing-field:partial:ownedPaths",
                "agent-plan-missing-field:partial:forbiddenPaths",
                "agent-plan-missing-field:partial:risk",
                "agent-plan-missing-field:partial:validation",
                "agent-plan-invalid-authority:partial:missing",
                "agent-plan-invalid-risk:partial:missing",
                "agent-plan-empty-owned-paths:partial",
                "agent-plan-empty-validation:partial",
            ],
        )

    def test_high_risk_approval_blocker_requires_stop_state(self) -> None:
        self.assertEqual(decision_packet.milestone_state(["debugger-required"]), "blocked-needs-approval")
        reminder = decision_packet.build_llm_reminder({"command": ["ask"]}, "blocked-needs-approval")

        self.assertIn("debugger or CE would be required", reminder["mustStopIf"])

    def test_safe_validation_exit_two_is_known_safe_blocked_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "safe_blocker.py"
            write_text(script, "raise SystemExit(2)\n")
            plan = {
                "commands": [
                    decision_packet.command_spec(
                        "known-safe-blocker",
                        [sys.executable, str(script)],
                        "Fixture exits 2 as a known blocker.",
                        expected=(0, 2),
                    )
                ]
            }

            results = decision_packet.run_safe_validations(root, plan)

        self.assertEqual(results[0]["exitCode"], 2)
        self.assertTrue(results[0]["ok"])
        self.assertTrue(results[0]["knownSafeBlocked"])

    def test_llm_reminder_contains_continue_and_stop_rules(self) -> None:
        reminder = decision_packet.build_llm_reminder({"command": ["python", "x.py"]}, "blocked-safe")

        self.assertIn("safe validation passed", reminder["doNotStopIf"])
        self.assertIn("debugger or CE would be required", reminder["mustStopIf"])
        self.assertEqual(reminder["continueWith"]["command"], ["python", "x.py"])

    def test_build_decision_packet_from_temp_repo_reports_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["kind"], "riftreader-decision-packet")
        self.assertEqual(packet["targetEpoch"]["status"], "current")
        self.assertEqual(packet["truth"]["actorChain"]["status"], "candidate-only")
        self.assertIn("actor-chain-candidate-only", packet["blockers"])
        self.assertEqual(packet["milestoneStatus"]["state"], "blocked-safe")

    def _write_route_run_report(self, root: Path, *, terrain_blocked: bool = False, no_progress_count: int = 0, arrived: bool = True, steps_run: int = 2) -> None:
        """Write a route-run report fixture with configurable terrain evidence."""
        report_dir = root / "scripts" / "captures" / "2026-05-29" / "static-owner-nav-route-run-report" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)
        steps: list[dict[str, Any]] = []
        for i in range(1, steps_run + 1):
            is_last = i == steps_run
            if is_last and arrived:
                steps.append({
                    "stepNumber": i, "status": "passed",
                    "verdict": "route-step-live-movement-progress-validated",
                    "routeStatus": "arrived", "stopReason": "within-arrival-radius",
                })
            elif terrain_blocked and i <= no_progress_count:
                steps.append({
                    "stepNumber": i, "status": "blocked",
                    "verdict": "route-step-blocked", "routeStatus": "no-progress",
                    "stopReason": "no-progress",
                    "noProgressSubClassification": "blocked-stationary-no-movement",
                })
            elif no_progress_count > 0 and i <= no_progress_count:
                steps.append({
                    "stepNumber": i, "status": "blocked",
                    "verdict": "route-step-blocked", "routeStatus": "no-progress",
                    "stopReason": "no-progress",
                    "noProgressSubClassification": "insufficient-progress-below-threshold",
                })
            else:
                steps.append({
                    "stepNumber": i, "status": "passed",
                    "verdict": "route-step-live-movement-progress-validated",
                    "routeStatus": "progress", "stopReason": "distance-decreased",
                })
        report = {
            "schemaVersion": 1,
            "kind": "static-owner-nav-route-run-report",
            "generatedAtUtc": "2026-05-29T00:00:00Z",
            "status": "passed" if arrived else "blocked",
            "sourceSummaryJson": "fixture/summary.json",
            "source": {
                "kind": "static-owner-nav-route-run",
                "status": "passed" if arrived else "blocked",
                "verdict": "route-run-arrived" if arrived else "route-run-blocked",
                "aggregate": {
                    "stepsRun": steps_run, "arrived": arrived,
                    "lastRouteStatus": "arrived" if arrived else "no-progress",
                },
                "steps": steps,
            },
            "contract": {"status": "passed" if arrived else "blocked", "stepsRun": steps_run, "arrived": arrived},
        }
        report_path = report_dir / "summary.json"
        write_json(report_path, report)

    def test_route_run_report_terrain_missing_when_no_captures_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_empty_repo(root)

            terrain = decision_packet._summarize_latest_route_run_report_terrain(root)

        self.assertEqual(terrain["status"], "route-run-report-missing")
        self.assertFalse(terrain["capturesDirectoryExists"])

    def test_route_run_report_terrain_missing_when_no_report_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            (root / "scripts" / "captures").mkdir(parents=True, exist_ok=True)
            write_json(root / "scripts" / "captures" / "other" / "summary.json", {"kind": "not-a-route-run-report"})

            terrain = decision_packet._summarize_latest_route_run_report_terrain(root)

        self.assertEqual(terrain["status"], "route-run-report-missing")
        self.assertTrue(terrain["capturesDirectoryExists"])
        self.assertEqual(terrain["candidateCount"], 0)

    def test_route_run_report_terrain_found_with_clean_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, arrived=True, steps_run=2)

            terrain = decision_packet._summarize_latest_route_run_report_terrain(root)

        self.assertEqual(terrain["status"], "route-run-report-found")
        self.assertTrue(terrain["arrived"])
        self.assertEqual(terrain["stepsRun"], 2)
        self.assertEqual(terrain["noProgressStepCount"], 0)
        self.assertEqual(terrain["terrainSubClassifications"], {})
        self.assertFalse(terrain["terrainBlockerPresent"])

    def test_route_run_report_terrain_found_with_blocked_stationary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=True, no_progress_count=1, arrived=False, steps_run=2)

            terrain = decision_packet._summarize_latest_route_run_report_terrain(root)

        self.assertEqual(terrain["status"], "route-run-report-found")
        self.assertFalse(terrain["arrived"])
        self.assertEqual(terrain["noProgressStepCount"], 1)
        self.assertEqual(terrain["terrainSubClassifications"], {"blocked-stationary-no-movement": 1})
        self.assertTrue(terrain["terrainBlockerPresent"])

    def test_route_run_report_terrain_count_aggregates_multiple_no_progress_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=True, no_progress_count=2, arrived=False, steps_run=3)

            terrain = decision_packet._summarize_latest_route_run_report_terrain(root)

        self.assertEqual(terrain["noProgressStepCount"], 2)
        self.assertEqual(terrain["terrainSubClassifications"], {"blocked-stationary-no-movement": 2})
        self.assertTrue(terrain["terrainBlockerPresent"])

    def test_decision_packet_includes_navigation_terrain_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=True, no_progress_count=1, arrived=False, steps_run=2)

            packet = decision_packet.build_decision_packet(root)

        self.assertIn("navigationTerrain", packet)
        terrain = packet["navigationTerrain"]
        self.assertEqual(terrain["status"], "route-run-report-found")
        self.assertTrue(terrain["terrainBlockerPresent"])
        self.assertEqual(terrain["noProgressStepCount"], 1)
        self.assertEqual(terrain["terrainSubClassifications"], {"blocked-stationary-no-movement": 1})

    def test_decision_packet_surfaces_terrain_blocker_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=True, no_progress_count=1, arrived=False, steps_run=2)

            packet = decision_packet.build_decision_packet(root)

        terrain_warnings = [w for w in packet["warnings"] if w.startswith("navigation-terrain-blocked-stationary")]
        self.assertEqual(len(terrain_warnings), 1)
        self.assertIn("count=1", terrain_warnings[0])
        self.assertIn("check navigation resume status for terrain scouting guidance", terrain_warnings[0])

    def test_decision_packet_surfaces_no_progress_counts_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=False, no_progress_count=2, arrived=False, steps_run=3)

            packet = decision_packet.build_decision_packet(root)

        terrain_warnings = [w for w in packet["warnings"] if w.startswith("navigation-terrain-no-progress-steps")]
        self.assertEqual(len(terrain_warnings), 1)
        self.assertIn("count=2", terrain_warnings[0])

    def test_decision_packet_no_terrain_warning_without_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)

            packet = decision_packet.build_decision_packet(root)

        terrain_warnings = [w for w in packet["warnings"] if w.startswith("navigation-terrain-")]
        self.assertEqual(terrain_warnings, [])
        self.assertEqual(packet["navigationTerrain"]["status"], "route-run-report-missing")

    def test_compact_packet_includes_terrain_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=True, no_progress_count=1, arrived=False, steps_run=2)

            packet = decision_packet.build_decision_packet(root)
            compact = decision_packet.compact_decision_packet(packet)

        self.assertIn("navigationTerrain", compact)
        terrain = compact["navigationTerrain"]
        self.assertEqual(terrain["status"], "route-run-report-found")
        self.assertTrue(terrain["terrainBlockerPresent"])
        self.assertEqual(terrain["noProgressStepCount"], 1)

    def test_markdown_includes_terrain_context_when_report_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            self._write_route_run_report(root, terrain_blocked=True, no_progress_count=1, arrived=False, steps_run=2)

            packet = decision_packet.build_decision_packet(root)
            markdown = decision_packet.build_markdown(packet)

        self.assertIn("## Navigation terrain context (from latest route-run report)", markdown)
        self.assertIn("`blocked-stationary-no-movement`", markdown)
        self.assertIn("Terrain blocker detected", markdown)

    def test_markdown_reports_missing_terrain_context_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)

            packet = decision_packet.build_decision_packet(root)
            markdown = decision_packet.build_markdown(packet)

        self.assertIn("## Navigation terrain context", markdown)
        self.assertIn("No route-run report available for terrain context", markdown)

    def test_full_packet_schema_preserves_required_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(
            set(packet),
            {
                "schemaVersion",
                "kind",
                "helperVersion",
                "generatedAtUtc",
                "status",
                "lane",
                "risk",
                "repoRoot",
                "repo",
                "targetEpoch",
                "truth",
                "toolCatalog",
                "staticOwnerReadback",
                "postUpdateRecovery",
                "navigationTerrain",
                "navigationPointerChains",
                "navigationPointerDiscovery",
                "retiredSurfaces",
                "allowedActions",
                "forbiddenActions",
                "safeNextAction",
                "automationPlan",
                "validationPlan",
                "validationResults",
                "commitPlan",
                "agentPlan",
                "llmReminder",
                "milestoneStatus",
                "fingerprint",
                "cacheStatus",
                "performance",
                "cacheSafety",
                "blockers",
                "warnings",
                "errors",
                "safety",
            },
        )
        self.assertEqual(packet["schemaVersion"], decision_packet.SCHEMA_VERSION)
        self.assertEqual(packet["kind"], "riftreader-decision-packet")
        self.assertIn("command", packet["safeNextAction"])
        self.assertIn("commands", packet["validationPlan"])
        self.assertIn("safeRefreshCommand", packet["toolCatalog"])
        self.assertIn("blocksCurrentStaticResolver", packet["staticOwnerReadback"])
        self.assertIn("recommendedGhidraAction", packet["toolCatalog"])
        self.assertIn("recommendedTriggers", packet["toolCatalog"]["ghidraStaticLane"])
        self.assertIn("recommended", packet["commitPlan"])
        self.assertIn("banner", packet["llmReminder"])
        self.assertIn("state", packet["milestoneStatus"])
        self.assertIn("buildMode", packet["performance"])
        self.assertFalse(packet["safety"]["movementSent"])

    def test_schema_contract_lists_required_fields_and_stage_command(self) -> None:
        contract = decision_packet.build_schema_contract()

        self.assertEqual(contract["kind"], "riftreader-decision-packet-schema-contract")
        self.assertIn("commitPlan", contract["requiredTopLevelFields"])
        self.assertIn("toolCatalog", contract["requiredTopLevelFields"])
        self.assertIn("staticOwnerReadback", contract["requiredTopLevelFields"])
        self.assertIn("blocksCurrentStaticResolver", contract["staticOwnerReadbackFields"])
        self.assertIn("stageCommand", contract["commitPlanFields"])
        self.assertIn("stageCommandPreview", contract["commitPlanFields"])
        self.assertIn("retiredSurfacePaths", contract["commitPlanFields"])
        self.assertIn("retiredSurface", contract["repoChangedFileFields"])
        self.assertIn("retiredSurfacePolicy", contract["repoChangedFileFields"])
        self.assertEqual(
            contract["retiredSurfaceFields"],
            ["paths", "policy", "blocker", "requiresExplicitReauthorization", "recommendedAction"],
        )
        self.assertEqual(contract["retiredSurfacePolicies"]["opencode"]["policy"], decision_packet.RETIRED_OPENCODE_POLICY)
        self.assertEqual(contract["retiredSurfacePolicies"]["opencode"]["recommendedAction"], "inspect-revert-or-get-reauthorization")
        self.assertIn("retired_opencode_work_without_explicit_reauthorization", contract["forbiddenActions"])
        self.assertIn("ownedPaths", contract["agentPlanFields"])
        self.assertIn("forbiddenPaths", contract["agentPlanFields"])
        self.assertEqual(contract["agentPlanAuthorityValues"], ["read", "write"])
        self.assertEqual(contract["agentPlanRiskValues"], ["low", "medium", "high"])
        self.assertIn("blocked-safe", contract["milestoneStates"])
        self.assertFalse(contract["safety"]["movementSent"])

    def test_cli_schema_json_outputs_static_contract_without_repo_packet(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = decision_packet.main(["--repo-root", str(REPO_ROOT), "--schema-json"])
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-decision-packet-schema-contract")
        self.assertIn("requiredTopLevelFields", payload)
        self.assertIn("commitPlanFields", payload)
        self.assertIn("agentPlanFields", payload)
        self.assertIn("agentPlanAuthorityValues", payload)
        self.assertIn("agentPlanRiskValues", payload)

    def test_cli_agent_plan_outputs_plan_and_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = decision_packet.main(["--repo-root", str(root), "--agent-plan"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertIn("agentPlan", payload)
        self.assertIn("llmReminder", payload)
        self.assertTrue(payload["agentPlan"])
        self.assertEqual(payload["agentPlan"][0]["authority"], "write")
        self.assertIn("ownedPaths", payload["agentPlan"][0])
        self.assertEqual(payload["llmReminder"]["banner"], "# **🚦 NEXT ACTION — CONTINUE SAFELY**")

    def test_malformed_current_truth_fails_closed_with_structured_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_text(root / "docs" / "recovery" / "current-truth.json", "{not-json")

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["status"], "failed")
        self.assertIn("current-truth-malformed", packet["blockers"])
        self.assertTrue(any(str(item).startswith("current-truth-malformed:") for item in packet["errors"]))
        self.assertNotEqual(packet["targetEpoch"]["status"], "current")

    def test_missing_current_truth_target_with_current_proof_blocks_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            (root / "docs" / "recovery" / "current-truth.json").unlink()

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["targetEpoch"]["status"], "in-world-unproven")
        self.assertIn("current-truth-target-missing", packet["blockers"])
        self.assertIn("current-truth-missing:docs\\recovery\\current-truth.json", packet["warnings"])
        self.assertNotEqual(packet["targetEpoch"]["status"], "current")

    def test_retired_opencode_surface_change_blocks_commit_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            retired_path = root / "tools" / "riftreader_workflow" / "opencode_bridge.py"
            write_text(retired_path, "# retired historical surface\n")

            packet = decision_packet.build_decision_packet(root)

        changed_by_path = {item["path"]: item for item in packet["repo"]["changedFiles"]}
        retired_item = changed_by_path["tools/riftreader_workflow/opencode_bridge.py"]
        labels = [item["label"] for item in packet["validationPlan"]["commands"]]

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(retired_item["retiredSurface"])
        self.assertEqual(retired_item["retiredSurfacePolicy"], decision_packet.RETIRED_OPENCODE_POLICY)
        self.assertIn("retired-opencode-surface-changed", packet["blockers"])
        self.assertIn(
            "retired-opencode-requires-explicit-reauthorization:tools/riftreader_workflow/opencode_bridge.py",
            packet["warnings"],
        )
        self.assertEqual(packet["safeNextAction"]["key"], "retired-opencode-surface-review")
        self.assertEqual(packet["retiredSurfaces"]["paths"], ["tools/riftreader_workflow/opencode_bridge.py"])
        self.assertEqual(packet["retiredSurfaces"]["policy"], decision_packet.RETIRED_OPENCODE_POLICY)
        self.assertEqual(packet["retiredSurfaces"]["blocker"], "retired-opencode-surface-changed")
        self.assertTrue(packet["retiredSurfaces"]["requiresExplicitReauthorization"])
        self.assertEqual(packet["retiredSurfaces"]["recommendedAction"], "inspect-revert-or-get-reauthorization")
        self.assertEqual(packet["commitPlan"]["reason"], "retired-opencode-surface-requires-explicit-reauthorization")
        self.assertEqual(packet["commitPlan"]["retiredSurfacePaths"], ["tools/riftreader_workflow/opencode_bridge.py"])
        self.assertNotIn("opencode-bridge-tests", labels)
        self.assertIn(
            "retired OpenCode surface work would proceed without explicit reauthorization",
            packet["llmReminder"]["mustStopIf"],
        )

    def test_dot_opencode_retired_surface_is_visible_in_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            retired_path = root / ".opencode" / "opencode.example.jsonc"
            write_text(retired_path, "{}\n")

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["retiredSurfaces"]["paths"], [".opencode/opencode.example.jsonc"])
        self.assertIn("retired-opencode-surface-changed", packet["blockers"])
        self.assertEqual(packet["safeNextAction"]["key"], "retired-opencode-surface-review")

    def test_malformed_current_proof_fails_closed_with_structured_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_text(root / "docs" / "recovery" / "current-proof-anchor-readback.json", "[]")

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["status"], "failed")
        self.assertIn("current-proof-malformed", packet["blockers"])
        self.assertTrue(any(str(item).startswith("current-proof-malformed:") for item in packet["errors"]))
        self.assertNotEqual(packet["targetEpoch"]["status"], "current")

    def test_cli_compact_json_malformed_current_truth_exits_failed_with_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_text(root / "docs" / "recovery" / "current-truth.json", "{not-json")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = decision_packet.main(["--repo-root", str(root), "--compact-json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["kind"], "riftreader-decision-packet")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["targetEpoch"]["status"], "invalid-artifact")
        self.assertIn("current-truth-malformed", payload["blockers"])

    def test_cli_compact_json_malformed_current_proof_exits_failed_with_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_text(root / "docs" / "recovery" / "current-proof-anchor-readback.json", "[]")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = decision_packet.main(["--repo-root", str(root), "--compact-json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["kind"], "riftreader-decision-packet")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["targetEpoch"]["status"], "invalid-artifact")
        self.assertIn("current-proof-malformed", payload["blockers"])

    def test_cache_reuses_packet_only_when_fingerprint_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            cached = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(cached["cacheStatus"], "reused")
        self.assertEqual(cached["performance"]["buildMode"], "cache-reused")
        self.assertTrue(cached["performance"]["cacheReused"])
        self.assertFalse(cached["performance"]["runSafeChecks"])
        self.assertIsInstance(cached["performance"]["totalDurationSeconds"], float)
        self.assertTrue(cached["cacheSafety"]["freshFingerprintChecked"])
        self.assertEqual(cached["targetEpoch"]["status"], "current")
        self.assertIn("actor-chain-candidate-only", cached["blockers"])

    def test_cache_miss_when_retired_opencode_surface_becomes_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            write_text(root / ".opencode" / "opencode.example.jsonc", "{}\n")
            rebuilt = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(rebuilt["cacheStatus"], "miss")
        self.assertEqual(rebuilt["performance"]["buildMode"], "fresh")
        self.assertFalse(rebuilt["performance"]["cacheReused"])
        self.assertEqual(rebuilt["retiredSurfaces"]["paths"], [".opencode/opencode.example.jsonc"])
        self.assertIn("retired-opencode-surface-changed", rebuilt["blockers"])

    def test_corrupted_cache_is_miss_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            write_text(output_dir / "decision-packet.json", "{corrupt-cache")
            rebuilt = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(rebuilt["cacheStatus"], "miss")
        self.assertEqual(rebuilt["performance"]["buildMode"], "fresh")
        self.assertFalse(rebuilt["performance"]["cacheReused"])
        self.assertEqual(rebuilt["targetEpoch"]["status"], "current")

    def test_corrupted_fingerprint_does_not_block_output_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            write_text(output_dir / "fingerprint.json", "{corrupt-fingerprint")
            artifacts = decision_packet.write_outputs(root, packet, output_dir)

        self.assertEqual(packet["cacheStatus"], "miss")
        self.assertEqual(
            decision_packet.normalize_path(artifacts["fingerprint"]),
            "riftreader-local/decision-packet/latest/fingerprint.json",
        )

    def test_cli_use_cache_reuses_written_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            first_stdout = io.StringIO()
            cached_stdout = io.StringIO()

            with contextlib.redirect_stdout(first_stdout):
                first_exit = decision_packet.main(["--repo-root", str(root), "--write", "--compact-json"])
            with contextlib.redirect_stdout(cached_stdout):
                cached_exit = decision_packet.main(["--repo-root", str(root), "--use-cache", "--compact-json"])
            cached_payload = json.loads(cached_stdout.getvalue())

        self.assertEqual(first_exit, 2)
        self.assertEqual(cached_exit, 2)
        self.assertEqual(cached_payload["cacheStatus"], "reused")
        self.assertEqual(cached_payload["performance"]["buildMode"], "cache-reused")
        self.assertTrue(cached_payload["performance"]["cacheReused"])
        self.assertIn("actor-chain-candidate-only", cached_payload["blockers"])

    def test_cli_explain_renders_reminder_commit_and_performance_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = decision_packet.main(["--repo-root", str(root), "--explain"])
            markdown = stdout.getvalue()

        self.assertEqual(exit_code, 2)
        self.assertIn("# **🚦 NEXT ACTION — CONTINUE SAFELY**", markdown)
        self.assertIn("## Commit planner", markdown)
        self.assertIn("# **⚠️ NOT COMMIT-READY**", markdown)
        self.assertIn("## Performance", markdown)
        self.assertIn("| Build mode | `fresh` |", markdown)
        self.assertIn("actor-chain-candidate-only", markdown)

    def test_cache_miss_after_current_truth_mtime_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"
            truth_path = root / "docs" / "recovery" / "current-truth.json"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            old_stat = truth_path.stat()
            os.utime(truth_path, (old_stat.st_atime + 10, old_stat.st_mtime + 10))
            rebuilt = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(rebuilt["cacheStatus"], "miss")
        self.assertEqual(rebuilt["performance"]["buildMode"], "fresh")
        self.assertFalse(rebuilt["performance"]["cacheReused"])
        self.assertEqual(rebuilt["targetEpoch"]["status"], "current")

    def test_cache_miss_after_same_dirty_file_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"
            changed_path = root / "agents.md"
            write_text(changed_path, "# test\nfirst dirty edit\n")

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            old_stat = changed_path.stat()
            write_text(changed_path, "# test\nsecond dirty edit with same changed path\n")
            os.utime(changed_path, (old_stat.st_atime + 10, old_stat.st_mtime + 10))
            rebuilt = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(rebuilt["cacheStatus"], "miss")
        self.assertEqual(rebuilt["performance"]["buildMode"], "fresh")
        self.assertFalse(rebuilt["performance"]["cacheReused"])
        self.assertEqual(rebuilt["fingerprint"]["changedFiles"][0]["path"], "agents.md")
        self.assertTrue(rebuilt["fingerprint"]["changedFiles"][0]["file"]["exists"])

    def test_run_safe_checks_disables_cache_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            rebuilt = decision_packet.build_decision_packet(root, run_safe_checks=True, use_cache=True, cache_dir=output_dir)

        self.assertNotEqual(rebuilt["cacheStatus"], "reused")
        self.assertTrue(rebuilt["cacheSafety"]["runSafeChecksDisablesCache"])
        self.assertTrue(rebuilt["performance"]["runSafeChecks"])
        self.assertGreater(rebuilt["performance"]["safeValidationCommandCount"], 0)

    def test_compact_packet_schema_preserves_llm_reminder_contract(self) -> None:
        packet = {
            "schemaVersion": 1,
            "kind": "riftreader-decision-packet",
            "status": "blocked",
            "lane": "actor-chain",
            "risk": "high",
            "targetEpoch": {"status": "stale", "blockers": ["target-epoch-pid-drift"]},
            "safeNextAction": {"key": "safe", "command": ["python", "safe.py"], "why": "fixture"},
            "llmReminder": decision_packet.build_llm_reminder({"command": ["python", "safe.py"]}, "blocked-safe"),
            "milestoneStatus": {"state": "blocked-safe"},
            "commitPlan": {"recommended": False},
            "agentPlan": [
                {
                    "name": "docs",
                    "authority": "write",
                    "ownedPaths": ["docs/workflow/example.md"],
                    "forbiddenPaths": ["tools/**"],
                    "risk": "low",
                    "validation": ["git --no-pager diff --check"],
                }
            ],
            "blockers": ["target-epoch-pid-drift"],
            "warnings": [],
            "navigationPointerDiscovery": {
                "status": "passed",
                "verdict": "navigation-pointer-discovery-indexed",
                "candidates": {
                    "promotedCoordinate": {"status": "promoted", "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328"},
                    "candidateFacingTarget": {
                        "status": "candidate-only",
                        "offset": "0x30C",
                        "comparisonMaxAbsYawDeltaDegrees": 62.1,
                    },
                    "candidateTurnRate": {"status": "candidate-only", "offset": "0x304"},
                    "coordinateDeltaCandidate": {
                        "status": "confirms-promoted-coordinate-offset",
                        "trackingErrorMaxAbs": 0.006,
                    },
                },
                "proofGates": {
                    "ghidraStaticEvidence": {
                        "status": "passed",
                        "generatedAtUtc": "2026-06-01T07:21:17Z",
                        "rootAddress": "1432ebc80",
                        "rootReferenceCountCaptured": 200,
                        "instructionsScanned": 8057130,
                        "analysisTimedOutProjectSaved": True,
                        "offlineOnly": True,
                    },
                },
                "candidateLedger": {
                    "velocitySpeed": {
                        "status": "forward-back-stop-live-correlation-passed",
                        "liveCorrelationPassed": True,
                        "latestPlanarSpeedPerSecond": 0.0,
                        "forwardProgressPassed": True,
                        "backwardContrastPassed": True,
                        "stopStationaryReadbackPassed": True,
                    },
                },
                "next": {"recommendedAction": "fixture"},
            },
            "retiredSurfaces": {
                "paths": ["tools/riftreader_workflow/opencode_bridge.py"],
                "policy": decision_packet.RETIRED_OPENCODE_POLICY,
                "blocker": "retired-opencode-surface-changed",
                "requiresExplicitReauthorization": True,
                "recommendedAction": "inspect-revert-or-get-reauthorization",
            },
            "cacheStatus": "miss",
            "performance": {"buildMode": "fresh", "cacheReused": False, "totalDurationSeconds": 0.01},
        }

        compact = decision_packet.compact_decision_packet(packet)

        self.assertEqual(
            set(compact),
            {
                "schemaVersion",
                "kind",
                "status",
                "lane",
                "risk",
                "targetEpoch",
                "safeNextAction",
                "llmReminder",
                "milestoneStatus",
                "commitPlan",
                "agentPlan",
                "toolCatalog",
                "staticOwnerReadback",
                "postUpdateRecovery",
                "navigationTerrain",
                "navigationPointerChains",
                "navigationPointerDiscovery",
                "retiredSurfaces",
                "blockers",
                "warnings",
                "cacheStatus",
                "performance",
            },
        )
        self.assertEqual(compact["llmReminder"]["banner"], "# **🚦 NEXT ACTION — CONTINUE SAFELY**")
        self.assertIn("status helper returned a known blocker", compact["llmReminder"]["doNotStopIf"])
        self.assertIn("debugger or CE would be required", compact["llmReminder"]["mustStopIf"])
        self.assertEqual(compact["agentPlan"][0]["name"], "docs")
        self.assertEqual(compact["retiredSurfaces"]["paths"], ["tools/riftreader_workflow/opencode_bridge.py"])
        self.assertEqual(compact["performance"]["buildMode"], "fresh")
        compact_nav = compact["navigationPointerDiscovery"]
        self.assertEqual("passed", compact_nav["ghidraStaticEvidenceStatus"])
        self.assertEqual("1432ebc80", compact_nav["ghidraStaticRootAddress"])
        self.assertEqual(200, compact_nav["ghidraStaticRootReferenceCountCaptured"])
        self.assertTrue(compact_nav["ghidraStaticOfflineOnly"])
        self.assertEqual(
            "forward-back-stop-live-correlation-passed",
            compact_nav["velocitySpeedStatus"],
        )
        self.assertTrue(compact_nav["velocitySpeedLiveCorrelationPassed"])
        self.assertEqual(0.0, compact_nav["velocitySpeedLatestPlanarSpeedPerSecond"])
        self.assertTrue(compact_nav["velocitySpeedForwardProgressPassed"])
        self.assertTrue(compact_nav["velocitySpeedBackwardContrastPassed"])
        self.assertTrue(compact_nav["velocitySpeedStopStationaryReadbackPassed"])

        markdown = decision_packet.build_markdown(packet)
        self.assertIn("Ghidra static evidence", markdown)
        self.assertIn("root refs `200`", markdown)
        self.assertIn("Velocity/speed: `forward-back-stop-live-correlation-passed`", markdown)

    def test_markdown_renders_big_reminder_banner(self) -> None:
        packet = {
            "status": "blocked",
            "lane": "actor-chain",
            "risk": "high",
            "targetEpoch": {"status": "current"},
            "cacheStatus": "miss",
            "safeNextAction": {"key": "actor", "command": ["python", "actor.py"], "why": "candidate only"},
            "llmReminder": decision_packet.build_llm_reminder({"command": ["python", "actor.py"]}, "blocked-safe"),
            "milestoneStatus": {"state": "blocked-safe"},
            "validationPlan": {"commands": []},
            "commitPlan": {"recommended": False, "reason": "no-stageable-tracked-paths", "explicitPaths": []},
            "toolCatalog": {
                "ghidraStaticLane": {
                    "status": "ready",
                    "priority": "default-offline-static-first-for-pointer-chain-discovery",
                    "capabilities": ["decompiler", "cross-references", "writer-site discovery"],
                    "recommendedTriggers": ["navigation-pointer-discovery", "restart-survival-failure"],
                    "targetOffsets": ["rift_x64+0x32EBC80", "owner+0x30C", "owner+0x438"],
                    "suggestedRunCommand": [".\\scripts\\riftreader-tool-catalog.cmd", "--ghidra-static-plan", "--json"],
                },
                "recommendedGhidraAction": {
                    "command": [".\\scripts\\riftreader-tool-catalog.cmd", "--ghidra-static-plan", "--json"],
                },
            },
            "performance": {
                "buildMode": "fresh",
                "cacheReused": False,
                "runSafeChecks": False,
                "safeValidationCommandCount": 0,
                "safeValidationDurationSeconds": 0,
                "totalDurationSeconds": 0.01,
            },
            "blockers": ["actor-chain-candidate-only"],
        }

        markdown = decision_packet.build_markdown(packet)

        self.assertIn("# **🚦 NEXT ACTION — CONTINUE SAFELY**", markdown)
        self.assertIn("## **🔄 DO NOT STOP HERE**", markdown)
        self.assertIn("# **⚠️ NOT COMMIT-READY**", markdown)
        self.assertIn("## Performance", markdown)
        self.assertIn("| Build mode | `fresh` |", markdown)
        self.assertIn("## Offline static analysis / Ghidra", markdown)
        self.assertIn("first-class reverse-engineering/decompiler platform", markdown)
        self.assertIn("owner+0x30C", markdown)

    def test_markdown_renders_retired_surface_approval_banner(self) -> None:
        packet = {
            "status": "blocked",
            "lane": "git",
            "risk": "medium",
            "targetEpoch": {"status": "current"},
            "cacheStatus": "miss",
            "safeNextAction": {
                "key": "retired-opencode-surface-review",
                "command": ["git", "--no-pager", "diff", "--", ".opencode/opencode.example.jsonc"],
                "why": "fixture",
            },
            "llmReminder": decision_packet.build_llm_reminder({"command": ["git", "status"]}, "blocked-safe"),
            "milestoneStatus": {"state": "blocked-safe"},
            "validationPlan": {"commands": []},
            "commitPlan": {
                "recommended": False,
                "reason": "retired-opencode-surface-requires-explicit-reauthorization",
                "explicitPaths": [".opencode/opencode.example.jsonc"],
            },
            "retiredSurfaces": {
                "paths": [".opencode/opencode.example.jsonc"],
                "policy": decision_packet.RETIRED_OPENCODE_POLICY,
                "blocker": "retired-opencode-surface-changed",
                "requiresExplicitReauthorization": True,
                "recommendedAction": "inspect-revert-or-get-reauthorization",
            },
            "performance": {
                "buildMode": "fresh",
                "cacheReused": False,
                "runSafeChecks": False,
                "safeValidationCommandCount": 0,
                "safeValidationDurationSeconds": 0,
                "totalDurationSeconds": 0.01,
            },
            "blockers": ["retired-opencode-surface-changed"],
        }

        markdown = decision_packet.build_markdown(packet)

        self.assertIn("# **🛑 RETIRED SURFACE — APPROVAL REQUIRED**", markdown)
        self.assertIn("`retired-opencode-requires-explicit-reauthorization`", markdown)
        self.assertIn("`.opencode/opencode.example.jsonc`", markdown)

    def test_markdown_renders_commit_ready_explicit_paths(self) -> None:
        packet = {
            "status": "passed",
            "lane": "docs",
            "risk": "low",
            "targetEpoch": {"status": "current"},
            "cacheStatus": "miss",
            "safeNextAction": {"key": "status", "command": ["git", "status"], "why": "fixture"},
            "llmReminder": decision_packet.build_llm_reminder({"command": ["git", "status"]}, "passed"),
            "milestoneStatus": {"state": "passed"},
            "validationPlan": {"commands": []},
            "commitPlan": {
                "recommended": True,
                "validationRequired": False,
                "suggestedMessage": "Update docs",
                "explicitPaths": ["docs/workflow/example.md"],
                "excludedGeneratedPaths": ["scripts/captures/run/summary.json"],
                "stageCommand": ["git", "add", "--", "docs/workflow/example.md"],
                "stageCommandPreview": "git add -- docs/workflow/example.md",
            },
            "performance": {
                "buildMode": "cache-reused",
                "cacheReused": True,
                "runSafeChecks": False,
                "safeValidationCommandCount": 0,
                "safeValidationDurationSeconds": 0,
                "totalDurationSeconds": 0.02,
            },
            "blockers": [],
        }

        markdown = decision_packet.build_markdown(packet)

        self.assertIn("# **✅ COMMIT-READY — EXPLICIT PATHS ONLY**", markdown)
        self.assertIn("`git add -- docs/workflow/example.md`", markdown)
        self.assertIn('`["git", "add", "--", "docs/workflow/example.md"]`', markdown)
        self.assertIn("`docs/workflow/example.md`", markdown)
        self.assertIn("`scripts/captures/run/summary.json`", markdown)
        self.assertIn("| Build mode | `cache-reused` |", markdown)
        self.assertIn("| Cache reused | `true` |", markdown)


if __name__ == "__main__":
    unittest.main()
