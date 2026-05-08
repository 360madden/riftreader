from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.actor_yaw_current_truth_status import (
    build_current_truth_status,
    markdown_for_status,
)
from test_current_actor_yaw_disambiguation import valid_lead, valid_packet, write_json


class ActorYawCurrentTruthStatusTests(unittest.TestCase):
    def build_status(self, packet: dict, lead: dict) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            packet_file = root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json"
            lead_file = root / "scripts" / "actor-facing-behavior-backed-lead.json"
            write_json(packet_file, packet)
            write_json(lead_file, lead)
            return build_current_truth_status(packet_file=packet_file, lead_file=lead_file, repo_root=root)

    def test_valid_status_reports_current_lead_and_blocks_movement(self) -> None:
        status = self.build_status(valid_packet(), valid_lead())

        self.assertEqual(status["status"], "current")
        self.assertEqual(status["decision"], "use-promoted-actor-yaw-lead")
        self.assertEqual(status["currentActorYawLead"]["sourceAddress"], "0xABCDEF00")
        self.assertEqual(status["currentActorYawLead"]["basisForwardOffset"], "0xD4")
        self.assertFalse(status["safety"]["movementAllowed"])
        self.assertEqual(status["validation"]["status"], "pass")

    def test_status_blocks_when_validator_fails(self) -> None:
        lead = valid_lead()
        lead["SourceAddress"] = "0xDEADBEEF"

        status = self.build_status(valid_packet(), lead)

        self.assertEqual(status["status"], "blocked")
        self.assertEqual(status["decision"], "repair-current-actor-yaw-truth")
        self.assertIn("lead_file_mismatch", status["validation"]["issues"])
        self.assertFalse(status["safety"]["movementAllowed"])

    def test_markdown_includes_operator_truth(self) -> None:
        status = self.build_status(valid_packet(), valid_lead())
        markdown = markdown_for_status(status)

        self.assertIn("Actor-Yaw Current Truth Status", markdown)
        self.assertIn("`0xABCDEF00 @ 0xD4`", markdown)
        self.assertIn("Movement allowed | `false`", markdown)
        self.assertIn("No Cheat Engine | `true`", markdown)

    def test_current_repo_status_passes(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        status = build_current_truth_status(
            packet_file=repo_root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json",
            lead_file=repo_root / "scripts" / "actor-facing-behavior-backed-lead.json",
            repo_root=repo_root,
        )

        self.assertEqual(status["status"], "current", json.dumps(status["validation"], indent=2))
        self.assertEqual(status["currentActorYawLead"]["sourceAddress"], "0x202CA5D23E0")
        self.assertFalse(status["safety"]["movementAllowed"])


if __name__ == "__main__":
    unittest.main()
