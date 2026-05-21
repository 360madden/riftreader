#!/usr/bin/env python3
"""Build and run adaptive OpenCode prompts for RiftReader workflow lanes.

This helper keeps the .cmd launchers dumb and makes the OpenCode prompt derive
from the current status packet before every run. It is intentionally no-input and
no-Git-mutation; generated prompts and run envelopes are written only under the
ignored .riftreader-local tree.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, preview_text, repo_rel, safety_flags, timestamped_output_dir, utc_iso
    from .decision_packet import build_decision_packet, compact_decision_packet
    from .status_packet import (
        build_status_packet,
        compact_summary,
        desired_opencode_model,
        desired_opencode_variant,
    )
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import (  # type: ignore[no-redef]
        find_repo_root,
        preview_text,
        repo_rel,
        safety_flags,
        timestamped_output_dir,
        utc_iso,
    )
    from riftreader_workflow.decision_packet import build_decision_packet, compact_decision_packet  # type: ignore[no-redef]
    from riftreader_workflow.status_packet import (  # type: ignore[no-redef]
        build_status_packet,
        compact_summary,
        desired_opencode_model,
        desired_opencode_variant,
    )


DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "opencode-prompts"
DEFAULT_RUN_OUTPUT_DIR = Path(".riftreader-local") / "opencode-runs"
SUPPORTED_LANES = {"sitrep", "live-observer", "package-review", "integration"}
LANE_RECOMMENDED_AGENTS: dict[str, str] = {
    "sitrep": "riftreader-readonly",
    "live-observer": "riftreader-live-observer",
    "package-review": "riftreader-applier",
    "integration": "riftreader-integration",
}
INTEGRATION_ALLOWED_EDIT_PATHS: tuple[str, ...] = (
    "tools/riftreader_workflow/opencode_bridge.py",
    "tools/riftreader_workflow/status_packet.py",
    "tools/riftreader_workflow/decision_packet.py",
    "scripts/riftreader-opencode-*.cmd",
    "scripts/riftreader-decision-packet.cmd",
    "scripts/test_opencode*.py",
    "scripts/test_decision_packet.py",
    "docs/workflow/opencode-non-codex-bridge.md",
    "docs/workflow/non-codex-desktop-chatgpt-workflow.md",
    ".opencode/opencode.example.jsonc",
)
INTEGRATION_GROUNDING_FILES: tuple[str, ...] = (
    "tools/riftreader_workflow/opencode_bridge.py",
    "tools/riftreader_workflow/status_packet.py",
    "tools/riftreader_workflow/decision_packet.py",
    "scripts/riftreader-decision-packet.cmd",
    "scripts/riftreader-opencode-prompt.cmd",
    "scripts/riftreader-opencode-integration.cmd",
    "scripts/riftreader-opencode-sitrep.cmd",
    "scripts/riftreader-opencode-live-observer.cmd",
    "scripts/riftreader-opencode-package-review.cmd",
    "scripts/test_opencode_bridge.py",
    "scripts/test_opencode_status_packet.py",
    "scripts/test_decision_packet.py",
    "docs/workflow/opencode-non-codex-bridge.md",
    "docs/workflow/non-codex-desktop-chatgpt-workflow.md",
    ".opencode/opencode.example.jsonc",
)
COMMON_FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "live-input",
    "movement",
    "game-click",
    "reloadui",
    "screenshot-hotkeys",
    "cheat-engine",
    "x64dbg",
    "proof-promotion",
    "provider-repo-write",
    "git-mutation",
    "package-apply-without-current-turn-approval",
)
INTEGRATION_HARD_STOP_CONDITIONS: tuple[str, ...] = (
    "no-further-useful-opencode-integration-improvements",
    "next-step-requires-live-input-or-proof-promotion",
    "next-step-requires-edit-outside-opencode-integration-scope",
    "next-step-requires-git-mutation",
    "same-failure-pattern-repeated-three-times",
    "missing-required-external-dependency-credential-provider-setting-or-user-decision",
    "validation-exposes-risk-that-should-not-be-fixed-autonomously",
)
READ_ONLY_HARD_STOP_CONDITIONS: tuple[str, ...] = (
    "tracked-edit-needed",
    "package-apply-needed",
    "live-input-or-proof-action-needed",
    "git-mutation-needed",
    "external-dependency-or-user-decision-needed",
)
INTEGRATION_TARGETED_VALIDATION: tuple[str, ...] = (
    r"python -m compileall tools\riftreader_workflow scripts\test_opencode_bridge.py scripts\test_opencode_status_packet.py",
    "python -m unittest scripts.test_opencode_bridge scripts.test_opencode_status_packet",
    "git --no-pager diff --check",
)


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: Any, default: str = "none") -> str:
    text = "" if value is None else str(value)
    return text if text.strip() else default


def selected_opencode_agent(explicit_agent: str | None = None) -> str | None:
    """Return the configured OpenCode agent override, if any."""

    raw = explicit_agent if explicit_agent is not None else os.environ.get("RIFTREADER_OPENCODE_AGENT", "")
    agent = raw.strip()
    return agent or None


def _quote_path(path: str) -> str:
    return '"' + path.replace('"', '\\"') + '"'


def _compact_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def lane_policy(lane: str) -> dict[str, Any]:
    """Return the machine-readable safety/edit policy for an OpenCode lane."""

    if lane not in SUPPORTED_LANES:
        raise ValueError(f"unsupported-lane:{lane}")
    mode_by_lane = {
        "sitrep": "read-only-sitrep",
        "live-observer": "read-only-live-observer",
        "package-review": "read-only-package-review",
        "integration": "opencode-integration-patch-and-test",
    }
    allows_tracked_edits = lane == "integration"
    return {
        "lane": lane,
        "mode": mode_by_lane[lane],
        "recommendedAgent": LANE_RECOMMENDED_AGENTS[lane],
        "allowsTrackedEdits": allows_tracked_edits,
        "allowedEditPaths": list(INTEGRATION_ALLOWED_EDIT_PATHS) if allows_tracked_edits else [],
        "groundingFiles": list(INTEGRATION_GROUNDING_FILES) if allows_tracked_edits else [],
        "ignoredWriteRoots": [r".riftreader-local\opencode-prompts", r".riftreader-local\opencode-runs"],
        "forbiddenActions": list(COMMON_FORBIDDEN_ACTIONS),
        "hardStopConditions": list(INTEGRATION_HARD_STOP_CONDITIONS if allows_tracked_edits else READ_ONLY_HARD_STOP_CONDITIONS),
        "targetedValidation": list(INTEGRATION_TARGETED_VALIDATION if allows_tracked_edits else ()),
    }


def opencode_run_command(repo_root: Path, *, model: str, variant: str, agent: str | None = None) -> list[str]:
    """Return a Windows npm-shim-safe OpenCode run command."""

    command = [
        "opencode",
        "run",
        "--dir",
        str(repo_root),
        "-m",
        model,
        "--variant",
        variant,
    ]
    selected_agent = selected_opencode_agent(agent)
    if selected_agent:
        command.extend(["--agent", selected_agent])
    if sys.platform == "win32":
        return ["cmd", "/d", "/c", *command]
    return command


def run_command_envelope_with_input(
    label: str,
    args: list[str],
    cwd: Path,
    *,
    stdin_text: str,
    timeout_seconds: float,
    expected_exit_codes: set[int] | None = None,
) -> dict[str, Any]:
    """Run a command with stdin while preserving the shared envelope shape."""

    expected = expected_exit_codes if expected_exit_codes is not None else {0}
    start_monotonic = time.monotonic()
    envelope: dict[str, Any] = {
        "label": label,
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": utc_iso(),
        "timeoutSeconds": timeout_seconds,
        "exitCode": None,
        "ok": False,
        "timedOut": False,
        "stdoutPreview": "",
        "stderrPreview": "",
        "stdinBytes": len(stdin_text.encode("utf-8")),
        "stdinMode": "prompt-via-stdin",
    }
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        envelope["exitCode"] = completed.returncode
        envelope["ok"] = completed.returncode in expected
        envelope["stdoutPreview"] = preview_text(completed.stdout)
        envelope["stderrPreview"] = preview_text(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        envelope["timedOut"] = True
        envelope["error"] = f"TimeoutExpired:{exc}"
        envelope["stdoutPreview"] = preview_text(exc.stdout if isinstance(exc.stdout, str) else "")
        envelope["stderrPreview"] = preview_text(exc.stderr if isinstance(exc.stderr, str) else "")
    except FileNotFoundError as exc:
        envelope["error"] = f"FileNotFoundError:{exc}"
    except Exception as exc:  # noqa: BLE001 - command envelope must capture unexpected local failures.
        envelope["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        envelope["endedAtUtc"] = utc_iso()
        envelope["durationSeconds"] = round(time.monotonic() - start_monotonic, 3)
    return envelope


def _append_bounded_preview(chunks: list[str], char_count: list[int], text: str, *, limit: int = 20000) -> None:
    remaining = limit - char_count[0]
    if remaining > 0:
        chunks.append(text[:remaining])
    char_count[0] += len(text)


def _stream_pipe_to_file(
    pipe: Any,
    output_path: Path,
    echo: Any,
    preview_chunks: list[str],
    preview_chars: list[int],
    errors: list[str],
    stream_name: str,
) -> None:
    try:
        with output_path.open("w", encoding="utf-8", errors="replace") as output:
            for chunk in iter(pipe.readline, ""):
                output.write(chunk)
                output.flush()
                _append_bounded_preview(preview_chunks, preview_chars, chunk)
                try:
                    echo.write(chunk)
                    echo.flush()
                except Exception as exc:  # noqa: BLE001 - streaming must not fail the child command.
                    errors.append(f"{stream_name}-echo-failed:{type(exc).__name__}:{exc}")
    except Exception as exc:  # noqa: BLE001 - preserve command envelope instead of crashing.
        errors.append(f"{stream_name}-stream-failed:{type(exc).__name__}:{exc}")
    finally:
        try:
            pipe.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup only.
            pass


def _write_stdin(pipe: Any, stdin_text: str, errors: list[str]) -> None:
    try:
        pipe.write(stdin_text)
        pipe.flush()
    except (BrokenPipeError, OSError) as exc:
        errors.append(f"stdin-write-failed:{type(exc).__name__}:{exc}")
    except Exception as exc:  # noqa: BLE001 - preserve command envelope instead of crashing.
        errors.append(f"stdin-write-failed:{type(exc).__name__}:{exc}")
    finally:
        try:
            pipe.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup only.
            pass


def _terminate_process(process: subprocess.Popen[Any], *, grace_seconds: float = 5.0) -> list[str]:
    notes: list[str] = []
    if process.poll() is not None:
        return notes
    if sys.platform == "win32":
        notes.extend(_taskkill_process_tree(process, grace_seconds=grace_seconds))
        if process.poll() is not None:
            return notes
    try:
        process.terminate()
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        notes.append("terminate-timeout")
        try:
            process.kill()
            process.wait(timeout=grace_seconds)
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup only.
            notes.append(f"kill-failed:{type(exc).__name__}:{exc}")
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup only.
        notes.append(f"terminate-failed:{type(exc).__name__}:{exc}")
        try:
            process.kill()
        except Exception as kill_exc:  # noqa: BLE001
            notes.append(f"kill-failed:{type(kill_exc).__name__}:{kill_exc}")
    return notes


def _popen_platform_options() -> dict[str, Any]:
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {}


def _safe_join_thread(thread: threading.Thread, errors: list[str], label: str) -> None:
    try:
        thread.join(timeout=2.0)
        if thread.is_alive():
            errors.append(f"{label}-thread-still-running")
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup only.
        errors.append(f"{label}-thread-join-failed:{type(exc).__name__}:{exc}")


def _taskkill_process_tree(process: subprocess.Popen[Any], *, grace_seconds: float = 5.0) -> list[str]:
    notes: list[str] = []
    if sys.platform != "win32" or process.poll() is not None:
        return notes
    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=grace_seconds,
        )
        if completed.returncode != 0:
            detail = preview_text((completed.stderr or completed.stdout or "").strip(), max_lines=3, max_chars=500)
            notes.append(f"taskkill-exit:{completed.returncode}:{detail}")
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup only.
        notes.append(f"taskkill-failed:{type(exc).__name__}:{exc}")
    try:
        process.wait(timeout=grace_seconds)
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup only.
        notes.append(f"taskkill-wait-failed:{type(exc).__name__}:{exc}")
    return notes


def _sleep(seconds: float) -> None:
    """Small indirection for polling sleeps so tests do not patch global time.sleep."""
    time.sleep(seconds)


def run_streaming_command_with_input(
    label: str,
    args: list[str],
    cwd: Path,
    *,
    stdin_text: str,
    timeout_seconds: float,
    expected_exit_codes: set[int] | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Run a command with stdin while teeing stdout/stderr live and to disk."""

    expected = expected_exit_codes if expected_exit_codes is not None else {0}
    start_monotonic = time.monotonic()
    base = output_root if output_root is not None else cwd / DEFAULT_RUN_OUTPUT_DIR
    if not base.is_absolute():
        base = cwd / base
    output_dir = timestamped_output_dir(base)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    envelope_path = output_dir / "run-envelope.json"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    envelope: dict[str, Any] = {
        "label": label,
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": utc_iso(),
        "timeoutSeconds": timeout_seconds,
        "exitCode": None,
        "ok": False,
        "timedOut": False,
        "interrupted": False,
        "stdoutPreview": "",
        "stderrPreview": "",
        "stdinBytes": len(stdin_text.encode("utf-8")),
        "stdinMode": "prompt-via-stdin",
        "streaming": True,
        "artifacts": {
            "outputDir": repo_rel(cwd, output_dir),
            "stdout": repo_rel(cwd, stdout_path),
            "stderr": repo_rel(cwd, stderr_path),
            "runEnvelopeJson": repo_rel(cwd, envelope_path),
        },
    }
    process: subprocess.Popen[Any] | None = None
    threads: list[threading.Thread] = []
    stdin_thread: threading.Thread | None = None
    reader_errors: list[str] = []
    stdout_preview: list[str] = []
    stderr_preview: list[str] = []
    stdout_preview_chars = [0]
    stderr_preview_chars = [0]
    try:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **_popen_platform_options(),
        )
        envelope["pid"] = process.pid
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        threads = [
            threading.Thread(
                target=_stream_pipe_to_file,
                args=(process.stdout, stdout_path, sys.stdout, stdout_preview, stdout_preview_chars, reader_errors, "stdout"),
                daemon=True,
            ),
            threading.Thread(
                target=_stream_pipe_to_file,
                args=(process.stderr, stderr_path, sys.stderr, stderr_preview, stderr_preview_chars, reader_errors, "stderr"),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        stdin_thread = threading.Thread(
            target=_write_stdin,
            args=(process.stdin, stdin_text, reader_errors),
            daemon=True,
        )
        stdin_thread.start()
        deadline = start_monotonic + timeout_seconds
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                envelope["exitCode"] = exit_code
                break
            if time.monotonic() >= deadline:
                envelope["timedOut"] = True
                envelope["error"] = f"TimeoutExpired:command exceeded {timeout_seconds} second(s)"
                reader_errors.extend(_terminate_process(process))
                envelope["exitCode"] = process.returncode
                break
            _sleep(0.1)
        envelope["ok"] = envelope.get("exitCode") in expected and not envelope.get("timedOut")
    except FileNotFoundError as exc:
        envelope["error"] = f"FileNotFoundError:{exc}"
    except KeyboardInterrupt:
        envelope["interrupted"] = True
        envelope["error"] = "KeyboardInterrupt"
        if process is not None:
            reader_errors.extend(_terminate_process(process))
            envelope["exitCode"] = process.returncode
    except Exception as exc:  # noqa: BLE001 - command envelope must capture unexpected local failures.
        envelope["error"] = f"{type(exc).__name__}:{exc}"
        if process is not None:
            reader_errors.extend(_terminate_process(process))
            envelope["exitCode"] = process.returncode
    finally:
        if stdin_thread is not None:
            _safe_join_thread(stdin_thread, reader_errors, "stdin")
        for thread in threads:
            _safe_join_thread(thread, reader_errors, "stream")
        if reader_errors:
            envelope["readerErrors"] = reader_errors
        envelope["stdoutPreview"] = preview_text("".join(stdout_preview))
        envelope["stderrPreview"] = preview_text("".join(stderr_preview))
        envelope["stdoutBytes"] = stdout_path.stat().st_size if stdout_path.exists() else 0
        envelope["stderrBytes"] = stderr_path.stat().st_size if stderr_path.exists() else 0
        envelope["endedAtUtc"] = utc_iso()
        envelope["durationSeconds"] = round(time.monotonic() - start_monotonic, 3)
        envelope_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return envelope


def required_commands(lane: str, package_path: str | None = None) -> list[str]:
    if lane == "integration":
        return [
            r".\scripts\riftreader-workflow-status.cmd --compact-json --write",
            "git status --short --branch",
        ]
    if lane == "live-observer":
        return [
            r".\scripts\riftreader-live-triage.cmd --json --write",
            r".\scripts\riftreader-workflow-status.cmd --compact-json --write",
        ]
    if lane == "package-review":
        if not package_path:
            return [r".\scripts\riftreader-package-intake.cmd --package <package-path> --compact-json"]
        return [
            rf".\scripts\riftreader-package-intake.cmd --package {_quote_path(package_path)} --compact-json",
            r".\scripts\riftreader-workflow-status.cmd --compact-json --write",
        ]
    return [r".\scripts\riftreader-workflow-status.cmd --compact-json --write"]


def adaptive_focus(compact: dict[str, Any], *, lane: str, package_path: str | None = None) -> list[str]:
    """Return condition-specific directives for the current preflight state."""

    focus: list[str] = []
    git = compact.get("git") if isinstance(compact.get("git"), dict) else {}
    proof = compact.get("currentProof") if isinstance(compact.get("currentProof"), dict) else {}
    live_target = compact.get("liveTarget") if isinstance(compact.get("liveTarget"), dict) else {}
    movement = compact.get("movementGate") if isinstance(compact.get("movementGate"), dict) else {}
    opencode = compact.get("opencode") if isinstance(compact.get("opencode"), dict) else {}
    blockers = [str(item) for item in _list(compact.get("blockers"))]
    warnings = [str(item) for item in _list(compact.get("warnings"))]
    errors = [str(item) for item in _list(compact.get("errors"))]

    if opencode.get("available") is False:
        focus.append(
            "OpenCode was not available during preflight. If this run somehow starts, report the CLI/provider mismatch first and do not infer repo or live-game truth from a partial run."
        )
    if opencode.get("modelVisible") is False:
        focus.append(
            f"Requested model {_str(opencode.get('desiredModel'))} was not visible in the provider catalog. Report this as a provider/model configuration blocker before doing any optional lane work."
        )
    if errors:
        focus.append("Status packet errors exist. Report the errors exactly and stop before expanding scope.")
    if git.get("isClean") is False:
        focus.append(
            "The worktree is not clean. Summarize tracked/untracked paths from status output, do not overwrite local files, and do not stage/commit/push. Treat untracked handoffs as local resume artifacts until explicitly approved for commit."
        )

    live_verdict = str(live_target.get("verdict") or "")
    if live_verdict == "artifact-pid-stale":
        focus.append(
            "A rift_x64 process is visible, but the proof artifact targets a historical PID/HWND. Treat process presence as process-only context, not in-world or same-target proof; keep movement blocked and recommend no-input current-target reacquisition/status refresh."
        )
    elif live_verdict == "no-live-process":
        focus.append("No live rift_x64 process is visible. Stay offline/status-only and do not run ProofOnly, movement, input, CE, or x64dbg.")
    elif live_verdict == "artifact-pid-missing":
        focus.append("A live target may exist but the proof artifact has no target PID. Keep movement blocked and require current-target status/reacquisition before ProofOnly.")

    proof_status = str(proof.get("status") or "")
    if proof_status.startswith("blocked"):
        focus.append(
            f"Current proof status is {proof_status}. Do not use stale candidate/address fields as current proof or movement permission."
        )
    if movement.get("allowed") is False:
        focus.append(
            f"Movement gate is closed ({_str(movement.get('status'))}). Do not send input, movement, /reloadui, screenshot hotkeys, or proof-promotion commands."
        )

    if lane == "integration":
        focus.extend(
            [
                "This is the autonomous OpenCode-integration development lane: continue through small patch+test milestones until a hard stop condition is reached.",
                "A completed milestone is a checkpoint, not the end of the task. After each validated milestone, immediately choose the next safe in-scope OpenCode-integration improvement.",
                f"Allowed edit scope is limited to {', '.join(INTEGRATION_ALLOWED_EDIT_PATHS)}.",
                "For every patch, run targeted compile/unit validation and git diff --check before declaring the milestone complete.",
                "Do not stop for a single passing patch, test run, wrapper fix, docs update, handoff/status summary, or milestone-complete message.",
                "Stop only when no further useful in-scope OpenCode-integration improvement remains, the next step requires a forbidden live/proof/Git action, a required external dependency/user decision is missing, or the same failure pattern has repeated three times.",
            ]
        )
    elif lane == "live-observer":
        focus.append("This is the no-input live observer lane: observe and summarize only; never repair proof, promote candidates, or send live input in this run.")
    elif lane == "package-review":
        focus.append(
            "This is package review only. Run package intake in dry-run mode, summarize manifest/diff/safety results, and state that --apply still requires explicit operator approval in the current turn."
        )
        if package_path:
            focus.append(f"Inspect exactly this package path: {package_path}")
    else:
        focus.append("This is the read-only SITREP lane: produce a compact pasteback truth summary and next safest action, not a patch.")

    if blockers:
        focus.append("Existing blockers must be reported before any recommendations. Do not convert a blocker into permission to proceed.")
    if warnings:
        focus.append("Warnings are evidence, not noise. Include warnings that affect target freshness, model/provider setup, or local worktree state.")
    if not blockers and not errors and movement.get("allowed") is not False:
        focus.append("If the rerun status has no blockers, recommend only the smallest lane-appropriate validation or approved next step; do not assume live-input authorization.")
    return focus


def build_adaptive_prompt(lane: str, compact: dict[str, Any], *, package_path: str | None = None) -> str:
    if lane not in SUPPORTED_LANES:
        raise ValueError(f"unsupported-lane:{lane}")
    commands = required_commands(lane, package_path)
    focus = adaptive_focus(compact, lane=lane, package_path=package_path)
    safety = safety_flags()
    policy = lane_policy(lane)
    safety_lines = ["Hard safety boundaries:"]
    if policy["allowsTrackedEdits"]:
        safety_lines.extend(
            [
                "- Tracked edits are allowed only inside the OpenCode-integration allowlist in the lane policy JSON below.",
                "- Preserve unrelated dirty worktree changes. If the next required edit is outside the allowlist, stop and report the blocker.",
            ]
        )
    else:
        safety_lines.append(
            "- Do not edit tracked repo files; only write ignored .riftreader-local status/prompt artifacts when the invoked lane helper does so explicitly."
        )
    safety_lines.extend(
        [
            "- Do not apply packages, stage, commit, push, pull, reset, clean, or mutate Git refs.",
            "- Do not send live input, click, move, /reloadui, screenshot hotkeys, or run movement/proof-promotion helpers.",
            "- Do not attach Cheat Engine or x64dbg, and do not write provider repos.",
            "- Do not treat a visible rift_x64 process as in-world proof or same-target coordinate proof.",
            "- Treat old PID/HWND/address/candidate fields as historical reacquisition hints only until current-target proof gates pass.",
        ]
    )
    if lane == "integration":
        objective_lines = [
            "- Continue improving RiftReader OpenCode integration through small validated patch+test milestones.",
            "- Do not stop after one successful milestone; continue until a hard stop condition is reached.",
            "- Keep all edits inside the OpenCode-integration allowlist and preserve unrelated dirty worktree changes.",
        ]
    else:
        objective_lines = [
            "- Produce a concise, paste-ready local truth summary for desktop ChatGPT.",
            "- Adapt to the current repo/process/proof/model state observed at runtime.",
            "- Prefer the smallest safe next action; never silently cross a safety boundary.",
        ]
    lines = [
        "You are OpenCode running the RiftReader adaptive non-Codex bridge.",
        f"Lane: {lane}",
        "",
        "Objective:",
        *objective_lines,
        "",
        *safety_lines,
        "",
        "Lane policy JSON:",
        "```json",
        json.dumps(policy, indent=2, sort_keys=True),
        "```",
        "",
        "Required command sequence:",
    ]
    for index, command in enumerate(commands, start=1):
        lines.append(f"{index}. Run `{command}`.")
    grounding_files = _list(policy.get("groundingFiles"))
    if grounding_files:
        lines.extend(
            [
                "",
                "Grounding file set:",
                "- Before the first patch, inspect the relevant files from this set and treat their current contents as repo truth.",
            ]
        )
        for path in grounding_files:
            lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "Auto-adaptive decision rules:",
            "- Prefer the local decision packet embedded in the preflight snapshot for lane, risk, stale-target blockers, reminders, validation plan, and safe next action.",
        ]
    )
    for item in focus:
        lines.append(f"- {item}")
    lines.extend(
        [
            "- Rerun the required command sequence before the final answer; the preflight snapshot below may already be stale.",
            "- If a required command fails, stop broadening scope and summarize the failed command, exit code, stdout/stderr preview, and next safest fix.",
            "- If state changes during the run, trust the newest command output and explicitly say which older preflight fact was superseded.",
            "",
            "Output contract:",
            "- For the integration lane, start with `# ✅ OpenCode Integration Milestone Complete`, `# ⚠️ OpenCode Integration Blocked`, or `# ❌ OpenCode Integration Failed` only when a hard stop condition is reached.",
            "- For non-integration lanes, start with `# ✅ OpenCode RiftReader SITREP` or `# ⚠️ OpenCode RiftReader BLOCKED`.",
            "- Include a compact table for branch/HEAD/worktree, latest handoff, OpenCode model/variant/model visibility, live target verdict, proof status, movement permission, blockers, warnings, artifacts, and next safe action.",
            "- Keep stale-vs-current proof distinctions explicit and avoid speculative movement or proof claims.",
            "- End with practical next actions only if they are specific to the observed state.",
            "",
            "Preflight snapshot from the launching helper (verify before final):",
            "```json",
            _compact_json(compact),
            "```",
            "",
            "Safety flags expected from this launcher:",
            "```json",
            _compact_json(safety),
            "```",
        ]
    )
    return "\n".join(lines)


def build_bridge_summary(
    repo_root: Path,
    *,
    lane: str,
    package_path: str | None = None,
    output_root: Path | None = None,
    check_opencode: bool = True,
    agent: str | None = None,
) -> dict[str, Any]:
    packet = build_status_packet(
        repo_root,
        commit_count=20,
        ref_count=10,
        run_coordinate_status=True,
        check_opencode=check_opencode,
        collect_git_state=True,
    )
    decision_packet = build_decision_packet(repo_root)
    compact = compact_summary(packet)
    compact["decisionPacket"] = compact_decision_packet(decision_packet)
    prompt = build_adaptive_prompt(lane, compact, package_path=package_path)
    base = output_root if output_root is not None else repo_root / DEFAULT_OUTPUT_DIR
    if not base.is_absolute():
        base = repo_root / base
    output_dir = timestamped_output_dir(base)
    prompt_path = output_dir / f"{lane}-prompt.txt"
    summary_path = output_dir / f"{lane}-prompt-summary.json"
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "riftreader-opencode-adaptive-prompt",
        "generatedAtUtc": utc_iso(),
        "lane": lane,
        "packagePath": package_path,
        "opencodeAgent": selected_opencode_agent(agent),
        "repoRoot": str(repo_root),
        "promptPath": repo_rel(repo_root, prompt_path),
        "summaryPath": repo_rel(repo_root, summary_path),
        "promptPreview": preview_text(prompt, max_lines=60, max_chars=12000),
        "lanePolicy": lane_policy(lane),
        "compactStatus": compact,
        "decisionPacket": compact["decisionPacket"],
        "requiredCommands": required_commands(lane, package_path),
        "safety": safety_flags(),
        "artifacts": {
            "outputDir": repo_rel(repo_root, output_dir),
            "prompt": repo_rel(repo_root, prompt_path),
            "summaryJson": repo_rel(repo_root, summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_self_test(repo_root: Path, *, output_root: Path | None = None) -> dict[str, Any]:
    """Generate every lane prompt without launching OpenCode and validate invariants."""

    lane_specs: list[tuple[str, str | None]] = [
        ("sitrep", None),
        ("live-observer", None),
        ("package-review", r"C:\tmp\riftreader-package-selftest.zip"),
        ("integration", None),
    ]
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for lane, package_path in lane_specs:
        summary = build_bridge_summary(
            repo_root,
            lane=lane,
            package_path=package_path,
            output_root=output_root,
            check_opencode=False,
        )
        prompt_path = repo_root / str(summary["promptPath"]).replace("\\", "/")
        prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
        lane_errors: list[str] = []
        for required in required_commands(lane, package_path):
            if required not in prompt:
                lane_errors.append(f"required-command-missing:{required}")
        for required_text in [
            "Do not send live input",
            "Do not apply packages, stage, commit, push, pull, reset, clean, or mutate Git refs.",
            "prompt-via-stdin",
        ]:
            if required_text == "prompt-via-stdin":
                continue
            if required_text not in prompt:
                lane_errors.append(f"safety-text-missing:{required_text}")
        if lane == "integration":
            for required_text in [
                "A completed milestone is a checkpoint, not the end of the task.",
                "Do not stop for a single passing patch",
            ]:
                if required_text not in prompt:
                    lane_errors.append(f"integration-loop-text-missing:{required_text}")
        policy = summary.get("lanePolicy") if isinstance(summary.get("lanePolicy"), dict) else {}
        if lane == "integration":
            if policy.get("allowsTrackedEdits") is not True:
                lane_errors.append("lane-policy-integration-not-edit-enabled")
            for required_path in INTEGRATION_ALLOWED_EDIT_PATHS:
                if required_path not in _list(policy.get("allowedEditPaths")):
                    lane_errors.append(f"lane-policy-allowlist-missing:{required_path}")
            for required_file in INTEGRATION_GROUNDING_FILES:
                if required_file not in _list(policy.get("groundingFiles")):
                    lane_errors.append(f"lane-policy-grounding-file-missing:{required_file}")
            for required_stop in INTEGRATION_HARD_STOP_CONDITIONS:
                if required_stop not in _list(policy.get("hardStopConditions")):
                    lane_errors.append(f"lane-policy-hard-stop-missing:{required_stop}")
        else:
            if policy.get("allowsTrackedEdits") is not False:
                lane_errors.append("lane-policy-readonly-edit-enabled")
            if _list(policy.get("allowedEditPaths")):
                lane_errors.append("lane-policy-readonly-has-allowlist")
            if _list(policy.get("groundingFiles")):
                lane_errors.append("lane-policy-readonly-has-grounding-files")
        if lane_errors:
            errors.extend(f"{lane}:{item}" for item in lane_errors)
        results.append(
            {
                "lane": lane,
                "packagePath": package_path,
                "promptPath": summary.get("promptPath"),
                "summaryPath": summary.get("summaryPath"),
                "lanePolicy": summary.get("lanePolicy"),
                "promptBytes": len(prompt.encode("utf-8")),
                "status": "failed" if lane_errors else "passed",
                "errors": lane_errors,
            }
        )
    return {
        "schemaVersion": 1,
        "kind": "riftreader-opencode-adaptive-bridge-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "passed",
        "errors": errors,
        "lanes": results,
        "safety": safety_flags(),
    }


def run_opencode(summary: dict[str, Any], *, timeout_seconds: float, agent: str | None = None) -> dict[str, Any]:
    repo_root = Path(str(summary["repoRoot"]))
    compact = summary.get("compactStatus") if isinstance(summary.get("compactStatus"), dict) else {}
    opencode = compact.get("opencode") if isinstance(compact.get("opencode"), dict) else {}
    if opencode.get("available") is False:
        return {
            "label": "opencode-run",
            "ok": False,
            "exitCode": None,
            "error": "opencode-unavailable-preflight",
            "stdoutPreview": "",
            "stderrPreview": "OpenCode was not available during preflight.",
        }
    if opencode.get("modelVisible") is False:
        requested_model = str(opencode.get("desiredModel") or desired_opencode_model())
        return {
            "label": "opencode-run",
            "ok": False,
            "exitCode": None,
            "error": f"opencode-model-not-visible-preflight:{requested_model}",
            "stdoutPreview": "",
            "stderrPreview": f"Requested OpenCode model {requested_model} was not visible during preflight.",
        }
    prompt_path = repo_root / str(summary["promptPath"]).replace("\\", "/")
    prompt = prompt_path.read_text(encoding="utf-8")
    model = os.environ.get("RIFTREADER_OPENCODE_MODEL", "").strip() or desired_opencode_model()
    variant = os.environ.get("RIFTREADER_OPENCODE_VARIANT", "").strip() or desired_opencode_variant()
    summary_agent = summary.get("opencodeAgent") if isinstance(summary.get("opencodeAgent"), str) else None
    command = opencode_run_command(repo_root, model=model, variant=variant, agent=selected_opencode_agent(agent or summary_agent))
    return run_streaming_command_with_input(
        "opencode-run",
        command,
        repo_root,
        stdin_text=prompt,
        timeout_seconds=timeout_seconds,
        expected_exit_codes={0},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or run an adaptive RiftReader OpenCode prompt.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to auto-detect from cwd.")
    parser.add_argument("--lane", choices=sorted(SUPPORTED_LANES), default="sitrep")
    parser.add_argument("--package", dest="package_path", default=None, help="Package path for package-review lane.")
    parser.add_argument("--output-dir", default=None, help="Override ignored output root for prompt artifacts.")
    parser.add_argument("--run", action="store_true", help="Run OpenCode with the generated prompt.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary instead of prompt text.")
    parser.add_argument("--self-test", action="store_true", help="Generate all adaptive lane prompts without running OpenCode.")
    parser.add_argument("--agent", default=None, help="Configured OpenCode agent to pass to `opencode run`; also supports RIFTREADER_OPENCODE_AGENT.")
    parser.add_argument("--timeout-seconds", type=float, default=900.0, help="OpenCode run timeout when --run is used.")
    parser.add_argument("--skip-opencode-check", action="store_true", help="Build prompt without checking OpenCode availability/model catalog.")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.self_test:
        result = build_self_test(
            repo_root,
            output_root=Path(args.output_dir) if args.output_dir else None,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "passed" else 1
    if args.lane == "package-review" and not args.package_path:
        print("package-review lane requires --package <path>", file=sys.stderr)
        return 1
    summary = build_bridge_summary(
        repo_root,
        lane=args.lane,
        package_path=args.package_path,
        output_root=Path(args.output_dir) if args.output_dir else None,
        check_opencode=not args.skip_opencode_check,
        agent=args.agent,
    )
    exit_code = 0
    if args.run:
        run_envelope = run_opencode(summary, timeout_seconds=args.timeout_seconds, agent=args.agent)
        summary["opencodeRun"] = run_envelope
        summary_path = repo_root / str(summary["summaryPath"]).replace("\\", "/")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if run_envelope.get("streaming"):
            artifacts = run_envelope.get("artifacts") if isinstance(run_envelope.get("artifacts"), dict) else {}
            run_summary = artifacts.get("runEnvelopeJson") or summary.get("summaryPath")
            print(f"\nOpenCode run envelope: {run_summary}", file=sys.stderr)
        else:
            stdout = str(run_envelope.get("stdoutPreview") or "")
            if stdout:
                print(stdout)
            stderr = str(run_envelope.get("stderrPreview") or "")
            if stderr:
                print(stderr, file=sys.stderr)
        exit_code = int(run_envelope.get("exitCode") or 1) if not run_envelope.get("ok") else 0
    elif args.json:
        print(json.dumps(summary, indent=2))
    else:
        prompt_path = repo_root / str(summary["promptPath"]).replace("\\", "/")
        print(prompt_path.read_text(encoding="utf-8"))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
