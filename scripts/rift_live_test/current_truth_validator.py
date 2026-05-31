from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = [
    "schemaVersion",
    "kind",
    "updatedAtUtc",
    "status",
    "target",
    "liveReferenceSurface",
    "movementGate",
    "bestCurrentCandidate",
    "staleOrInvalid",
    "currentBlockers",
    "canonicalArtifacts",
    "nextRecommendedAction",
]

REQUIRED_TARGET = ["processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase"]
REQUIRED_CANDIDATE = ["candidateId", "addressHex", "candidateFile", "readbackSummary", "status"]
REQUIRED_LIVE_REFERENCE = ["authoritative", "status", "source", "view", "savedVariablesUse"]


def candidate_allows_empty_current(document: dict[str, Any], candidate: dict[str, Any]) -> bool:
    combined_status = " ".join(
        str(value or "").lower()
        for value in (
            document.get("status"),
            candidate.get("status"),
        )
    )
    return any(
        marker in combined_status
        for marker in (
            "no_current_candidate",
            "none_current",
            "reacquisition_required",
        )
    )


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_timestamp(value: str, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"missing-timestamp:{field}")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"invalid-timestamp:{field}:{value}")


def require_mapping(document: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        errors.append(f"missing-object:{key}")
        return {}
    return value


def require_list(document: dict[str, Any], key: str, errors: list[str], *, allow_empty: bool = False) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list) or (not value and not allow_empty):
        errors.append(f"missing-list:{key}")
        return []
    return value


def resolve_artifact(repo_root: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root / path


def iter_artifact_paths(document: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    live = document.get("liveReferenceSurface") if isinstance(document.get("liveReferenceSurface"), dict) else {}
    for key in ("latestPreflight", "latestReference", "latestMarkerDiagnostic", "latestAddonDiagnostic"):
        value = live.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    candidate = document.get("bestCurrentCandidate") if isinstance(document.get("bestCurrentCandidate"), dict) else {}
    for key in ("candidateFile", "readbackSummary"):
        value = candidate.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    pointer = document.get("latestPointerEvidence") if isinstance(document.get("latestPointerEvidence"), dict) else {}
    for key in ("boundedPointerScan", "ownerBatch"):
        value = pointer.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    artifacts = document.get("canonicalArtifacts") if isinstance(document.get("canonicalArtifacts"), dict) else {}
    for value in artifacts.values():
        if isinstance(value, str) and value:
            paths.append(value)
    return paths


def validate_truth(document: dict[str, Any], *, repo_root: Path, check_artifacts: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in document:
            errors.append(f"missing-top-level:{key}")

    if document.get("schemaVersion") != 1:
        errors.append(f"unsupported-schemaVersion:{document.get('schemaVersion')}")
    if document.get("kind") != "riftreader-current-truth":
        errors.append(f"unexpected-kind:{document.get('kind')}")
    parse_timestamp(str(document.get("updatedAtUtc", "")), "updatedAtUtc", errors)

    target = require_mapping(document, "target", errors)
    for key in REQUIRED_TARGET:
        if target.get(key) in (None, ""):
            errors.append(f"missing-target:{key}")

    live = require_mapping(document, "liveReferenceSurface", errors)
    for key in REQUIRED_LIVE_REFERENCE:
        if live.get(key) in (None, ""):
            errors.append(f"missing-live-reference:{key}")
    if str(live.get("savedVariablesUse", "")).lower() != "none":
        errors.append("live-reference-must-not-use-savedvariables")

    gate = require_mapping(document, "movementGate", errors)
    if not isinstance(gate.get("allowed"), bool):
        errors.append("movementGate.allowed-must-be-bool")
    if gate.get("allowed") is True and not gate.get("proofArtifact"):
        errors.append("movement-allowed-requires-proofArtifact")

    candidate = require_mapping(document, "bestCurrentCandidate", errors)
    allow_empty_current_candidate = candidate_allows_empty_current(document, candidate)
    for key in REQUIRED_CANDIDATE:
        if candidate.get(key) in (None, "") and not allow_empty_current_candidate:
            errors.append(f"missing-best-candidate:{key}")
    if gate.get("allowed") is False and "candidate" not in str(candidate.get("status", "")).lower() and not allow_empty_current_candidate:
        warnings.append("movement-blocked-but-candidate-status-does-not-say-candidate")

    require_list(document, "staleOrInvalid", errors)
    require_list(document, "currentBlockers", errors, allow_empty=True)

    if check_artifacts:
        for artifact in iter_artifact_paths(document):
            if not resolve_artifact(repo_root, artifact).exists():
                errors.append(f"artifact-missing:{artifact}")

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "artifactCount": len(iter_artifact_paths(document)),
    }


def load_truth(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError("truth JSON must contain an object")
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate RiftReader's compact current-truth JSON contract.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--truth-json", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--skip-artifact-exists", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root or repo_root_from_module()
    truth_path = args.truth_json if args.truth_json.is_absolute() else repo_root / args.truth_json
    result = validate_truth(
        load_truth(truth_path),
        repo_root=repo_root,
        check_artifacts=not args.skip_artifact_exists,
    )
    result["truthJson"] = str(truth_path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"current-truth validation: {result['status']}")
        if result["errors"]:
            print("errors:")
            for error in result["errors"]:
                print(f"- {error}")
        if result["warnings"]:
            print("warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
