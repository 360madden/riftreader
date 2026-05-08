from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RIFTSCAN_ROOT = Path(r"C:\RIFT MODDING\Riftscan")


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def file_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
        }

    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "lastWriteUtc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sizeBytes": stat.st_size,
    }


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        if value is not None:
            return int(str(value))
    except ValueError:
        pass
    return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def best_pointer_hop(candidate_search: dict[str, Any]) -> dict[str, Any] | None:
    candidate = candidate_search.get("BestPointerHopCandidate")
    if not isinstance(candidate, dict):
        return None
    return {
        "address": candidate.get("Address"),
        "basisForwardOffset": candidate.get("BasisPrimaryForwardOffset"),
        "score": candidate.get("Score"),
        "rawScore": candidate.get("RawScore"),
        "ledgerPenalty": candidate.get("LedgerPenalty") or 0,
        "ledgerRejectionReason": candidate.get("LedgerRejectionReason"),
        "discoveryMode": candidate.get("DiscoveryMode"),
        "rootSource": candidate.get("RootSource"),
        "hopDepth": candidate.get("HopDepth"),
    }


def summarize_candidate_search(path: Path) -> dict[str, Any]:
    info = file_info(path)
    summary: dict[str, Any] = {
        "file": info,
        "loaded": False,
        "error": None,
        "candidateCount": 0,
        "pointerHopCandidateCount": 0,
        "penalizedPointerHopCandidateCount": 0,
        "bestPointerHopCandidate": None,
        "notes": [],
    }
    if not info["exists"]:
        summary["error"] = "candidate-search-file-missing"
        return summary

    try:
        document = load_json(path)
    except Exception as exc:  # pragma: no cover - exact JSON error is platform/runtime dependent.
        summary["error"] = f"candidate-search-file-invalid: {exc}"
        return summary

    pointer_hop_candidates = [
        candidate
        for candidate in document.get("PointerHopCandidates") or []
        if isinstance(candidate, dict)
    ]
    summary.update(
        {
            "loaded": True,
            "mode": document.get("Mode"),
            "processId": document.get("ProcessId"),
            "processName": document.get("ProcessName"),
            "candidateCount": as_int(document.get("CandidateCount")),
            "pointerHopCandidateCount": as_int(document.get("PointerHopCandidateCount")),
            "penalizedPointerHopCandidateCount": sum(
                1 for candidate in pointer_hop_candidates if as_int(candidate.get("LedgerPenalty")) > 0
            ),
            "bestPointerHopCandidate": best_pointer_hop(document),
            "notes": [str(note) for note in document.get("Notes") or []],
        }
    )
    return summary


def infer_validation_summary(document: dict[str, Any]) -> dict[str, Any]:
    validation_summary = document.get("ValidationSummary")
    if isinstance(validation_summary, dict):
        return validation_summary

    results = [row for row in document.get("Results") or [] if isinstance(row, dict)]
    truth_like = [row for row in results if as_bool(row.get("TruthLike"))]
    responsive = [row for row in results if as_bool(row.get("CandidateResponsive"))]
    reversible = [row for row in results if as_bool(row.get("Reversible"))]
    best = document.get("BestTruthLikeCandidate")
    if not isinstance(best, dict):
        best = truth_like[0] if truth_like else (responsive[0] if responsive else (results[0] if results else None))

    return {
        "ValidationFocus": document.get("ValidationFocus") or "legacy-actor-yaw-candidate-test",
        "CandidateCount": as_int(document.get("CandidateCount"), len(results)),
        "TruthLikeCandidateCount": as_int(document.get("TruthLikeCandidateCount"), len(truth_like)),
        "ResponsiveCandidateCount": len(responsive),
        "ReversibleCandidateCount": len(reversible),
        "BestCandidate": best,
        "FacingPromotionAttempted": bool(document.get("FacingPromotionAttempted", False)),
        "DownstreamFacingUse": document.get("DownstreamFacingUse") or "not-promoted-by-this-script",
    }


def summarize_yaw_validation(path: Path) -> dict[str, Any]:
    info = file_info(path)
    summary: dict[str, Any] = {
        "file": info,
        "loaded": False,
        "error": None,
        "validationFocus": None,
        "candidateCount": 0,
        "truthLikeCandidateCount": 0,
        "responsiveCandidateCount": 0,
        "reversibleCandidateCount": 0,
        "facingPromotionAttempted": False,
        "downstreamFacingUse": "not-promoted-by-this-script",
        "bestCandidate": None,
    }
    if not info["exists"]:
        summary["error"] = "yaw-validation-file-missing"
        return summary

    try:
        document = load_json(path)
    except Exception as exc:  # pragma: no cover - exact JSON error is platform/runtime dependent.
        summary["error"] = f"yaw-validation-file-invalid: {exc}"
        return summary

    validation_summary = infer_validation_summary(document)
    best = validation_summary.get("BestCandidate")
    if not isinstance(best, dict):
        best = None
    summary.update(
        {
            "loaded": True,
            "mode": document.get("Mode"),
            "generatedAtUtc": document.get("GeneratedAtUtc"),
            "processName": document.get("ProcessName"),
            "stimulusKey": document.get("StimulusKey"),
            "reverseStimulusKey": document.get("ReverseStimulusKey"),
            "validationFocus": validation_summary.get("ValidationFocus"),
            "candidateCount": as_int(validation_summary.get("CandidateCount")),
            "truthLikeCandidateCount": as_int(validation_summary.get("TruthLikeCandidateCount")),
            "responsiveCandidateCount": as_int(validation_summary.get("ResponsiveCandidateCount")),
            "reversibleCandidateCount": as_int(validation_summary.get("ReversibleCandidateCount")),
            "facingPromotionAttempted": as_bool(validation_summary.get("FacingPromotionAttempted")),
            "downstreamFacingUse": validation_summary.get("DownstreamFacingUse") or "not-promoted-by-this-script",
            "bestCandidate": summarize_best_yaw_candidate(best),
        }
    )
    return summary


def summarize_best_yaw_candidate(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "candidateKey": candidate.get("CandidateKey"),
        "sourceAddress": candidate.get("SourceAddress"),
        "basisForwardOffset": candidate.get("BasisForwardOffset"),
        "discoveryMode": candidate.get("DiscoveryMode"),
        "truthLike": as_bool(candidate.get("TruthLike")),
        "candidateResponsive": as_bool(candidate.get("CandidateResponsive")),
        "reversible": as_bool(candidate.get("Reversible")),
        "yawDeltaDegrees": candidate.get("YawDeltaDegrees"),
        "reverseYawDeltaDegrees": candidate.get("ReverseYawDeltaDegrees"),
        "playerCoordDeltaMagnitude": candidate.get("PlayerCoordDeltaMagnitude"),
        "yawDiscoveryStatus": candidate.get("YawDiscoveryStatus"),
    }


def decide_readiness(candidate_search: dict[str, Any], yaw_validation: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    recommended_actions: list[dict[str, str]] = []

    if yaw_validation.get("facingPromotionAttempted"):
        warnings.append("yaw validation artifact claims FacingPromotionAttempted=true; do not treat this as yaw-only evidence")

    if not candidate_search.get("loaded") and not yaw_validation.get("loaded"):
        status = "missing-evidence"
        decision = "run-candidate-search"
        recommended_actions.append(
            {
                "action": "Run find-player-orientation-candidate.ps1 against the exact live process.",
                "why": "No candidate search or yaw validation artifact was available.",
            }
        )
    elif candidate_search.get("loaded") and not yaw_validation.get("loaded"):
        status = "candidate-search-only"
        decision = "run-yaw-behavior-validation"
        recommended_actions.append(
            {
                "action": "Run test-actor-yaw-candidates.ps1 on the current candidate screen.",
                "why": "Candidate search exists, but no behavior-backed yaw validation artifact was available.",
            }
        )
    elif as_int(yaw_validation.get("truthLikeCandidateCount")) > 0 and as_int(yaw_validation.get("reversibleCandidateCount")) > 0:
        status = "yaw-ready-for-facing-proof-suite"
        decision = "run-facing-proof-suite-before-promotion"
        recommended_actions.append(
            {
                "action": "Run scripts/test-actor-facing-proof-suite.ps1 before any facing promotion.",
                "why": "Yaw evidence has truth-like reversible candidates, but actor-facing promotion is a separate gate.",
            }
        )
    elif as_int(yaw_validation.get("truthLikeCandidateCount")) > 0:
        status = "yaw-truth-like-needs-reversible-confirmation"
        decision = "rerun-yaw-validation-with-reverse-stimulus"
        recommended_actions.append(
            {
                "action": "Rerun yaw validation with reverse stimulus/repeats.",
                "why": "Truth-like yaw evidence exists, but reversible evidence was not counted.",
            }
        )
    elif as_int(yaw_validation.get("responsiveCandidateCount")) > 0:
        status = "yaw-responsive-needs-truth-like-proof"
        decision = "collect-stronger-yaw-proof"
        recommended_actions.append(
            {
                "action": "Collect stronger yaw proof with controlled reverse stimulus and coordinate drift checks.",
                "why": "Responsive candidates exist, but none are truth-like.",
            }
        )
    else:
        status = "not-ready"
        decision = "expand-or-refresh-yaw-discovery"
        recommended_actions.append(
            {
                "action": "Refresh candidate search and inspect ledger penalties before retrying yaw validation.",
                "why": "No behavior-responsive yaw candidate was found.",
            }
        )

    if candidate_search.get("penalizedPointerHopCandidateCount", 0) > 0:
        recommended_actions.append(
            {
                "action": "Inspect penalized pointer-hop candidates before expanding search breadth.",
                "why": "Ledger evidence has already marked at least one candidate as lower priority.",
            }
        )

    return {
        "status": status,
        "decision": decision,
        "movementAllowed": False,
        "facingPromotionAllowed": False,
        "noCheatEngine": True,
        "writesToRiftScan": False,
        "warnings": warnings,
        "recommendedActions": recommended_actions,
    }


def summarize_freshness(
    candidate_search: dict[str, Any],
    yaw_validation: dict[str, Any],
    max_artifact_age_hours: float,
    now: datetime,
) -> dict[str, Any]:
    artifact_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for label, artifact in (("candidateSearch", candidate_search), ("yawValidation", yaw_validation)):
        file = artifact.get("file") if isinstance(artifact.get("file"), dict) else {}
        if not file.get("exists"):
            artifact_rows.append(
                {
                    "name": label,
                    "path": file.get("path"),
                    "status": "missing",
                    "ageHours": None,
                    "maxArtifactAgeHours": max_artifact_age_hours,
                }
            )
            continue

        last_write = parse_datetime(file.get("lastWriteUtc"))
        if last_write is None:
            artifact_rows.append(
                {
                    "name": label,
                    "path": file.get("path"),
                    "status": "unknown",
                    "ageHours": None,
                    "maxArtifactAgeHours": max_artifact_age_hours,
                }
            )
            warnings.append(f"{label} freshness is unknown because lastWriteUtc could not be parsed.")
            continue

        age_hours = max(0.0, (now - last_write).total_seconds() / 3600.0)
        if max_artifact_age_hours <= 0:
            status = "not-checked"
        elif age_hours > max_artifact_age_hours:
            status = "stale"
            warnings.append(
                f"{label} artifact is stale: age {age_hours:.2f}h exceeds maxArtifactAgeHours {max_artifact_age_hours:.2f}."
            )
        else:
            status = "fresh"

        artifact_rows.append(
            {
                "name": label,
                "path": file.get("path"),
                "status": status,
                "ageHours": round(age_hours, 4),
                "maxArtifactAgeHours": max_artifact_age_hours,
                "lastWriteUtc": file.get("lastWriteUtc"),
            }
        )

    return {
        "maxArtifactAgeHours": max_artifact_age_hours,
        "freshnessGatePassed": sum(1 for row in artifact_rows if row["status"] == "stale") == 0,
        "staleArtifactCount": sum(1 for row in artifact_rows if row["status"] == "stale"),
        "warnings": warnings,
        "artifacts": artifact_rows,
    }


def build_summary(
    candidate_search_file: Path,
    yaw_validation_file: Path,
    max_artifact_age_hours: float = 12.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    candidate_search = summarize_candidate_search(candidate_search_file)
    yaw_validation = summarize_yaw_validation(yaw_validation_file)
    freshness = summarize_freshness(
        candidate_search,
        yaw_validation,
        max_artifact_age_hours=max_artifact_age_hours,
        now=generated_at,
    )
    readiness = decide_readiness(candidate_search, yaw_validation)
    if freshness["warnings"]:
        readiness["warnings"].extend(freshness["warnings"])
    if freshness["staleArtifactCount"] > 0:
        readiness["evidenceStatusBeforeFreshnessGate"] = readiness["status"]
        readiness["evidenceDecisionBeforeFreshnessGate"] = readiness["decision"]
        readiness["status"] = "stale-artifacts-refresh-required"
        readiness["decision"] = "refresh-stale-artifacts"
        readiness["recommendedActions"].insert(
            0,
            {
                "action": "Refresh stale actor-yaw discovery artifacts against the exact live PID/HWND before promotion work.",
                "why": "Session-bound yaw candidate and validation artifacts can become misleading after process restarts or long delays.",
            },
        )
    return {
        "schemaVersion": 1,
        "mode": "player-actor-yaw-discovery-readiness",
        "generatedAtUtc": generated_at.isoformat(),
        "candidateSearch": candidate_search,
        "yawValidation": yaw_validation,
        "artifactFreshness": freshness,
        "readiness": readiness,
    }


def format_markdown(summary: dict[str, Any]) -> str:
    readiness = summary["readiness"]
    candidate_search = summary["candidateSearch"]
    yaw_validation = summary["yawValidation"]
    lines = [
        "# Player actor-yaw discovery readiness",
        "",
        "_Generated by `scripts/summarize_actor_yaw_discovery.py`. This is an offline readiness report only; it does not authorize movement or actor-facing promotion._",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{readiness['status']}` |",
        f"| Decision | `{readiness['decision']}` |",
        f"| Movement allowed | `{readiness['movementAllowed']}` |",
        f"| Facing promotion allowed | `{readiness['facingPromotionAllowed']}` |",
        f"| No Cheat Engine | `{readiness['noCheatEngine']}` |",
        f"| Writes to RiftScan | `{readiness['writesToRiftScan']}` |",
        f"| Candidate search loaded | `{candidate_search['loaded']}` |",
        f"| Candidate count | `{candidate_search['candidateCount']}` |",
        f"| Pointer-hop candidate count | `{candidate_search['pointerHopCandidateCount']}` |",
        f"| Penalized pointer-hop candidates | `{candidate_search['penalizedPointerHopCandidateCount']}` |",
        f"| Yaw validation loaded | `{yaw_validation['loaded']}` |",
        f"| Yaw validation focus | `{yaw_validation.get('validationFocus') or ''}` |",
        f"| Truth-like yaw candidates | `{yaw_validation['truthLikeCandidateCount']}` |",
        f"| Responsive yaw candidates | `{yaw_validation['responsiveCandidateCount']}` |",
        f"| Reversible yaw candidates | `{yaw_validation['reversibleCandidateCount']}` |",
        f"| Facing promotion attempted | `{yaw_validation['facingPromotionAttempted']}` |",
        f"| Stale artifact count | `{summary.get('artifactFreshness', {}).get('staleArtifactCount', 0)}` |",
        "",
    ]

    best = yaw_validation.get("bestCandidate")
    if best:
        lines.extend(
            [
                "## Best yaw candidate",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| Candidate key | `{best.get('candidateKey') or ''}` |",
                f"| Source | `{best.get('sourceAddress') or ''}` |",
                f"| Offset | `{best.get('basisForwardOffset') or ''}` |",
                f"| Status | `{best.get('yawDiscoveryStatus') or ''}` |",
                f"| Truth-like | `{best.get('truthLike')}` |",
                f"| Responsive | `{best.get('candidateResponsive')}` |",
                f"| Reversible | `{best.get('reversible')}` |",
                "",
            ]
        )

    actions = readiness.get("recommendedActions") or []
    lines.extend(["## Recommended actions", ""])
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index}. **{action['action']}** {action['why']}")
    if not actions:
        lines.append("- None.")

    warnings = readiness.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    return "\n".join(lines).rstrip() + "\n"


def default_summary_file(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"actor-yaw-discovery-readiness-{stamp}.json"


def default_latest_pointer_file(repo_root: Path) -> Path:
    return repo_root / "scripts" / "captures" / "latest-actor-yaw-discovery-readiness.json"


def assert_not_riftscan_output(path: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(path, riftscan_root):
        raise ValueError(f"Refusing to write actor-yaw readiness output inside RiftScan: {path}")


def write_summary(summary: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    assert_not_riftscan_output(output_file, riftscan_root=riftscan_root)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def write_markdown_summary(summary: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    assert_not_riftscan_output(output_file, riftscan_root=riftscan_root)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(format_markdown(summary), encoding="utf-8")


def build_latest_pointer(summary: dict[str, Any]) -> dict[str, Any]:
    readiness = summary.get("readiness") if isinstance(summary.get("readiness"), dict) else {}
    freshness = summary.get("artifactFreshness") if isinstance(summary.get("artifactFreshness"), dict) else {}
    candidate_search = summary.get("candidateSearch") if isinstance(summary.get("candidateSearch"), dict) else {}
    yaw_validation = summary.get("yawValidation") if isinstance(summary.get("yawValidation"), dict) else {}
    return {
        "schemaVersion": 1,
        "mode": "latest-player-actor-yaw-discovery-readiness-pointer",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "readinessGeneratedAtUtc": summary.get("generatedAtUtc"),
        "summaryFile": summary.get("summaryFile"),
        "markdownFile": summary.get("markdownFile"),
        "status": readiness.get("status"),
        "decision": readiness.get("decision"),
        "movementAllowed": readiness.get("movementAllowed"),
        "facingPromotionAllowed": readiness.get("facingPromotionAllowed"),
        "noCheatEngine": readiness.get("noCheatEngine"),
        "writesToRiftScan": readiness.get("writesToRiftScan"),
        "freshnessGatePassed": freshness.get("freshnessGatePassed"),
        "staleArtifactCount": freshness.get("staleArtifactCount"),
        "candidateSearchFile": (candidate_search.get("file") or {}).get("path")
        if isinstance(candidate_search.get("file"), dict)
        else None,
        "yawValidationFile": (yaw_validation.get("file") or {}).get("path")
        if isinstance(yaw_validation.get("file"), dict)
        else None,
    }


def write_latest_pointer(summary: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    assert_not_riftscan_output(output_file, riftscan_root=riftscan_root)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(build_latest_pointer(summary), indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    repo_root = repo_root_from_script()
    parser = argparse.ArgumentParser(description="Summarize player actor-yaw discovery readiness from offline artifacts.")
    parser.add_argument(
        "--candidate-search-file",
        type=Path,
        default=repo_root / "scripts" / "captures" / "player-orientation-candidate-search.json",
        help="Player orientation candidate search JSON.",
    )
    parser.add_argument(
        "--yaw-validation-file",
        type=Path,
        default=repo_root / "scripts" / "captures" / "actor-yaw-candidate-test.json",
        help="Actor-yaw candidate validation JSON.",
    )
    parser.add_argument(
        "--riftscan-root",
        type=Path,
        default=DEFAULT_RIFTSCAN_ROOT,
        help="RiftScan provider repo root. Output paths under this root are refused.",
    )
    parser.add_argument("--output-json", type=Path, default=None, help="Optional readiness JSON output.")
    parser.add_argument("--output-markdown", type=Path, default=None, help="Optional readiness Markdown output.")
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write the readiness JSON under RiftReader scripts/captures.",
    )
    parser.add_argument("--summary-file", type=Path, default=None, help="Explicit readiness JSON output file.")
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="Write a Markdown companion next to the JSON summary.",
    )
    parser.add_argument("--markdown-file", type=Path, default=None, help="Explicit readiness Markdown output file.")
    parser.add_argument(
        "--update-latest-pointer",
        action="store_true",
        help="Update scripts/captures/latest-actor-yaw-discovery-readiness.json after writing a summary.",
    )
    parser.add_argument("--latest-pointer-file", type=Path, default=None, help="Explicit latest-pointer output file.")
    parser.add_argument("--compact-json", action="store_true", help="Print compact JSON instead of Markdown.")
    parser.add_argument(
        "--require-fresh",
        action="store_true",
        help="Exit nonzero when stale input artifacts are detected. The report is still printed/written.",
    )
    parser.add_argument(
        "--max-artifact-age-hours",
        type=float,
        default=12.0,
        help="Warn when existing input artifacts are older than this many hours. Use 0 to disable age checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = repo_root_from_script()
    riftscan_root = args.riftscan_root.resolve()
    summary = build_summary(
        args.candidate_search_file,
        args.yaw_validation_file,
        max_artifact_age_hours=args.max_artifact_age_hours,
    )

    if args.output_json:
        write_summary(summary, args.output_json, riftscan_root=riftscan_root)

    markdown = format_markdown(summary)
    if args.output_markdown:
        write_markdown_summary(summary, args.output_markdown, riftscan_root=riftscan_root)

    summary_file = args.summary_file or default_summary_file(repo_root)
    if args.write_summary or args.summary_file or args.write_markdown or args.markdown_file:
        summary["summaryFile"] = str(summary_file)
        markdown_file = args.markdown_file or summary_file.with_suffix(".md")
        if args.write_markdown or args.markdown_file:
            summary["markdownFile"] = str(markdown_file)
        latest_pointer_file = None
        if args.update_latest_pointer or args.latest_pointer_file:
            latest_pointer_file = args.latest_pointer_file or default_latest_pointer_file(repo_root)
            summary["latestPointerFile"] = str(latest_pointer_file)
        write_summary(summary, summary_file, riftscan_root=riftscan_root)
        if args.write_markdown or args.markdown_file:
            write_markdown_summary(summary, markdown_file, riftscan_root=riftscan_root)
        if latest_pointer_file is not None:
            write_latest_pointer(summary, latest_pointer_file, riftscan_root=riftscan_root)
    elif args.update_latest_pointer or args.latest_pointer_file:
        raise ValueError("--update-latest-pointer requires --write-summary or an explicit summary/markdown output.")

    if args.compact_json:
        print(json.dumps(summary, separators=(",", ":")))
    elif not args.output_markdown:
        print(markdown, end="")

    if args.require_fresh and not summary["artifactFreshness"]["freshnessGatePassed"]:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
