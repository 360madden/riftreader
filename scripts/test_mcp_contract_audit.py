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

TEMP_ROOT = REPO_ROOT / ".riftreader-local" / "unit-test-temp"


def temporary_repo_child() -> tempfile.TemporaryDirectory[str]:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=TEMP_ROOT)


class McpContractAuditTests(unittest.TestCase):
    def test_contract_audit_passes_with_seeded_artifacts(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = audit.build_contract_audit(root)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["toolSurface"]["expectedToolCount"], 40)
        self.assertEqual(payload["toolSurface"]["observedProposalSmokeToolCount"], 40)
        self.assertTrue(payload["toolSurface"]["actualClientProof"]["toolOutputSchemasPresent"])
        self.assertTrue(payload["performanceWarnings"]["slowMcpStages"])
        self.assertTrue(payload["performanceWarnings"]["slowUnittestModules"])
        self.assertIn("categoryCounts", payload["artifactClassificationSummary"])
        self.assertTrue(payload["safety"]["readOnlyAudit"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])

    def test_contract_audit_blocks_missing_expected_tool(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root, missing_tool="health")  # noqa: SLF001 - shared test fixture.

            payload = audit.build_contract_audit(root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        blockers = "\n".join(payload["blockers"])
        self.assertIn("proposal-smoke-tool-count-mismatch:39", blockers)
        self.assertIn("proposal-smoke-missing-expected-tools:health", blockers)
        self.assertIn("actual-client-proof-missing-tools:health", blockers)

    def test_contract_audit_writes_ignored_artifacts(self) -> None:
        with temporary_repo_child() as temp_dir:
            root = Path(temp_dir)
            audit._seed_contract_artifacts(root)  # noqa: SLF001 - shared test fixture.

            payload = audit.build_contract_audit(root, write=True, summary_md=True)

            artifacts = payload["artifacts"]
            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            self.assertTrue(str(summary_json.relative_to(root)).startswith(".riftreader-local"))
            self.assertIn("RiftReader MCP Contract Audit", summary_md.read_text(encoding="utf-8"))

    def test_self_test_passes(self) -> None:
        payload = audit.self_test()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")


if __name__ == "__main__":
    unittest.main()
