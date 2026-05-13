from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_access_event_template import main


class X64DbgAccessEventTemplateTests(unittest.TestCase):
    def write_planner_summary(
        self,
        path: Path,
        *,
        status: str = "planned",
        candidate_address: str | None = "0x17382765E40",
        candidate_id: str = "api-family-hit-000001",
        candidate_artifact_path: str | None = None,
        readiness: str = "ready-for-current-turn-approval",
        generated_at: str = "2026-05-13T03:00:00Z",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "status": status,
                    "generatedAtUtc": generated_at,
                    "process": {
                        "name": "rift_x64",
                        "pid": 79184,
                        "hwnd": "0xA90BFC",
                        "startTimeUtc": "2026-05-13T00:43:12.080812Z",
                        "moduleBaseAddressHex": "0x7FF796B50000",
                    },
                    "candidate": {
                        "candidateId": candidate_id,
                        "address": candidate_address,
                        "axisOrder": "xyz",
                        "watchSizeBytes": 12,
                        "poseCountRequired": 3,
                        "artifactPath": candidate_artifact_path,
                    },
                    "truthSurface": {
                        "kind": "api-now",
                        "source": "chromalink-riftreader-world-state",
                        "sampledAtUtc": "2026-05-13T03:00:00Z",
                        "x": 7376.41,
                        "y": 863.58,
                        "z": 2989.52,
                    },
                    "readiness": {
                        "status": readiness,
                    },
                    "artifacts": {
                        "summaryJson": str(path),
                    },
                }
            ),
            encoding="utf-8",
        )

    def run_main(self, args: list[str]) -> int:
        with redirect_stdout(StringIO()):
            return main(args)

    def test_template_from_planner_summary_prefills_target_and_candidate_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            planner = temp_path / "coord-chain-plan-summary.json"
            out = temp_path / "template"
            self.write_planner_summary(planner)

            code = self.run_main(["--planner-summary", str(planner), "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            template = json.loads((out / "x64dbg-manual-access-events-template.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["eventCount"], 3)
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["x64dbgCommandsExecuted"])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertEqual(template["kind"], "x64dbg-manual-access-events")
            self.assertEqual(template["status"], "template-needs-fill")
            self.assertEqual(template["process"]["pid"], 79184)
            self.assertEqual(template["process"]["hwnd"], "0xA90BFC")
            self.assertEqual(template["watchWindow"]["baseAddress"], "0x17382765E40")
            self.assertEqual(template["events"][0]["memoryNow"]["address"], "0x17382765E40")
            self.assertIsNone(template["events"][0]["truthSurface"]["x"])
            self.assertIsNone(template["events"][0]["instruction"]["address"])

    def test_template_embeds_coordinate_family_ranking_context_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            ranking = temp_path / "coordinate-family-rankings.json"
            ranking.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "mode": "riftreader-coordinate-family-pose-ranking",
                        "status": "ranked",
                        "generatedAtUtc": "2026-05-13T03:47:22Z",
                        "candidateFileCount": 4,
                        "acceptedCandidateFileCount": 3,
                        "observationCount": 18,
                        "observationPoseCount": 2,
                        "topFamily": {"familyBaseHex": "0x17381270000"},
                        "addressRankings": [
                            {
                                "addressHex": "0x1738127A5A4",
                                "familyBaseHex": "0x17381270000",
                                "offsetHex": "0xA5A4",
                                "supportPoseCount": 2,
                                "avgBestMaxAbsDistance": 0.05882,
                                "maxBestMaxAbsDistance": 0.05882,
                                "promotionBlockers": [
                                    "restart-validation-missing",
                                    "runtime-readback-proof-missing",
                                ],
                            }
                        ],
                        "poseGroups": [
                            {
                                "poseKey": "pose-000001",
                                "reference": {"x": 7376.67, "y": 863.58, "z": 2988.98},
                                "sourceFiles": ["a.json"],
                                "observationCount": 6,
                            },
                            {
                                "poseKey": "pose-000002",
                                "reference": {"x": 7376.41, "y": 863.58, "z": 2989.52},
                                "sourceFiles": ["b.json", "b-repeat.json"],
                                "observationCount": 12,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            planner = temp_path / "coord-chain-plan-summary.json"
            out = temp_path / "template"
            self.write_planner_summary(
                planner,
                candidate_id="ranked-address-000001",
                candidate_address="0x1738127A5A4",
                candidate_artifact_path=str(ranking),
            )

            code = self.run_main(["--planner-summary", str(planner), "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            template = json.loads((out / "x64dbg-manual-access-events-template.json").read_text(encoding="utf-8"))
            evidence = template["candidateEvidence"]
            self.assertEqual(summary["candidateEvidence"]["kind"], "coordinate-family-ranking")
            self.assertEqual(evidence["kind"], "coordinate-family-ranking")
            self.assertEqual(evidence["selectedAddress"]["addressHex"], "0x1738127A5A4")
            self.assertEqual(evidence["selectedAddress"]["supportPoseCount"], 2)
            self.assertEqual(evidence["poseGroupCount"], 2)
            self.assertFalse(evidence["promotionEligible"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])

    def test_latest_planner_summary_uses_newest_planned_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            old_planner = (
                temp_path
                / "scripts"
                / "captures"
                / "x64dbg-coord-chain-plan-old"
                / "coord-chain-plan-summary.json"
            )
            latest_planner = (
                temp_path
                / "scripts"
                / "captures"
                / "x64dbg-coord-chain-plan-new"
                / "coord-chain-plan-summary.json"
            )
            blocked_planner = (
                temp_path
                / "scripts"
                / "captures"
                / "x64dbg-coord-chain-plan-blocked"
                / "coord-chain-plan-summary.json"
            )
            self.write_planner_summary(old_planner, candidate_address="0x1111", generated_at="2026-05-13T03:00:00Z")
            self.write_planner_summary(latest_planner, candidate_address="0x2222", generated_at="2026-05-13T03:01:00Z")
            self.write_planner_summary(
                blocked_planner,
                status="blocked",
                candidate_address="0x3333",
                generated_at="2026-05-13T03:02:00Z",
            )
            out = temp_path / "template"

            code = self.run_main(
                [
                    "--repo-root",
                    str(temp_path),
                    "--planner-summary",
                    "latest",
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            template = json.loads((out / "x64dbg-manual-access-events-template.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["plannerSummary"]["requestedSummary"], "latest")
            self.assertEqual(summary["plannerSummary"]["resolvedFromAlias"], "latest")
            self.assertEqual(summary["plannerSummary"]["summaryPath"], str(latest_planner))
            self.assertEqual(template["watchWindow"]["baseAddress"], "0x2222")

    def test_missing_candidate_address_blocks_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            planner = temp_path / "coord-chain-plan-summary.json"
            out = temp_path / "template"
            self.write_planner_summary(planner, candidate_address=None)

            code = self.run_main(["--planner-summary", str(planner), "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("planner-missing-candidate-address", summary["blockers"])
            self.assertIsNone(summary["artifacts"]["templateJson"])


if __name__ == "__main__":
    unittest.main()
