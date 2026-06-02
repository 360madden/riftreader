from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-schema-validation"
SCHEMA_DIR = Path("docs") / "schemas" / "navigation"

SCHEMA_FILES = {
    "navigation-consumer-state": "navigation-consumer-state.schema.json",
    "normalized-waypoints": "normalized-waypoints.schema.json",
    "static-owner-continuous-route-sequence": "static-owner-continuous-route-sequence.schema.json",
    "static-owner-continuous-route-sequence-contract-report": (
        "static-owner-continuous-route-sequence-contract-report.schema.json"
    ),
    "navigation-waypoint-readiness": "navigation-waypoint-readiness.schema.json",
    "navigation-consumer-demo": "navigation-consumer-demo.schema.json",
    "navigation-consumer-refresh": "navigation-consumer-refresh.schema.json",
}

KIND_TO_SCHEMA_KEY = {
    "riftreader-navigation-consumer-state": "navigation-consumer-state",
    "riftreader-normalized-navigation-waypoints": "normalized-waypoints",
    "static-owner-continuous-route-sequence": "static-owner-continuous-route-sequence",
    "static-owner-continuous-route-sequence-contract-report": (
        "static-owner-continuous-route-sequence-contract-report"
    ),
    "riftreader-navigation-waypoint-readiness": "navigation-waypoint-readiness",
    "riftreader-navigation-consumer-demo": "navigation-consumer-demo",
    "riftreader-navigation-consumer-refresh": "navigation-consumer-refresh",
}


def schema_path(root: Path, key: str) -> Path:
    if key not in SCHEMA_FILES:
        raise ValueError(f"unknown-schema-key:{key}")
    return root / SCHEMA_DIR / SCHEMA_FILES[key]


def infer_schema_key(payload: Mapping[str, Any]) -> str | None:
    kind = payload.get("kind")
    if isinstance(kind, str) and kind in KIND_TO_SCHEMA_KEY:
        return KIND_TO_SCHEMA_KEY[kind]
    provenance_kind = safe_mapping(payload.get("provenance")).get("kind")
    if isinstance(provenance_kind, str) and provenance_kind in KIND_TO_SCHEMA_KEY:
        return KIND_TO_SCHEMA_KEY[provenance_kind]
    return None


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, Mapping)
    return True


def validate_value(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, str(item)) for item in expected_types):
            joined = "|".join(str(item) for item in expected_types)
            return [f"{path}:type-mismatch:expected={joined}:actual={json_type_name(value)}"]

    if "const" in schema and value != schema.get("const"):
        errors.append(f"{path}:const-mismatch:expected={schema.get('const')!r}:actual={value!r}")
    if "enum" in schema and value not in schema.get("enum", []):
        errors.append(f"{path}:enum-mismatch:actual={value!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}:minimum:{value}<{minimum}")

    if isinstance(value, Mapping):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}.{key}:required-missing")
        properties = schema.get("properties", {})
        if isinstance(properties, Mapping):
            for key, sub_schema in properties.items():
                if key in value and isinstance(sub_schema, Mapping):
                    errors.extend(validate_value(value[key], sub_schema, f"{path}.{key}"))

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                errors.extend(validate_value(item, item_schema, f"{path}[{index}]"))

    return errors


def validate_payload(payload: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_value(payload, schema)
    return {
        "status": "passed" if not errors else "blocked",
        "errorCount": len(errors),
        "errors": errors,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-schema-validation-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path
    safety = base_safety()
    safety["targetMemoryBytesRead"] = False
    safety["targetMemoryBytesWritten"] = False
    safety["readOnlySavedJson"] = True

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "repoRoot": str(root),
        "inputJson": str(input_path),
        "inputKind": None,
        "schemaKey": args.schema_key,
        "schemaJson": None,
        "validation": {},
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    try:
        payload = load_json_object(input_path)
        summary["inputKind"] = payload.get("kind") or safe_mapping(payload.get("provenance")).get("kind")
        key = args.schema_key or infer_schema_key(payload)
        if not key:
            summary["status"] = "blocked"
            summary["blockers"].append("schema-key-not-provided-and-kind-not-recognized")
            return summary
        schema_file = schema_path(root, key)
        schema = load_json_object(schema_file)
        validation = validate_payload(payload, schema)
        summary["schemaKey"] = key
        summary["schemaJson"] = str(schema_file)
        summary["validation"] = validation
        summary["blockers"].extend(validation["errors"])
        summary["status"] = "passed" if validation["status"] == "passed" else "blocked"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    validation = safe_mapping(summary.get("validation"))
    lines = [
        "# Navigation schema validation",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Input: `{summary.get('inputJson')}`",
        f"Schema key: `{summary.get('schemaKey')}`",
        f"Schema JSON: `{summary.get('schemaJson')}`",
        f"Validation error count: `{validation.get('errorCount')}`",
        "",
    ]
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
        lines.append("")
    if summary.get("errors"):
        lines.extend(["## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
        lines.append("")
    return "\n".join(lines) + "\n"


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    validation = safe_mapping(summary.get("validation"))
    return {
        "status": summary.get("status"),
        "kind": summary.get("kind"),
        "inputJson": summary.get("inputJson"),
        "inputKind": summary.get("inputKind"),
        "schemaKey": summary.get("schemaKey"),
        "schemaJson": summary.get("schemaJson"),
        "validationStatus": validation.get("status"),
        "validationErrorCount": validation.get("errorCount"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate saved RiftReader navigation JSON against tracked schemas")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--input", required=True, help="Saved JSON artifact to validate")
    parser.add_argument("--schema-key", choices=sorted(SCHEMA_FILES), help="Schema key; inferred from kind when omitted")
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
