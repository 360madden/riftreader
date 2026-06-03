from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_JSON = REPO_ROOT / "docs" / "recovery" / "current-truth.json"
TRUTH_MD = REPO_ROOT / "docs" / "recovery" / "current-truth.md"


class CurrentTruthConsistencyTests(unittest.TestCase):
    def load_truth(self) -> dict:
        with TRUTH_JSON.open(encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        self.assertIsInstance(payload, dict)
        return payload

    def load_markdown(self) -> str:
        return TRUTH_MD.read_text(encoding="utf-8")

    def markdown_is_post_update_recovery_blocker(self, markdown: str) -> bool:
        return (
            "POST-UPDATE RECOVERY IN PROGRESS" in markdown
            and "previous promoted current resolver" in markdown
            and "current-truth apply" in markdown
        )

    def test_json_current_target_identity_is_not_historical_pid(self) -> None:
        truth = self.load_truth()
        target = truth["target"]
        live = truth["liveReferenceSurface"]
        candidate = truth["bestCurrentCandidate"]
        static_primary = truth["staticChainStatus"]["primaryCandidate"]
        latest_readback = truth["staticChainStatus"]["latestCurrentStaticReadback"]

        current_pid = int(target["processId"])
        current_hwnd = str(target["targetWindowHandle"]).upper()
        current_start = str(target["processStartUtc"])

        self.assertGreater(current_pid, 0)
        self.assertRegex(current_hwnd, r"^0X[0-9A-F]+$")
        self.assertTrue(current_start)
        self.assertNotIn("current_pid_34176", str(truth.get("status", "")))
        self.assertNotIn("PID 34176 / HWND 0x3D1544", str(live.get("view", "")))

        current_scoped_payload = {
            "target": {
                "processId": target.get("processId"),
                "targetWindowHandle": target.get("targetWindowHandle"),
                "processStartUtc": target.get("processStartUtc"),
                "moduleBase": target.get("moduleBase"),
                "status": target.get("status"),
            },
            "liveReferenceSurface": {
                "status": live.get("status"),
                "view": live.get("view"),
                "apiNowStatus": live.get("apiNowStatus"),
                "currentCoordinateFromStaticChainCandidate": live.get(
                    "currentCoordinateFromStaticChainCandidate"
                ),
                "latestCurrentStaticReadback": live.get("latestCurrentStaticReadback"),
                "latestCurrentNavStateReadback": live.get("latestCurrentNavStateReadback"),
            },
            "bestCurrentCandidate": {
                "rootAddress": candidate.get("rootAddress"),
                "currentOwnerAddress": candidate.get("currentOwnerAddress"),
                "currentCoordinateAddress": candidate.get("currentCoordinateAddress"),
                "coordinate": candidate.get("coordinate"),
                "status": candidate.get("status"),
            },
            "staticChainPrimaryCandidate": {
                "rootAddress": static_primary.get("rootAddress"),
                "ownerAddress": static_primary.get("ownerAddress"),
                "coordinateAddress": static_primary.get("coordinateAddress"),
                "coordinate": static_primary.get("coordinate"),
            },
            "latestCurrentStaticReadback": latest_readback,
        }
        current_scoped_text = json.dumps(current_scoped_payload, sort_keys=True)
        self.assertNotIn("34176", current_scoped_text)
        self.assertNotIn("0x3D1544", current_scoped_text)

    def test_current_api_now_is_fresh_for_current_pid(self) -> None:
        truth = self.load_truth()
        current_pid = int(truth["target"]["processId"])
        live = truth["liveReferenceSurface"]

        self.assertEqual(live["apiNowStatus"], f"passed-current-pid-{current_pid}-api-now-vs-chain-now")
        self.assertEqual(live["apiNowBlockers"], [])
        latest_api = live["latestApiCoordinate"]
        self.assertEqual(
            latest_api["status"],
            f"passed-current-pid-{current_pid}-api-now-vs-chain-now",
        )
        self.assertIsNotNone(latest_api["coordinate"])
        self.assertIsNotNone(latest_api["capturedAtUtc"])
        self.assertIn(f"currentpid-{current_pid}", latest_api["referenceFile"])

    def test_markdown_current_target_matches_json_target(self) -> None:
        truth = self.load_truth()
        markdown = self.load_markdown()

        if self.markdown_is_post_update_recovery_blocker(markdown):
            self.assertIn("Historical promoted truth remains archived below", markdown)
            self.assertIn("Candidate-only recovery evidence", markdown)
            self.assertIn("Do **not** use the 2026-06-01 promoted resolver", markdown)
            self.assertIn("This is **not** a promotion", markdown)
            self.assertIn("current-truth apply", markdown)
            return

        target = truth["target"]
        pid = str(target["processId"])
        hwnd = str(target["targetWindowHandle"])
        process_start = str(target["processStartUtc"])
        module_base = str(target["moduleBase"])

        self.assertIn(f"| PID | `{pid}` |", markdown)
        self.assertIn(f"| HWND | `{hwnd}` |", markdown)
        self.assertIn(f"| Process start UTC | `{process_start}` |", markdown)
        self.assertIn(f"| Module base | `{module_base}` |", markdown)
        self.assertIn(f"Latest RRAPICOORD API coordinate for PID {pid}", markdown)
        self.assertIn(f"current PID `{pid}` API-now", markdown)

        current_target_section = re.search(
            r"## Current target\n(?P<section>.*?)(?:\n## Promotion gate summary)",
            markdown,
            flags=re.S,
        )
        self.assertIsNotNone(current_target_section)
        section_text = current_target_section.group("section") if current_target_section else ""
        self.assertNotIn("34176", section_text)
        self.assertNotIn("0x3D1544", section_text)

    def test_historical_pid_is_labeled_historical_when_present(self) -> None:
        markdown = self.load_markdown()
        for line in markdown.splitlines():
            if "34176" not in line:
                continue
            if "scripts\\captures\\" in line or "rift-api-reference-currentpid-34176" in line:
                continue
            self.assertRegex(line.lower(), r"historical|promotion-validation|pid `34176` epoch")


if __name__ == "__main__":
    unittest.main()
