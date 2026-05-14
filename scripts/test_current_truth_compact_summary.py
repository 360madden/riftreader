from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.current_truth_compact_summary import build_summary, main, render_html, render_markdown


class CurrentTruthCompactSummaryTests(unittest.TestCase):
    def _root(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def _truth(self, root: Path) -> Path:
        return self._write_json(
            root / "docs" / "recovery" / "current-truth.json",
            {
                "schemaVersion": 1,
                "kind": "riftreader-current-truth",
                "updatedAtUtc": "2026-05-14T00:00:00Z",
                "status": "read_only_api_memory_match_displacement_gate_blocked_movement_blocked",
                "target": {
                    "processName": "rift_x64",
                    "processId": 123,
                    "targetWindowHandle": "0xABC",
                    "processStartUtc": "2026-05-14T00:00:00Z",
                },
                "movementGate": {
                    "allowed": False,
                    "status": "blocked",
                    "reason": "displaced gate blocked",
                },
                "bestCurrentCandidate": {
                    "candidateId": "api-family-hit-000001",
                    "addressHex": "0x1234",
                    "status": "same_pose_api_memory_match_candidate_displacement_gate_blocked",
                    "candidateFile": "scripts/captures/candidates.json",
                    "readbackSummary": "scripts/captures/readback.json",
                },
                "currentBlockers": ["movement-blocked"],
                "canonicalArtifacts": {},
                "visualEvidenceRouting": {},
                "nextRecommendedAction": "Capture a real displaced pose.",
            },
        )

    def _route(self, root: Path) -> Path:
        return self._write_json(
            root / "scripts" / "captures" / "route" / "coordinate-proof-route.json",
            {
                "status": "api-memory-match",
                "path": "scripts/captures/route/coordinate-proof-route.json",
                "target": {
                    "processName": "rift_x64",
                    "processId": 123,
                    "targetWindowHandle": "0xABC",
                    "processStartUtc": "2026-05-14T00:00:00Z",
                },
                "decision": {"readOnlyProofAllowed": True, "movementAllowed": False},
                "artifacts": {"summaryHtml": "scripts/captures/route/coordinate-proof-route.html"},
                "candidateRouting": {
                    "candidateComparisons": [
                        {
                            "path": "scripts/captures/comparison/summary.json",
                            "status": "blocked",
                            "rawBothReferenceMatchCount": 2,
                            "bothReferenceMatchCount": 0,
                            "blockers": ["displaced-api-reference-planar-distance-too-small:0.01<1.0"],
                        }
                    ]
                },
                "displacedReadiness": {
                    "status": "blocked",
                    "items": [{"path": "readiness.json", "status": "blocked", "planarDistance": 0.01}],
                },
                "promotionReadiness": {
                    "status": "blocked-promotion-readiness",
                    "proofAnchorPromotionAllowed": False,
                    "blockers": ["promotion-two-reference-candidate-match-missing"],
                },
            },
        )

    def test_summary_renders_raw_vs_valid_counts_and_blocked_movement(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            truth = self._truth(root)
            route = self._route(root)

            summary = build_summary(repo_root=root, truth_json=truth, route_summary=route)
            markdown = render_markdown(summary)
            html = render_html(summary)

            self.assertEqual(summary["candidateComparison"]["rawBothReferenceMatchCount"], 2)
            self.assertEqual(summary["candidateComparison"]["validBothReferenceMatchCount"], 0)
            self.assertIn("Movement allowed | `false`", markdown)
            self.assertIn("Raw both-reference matches", html)
            self.assertIn("Valid both-reference matches", html)
            self.assertIn("displaced-api-reference-planar-distance-too-small:0.01&lt;1.0", html)

    def test_cli_writes_timestamped_files_and_updates_current_truth(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            truth = self._truth(root)
            route = self._route(root)
            output_dir = root / "docs" / "recovery"
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--truth-json",
                        str(truth),
                        "--route-summary",
                        str(route),
                        "--output-dir",
                        str(output_dir),
                        "--update-current-truth",
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            updated_truth = json.loads(truth.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertTrue((root / payload["artifacts"]["summaryHtml"]).exists())
            self.assertTrue((root / payload["artifacts"]["summaryMarkdown"]).exists())
            self.assertTrue((root / payload["artifacts"]["summaryJson"]).exists())
            self.assertEqual(
                updated_truth["canonicalArtifacts"]["latestCompactTruthHtml"],
                payload["artifacts"]["summaryHtml"],
            )


if __name__ == "__main__":
    unittest.main()
