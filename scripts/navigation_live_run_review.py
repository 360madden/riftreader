from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .navigation_schema_validate import validate_payload
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from navigation_schema_validate import validate_payload  # type: ignore
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-live-run-review"
REVIEW_CONTRACT_VERSION = "navigation-live-run-review/v1"
SCHEMA_DIR = Path("docs") / "schemas" / "navigation"
DEFAULT_MAX_REQUEST_AGE_SECONDS = 3600.0
DEFAULT_MAX_SOURCE_PACKAGE_AGE_SECONDS = 3600.0

UNSAFE_REQUEST_SAFETY_FLAGS = (
    "movementSent",
    "inputSent",
    "targetMemoryBytesRead",
    "targetMemoryBytesWritten",
    "providerWrites",
    "x64dbgAttach",
    "debuggerAttached",
    "proofPromotion",
    "actorChainPromotion",
    "facingPromotion",
    "navigationControl",
)

UNSAFE_SOURCE_PACKAGE_FLAGS = (
    "movementSent",
    "inputSent",
    "navigationControl",
    "targetMemoryBytesWritten",
    "providerWrites",
    "x64dbgAttach",
    "debuggerAttached",
    "proofPromotion",
    "actorChainPromotion",
    "facingPromotion",
)


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def latest_live_run_request(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(
        capture_root.glob("navigation-live-run-request-*/summary.json"),
        key=lambda item: item.stat().st_mtime_ns if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def parse_utc(value: Any) -> datetime | None:
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
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def age_report(value: Any, *, max_age_seconds: float) -> dict[str, Any]:
    observed = parse_utc(value)
    if observed is None:
        return {
            "status": "unknown",
            "observedAtUtc": value,
            "ageSeconds": None,
            "maxAgeSeconds": max_age_seconds,
            "fresh": False,
        }
    age = (datetime.now(UTC) - observed).total_seconds()
    return {
        "status": "fresh" if age <= max_age_seconds else "stale",
        "observedAtUtc": observed.isoformat(),
        "ageSeconds": age,
        "maxAgeSeconds": max_age_seconds,
        "fresh": age <= max_age_seconds,
    }


def safety_blockers(payload: Mapping[str, Any], *, flags: Sequence[str], prefix: str) -> list[str]:
    safety = safe_mapping(payload.get("safety"))
    return [f"{prefix}-{key}-must-be-false" for key in flags if safety.get(key) is True]


def schema_validation(root: Path, *, label: str, schema_file: str, payload: Mapping[str, Any], input_json: Path | None) -> dict[str, Any]:
    schema_path = root / SCHEMA_DIR / schema_file
    try:
        schema = load_json_object(schema_path)
        validation = validate_payload(payload, schema)
        errors = validation.get("errors", [])
        return {
            "label": label,
            "status": "passed" if validation.get("status") == "passed" else "blocked",
            "inputJson": str(input_json) if input_json else None,
            "schemaJson": str(schema_path),
            "validationStatus": validation.get("status"),
            "validationErrorCount": validation.get("errorCount"),
            "blockers": errors,
            "warnings": [],
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001 - durable error capture.
        return {
            "label": label,
            "status": "failed",
            "inputJson": str(input_json) if input_json else None,
            "schemaJson": str(schema_path),
            "validationStatus": "failed",
            "validationErrorCount": None,
            "blockers": [],
            "warnings": [],
            "errors": [f"{type(exc).__name__}:{exc}"],
        }


def source_package_path(root: Path, request_payload: Mapping[str, Any]) -> Path | None:
    request = safe_mapping(request_payload.get("request"))
    source = request.get("sourcePackageSummaryJson")
    if not source:
        source = safe_mapping(request.get("sourceArtifacts")).get("downstreamPackageSummaryJson")
    return resolve_path(root, source) if source else None


def request_gate_blockers(request_payload: Mapping[str, Any]) -> list[str]:
    request = safe_mapping(request_payload.get("request"))
    gate = safe_mapping(request.get("executionGate"))
    caps = safe_mapping(request.get("capabilitySnapshot"))
    consumer_instruction = safe_mapping(request.get("consumerInstruction"))
    blockers: list[str] = []
    if request_payload.get("kind") != "riftreader-navigation-live-run-request":
        blockers.append(f"request-kind-not-supported:{request_payload.get('kind')}")
    if request_payload.get("status") != "passed":
        blockers.append(f"request-status-not-passed:{request_payload.get('status')}")
    if gate.get("requestAcceptedForReview") is not True:
        blockers.append("request-not-accepted-for-review")
    if gate.get("executionAuthorized") is not False:
        blockers.append("request-execution-authorized-must-be-false")
    if gate.get("executionAttempted") is not False:
        blockers.append("request-execution-attempted-must-be-false")
    if gate.get("routeRunnerInvoked") is not False:
        blockers.append("request-route-runner-invoked-must-be-false")
    if caps.get("canExecuteLiveNavigation") is not False:
        blockers.append("request-can-execute-live-navigation-must-be-false")
    if consumer_instruction.get("notExecutableByThisArtifact") is not True:
        blockers.append("request-must-be-non-executable")
    return blockers


def source_package_blockers(payload: Mapping[str, Any]) -> list[str]:
    capabilities = safe_mapping(payload.get("capabilities"))
    blockers: list[str] = []
    if payload.get("kind") != "riftreader-navigation-downstream-package":
        blockers.append(f"source-package-kind-not-supported:{payload.get('kind')}")
    if payload.get("status") != "passed":
        blockers.append(f"source-package-status-not-passed:{payload.get('status')}")
    if capabilities.get("canQueueGatedLiveRunRequest") is not True:
        blockers.append("source-package-cannot-queue-gated-live-run-request")
    if capabilities.get("canExecuteLiveNavigation") is not False:
        blockers.append("source-package-live-execution-must-remain-false")
    blockers.extend(safety_blockers(payload, flags=UNSAFE_SOURCE_PACKAGE_FLAGS, prefix="source-package-safety"))
    return blockers


def build_review(args: argparse.Namespace, request_path: Path | None, request_payload: Mapping[str, Any], package_path: Path | None, package_payload: Mapping[str, Any]) -> dict[str, Any]:
    request = safe_mapping(request_payload.get("request"))
    request_gate = safe_mapping(request.get("executionGate"))
    package_caps = safe_mapping(package_payload.get("capabilities"))
    request_freshness = age_report(
        request_payload.get("generatedAtUtc"),
        max_age_seconds=float(args.max_request_age_seconds),
    )
    package_freshness = age_report(
        package_payload.get("generatedAtUtc"),
        max_age_seconds=float(args.max_source_package_age_seconds),
    )
    ready_for_separate_live_approval = (
        request_gate.get("requestAcceptedForReview") is True
        and request_freshness.get("fresh") is True
        and package_freshness.get("fresh") is True
        and package_caps.get("canQueueGatedLiveRunRequest") is True
        and package_caps.get("canExecuteLiveNavigation") is False
    )
    return {
        "reviewId": str(args.review_id or f"live-run-review-{utc_stamp()}"),
        "requestId": request.get("requestId"),
        "requestSummaryJson": str(request_path) if request_path else None,
        "sourcePackageSummaryJson": str(package_path) if package_path else None,
        "reviewState": "ready-for-separate-live-approval" if ready_for_separate_live_approval else "blocked-review",
        "requestAcceptedForReview": request_gate.get("requestAcceptedForReview") is True,
        "requestFresh": request_freshness.get("fresh") is True,
        "sourcePackageFresh": package_freshness.get("fresh") is True,
        "readyForSeparateLiveApproval": ready_for_separate_live_approval,
        "executionReviewApproved": False,
        "executionAuthorized": False,
        "executionAttempted": False,
        "routeRunnerInvoked": False,
        "movementApproved": False,
        "turnApproved": False,
        "candidateTurnControlAllowed": False,
        "requiresExplicitLiveMovementApproval": True,
        "requiredBeforeExecution": [
            "separate-explicit-live-movement-approval",
            "fresh-exact-target-static-chain-readback",
            "fresh-target-identity-check",
            "live-input-surface-audit-pass",
            "route-runner-gates-pass",
        ],
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    review = safe_mapping(summary.get("review"))
    lines = [
        "# Navigation live-run review",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        f"Review ID: `{review.get('reviewId')}`",
        f"Request ID: `{review.get('requestId')}`",
        "",
        "## Review gate",
        "",
        f"- Request accepted for review: `{review.get('requestAcceptedForReview')}`",
        f"- Request fresh: `{review.get('requestFresh')}`",
        f"- Source package fresh: `{review.get('sourcePackageFresh')}`",
        f"- Ready for separate live approval: `{review.get('readyForSeparateLiveApproval')}`",
        f"- Execution review approved: `{review.get('executionReviewApproved')}`",
        f"- Execution authorized: `{review.get('executionAuthorized')}`",
        f"- Route runner invoked: `{review.get('routeRunnerInvoked')}`",
        "",
        "This review is non-executable. It does not approve or invoke movement.",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    review = safe_mapping(summary.get("review"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "reviewId": review.get("reviewId"),
        "requestId": review.get("requestId"),
        "requestSummaryJson": review.get("requestSummaryJson"),
        "sourcePackageSummaryJson": review.get("sourcePackageSummaryJson"),
        "readyForSeparateLiveApproval": review.get("readyForSeparateLiveApproval"),
        "executionReviewApproved": review.get("executionReviewApproved"),
        "executionAuthorized": review.get("executionAuthorized"),
        "executionAttempted": review.get("executionAttempted"),
        "routeRunnerInvoked": review.get("routeRunnerInvoked"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "targetMemoryBytesRead": safety.get("targetMemoryBytesRead"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-live-run-review-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    request_path = resolve_path(root, args.live_run_request_json) if args.live_run_request_json else latest_live_run_request(root)

    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    request_payload: dict[str, Any] = {}
    package_payload: dict[str, Any] = {}
    package_path: Path | None = None
    schema_validations: list[dict[str, Any]] = []

    if request_path is None:
        errors.append("live-run-request-json-not-found")
    else:
        try:
            request_payload = load_json_object(request_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"live-run-request-load-failed:{type(exc).__name__}:{exc}")

    if request_payload:
        request_validation = schema_validation(
            root,
            label="live-run-request",
            schema_file="navigation-live-run-request.schema.json",
            payload=request_payload,
            input_json=request_path,
        )
        schema_validations.append(request_validation)
        if request_validation["status"] != "passed":
            blockers.append(f"live-run-request-schema-not-passed:{request_validation['status']}")
            blockers.extend(str(item) for item in request_validation.get("blockers", []))
        blockers.extend(request_gate_blockers(request_payload))
        blockers.extend(safety_blockers(request_payload, flags=UNSAFE_REQUEST_SAFETY_FLAGS, prefix="request-safety"))
        request_freshness = age_report(request_payload.get("generatedAtUtc"), max_age_seconds=float(args.max_request_age_seconds))
        if request_freshness["status"] == "unknown":
            blockers.append("request-generatedAtUtc-unparseable")
        elif not request_freshness["fresh"]:
            blockers.append(
                f"request-stale:ageSeconds={request_freshness['ageSeconds']:.3f};"
                f"maxAgeSeconds={request_freshness['maxAgeSeconds']}"
            )

        package_path = source_package_path(root, request_payload)
        if package_path is None:
            blockers.append("source-package-summary-json-missing")
        else:
            try:
                package_payload = load_json_object(package_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"source-package-load-failed:{type(exc).__name__}:{exc}")

    if package_payload:
        package_validation = schema_validation(
            root,
            label="source-package",
            schema_file="navigation-downstream-package.schema.json",
            payload=package_payload,
            input_json=package_path,
        )
        schema_validations.append(package_validation)
        if package_validation["status"] != "passed":
            blockers.append(f"source-package-schema-not-passed:{package_validation['status']}")
            blockers.extend(str(item) for item in package_validation.get("blockers", []))
        blockers.extend(source_package_blockers(package_payload))
        package_freshness = age_report(
            package_payload.get("generatedAtUtc"),
            max_age_seconds=float(args.max_source_package_age_seconds),
        )
        if package_freshness["status"] == "unknown":
            blockers.append("source-package-generatedAtUtc-unparseable")
        elif not package_freshness["fresh"]:
            blockers.append(
                f"source-package-stale:ageSeconds={package_freshness['ageSeconds']:.3f};"
                f"maxAgeSeconds={package_freshness['maxAgeSeconds']}"
            )
        if safe_mapping(package_payload.get("safety")).get("targetMemoryBytesRead") is True:
            warnings.append("source-package-used-read-only-target-memory-refresh")

    review = build_review(args, request_path, request_payload, package_path, package_payload)
    if errors:
        status = "failed"
        verdict = "navigation-live-run-review-failed"
    elif blockers:
        status = "blocked"
        verdict = "navigation-live-run-review-blocked"
        review["readyForSeparateLiveApproval"] = False
        review["reviewState"] = "blocked-review"
    else:
        status = "passed"
        verdict = "navigation-live-run-review-ready-for-separate-live-approval"

    safety = base_safety()
    safety.update(
        {
            "readOnlySavedJson": True,
            "liveRunReviewOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "routeControlAuthorized": False,
            "routeRunnerInvoked": False,
        }
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "contractVersion": REVIEW_CONTRACT_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(root),
        "input": {
            "liveRunRequestJson": str(request_path) if request_path else None,
            "maxRequestAgeSeconds": float(args.max_request_age_seconds),
            "maxSourcePackageAgeSeconds": float(args.max_source_package_age_seconds),
            "reviewId": args.review_id,
        },
        "review": review,
        "freshness": {
            "request": age_report(request_payload.get("generatedAtUtc"), max_age_seconds=float(args.max_request_age_seconds))
            if request_payload
            else None,
            "sourcePackage": age_report(
                package_payload.get("generatedAtUtc"),
                max_age_seconds=float(args.max_source_package_age_seconds),
            )
            if package_payload
            else None,
        },
        "schemaValidations": schema_validations,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review a saved navigation live-run request without approving execution")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--live-run-request-json", help="Saved live-run request summary; defaults to newest")
    parser.add_argument("--review-id")
    parser.add_argument("--max-request-age-seconds", type=float, default=DEFAULT_MAX_REQUEST_AGE_SECONDS)
    parser.add_argument("--max-source-package-age-seconds", type=float, default=DEFAULT_MAX_SOURCE_PACKAGE_AGE_SECONDS)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = build_report(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
