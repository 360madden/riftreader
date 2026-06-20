#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
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

    def test_self_test_passes(self) -> None:
        payload = packet.self_test()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")


if __name__ == "__main__":
    unittest.main()
