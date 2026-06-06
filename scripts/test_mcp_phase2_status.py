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

from riftreader_workflow import chatgpt_trial_recorder as recorder  # noqa: E402
from riftreader_workflow import mcp_ci_status as ci  # noqa: E402
from riftreader_workflow import mcp_phase2_status as phase2  # noqa: E402
from riftreader_workflow import mcp_proof_replay as replay  # noqa: E402
from riftreader_workflow import mcp_workflow_state as state  # noqa: E402


CURRENT_HEAD = "0123456789abcdef0123456789abcdef01234567"


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "agents.md"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "baseline"],
        cwd=root,
        check=True,
    )


def valid_proof() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "connectionMode": "manual-public-ip",
        "publicMcpUrl": "https://203.0.113.10/mcp",
        "chatgptRegistrationSucceeded": True,
        "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "toolOutputSchemasPresent": True,
        "toolOutputSchemaCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "toolOutputSchemaToolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "health": {
            "repoRoot": ".",
            "repoName": "RiftReader",
            "absoluteRepoRootExposed": False,
        },
        "templateFetched": True,
        "submitPackageProposalSucceeded": True,
        "inboxId": "20260519T010000Z-abcdef",
        "listInboxSawInboxId": True,
        "createPackageDraftSucceeded": True,
        "draftId": "20260519T010100Z-abcdef",
        "reviewLatestPackageDraftSucceeded": True,
        "reviewLatestPackageDraftReadOnly": True,
        "dryRunDiffPreviewOk": True,
        "dryRunDiffPreviewArtifactUnderPackageIntake": True,
        "dryRunDiffPreviewBoundedBytes": True,
        "dryRunDiffPreviewTextLength": 195,
        "dryRunDiffPreviewTruncated": False,
        "dryRunSucceeded": True,
        "applyLatestPackageDraftWithoutApprovalBlocked": True,
        "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
        "applyLatestPackageDraftWithoutApprovalApplied": False,
        "notes": "Observed manually in ChatGPT Developer Mode.",
    }


def write_json(path: Path, payload: dict[str, object], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def write_phase1_artifacts(root: Path, mtime: int = 1_800_000_000) -> Path:
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-trial-readiness.json",
        {"kind": "readiness", "status": "passed", "ok": True},
        mtime,
    )
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010100Z-proposal-transport-smoke.json",
        {"kind": "proposal", "status": "passed", "ok": True},
        mtime + 1,
    )
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010200Z-cloudflare-tunnel-smoke.json",
        {
            "kind": "cloudflare",
            "status": "passed",
            "ok": True,
            "publicMcpUrl": "https://example.trycloudflare.com/mcp",
            "safety": {"publicTunnelStopped": True},
        },
        mtime + 2,
    )
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010300Z-chatgpt-trial-session-ready.json",
        {
            "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session-ready",
            "status": "ready",
            "ok": True,
            "publicMcpUrl": "https://trial.trycloudflare.com/mcp",
        },
        mtime + 3,
    )
    proof_record = {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-actual-client-proof",
        "generatedAtUtc": "2026-05-19T10:09:45Z",
        "status": "passed",
        "ok": True,
        "proof": valid_proof(),
        "blockers": [],
        "warnings": [],
        "safety": {
            "operatorSuppliedFactsOnly": True,
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }
    proof_path = root / state.ACTUAL_CLIENT_PROOF_ROOT / "20260519-010400Z" / "proof.json"
    write_json(proof_path, proof_record, mtime + 4)
    return proof_path


def successful_runs(head: str = CURRENT_HEAD) -> list[dict[str, object]]:
    return [
        {
            "databaseId": 1,
            "workflowName": ".NET build and test",
            "headSha": head,
            "status": "completed",
            "conclusion": "success",
            "createdAt": "2026-05-19T10:00:00Z",
            "updatedAt": "2026-05-19T10:01:00Z",
            "event": "push",
            "url": "https://example.invalid/dotnet",
        },
        {
            "databaseId": 2,
            "workflowName": "RiftReader Policy",
            "headSha": head,
            "status": "completed",
            "conclusion": "success",
            "createdAt": "2026-05-19T10:00:00Z",
            "updatedAt": "2026-05-19T10:02:00Z",
            "event": "push",
            "url": "https://example.invalid/policy",
        },
    ]


class McpPhase2StatusTests(unittest.TestCase):
    def test_current_head_ci_passes_when_required_workflows_succeeded(self) -> None:
        payload = ci.evaluate_ci_runs(current_head=CURRENT_HEAD, runs=successful_runs())

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])

    def test_current_head_ci_blocks_on_failed_workflow(self) -> None:
        runs = successful_runs()
        runs[1]["conclusion"] = "failure"

        payload = ci.evaluate_ci_runs(current_head=CURRENT_HEAD, runs=runs)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertIn("ci-workflow-not-success:RiftReader Policy:failure", payload["blockers"])

    def test_current_head_ci_unavailable_is_fail_closed_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            def unavailable(_args: list[str], _cwd: Path, _timeout: float) -> dict[str, object]:
                return {"ok": False, "exitCode": 127, "error": "FileNotFoundError:gh"}

            payload = ci.current_head_ci_status(root, gh_runner=unavailable)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertIn("ci-status-unavailable", payload["blockers"])
        self.assertTrue(any(str(warning).startswith("ci-status-unavailable") for warning in payload["warnings"]))

    def test_fresh_actual_client_proof_replays_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            proof_path = write_phase1_artifacts(root)

            payload = replay.replay_actual_client_proof(root, proof_path=proof_path, freshness_budget_seconds=999_999_999)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["proofFreshness"]["status"], "fresh")
        self.assertIn("artifactConsistency", payload)

    def test_stale_actual_client_proof_warns_without_invalidating_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            proof_path = write_phase1_artifacts(root, mtime=1)

            payload = replay.replay_actual_client_proof(root, proof_path=proof_path, freshness_budget_seconds=1)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["proofFreshness"]["status"], "stale")
        self.assertTrue(any(str(warning).startswith("actual-client-proof-age-exceeds-budget") for warning in payload["warnings"]))

    def test_phase2_status_combines_phase1_proof_ci_replay_and_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_phase1_artifacts(root)
            ci_payload = ci.evaluate_ci_runs(current_head=CURRENT_HEAD, runs=successful_runs())

            payload = phase2.phase2_status(root, ci_status_payload=ci_payload)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["phase1Proof"]["ok"])
        self.assertTrue(payload["proofReplay"]["ok"])
        self.assertTrue(payload["ciStatus"]["ok"])
        self.assertIn("artifactFreshness", payload)
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_compact_phase2_status_keeps_operator_fields_without_full_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_phase1_artifacts(root)
            ci_payload = ci.evaluate_ci_runs(current_head=CURRENT_HEAD, runs=successful_runs())

            payload = phase2.phase2_status(root, ci_status_payload=ci_payload)
            compact = phase2.compact_phase2_status(payload)

        self.assertEqual(compact["kind"], "riftreader-mcp-phase2-compact-status")
        self.assertEqual(compact["status"], "passed")
        self.assertEqual(compact["ciStatus"], "passed")
        self.assertEqual(compact["proofReplayStatus"], "passed")
        self.assertIn("recommendedNextAction", compact)
        self.assertNotIn("phase1Status", compact)

    def test_phase2_status_blocks_when_ci_for_current_head_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_phase1_artifacts(root)
            runs = successful_runs()
            runs[0]["conclusion"] = "failure"
            ci_payload = ci.evaluate_ci_runs(current_head=CURRENT_HEAD, runs=runs)

            payload = phase2.phase2_status(root, ci_status_payload=ci_payload)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any(blocker.startswith("ci:ci-workflow-not-success:.NET build and test") for blocker in payload["blockers"]))

    def test_phase2_uses_same_proof_rules_as_trial_recorder(self) -> None:
        proof = valid_proof()
        proof["toolCount"] = 7

        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:7", recorder.validate_proof(proof))


if __name__ == "__main__":
    unittest.main()
