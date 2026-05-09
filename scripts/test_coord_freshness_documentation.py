from __future__ import annotations

import unittest
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


class CoordinateFreshnessDocumentationTests(unittest.TestCase):
    def test_core_workflows_require_api_now_vs_memory_now(self) -> None:
        required_docs = [
            "AGENTS.md",
            "agents.md",
            ".codex/skills/rift-window-control/SKILL.md",
            "docs/assistant-operating-policy.md",
            "docs/recovery/README.md",
            "docs/recovery/current-truth.md",
            "docs/live-testing-python-orchestrator-plan.md",
            "docs/candidate-trajectory-promotion-gate.md",
        ]

        for rel_path in required_docs:
            with self.subTest(path=rel_path):
                text = (repo_root() / rel_path).read_text(encoding="utf-8")
                self.assertIn("API-now vs memory-now", text)

    def test_pid_hwnd_is_documented_as_preflight_not_freshness_proof(self) -> None:
        docs = [
            "AGENTS.md",
            "agents.md",
            "docs/assistant-operating-policy.md",
            "docs/recovery/README.md",
            "docs/recovery/current-truth.md",
            "docs/live-testing-python-orchestrator-plan.md",
        ]

        for rel_path in docs:
            with self.subTest(path=rel_path):
                text = (repo_root() / rel_path).read_text(encoding="utf-8")
                self.assertIn("PID/HWND", text)
                self.assertRegex(text, r"targeting preflight|preflight only")

    def test_snapshot_coordinate_is_not_presented_as_current_now(self) -> None:
        current_truth = (repo_root() / "docs/recovery/current-truth.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Latest recorded coordinate snapshot", current_truth)
        self.assertIn("do not present this value as current-now", current_truth)

    def test_freshness_evidence_requirements_are_documented(self) -> None:
        policy = (repo_root() / "docs/assistant-operating-policy.md").read_text(
            encoding="utf-8"
        )

        for required in [
            "API coordinate/timestamp/source",
            "memory coordinate/timestamp/address/candidate",
            "per-axis deltas",
            "tolerance",
            "verdict",
        ]:
            with self.subTest(required=required):
                self.assertIn(required, policy)


if __name__ == "__main__":
    unittest.main()
