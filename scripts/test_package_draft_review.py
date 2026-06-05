#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import package_draft_review  # noqa: E402


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "riftreader-package-intake.cmd").write_text(
        "@echo off\n"
        "echo {\"status\":\"passed\",\"dryRun\":true,\"changedFileCount\":1}\n"
        "exit /b 0\n",
        encoding="utf-8",
    )


def make_draft(root: Path, draft_id: str, *, title: str, target: str = "docs/proposed.md", self_test: bool = False) -> Path:
    draft_dir = root / ".riftreader-local" / "artifact-bridge-package-drafts" / draft_id
    package_root = draft_dir / "package"
    files_dir = package_root / "files"
    files_dir.mkdir(parents=True)
    source = files_dir / "file-0001.txt"
    source.write_text("# Proposed\n", encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "packageName": title,
        "files": [
            {
                "source": "files/file-0001.txt",
                "target": target,
                "sha256": "",  # replaced below
            }
        ],
        "checks": [],
    }
    # Keep the fixture independent from package_manifest internals while still
    # writing the real manifest name expected by package intake.
    import hashlib

    manifest["files"][0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    (package_root / "riftreader-package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary = {
        "schemaVersion": 1,
        "ok": True,
        "status": "created",
        "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
        "generatedAtUtc": "2026-05-18T18:00:00Z",
        "inboxId": draft_id,
        "messageTitle": title,
        "packageName": title,
        "messageMetadata": {"selfTest": True, "requiresHumanReview": True, "draftOnly": True} if self_test else {},
        "messageSource": {"tool": "package-draft-review-self-test" if self_test else "Desktop ChatGPT"},
        "draftRoot": str(draft_dir.relative_to(root)).replace("/", "\\"),
        "packageRoot": str(package_root.relative_to(root)).replace("/", "\\"),
        "manifestPath": str((package_root / "riftreader-package-manifest.json").relative_to(root)).replace("/", "\\"),
        "fileCount": 1,
        "validation": {"errors": [], "warnings": []},
    }
    (draft_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return draft_dir


def make_unsafe_draft(root: Path, draft_id: str) -> Path:
    draft_dir = root / ".riftreader-local" / "artifact-bridge-package-drafts" / draft_id
    draft_dir.mkdir(parents=True)
    outside_package = root / "outside-package-root"
    outside_package.mkdir(parents=True)
    (outside_package / "riftreader-package-manifest.json").write_text("{}", encoding="utf-8")
    summary = {
        "schemaVersion": 1,
        "ok": True,
        "status": "created",
        "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
        "generatedAtUtc": "2026-05-18T18:00:00Z",
        "inboxId": draft_id,
        "messageTitle": "Unsafe",
        "draftRoot": str(draft_dir.relative_to(root)).replace("/", "\\"),
        "packageRoot": str(outside_package.relative_to(root)).replace("/", "\\"),
        "manifestPath": str((outside_package / "riftreader-package-manifest.json").relative_to(root)).replace("/", "\\"),
        "fileCount": 1,
        "validation": {"errors": [], "warnings": []},
    }
    (draft_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return draft_dir


def make_dry_run_summary(
    root: Path,
    package_root: Path,
    *,
    run_id: str = "20260518T140000Z-dry-run",
    generated_at: str = "2026-05-18T14:00:00Z",
    diff_text: str = "--- a/docs/proposed.md\n+++ b/docs/proposed.md\n",
) -> tuple[Path, str]:
    intake_dir = root / ".riftreader-local" / "package-intake" / run_id
    intake_dir.mkdir(parents=True)
    diff_path = intake_dir / "package.diff"
    diff_path.write_text(diff_text, encoding="utf-8")
    diff_sha256 = hashlib.sha256(diff_path.read_bytes()).hexdigest()
    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-package-intake-summary",
        "generatedAtUtc": generated_at,
        "status": "passed",
        "dryRun": True,
        "packagePath": str(package_root.resolve()),
        "packageRoot": str(package_root.resolve()),
        "blockers": [],
        "warnings": [],
        "errors": [],
        "changedFiles": ["docs/proposed.md"],
        "artifacts": {
            "intakeDir": str(intake_dir.relative_to(root)).replace("/", "\\"),
            "summaryJson": str((intake_dir / "package-intake-summary.json").relative_to(root)).replace("/", "\\"),
            "diff": str(diff_path.relative_to(root)).replace("/", "\\"),
        },
        "safety": {"applyFlagSent": False},
    }
    summary_path = intake_dir / "package-intake-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path, diff_sha256


class PackageDraftReviewTests(unittest.TestCase):
    def test_latest_blocks_when_no_package_drafts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = package_draft_review.latest_package_draft(root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "PACKAGE_DRAFT_EMPTY")
        self.assertTrue(payload["safety"]["readOnlyReview"])

    def test_latest_returns_newest_draft_summary_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            older = make_draft(root, "20260518T120000Z-aaaaaaaaaaaa", title="Older")
            newer = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Newer")
            os.utime(older / "summary.json", (1_700_000_000, 1_700_000_000))
            os.utime(newer / "summary.json", (1_800_000_000, 1_800_000_000))

            payload = package_draft_review.latest_package_draft(root)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["draft"]["draftId"], "20260518T130000Z-bbbbbbbbbbbb")
        self.assertEqual(payload["draft"]["messageTitle"], "Newer")
        self.assertTrue(payload["draft"]["packageRootExists"])
        self.assertTrue(payload["draft"]["manifestExists"])
        self.assertTrue(payload["draft"]["reviewReady"])
        self.assertEqual(payload["draft"]["blockers"], [])
        self.assertFalse(payload["draft"]["selfTest"])
        self.assertEqual(payload["draft"]["origin"], "operator-proposal")

    def test_index_classifies_self_test_drafts_and_tracks_latest_operator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            operator = make_draft(root, "20260518T120000Z-aaaaaaaaaaaa", title="Operator draft")
            self_test = make_draft(
                root,
                "20260518T130000Z-bbbbbbbbbbbb",
                title="Package draft review self-test proposal",
                self_test=True,
            )
            os.utime(operator / "summary.json", (1_700_000_000, 1_700_000_000))
            os.utime(self_test / "summary.json", (1_800_000_000, 1_800_000_000))

            payload = package_draft_review.discover_package_drafts(root)
            latest = package_draft_review.latest_package_draft(root)
            latest_operator = package_draft_review.latest_package_draft(root, operator_only=True)

        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["operatorDraftCount"], 1)
        self.assertEqual(payload["selfTestDraftCount"], 1)
        self.assertEqual(payload["latestDraftId"], "20260518T130000Z-bbbbbbbbbbbb")
        self.assertEqual(payload["latestOperatorDraftId"], "20260518T120000Z-aaaaaaaaaaaa")
        self.assertTrue(payload["latest"]["selfTest"])
        self.assertFalse(payload["latestOperator"]["selfTest"])
        self.assertIn("latest_draft_is_self_test", payload["warnings"])
        self.assertTrue(latest["draft"]["selfTest"])
        self.assertEqual(latest["latestOperatorDraftId"], "20260518T120000Z-aaaaaaaaaaaa")
        self.assertIn("latest_draft_is_self_test", latest["warnings"])

        self.assertTrue(latest_operator["ok"])
        self.assertEqual(latest_operator["kind"], "riftreader-package-draft-review-latest-operator")
        self.assertEqual(latest_operator["draft"]["draftId"], "20260518T120000Z-aaaaaaaaaaaa")
        self.assertFalse(latest_operator["draft"]["selfTest"])
        self.assertTrue(latest_operator["operatorOnly"])

    def test_latest_operator_blocks_when_only_self_test_drafts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            make_draft(
                root,
                "20260518T130000Z-bbbbbbbbbbbb",
                title="Package draft review self-test proposal",
                self_test=True,
            )

            latest_operator = package_draft_review.latest_package_draft(root, operator_only=True)
            dry_run = package_draft_review.dry_run_latest_package_draft(root, timeout_seconds=30, operator_only=True)

        self.assertFalse(latest_operator["ok"])
        self.assertEqual(latest_operator["code"], "PACKAGE_DRAFT_OPERATOR_EMPTY")
        self.assertEqual(latest_operator["operatorDraftCount"], 0)
        self.assertEqual(latest_operator["selfTestDraftCount"], 1)
        self.assertFalse(dry_run["ok"])
        self.assertEqual(dry_run["kind"], "riftreader-package-draft-review-dry-run-latest-operator")
        self.assertEqual(dry_run["code"], "PACKAGE_DRAFT_OPERATOR_EMPTY")

    def test_dry_run_latest_operator_uses_operator_draft_when_self_test_is_newer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            operator = make_draft(root, "20260518T120000Z-aaaaaaaaaaaa", title="Operator draft")
            self_test = make_draft(
                root,
                "20260518T130000Z-bbbbbbbbbbbb",
                title="Package draft review self-test proposal",
                self_test=True,
            )
            os.utime(operator / "summary.json", (1_700_000_000, 1_700_000_000))
            os.utime(self_test / "summary.json", (1_800_000_000, 1_800_000_000))

            payload = package_draft_review.dry_run_latest_package_draft(root, timeout_seconds=30, operator_only=True)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kind"], "riftreader-package-draft-review-dry-run-latest-operator")
        self.assertEqual(payload["draft"]["draftId"], "20260518T120000Z-aaaaaaaaaaaa")
        self.assertFalse(payload["draft"]["selfTest"])
        self.assertTrue(payload["command"]["operatorOnly"])
        self.assertNotIn("--apply", payload["command"]["args"])

    def test_latest_blocks_if_summary_points_package_outside_draft_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            make_unsafe_draft(root, "20260518T130000Z-bbbbbbbbbbbb")

            payload = package_draft_review.latest_package_draft(root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "PACKAGE_DRAFT_NOT_REVIEW_READY")
        self.assertIn("package-root-outside-draft-root", payload["draft"]["blockers"])
        self.assertIn("manifest-path-outside-draft-root", payload["draft"]["blockers"])
        self.assertFalse(payload["draft"]["packageRootExists"])
        self.assertFalse(payload["draft"]["manifestExists"])

    def test_dry_run_blocks_if_summary_points_package_outside_draft_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            make_unsafe_draft(root, "20260518T130000Z-bbbbbbbbbbbb")

            payload = package_draft_review.dry_run_latest_package_draft(root, timeout_seconds=30)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "PACKAGE_DRAFT_NOT_REVIEW_READY")
        self.assertNotIn("commandEnvelope", payload)

    def test_dry_run_latest_invokes_package_intake_without_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Dry run me")

            payload = package_draft_review.dry_run_latest_package_draft(root, timeout_seconds=30)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertNotIn("--apply", payload["command"]["args"])
        self.assertTrue(payload["command"]["dryRunOnly"])
        self.assertTrue(payload["safety"]["packageIntakeInvoked"])
        self.assertTrue(payload["safety"]["dryRunOnly"])
        self.assertEqual(payload["intakeCompactSummary"]["status"], "passed")
        self.assertTrue(payload["intakeCompactSummary"]["dryRun"])

    def test_apply_preflight_latest_operator_binds_fresh_dry_run_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Apply preflight me")
            package_root = draft / "package"
            summary_path, diff_sha256 = make_dry_run_summary(root, package_root)

            payload = package_draft_review.apply_preflight_latest_package_draft(
                root,
                dry_run_summary_path=str(summary_path.relative_to(root)),
                dry_run_diff_sha256=diff_sha256,
                max_age_seconds=10**9,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["approvalFacts"]["draftId"], "20260518T130000Z-bbbbbbbbbbbb")
        self.assertEqual(payload["approvalFacts"]["dryRunDiffSha256"], diff_sha256)
        self.assertFalse(payload["applyToolExposed"])
        self.assertFalse(payload["safety"]["applyFlagSent"])
        self.assertFalse(payload["safety"]["repoSourceMutationExpected"])

    def test_apply_preflight_blocks_diff_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Hash mismatch")
            summary_path, _diff_sha256 = make_dry_run_summary(root, draft / "package")

            payload = package_draft_review.apply_preflight_latest_package_draft(
                root,
                dry_run_summary_path=str(summary_path.relative_to(root)),
                dry_run_diff_sha256="0" * 64,
                max_age_seconds=10**9,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("APPLY_DRY_RUN_HASH_MISMATCH", payload["blockers"])

    def test_apply_preflight_blocks_stale_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Stale dry run")
            summary_path, diff_sha256 = make_dry_run_summary(root, draft / "package", generated_at="2020-01-01T00:00:00Z")

            payload = package_draft_review.apply_preflight_latest_package_draft(
                root,
                dry_run_summary_path=str(summary_path.relative_to(root)),
                dry_run_diff_sha256=diff_sha256,
                max_age_seconds=1,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("APPLY_DRY_RUN_STALE", payload["blockers"])

    def test_apply_preflight_blocks_self_test_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(
                root,
                "20260518T130000Z-bbbbbbbbbbbb",
                title="Package draft review self-test proposal",
                self_test=True,
            )
            summary_path, diff_sha256 = make_dry_run_summary(root, draft / "package")

            payload = package_draft_review.apply_preflight_latest_package_draft(
                root,
                operator_only=False,
                dry_run_summary_path=str(summary_path.relative_to(root)),
                dry_run_diff_sha256=diff_sha256,
                max_age_seconds=10**9,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("APPLY_DRAFT_SELF_TEST_BLOCKED", payload["blockers"])

    def test_self_test_runs_package_proposal_to_dry_run_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = package_draft_review.run_self_test(root, timeout_seconds=30)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])
        self.assertTrue(payload["stages"]["inboxProposalStored"]["ok"])
        self.assertTrue(payload["stages"]["packageDraftCreated"]["ok"])
        self.assertTrue(payload["stages"]["latestDraftReview"]["ok"])
        self.assertTrue(payload["stages"]["latestDraftDryRun"]["ok"])
        self.assertTrue(payload["safety"]["packageIntakeDryRunOnly"])
        self.assertTrue(payload["safety"]["noRepoTargetWrites"])
        dry_run_command = payload["stages"]["latestDraftDryRun"]["command"]["args"]
        self.assertNotIn("--apply", dry_run_command)


if __name__ == "__main__":
    unittest.main()
