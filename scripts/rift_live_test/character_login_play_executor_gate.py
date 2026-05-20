from __future__ import annotations

import argparse
import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
KIND = "riftreader-character-login-play-executor-gate"
DEFAULT_MAX_ARTIFACT_AGE_SECONDS = 300.0
REQUIRED_MCP_STEPS = [
    "bind-exact-target",
    "capture-before-focus",
    "focus-for-click",
    "click-play-once",
    "wait-for-world-transition",
    "capture-after-transition",
    "post-world-proof",
]


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_summary(repo_root: Path, folder: str, filename: str) -> Path | None:
    latest = repo_root / ".riftreader-local" / folder / "latest-run.txt"
    if latest.exists():
        candidate = Path(latest.read_text(encoding="utf-8").strip()) / filename
        if candidate.exists():
            return candidate.resolve()
    matches = [Path(item) for item in glob.glob(str(repo_root / ".riftreader-local" / folder / "run-*" / filename))]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def load_json_object(path: Path | None, label: str, errors: list[dict[str, str]], blockers: list[str]) -> dict[str, Any]:
    if path is None:
        blockers.append(f"missing-{label}")
        return {}
    if not path.exists():
        blockers.append(f"{label}-not-found")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("JSON root is not an object")
        return value
    except Exception as exc:  # noqa: BLE001 - gate should preserve durable parse failures.
        errors.append({"type": type(exc).__name__, "message": str(exc), "path": str(path), "stage": f"load-{label}"})
        return {}


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def artifact_age_seconds(document: dict[str, Any]) -> float | None:
    generated = parse_utc(document.get("generatedAtUtc"))
    if generated is None:
        return None
    return max(0.0, (datetime.now(UTC) - generated).total_seconds())


def normalize_hwnd(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.lower().startswith("0x"):
        return "0x" + text[2:].upper()
    try:
        return f"0x{int(text):X}"
    except ValueError:
        return text.upper()


def target_identity(document: dict[str, Any], *, key: str = "target") -> dict[str, Any]:
    target = document.get(key) if isinstance(document.get(key), dict) else {}
    return {
        "processName": target.get("processName"),
        "processId": target.get("processId"),
        "windowHandle": normalize_hwnd(target.get("windowHandle") or target.get("targetWindowHandle")),
        "processStartUtc": target.get("processStartUtc"),
        "moduleBase": target.get("moduleBase"),
    }


def targets_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left.get("processId") == right.get("processId") and normalize_hwnd(left.get("windowHandle")) == normalize_hwnd(right.get("windowHandle"))


def ordered_manifest_steps(manifest: dict[str, Any]) -> list[str]:
    sequence = manifest.get("mcpToolSequence") if isinstance(manifest.get("mcpToolSequence"), list) else []
    return [str(item.get("step") or "") for item in sequence if isinstance(item, dict)]


def sequence_by_step(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sequence = manifest.get("mcpToolSequence") if isinstance(manifest.get("mcpToolSequence"), list) else []
    return {str(item.get("step") or ""): item for item in sequence if isinstance(item, dict)}


def validate_manifest(manifest: dict[str, Any], blockers: list[str], warnings: list[str]) -> None:
    steps = ordered_manifest_steps(manifest)
    if steps != REQUIRED_MCP_STEPS:
        blockers.append("future-mcp-action-manifest-step-order-mismatch")
    by_step = sequence_by_step(manifest)
    if by_step.get("bind-exact-target", {}).get("tool") != "mcp__rift_game__.find_game_window":
        blockers.append("manifest-bind-step-not-find-game-window")
    if by_step.get("capture-before-focus", {}).get("tool") != "mcp__rift_game__.capture_game_window":
        blockers.append("manifest-pre-capture-step-not-capture-game-window")
    if by_step.get("focus-for-click", {}).get("tool") != "mcp__rift_game__.focus_game_window":
        blockers.append("manifest-focus-step-not-focus-game-window")
    click_step = by_step.get("click-play-once", {})
    if click_step.get("tool") != "mcp__rift_game__.click_client":
        blockers.append("manifest-click-step-not-click-client")
    if click_step.get("arguments") != {"x": 517, "y": 343}:
        blockers.append("manifest-click-arguments-not-expected-play-point")
    if by_step.get("wait-for-world-transition", {}).get("tool") != "mcp__rift_game__.wait_for_frame_change":
        blockers.append("manifest-transition-step-not-wait-for-frame-change")
    if by_step.get("capture-after-transition", {}).get("tool") != "mcp__rift_game__.capture_game_window":
        blockers.append("manifest-post-transition-capture-step-not-capture-game-window")
    if by_step.get("post-world-proof", {}).get("tool") != "repo-proofonly-workflow":
        blockers.append("manifest-post-world-proof-step-missing")
    if manifest.get("neverExecuteBySupervisor") is not True:
        warnings.append("manifest-neverExecuteBySupervisor-not-true")
    play = manifest.get("playButton") if isinstance(manifest.get("playButton"), dict) else {}
    if play.get("maxClicks") != 1:
        blockers.append("manifest-play-max-clicks-not-one")
    if play.get("coordinateSpace") != "client":
        blockers.append("manifest-play-coordinate-space-not-client")


def build_gate(
    *,
    repo_root: Path,
    output_root: Path,
    supervisor_path: Path | None,
    manifest_path: Path | None,
    screen_state_path: Path | None,
    current_truth_path: Path,
    current_proof_path: Path,
    approval_token: str | None,
    allow_world_entry: bool,
    max_artifact_age_seconds: float,
) -> dict[str, Any]:
    blockers: list[str] = []
    execution_blockers: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, str]] = []

    supervisor = load_json_object(supervisor_path, "supervisor-summary", errors, blockers)
    manifest = load_json_object(manifest_path, "future-mcp-action-manifest", errors, blockers)
    screen_state = load_json_object(screen_state_path, "screen-state-summary", errors, blockers)
    current_truth = load_json_object(current_truth_path, "current-truth", errors, blockers)
    current_proof = load_json_object(current_proof_path, "current-proof", errors, blockers)

    if supervisor.get("status") == "failed":
        blockers.append("supervisor-status-failed")
    append_supervisor_data = supervisor.get("dataBlockers") if isinstance(supervisor.get("dataBlockers"), list) else []
    for blocker in append_supervisor_data:
        blockers.append(f"supervisor:{blocker}")
    allowed_supervisor_execution_blockers = {
        "executor-contract-not-ready:blocked",
        "executor-contract:world-entry-not-permitted-by-source-environment",
        "executor-contract:explicit-world-entry-approval-token-missing-or-mismatched",
    }
    supervisor_execution_blockers = (
        supervisor.get("executionBlockers") if isinstance(supervisor.get("executionBlockers"), list) else []
    )
    for blocker in supervisor_execution_blockers:
        if str(blocker) not in allowed_supervisor_execution_blockers:
            blockers.append(f"supervisor-unexpected-execution-blocker:{blocker}")

    manifest_blockers = manifest.get("blockers") if isinstance(manifest.get("blockers"), list) else []
    for blocker in manifest_blockers:
        if str(blocker) != "supervisor-execution-blockers-present":
            blockers.append(f"manifest-unexpected-blocker:{blocker}")

    for label, document in (("supervisor", supervisor), ("screen-state", screen_state)):
        age = artifact_age_seconds(document)
        if age is None:
            blockers.append(f"{label}-missing-generatedAtUtc")
        elif age > max_artifact_age_seconds:
            blockers.append(f"{label}-artifact-too-old:{age:.3f}>{max_artifact_age_seconds:.3f}")

    if screen_state.get("status") != "classified-character-select":
        blockers.append(f"screen-state-not-character-select:{screen_state.get('status')}")
    if screen_state.get("classification") != "character-selection-not-in-world":
        blockers.append(f"screen-classification-not-character-select:{screen_state.get('classification')}")
    if screen_state.get("decision", {}).get("safeToUseCharacterSelectClickTargets") is not True:
        blockers.append("screen-state-click-targets-not-safe")

    validate_manifest(manifest, blockers, warnings)

    supervisor_target = target_identity(supervisor)
    manifest_target = target_identity(manifest)
    truth_target = target_identity(current_truth)
    proof_target = target_identity(current_proof)
    if supervisor and manifest and not targets_match(supervisor_target, manifest_target):
        blockers.append("supervisor-target-does-not-match-manifest-target")
    if supervisor and current_truth and not targets_match(supervisor_target, truth_target):
        blockers.append("supervisor-target-does-not-match-current-truth")
    if supervisor and current_proof and not targets_match(supervisor_target, proof_target):
        blockers.append("supervisor-target-does-not-match-current-proof")

    movement_gate = current_truth.get("movementGate") if isinstance(current_truth.get("movementGate"), dict) else {}
    if movement_gate.get("allowed") is True:
        warnings.append("current-truth-movement-gate-unexpectedly-allowed-before-world-entry")
    current_proof_status = str(current_proof.get("status") or "")
    if current_proof_status != "blocked-target-not-in-world":
        warnings.append(f"current-proof-status-not-character-select-blocker:{current_proof_status}")

    approval = manifest.get("approval") if isinstance(manifest.get("approval"), dict) else {}
    expected_token = str(approval.get("token") or supervisor.get("supervisorDecision", {}).get("expectedApprovalToken") or "").strip()
    provided_token = str(approval_token or "").strip()
    approval_matches = bool(expected_token and provided_token == expected_token)
    if not approval_matches:
        execution_blockers.append("explicit-world-entry-approval-token-missing-or-mismatched")
    if not allow_world_entry:
        execution_blockers.append("allow-world-entry-flag-missing")

    if errors:
        status = "failed"
    elif blockers:
        status = "blocked-data"
    elif execution_blockers:
        status = "blocked-approval-required"
    else:
        status = "ready-for-manual-mcp-executor"

    mcp_sequence = manifest.get("mcpToolSequence") if isinstance(manifest.get("mcpToolSequence"), list) else []
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "blockers": blockers,
        "executionBlockers": execution_blockers,
        "warnings": warnings,
        "errors": errors,
        "input": {
            "supervisorSummary": str(supervisor_path.resolve()) if supervisor_path else None,
            "futureMcpActionManifest": str(manifest_path.resolve()) if manifest_path else None,
            "screenStateSummary": str(screen_state_path.resolve()) if screen_state_path else None,
            "currentTruth": str(current_truth_path.resolve()),
            "currentProof": str(current_proof_path.resolve()),
            "approvalTokenProvided": bool(provided_token),
            "allowWorldEntry": allow_world_entry,
            "maxArtifactAgeSeconds": max_artifact_age_seconds,
        },
        "target": supervisor_target or manifest_target,
        "screenState": {
            "status": screen_state.get("status"),
            "classification": screen_state.get("classification"),
            "confidence": screen_state.get("confidence"),
            "safeToUseCharacterSelectClickTargets": screen_state.get("decision", {}).get("safeToUseCharacterSelectClickTargets"),
        },
        "approval": {
            "required": True,
            "expectedToken": expected_token,
            "provided": bool(provided_token),
            "matches": approval_matches,
            "allowWorldEntry": allow_world_entry,
            "oldTokensInvalidAfterCrashOrRelaunch": True,
        },
        "mcpActionEnvelope": {
            "status": "ready" if status == "ready-for-manual-mcp-executor" else "blocked",
            "willExecuteLiveActions": False,
            "requiresAssistantMcpTools": True,
            "target": supervisor_target or manifest_target,
            "mcpToolSequence": mcp_sequence,
            "maxPlayClicks": 1,
            "failClosedOn": manifest.get("failClosedOn") if isinstance(manifest.get("failClosedOn"), list) else [],
            "postWorldProofRequired": True,
            "note": "This gate never clicks. A future assistant-run MCP executor must revalidate this packet in the same run before focusing/clicking.",
        },
        "safety": {
            "planOnly": True,
            "willExecuteLiveActions": False,
            "movementSent": False,
            "keyInputSent": False,
            "mouseClickSent": False,
            "worldEntryClicked": False,
            "clientLaunchAttempted": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
            "providerWrites": False,
            "gitMutation": False,
        },
        "artifacts": {
            "summaryJson": str((output_root / "character-login-play-executor-gate-summary.json").resolve()),
            "summaryMarkdown": str((output_root / "character-login-play-executor-gate.md").resolve()),
        },
        "next": {
            "recommendedAction": "If world entry is explicitly approved, rerun the supervisor and this gate immediately with the matching token and allow-world-entry flag; then perform at most one MCP Play click and require post-world ProofOnly before movement.",
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    target = summary.get("target") if isinstance(summary.get("target"), dict) else {}
    approval = summary.get("approval") if isinstance(summary.get("approval"), dict) else {}
    screen = summary.get("screenState") if isinstance(summary.get("screenState"), dict) else {}
    lines = [
        "# Character login Play executor gate",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Target: PID `{target.get('processId')}`, HWND `{target.get('windowHandle')}`",
        f"- Screen: `{screen.get('classification')}` confidence `{screen.get('confidence')}`",
        f"- Approval provided: `{str(approval.get('provided')).lower()}`",
        f"- Approval matches: `{str(approval.get('matches')).lower()}`",
        f"- Allow world entry flag: `{str(approval.get('allowWorldEntry')).lower()}`",
        f"- Expected token: `{approval.get('expectedToken')}`",
        "",
        "## Data blockers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in (summary.get("blockers") or [])] or ["- none"])
    lines.extend(["", "## Execution blockers", ""])
    lines.extend([f"- `{item}`" for item in (summary.get("executionBlockers") or [])] or ["- none"])
    lines.extend([
        "",
        "## Safety",
        "",
        "This gate never launches, focuses, clicks, sends keys, enters world, moves, reads live memory, attaches CE/x64dbg, writes providers, or mutates Git.",
        "",
    ])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a future approved Play-click MCP executor packet without sending input.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--supervisor-summary", type=Path)
    parser.add_argument("--future-mcp-action-manifest", type=Path)
    parser.add_argument("--screen-state-summary", type=Path)
    parser.add_argument("--current-truth", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--current-proof", type=Path, default=Path("docs/recovery/current-proof-anchor-readback.json"))
    parser.add_argument("--approval-token")
    parser.add_argument("--allow-world-entry", action="store_true")
    parser.add_argument("--max-artifact-age-seconds", type=float, default=DEFAULT_MAX_ARTIFACT_AGE_SECONDS)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-play-executor-gate" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)

    supervisor_path = args.supervisor_summary.resolve() if args.supervisor_summary else latest_summary(repo_root, "character-login-supervisor", "character-login-supervisor-summary.json")
    manifest_path = args.future_mcp_action_manifest.resolve() if args.future_mcp_action_manifest else (supervisor_path.parent / "future-mcp-action-manifest.json" if supervisor_path else None)
    screen_state_path = args.screen_state_summary.resolve() if args.screen_state_summary else latest_summary(repo_root, "character-login-screen-state", "character-login-screen-state-summary.json")
    current_truth = args.current_truth if args.current_truth.is_absolute() else repo_root / args.current_truth
    current_proof = args.current_proof if args.current_proof.is_absolute() else repo_root / args.current_proof

    summary = build_gate(
        repo_root=repo_root,
        output_root=output_root,
        supervisor_path=supervisor_path,
        manifest_path=manifest_path,
        screen_state_path=screen_state_path,
        current_truth_path=current_truth,
        current_proof_path=current_proof,
        approval_token=args.approval_token,
        allow_world_entry=args.allow_world_entry,
        max_artifact_age_seconds=max(0.0, args.max_artifact_age_seconds),
    )
    summary_json = output_root / "character-login-play-executor-gate-summary.json"
    summary_markdown = output_root / "character-login-play-executor-gate.md"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-play-executor-gate" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))
    if args.json:
        print(json.dumps(summary, indent=2))
    if summary.get("status") == "ready-for-manual-mcp-executor":
        return 0
    if str(summary.get("status", "")).startswith("blocked"):
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
