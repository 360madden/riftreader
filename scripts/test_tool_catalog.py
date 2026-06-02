from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import tool_catalog  # noqa: E402


def write(path: Path, text: str = "# test\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_fake_repo(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    external = root / "Tools"
    repo.mkdir()
    write(repo / "agents.md")
    for rel in [
        "scripts/riftreader-decision-packet.cmd",
        "scripts/riftreader-workflow-status.cmd",
        "scripts/riftreader-tool-catalog.cmd",
        "scripts/riftreader-ghidra-static-evidence.cmd",
        "scripts/riftreader-static-field-access-matrix.cmd",
        "scripts/riftreader-phase1-target-entity-snapshot.cmd",
        "scripts/riftreader-policy-lint.cmd",
        "scripts/riftreader-validation-ledger.cmd",
        "scripts/riftreader-navigation-pointer-discovery.cmd",
        "scripts/riftreader-current-truth-refresh-plan.cmd",
        "scripts/riftreader-current-truth-refresh-apply.cmd",
        "scripts/riftreader-facing-target-three-pose-gate.cmd",
        "scripts/riftreader-facing-target-restart-survival-packet.cmd",
        "scripts/riftreader-facing-target-promotion-readiness-review.cmd",
        "scripts/riftreader-facing-target-promotion-apply.cmd",
        "scripts/riftreader-turn-rate-promotion-readiness-review.cmd",
        "scripts/riftreader-owner-0x304-semantics-review.cmd",
        "scripts/riftreader-turn-rate-promotion-apply.cmd",
        "scripts/riftreader-sensitive-artifact-scan.cmd",
        "scripts/riftreader-live-input-surface-audit.cmd",
        "scripts/riftreader-actor-chain-no-debug-status.cmd",
        "scripts/static-owner-coordinate-chain-readback.cmd",
        "scripts/riftreader-navigation-consumer-state.cmd",
        "scripts/static-owner-nav-now.cmd",
        "scripts/static-owner-turn-aware-route-plan.cmd",
        "scripts/static-owner-camera-yaw-classification.cmd",
        "scripts/static-owner-turn-forward-experiment.cmd",
        "scripts/static-owner-nav-route-step.cmd",
        "scripts/static-owner-nav-route-run.cmd",
        "scripts/static-owner-nav-report-route-run.cmd",
        "scripts/static-owner-continuous-route-sequence-contract.cmd",
        "scripts/riftreader-navigation-waypoint-readiness.cmd",
        "scripts/riftreader-navigation-schema-validate.cmd",
        "scripts/riftreader-navigation-consumer-demo.cmd",
        "scripts/riftreader-navigation-consumer-refresh.cmd",
        "scripts/riftreader-navigation-route-preview.cmd",
        "scripts/riftreader-navigation-downstream-package.cmd",
        "scripts/riftreader-navigation-live-run-request.cmd",
        "scripts/riftreader-navigation-live-run-review.cmd",
        "scripts/riftscan_milestone_review.py",
        "tools/riftreader_workflow/opencode_bridge.py",
        "tools/riftreader_workflow/ghidra_scripts/RiftReaderPointerEvidence.java",
        "tools/RiftReader.SendInput/Program.cs",
        "tools/RiftReader.WindowTools/Program.cs",
    ]:
        write(repo / rel)
    for rel in [
        "ghidra-headless.bat",
        "ghidra_12.1_PUBLIC/ghidraRun.bat",
        "x64dbg/release/x64/x64dbg.exe",
        "x64dbg/release/x64/headless.exe",
        "SysinternalsSuite/Listdlls64.exe",
        "SysinternalsSuite/handle64.exe",
        "SysinternalsSuite/procdump64.exe",
        "SysinternalsSuite/vmmap64.exe",
    ]:
        write(external / rel, "test\n")
    return repo, external


class ToolCatalogTests(unittest.TestCase):
    def test_catalog_routes_external_tools_by_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))

            catalog = tool_catalog.build_tool_catalog(repo, external)

        self.assertEqual(catalog["status"], "passed")
        self.assertIn("ghidra-headless", catalog["canonicalToolKeys"])
        self.assertIn("x64dbg-gui", catalog["gatedToolKeys"])
        self.assertIn("opencode-retired", catalog["retiredToolKeys"])
        self.assertEqual(catalog["lanes"]["ghidraStatic"]["status"], "ready")
        self.assertFalse(catalog["safety"]["inputSent"])

    def test_compact_catalog_contains_workflow_and_static_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))

            compact = tool_catalog.build_compact_catalog(tool_catalog.build_tool_catalog(repo, external))

        self.assertEqual(compact["kind"], "riftreader-tool-catalog-compact")
        self.assertEqual(compact["ghidraStaticLane"]["status"], "ready")
        self.assertEqual(compact["inputSurfacePolicyCommand"], ["scripts\\riftreader-live-input-surface-audit.cmd", "--json"])
        workflow_steps = [item["step"] for item in compact["recommendedWorkflow"]]
        self.assertTrue(any(item["step"] == "offline-static-first" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "ghidra-static-evidence-plan" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "static-field-access-matrix-quick" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "phase1-target-entity-snapshot" for item in compact["recommendedWorkflow"]))
        self.assertLess(workflow_steps.index("offline-static-first"), workflow_steps.index("workflow-status"))
        self.assertLess(workflow_steps.index("static-field-access-matrix-quick"), workflow_steps.index("actor-chain-status-separate"))
        self.assertLess(workflow_steps.index("phase1-target-entity-snapshot"), workflow_steps.index("workflow-status"))
        self.assertLess(workflow_steps.index("offline-static-first"), workflow_steps.index("navigation-pointer-discovery"))
        self.assertTrue(any(item["step"] == "actor-chain-status-separate" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "navigation-pointer-discovery" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "current-truth-refresh-plan" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "current-truth-refresh-apply-dry-run" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "facing-three-pose-gate-report" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "facing-restart-survival-report" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "facing-promotion-readiness-review" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "facing-promotion-apply-dry-run" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "turn-rate-promotion-readiness-review" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "owner-0x304-semantics-review" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "turn-rate-promotion-apply-dry-run" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "static-chain-readback-before-nav" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "navigation-consumer-state" for item in compact["recommendedWorkflow"]))
        self.assertTrue(
            any(item["step"] == "route-sequence-contract-for-consumer" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "waypoint-readiness-for-consumer" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-schema-validate-for-consumer" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-consumer-demo-for-downstream" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-consumer-refresh-for-downstream" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-route-preview-for-downstream" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-downstream-package-for-consumer" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-live-run-request-for-review" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "navigation-live-run-review-before-live" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(
            any(item["step"] == "camera-yaw-classification-before-turn-route" for item in compact["recommendedWorkflow"])
        )
        self.assertTrue(any(item["step"] == "route-run-report-before-rerun" for item in compact["recommendedWorkflow"]))
        self.assertIn("actor-chain-no-debug-status", compact["canonicalToolKeys"])
        self.assertIn("validation-ledger", compact["canonicalToolKeys"])
        self.assertIn("ghidra-static-evidence", compact["canonicalToolKeys"])
        self.assertIn("static-field-access-matrix", compact["canonicalToolKeys"])
        self.assertIn("phase1-target-entity-snapshot", compact["canonicalToolKeys"])
        self.assertIn("navigation-pointer-discovery", compact["canonicalToolKeys"])
        self.assertIn("current-truth-refresh-plan", compact["canonicalToolKeys"])
        self.assertIn("current-truth-refresh-apply", compact["canonicalToolKeys"])
        self.assertIn("current-truth-refresh-apply", compact["gatedToolKeys"])
        self.assertIn("facing-target-three-pose-gate", compact["canonicalToolKeys"])
        self.assertIn("facing-target-restart-survival-packet", compact["canonicalToolKeys"])
        self.assertIn("facing-target-promotion-readiness-review", compact["canonicalToolKeys"])
        self.assertIn("facing-target-promotion-apply", compact["canonicalToolKeys"])
        self.assertIn("facing-target-promotion-apply", compact["gatedToolKeys"])
        self.assertIn("turn-rate-promotion-readiness-review", compact["canonicalToolKeys"])
        self.assertIn("owner-0x304-semantics-review", compact["canonicalToolKeys"])
        self.assertIn("turn-rate-promotion-apply", compact["canonicalToolKeys"])
        self.assertIn("turn-rate-promotion-apply", compact["gatedToolKeys"])
        self.assertIn("static-owner-coordinate-chain-readback", compact["canonicalToolKeys"])
        self.assertIn("navigation-consumer-state", compact["canonicalToolKeys"])
        self.assertIn("static-owner-camera-yaw-classification", compact["canonicalToolKeys"])
        self.assertIn("static-owner-route-run-report", compact["canonicalToolKeys"])
        self.assertIn("static-owner-route-sequence-contract", compact["canonicalToolKeys"])
        self.assertIn("navigation-waypoint-readiness", compact["canonicalToolKeys"])
        self.assertIn("navigation-schema-validate", compact["canonicalToolKeys"])
        self.assertIn("navigation-consumer-demo", compact["canonicalToolKeys"])
        self.assertIn("navigation-consumer-refresh", compact["canonicalToolKeys"])
        self.assertIn("navigation-route-preview", compact["canonicalToolKeys"])
        self.assertIn("navigation-downstream-package", compact["canonicalToolKeys"])
        self.assertIn("navigation-live-run-request", compact["canonicalToolKeys"])
        self.assertIn("navigation-live-run-review", compact["canonicalToolKeys"])
        self.assertIn("restart-survival-failure", compact["ghidraStaticLane"]["recommendedTriggers"])
        self.assertIn("owner+0x30C", compact["ghidraStaticLane"]["targetOffsets"])
        self.assertIn("owner+0x438", compact["ghidraStaticLane"]["targetOffsets"])
        self.assertIn("suggestedRunCommand", compact["ghidraStaticLane"])
        self.assertIn("decompiler", compact["ghidraStaticLane"]["capabilities"])

    def test_missing_external_tools_warns_without_authorizing_debugger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, _external = make_fake_repo(Path(temp_dir))
            missing = Path(temp_dir) / "missing-tools"

            catalog = tool_catalog.build_tool_catalog(repo, missing)

        self.assertEqual(catalog["status"], "passed-with-warnings")
        self.assertIn("external-tools-root-missing", catalog["warnings"])
        self.assertIn("x64dbg-gui", catalog["gatedToolKeys"])
        self.assertFalse(catalog["safety"]["x64dbgAttach"])

    def test_ghidra_plan_never_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))

            plan = tool_catalog.build_ghidra_static_lane(repo, external)

        self.assertEqual(plan["status"], "ready")
        self.assertFalse(plan["doesRun"])
        self.assertFalse(plan["safety"]["x64dbgAttach"])
        self.assertIn("scripts\\riftreader-ghidra-static-evidence.cmd", plan["commandTemplate"])
        self.assertIn("--run", plan["suggestedRunCommand"])
        self.assertIn("-import", plan["headlessCommandTemplate"])
        self.assertIn("default-offline-static-first-for-pointer-chain-discovery", plan["priority"])
        self.assertIn("navigation-pointer-discovery", plan["recommendedTriggers"])
        self.assertIn("rift_x64+0x32EBC80", plan["targetOffsets"])
        self.assertIn("writer-site discovery", plan["capabilities"])
        self.assertTrue(any("not a simple reader" in note for note in plan["whyUseMoreOften"]))
        self.assertTrue(plan["defaultBinaryCandidates"])

    def test_cli_self_test_and_compact_json(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = tool_catalog.main(["--self-test"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])

        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = tool_catalog.main(
                    ["--repo-root", str(repo), "--external-tools-root", str(external), "--compact-json"]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-tool-catalog-compact")


if __name__ == "__main__":
    unittest.main()
