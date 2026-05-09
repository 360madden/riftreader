from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .commands import (
    JsonCommandResult,
    command_envelope,
    ps_quote,
    pwsh_encoded_command,
    pwsh_file_command,
    run_json_command,
)


VISUAL_GATE_PASSED = "passed-visual-baseline"
VISUAL_GATE_BLOCKED_TARGET = "blocked-target-resolution"
VISUAL_GATE_BLOCKED_CAPTURE = "blocked-visual-baseline"


@dataclass(frozen=True)
class VisualGateOptions:
    repo_root: Path
    process_id: int | None = None
    window_handle: str | None = None
    process_name: str = "rift_x64"
    title_contains: str = "RIFT"
    output_dir: Path | None = None
    focus_first: bool = True
    full: bool = False
    timeout_seconds: int = 45


def run_visual_gate(options: VisualGateOptions) -> dict[str, Any]:
    repo_root = options.repo_root.resolve()
    output_dir = (options.output_dir or _default_output_dir(repo_root, options.process_id)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    attempted_at = _utc_now()
    window_tools = repo_root / "tools" / "rift-game-mcp" / "helpers" / "window-tools.ps1"
    attempts: list[dict[str, Any]] = []
    blockers: list[str] = []

    inspect_result = _run_window_tool(
        window_tools,
        options,
        operation="inspect",
        label="inspect-window",
        cwd=repo_root,
        timeout_seconds=options.timeout_seconds,
    )
    inspect_envelope = _command_envelope(inspect_result)
    attempts.append(inspect_envelope)
    window = inspect_result.json_data if isinstance(inspect_result.json_data, dict) else None

    if not inspect_result.ok:
        blockers.append("target-window-not-resolved")

    focus_envelope: dict[str, Any] | None = None
    if inspect_result.ok and options.focus_first:
        focus_result = _run_window_tool(
            window_tools,
            options,
            operation="focus",
            label="focus-window",
            cwd=repo_root,
            timeout_seconds=options.timeout_seconds,
        )
        focus_envelope = _command_envelope(focus_result)
        attempts.append(focus_envelope)
        if isinstance(focus_result.json_data, dict):
            window = focus_result.json_data
        if focus_result.exit_code != 0:
            blockers.append("focus-window-failed")
        elif not _focus_envelope_confirms_foreground(focus_envelope):
            blockers.append("focus-window-not-foreground")

    if inspect_result.ok:
        copy_sanity = _run_copyfromscreen_sanity(
            options=options,
            output_dir=output_dir,
            window=window,
            cwd=repo_root,
            timeout_seconds=options.timeout_seconds,
        )
        attempts.append(_command_envelope(copy_sanity))

        helper_capture = _run_window_tool(
            window_tools,
            options,
            operation="capture",
            label="rift-mcp-copyfromscreen-capture",
            cwd=repo_root,
            timeout_seconds=options.timeout_seconds,
            extra_args=["-OutputPath", str(output_dir / "rift-mcp-copyfromscreen-capture.png")],
        )
        attempts.append(_command_envelope(helper_capture))

        printwindow = _run_printwindow(
            repo_root=repo_root,
            options=options,
            output_dir=output_dir,
            timeout_seconds=options.timeout_seconds,
        )
        attempts.append(_command_envelope(printwindow))

        wgc_window = _run_wgc(
            repo_root=repo_root,
            options=options,
            output_dir=output_dir,
            label="wgc-window",
            extra_args=[],
            timeout_seconds=options.timeout_seconds,
        )
        attempts.append(_command_envelope(wgc_window))

        if options.full:
            wgc_monitor = _run_wgc(
                repo_root=repo_root,
                options=options,
                output_dir=output_dir,
                label="wgc-monitor",
                extra_args=["-CaptureMonitor"],
                timeout_seconds=options.timeout_seconds,
            )
            attempts.append(_command_envelope(wgc_monitor))

            dxgi = _run_wgc(
                repo_root=repo_root,
                options=options,
                output_dir=output_dir,
                label="dxgi-desktop-duplication",
                extra_args=["-DesktopDuplication"],
                timeout_seconds=options.timeout_seconds,
            )
            attempts.append(_command_envelope(dxgi))

    verdict = build_visual_gate_verdict(
        target_resolved=inspect_result.ok,
        focus_ok=(not options.focus_first) or _focus_envelope_confirms_foreground(focus_envelope),
        attempts=attempts,
        existing_blockers=blockers,
    )

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "status": verdict["status"],
        "ok": verdict["readyForLiveInput"],
        "readyForLiveInput": verdict["readyForLiveInput"],
        "movementSent": False,
        "inputSent": False,
        "noCheatEngine": True,
        "savedVariablesUsedAsLiveTruth": False,
        "attemptedAtUtc": attempted_at,
        "completedAtUtc": _utc_now(),
        "repoRoot": str(repo_root),
        "outputDir": str(output_dir),
        "processId": options.process_id,
        "targetWindowHandle": options.window_handle,
        "processName": options.process_name,
        "titleContains": options.title_contains,
        "focusFirst": options.focus_first,
        "focusConfirmedForeground": (not options.focus_first) or _focus_envelope_confirms_foreground(focus_envelope),
        "full": options.full,
        "window": window,
        "usableCaptureMethod": verdict["usableCaptureMethod"],
        "blockers": verdict["blockers"],
        "captureFailureClassifications": verdict["captureFailureClassifications"],
        "recoveryRecommendations": build_visual_gate_recovery_recommendations(verdict["blockers"]),
        "cautions": verdict["cautions"],
        "attempts": attempts,
    }
    summary["summaryPath"] = str(output_dir / "visual-gate-status.json")

    summary_path = Path(summary["summaryPath"])
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_markdown_summary(summary, output_dir / "visual-gate-status.md")
    return summary


def build_visual_gate_verdict(
    *,
    target_resolved: bool,
    focus_ok: bool,
    attempts: list[dict[str, Any]],
    existing_blockers: list[str] | None = None,
) -> dict[str, Any]:
    blockers = list(existing_blockers or [])
    cautions: list[str] = []

    usable_capture = next((attempt for attempt in attempts if _attempt_has_usable_capture(attempt)), None)
    if target_resolved and focus_ok and usable_capture is not None:
        return {
            "status": VISUAL_GATE_PASSED,
            "readyForLiveInput": True,
            "usableCaptureMethod": usable_capture.get("label"),
            "blockers": blockers,
            "captureFailureClassifications": [],
            "cautions": _dedupe(cautions),
        }

    if not target_resolved and "target-window-not-resolved" not in blockers:
        blockers.append("target-window-not-resolved")
    if not focus_ok and not _has_focus_blocker(blockers):
        blockers.append("focus-window-failed")
    capture_failure_classifications: list[str] = []
    if target_resolved and usable_capture is None:
        capture_failure_classifications = _classify_capture_blockers(attempts)
        blockers.extend(capture_failure_classifications)

    return {
        "status": VISUAL_GATE_BLOCKED_TARGET if not target_resolved else VISUAL_GATE_BLOCKED_CAPTURE,
        "readyForLiveInput": False,
        "usableCaptureMethod": None,
        "blockers": _dedupe(blockers),
        "captureFailureClassifications": _dedupe(capture_failure_classifications),
        "cautions": _dedupe(cautions),
    }


def build_visual_gate_recovery_recommendations(blockers: list[str]) -> list[dict[str, str]]:
    blocker_set = set(blockers)
    recommendations: list[dict[str, str]] = []

    def add(identifier: str, action: str, why: str) -> None:
        if any(item["id"] == identifier for item in recommendations):
            return
        recommendations.append({"id": identifier, "action": action, "why": why})

    if "target-window-not-resolved" in blocker_set:
        add(
            "resolve-target-window",
            "Re-run the gate with the exact live Rift PID/HWND after confirming the client window still exists.",
            "Movement input must not be sent unless the gate can bind the intended RIFT window.",
        )

    if blocker_set & {"focus-window-failed", "focus-window-not-foreground"}:
        add(
            "restore-focus",
            "Restore/unminimize the Rift window and foreground it, then rerun the visual gate.",
            "The live-input path requires a known focused/targetable window before any capture or movement proof.",
        )

    if blocker_set & {"desktop-capture-access-denied", "desktop-copyfromscreen-invalid-handle"}:
        add(
            "restore-interactive-desktop-capture",
            "Unlock/reconnect the interactive desktop or restart the capture host/session, then rerun the full visual gate.",
            "CopyFromScreen/WGC/DXGI failures mean the automation cannot prove the current window view safely.",
        )

    if "capture-methods-return-black-or-flat-content" in blocker_set:
        add(
            "restore-visible-window-content",
            "Make Rift visible and unobscured, avoid minimized/off-screen states, then rerun the full visual gate.",
            "Black or flat captures are not a usable visual baseline for live input verification.",
        )

    if "no-usable-visual-baseline-capture" in blocker_set:
        add(
            "inspect-capture-attempts",
            "Inspect the visual-gate attempts and rerun with --full before changing live-input behavior.",
            "The gate did not identify a usable screenshot method or a more specific capture failure.",
        )

    if blocker_set:
        add(
            "keep-live-input-blocked",
            "Do not send live input until a new visual gate returns readyForLiveInput=true.",
            "The visual baseline is the final operator safety check before movement or yaw stimulus.",
        )

    return recommendations


def _has_focus_blocker(blockers: list[str]) -> bool:
    return any(blocker in {"focus-window-failed", "focus-window-not-foreground"} for blocker in blockers)


def _command_envelope(result: JsonCommandResult) -> dict[str, Any]:
    envelope = command_envelope(result)
    args = list(envelope.get("args") or [])
    for index, value in enumerate(args[:-1]):
        if value == "-EncodedCommand":
            args[index + 1] = "<encoded-copyfromscreen-sanity-script>"
    envelope["args"] = args
    return envelope


def _focus_envelope_confirms_foreground(envelope: dict[str, Any] | None) -> bool:
    if envelope is None or envelope.get("exitCode") != 0:
        return False

    data = envelope.get("json")
    return isinstance(data, dict) and data.get("isForeground") is True


def _attempt_has_usable_capture(attempt: dict[str, Any]) -> bool:
    if attempt.get("exitCode") != 0:
        return False

    data = attempt.get("json")
    if not isinstance(data, dict):
        return False

    if data.get("usable") is True or data.get("Usable") is True:
        return True

    if data.get("screenshotPath") and isinstance(data.get("imageSize"), dict):
        return True

    attempts = data.get("attempts")
    if isinstance(attempts, list):
        return any(isinstance(item, dict) and item.get("ok") is True for item in attempts)

    return False


def _classify_capture_blockers(attempts: list[dict[str, Any]]) -> list[str]:
    haystack = "\n".join(
        str(part)
        for attempt in attempts
        for part in (
            attempt.get("label"),
            attempt.get("stdout"),
            attempt.get("stderr"),
            attempt.get("jsonParseError"),
            json.dumps(attempt.get("json"), default=str) if attempt.get("json") is not None else "",
        )
        if part
    ).lower()

    blockers: list[str] = []
    if "e_accessdenied" in haystack or "access is denied" in haystack:
        blockers.append("desktop-capture-access-denied")
    if "copyfromscreen" in haystack and "handle is invalid" in haystack:
        blockers.append("desktop-copyfromscreen-invalid-handle")
    if "black" in haystack or "flat" in haystack or "transparent" in haystack:
        blockers.append("capture-methods-return-black-or-flat-content")
    if not blockers:
        blockers.append("no-usable-visual-baseline-capture")
    return _dedupe(blockers)


def _classify_capture_blocker(attempts: list[dict[str, Any]]) -> str:
    return _classify_capture_blockers(attempts)[0]


def _run_window_tool(
    script: Path,
    options: VisualGateOptions,
    *,
    operation: str,
    label: str,
    cwd: Path,
    timeout_seconds: int,
    extra_args: list[str] | None = None,
) -> JsonCommandResult:
    args = ["-Operation", operation, *_selector_args(options), *(extra_args or [])]
    return run_json_command(
        pwsh_file_command(script, args),
        cwd=cwd,
        label=label,
        timeout_seconds=timeout_seconds,
    )


def _run_printwindow(
    *,
    repo_root: Path,
    options: VisualGateOptions,
    output_dir: Path,
    timeout_seconds: int,
) -> JsonCommandResult:
    script = repo_root / "scripts" / "capture-rift-window-printwindow.ps1"
    args = [
        *_process_args(options),
        "-OutputPath",
        str(output_dir / "printwindow-capture.png"),
        "-RequireUsable",
        "-Json",
    ]
    return run_json_command(
        pwsh_file_command(script, args),
        cwd=repo_root,
        label="printwindow-capture",
        timeout_seconds=timeout_seconds,
    )


def _run_wgc(
    *,
    repo_root: Path,
    options: VisualGateOptions,
    output_dir: Path,
    label: str,
    extra_args: list[str],
    timeout_seconds: int,
) -> JsonCommandResult:
    script = repo_root / "scripts" / "capture-rift-window-wgc.ps1"
    args = [
        *_process_args(options),
        "-OutputPath",
        str(output_dir / f"{label}.png"),
        "-Attempts",
        "1",
        "-TimeoutMs",
        "2500",
        "-RequireUsable",
        "-Json",
        *extra_args,
    ]
    return run_json_command(
        pwsh_file_command(script, args),
        cwd=repo_root,
        label=label,
        timeout_seconds=timeout_seconds,
    )


def _run_copyfromscreen_sanity(
    *,
    options: VisualGateOptions,
    output_dir: Path,
    window: dict[str, Any] | None,
    cwd: Path,
    timeout_seconds: int,
) -> JsonCommandResult:
    client_rect = window.get("clientRect") if isinstance(window, dict) else None
    client_attempt = ""
    if isinstance(client_rect, dict):
        try:
            left = int(client_rect["left"])
            top = int(client_rect["top"])
            width = max(1, min(64, int(client_rect["width"])))
            height = max(1, min(64, int(client_rect["height"])))
            client_path = output_dir / "copyfromscreen-client-sanity.png"
            client_attempt = (
                "$result.attempts += Try-Capture -Name 'client-sanity' "
                f"-X {left} -Y {top} -Width {width} -Height {height} -Path {ps_quote(client_path)}\n"
            )
        except (KeyError, TypeError, ValueError):
            client_attempt = ""

    desktop_path = output_dir / "copyfromscreen-desktop-sanity.png"
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
function Try-Capture {{
    param(
        [string]$Name,
        [int]$X,
        [int]$Y,
        [int]$Width,
        [int]$Height,
        [string]$Path
    )
    try {{
        $bitmap = New-Object System.Drawing.Bitmap $Width, $Height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {{
            $graphics.CopyFromScreen($X, $Y, 0, 0, [System.Drawing.Size]::new($Width, $Height))
            $directory = [System.IO.Path]::GetDirectoryName($Path)
            if (-not [string]::IsNullOrWhiteSpace($directory)) {{
                [System.IO.Directory]::CreateDirectory($directory) | Out-Null
            }}
            $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
            return [ordered]@{{ name=$Name; ok=$true; output=$Path; x=$X; y=$Y; width=$Width; height=$Height }}
        }}
        finally {{
            if ($null -ne $graphics) {{ $graphics.Dispose() }}
            if ($null -ne $bitmap) {{ $bitmap.Dispose() }}
        }}
    }}
    catch {{
        return [ordered]@{{
            name=$Name
            ok=$false
            output=$Path
            x=$X
            y=$Y
            width=$Width
            height=$Height
            error=$_.Exception.Message
            errorType=$_.Exception.GetType().FullName
        }}
    }}
}}
$result = [ordered]@{{
    attemptedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    attempts = @()
}}
$result.attempts += Try-Capture -Name 'desktop-sanity' -X 0 -Y 0 -Width 1 -Height 1 -Path {ps_quote(desktop_path)}
{client_attempt}
$result | ConvertTo-Json -Depth 6
"""
    return run_json_command(
        pwsh_encoded_command(script),
        cwd=cwd,
        label="copyfromscreen-sanity",
        timeout_seconds=timeout_seconds,
    )


def _selector_args(options: VisualGateOptions) -> list[str]:
    args: list[str] = []
    if options.window_handle:
        args += ["-WindowHandle", options.window_handle]
        if options.process_id is not None:
            args += ["-ExpectedProcessId", str(options.process_id)]
        if options.process_name:
            args += ["-ExpectedProcessName", options.process_name]
        if options.title_contains:
            args += ["-ExpectedTitleContains", options.title_contains]
        return args

    args += _process_args(options)
    if options.process_name:
        args += ["-ExpectedProcessName", options.process_name]
    if options.title_contains:
        args += ["-ExpectedTitleContains", options.title_contains]
    return args


def _process_args(options: VisualGateOptions) -> list[str]:
    args: list[str] = []
    if options.process_id is not None:
        args += ["-ProcessId", str(options.process_id)]
    elif options.process_name:
        args += ["-ProcessName", options.process_name]
    if options.title_contains:
        args += ["-TitleContains", options.title_contains]
    return args


def _default_output_dir(repo_root: Path, process_id: int | None) -> Path:
    pid_text = f"currentpid-{process_id}" if process_id is not None else "currenttarget"
    local_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"visual-gate-{pid_text}-{local_stamp}"


def _write_markdown_summary(summary: dict[str, Any], path: Path) -> None:
    rows = "\n".join(
        f"| `{attempt.get('label')}` | `{attempt.get('exitCode')}` | "
        f"`{_attempt_json_summary(attempt)}` |"
        for attempt in summary.get("attempts", [])
        if isinstance(attempt, dict)
    )
    recovery_rows = "\n".join(
        f"| `{item.get('id')}` | {item.get('action')} | {item.get('why')} |"
        for item in summary.get("recoveryRecommendations", [])
        if isinstance(item, dict)
    )
    recovery_section = ""
    if recovery_rows:
        recovery_section = f"""
## Recovery recommendations

| ID | Action | Why |
|---|---|---|
{recovery_rows}
"""
    body = f"""# Visual gate status

| Field | Value |
|---|---|
| Status | `{summary.get('status')}` |
| Ready for live input | `{summary.get('readyForLiveInput')}` |
| Focus confirmed foreground | `{summary.get('focusConfirmedForeground')}` |
| Target | PID `{summary.get('processId')}`, HWND `{summary.get('targetWindowHandle')}` |
| Usable capture method | `{summary.get('usableCaptureMethod')}` |
| Blockers | `{', '.join(summary.get('blockers') or [])}` |
| Capture failure classifications | `{', '.join(summary.get('captureFailureClassifications') or [])}` |
| Summary JSON | `{summary.get('summaryPath')}` |
{recovery_section}

## Attempts

| Attempt | Exit | Result |
|---|---:|---|
{rows}
"""
    path.write_text(body, encoding="utf-8")


def _attempt_json_summary(attempt: dict[str, Any]) -> str:
    data = attempt.get("json")
    if isinstance(data, dict):
        for key in ("Message", "message", "error", "ErrorType", "screenshotPath", "Output"):
            value = data.get(key)
            if value:
                return str(value).replace("\r", " ").replace("\n", " ")[:180]
        if "attempts" in data:
            return json.dumps(data["attempts"], default=str)[:180]
    stderr = str(attempt.get("stderr") or "").strip()
    if stderr:
        return stderr.replace("\r", " ").replace("\n", " ")[:180]
    stdout = str(attempt.get("stdout") or "").strip()
    if stdout:
        return stdout.replace("\r", " ").replace("\n", " ")[:180]
    return ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a no-input Rift visual-baseline gate before live movement.",
    )
    parser.add_argument("--pid", type=int, dest="process_id", help="Exact target Rift process id.")
    parser.add_argument("--hwnd", dest="window_handle", help="Exact target window handle, e.g. 0x5121A.")
    parser.add_argument("--process-name", default="rift_x64", help="Expected process name.")
    parser.add_argument("--title-contains", default="RIFT", help="Expected title substring.")
    parser.add_argument("--output-dir", type=Path, help="Directory for capture attempts and summary files.")
    parser.add_argument("--skip-focus", action="store_true", help="Do not call the focus preflight.")
    parser.add_argument("--full", action="store_true", help="Also run monitor WGC and DXGI Desktop Duplication.")
    parser.add_argument("--timeout-seconds", type=int, default=45, help="Per-command timeout.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON instead of a short text summary.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    summary = run_visual_gate(
        VisualGateOptions(
            repo_root=repo_root,
            process_id=args.process_id,
            window_handle=args.window_handle,
            process_name=args.process_name,
            title_contains=args.title_contains,
            output_dir=args.output_dir,
            focus_first=not args.skip_focus,
            full=args.full,
            timeout_seconds=args.timeout_seconds,
        )
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"{summary['status']}: readyForLiveInput={summary['readyForLiveInput']} "
            f"blockers={','.join(summary['blockers']) or 'none'}"
        )
        print(f"summaryPath={summary['summaryPath']}")

    return 0 if summary["readyForLiveInput"] else 2


if __name__ == "__main__":
    sys.exit(main())
