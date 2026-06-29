#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import chatgpt_trial_recorder as recorder  # noqa: E402
from riftreader_workflow import mcp_final_readiness as final  # noqa: E402
from riftreader_workflow import riftreader_chatgpt_mcp as chatgpt_mcp  # noqa: E402


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


def state_with_proof_input_template() -> dict[str, object]:
    payload = base_state()
    payload["latestArtifacts"] = {
        "proof-input-template": {
            "status": "ready",
            "ok": True,
            "artifactAgeSeconds": 120,
            "connectionMode": "cloudflare-named-tunnel",
            "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "toolOutputSchemaCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolOutputSchemaToolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "artifactPaths": {
                "proofInputJson": ".riftreader-local\\riftreader-chatgpt-mcp\\proof-input-templates\\20260519-010350Z\\proof-input.json"
            },
        }
    }
    return payload


def state_with_stale_shape_proof_input_template() -> dict[str, object]:
    payload = state_with_proof_input_template()
    template = payload["latestArtifacts"]["proof-input-template"]  # type: ignore[index]
    template["connectionMode"] = "openai-secure-mcp-tunnel"  # type: ignore[index]
    template["toolCount"] = recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT - 1  # type: ignore[index]
    return payload


def state_with_classified_artifact_warning() -> dict[str, object]:
    payload = base_state()
    payload["warnings"] = ["artifact-age-exceeds-budget:actual-client-proof:90000s>86400s:.riftreader-local\\proof.json"]
    payload["artifactClassifications"] = {
        "summary": {
            "categoryCounts": {
                "release-blocker": 1,
                "operator-action-needed": 0,
                "historical-warning": 0,
                "expected-expired": 2,
                "ignored-local-evidence": 1,
                "obsolete-superseded": 3,
            },
            "releaseBlockerKeys": ["artifact-age-exceeds-budget:actual-client-proof"],
            "operatorActionKeys": ["artifact-age-exceeds-budget:actual-client-proof"],
            "expectedExpiredKeys": ["ephemeral-public-url-expected-expired:trial-session"],
            "obsoleteSupersededCount": 3,
            "historicalWarningCount": 0,
            "ignoredLocalEvidenceCount": 1,
        },
        "operatorWarnings": payload["warnings"],
    }
    return payload


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
                "tunnel-client": {
                    "status": "retired",
                    "ok": True,
                    "required": False,
                    "path": None,
                    "binaryDiagnostics": None,
                },
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


def write_tool_surface_fixture(
    root: Path,
    *,
    tool_names: list[str] | None = None,
    repo_root_value: str = ".",
    health_safety_overrides: dict[str, object] | None = None,
    root_safety_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    artifact = root / ".riftreader-local" / "proposal.json"
    health_safety = {key: True for key in final.TRUE_HEALTH_SAFETY_KEYS}
    health_safety.update(final.safety_flags())
    health_safety["absoluteRepoRootExposed"] = False
    if health_safety_overrides:
        health_safety.update(health_safety_overrides)
    root_safety = final.safety_flags()
    if root_safety_overrides:
        root_safety.update(root_safety_overrides)
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "client": {
                    "toolNames": tool_names or list(final.APPROVED_TOOL_NAMES),
                    "healthStructuredContent": {
                        "repoRoot": repo_root_value,
                        "safety": health_safety,
                    },
                },
                "safety": root_safety,
            }
        ),
        encoding="utf-8",
    )
    return {"latestArtifacts": {"proposal-smoke": {"path": os.path.relpath(artifact, root)}}}


class McpFinalReadinessTests(unittest.TestCase):
    def test_approved_tool_surface_tracks_mcp_adapter_order(self) -> None:
        self.assertEqual(final.APPROVED_TOOL_NAMES, chatgpt_mcp.EXPECTED_TOOL_ORDER)
        self.assertIn("apply_latest_package_draft", final.APPROVED_TOOL_NAMES)

    def test_all_pass_fixture_passes(self) -> None:
        payload = final_status()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_passed_gate_without_release_handoff_recommends_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = final.final_readiness(
                Path(temp_dir),
                phase2_payload=base_phase2(),
                state_payload=base_state(),
                **ok_gate_overrides(),
            )

        self.assertEqual(payload["status"], "passed")
        self.assertIsNone(payload["artifacts"]["releaseHandoffPath"])  # type: ignore[index]
        self.assertEqual(payload["recommendedNextAction"]["key"], "ready-for-release-handoff")  # type: ignore[index]

    def test_passed_gate_with_release_handoff_recommends_maintenance_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            handoff = root / "docs" / "handoffs" / "20260519-1645-mcp-final-readiness-release-handoff.md"
            current_handoff = root / "docs" / "handoffs" / "20260617-mcp-stage21-apply-stage27-commit-proof.md"
            handoff.parent.mkdir(parents=True)
            handoff.write_text("# release handoff\n", encoding="utf-8")
            current_handoff.write_text("# current MCP handoff\n", encoding="utf-8")
            os.utime(handoff, (1000, 1000))
            os.utime(current_handoff, (2000, 2000))

            payload = final.final_readiness(
                root,
                phase2_payload=base_phase2(),
                state_payload=base_state(),
                **ok_gate_overrides(),
            )
            compact = final.compact_final_readiness(payload)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["artifacts"]["releaseHandoffPath"], "docs\\handoffs\\20260519-1645-mcp-final-readiness-release-handoff.md")  # type: ignore[index]
        self.assertEqual(payload["artifacts"]["latestMcpHandoffPath"], "docs\\handoffs\\20260617-mcp-stage21-apply-stage27-commit-proof.md")  # type: ignore[index]
        self.assertEqual(payload["recommendedNextAction"]["key"], "maintenance-loop")  # type: ignore[index]
        self.assertEqual(compact["releaseHandoffPath"], "docs\\handoffs\\20260519-1645-mcp-final-readiness-release-handoff.md")
        self.assertEqual(compact["latestMcpHandoffPath"], "docs\\handoffs\\20260617-mcp-stage21-apply-stage27-commit-proof.md")

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
        self.assertEqual(payload["recommendedNextAction"]["key"], "record-actual-client-proof")

    def test_proof_action_beats_generic_phase2_and_ci_blockers(self) -> None:
        phase2 = base_phase2()
        phase2["status"] = "blocked"
        phase2["ok"] = False
        phase2["ciStatus"] = {
            "status": "blocked",
            "ok": False,
            "currentHead": "012345",
            "blockers": ["ci-workflow-missing-current-head:.NET build and test"],
        }
        phase2["proofReplay"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["required-field-missing:connectionMode"],
            "proofFreshness": {"status": "stale"},
        }

        payload = final_status(phase2=phase2)

        self.assertIn("phase2:not-ready", payload["blockers"])
        self.assertIn("ci:missing:.NET build and test", payload["blockers"])
        self.assertIn("proof:replay-failed:required-field-missing:connectionMode", payload["blockers"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "record-actual-client-proof")

    def test_proof_action_uses_latest_fresh_template_when_present(self) -> None:
        phase2 = base_phase2()
        phase2["proofReplay"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["required-field-missing:connectionMode"],
            "proofFreshness": {"status": "stale"},
        }

        payload = final_status(phase2=phase2, state=state_with_proof_input_template())

        self.assertEqual(payload["recommendedNextAction"]["key"], "check-actual-client-proof-input")
        self.assertEqual(
            payload["recommendedNextAction"]["command"],
            [
                "scripts\\riftreader-chatgpt-trial-recorder.cmd",
                "--check-input",
                "--input",
                ".riftreader-local\\riftreader-chatgpt-mcp\\proof-input-templates\\20260519-010350Z\\proof-input.json",
                "--json",
            ],
        )

    def test_proof_action_ignores_stale_shape_latest_template(self) -> None:
        phase2 = base_phase2()
        phase2["proofReplay"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["required-field-missing:connectionMode"],
            "proofFreshness": {"status": "stale"},
        }

        payload = final_status(phase2=phase2, state=state_with_stale_shape_proof_input_template())

        self.assertEqual(payload["recommendedNextAction"]["key"], "record-actual-client-proof")
        self.assertEqual(
            payload["recommendedNextAction"]["command"],
            ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--write-template", "--json"],
        )

    def test_upstream_sync_blocker_has_non_mutating_recommendation(self) -> None:
        overrides = ok_gate_overrides()
        overrides["git_sync_payload"] = {
            "status": "blocked",
            "ok": False,
            "blockers": ["git:upstream-not-synced:behind=0:ahead=1"],
            "warnings": [],
            "ahead": 1,
            "behind": 0,
        }

        payload = final.final_readiness(
            Path.cwd(),
            phase2_payload=base_phase2(),
            state_payload=base_state(),
            **overrides,
        )

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["recommendedNextAction"]["key"], "request-push-approval")
        self.assertEqual(payload["recommendedNextAction"]["command"], ["git", "--no-pager", "status", "--short", "--branch"])

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

    def test_tunnel_client_binary_diagnostics_records_hash_and_version_probe(self) -> None:
        diagnostics = final._tunnel_client_binary_diagnostics(sys.executable, REPO_ROOT)  # noqa: SLF001

        self.assertEqual(diagnostics["status"], "passed")
        self.assertTrue(diagnostics["ok"])
        self.assertEqual(len(diagnostics["sha256"]), 64)
        self.assertTrue(diagnostics["versionProbe"]["ok"])

    def test_dependency_preflight_marks_tunnel_client_retired_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                mock.patch.object(final, "_find_executable", side_effect=lambda name, extra_candidates=None: sys.executable),
                mock.patch.object(
                    final,
                    "_tunnel_client_binary_diagnostics",
                    return_value={
                        "status": "blocked",
                        "ok": False,
                        "blockers": ["tunnel-client-version-probe-failed"],
                        "warnings": [],
                    },
                ),
            ):
                payload = final.dependency_preflight(root)

        self.assertEqual(payload["dependencies"]["tunnel-client"]["status"], "retired")
        self.assertFalse(payload["dependencies"]["tunnel-client"]["required"])
        self.assertNotIn("dependency:tunnel-client-version-probe-failed", payload["blockers"])

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

    def test_public_session_status_ages_out_stale_ephemeral_ready_url(self) -> None:
        payload = final.public_session_status(
            {
                "latestArtifacts": {
                    "trial-session": {
                        "status": "ready",
                        "publicMcpUrl": "https://old.trycloudflare.com/mcp",
                        "publicUrlEphemeral": True,
                        "artifactAgeSeconds": final.EPHEMERAL_PUBLIC_READY_MAX_AGE_SECONDS + 1,
                    }
                }
            }
        )

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["states"]["trial-session"], "expected-expired")

    def test_public_session_status_blocks_fresh_unexpected_public_ready_url(self) -> None:
        payload = final.public_session_status(
            {
                "latestArtifacts": {
                    "trial-session": {
                        "status": "ready",
                        "publicMcpUrl": "https://fresh.trycloudflare.com/mcp",
                        "publicUrlEphemeral": True,
                        "artifactAgeSeconds": 1,
                    }
                }
            }
        )

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("public-session:unexpected-active:trial-session", payload["blockers"])

    def test_tool_surface_parser_blocks_unapproved_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = write_tool_surface_fixture(root, tool_names=[*final.APPROVED_TOOL_NAMES, "unsafe_extra_tool"])

            payload = final.tool_surface_status(root, state)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("safety:unexpected-tool-surface", payload["blockers"])

    def test_tool_surface_parser_blocks_absolute_repo_root_exposure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = write_tool_surface_fixture(
                root,
                repo_root_value="C:\\RIFT MODDING\\RiftReader",
                health_safety_overrides={"absoluteRepoRootExposed": True},
            )

            payload = final.tool_surface_status(root, state)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("safety:absolute-repo-root-exposed", payload["blockers"])

    def test_tool_surface_parser_blocks_missing_health_boundary_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = write_tool_surface_fixture(root, health_safety_overrides={"noShellExecutionEndpoint": False})

            payload = final.tool_surface_status(root, state)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("safety:unsafe-tool-boundary:noShellExecutionEndpoint", payload["blockers"])

    def test_tool_surface_parser_blocks_unknown_root_safety_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = write_tool_surface_fixture(root, root_safety_overrides={"applyFlagSent": None})

            payload = final.tool_surface_status(root, state)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("safety:unsafe-action-unknown:applyFlagSent", payload["blockers"])

    def test_tool_surface_parser_blocks_unsafe_root_actions(self) -> None:
        unsafe_flags = {
            "gitMutation": True,
            "providerWrites": True,
            "inputSent": True,
            "x64dbgAttach": True,
            "savedVariablesUsedAsLiveTruth": True,
            "noCheatEngine": False,
        }
        for key, value in unsafe_flags.items():
            with self.subTest(key=key):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    state = write_tool_surface_fixture(root, root_safety_overrides={key: value})

                    payload = final.tool_surface_status(root, state)

                self.assertEqual(payload["status"], "blocked")
                self.assertIn(f"safety:unsafe-action:{key}", payload["blockers"])

    def test_compact_status_keeps_operator_fields(self) -> None:
        payload = final_status()
        compact = final.compact_final_readiness(payload)

        self.assertEqual(compact["kind"], "riftreader-mcp-final-compact-status")
        self.assertEqual(compact["status"], "passed")
        self.assertEqual(compact["phase2Status"], "passed")
        self.assertEqual(compact["dependencyStatus"], "passed")
        self.assertNotIn("tunnel-client", compact["requiredDependencies"])
        self.assertEqual(compact["secureTunnelClient"]["status"], "retired")
        self.assertIsNone(compact["secureTunnelClient"]["binaryDiagnosticsStatus"])
        self.assertEqual(compact["environmentStatus"], "passed")
        self.assertIn("recommendedNextAction", compact)

    def test_compact_status_includes_artifact_classification_summary(self) -> None:
        payload = final_status(state=state_with_classified_artifact_warning())
        compact = final.compact_final_readiness(payload)

        summary = compact["artifactClassificationSummary"]
        self.assertEqual(summary["categoryCounts"]["release-blocker"], 1)
        self.assertEqual(summary["obsoleteSupersededCount"], 3)
        self.assertEqual(compact["warnings"], ["artifact-age-exceeds-budget:actual-client-proof:90000s>86400s:.riftreader-local\\proof.json"])

    def test_self_test_passes(self) -> None:
        payload = final.self_test()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
