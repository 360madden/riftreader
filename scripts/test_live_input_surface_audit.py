from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import live_input_surface_audit as audit


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LiveInputSurfaceAuditTests(unittest.TestCase):
    def test_known_guarded_and_release_surfaces_are_classified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_text(root / "scripts" / "current_pid_family_snapshot_sequence.py", "--auto-displacement-key --allow-window-message-auto-displacement\n")
            write_text(root / "scripts" / "rift_live_test" / "emergency_key_release.py", "MOUSEEVENTF_LEFTUP\n")

            surfaces = audit.audit_files(root, audit.iter_source_files(root))
            by_path = {item["path"]: item for item in surfaces}

        self.assertEqual(by_path["scripts/current_pid_family_snapshot_sequence.py"]["classification"], "guarded-live-movement")
        self.assertEqual(by_path["scripts/rift_live_test/emergency_key_release.py"]["classification"], "release-only")
        self.assertFalse(by_path["scripts/rift_live_test/emergency_key_release.py"]["reviewRequired"])

    def test_unknown_legacy_input_reference_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_text(root / "scripts" / "legacy-wrapper.py", "run(['powershell', 'post-rift-key.ps1', '-UseWindowMessage'])\n")

            surfaces = audit.audit_files(root, audit.iter_source_files(root))

        self.assertEqual(len(surfaces), 1)
        self.assertEqual(surfaces[0]["classification"], "input-workflow-reference")
        self.assertTrue(surfaces[0]["reviewRequired"])
        self.assertIn("post-rift-key", surfaces[0]["tokens"])

    def test_test_files_are_not_runtime_review_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_text(root / "scripts" / "test_legacy_wrapper.py", "self.assertIn('send-rift-key.ps1', command)\n")

            surfaces = audit.audit_files(root, audit.iter_source_files(root))

        self.assertEqual(surfaces[0]["classification"], "test-reference-only")
        self.assertFalse(surfaces[0]["reviewRequired"])

    def test_tool_catalog_policy_references_are_not_runtime_review_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_text(
                root / "tools" / "riftreader_workflow" / "tool_catalog.py",
                '"tools/RiftReader.SendInput/Program.cs" "PostMessage helpers"\n',
            )

            surfaces = audit.audit_files(root, audit.iter_source_files(root))

        self.assertEqual(surfaces[0]["classification"], "policy-reference")
        self.assertFalse(surfaces[0]["reviewRequired"])

    def test_debugger_stimulus_surface_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_text(root / "scripts" / "some_x64dbg_probe.py", "--allow-game-input --stimulus-key\n")

            surfaces = audit.audit_files(root, audit.iter_source_files(root))

        self.assertEqual(surfaces[0]["classification"], "debugger-or-stimulus-surface")
        self.assertEqual(surfaces[0]["risk"], "critical")
        self.assertTrue(surfaces[0]["reviewRequired"])

    def test_run_writes_summary_and_reads_current_truth_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_text(root / "scripts" / "post-rift-key.ps1", "SendInput\n")
            write_text(
                root / "docs" / "recovery" / "current-truth.json",
                json.dumps(
                    {
                        "movementGate": {
                            "allowed": False,
                            "status": "blocked-live-input-spin-incident",
                            "liveInputIncident": {"automationMovementPaused": True},
                        },
                        "target": {
                            "clientGeometry": {
                                "requiredClientWidth": 640,
                                "requiredClientHeight": 360,
                            }
                        },
                    }
                ),
            )
            code, summary = audit.build_summary(
                argparse.Namespace(
                    repo_root=root,
                    current_truth_json=Path("docs/recovery/current-truth.json"),
                    current_proof_json=Path("docs/recovery/current-proof-anchor-readback.json"),
                    output_root=root / "out",
                    scan_root=None,
                    max_evidence_per_file=12,
                    self_test=False,
                    json=True,
                )
            )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "passed-with-review-required")
            self.assertEqual(summary["currentTruthGates"]["movementGate"]["status"], "blocked-live-input-spin-incident")
            self.assertTrue(summary["currentTruthGates"]["movementGate"]["automationMovementPaused"])
            self.assertTrue(Path(summary["artifacts"]["summaryJson"]).is_file())
            self.assertFalse(summary["safety"]["inputSent"])

    def test_stale_proof_freshness_overrides_raw_allowed_movement_gate(self) -> None:
        current_truth = {
            "movementGate": {
                "allowed": True,
                "status": "allowed-current-target-proofonly-passed-route-smoke-passed",
                "reason": "historically allowed",
            }
        }
        current_proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-27T07:00:00Z",
            "latestValidation": {
                "status": "valid",
                "movementAllowed": True,
                "movementSent": False,
                "generatedAtUtc": "2026-05-27T07:00:00Z",
            },
        }

        summary = audit.summarize_current_truth_gate(
            current_truth,
            current_proof,
            now=datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc),
        )

        gate = summary["movementGate"]
        self.assertFalse(gate["allowed"])
        self.assertEqual(gate["status"], "blocked-proof-anchor-age-out-of-range")
        self.assertTrue(gate["automationMovementPaused"])
        self.assertEqual(gate["proofFreshness"]["ageSeconds"], 120)
        self.assertEqual(gate["proofFreshnessBlocker"], "proof-anchor-stale-for-movement:ageSeconds=120;maxAgeSeconds=60")

    def test_self_test_passes(self) -> None:
        result = audit.self_test()

        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
