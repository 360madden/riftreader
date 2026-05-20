from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
SUPERVISOR_KIND = "riftreader-character-login-supervisor"
DEFAULT_TARGET_CHARACTER = "ATANK"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def preview(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... <truncated {len(text) - limit} chars>"


def parse_json_stdout(stdout: str) -> tuple[dict[str, Any], str | None]:
    text = stdout.strip()
    if not text:
        return {}, "empty-stdout"
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            return {}, "stdout-json-root-not-object"
        return value, None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}, "stdout-does-not-contain-json-object"
        try:
            value = json.loads(text[start : end + 1])
            if not isinstance(value, dict):
                return {}, "stdout-json-root-not-object"
            return value, None
        except json.JSONDecodeError as exc:
            return {}, f"stdout-json-parse-failed:{exc.msg}"


def run_command_envelope(
    *,
    key: str,
    label: str,
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    allowed_exit_codes: set[int],
) -> dict[str, Any]:
    started = time.monotonic()
    started_utc = utc_iso()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(1, timeout_seconds),
            check=False,
        )
        duration = time.monotonic() - started
        parsed, parse_error = parse_json_stdout(completed.stdout)
        return {
            "key": key,
            "label": label,
            "command": command,
            "cwd": str(cwd.resolve()),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(duration, 3),
            "exitCode": completed.returncode,
            "allowedExitCode": completed.returncode in allowed_exit_codes,
            "ok": completed.returncode in allowed_exit_codes and parse_error is None,
            "stdoutPreview": preview(completed.stdout),
            "stderrPreview": preview(completed.stderr),
            "jsonParseError": parse_error,
            "json": parsed,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        return {
            "key": key,
            "label": label,
            "command": command,
            "cwd": str(cwd.resolve()),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(duration, 3),
            "exitCode": None,
            "allowedExitCode": False,
            "ok": False,
            "stdoutPreview": preview(exc.stdout or ""),
            "stderrPreview": preview(exc.stderr or ""),
            "jsonParseError": "timeout",
            "json": {},
            "error": {"type": "TimeoutExpired", "message": str(exc), "timeoutSeconds": timeout_seconds},
        }
    except Exception as exc:  # noqa: BLE001 - supervisor must report child launch failures.
        duration = time.monotonic() - started
        return {
            "key": key,
            "label": label,
            "command": command,
            "cwd": str(cwd.resolve()),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(duration, 3),
            "exitCode": None,
            "allowedExitCode": False,
            "ok": False,
            "stdoutPreview": "",
            "stderrPreview": "",
            "jsonParseError": "launch-failed",
            "json": {},
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def envelope_by_key(envelopes: list[dict[str, Any]], key: str) -> dict[str, Any]:
    for envelope in envelopes:
        if envelope.get("key") == key:
            return envelope
    return {"key": key, "ok": False, "json": {}, "jsonParseError": "missing-envelope"}


def child_json(envelopes: list[dict[str, Any]], key: str) -> dict[str, Any]:
    value = envelope_by_key(envelopes, key).get("json")
    return value if isinstance(value, dict) else {}


def list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def append_prefixed(target: list[str], prefix: str, values: Any) -> None:
    for value in list_strings(values):
        item = f"{prefix}:{value}"
        if item not in target:
            target.append(item)


def extract_artifact(document: dict[str, Any], key: str) -> Any:
    artifacts = document.get("artifacts") if isinstance(document.get("artifacts"), dict) else {}
    return artifacts.get(key)


def expected_approval_token(readiness: dict[str, Any], contract: dict[str, Any]) -> str | None:
    if isinstance(contract.get("expectedApprovalToken"), str):
        return contract["expectedApprovalToken"]
    automation = readiness.get("automationReadiness") if isinstance(readiness.get("automationReadiness"), dict) else {}
    token = automation.get("expectedApprovalToken")
    return token if isinstance(token, str) else None


def build_supervisor_summary(
    *,
    repo_root: Path,
    output_root: Path,
    target_character: str,
    envelopes: list[dict[str, Any]],
    approval_token_provided: bool,
) -> dict[str, Any]:
    data_blockers: list[str] = []
    execution_blockers: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, str]] = []

    for envelope in envelopes:
        if not envelope.get("allowedExitCode"):
            errors.append(
                {
                    "type": "ChildExitCode",
                    "message": f"{envelope.get('key')} exited with {envelope.get('exitCode')}",
                    "stage": str(envelope.get("key")),
                }
            )
        if envelope.get("jsonParseError"):
            errors.append(
                {
                    "type": "ChildJsonParse",
                    "message": str(envelope.get("jsonParseError")),
                    "stage": str(envelope.get("key")),
                }
            )
        if envelope.get("error"):
            error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
            errors.append(
                {
                    "type": str(error.get("type") or "ChildError"),
                    "message": str(error.get("message") or ""),
                    "stage": str(envelope.get("key")),
                }
            )

    crash_watch = child_json(envelopes, "crash-watch")
    screen_state = child_json(envelopes, "screen-state")
    readiness = child_json(envelopes, "readiness-packet")
    contract = child_json(envelopes, "executor-contract")
    status_packet = child_json(envelopes, "workflow-status")

    watch_status = crash_watch.get("watchStatus")
    if crash_watch.get("status") != "watch-ready":
        data_blockers.append(f"crash-watch-not-ready:{watch_status or crash_watch.get('status')}")
        append_prefixed(data_blockers, "crash-watch", crash_watch.get("dataBlockers"))
        append_prefixed(data_blockers, "crash-watch", crash_watch.get("watchBlockers"))

    screen_status = screen_state.get("status")
    if screen_status != "classified-character-select":
        data_blockers.append(f"screen-state-not-character-select:{screen_status}")
        append_prefixed(data_blockers, "screen-state", screen_state.get("blockers"))

    readiness_status = readiness.get("status")
    if readiness_status != "packet-ready":
        data_blockers.append(f"readiness-packet-not-ready:{readiness_status}")
        append_prefixed(data_blockers, "readiness", readiness.get("dataBlockers"))

    contract_status = contract.get("status")
    if contract_status != "ready-for-executor":
        execution_blockers.append(f"executor-contract-not-ready:{contract_status}")
        append_prefixed(execution_blockers, "executor-contract", contract.get("blockers"))

    append_prefixed(warnings, "crash-watch", crash_watch.get("warnings"))
    append_prefixed(warnings, "screen-state", screen_state.get("warnings"))
    append_prefixed(warnings, "readiness", readiness.get("warnings"))
    append_prefixed(warnings, "executor-contract", contract.get("warnings"))

    movement_gate = status_packet.get("movementGate") if isinstance(status_packet.get("movementGate"), dict) else {}
    if movement_gate.get("allowed") is True:
        warnings.append("workflow-status-movement-gate-unexpectedly-allowed")
    live_target = status_packet.get("liveTarget") if isinstance(status_packet.get("liveTarget"), dict) else {}

    approval_required = contract_status != "ready-for-executor"
    approval_missing_or_mismatch = any("approval-token" in item for item in execution_blockers)
    if errors:
        supervisor_status = "failed"
    elif data_blockers:
        supervisor_status = "blocked"
    elif not approval_token_provided and approval_missing_or_mismatch:
        supervisor_status = "blocked-approval-required"
    elif data_blockers or execution_blockers:
        supervisor_status = "blocked"
    else:
        supervisor_status = "ready-for-approved-executor"

    automation = readiness.get("automationReadiness") if isinstance(readiness.get("automationReadiness"), dict) else {}
    selection = readiness.get("selection") if isinstance(readiness.get("selection"), dict) else {}
    play = readiness.get("playButton") if isinstance(readiness.get("playButton"), dict) else {}
    crash_resume = (
        crash_watch.get("resumeDecision")
        if isinstance(crash_watch.get("resumeDecision"), dict)
        else {}
    )
    summary_json = output_root / "character-login-supervisor-summary.json"
    summary_markdown = output_root / "character-login-supervisor.md"
    command_envelopes = output_root / "character-login-supervisor-command-envelopes.json"

    decision = {
        "canObserveSameEpoch": watch_status == "target-present-same-epoch",
        "canPlanCharacterLogin": automation.get("canPlanCharacterLogin") is True
        and screen_status == "classified-character-select",
        "canExecuteLiveActionsNow": False,
        "mayClickPlayInThisSupervisor": False,
        "futureExecutorMayClickPlay": contract_status == "ready-for-executor",
        "approvalTokenProvided": approval_token_provided,
        "expectedApprovalToken": expected_approval_token(readiness, contract),
        "approvalRequired": approval_required,
        "postWorldProofRequired": True,
        "movementAllowed": False,
        "resumeAtState": crash_resume.get("resumeAtState"),
        "recommendedAction": recommended_action(
            supervisor_status=supervisor_status,
            data_blockers=data_blockers,
            execution_blockers=execution_blockers,
            crash_resume=crash_resume,
        ),
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": SUPERVISOR_KIND,
        "status": supervisor_status,
        "generatedAtUtc": utc_iso(),
        "targetCharacter": target_character,
        "dataBlockers": data_blockers,
        "executionBlockers": execution_blockers,
        "warnings": warnings,
        "errors": errors,
        "childStatuses": {
            "crashWatch": crash_watch.get("status"),
            "watchStatus": watch_status,
            "screenState": screen_status,
            "screenClassification": screen_state.get("classification"),
            "readinessPacket": readiness_status,
            "executorContract": contract_status,
            "workflowStatus": status_packet.get("status"),
        },
        "target": readiness.get("target") or crash_watch.get("expectedTarget"),
        "selection": selection,
        "playButton": play,
        "liveTarget": live_target,
        "movementGate": movement_gate,
        "supervisorDecision": decision,
        "futureMcpActionManifest": build_future_mcp_action_manifest(
            target=readiness.get("target") or crash_watch.get("expectedTarget") or {},
            selection=selection,
            play_button=play,
            decision=decision,
            data_blockers=data_blockers,
            execution_blockers=execution_blockers,
        ),
        "resumePolicy": {
            "onCrashOrRelaunch": "rerun crash-watch; if PID/HWND changed, discard old approval token and recapture character-select environment",
            "onSameEpoch": "rerun readiness packet immediately before any future approved click",
            "afterPlayClick": "wait for world load, rediscover exact PID/HWND, collect fresh API/runtime coordinate truth, and run same-target ProofOnly",
            "neverReuseAsCurrentTruth": [
                "old absolute memory addresses",
                "old PID/HWND-specific proof pointers",
                "old screenshots without geometry revalidation",
                "old approval tokens",
                "SavedVariables snapshots",
            ],
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
        "childArtifacts": {
            "crashWatchSummary": extract_artifact(crash_watch, "summaryJson"),
            "screenStateSummary": extract_artifact(screen_state, "summaryJson"),
            "readinessPacketSummary": extract_artifact(readiness, "summaryJson"),
            "executorContractSummary": extract_artifact(contract, "summaryJson"),
            "workflowStatusArtifacts": status_packet.get("artifacts"),
        },
        "artifacts": {
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_markdown.resolve()),
            "commandEnvelopes": str(command_envelopes.resolve()),
        },
    }


def recommended_action(
    *,
    supervisor_status: str,
    data_blockers: list[str],
    execution_blockers: list[str],
    crash_resume: dict[str, Any],
) -> str:
    if supervisor_status == "ready-for-approved-executor":
        return "A future executor may proceed only if it revalidates target/screenshot and still has current explicit approval; this supervisor itself does not click."
    if data_blockers:
        if any("crash-watch" in item for item in data_blockers):
            return str(crash_resume.get("recommendedAction") or "Resolve crash/relogin target drift, then rerun the supervisor.")
        return "Refresh or repair the missing/mismatched readiness artifacts, then rerun the supervisor."
    if execution_blockers:
        return "World-entry execution remains blocked. Provide explicit current-run approval only if you want a future one-click executor to enter the world."
    return "Review supervisor output before adding any executor path."


def build_future_mcp_action_manifest(
    *,
    target: Any,
    selection: dict[str, Any],
    play_button: dict[str, Any],
    decision: dict[str, Any],
    data_blockers: list[str],
    execution_blockers: list[str],
) -> dict[str, Any]:
    target_obj = target if isinstance(target, dict) else {}
    approval_token = decision.get("expectedApprovalToken")
    click_point = play_button.get("clickPoint") if isinstance(play_button.get("clickPoint"), list) else None
    bbox = play_button.get("bbox") if isinstance(play_button.get("bbox"), list) else None
    manifest_blockers: list[str] = []
    if data_blockers:
        manifest_blockers.append("supervisor-data-blockers-present")
    if execution_blockers:
        manifest_blockers.append("supervisor-execution-blockers-present")
    if not decision.get("canObserveSameEpoch"):
        manifest_blockers.append("same-target-epoch-not-observed")
    if not decision.get("canPlanCharacterLogin"):
        manifest_blockers.append("character-login-not-plannable")
    if not click_point:
        manifest_blockers.append("missing-play-click-point")
    if not bbox:
        manifest_blockers.append("missing-play-bbox")
    if not approval_token:
        manifest_blockers.append("missing-approval-token-contract")

    return {
        "schemaVersion": 1,
        "kind": "riftreader-future-mcp-character-login-action-manifest",
        "status": "blocked" if manifest_blockers else "ready-for-future-approved-executor",
        "blockers": manifest_blockers,
        "neverExecuteBySupervisor": True,
        "approval": {
            "required": True,
            "token": approval_token,
            "mustBeProvidedInSameRunAsClick": True,
            "oldTokensInvalidAfterCrashOrRelaunch": True,
        },
        "target": {
            "processName": target_obj.get("processName") or "rift_x64",
            "processId": target_obj.get("processId"),
            "windowHandle": target_obj.get("windowHandle") or target_obj.get("targetWindowHandle"),
            "windowTitle": target_obj.get("windowTitle") or target_obj.get("title") or "RIFT",
            "expectedClientSize": {"width": 640, "height": 360},
        },
        "selection": {
            "targetCharacter": selection.get("targetCharacter"),
            "selectedCharacter": selection.get("selectedCharacter"),
            "selectedAlready": selection.get("selectedAlready") is True,
            "targetSlot": selection.get("targetSlot"),
        },
        "playButton": {
            "clickPoint": click_point,
            "bbox": bbox,
            "coordinateSpace": "client",
            "maxClicks": 1,
        },
        "mcpToolSequence": [
            {
                "step": "bind-exact-target",
                "tool": "mcp__rift_game__.find_game_window",
                "arguments": {
                    "processId": target_obj.get("processId"),
                    "processName": target_obj.get("processName") or "rift_x64",
                    "windowHandle": target_obj.get("windowHandle") or target_obj.get("targetWindowHandle"),
                    "titleContains": "RIFT",
                },
                "approvalRequired": False,
                "stopOnFailure": True,
                "expected": "bound exact same PID/HWND",
            },
            {
                "step": "capture-before-focus",
                "tool": "mcp__rift_game__.capture_game_window",
                "arguments": {},
                "approvalRequired": False,
                "stopOnFailure": True,
                "expected": "fresh 640x360 character-select screenshot with target character selected",
            },
            {
                "step": "focus-for-click",
                "tool": "mcp__rift_game__.focus_game_window",
                "arguments": {},
                "approvalRequired": True,
                "stopOnFailure": True,
                "expected": "exact bound window foreground before click_client",
            },
            {
                "step": "click-play-once",
                "tool": "mcp__rift_game__.click_client",
                "arguments": {"x": click_point[0], "y": click_point[1]} if click_point else {},
                "approvalRequired": True,
                "requiredApprovalToken": approval_token,
                "stopOnFailure": True,
                "expected": "one Play click only; no repeated blind clicks",
            },
            {
                "step": "wait-for-world-transition",
                "tool": "mcp__rift_game__.wait_for_frame_change",
                "arguments": {
                    "timeoutMilliseconds": 60000,
                    "pollIntervalMilliseconds": 1000,
                    "changeThresholdPercent": 2.0,
                },
                "approvalRequired": False,
                "stopOnFailure": True,
                "expected": "visible transition away from the pre-click character-select baseline; if changed=false, stop without retry clicks",
            },
            {
                "step": "capture-after-transition",
                "tool": "mcp__rift_game__.capture_game_window",
                "arguments": {},
                "approvalRequired": False,
                "stopOnFailure": True,
                "expected": "post-transition screenshot for world-load or blocker classification",
            },
            {
                "step": "post-world-proof",
                "tool": "repo-proofonly-workflow",
                "arguments": {
                    "required": [
                        "rediscover exact PID/HWND/process start",
                        "collect fresh API/runtime coordinate truth",
                        "run same-target ProofOnly",
                    ]
                },
                "approvalRequired": False,
                "stopOnFailure": True,
                "expected": "movement remains blocked unless ProofOnly passes",
            },
        ],
        "failClosedOn": [
            "PID/HWND mismatch",
            "client size not 640x360",
            "target character not selected",
            "missing or mismatched approval token",
            "window not foreground before click_client",
            "Play click point outside measured bbox",
            "wait_for_frame_change reports changed=false",
            "world-load timeout",
            "post-world ProofOnly missing, stale, or failed",
        ],
        "safety": {
            "movementAllowedBeforePostWorldProof": False,
            "sendKeysAllowed": False,
            "mouseClickAllowedOnlyForPlayWithApproval": True,
            "maxPlayClicks": 1,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "providerWrites": False,
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    decision = summary.get("supervisorDecision") if isinstance(summary.get("supervisorDecision"), dict) else {}
    target = summary.get("target") if isinstance(summary.get("target"), dict) else {}
    selection = summary.get("selection") if isinstance(summary.get("selection"), dict) else {}
    play = summary.get("playButton") if isinstance(summary.get("playButton"), dict) else {}
    child = summary.get("childStatuses") if isinstance(summary.get("childStatuses"), dict) else {}
    future_manifest = summary.get("futureMcpActionManifest")
    future_manifest_status = future_manifest.get("status") if isinstance(future_manifest, dict) else None
    lines = [
        "# Character login supervisor",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target character: `{summary.get('targetCharacter')}`",
        f"- Target: PID `{target.get('processId')}`, HWND `{target.get('windowHandle')}`",
        f"- Selected: `{selection.get('selectedCharacter')}`",
        f"- Play click: `{play.get('clickPoint')}`",
        f"- Future executor may click Play: `{str(decision.get('futureExecutorMayClickPlay')).lower()}`",
        f"- Future MCP manifest: `{future_manifest_status}`",
        f"- This supervisor may click Play: `{str(decision.get('mayClickPlayInThisSupervisor')).lower()}`",
        f"- Movement allowed: `{str(decision.get('movementAllowed')).lower()}`",
        "",
        "## Child checks",
        "",
        "| Check | Status |",
        "|---|---|",
        f"| Crash watch | `{child.get('crashWatch')}` / `{child.get('watchStatus')}` |",
        f"| Screen state | `{child.get('screenState')}` / `{child.get('screenClassification')}` |",
        f"| Readiness packet | `{child.get('readinessPacket')}` |",
        f"| Executor contract | `{child.get('executorContract')}` |",
        f"| Workflow status | `{child.get('workflowStatus')}` |",
        "",
        "## Data blockers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in (summary.get("dataBlockers") or [])] or ["- none"])
    lines.extend(["", "## Execution blockers", ""])
    lines.extend([f"- `{item}`" for item in (summary.get("executionBlockers") or [])] or ["- none"])
    lines.extend(["", "## Recommendation", "", str(decision.get("recommendedAction") or ""), ""])
    lines.extend(
        [
            "## Safety",
            "",
            "No client launch, click, key input, world entry, movement, Cheat Engine, x64dbg attach, provider write, or Git mutation is performed by this supervisor.",
            "",
        ]
    )
    return "\n".join(lines)


def build_child_commands(
    *,
    repo_root: Path,
    output_root: Path,
    target_character: str,
    samples: int,
    interval_seconds: float,
    approval_token: str | None,
) -> list[tuple[str, str, list[str], set[int]]]:
    python = sys.executable
    scripts = repo_root / "scripts"
    tools = repo_root / "tools" / "riftreader_workflow"
    commands: list[tuple[str, str, list[str], set[int]]] = [
        (
            "crash-watch",
            "Character login crash/relogin watch",
            [
                python,
                str(scripts / "character_login_crash_watch.py"),
                "--samples",
                str(max(1, samples)),
                "--interval-seconds",
                str(max(0.0, interval_seconds)),
                "--output-root",
                str(output_root / "crash-watch"),
                "--json",
            ],
            {0, 2},
        ),
        (
            "screen-state",
            "Character login screenshot state classifier",
            [
                python,
                str(scripts / "character_login_screen_state.py"),
                "--expect-character-select",
                "--output-root",
                str(output_root / "screen-state"),
                "--json",
            ],
            {0, 2},
        ),
        (
            "executor-contract",
            "Character login executor contract",
            [
                python,
                str(scripts / "character_login_executor_contract.py"),
                "--output-root",
                str(output_root / "executor-contract"),
                "--json",
            ],
            {0, 2},
        ),
        (
            "readiness-packet",
            "Character login readiness packet",
            [
                python,
                str(scripts / "character_login_readiness_packet.py"),
                "--target-character",
                target_character,
                "--output-root",
                str(output_root / "readiness-packet"),
                "--json",
            ],
            {0, 2},
        ),
        (
            "workflow-status",
            "RiftReader compact workflow status",
            [
                python,
                str(tools / "status_packet.py"),
                "--repo-root",
                str(repo_root),
                "--compact-json",
            ],
            {0, 1, 2},
        ),
    ]
    if approval_token:
        contract_command = commands[1][2]
        contract_command.extend(["--approval-token", approval_token])
    return commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run no-input character-login supervision checks and emit one resumable packet."
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--target-character", default=DEFAULT_TARGET_CHARACTER)
    parser.add_argument("--approval-token")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--child-timeout-seconds", type=int, default=45)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-supervisor" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)

    envelopes: list[dict[str, Any]] = []
    for key, label, command, allowed_exit_codes in build_child_commands(
        repo_root=repo_root,
        output_root=output_root,
        target_character=args.target_character,
        samples=args.samples,
        interval_seconds=args.interval_seconds,
        approval_token=args.approval_token,
    ):
        envelopes.append(
            run_command_envelope(
                key=key,
                label=label,
                command=command,
                cwd=repo_root,
                timeout_seconds=args.child_timeout_seconds,
                allowed_exit_codes=allowed_exit_codes,
            )
        )

    summary = build_supervisor_summary(
        repo_root=repo_root,
        output_root=output_root,
        target_character=args.target_character,
        envelopes=envelopes,
        approval_token_provided=bool(str(args.approval_token or "").strip()),
    )
    command_envelopes_path = output_root / "character-login-supervisor-command-envelopes.json"
    summary_json = output_root / "character-login-supervisor-summary.json"
    summary_markdown = output_root / "character-login-supervisor.md"
    future_manifest_path = output_root / "future-mcp-action-manifest.json"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    summary["artifacts"]["commandEnvelopes"] = str(command_envelopes_path.resolve())
    summary["artifacts"]["futureMcpActionManifest"] = str(future_manifest_path.resolve())
    write_json(command_envelopes_path, envelopes)
    write_json(future_manifest_path, summary["futureMcpActionManifest"])
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-supervisor" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))

    if args.json:
        print(json.dumps(summary, indent=2))

    if summary.get("status") == "ready-for-approved-executor":
        return 0
    if str(summary.get("status", "")).startswith("blocked"):
        return 2
    return 1
