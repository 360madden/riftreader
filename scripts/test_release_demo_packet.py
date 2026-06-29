#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_contract_audit as audit  # noqa: E402
from riftreader_workflow import release_demo_packet as packet  # noqa: E402

TEMP_ROOT = REPO_ROOT / ".riftreader-local" / "unit-test-temp"


def temporary_repo_child() -> tempfile.TemporaryDirectory[str]:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=TEMP_ROOT)


def final_status(ok: bool = True) -> dict[str, object]:
    return {
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "currentHead": "abc123",
        "ciStatus": "passed" if ok else "failed",
        "artifactFreshnessStatus": "fresh" if ok else "stale",
        "proofReplayStatus": "passed" if ok else "blocked",
        "toolSurfaceStatus": "passed" if ok else "blocked",
        "upstreamStatus": "passed" if ok else "blocked",
        "blockers": [] if ok else ["ci-not-passed"],
    }


def decision_packet() -> dict[str, object]:
    return {
        "status": "blocked",
        "ok": False,
        "lane": "proof-recovery",
        "risk": "high",
        "blockers": ["latest-static-owner-readback-root-pointer-null"],
        "safeNextAction": {"command": ["scripts\\get-rift-window-targets.cmd", "-Json"]},
    }


def operator_status() -> dict[str, object]:
    return {
        "status": "passed",
        "overallState": "blocked",
        "git": {"branch": "main", "dirty": False},
        "handoff": {"pointerTarget": "docs\\handoffs\\latest.md"},
        "mcpRuntime": {"status": "blocked-query-failed", "ok": False, "localMcpUrl": "http://127.0.0.1:8770/mcp", "listenerCount": 0, "stdioCounterparts": {"count": 1}, "blockers": ["local-mcp-server-listener-query-failed"]},
        "workflowArtifacts": {
            "latest": {
                "actualClientProof": {"status": "stale", "path": "proof.json"},
                "trialReadiness": {"status": "stale", "path": "readiness.json"},
                "proposalSmoke": {"status": "stale", "path": "proposal.json"},
            }
        },
        "riftTargets": {"count": 0},
        "recommendedActions": [
            {"key": "refresh-trial-readiness", "why": "refresh trial", "command": ["trial"], "source": "workflowArtifacts"},
            {"key": "refresh-unified-operator-status", "why": "refresh status", "command": ["status"], "source": "operatorStatus"},
        ],
        "recommendedNextAction": {"key": "refresh-trial-readiness"},
    }


def recovery_plan() -> dict[str, object]:
    return {
        "status": "blocked",
        "ok": False,
        "releaseBlockerCount": 2,
        "primaryStep": {"key": "refresh-trial-readiness"},
        "steps": [
            {"priority": 30, "key": "refresh-trial-readiness", "category": "release-blocker", "releaseBlocker": True, "operatorStep": False, "commands": [{"args": ["trial"]}]},
            {"priority": 70, "key": "refresh-actual-client-proof", "category": "operator-action-needed", "releaseBlocker": True, "operatorStep": True, "commands": [{"args": ["proof"]}]},
        ],
    }


class ReleaseDemoPacketTests(unittest.TestCase):
    def test_release_packet_passes_with_final_and_contract_green(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                final_status_override=final_status(True),
                decision_packet_override=decision_packet(),
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["releaseReadiness"]["status"], "passed")
        self.assertEqual(payload["contractAudit"]["status"], "passed")
        self.assertTrue(payload["deferredLanes"]["proofRecovery"]["deferredForReleasePacket"])
        self.assertIn("proof-recovery-lane-deferred", "\n".join(payload["warnings"]))
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertEqual(payload["safeLocalRefresh"], {"enabled": False})
        self.assertEqual(payload["operatorRunbook"]["commands"]["releaseDemoPacket"], ["scripts\\riftreader-release-demo-packet.cmd", "--json", "--write", "--summary-md"])
        self.assertEqual(
            payload["operatorRunbook"]["commands"]["releaseDemoPacketRefresh"],
            ["scripts\\riftreader-release-demo-packet.cmd", "--json", "--write", "--summary-md", "--refresh-safe-local"],
        )

    def test_release_packet_blocks_when_final_gate_blocks(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                final_status_override=final_status(False),
                decision_packet_override=decision_packet(),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("final-readiness-not-passed", payload["blockers"])
        self.assertIn("final:ci-not-passed", payload["blockers"])

    def test_release_packet_writes_ignored_artifacts(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                write=True,
                summary_md=True,
                final_status_override=final_status(True),
                decision_packet_override=decision_packet(),
            )

            artifacts = payload["artifacts"]
            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            self.assertTrue(str(summary_json.relative_to(root)).startswith(".riftreader-local"))
            self.assertIn("RiftReader MCP Release/Demo Packet", summary_md.read_text(encoding="utf-8"))

    def test_no_refresh_does_not_collect_optional_components(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            with (
                mock.patch.object(packet, "build_operator_status", side_effect=AssertionError("operator status should not run")),
                mock.patch.object(packet, "build_recovery_plan", side_effect=AssertionError("recovery plan should not run")),
            ):
                payload = packet.build_release_demo_packet(
                    root,
                    final_status_override=final_status(True),
                    decision_packet_override=decision_packet(),
                )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["safeLocalRefresh"], {"enabled": False})
        self.assertFalse(payload["safety"]["refreshSafeLocal"])

    def test_refresh_safe_local_includes_operator_status_and_recovery_plan(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                refresh_safe_local=True,
                final_status_override=final_status(False),
                decision_packet_override=decision_packet(),
                operator_status_override=operator_status(),
                recovery_plan_override=recovery_plan(),
                dashboard_self_test_override={"status": "passed", "ok": True},
            )

        refresh = payload["safeLocalRefresh"]
        self.assertTrue(refresh["enabled"])
        self.assertEqual(refresh["operatorStatus"]["mcpRuntime"]["status"], "blocked-query-failed")
        self.assertEqual(refresh["operatorStatus"]["recommendedActions"][0]["key"], "refresh-trial-readiness")
        self.assertEqual(refresh["recoveryPlan"]["releaseBlockerCount"], 2)
        self.assertEqual(refresh["recoveryPlan"]["primaryStep"]["key"], "refresh-trial-readiness")
        self.assertEqual(refresh["dashboardSelfTest"]["status"], "passed")
        self.assertFalse(refresh["releaseImpact"]["topLevelOk"])
        self.assertIn("final-readiness-not-passed", refresh["releaseImpact"]["releaseBlockerKeys"])
        self.assertFalse(refresh["releaseImpact"]["deferredProofRecoveryIsReleaseBlocker"])
        self.assertTrue(payload["safety"]["refreshSafeLocal"])
        self.assertFalse(payload["safety"]["serverStarted"])

    def test_refresh_plan_blocked_does_not_reclassify_green_release_packet(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                refresh_safe_local=True,
                final_status_override=final_status(True),
                decision_packet_override=decision_packet(),
                operator_status_override=operator_status(),
                recovery_plan_override=recovery_plan(),
                dashboard_self_test_override={"status": "passed", "ok": True},
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertFalse(payload["safeLocalRefresh"]["releaseImpact"]["deferredProofRecoveryIsReleaseBlocker"])
        self.assertEqual(payload["safeLocalRefresh"]["releaseImpact"]["safeLocalReleaseBlockerCount"], 0)

    def test_refresh_helper_failure_semantics(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                refresh_safe_local=True,
                final_status_override=final_status(True),
                decision_packet_override=decision_packet(),
                operator_status_override=operator_status(),
                recovery_plan_override={"status": "failed", "ok": False, "blockers": ["boom"]},
                dashboard_self_test_override={"status": "failed", "ok": False, "blockers": ["dashboard"]},
            )

        self.assertFalse(payload["ok"])
        self.assertIn("recovery-plan-failed", payload["blockers"])
        self.assertIn("dashboard-self-test-not-passed", payload["warnings"])

    def test_refresh_markdown_summary_includes_v2_section(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = packet.build_release_demo_packet(
                root,
                write=True,
                summary_md=True,
                refresh_safe_local=True,
                final_status_override=final_status(True),
                decision_packet_override=decision_packet(),
                operator_status_override=operator_status(),
                recovery_plan_override=recovery_plan(),
                dashboard_self_test_override={"status": "passed", "ok": True},
            )

            summary_md = root / payload["artifacts"]["summaryMarkdown"]
            text = summary_md.read_text(encoding="utf-8")

        self.assertIn("Safe-local refresh v2", text)
        self.assertIn("refresh-trial-readiness", text)

    def test_parser_accepts_refresh_safe_local_flag(self) -> None:
        args = packet.build_parser().parse_args(["--refresh-safe-local"])

        self.assertTrue(args.refresh_safe_local)

    def test_self_test_passes(self) -> None:
        payload = packet.self_test()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["packetVersion"], "stage53-v2")


if __name__ == "__main__":
    unittest.main()
