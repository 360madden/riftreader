from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "player-actor-yaw-candidate-ledger.md"
README_PATH = REPO_ROOT / "docs" / "recovery" / "README.md"


class ActorYawCandidateLedgerDocsTests(unittest.TestCase):
    def test_ledger_doc_contains_required_contract_terms(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")

        required_terms = [
            "CandidateKey",
            "sourceAddress|normalized basisForwardOffset",
            "stable_but_nonresponsive",
            "idle_drift",
            "inter_preflight_idle_drift",
            "RawScore",
            "LedgerPenalty",
            "LedgerRejectionReason",
            "FacingPromotionAttempted=false",
            "test-actor-facing-proof-suite.ps1",
            "SavedVariables are not live IPC",
        ]
        missing = [term for term in required_terms if term not in text]
        self.assertEqual([], missing)

    def test_recovery_readme_links_ledger_contract(self) -> None:
        text = README_PATH.read_text(encoding="utf-8")

        self.assertIn("docs\\player-actor-yaw-candidate-ledger.md", text)
        self.assertIn("ledger penalties", text)
        self.assertIn("cannot promote actor-facing truth", text)


if __name__ == "__main__":
    unittest.main()
