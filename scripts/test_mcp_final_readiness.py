#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_final_readiness as final  # noqa: E402


def base_phase2() -> dict[str, object]:
    return {
        "status": "passed",
        "ok": True,
        "ciStatus": {"status": "passed", "ok": True, "currentHead": "012345", "blockers": []},
        "proofReplay": {"status": "passed", "ok": True, "blockers": [], "proofFreshness": {"status": "fresh"}},
        "artifactFreshness": {
            "status": "fresh",
            "items": {
                "readiness": {"status": "fresh"},
                "proposal-smoke": {"status": "fresh"},
            },
        },
        "warnings": [],
        "safety": final.safety_flags(),
    }


def base_state(*, dirty: bool = False) -> dict[str, object]:
    return {
        "warnings": [],
        "latestArtifacts": {},
        "gitDirtyState": {
            "dirty": dirty,
            "dirtyCount": 1 if dirty else 0,
            "entries": [{"status": "??", "path": "tools/riftreader_workflow/x.py"}] if dirty else [],
        },
    }


def ok_gate_overrides() -> dict[str, dict[str, object]]:
    return {
        "git_sync_payload": {"status": "passed", "ok": True, "blockers": [], "warnings": [], "ahead": 0, "behind": 0},
        "dependency_payload": {
            "status": "passed",
            "ok": True,
            "blockers": [],
            "warnings": [],
            "dependencies": {
                "python": {"status": "passed", "required": True},
                "mcp-sdk": {"status": "passed", "required": True},
                "gh": {"status": "passed", "required": True},
            },
        },
        "environment_payload": {
            "status": "passed",
            "ok": True,
            "blockers": [],
            "warnings": [],
            "loopback": {
                "ephemeralPort": {"status": "available", "ok": True},
                "defaultServePort": {"status": "available", "ok": True},
            },
        },
        "tool_surface_payload": {"status": "passed", "ok": True, "blockers": [], "warnings": []},
        "public_session_payload": {"status": "passed", "ok": True, "blockers": [], "warnings": [], "states": {}},
    }


def final_status(*, phase2: dict[str, object] | None = None, state: dict[str, object] | None = None) -> dict[str, object]:
    return final.final_readiness(
        Path.cwd(),
        phase2_payload=phase2 or base_phase2(),
        state_payload=state or base_state(),
        **ok_gate_overrides(),
    )


class McpFinalReadinessTests(unittest.TestCase):
    def test_all_pass_fixture_passes(self) -> None:
        payload = final_status()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_dirty_tree_blocks_final_readiness(self) -> None:
        payload = final_status(state=base_state(dirty=True))

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("git:dirty-worktree", payload["blockers"])

    def test_stale_proof_blocks_final_readiness(self) -> None:
        phase2 = base_phase2()
        phase2["proofReplay"]["proofFreshness"]["status"] = "stale"  # type: ignore[index]

        payload = final_status(phase2=phase2)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("proof:stale", payload["blockers"])

    def test_stale_readiness_and_proposal_smoke_block_final_readiness(self) -> None:
        phase2 = base_phase2()
        items = phase2["artifactFreshness"]["items"]  # type: ignore[index]
        items["readiness"]["status"] = "stale"  # type: ignore[index]
        items["proposal-smoke"]["status"] = "stale"  # type: ignore[index]

        payload = final_status(phase2=phase2)

        self.assertIn("artifact:trial-readiness-stale", payload["blockers"])
        self.assertIn("artifact:proposal-smoke-stale", payload["blockers"])

    def test_pending_ci_maps_to_final_ci_blocker(self) -> None:
        phase2 = base_phase2()
        phase2["ciStatus"] = {
            "status": "blocked",
            "ok": False,
            "currentHead": "012345",
            "blockers": ["ci-workflow-not-completed:.NET build and test:in_progress"],
        }

        payload = final_status(phase2=phase2)

        self.assertIn("ci:not-completed:.NET build and test:in_progress", payload["blockers"])

    def test_failed_ci_maps_to_final_ci_blocker(self) -> None:
        phase2 = base_phase2()
        phase2["ciStatus"] = {
            "status": "blocked",
            "ok": False,
            "currentHead": "012345",
            "blockers": ["ci-workflow-not-success:RiftReader Policy:failure"],
        }

        payload = final_status(phase2=phase2)

        self.assertIn("ci:failed:RiftReader Policy:failure", payload["blockers"])

    def test_missing_required_dependency_blocks_final_readiness(self) -> None:
        overrides = ok_gate_overrides()
        overrides["dependency_payload"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["dependency:missing:mcp-sdk"],
            "warnings": [],
            "dependencies": {"mcp-sdk": {"status": "blocked", "required": True}},
        }

        payload = final.final_readiness(
            Path.cwd(),
            phase2_payload=base_phase2(),
            state_payload=base_state(),
            **overrides,
        )

        self.assertIn("dependency:missing:mcp-sdk", payload["blockers"])

    def test_unsafe_tool_surface_blocks_final_readiness(self) -> None:
        overrides = ok_gate_overrides()
        overrides["tool_surface_payload"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["safety:unexpected-tool-surface"],
            "warnings": [],
        }

        payload = final.final_readiness(
            Path.cwd(),
            phase2_payload=base_phase2(),
            state_payload=base_state(),
            **overrides,
        )

        self.assertIn("safety:unexpected-tool-surface", payload["blockers"])

    def test_environment_blocker_blocks_final_readiness(self) -> None:
        overrides = ok_gate_overrides()
        overrides["environment_payload"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["environment:artifact-root-not-ignored:.riftreader-local"],
            "warnings": [],
        }

        payload = final.final_readiness(
            Path.cwd(),
            phase2_payload=base_phase2(),
            state_payload=base_state(),
            **overrides,
        )

        self.assertIn("environment:artifact-root-not-ignored:.riftreader-local", payload["blockers"])

    def test_tool_surface_parser_blocks_unapproved_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / ".riftreader-local" / "proposal.json"
            health_safety = {key: True for key in final.TRUE_HEALTH_SAFETY_KEYS}
            health_safety["absoluteRepoRootExposed"] = False
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                json.dumps(
                    {
                        "client": {
                            "toolNames": [*final.APPROVED_TOOL_NAMES, "unsafe_extra_tool"],
                            "healthStructuredContent": {
                                "repoRoot": ".",
                                "safety": health_safety,
                            },
                        },
                        "safety": final.safety_flags(),
                    }
                ),
                encoding="utf-8",
            )
            state = {"latestArtifacts": {"proposal-smoke": {"path": os.path.relpath(artifact, root)}}}

            payload = final.tool_surface_status(root, state)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("safety:unexpected-tool-surface", payload["blockers"])

    def test_compact_status_keeps_operator_fields(self) -> None:
        payload = final_status()
        compact = final.compact_final_readiness(payload)

        self.assertEqual(compact["kind"], "riftreader-mcp-final-compact-status")
        self.assertEqual(compact["status"], "passed")
        self.assertEqual(compact["phase2Status"], "passed")
        self.assertEqual(compact["dependencyStatus"], "passed")
        self.assertEqual(compact["environmentStatus"], "passed")
        self.assertIn("recommendedNextAction", compact)

    def test_self_test_passes(self) -> None:
        payload = final.self_test()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
