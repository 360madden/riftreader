from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RetiredSurfacePolicyDocsTests(unittest.TestCase):
    def assert_doc_contains(self, relative_path: str, required_text: list[str]) -> None:
        path = REPO_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        for expected in required_text:
            with self.subTest(path=relative_path, expected=expected):
                self.assertIn(expected, text)

    def test_opencode_retirement_boundary_is_durable_in_primary_agent_docs(self) -> None:
        required = [
            "OpenCode retirement boundary",
            "retired/demoted",
            "re-authorizes OpenCode",
        ]

        self.assert_doc_contains("agents.md", required)

    def test_opencode_retirement_boundary_is_durable_in_control_plane_docs(self) -> None:
        self.assert_doc_contains(
            "docs/workflow/local-decision-control-plane-plan.md",
            [
                "OpenCode retirement boundary",
                "retired/demoted for RiftReader",
                "retired-opencode-surface-changed",
            ],
        )

    def test_opencode_retirement_boundary_is_durable_in_routing_docs(self) -> None:
        self.assert_doc_contains(
            "docs/workflow/codex-agent-routing-policy.md",
            [
                "OpenCode retirement boundary",
                "retired/demoted for RiftReader",
                "Do not route work through",
            ],
        )


if __name__ == "__main__":
    unittest.main()
