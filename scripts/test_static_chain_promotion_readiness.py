from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rift_live_test.static_chain_promotion_readiness import build_markdown, build_summary_from_documents


NOW = datetime(2026, 5, 27, 20, 0, 0, tzinfo=UTC)


def base_truth(*, promotion_allowed: bool = False, latest_refresh_status: str | None = None) -> dict:
    latest_refresh = {}
    if latest_refresh_status:
        latest_refresh = {
            "status": latest_refresh_status,
            "rrapicoordBlockers": ["rrapicoord-no-usable-marker"] if latest_refresh_status == "blocked" else [],
            "chromalinkBlockers": ["world-state-player-position-stale"] if latest_refresh_status == "blocked" else [],
            "doesNotPromote": True,
        }
    return {
        "target": {
            "processName": "rift_x64",
            "processId": 34176,
            "targetWindowHandle": "0x3D1544",
            "processStartUtc": "2026-05-27T18:06:53Z",
            "moduleBase": "0x7FF77AF40000",
            "live": True,
            "inWorld": True,
        },
        "staticChainStatus": {
            "status": "promotion-review-ready-not-promoted",
            "promotionAllowed": promotion_allowed,
            "primaryCandidate": {
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "rootModule": "rift_x64.exe",
                "rootRva": "0x32EBC80",
                "rootAddress": "0x7FF77E22BC80",
                "ownerAddress": "0x278C3830010",
                "coordinateAddress": "0x278C3830330",
                "restartRelogSurvived": True,
            },
            "latestApiNowValidation": {"status": "passed"},
            "latestFreshApiSourceRefreshAttempt": latest_refresh,
        },
    }


def promotion_review(*, captured_at: datetime | None = None) -> dict:
    captured = captured_at or (NOW - timedelta(seconds=10))
    captured_text = captured.isoformat().replace("+00:00", "Z")
    return {
        "status": "ready-for-explicit-promotion-approval-not-promoted",
        "verdict": "promotion-evidence-ready-but-not-applied",
        "candidate": {
            "expression": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            "rootRva": "0x32EBC80",
        },
        "target": {
            "processName": "rift_x64",
            "processId": 34176,
            "targetWindowHandle": "0x3D1544",
            "processStartUtc": "2026-05-27T18:06:53Z",
            "moduleBase": "0x7FF77AF40000",
        },
        "finalFreshSample": {
            "apiNow": {
                "status": "captured",
                "capturedAtUtc": captured_text,
                "coordinate": {"x": 7259.9497, "y": 821.44, "z": 2990.3799},
                "movementSent": False,
                "savedVariablesUse": "none",
                "noCheatEngine": True,
            },
            "chainNow": {
                "status": "passed",
                "capturedAtUtc": captured_text,
                "coordinate": {"x": 7259.94970703125, "y": 821.4375610351562, "z": 2990.375732421875},
                "movementSent": False,
                "noCheatEngine": True,
            },
            "comparison": {
                "maxAbsDelta": 0.004167578124906868,
                "tolerance": 0.25,
                "withinTolerance": True,
            },
        },
        "promotionPlan": {"approved": False, "applied": False},
    }


def chain_readback(*, generated_at: datetime | None = None) -> dict:
    generated = generated_at or (NOW - timedelta(seconds=5))
    return {
        "path": "static-owner-coordinate-chain-readback-fixture/summary.json",
        "status": "passed",
        "verdict": "static-module-root-owner-plus-0x320-coordinate-chain-resolved",
        "generatedAtUtc": generated.isoformat().replace("+00:00", "Z"),
        "ageSeconds": (NOW - generated).total_seconds(),
        "currentReadbackPassed": True,
        "candidate": {"rootRva": "0x32EBC80", "rootAddress": "0x7FF77E22BC80"},
        "reads": {
            "ownerAddress": "0x278C3830010",
            "coordinate": {"x": 7259.98, "y": 821.43, "z": 2990.99},
        },
        "blockers": [],
        "warnings": ["api-now-vs-chain-now-not-refreshed-in-this-helper"],
    }


class StaticChainPromotionReadinessTests(unittest.TestCase):
    def reference_recovery_none(self) -> dict:
        return {"status": "unknown", "pendingSettingsRepairApproval": False, "doesNotPromote": True}

    def reference_recovery_pending_repair(self) -> dict:
        return {
            "status": "blocked",
            "rrapicoordScanDiagnostics": {
                "status": "blocked",
                "verdict": "blocked-rrapicoord-no-usable-marker",
                "counts": {
                    "scanFileCount": 1,
                    "rrapicoordTextHitCount": 13,
                    "sourceTextHitCount": 10,
                    "markerLikeCount": 5,
                    "usableMarkerCount": 0,
                },
                "blockers": ["rrapicoord-no-usable-marker"],
                "inferredCauses": ["only-starting/default-marker-observed"],
            },
            "addonStateDiagnostics": {
                "status": "blocked",
                "verdict": "blocked-live-reference-runtime-marker-not-observed",
                "blockers": ["current-scan-has-no-usable-rrapicoord-live-marker"],
            },
            "addonSettingsRepairDryRun": {
                "status": "passed",
                "verdict": "addon-settings-repair-dry-run",
                "counts": {"repairCount": 1, "changedCount": 1, "appliedCount": 0, "enabledAfterCount": 1},
                "pendingRepairs": [
                    {
                        "path": r"C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.2@gmail.com\AddonSettings.lua",
                        "statusBefore": "missing",
                        "action": "inserted:missing->enabled",
                        "changed": True,
                        "applied": False,
                        "enabledAfter": True,
                    }
                ],
            },
            "pendingSettingsRepairApproval": True,
            "runtimeRefreshRequiredAfterRepair": True,
            "doesNotPromote": True,
            "recommendedAction": "Approval required: apply the selected AddonSettings repair, refresh the live addon runtime, then rerun RRAPICOORD capture.",
        }

    def test_ready_fresh_review_still_requires_explicit_approval(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(),
            promotion_review=promotion_review(),
            proof={"target": {"processId": 12148, "targetWindowHandle": "0x640C0C"}, "status": "current-target-proofonly-passed"},
            reference_recovery=self.reference_recovery_none(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["verdict"], "ready-for-explicit-promotion-approval")
        self.assertIn("explicit-promotion-approval-required", summary["blockers"])
        self.assertFalse(summary["promotionGates"]["staleProofPointerUsed"])
        self.assertIn("stale-proof-pointer-ignored", summary["warnings"])

    def test_promoted_fresh_review_passes_without_using_stale_proof_pointer(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(promotion_allowed=True),
            promotion_review=promotion_review(),
            proof={"target": {"processId": 12148, "targetWindowHandle": "0x640C0C"}, "status": "current-target-proofonly-passed"},
            reference_recovery=self.reference_recovery_none(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["verdict"], "static-chain-promotion-gates-passed")
        self.assertTrue(summary["promotionGates"]["promotionAllowed"])
        self.assertFalse(summary["promotionGates"]["staleProofPointerUsed"])

    def test_latest_blocked_fresh_api_attempt_blocks_historical_review_reuse(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(latest_refresh_status="blocked"),
            promotion_review=promotion_review(),
            reference_recovery=self.reference_recovery_none(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["verdict"], "blocked-fresh-api-reference-unavailable")
        self.assertIn("latest-fresh-api-source-refresh-blocked", summary["blockers"])
        self.assertIn("rrapicoord:rrapicoord-no-usable-marker", summary["blockers"])
        self.assertFalse(summary["promotionGates"]["freshApiNowVsChainNowCurrent"])

    def test_stale_final_sample_blocks_promotion_readiness(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(),
            promotion_review=promotion_review(captured_at=NOW - timedelta(seconds=900)),
            reference_recovery=self.reference_recovery_none(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["verdict"], "blocked-fresh-api-sample-stale")
        self.assertTrue(any(blocker.startswith("api-now-sample-too-old") for blocker in summary["blockers"]))
        self.assertTrue(any(blocker.startswith("chain-now-sample-too-old") for blocker in summary["blockers"]))

    def test_markdown_contains_chain_and_safety_boundary(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(latest_refresh_status="blocked"),
            promotion_review=promotion_review(),
            reference_recovery=self.reference_recovery_none(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )
        markdown = build_markdown(summary)

        self.assertIn("[rift_x64+0x32EBC80]+0x320/+0x324/+0x328", markdown)
        self.assertIn("does not send input", markdown)
        self.assertIn("latest-fresh-api-source-refresh-blocked", markdown)

    def test_pending_rrapicoord_addon_settings_repair_is_actionable_blocker(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(latest_refresh_status="blocked"),
            promotion_review=promotion_review(),
            reference_recovery=self.reference_recovery_pending_repair(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("rrapicoord-addon-settings-repair-pending-approval", summary["blockers"])
        self.assertTrue(summary["freshnessGate"]["referenceRecoveryDiagnostics"]["pendingSettingsRepairApproval"])
        scan_diagnostics = summary["freshnessGate"]["referenceRecoveryDiagnostics"]["rrapicoordScanDiagnostics"]
        self.assertEqual(scan_diagnostics["counts"]["usableMarkerCount"], 0)
        self.assertIn("Approval required", summary["next"]["recommendedAction"])
        approval = summary["next"]["approvalRequest"]
        self.assertTrue(approval["required"])
        self.assertIn("actionbar 1 slot '-'", approval["approvalText"])
        self.assertFalse(approval["safety"]["movementAllowed"])
        self.assertEqual(approval["liveRefresh"]["slot"], "-")
        self.assertEqual(approval["addonSettingsRepairs"][0]["statusBefore"], "missing")
        self.assertFalse(summary["promotionGates"]["freshApiNowVsChainNowCurrent"])
        step_keys = [step["key"] for step in summary["next"]["steps"]]
        self.assertLess(step_keys.index("rrapicoord-scan-diagnostics"), step_keys.index("rrapicoord-addon-state-diagnostics"))
        steps = {step["key"]: step for step in summary["next"]["steps"]}
        self.assertFalse(steps["rrapicoord-scan-diagnostics"]["requiresApproval"])
        self.assertIn("--target-pid", steps["rrapicoord-scan-diagnostics"]["command"])
        self.assertTrue(steps["apply-rrapicoord-addon-settings-repair"]["requiresApproval"])
        self.assertTrue(steps["refresh-live-addon-runtime"]["requiresApproval"])
        self.assertEqual(steps["refresh-live-addon-runtime"]["knownReloaduiAction"]["slot"], "-")
        self.assertTrue(steps["refresh-live-addon-runtime"]["knownReloaduiAction"]["requiresExactWindowTarget"])
        self.assertFalse(steps["capture-rrapicoord-reference"]["requiresApproval"])
        self.assertIn("34176", steps["capture-rrapicoord-reference"]["command"])
        self.assertIn("", steps["read-static-chain-now"]["command"])
        self.assertEqual(steps["request-static-chain-promotion-approval"]["approvalReason"], "Actor/static-chain promotion is a hard gate.")

        markdown = build_markdown(summary)
        self.assertIn("RRAPICOORD scan diagnostic", markdown)
        self.assertIn("usable=0", markdown)
        self.assertIn("Approval request", markdown)

    def test_no_pending_settings_repair_omits_external_write_step(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(latest_refresh_status="blocked"),
            promotion_review=promotion_review(),
            reference_recovery=self.reference_recovery_none(),
            chain_readback=chain_readback(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        step_keys = {step["key"] for step in summary["next"]["steps"]}
        self.assertNotIn("apply-rrapicoord-addon-settings-repair", step_keys)
        self.assertIn("capture-rrapicoord-reference", step_keys)
        self.assertIn("request-static-chain-promotion-approval", step_keys)

    def test_missing_chain_readback_blocks_even_when_api_sample_is_fresh(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(),
            promotion_review=promotion_review(),
            reference_recovery=self.reference_recovery_none(),
            chain_readback={
                "status": "missing",
                "currentReadbackPassed": False,
                "blockers": ["static-chain-readback-summary-not-found"],
                "warnings": [],
            },
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["verdict"], "blocked-static-chain-current-readback")
        self.assertFalse(summary["promotionGates"]["staticChainCurrentReadbackPassed"])
        self.assertIn("static-chain-readback-summary-not-found", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
