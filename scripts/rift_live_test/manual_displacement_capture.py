from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_MIN_DISPLACED_PLANAR_DISTANCE = 1.0
DEFAULT_MAX_DISPLACED_REFERENCE_AGE_SECONDS = 300.0


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def path_text(path: Path | str | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    resolved = Path(str(path))
    try:
        return str(resolved.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(resolved)


def resolve_path(repo_root: Path, value: Path | str | None) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else repo_root / path


def normalize_hwnd(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text


def load_coordinate_route(repo_root: Path, route_summary: Path | None) -> tuple[dict[str, Any] | None, list[str]]:
    route_path = route_summary or repo_root / "scripts" / "captures" / "latest-coordinate-proof-route.json"
    route_path = route_path if route_path.is_absolute() else repo_root / route_path
    if not route_path.exists():
        return None, [f"coordinate-proof-route-missing:{path_text(route_path, repo_root)}"]
    route = read_json_object(route_path)
    if route.get("kind") == "latest-coordinate-proof-route-pointer":
        summary_json = resolve_path(repo_root, route.get("summaryJson"))
        if summary_json is None or not summary_json.exists():
            return route, [f"coordinate-proof-route-pointer-summary-missing:{route.get('summaryJson')}"]
        resolved = read_json_object(summary_json)
        resolved["path"] = path_text(summary_json, repo_root)
        resolved["pointerPath"] = path_text(route_path, repo_root)
        return resolved, []
    route["path"] = path_text(route_path, repo_root)
    return route, []


def candidate_compare_file_for(path: Path | None) -> Path | None:
    if path is None:
        return None
    if path.suffix.lower() == ".json":
        return path if path.exists() else None
    if path.suffix.lower() != ".jsonl":
        return None
    candidate = path.with_suffix(".json")
    return candidate if candidate.exists() else None


def sibling_json_for_jsonl(path: Path) -> Path | None:
    return candidate_compare_file_for(path)


def selected_paths_from_route(repo_root: Path, route: dict[str, Any]) -> dict[str, Any]:
    artifacts = route.get("artifacts") if isinstance(route.get("artifacts"), dict) else {}
    memory = route.get("memoryReadback") if isinstance(route.get("memoryReadback"), dict) else {}
    target = route.get("target") if isinstance(route.get("target"), dict) else {}
    readback_path = resolve_path(repo_root, artifacts.get("memoryReadback") or memory.get("path"))
    source_candidate: Path | None = None
    if readback_path and readback_path.exists():
        try:
            readback = read_json_object(readback_path)
            source_candidate = resolve_path(repo_root, readback.get("SourceCandidateFile"))
        except Exception:
            source_candidate = None
    baseline_reference = resolve_path(repo_root, artifacts.get("apiReference"))
    center_files = [
        path
        for value in artifacts.get("centerFiles", [])
        if (path := resolve_path(repo_root, value)) is not None
    ] if isinstance(artifacts.get("centerFiles"), list) else []
    return {
        "target": target,
        "baselineReference": baseline_reference,
        "candidateReadbackFile": source_candidate,
        "candidateCompareFile": candidate_compare_file_for(source_candidate),
        "centerFiles": center_files,
    }


def command_envelope(command: list[str], *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    started_utc = utc_iso()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        ended = time.monotonic()
        return {
            "command": command,
            "cwd": str(cwd),
            "startedAtUtc": started_utc,
            "endedAtUtc": utc_iso(),
            "durationSeconds": round(ended - started, 3),
            "exitCode": result.returncode,
            "timedOut": False,
            "stdoutPreview": result.stdout[-6000:],
            "stderrPreview": result.stderr[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        ended = time.monotonic()
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return {
            "command": command,
            "cwd": str(cwd),
            "startedAtUtc": started_utc,
            "endedAtUtc": utc_iso(),
            "durationSeconds": round(ended - started, 3),
            "exitCode": None,
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
            "stdoutPreview": stdout[-6000:],
            "stderrPreview": stderr[-6000:],
        }


def parse_stdout_json(envelope: dict[str, Any]) -> dict[str, Any]:
    stdout = str(envelope.get("stdoutPreview") or "").strip()
    if not stdout:
        raise ValueError("child stdout was empty")
    value = json.loads(stdout)
    if not isinstance(value, dict):
        raise ValueError("child stdout JSON was not an object")
    return value


def build_command_plan(
    *,
    repo_root: Path,
    output_root: Path,
    process_id: int | None,
    target_window_handle: str | None,
    process_name: str,
    process_start_utc: str | None,
    baseline_reference: Path,
    candidate_readback_file: Path,
    candidate_compare_file: Path,
    center_files: Sequence[Path],
    pose_label: str,
    min_displaced_planar_distance: float,
    max_displaced_reference_age_seconds: float,
) -> dict[str, Any]:
    capture_root = output_root / "capture"
    readiness_root = output_root / "displaced-readiness"
    comparison_root = output_root / "candidate-comparison"
    route_root = output_root / "route"
    milestone_summary = output_root / "milestone-review.json"
    readiness_gate_root = output_root / "proof-readiness-gate"

    capture_command = [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo_root / "scripts" / "capture-riftscan-proof-pose.ps1"),
        "-CandidateFile",
        str(candidate_readback_file),
        "-OutputRoot",
        str(capture_root),
        "-PoseLabel",
        pose_label,
        "-ProcessName",
        process_name,
        "-Json",
    ]
    if process_id is not None:
        capture_command.extend(["-ProcessId", str(process_id)])
    if target_window_handle:
        capture_command.extend(["-TargetWindowHandle", normalize_hwnd(target_window_handle) or str(target_window_handle)])

    route_command = [
        sys.executable,
        str(repo_root / "scripts" / "coordinate_proof_route.py"),
        "--pid",
        str(process_id),
        "--hwnd",
        normalize_hwnd(target_window_handle) or str(target_window_handle),
        "--process-name",
        process_name,
        "--api-reference",
        "{displaced_reference}",
        "--memory-readback",
        "{memory_readback}",
        *sum((["--center-file", str(path)] for path in center_files), []),
        "--candidate-comparison",
        str(comparison_root / "summary.json"),
        "--displaced-readiness-summary",
        str(readiness_root / "summary.json"),
        "--output-root",
        str(route_root),
        "--write-summary",
        "--update-current-truth",
        "--compact-json",
    ]
    if process_start_utc:
        route_command.extend(["--process-start-utc", process_start_utc])

    return {
        "captureRoot": str(capture_root),
        "readinessRoot": str(readiness_root),
        "comparisonRoot": str(comparison_root),
        "routeRoot": str(route_root),
        "milestoneSummary": str(milestone_summary),
        "readinessGateRoot": str(readiness_gate_root),
        "capture": capture_command,
        "readinessTemplate": [
            sys.executable,
            str(repo_root / "scripts" / "coordinate_displaced_reference_readiness.py"),
            "--pid",
            str(process_id),
            "--hwnd",
            normalize_hwnd(target_window_handle) or str(target_window_handle),
            "--api-reference",
            str(baseline_reference),
            "--displaced-api-reference",
            "{displaced_reference}",
            "--max-age-delta-seconds",
            str(max_displaced_reference_age_seconds),
            "--min-planar-displacement",
            str(min_displaced_planar_distance),
            "--output-root",
            str(readiness_root),
            "--json",
        ],
        "comparisonTemplate": [
            sys.executable,
            str(repo_root / "scripts" / "coordinate_candidate_compare.py"),
            "--api-reference",
            str(baseline_reference),
            "--displaced-api-reference",
            "{displaced_reference}",
            "--candidate-file",
            str(candidate_compare_file),
            "--min-displaced-planar-distance",
            str(min_displaced_planar_distance),
            "--max-displaced-reference-age-seconds",
            str(max_displaced_reference_age_seconds),
            "--output-root",
            str(comparison_root),
            "--json",
        ],
        "routeTemplate": route_command,
        "milestoneReviewTemplate": [
            sys.executable,
            str(repo_root / "scripts" / "riftscan_milestone_review.py"),
            "--pid",
            str(process_id),
            "--hwnd",
            normalize_hwnd(target_window_handle) or str(target_window_handle),
            "--process-name",
            process_name,
            "--proof-route-summary",
            str(route_root / "coordinate-proof-route.json"),
            "--write-summary",
            "--write-markdown",
            "--summary-file",
            str(milestone_summary),
            "--compact-json",
        ],
        "readinessGateTemplate": [
            sys.executable,
            str(repo_root / "scripts" / "coordinate_proof_readiness_gate.py"),
            "--target-pid",
            str(process_id),
            "--target-hwnd",
            normalize_hwnd(target_window_handle) or str(target_window_handle),
            "--process-name",
            process_name,
            "--milestone-review-summary",
            str(milestone_summary),
            "--output-root",
            str(readiness_gate_root),
            "--json",
        ],
    }


def fill_template(command: list[str], replacements: dict[str, str]) -> list[str]:
    return [replacements.get(part, part) for part in command]


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Manual displacement capture summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Output root: `{summary.get('outputRoot')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        f"- Input sent: `{str(summary.get('safety', {}).get('inputSent')).lower()}`",
        f"- No Cheat Engine: `{str(summary.get('safety', {}).get('noCheatEngine')).lower()}`",
        "",
        "## Artifacts",
        "",
        "| Artifact | Path |",
        "|---|---|",
    ]
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    for name, value in artifacts.items():
        lines.append(f"| `{name}` | `{value}` |")
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings") or [])
    next_action = dict_or_empty(summary.get("next"))
    if next_action:
        lines.extend(["", "## Next", ""])
        lines.append(f"- Recommended action: `{next_action.get('recommendedAction')}`")
    lines.extend(["", "## Commands", "", "| Step | Exit code | Duration seconds |", "|---|---:|---:|"])
    for step in summary.get("commands", []):
        lines.append(f"| `{step.get('step')}` | `{step.get('exitCode')}` | `{step.get('durationSeconds')}` |")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="After the operator manually displaces the player, capture a no-input displaced reference and run proof gates."
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--route-summary", type=Path, help="Coordinate proof route JSON or latest pointer. Defaults to latest pointer.")
    parser.add_argument("--baseline-api-reference", type=Path, help="Baseline API reference captured before manual displacement.")
    parser.add_argument("--candidate-file", type=Path, help="Candidate file for readback. JSONL is supported by the readback leaf helper.")
    parser.add_argument("--candidate-compare-file", type=Path, help="JSON candidate file for offline comparison. Defaults to JSON sibling of --candidate-file.")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--pose-label", default="operator-displaced")
    parser.add_argument("--min-displaced-planar-distance", type=float, default=DEFAULT_MIN_DISPLACED_PLANAR_DISTANCE)
    parser.add_argument("--max-displaced-reference-age-seconds", type=float, default=DEFAULT_MAX_DISPLACED_REFERENCE_AGE_SECONDS)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def run_self_test() -> dict[str, Any]:
    with __import__("tempfile").TemporaryDirectory() as temp:
        root = Path(temp)
        candidate_jsonl = root / "candidate.jsonl"
        candidate_json = root / "candidate.json"
        candidate_jsonl.write_text("{}\n", encoding="utf-8")
        candidate_json.write_text("{}", encoding="utf-8")
        resolved = sibling_json_for_jsonl(candidate_jsonl)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "manual-displacement-capture-self-test",
            "status": "passed" if resolved == candidate_json else "failed",
            "candidateJsonSibling": str(resolved),
            "safety": {
                "movementSent": False,
                "inputSent": False,
                "noCheatEngine": True,
                "x64dbgAttached": False,
                "processAttachOrMemoryReadStarted": False,
            },
        }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        result = run_self_test()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "passed" else 1

    repo_root = args.repo_root.resolve()
    output_root = (args.output_root or repo_root / "scripts" / "captures" / f"manual-displacement-capture-{utc_stamp()}").resolve()
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-manual-displacement-capture",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "outputRoot": str(output_root),
        "blockers": [],
        "warnings": [],
        "errors": [],
        "commands": [],
        "artifacts": {"summaryJson": str(summary_json), "summaryMarkdown": str(summary_md)},
        "next": {
            "recommendedAction": "Ask the operator to manually move the player at least 1 meter, then rerun without --dry-run.",
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "processAttachOrMemoryReadStarted": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
        },
    }
    try:
        route, route_issues = load_coordinate_route(repo_root, args.route_summary)
        summary["blockers"].extend(route_issues)
        route_defaults = selected_paths_from_route(repo_root, route) if route else {}
        target = route_defaults.get("target") if isinstance(route_defaults.get("target"), dict) else {}
        process_id = args.pid if args.pid is not None else target.get("processId")
        hwnd = args.hwnd or target.get("targetWindowHandle")
        process_name = args.process_name or target.get("processName") or DEFAULT_PROCESS_NAME
        process_start_utc = target.get("processStartUtc")
        baseline = resolve_path(repo_root, args.baseline_api_reference) or route_defaults.get("baselineReference")
        candidate_readback = resolve_path(repo_root, args.candidate_file) or route_defaults.get("candidateReadbackFile")
        candidate_compare = resolve_path(repo_root, args.candidate_compare_file) or (
            candidate_compare_file_for(candidate_readback)
        ) or route_defaults.get("candidateCompareFile")
        center_files = [path for path in route_defaults.get("centerFiles", []) if isinstance(path, Path)]

        for label, path in (
            ("baseline-api-reference", baseline),
            ("candidate-file", candidate_readback),
            ("candidate-compare-file", candidate_compare),
        ):
            if path is None or not path.exists():
                summary["blockers"].append(f"{label}-missing:{path_text(path, repo_root)}")
        if process_id is None:
            summary["blockers"].append("target-pid-missing")
        if not hwnd:
            summary["blockers"].append("target-hwnd-missing")

        if not summary["blockers"]:
            plan = build_command_plan(
                repo_root=repo_root,
                output_root=output_root,
                process_id=int(process_id),
                target_window_handle=str(hwnd),
                process_name=str(process_name),
                process_start_utc=str(process_start_utc) if process_start_utc else None,
                baseline_reference=baseline,
                candidate_readback_file=candidate_readback,
                candidate_compare_file=candidate_compare,
                center_files=center_files,
                pose_label=args.pose_label,
                min_displaced_planar_distance=args.min_displaced_planar_distance,
                max_displaced_reference_age_seconds=args.max_displaced_reference_age_seconds,
            )
            summary["plan"] = plan

            if args.dry_run:
                summary["status"] = "dry-run"
                return 0

            capture = command_envelope(plan["capture"], cwd=repo_root, timeout_seconds=args.timeout_seconds)
            capture["step"] = "capture"
            summary["commands"].append(capture)
            if capture["exitCode"] != 0:
                if capture.get("timedOut"):
                    summary["blockers"].append(f"capture-timeout:{capture.get('timeoutSeconds')}")
                else:
                    summary["blockers"].append(f"capture-failed:{capture['exitCode']}")
                summary["status"] = "blocked"
                return 2
            capture_json = parse_stdout_json(capture)
            summary["safety"]["processAttachOrMemoryReadStarted"] = True
            summary["safety"]["readOnlyMemoryReadStarted"] = True
            displaced_reference = capture_json.get("ReferenceFile")
            memory_readback = capture_json.get("ReadbackSummaryFile")
            summary["artifacts"]["captureOutputRoot"] = capture_json.get("OutputRoot")
            summary["artifacts"]["displacedReference"] = displaced_reference
            summary["artifacts"]["memoryReadback"] = memory_readback
            if not displaced_reference or not memory_readback:
                summary["blockers"].append("capture-missing-reference-or-readback")
                summary["status"] = "blocked"
                return 2

            replacements = {"{displaced_reference}": str(displaced_reference), "{memory_readback}": str(memory_readback)}
            for step_name, template_key, tolerated_blocked in (
                ("displaced-readiness", "readinessTemplate", True),
                ("candidate-comparison", "comparisonTemplate", True),
                ("route", "routeTemplate", False),
                ("milestone-review", "milestoneReviewTemplate", False),
                ("readiness-gate", "readinessGateTemplate", False),
            ):
                command = fill_template(plan[template_key], replacements)
                envelope = command_envelope(command, cwd=repo_root, timeout_seconds=args.timeout_seconds)
                envelope["step"] = step_name
                summary["commands"].append(envelope)
                if envelope["exitCode"] not in (0, 2) or (envelope["exitCode"] == 2 and not tolerated_blocked):
                    if envelope.get("timedOut"):
                        summary["blockers"].append(f"{step_name}-timeout:{envelope.get('timeoutSeconds')}")
                    else:
                        summary["blockers"].append(f"{step_name}-failed:{envelope['exitCode']}")
                    summary["status"] = "blocked"
                    return 2

            readiness = read_json_object(output_root / "displaced-readiness" / "summary.json")
            comparison = read_json_object(output_root / "candidate-comparison" / "summary.json")
            route_summary = read_json_object(output_root / "route" / "coordinate-proof-route.json")
            summary["artifacts"].update(
                {
                    "displacedReadiness": str(output_root / "displaced-readiness" / "summary.json"),
                    "candidateComparison": str(output_root / "candidate-comparison" / "summary.json"),
                    "coordinateProofRoute": str(output_root / "route" / "coordinate-proof-route.json"),
                    "milestoneReview": str(output_root / "milestone-review.json"),
                    "readinessGate": str(output_root / "proof-readiness-gate" / "summary.json"),
                }
            )
            promotion = route_summary.get("promotionReadiness") if isinstance(route_summary.get("promotionReadiness"), dict) else {}
            if readiness.get("status") != "passed":
                summary["blockers"].append(f"displaced-readiness-not-passed:{readiness.get('status')}")
            if comparison.get("status") != "api-candidate-two-reference-match":
                summary["blockers"].append(f"candidate-comparison-not-two-reference:{comparison.get('status')}")
            if promotion.get("proofAnchorPromotionAllowed") is not True:
                summary["blockers"].append(f"proof-anchor-promotion-not-ready:{promotion.get('status')}")
            summary["status"] = "passed" if not summary["blockers"] else "blocked"
            summary["next"] = {
                "recommendedAction": (
                    "Review the new route for proof-anchor promotion."
                    if summary["status"] == "passed"
                    else "Move farther from the baseline pose and rerun the manual displacement capture."
                )
            }
            return 0 if summary["status"] == "passed" else 2
        summary["status"] = "blocked"
        summary["next"] = {"recommendedAction": "Resolve the listed input artifact/target blockers, then rerun."}
        return 2
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, markdown_summary(summary))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(json.dumps({"status": summary.get("status"), "summaryJson": str(summary_json)}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
