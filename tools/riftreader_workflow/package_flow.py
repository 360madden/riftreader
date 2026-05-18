# Version: riftreader-package-flow-v0.1.3
# Total-Character-Count: 24322
# Purpose: Python-owned package intake orchestration for repeated RiftReader patch apply/validation flows; PowerShell/CMD wrappers stay thin.

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple
import zipfile


TOOL_VERSION = "riftreader-package-flow-v0.1.4"
MANIFEST_NAME = "riftreader-package-manifest.json"

PROFILE_COMMANDS: Dict[str, Dict[str, Any]] = {
    "local-artifact-bridge": {
        "expected_files": [
            "tools/riftreader_workflow/local_artifact_bridge.py",
            "scripts/riftreader-local-artifact-bridge.cmd",
            "scripts/test_local_artifact_bridge.py",
            "docs/workflow/local-artifact-bridge.md",
        ],
        "commands": [
            [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/local_artifact_bridge.py", "scripts/test_local_artifact_bridge.py"],
            [sys.executable, "-m", "unittest", "scripts.test_local_artifact_bridge"],
            [sys.executable, "tools/riftreader_workflow/local_artifact_bridge.py", "--self-test"],
            ["git", "--no-pager", "diff", "--check"],
        ],
    },
    "transport-probe": {
        "expected_files": [
            "tools/riftreader_workflow/transport_probe.py",
            "scripts/riftreader-transport-probe.cmd",
            "scripts/test_transport_probe.py",
            "docs/workflow/transport-probe.md",
        ],
        "commands": [
            [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/transport_probe.py", "scripts/test_transport_probe.py"],
            [sys.executable, "-m", "unittest", "scripts.test_transport_probe"],
            [sys.executable, "tools/riftreader_workflow/transport_probe.py", "--json", "self-test"],
            ["git", "--no-pager", "diff", "--check"],
        ],
    },
    "package-flow": {
        "expected_files": [
            "tools/riftreader_workflow/package_flow.py",
            "scripts/riftreader-package-flow.cmd",
            "scripts/test_package_flow.py",
            "docs/workflow/package-flow.md",
        ],
        "commands": [
            [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/package_flow.py", "scripts/test_package_flow.py"],
            [sys.executable, "-m", "unittest", "scripts.test_package_flow"],
            [sys.executable, "tools/riftreader_workflow/package_flow.py", "--json", "self-test"],
            ["git", "--no-pager", "diff", "--check"],
        ],
    },

    "main-merge": {
        "expected_files": [
            "tools/riftreader_workflow/main_merge.py",
            "scripts/riftreader-main-merge.cmd",
            "scripts/test_main_merge.py",
            "docs/workflow/main-merge.md",
        ],
        "commands": [
            [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/main_merge.py", "scripts/test_main_merge.py"],
            [sys.executable, "-m", "unittest", "scripts.test_main_merge"],
            [sys.executable, "tools/riftreader_workflow/main_merge.py", "--json", "self-test"],
            ["git", "--no-pager", "diff", "--check"],
        ],
    },

    "policy-lint": {
        "expected_files": [
            "tools/riftreader_workflow/policy_lint.py",
            "scripts/riftreader-policy-lint.cmd",
            "scripts/test_policy_lint.py",
            "docs/workflow/policy-lint.md",
        ],
        "commands": [
            [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/policy_lint.py", "scripts/test_policy_lint.py"],
            [sys.executable, "-m", "unittest", "scripts.test_policy_lint"],
            [sys.executable, "tools/riftreader_workflow/policy_lint.py", "--json", "self-test"],
            [sys.executable, "tools/riftreader_workflow/policy_lint.py", "--json", "validate-repo", "--scope", "changed"],
            ["git", "--no-pager", "diff", "--check"],
        ],
    },
    "github-review-publish": {
        "expected_files": [
            "tools/riftreader_workflow/github_review_publish.py",
            "scripts/riftreader-github-review-publish.cmd",
            "scripts/test_github_review_publish.py",
            "docs/workflow/github-review-publish.md",
            "docs/workflow/chatgpt-development-standards.md",
        ],
        "commands": [
            [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/github_review_publish.py", "scripts/test_github_review_publish.py"],
            [sys.executable, "-m", "unittest", "scripts.test_github_review_publish"],
            [sys.executable, "tools/riftreader_workflow/github_review_publish.py", "--json", "self-test"],
            ["git", "--no-pager", "diff", "--check"],
        ],
    },
}

PROFILE_ALIASES = {
    "bridge": "local-artifact-bridge",
    "local_bridge": "local-artifact-bridge",
    "local-artifact-bridge": "local-artifact-bridge",
    "transport": "transport-probe",
    "transport-probe": "transport-probe",
    "package-flow": "package-flow",
    "main-merge": "main-merge",
    "main_merge": "main-merge",
    "merge": "main-merge",
    "policy-lint": "policy-lint",
    "policy_lint": "policy-lint",
    "policy": "policy-lint",
    "github-review-publish": "github-review-publish",
    "review-publish": "github-review-publish",
    "github-publish": "github-review-publish",
}


class PackageFlowError(RuntimeError):
    """Raised for controlled package-flow failures."""


def repo_root_from(start: Optional[str]) -> Path:
    if start:
        return Path(start).expanduser().resolve()
    return Path.cwd().resolve()


def repo_join(root: Path, rel: str) -> Path:
    safe = normalize_repo_path(rel)
    result = root
    for part in safe.split("/"):
        result = result / part
    return result


def normalize_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackageFlowError("empty repo-relative path")
    raw = value.replace("\\", "/")
    if raw.startswith("/") or raw.startswith("//"):
        raise PackageFlowError(f"absolute path rejected: {value}")
    if len(raw) >= 2 and raw[1] == ":":
        raise PackageFlowError(f"drive-rooted path rejected: {value}")
    parts = [part for part in raw.split("/") if part]
    if any(part in (".", "..") for part in parts):
        raise PackageFlowError(f"path traversal rejected: {value}")
    return "/".join(parts)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest_from_zip(package_path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(package_path, "r") as archive:
        try:
            with archive.open(MANIFEST_NAME, "r") as handle:
                return json.loads(handle.read().decode("utf-8"))
        except KeyError as exc:
            raise PackageFlowError(f"missing {MANIFEST_NAME}") from exc


def zip_member_names(package_path: Path) -> List[str]:
    with zipfile.ZipFile(package_path, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise PackageFlowError(f"corrupt zip member: {bad}")
        return sorted(archive.namelist())


def manifest_file_entries(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise PackageFlowError("manifest files[] is missing or empty")
    result: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise PackageFlowError(f"manifest file entry {index} is not an object")
        result.append(entry)
    return result


def entry_source(entry: Dict[str, Any]) -> str:
    source = entry.get("source")
    if not isinstance(source, str) or not source.strip():
        raise PackageFlowError("manifest file entry missing source")
    return normalize_repo_path(source)


def entry_target(entry: Dict[str, Any]) -> str:
    for key in ("target", "destination", "path", "source"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_repo_path(value)
    raise PackageFlowError("manifest file entry missing target/destination/path/source")


def infer_profile(package_path: Optional[Path], manifest: Optional[Dict[str, Any]]) -> str:
    probe = ""
    if package_path is not None:
        probe += " " + package_path.name.lower()
    if manifest is not None:
        for key in ("package", "packageName", "purpose", "promptType"):
            value = manifest.get(key)
            if isinstance(value, str):
                probe += " " + value.lower()
    if "transport" in probe:
        return "transport-probe"
    if "localartifactbridge" in probe or "local-artifact-bridge" in probe or "artifact bridge" in probe:
        return "local-artifact-bridge"
    if "githubreviewpublish" in probe or "github-review-publish" in probe or "review publish" in probe:
        return "github-review-publish"
    if "mainmerge" in probe or "main-merge" in probe or "main merge" in probe:
        return "main-merge"
    if "policylint" in probe or "policy-lint" in probe or "policy lint" in probe:
        return "policy-lint"
    if "packageflow" in probe or "package-flow" in probe or "package flow" in probe:
        return "package-flow"
    raise PackageFlowError("could not infer profile; pass --profile explicitly")


def resolve_profile(name: str, package_path: Optional[Path] = None, manifest: Optional[Dict[str, Any]] = None) -> str:
    if name == "auto":
        return infer_profile(package_path, manifest)
    key = name.strip().lower()
    if key not in PROFILE_ALIASES:
        raise PackageFlowError(f"unknown profile: {name}")
    return PROFILE_ALIASES[key]


def validate_package(package_path: Path, expected_sha256: Optional[str] = None) -> Dict[str, Any]:
    if not package_path.is_file():
        raise PackageFlowError(f"package missing: {package_path}")
    actual_sha = sha256_file(package_path)
    if expected_sha256:
        expected = expected_sha256.lower()
        if actual_sha.lower() != expected:
            raise PackageFlowError(f"ZIP SHA256 mismatch: actual={actual_sha} expected={expected}")

    members = zip_member_names(package_path)
    for member in members:
        normalized = normalize_repo_path(member)
        if normalized != member.replace("\\", "/"):
            raise PackageFlowError(f"zip member normalized unexpectedly: {member}")
        if "__pycache__" in normalized.split("/") or normalized.endswith(".pyc"):
            raise PackageFlowError(f"blocked build artifact in zip: {member}")

    manifest = load_manifest_from_zip(package_path)
    entries = manifest_file_entries(manifest)

    file_reports: List[Dict[str, Any]] = []
    with zipfile.ZipFile(package_path, "r") as archive:
        for entry in entries:
            source = entry_source(entry)
            target = entry_target(entry)
            if source not in members:
                raise PackageFlowError(f"manifest source missing from zip: {source}")
            data = archive.read(source)
            digest = hashlib.sha256(data).hexdigest()
            size = len(data)
            expected_digest = str(entry.get("sha256", "")).lower()
            if expected_digest and digest != expected_digest:
                raise PackageFlowError(f"manifest sha256 mismatch for {source}")
            expected_size = entry.get("sizeBytes")
            if isinstance(expected_size, int) and size != expected_size:
                raise PackageFlowError(f"manifest sizeBytes mismatch for {source}")
            file_reports.append({
                "source": source,
                "target": target,
                "sizeBytes": size,
                "sha256": digest,
            })

    return {
        "package": str(package_path),
        "packageSha256": actual_sha,
        "memberCount": len(members),
        "manifestFileCount": len(entries),
        "files": file_reports,
        "manifest": manifest,
    }


def command_for_platform(command: List[str]) -> List[str]:
    if command and command[0].lower().endswith((".cmd", ".bat")):
        if os.name == "nt":
            return ["cmd", "/d", "/c", command[0], *command[1:]]
        return ["cmd", "/c", command[0], *command[1:]]
    return command


def run_command(repo_root: Path, command: List[str], timeout_seconds: int) -> Dict[str, Any]:
    if not command:
        raise PackageFlowError("empty command")
    platform_command = command_for_platform(command)
    completed = subprocess.run(
        platform_command,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        shell=False,
    )
    report = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "pass": completed.returncode == 0,
    }
    if completed.returncode != 0:
        stdout_tail = completed.stdout[-1000:].replace("\n", "\\n")
        stderr_tail = completed.stderr[-1000:].replace("\n", "\\n")
        raise PackageFlowError(
            f"command failed rc={completed.returncode}: {' '.join(command)}; "
            f"stdout_tail={stdout_tail!r}; stderr_tail={stderr_tail!r}"
        )
    return report


def package_intake_path(repo_root: Path) -> Path:
    return repo_join(repo_root, "scripts/riftreader-package-intake.cmd")


def run_package_intake(repo_root: Path, package_path: Path, timeout_seconds: int) -> Dict[str, Any]:
    intake = package_intake_path(repo_root)
    if not intake.is_file():
        raise PackageFlowError(f"package intake helper missing: {intake}")
    command = [str(intake), "--package", str(package_path), "--apply"]
    completed = subprocess.run(
        command_for_platform(command),
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        shell=False,
    )
    failed_text = "Status: failed" in completed.stdout or "Status: failed" in completed.stderr
    report = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "pass": completed.returncode == 0 and not failed_text,
    }
    if not report["pass"]:
        raise PackageFlowError("package intake failed")
    return report


def verify_expected_files(repo_root: Path, expected_files: Iterable[str]) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for rel in expected_files:
        safe = normalize_repo_path(rel)
        path = repo_join(repo_root, safe)
        exists = path.is_file()
        reports.append({"path": safe, "exists": exists})
        if not exists:
            raise PackageFlowError(f"expected file missing after apply: {safe}")
    return reports


def profile_commands(profile: str) -> List[List[str]]:
    profile_data = PROFILE_COMMANDS.get(profile)
    if not profile_data:
        raise PackageFlowError(f"unknown profile: {profile}")
    return list(profile_data["commands"])


def profile_expected_files(profile: str) -> List[str]:
    profile_data = PROFILE_COMMANDS.get(profile)
    if not profile_data:
        raise PackageFlowError(f"unknown profile: {profile}")
    return list(profile_data["expected_files"])


def apply_validate(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = repo_root_from(args.repo_root)
    package_path = Path(args.package).expanduser().resolve()
    package_report = validate_package(package_path, args.expected_sha256)
    manifest = package_report["manifest"]
    profile = resolve_profile(args.profile, package_path, manifest)
    expected_files = profile_expected_files(profile)

    result: Dict[str, Any] = {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "apply-validate",
        "repoRoot": str(repo_root),
        "profile": profile,
        "package": package_report,
        "steps": [],
        "ok": False,
    }

    if not args.inspect_only:
        result["steps"].append({"name": "package_intake", **run_package_intake(repo_root, package_path, args.timeout_seconds)})
    result["steps"].append({"name": "expected_files", "files": verify_expected_files(repo_root, expected_files), "pass": True})

    if not args.inspect_only:
        for command in profile_commands(profile):
            result["steps"].append({"name": "command", **run_command(repo_root, command, args.timeout_seconds)})
    result["ok"] = True
    return result


def validate_current(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = repo_root_from(args.repo_root)
    profile = resolve_profile(args.profile)
    result: Dict[str, Any] = {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "validate-current",
        "repoRoot": str(repo_root),
        "profile": profile,
        "steps": [],
        "ok": False,
    }
    result["steps"].append({"name": "expected_files", "files": verify_expected_files(repo_root, profile_expected_files(profile)), "pass": True})
    for command in profile_commands(profile):
        result["steps"].append({"name": "command", **run_command(repo_root, command, args.timeout_seconds)})
    result["ok"] = True
    return result


def self_test(_args: argparse.Namespace) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="riftreader-package-flow-selftest-") as temp_name:
        temp = Path(temp_name)
        payload_file = temp / "tools" / "riftreader_workflow" / "sample.py"
        payload_file.parent.mkdir(parents=True)
        payload_file.write_text("# sample\n", encoding="utf-8")
        digest = sha256_file(payload_file)
        manifest = {
            "schemaVersion": 1,
            "package": "package-flow-self-test",
            "files": [
                {
                    "source": "tools/riftreader_workflow/sample.py",
                    "target": "tools/riftreader_workflow/sample.py",
                    "destination": "tools/riftreader_workflow/sample.py",
                    "path": "tools/riftreader_workflow/sample.py",
                    "sha256": digest,
                    "sizeBytes": payload_file.stat().st_size,
                }
            ],
        }
        manifest_file = temp / MANIFEST_NAME
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        package_path = temp / "self-test.zip"
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(payload_file, "tools/riftreader_workflow/sample.py")
            archive.write(manifest_file, MANIFEST_NAME)

        report = validate_package(package_path)
        checks.append({"name": "valid_package", "pass": report["manifestFileCount"] == 1})

        try:
            normalize_repo_path("../bad")
            checks.append({"name": "traversal_rejected", "pass": False})
        except PackageFlowError:
            checks.append({"name": "traversal_rejected", "pass": True})

        try:
            validate_package(package_path, "0" * 64)
            checks.append({"name": "sha_mismatch_rejected", "pass": False})
        except PackageFlowError:
            checks.append({"name": "sha_mismatch_rejected", "pass": True})

    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "selfTest": True,
        "checkCount": len(checks),
        "checks": checks,
        "ok": ok,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RiftReader Python-owned package intake flow orchestrator.")
    parser.add_argument("--json", action="store_true", help="Emit clean JSON only.")
    sub = parser.add_subparsers(dest="command", required=True)

    apply_parser = sub.add_parser("apply-validate", help="Validate package, apply through repo intake, and run profile tests.")
    apply_parser.add_argument("--package", required=True, help="Path to package ZIP.")
    apply_parser.add_argument("--expected-sha256", default=None, help="Expected ZIP SHA-256.")
    apply_parser.add_argument("--profile", default="auto", help="Profile: auto, local-artifact-bridge, transport-probe, package-flow, main-merge, policy-lint, github-review-publish.")
    apply_parser.add_argument("--repo-root", default=None, help="Repo root. Defaults to current directory.")
    apply_parser.add_argument("--timeout-seconds", type=int, default=180, help="Timeout per native command.")
    apply_parser.add_argument("--inspect-only", action="store_true", help="Validate package and expected files only; do not apply or run commands.")

    current_parser = sub.add_parser("validate-current", help="Run expected-file and validation commands for an already-applied profile.")
    current_parser.add_argument("--profile", required=True, help="Profile: local-artifact-bridge, transport-probe, package-flow, main-merge, policy-lint, github-review-publish.")
    current_parser.add_argument("--repo-root", default=None, help="Repo root. Defaults to current directory.")
    current_parser.add_argument("--timeout-seconds", type=int, default=180, help="Timeout per native command.")

    inspect_parser = sub.add_parser("inspect-package", help="Validate package manifest and hashes without applying.")
    inspect_parser.add_argument("--package", required=True, help="Path to package ZIP.")
    inspect_parser.add_argument("--expected-sha256", default=None, help="Expected ZIP SHA-256.")

    sub.add_parser("self-test", help="Run internal synthetic checks.")
    return parser


def print_report(report: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"tool: {report.get('tool', TOOL_VERSION)}")
    print(f"command: {report.get('command', 'self-test')}")
    print(f"ok: {report.get('ok')}")
    if "profile" in report:
        print(f"profile: {report['profile']}")
    if "package" in report:
        package = report["package"]
        print(f"packageSha256: {package.get('packageSha256')}")
        print(f"manifestFileCount: {package.get('manifestFileCount')}")
    if "checks" in report:
        for check in report["checks"]:
            print(f"check: {check['name']} pass={check['pass']}")
    if "steps" in report:
        for step in report["steps"]:
            print(f"step: {step['name']} pass={step.get('pass')}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "apply-validate":
            report = apply_validate(args)
        elif args.command == "validate-current":
            report = validate_current(args)
        elif args.command == "inspect-package":
            package_path = Path(args.package).expanduser().resolve()
            report = {
                "schemaVersion": 1,
                "tool": TOOL_VERSION,
                "command": "inspect-package",
                "package": validate_package(package_path, args.expected_sha256),
                "ok": True,
            }
        elif args.command == "self-test":
            report = self_test(args)
            if not report.get("ok"):
                print_report(report, args.json)
                return 1
        else:
            parser.error("unknown command")
            return 2
        print_report(report, args.json)
        return 0
    except (PackageFlowError, subprocess.TimeoutExpired, OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        error_report = {
            "schemaVersion": 1,
            "tool": TOOL_VERSION,
            "ok": False,
            "error": str(exc),
            "errorType": exc.__class__.__name__,
        }
        print_report(error_report, args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
