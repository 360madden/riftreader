from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-live-run-request"
REQUEST_CONTRACT_VERSION = "navigation-live-run-request/v1"


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def latest_downstream_package(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(
        capture_root.glob("navigation-downstream-package-*/summary.json"),
        key=lambda item: item.stat().st_mtime_ns if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def source_safety_blockers(payload: Mapping[str, Any]) -> list[str]:
    safety = safe_mapping(payload.get("safety"))
    blockers: list[str] = []
    for key in (
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
    ):
        if safety.get(key) is True:
            blockers.append(f"source-package-safety-{key}-must-be-false")
    return blockers


def build_execution_request(args: argparse.Namespace, package_path: Path | None, package_payload: Mapping[str, Any]) -> dict[str, Any]:
    capabilities = safe_mapping(package_payload.get("capabilities"))
    package_artifacts = safe_mapping(package_payload.get("artifacts"))
    consumer_refresh = safe_mapping(package_payload.get("consumerRefresh"))
    route_preview = safe_mapping(package_payload.get("routePreview"))
    request_id = str(args.request_id or f"live-run-request-{utc_stamp()}")
    requested_mode = str(args.requested_mode)
    explicit_approval_required = True
    source_package_usable = (
        package_payload.get("kind") == "riftreader-navigation-downstream-package"
        and package_payload.get("status") == "passed"
        and capabilities.get("canQueueGatedLiveRunRequest") is True
        and capabilities.get("canExecuteLiveNavigation") is False
        and not source_safety_blockers(package_payload)
    )
    return {
        "requestId": request_id,
        "requestedMode": requested_mode,
        "requestedBy": str(args.requested_by),
        "sourcePackageSummaryJson": str(package_path) if package_path else None,
        "sourcePackageStatus": package_payload.get("status"),
        "sourcePackageVerdict": package_payload.get("verdict"),
        "sourceArtifacts": {
            "downstreamPackageSummaryJson": package_artifacts.get("summaryJson") or str(package_path) if package_path else None,
            "consumerRefreshSummaryJson": consumer_refresh.get("summaryJson"),
            "consumerDemoSummaryJson": consumer_refresh.get("consumerDemoSummaryJson"),
            "consumerStateSummaryJson": consumer_refresh.get("consumerStateSummaryJson"),
            "routePreviewSummaryJson": route_preview.get("summaryJson"),
        },
        "capabilitySnapshot": {
            "canRenderRoute": capabilities.get("canRenderRoute"),
            "canUseDryRunContract": capabilities.get("canUseDryRunContract"),
            "canRenderRoutePreview": capabilities.get("canRenderRoutePreview"),
            "canUseRoutePreview": capabilities.get("canUseRoutePreview"),
            "canQueueGatedLiveRunRequest": capabilities.get("canQueueGatedLiveRunRequest"),
            "canExecuteLiveNavigation": False,
            "liveExecutionRequiresExplicitApproval": capabilities.get("liveExecutionRequiresExplicitApproval", True),
            "recommendedMode": capabilities.get("recommendedMode"),
            "nextRecommendedAction": capabilities.get("nextRecommendedAction"),
        },
        "executionGate": {
            "state": "queued-request-only" if source_package_usable else "blocked-source-package-not-queue-ready",
            "requestAcceptedForReview": source_package_usable,
            "executionAuthorized": False,
            "executionAttempted": False,
            "routeRunnerInvoked": False,
            "movementApproved": False,
            "turnApproved": False,
            "candidateTurnControlAllowed": False,
            "requiresExplicitLiveMovementApproval": explicit_approval_required,
            "requiredBeforeExecution": [
                "operator-explicit-live-movement-approval",
                "fresh-exact-target-static-chain-readback",
                "fresh-target-identity-check",
                "live-input-surface-audit-pass",
                "route-runner-gates-pass",
            ],
        },
        "consumerInstruction": {
            "queueable": source_package_usable,
            "safeForExternalQueue": source_package_usable,
            "notExecutableByThisArtifact": True,
            "handoff": (
                "This artifact records intent only. Do not execute route movement from it without a separate explicit live approval gate."
            ),
        },
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    request = safe_mapping(summary.get("request"))
    gate = safe_mapping(request.get("executionGate"))
    caps = safe_mapping(request.get("capabilitySnapshot"))
    lines = [
        "# Navigation live-run request",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        f"Request ID: `{request.get('requestId')}`",
        "",
        "## Gate",
        "",
        f"- Request accepted for review: `{gate.get('requestAcceptedForReview')}`",
        f"- Execution authorized: `{gate.get('executionAuthorized')}`",
        f"- Execution attempted: `{gate.get('executionAttempted')}`",
        f"- Route runner invoked: `{gate.get('routeRunnerInvoked')}`",
        f"- Can queue gated live-run request: `{caps.get('canQueueGatedLiveRunRequest')}`",
        f"- Can execute live navigation: `{caps.get('canExecuteLiveNavigation')}`",
        "",
        "This saved artifact expresses intent only and does not authorize or invoke movement.",
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
    request = safe_mapping(summary.get("request"))
    gate = safe_mapping(request.get("executionGate"))
    caps = safe_mapping(request.get("capabilitySnapshot"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "requestId": request.get("requestId"),
        "sourcePackageSummaryJson": request.get("sourcePackageSummaryJson"),
        "requestAcceptedForReview": gate.get("requestAcceptedForReview"),
        "executionAuthorized": gate.get("executionAuthorized"),
        "executionAttempted": gate.get("executionAttempted"),
        "routeRunnerInvoked": gate.get("routeRunnerInvoked"),
        "canQueueGatedLiveRunRequest": caps.get("canQueueGatedLiveRunRequest"),
        "canExecuteLiveNavigation": caps.get("canExecuteLiveNavigation"),
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
    run_dir = output_root / f"navigation-live-run-request-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    package_path = resolve_path(root, args.downstream_package_json) if args.downstream_package_json else latest_downstream_package(root)
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    package_payload: dict[str, Any] = {}
    if package_path is None:
        errors.append("downstream-package-json-not-found")
    else:
        try:
            package_payload = load_json_object(package_path)
        except Exception as exc:  # noqa: BLE001 - durable error capture.
            errors.append(f"downstream-package-load-failed:{type(exc).__name__}:{exc}")

    if package_payload:
        blockers.extend(source_safety_blockers(package_payload))
        capabilities = safe_mapping(package_payload.get("capabilities"))
        if package_payload.get("kind") != "riftreader-navigation-downstream-package":
            blockers.append(f"source-package-kind-not-supported:{package_payload.get('kind')}")
        if package_payload.get("status") != "passed":
            blockers.append(f"source-package-status-not-passed:{package_payload.get('status')}")
        if capabilities.get("canQueueGatedLiveRunRequest") is not True:
            blockers.append("source-package-cannot-queue-gated-live-run-request")
        if capabilities.get("canExecuteLiveNavigation") is not False:
            blockers.append("source-package-live-execution-must-remain-false")
        if safe_mapping(package_payload.get("safety")).get("targetMemoryBytesRead") is True:
            warnings.append("source-package-used-read-only-target-memory-refresh")

    request = build_execution_request(args, package_path, package_payload)
    if errors:
        status = "failed"
        verdict = "navigation-live-run-request-failed"
    elif blockers:
        status = "blocked"
        verdict = "navigation-live-run-request-blocked"
    else:
        status = "passed"
        verdict = "navigation-live-run-request-queued-for-gated-review"

    safety = base_safety()
    safety.update(
        {
            "readOnlySavedJson": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "liveRunRequestOnly": True,
            "routeControlAuthorized": False,
            "routeRunnerInvoked": False,
        }
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "contractVersion": REQUEST_CONTRACT_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(root),
        "input": {
            "downstreamPackageJson": str(package_path) if package_path else None,
            "requestedMode": str(args.requested_mode),
            "requestedBy": str(args.requested_by),
            "requestId": args.request_id,
        },
        "request": request,
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
    parser = argparse.ArgumentParser(description="Create a saved gated live-run request without executing movement")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--downstream-package-json", help="Saved navigation downstream package summary; defaults to newest")
    parser.add_argument("--request-id")
    parser.add_argument("--requested-by", default="external-consumer")
    parser.add_argument(
        "--requested-mode",
        default="continuous-route-run",
        choices=["continuous-route-run", "single-route-step", "preview-only"],
    )
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
