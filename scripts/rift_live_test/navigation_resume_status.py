from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from rift_live_test.reports import write_json, write_text_atomic


NAVIGATION_HANDOFF_KEYWORDS = (
    "navigation",
    "waypoint",
    "forward",
    "smoke",
    "native",
    "backend",
    "visual-gate",
    "focus",
)


@dataclass(frozen=True)
class NavigationResumeStatusOptions:
    repo_root: Path
    output_dir: Path | None = None
    write_summary: bool = False


def build_navigation_resume_status(options: NavigationResumeStatusOptions) -> dict[str, Any]:
    repo_root = options.repo_root.resolve()
    capture_root = repo_root / "scripts" / "captures"
    docs_root = repo_root / "docs"
    recovery_root = docs_root / "recovery"
    handoffs_root = docs_root / "handoffs"

    current_truth = _summarize_current_truth(recovery_root / "current-truth.md", repo_root)
    target_control = _summarize_target_control(
        _latest_file(capture_root, ("target-control-status.json",)),
        repo_root,
    )
    visual_gate = _summarize_visual_gate(
        _latest_file(capture_root, ("visual-gate-status.json",)),
        repo_root,
    )
    proof_only = _summarize_proof_only(
        _latest_file(capture_root, ("run-summary.json",), required_path_part="live-test-ProofOnly"),
        repo_root,
    )
    navigation_run = _summarize_navigation_run(
        _latest_file(capture_root, ("navigate-waypoints-run-summary.json",)),
        repo_root,
    )
    turn_backend = _summarize_turn_backend(recovery_root / "turn-key-profile-evidence.json", repo_root)
    latest_navigation_handoff = _summarize_latest_navigation_handoff(handoffs_root, repo_root)
    route_run_report = _summarize_route_run_report(
        _latest_file(capture_root, ("summary.json",), required_path_part="static-owner-nav-route-run-report"),
        repo_root,
    )

    blockers: list[str] = []
    warnings: list[str] = [
        "offline-status-only-currentness-not-proven",
        "rerun-exact-target-visual-gate-and-proofonly-before-live-input",
    ]

    if not target_control.get("readyForReadOnlyProof"):
        blockers.append("latest-target-control-not-ready-for-readonly-proof")
    for blocker in target_control.get("blockers") or []:
        if blocker in {"target-process-missing", "target-window-missing"}:
            blockers.append(f"latest-target-control-{blocker}")

    if current_truth.get("proofNotPromoted"):
        blockers.append("current-truth-coordinate-proof-not-promoted")
    if not visual_gate.get("readyForLiveInput"):
        blockers.append("latest-visual-gate-not-ready")
    if not proof_only.get("passedProofOnly"):
        blockers.append("latest-proofonly-not-passed-or-missing")

    visual_pid = visual_gate.get("processId")
    proof_pid = proof_only.get("processId")
    target_pid = target_control.get("processId")
    if target_pid and visual_pid and target_pid != visual_pid:
        blockers.append("latest-target-control-target-differs-from-latest-visual-gate")
    if target_pid and proof_pid and target_pid != proof_pid:
        blockers.append("latest-proofonly-target-differs-from-latest-target-control")
    if visual_pid and proof_pid and visual_pid != proof_pid:
        blockers.append("latest-proofonly-target-differs-from-latest-visual-gate")

    visual_hwnd = _normalize_hwnd(visual_gate.get("targetWindowHandle"))
    proof_hwnd = _normalize_hwnd(proof_only.get("targetWindowHandle"))
    target_hwnd = _normalize_hwnd(target_control.get("targetWindowHandle"))
    if target_hwnd and visual_hwnd and target_hwnd != visual_hwnd:
        blockers.append("latest-target-control-hwnd-differs-from-latest-visual-gate")
    if target_hwnd and proof_hwnd and target_hwnd != proof_hwnd:
        blockers.append("latest-proofonly-hwnd-differs-from-latest-target-control")
    if visual_hwnd and proof_hwnd and visual_hwnd != proof_hwnd:
        blockers.append("latest-proofonly-hwnd-differs-from-latest-visual-gate")

    if not turn_backend.get("hasPromotedCandidate"):
        warnings.append("auto-turn-not-promoted")

    _append_terrain_warnings(route_run_report, warnings)

    status = "blocked-for-live-input" if blockers else "ready-for-pre-live-recheck"
    blockers = _unique_strings(blockers)
    warnings = _unique_strings(warnings)
    recommended_actions = _recommended_actions(
        blockers,
        target_control,
        visual_gate,
        proof_only,
        navigation_run,
        turn_backend,
        route_run_report,
    )

    generated_at = _utc_now()
    output_dir = options.output_dir
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "navigation-resume-status",
        "status": status,
        "ok": not blockers,
        "generatedAtUtc": generated_at,
        "repoRoot": str(repo_root),
        "focus": {
            "product": "rift-mmo-navigation",
            "reverseEngineeringRole": "supporting-recovery-lane-only",
            "liveInputSentByThisHelper": False,
            "movementSentByThisHelper": False,
            "cheatEngineUsedByThisHelper": False,
            "providerWritesByThisHelper": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "evidence": {
            "currentTruth": current_truth,
            "latestNavigationHandoff": latest_navigation_handoff,
            "latestTargetControl": target_control,
            "latestVisualGate": visual_gate,
            "latestProofOnly": proof_only,
            "latestNavigationRun": navigation_run,
            "turnBackend": turn_backend,
            "latestRouteRunReport": route_run_report,
        },
        "recommendedActions": recommended_actions,
        "artifacts": {},
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "githubConnectorWrites": False,
            "providerWrites": False,
        },
    }

    if options.write_summary:
        if output_dir is None:
            output_dir = capture_root / f"navigation-resume-status-{_stamp()}"
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_json = output_dir / "summary.json"
        summary_md = output_dir / "summary.md"
        summary["artifacts"] = {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        }
        write_json(summary_json, summary)
        write_text_atomic(summary_md, _render_markdown(summary))

    return summary


def _summarize_target_control(path: Path | None, repo_root: Path) -> dict[str, Any]:
    if path is None:
        return _missing("target-control-missing")

    data, error = _read_json(path)
    if error is not None:
        return _json_error(path, repo_root, error)

    target = _pick(data, "target", default={})
    window = _pick(data, "window", default={})
    process_id = _pick(target, "processId") if isinstance(target, dict) else None
    if process_id is None and isinstance(window, dict):
        process_id = _pick(window, "processId")
    hwnd = _pick(target, "requestedWindowHandle") if isinstance(target, dict) else None
    if hwnd is None and isinstance(window, dict):
        hwnd = _pick(window, "windowHandleHex", "windowHandle")
    return {
        "path": _display_path(path, repo_root),
        "lastWriteTimeUtc": _mtime_utc(path),
        "status": _pick(data, "status"),
        "classification": _pick(data, "classification"),
        "ok": bool(_pick(data, "ok")),
        "readyForReadOnlyProof": bool(_pick(data, "readyForReadOnlyProof")),
        "readyForVisualGate": bool(_pick(data, "readyForVisualGate")),
        "readyForLiveInput": bool(_pick(data, "readyForLiveInput")),
        "processId": process_id,
        "targetWindowHandle": hwnd,
        "processName": _pick(target, "processName") if isinstance(target, dict) else None,
        "movementSent": bool(_pick(data, "movementSent")),
        "inputSent": bool(_pick(data, "inputSent")),
        "noCheatEngine": bool(_pick(data, "noCheatEngine")),
        "blockers": list(_pick(data, "blockers", default=[]) or []),
        "warnings": list(_pick(data, "warnings", default=[]) or []),
        "summaryPath": _pick(data, "summaryPath"),
    }


def _summarize_current_truth(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": _display_path(path, repo_root),
            "exists": False,
            "proofNotPromoted": True,
            "movementBlockedTextPresent": False,
            "navigationFocusPivotPresent": False,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    current_section = text[:8000].lower()
    return {
        "path": _display_path(path, repo_root),
        "exists": True,
        "lastWriteTimeUtc": _mtime_utc(path),
        "proofNotPromoted": "not promoted" in current_section,
        "movementBlockedTextPresent": "movement remains blocked" in current_section
        or "movement blocked" in current_section
        or "movement remains allowed only after" in current_section,
        "navigationFocusPivotPresent": "rift mmo\nnavigation" in current_section
        or "rift mmo navigation" in current_section
        or "navigation-first" in current_section,
    }


def _summarize_visual_gate(path: Path | None, repo_root: Path) -> dict[str, Any]:
    if path is None:
        return _missing("visual-gate-missing")

    data, error = _read_json(path)
    if error is not None:
        return _json_error(path, repo_root, error)

    blockers = list(_pick(data, "blockers") or [])
    status = _pick(data, "status")
    ready = bool(_pick(data, "readyForLiveInput")) and str(status).startswith("passed")
    return {
        "path": _display_path(path, repo_root),
        "lastWriteTimeUtc": _mtime_utc(path),
        "status": status,
        "ok": bool(_pick(data, "ok")),
        "readyForLiveInput": ready,
        "processId": _pick(data, "processId", "ProcessId"),
        "targetWindowHandle": _pick(data, "targetWindowHandle", "TargetWindowHandle"),
        "attemptedAtUtc": _pick(data, "attemptedAtUtc"),
        "completedAtUtc": _pick(data, "completedAtUtc"),
        "focusConfirmedForeground": bool(_pick(data, "focusConfirmedForeground")),
        "movementSent": bool(_pick(data, "movementSent")),
        "inputSent": bool(_pick(data, "inputSent")),
        "noCheatEngine": bool(_pick(data, "noCheatEngine")),
        "blockers": blockers,
    }


def _summarize_proof_only(path: Path | None, repo_root: Path) -> dict[str, Any]:
    if path is None:
        return _missing("proofonly-missing")

    data, error = _read_json(path)
    if error is not None:
        return _json_error(path, repo_root, error)

    status = _pick(data, "status")
    passed = bool(_pick(data, "ok")) and str(status).startswith("passed-proof-only")
    return {
        "path": _display_path(path, repo_root),
        "lastWriteTimeUtc": _mtime_utc(path),
        "status": status,
        "ok": bool(_pick(data, "ok")),
        "passedProofOnly": passed,
        "processId": _pick(data, "processId", "ProcessId"),
        "targetWindowHandle": _pick(data, "targetWindowHandle", "TargetWindowHandle"),
        "generatedAtUtc": _pick(data, "generatedAtUtc"),
        "movementSent": bool(_pick(data, "movementSent")),
        "movementAttempted": bool(_pick(data, "movementAttempted")),
        "noCheatEngine": bool(_pick(data, "noCheatEngine", default=True)),
        "savedVariablesUsedAsLiveTruth": bool(_pick(data, "savedVariablesUsedAsLiveTruth")),
        "coordinateRecordedAtUtc": (_pick(data, "currentCoordinate") or {}).get("recordedAtUtc")
        if isinstance(_pick(data, "currentCoordinate"), dict)
        else None,
        "currentness": "offline-unverified-rerun-required",
    }


def _summarize_navigation_run(path: Path | None, repo_root: Path) -> dict[str, Any]:
    if path is None:
        return _missing("navigation-run-missing")

    data, error = _read_json(path)
    if error is not None:
        return _json_error(path, repo_root, error)

    status = _pick(data, "Status", "status")
    return {
        "path": _display_path(path, repo_root),
        "lastWriteTimeUtc": _mtime_utc(path),
        "status": status,
        "success": str(status).lower() == "success",
        "processId": _pick(data, "ProcessId", "processId"),
        "processName": _pick(data, "ProcessName", "processName"),
        "movementBackend": _pick(data, "MovementBackend", "movementBackend"),
        "pulseCount": _pick(data, "PulseCount", "pulseCount"),
        "stopReason": _pick(data, "StopReason", "stopReason"),
        "finalPlanarDistance": _pick(data, "FinalPlanarDistance", "finalPlanarDistance"),
        "arrivalRadius": _pick(data, "ArrivalRadius", "arrivalRadius"),
        "anchorSource": _pick(data, "AnchorSource", "anchorSource"),
        "staleness": "historical-run-rerun-preflights-before-reuse",
    }


def _summarize_turn_backend(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": _display_path(path, repo_root),
            "exists": False,
            "hasPromotedCandidate": False,
            "status": "turn-evidence-missing",
        }

    data, error = _read_json(path)
    if error is not None:
        return _json_error(path, repo_root, error) | {"hasPromotedCandidate": False}

    promoted = _pick(data, "promotedCandidates", default=[])
    return {
        "path": _display_path(path, repo_root),
        "exists": True,
        "lastWriteTimeUtc": _mtime_utc(path),
        "hasPromotedCandidate": isinstance(promoted, list) and len(promoted) > 0,
        "promotedCandidateCount": len(promoted) if isinstance(promoted, list) else 0,
        "status": "promoted-candidate-present" if promoted else "no-promoted-turn-backend",
    }


def _summarize_latest_navigation_handoff(handoffs_root: Path, repo_root: Path) -> dict[str, Any]:
    if not handoffs_root.exists():
        return _missing("handoffs-directory-missing")

    candidates = [
        path
        for path in handoffs_root.glob("*.md")
        if any(keyword in path.name.lower() for keyword in NAVIGATION_HANDOFF_KEYWORDS)
    ]
    if not candidates:
        return _missing("navigation-handoff-missing")

    path = max(candidates, key=lambda item: item.stat().st_mtime)
    return {
        "path": _display_path(path, repo_root),
        "lastWriteTimeUtc": _mtime_utc(path),
        "name": path.name,
    }


def _summarize_route_run_report(path: Path | None, repo_root: Path) -> dict[str, Any]:
    """Read the latest route-run report and surface terrain classification evidence.

    The route-run REPORT (from report_saved_summary in static_owner_nav_route_run.py)
    contains steps with noProgressSubClassification fields. This function extracts
    terrain sub-classification counts and terrain blocker presence so operators can
    see terrain risk context before approving a new route.
    """
    if path is None:
        return _missing("route-run-report-missing")

    data, error = _read_json(path)
    if error is not None:
        return _json_error(path, repo_root, error)

    source = _pick(data, "source", default={}) if isinstance(_pick(data, "source"), dict) else {}
    steps = _pick(source, "steps", default=[]) if isinstance(_pick(source, "steps"), list) else []
    contract = _pick(data, "contract", default={}) if isinstance(_pick(data, "contract"), dict) else {}

    aggregate = _pick(source, "aggregate", default={}) if isinstance(_pick(source, "aggregate"), dict) else {}

    terrain_sub_classifications: dict[str, int] = {}
    no_progress_step_count = 0
    terrain_blocker_present = False

    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("routeStatus") == "no-progress":
            no_progress_step_count += 1
            sub = step.get("noProgressSubClassification") or "unspecified"
            if isinstance(sub, str):
                terrain_sub_classifications[sub] = terrain_sub_classifications.get(sub, 0) + 1
                if sub == "blocked-stationary-no-movement":
                    terrain_blocker_present = True

    return {
        "path": _display_path(path, repo_root),
        "lastWriteTimeUtc": _mtime_utc(path),
        "status": _pick(data, "status"),
        "sourceKind": _pick(source, "kind"),
        "sourceVerdict": _pick(source, "verdict"),
        "sourceStatus": _pick(source, "status"),
        "contractStatus": _pick(contract, "status"),
        "stepsRun": _pick(aggregate, "stepsRun") or _pick(contract, "stepsRun"),
        "arrived": _pick(aggregate, "arrived") or _pick(contract, "arrived"),
        "noProgressStepCount": no_progress_step_count,
        "terrainSubClassifications": terrain_sub_classifications,
        "terrainBlockerPresent": terrain_blocker_present,
        "terrainBlockerTypes": [sub for sub, count in terrain_sub_classifications.items() if sub == "blocked-stationary-no-movement" and count > 0],
    }


_TERRAIN_MEANINGS: dict[str, str] = {
    "blocked-stationary-no-movement": "Terrain/obstacle — player did not move at all during the forward pulse",
    "drifted-back-after-initial-progress": "Player moved forward then drifted back — terrain may have redirected",
    "insufficient-progress-below-threshold": "Player moved slightly but below the minimum progress threshold",
}


def _append_terrain_warnings(route_run_report: dict[str, Any], warnings: list[str]) -> None:
    """Surface terrain context from a prior route-run report as operator warnings.

    These are warnings, not blockers — a terrain-stalled previous route does not
    prevent a fresh route from succeeding. The warnings provide operator context
    for decision-making before approving movement.
    """
    if route_run_report.get("status") == "route-run-report-missing":
        warnings.append("no-route-run-report-available-for-terrain-context")
        return

    terrain_classifications = route_run_report.get("terrainSubClassifications") or {}
    if not terrain_classifications:
        return

    no_progress_count = route_run_report.get("noProgressStepCount") or 0
    terrain_count = (terrain_classifications.get("blocked-stationary-no-movement") or 0)
    drifted_count = (terrain_classifications.get("drifted-back-after-initial-progress") or 0)
    insufficient_count = (terrain_classifications.get("insufficient-progress-below-threshold") or 0)
    unspecified_count = (terrain_classifications.get("unspecified") or 0)

    if no_progress_count > 0:
        warnings.append(f"prior-route-run-had-no-progress-steps:count={no_progress_count}")

    if terrain_count > 0:
        warnings.append(
            f"prior-route-run-terrain-blocked-stationary:count={terrain_count} — "
            "player was stationary (zero movement) during forward pulses; "
            "consider scouting the route area before rerunning"
        )

    if drifted_count > 0:
        warnings.append(
            f"prior-route-run-drifted-back:{drifted_count} — "
            "player moved forward then drifted back; terrain slope or obstacle may have redirected"
        )

    if insufficient_count > 0:
        warnings.append(
            f"prior-route-run-insufficient-progress:{insufficient_count} — "
            "player made forward progress below the minimum threshold"
        )

    if unspecified_count > 0:
        warnings.append(
            f"prior-route-run-unspecified-no-progress:{unspecified_count} — "
            "no-progress steps without sub-classification (report was generated before terrain classification was added)"
        )


def _recommended_actions(
    blockers: list[str],
    target_control: dict[str, Any],
    visual_gate: dict[str, Any],
    proof_only: dict[str, Any],
    navigation_run: dict[str, Any],
    turn_backend: dict[str, Any],
    route_run_report: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []

    actions.append(
        {
            "action": "Refresh exact PID/HWND target inventory",
            "why": "The offline report cannot prove the game process/window is still the same epoch.",
        }
    )
    if "latest-target-control-not-ready-for-readonly-proof" in blockers:
        actions.append(
            {
                "action": "Stop live-input workflow until target-control resolves the RIFT window",
                "why": "Read-only proof and visual gate are unsafe when the target process/window is missing or ambiguous.",
            }
        )
    if "latest-visual-gate-not-ready" in blockers:
        actions.append(
            {
                "action": "Run the exact-target visual gate",
                "why": "Live input must stay blocked until focus/capture is proven for the current window.",
            }
        )
    else:
        actions.append(
            {
                "action": "Rerun visual gate immediately before input",
                "why": "The latest gate looks usable, but visual/focus state is short-lived.",
            }
        )

    if "latest-proofonly-not-passed-or-missing" in blockers or proof_only.get("currentness"):
        actions.append(
            {
            "action": "Run same-target ProofOnly",
            "why": "Navigation needs a fresh current proof anchor, not an old artifact.",
        }
        )

    if any("proofonly" in blocker for blocker in blockers):
        actions.append(
            {
                "action": "Reacquire the proof coordinate anchor before route work",
                "why": "Movement cannot rely on stale or different-target proof evidence.",
            }
        )

    actions.append(
        {
            "action": "Resume no-turn observed-forward waypoint smoke first",
            "why": "It is the latest proven navigation lane and does not require actor-facing truth.",
        }
    )
    actions.append(
        {
            "action": "Regenerate the observed-forward route from fresh ProofOnly plus current forward-series evidence",
            "why": "Old route coordinates are historical and should not be replayed blindly after process/session drift.",
        }
    )

    if navigation_run.get("movementBackend") != "native-window-message":
        actions.append(
            {
                "action": "Confirm the native exact-HWND movement backend is selected",
                "why": "The validated navigation path used repo-owned native window-message input.",
            }
        )

    if not turn_backend.get("hasPromotedCandidate"):
        actions.append(
            {
                "action": "Keep auto-turn disabled",
                "why": "No current promoted turn backend exists.",
            }
        )

    if route_run_report and route_run_report.get("terrainBlockerPresent"):
        terrain_sub = route_run_report.get("terrainSubClassifications") or {}
        terrain_count = terrain_sub.get("blocked-stationary-no-movement", 0)
        actions.append(
            {
                "action": f"Review terrain safety: {terrain_count} blocked-stationary step(s) in prior route-run",
                "why": (
                    "The last route-run report recorded stationary (zero-movement) forward pulses. "
                    "Before rerunning the same route, consider a short scouting pass or repositioning "
                    "the character away from potential obstacles. The terrain classification is a warning "
                    "only — it does not block a fresh route."
                ),
            }
        )

    actions.extend(
        [
            {
                "action": "Use short bounded routes during reacquisition",
                "why": "Limits risk while rebuilding live proof confidence.",
            },
            {
                "action": "If proof reacquisition blocks, use broad family-group snapshots plus offline delta comparison",
                "why": "Avoids wasting time on narrow stale-address or nearby-offset poking.",
            },
            {
                "action": "Record the next navigation pass or blocker in a fresh handoff",
                "why": "A small handoff keeps autonomous resumes aligned to the navigation lane.",
            },
            {
                "action": "Update current-truth after the next pass or blocker",
                "why": "Future resumes should start from navigation-first evidence.",
            },
        ]
    )

    return actions[:10]


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _render_markdown(summary: dict[str, Any]) -> str:
    evidence = summary["evidence"]
    lines = [
        "# Navigation resume status",
        "",
        f"Generated: `{summary['generatedAtUtc']}`",
        f"Status: `{summary['status']}`",
        "",
        "## Verdict",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Product focus | `{summary['focus']['product']}` |",
        f"| Reverse-engineering role | `{summary['focus']['reverseEngineeringRole']}` |",
        f"| Live input sent by this helper | `{str(summary['focus']['liveInputSentByThisHelper']).lower()}` |",
        f"| Movement sent by this helper | `{str(summary['focus']['movementSentByThisHelper']).lower()}` |",
        f"| Cheat Engine used by this helper | `{str(summary['focus']['cheatEngineUsedByThisHelper']).lower()}` |",
        "",
        "## Blockers",
        "",
    ]
    if summary["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    else:
        lines.append("- None recorded by this offline report. Rerun live gates before input.")

    lines.extend(
        [
            "",
            "## Evidence snapshot",
            "",
            "| Surface | Status | Target | Artifact |",
            "|---|---|---|---|",
            _evidence_row("Current truth", _bool_status(evidence["currentTruth"].get("exists")), "", evidence["currentTruth"].get("path")),
            _evidence_row(
                "Navigation handoff",
                evidence["latestNavigationHandoff"].get("name") or evidence["latestNavigationHandoff"].get("status"),
                "",
                evidence["latestNavigationHandoff"].get("path"),
            ),
            _evidence_row(
                "Target control",
                evidence["latestTargetControl"].get("classification") or evidence["latestTargetControl"].get("status"),
                _target_text(evidence["latestTargetControl"]),
                evidence["latestTargetControl"].get("path"),
            ),
            _evidence_row(
                "Visual gate",
                evidence["latestVisualGate"].get("status"),
                _target_text(evidence["latestVisualGate"]),
                evidence["latestVisualGate"].get("path"),
            ),
            _evidence_row(
                "ProofOnly",
                evidence["latestProofOnly"].get("status"),
                _target_text(evidence["latestProofOnly"]),
                evidence["latestProofOnly"].get("path"),
            ),
            _evidence_row(
                "Navigation run",
                evidence["latestNavigationRun"].get("status"),
                _target_text(evidence["latestNavigationRun"]),
                evidence["latestNavigationRun"].get("path"),
            ),
            _evidence_row(
                "Turn backend",
                evidence["turnBackend"].get("status"),
                "",
                evidence["turnBackend"].get("path"),
            ),
            _evidence_row(
                "Route-run report",
                evidence["latestRouteRunReport"].get("status"),
                _route_run_report_target_text(evidence["latestRouteRunReport"]),
                evidence["latestRouteRunReport"].get("path"),
            ),
            "",
            "## Terrain classification (from latest route-run report)",
            "",
            *_render_terrain_section(evidence["latestRouteRunReport"]),
            "",
            "## Top 10 recommended next actions",
            "",
            "| # | Action | Why |",
            "|---:|---|---|",
        ]
    )
    for index, item in enumerate(summary["recommendedActions"], start=1):
        lines.append(f"| {index} | {item['action']} | {item['why']} |")
    return "\n".join(lines).rstrip() + "\n"


def _route_run_report_target_text(data: dict[str, Any]) -> str:
    parts = []
    verdict = data.get("sourceVerdict")
    if verdict:
        parts.append(str(verdict))
    steps = data.get("stepsRun")
    if steps is not None:
        parts.append(f"{steps} steps")
    no_progress = data.get("noProgressStepCount")
    if no_progress:
        parts.append(f"{no_progress} no-progress")
    return "; ".join(parts)


def _render_terrain_section(report: dict[str, Any]) -> list[str]:
    status = str(report.get("status") or "")
    if status in ("route-run-report-missing", "json-read-error"):
        return [
            f"- Status: `{status}` — no terrain context available",
            "- Run `static-owner-nav-report-route-run` after a route run to generate terrain evidence.",
        ]

    terrain = report.get("terrainSubClassifications") or {}
    no_progress = report.get("noProgressStepCount") or 0
    steps = report.get("stepsRun") or 0
    arrived = report.get("arrived")
    verdict = report.get("sourceVerdict", "unknown")

    lines = [
        f"- Route verdict: `{verdict}` | Arrived: `{arrived}` | Steps: `{steps}`",
        f"- No-progress steps: `{no_progress}`",
    ]

    if not terrain:
        lines.append("- No terrain sub-classifications recorded (all steps progressed or arrived).")
        return lines

    lines.append("")
    lines.append("| Sub-classification | Count | Meaning |")
    lines.append("|---|---|---|")
    for sub, count in sorted(terrain.items()):
        meaning = _TERRAIN_MEANINGS.get(sub, "No-progress without sub-classification detail")
        icon = "🛑" if sub == "blocked-stationary-no-movement" else ("⚠️" if sub == "drifted-back-after-initial-progress" else "ℹ️")
        lines.append(f"| {icon} `{sub}` | `{count}` | {meaning} |")

    if report.get("terrainBlockerPresent"):
        lines.append("")
        lines.append(
            f"- ⚠️ **Terrain blocker detected** (`blocked-stationary-no-movement`). "
            "This is a warning only — it does not prevent a fresh route. "
            "Consider scouting the area or repositioning before rerunning the same waypoint."
        )

    return lines


def _evidence_row(surface: str, status: Any, target: str, artifact: Any) -> str:
    return f"| {surface} | `{status}` | `{target}` | `{artifact or ''}` |"


def _target_text(data: dict[str, Any]) -> str:
    pid = data.get("processId")
    hwnd = data.get("targetWindowHandle")
    parts = []
    if pid:
        parts.append(f"pid={pid}")
    if hwnd:
        parts.append(f"hwnd={hwnd}")
    return "; ".join(parts)


def _bool_status(value: bool) -> str:
    return "present" if value else "missing"


def _latest_file(root: Path, file_names: Iterable[str], required_path_part: str | None = None) -> Path | None:
    if not root.exists():
        return None
    wanted = set(file_names)
    lowered_part = required_path_part.lower() if required_path_part else None
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in wanted:
            continue
        if lowered_part and lowered_part not in str(path).lower():
            continue
        candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report parse errors in status JSON.
        return {}, f"{type(exc).__name__}:{exc}"
    if not isinstance(data, dict):
        return {}, "json-root-not-object"
    return data, None


def _pick(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return default


def _missing(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "ok": False,
        "exists": False,
        "blockers": [status],
    }


def _json_error(path: Path, repo_root: Path, error: str) -> dict[str, Any]:
    return {
        "path": _display_path(path, repo_root),
        "status": "json-read-error",
        "ok": False,
        "exists": True,
        "error": error,
        "blockers": ["json-read-error"],
    }


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def _normalize_hwnd(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return text.lower()
    return hex(number).lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write an offline navigation-first resume/readiness status.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--write-summary", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the status JSON to stdout.")
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Return 2 when live-input blockers are present. Default returns 0 after writing the report.",
    )
    args = parser.parse_args(argv)

    summary = build_navigation_resume_status(
        NavigationResumeStatusOptions(
            repo_root=args.root,
            output_dir=args.output_dir,
            write_summary=args.write_summary,
        )
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Navigation resume status: {summary['status']}")
        artifacts = summary.get("artifacts") or {}
        if artifacts.get("summaryJson"):
            print(f"Summary JSON: {artifacts['summaryJson']}")
        if artifacts.get("summaryMarkdown"):
            print(f"Summary Markdown: {artifacts['summaryMarkdown']}")

    if args.strict_exit and summary.get("blockers"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
