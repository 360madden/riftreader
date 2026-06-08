#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_workflow_state as state  # noqa: E402
from riftreader_workflow import chatgpt_trial_recorder as recorder  # noqa: E402
from riftreader_workflow import workflow_router  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, object], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def write_passed_readiness(root: Path) -> None:
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-trial-readiness.json",
        {"kind": "readiness", "status": "passed", "ok": True, "blockers": []},
        1_800_000_000,
    )


def write_passed_proposal(root: Path) -> None:
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010100Z-proposal-transport-smoke.json",
        {"kind": "proposal", "status": "passed", "ok": True, "blockers": []},
        1_800_000_010,
    )


def write_passed_cloudflare(root: Path) -> None:
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010200Z-cloudflare-tunnel-smoke.json",
        {
            "kind": "cloudflare",
            "status": "passed",
            "ok": True,
            "blockers": [],
            "publicMcpUrl": "https://example.trycloudflare.com/mcp",
            "safety": {"serverStopped": True, "publicTunnelStopped": True},
        },
        1_800_000_020,
    )


def write_manual_public_ip_plan(root: Path) -> None:
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010200Z-manual-public-ip-plan.json",
        {
            "kind": "riftreader-chatgpt-mcp-manual-public-ip-plan",
            "status": "ready",
            "ok": True,
            "blockers": [],
            "activePath": {"key": "manual-public-ip", "publicMcpUrl": "https://203.0.113.10/mcp"},
        },
        1_800_000_020,
    )


def write_actual_proof(root: Path) -> None:
    write_json(
        root / state.ACTUAL_CLIENT_PROOF_ROOT / "20260519-010300Z" / "proof.json",
        {
            "kind": "riftreader-chatgpt-actual-client-proof",
            "status": "passed",
            "ok": True,
            "proof": {"toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT, "publicMcpUrl": "https://client.example/mcp"},
            "blockers": [],
        },
        1_800_000_030,
    )


class WorkflowRouterTests(unittest.TestCase):
    def test_recommends_readiness_when_no_readiness_pass_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = workflow_router.route_mcp(root)

        self.assertEqual(payload["recommendedNextAction"]["key"], "mcp-trial-readiness")
        self.assertTrue(payload["safety"]["readOnlyRouting"])

    def test_recommends_commit_plan_for_dirty_validated_slice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_passed_readiness(root)
            write_passed_proposal(root)
            tools_file = root / "tools" / "riftreader_workflow" / "mcp_workflow_state.py"
            tools_file.parent.mkdir(parents=True)
            tools_file.write_text("# dirty\n", encoding="utf-8")

            payload = workflow_router.route_mcp(root)

        self.assertEqual(payload["recommendedNextAction"]["key"], "safe-commit-plan")
        self.assertIn("riftreader-safe-commit-packager.cmd", payload["recommendedNextAction"]["command"][0])

    def test_recommends_cloudflare_named_tunnel_plan_after_local_readiness_and_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_passed_readiness(root)
            write_passed_proposal(root)

            payload = workflow_router.route_mcp(root)

        self.assertEqual(payload["recommendedNextAction"]["key"], "cloudflare-named-tunnel-plan")

    def test_recommends_cloudflare_named_tunnel_proof_when_plan_exists_but_actual_client_proof_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_passed_readiness(root)
            write_passed_proposal(root)
            write_manual_public_ip_plan(root)

            payload = workflow_router.route_mcp(root)

        self.assertEqual(payload["recommendedNextAction"]["key"], "chatgpt-cloudflare-named-tunnel-proof")

    def test_recommends_draft_export_and_dry_run_based_on_inbox_and_draft_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_passed_readiness(root)
            write_passed_proposal(root)
            write_manual_public_ip_plan(root)
            write_actual_proof(root)
            write_json(
                root / state.INBOX_ROOT / "20260519T010400Z-inbox" / "metadata.json",
                {"kind": "riftreader-local-inbox-metadata", "inboxId": "20260519T010400Z-inbox"},
                1_800_000_040,
            )

            inbox_payload = workflow_router.route_mcp(root)

            write_json(
                root / state.DRAFT_ROOT / "20260519T010500Z-draft" / "summary.json",
                {"kind": "draft", "status": "created", "ok": True, "inboxId": "20260519T010400Z-inbox"},
                1_800_000_050,
            )
            draft_payload = workflow_router.route_mcp(root)

        self.assertEqual(inbox_payload["recommendedNextAction"]["key"], "inbox-to-draft")
        self.assertEqual(draft_payload["recommendedNextAction"]["key"], "draft-dry-run")

    def test_recommends_final_status_after_actual_client_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_passed_readiness(root)
            write_passed_proposal(root)
            write_manual_public_ip_plan(root)
            write_actual_proof(root)

            payload = workflow_router.route_mcp(root)

        self.assertEqual(payload["recommendedNextAction"]["key"], "mcp-final-status")
        self.assertIn("riftreader-mcp-final.cmd", payload["recommendedNextAction"]["command"][0])
        action_keys = [action["key"] for action in payload["rankedActions"]]
        self.assertIn("mcp-phase2-status", action_keys)


if __name__ == "__main__":
    unittest.main()
