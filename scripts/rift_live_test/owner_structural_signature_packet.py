from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_list, safe_mapping
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_MODULE_WINDOW_LIMIT = 0x10000000


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value), 0)
    except ValueError:
        return None


def hex_int(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def norm_hex(value: Any) -> str | None:
    parsed = parse_int(value)
    if parsed is not None:
        return hex_int(parsed)
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def module_rva(value: Any, module_base: Any, *, limit: int = DEFAULT_MODULE_WINDOW_LIMIT) -> str | None:
    value_int = parse_int(value)
    base_int = parse_int(module_base)
    if value_int is None or base_int is None or value_int < base_int:
        return None
    delta = value_int - base_int
    if delta > limit:
        return None
    return hex_int(delta)


def requested_rvas(values: Sequence[str]) -> list[str]:
    rvas: list[str] = []
    for value in values:
        normalized = norm_hex(value)
        if normalized and normalized not in rvas:
            rvas.append(normalized)
    return rvas


def owner_graph_by_base(owner_graph_summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for owner in safe_list(owner_graph_summary.get("owners")):
        if isinstance(owner, Mapping):
            owner_base = norm_hex(owner.get("ownerBase"))
            if owner_base:
                rows[owner_base] = owner
    return rows


def parent_slot_by_owner(parent_slot_summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for slot in safe_list(parent_slot_summary.get("slots")):
        if not isinstance(slot, Mapping):
            continue
        for target in safe_list(slot.get("exactTargets")):
            if isinstance(target, Mapping):
                address = norm_hex(target.get("address"))
                if address:
                    rows[address] = slot
    return rows


def module_fields(instance: Mapping[str, Any], module_base: str | None) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for qword in safe_list(instance.get("qwords")):
        if not isinstance(qword, Mapping):
            continue
        rva = module_rva(qword.get("value"), module_base)
        if rva is None:
            continue
        fields.append(
            {
                "offset": qword.get("offset"),
                "storage": qword.get("address"),
                "value": qword.get("value"),
                "rva": rva,
            }
        )
    return fields


def score_owner(
    *,
    instance: Mapping[str, Any],
    graph_owner: Mapping[str, Any] | None,
    parent_slot: Mapping[str, Any] | None,
    fields: Sequence[Mapping[str, Any]],
    target_rvas: Sequence[str],
) -> tuple[int, list[str]]:
    field_rvas = {str(field.get("rva")) for field in fields}
    field_by_rva = {str(field.get("rva")): field for field in fields}
    score = 0
    reasons: list[str] = []
    matched = [rva for rva in target_rvas if rva in field_rvas]
    if matched:
        score += 20 * len(matched)
        reasons.append(f"matched-module-rvas={len(matched)}")
    if set(target_rvas).issubset(field_rvas):
        score += 35
        reasons.append("complete-module-field-signature")
    if field_by_rva.get("0x26AAE70", {}).get("offset") == "0x0":
        score += 15
        reasons.append("type-marker-at-owner-base")
    if field_by_rva.get("0x263E950", {}).get("offset") == "0xE0":
        score += 25
        reasons.append("selected-rva-at-0xE0")
    if instance.get("coordPointerOffset") == "0x10":
        score += 15
        reasons.append("coord-pointer-at-0x10")
    if instance.get("coordPointerIsCandidate"):
        score += 40
        reasons.append("coord-pointer-is-stable-candidate")
    if instance.get("coordPointerVec3"):
        score += 25
        reasons.append("coord-pointer-vec3-readable")
    if graph_owner and graph_owner.get("parentRefCount") == 1:
        score += 10
        reasons.append("single-parent-ref")
    if graph_owner and graph_owner.get("classification") == "candidate-owner-heap-terminal":
        score += 10
        reasons.append("candidate-owner-heap-terminal")
    if parent_slot and parent_slot.get("ownerWindowModulePointerCount"):
        score += 15
        reasons.append("parent-slot-has-module-hint")
    if not instance.get("coordPointerIsCandidate"):
        score -= 20
        reasons.append("coord-pointer-not-stable-candidate")
    return score, reasons


def summarize_owner(
    *,
    instance: Mapping[str, Any],
    graph_owner: Mapping[str, Any] | None,
    parent_slot: Mapping[str, Any] | None,
    target_rvas: Sequence[str],
    module_base: str | None,
) -> dict[str, Any]:
    fields = module_fields(instance, module_base)
    field_rvas = {str(field.get("rva")) for field in fields}
    score, reasons = score_owner(
        instance=instance,
        graph_owner=graph_owner,
        parent_slot=parent_slot,
        fields=fields,
        target_rvas=target_rvas,
    )
    parent_refs = safe_list(graph_owner.get("parentRefs") if graph_owner else None)
    parent_ref = parent_refs[0] if parent_refs and isinstance(parent_refs[0], Mapping) else None
    return {
        "ownerBase": instance.get("ownerBase"),
        "score": score,
        "scoreReasons": reasons,
        "matchedRvas": [rva for rva in target_rvas if rva in field_rvas],
        "missingRvas": [rva for rva in target_rvas if rva not in field_rvas],
        "modulePointerFields": fields,
        "coordPointerOffset": instance.get("coordPointerOffset"),
        "coordPointerStorage": instance.get("coordPointerStorage"),
        "coordPointer": instance.get("coordPointer"),
        "coordPointerIsCandidate": instance.get("coordPointerIsCandidate"),
        "coordPointerCandidate": instance.get("coordPointerCandidate"),
        "coordPointerVec3": instance.get("coordPointerVec3"),
        "parentRef": dict(parent_ref) if parent_ref else None,
        "parentSlot": {
            "ownerSlot": parent_slot.get("ownerSlot"),
            "classification": parent_slot.get("classification"),
            "ownerWindowModuleRvas": parent_slot.get("ownerWindowModuleRvas"),
            "ownerWindowModulePointerCount": parent_slot.get("ownerWindowModulePointerCount"),
            "regionMatchCount": parent_slot.get("regionMatchCount"),
        }
        if parent_slot
        else None,
        "ownerGraphClassification": graph_owner.get("classification") if graph_owner else None,
    }


def build_summary(
    *,
    owner_instance_path: Path,
    owner_graph_path: Path,
    parent_slot_path: Path,
    target_rvas: Sequence[str],
    module_base: str | None,
) -> dict[str, Any]:
    owner_instance_summary = load_json_object(owner_instance_path)
    owner_graph_summary = load_json_object(owner_graph_path)
    parent_slot_summary = load_json_object(parent_slot_path)
    graph_by_owner = owner_graph_by_base(owner_graph_summary)
    slot_by_owner = parent_slot_by_owner(parent_slot_summary)
    owners: list[dict[str, Any]] = []
    for instance in safe_list(owner_instance_summary.get("instances")):
        if not isinstance(instance, Mapping):
            continue
        owner_base = norm_hex(instance.get("ownerBase"))
        owners.append(
            summarize_owner(
                instance=instance,
                graph_owner=graph_by_owner.get(owner_base or ""),
                parent_slot=slot_by_owner.get(owner_base or ""),
                target_rvas=target_rvas,
                module_base=module_base,
            )
        )
    owners.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("ownerBase"))))
    blockers = [] if owners else ["no-owner-instances-found"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "owner-structural-signature-packet",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": [
            "Offline structural signature ranking only; this does not read live target memory or prove a static chain.",
            "Owner scores rank current-session candidates and still require restart validation plus API-now-vs-memory-now proof.",
        ],
        "inputs": {
            "ownerInstanceSummaryJson": str(owner_instance_path.resolve()),
            "ownerParentGraphJson": str(owner_graph_path.resolve()),
            "parentSlotSummaryJson": str(parent_slot_path.resolve()),
            "targetRvas": list(target_rvas),
            "moduleBase": module_base,
        },
        "counts": {
            "ownerCount": len(owners),
            "targetRvaCount": len(target_rvas),
            "completeSignatureOwnerCount": sum(1 for owner in owners if not owner.get("missingRvas")),
            "stableCoordCandidateOwnerCount": sum(1 for owner in owners if owner.get("coordPointerIsCandidate")),
        },
        "topOwner": owners[0] if owners else None,
        "owners": owners,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
            "candidateOnly": True,
            "movementProofEligible": False,
        },
        "next": {
            "recommendedAction": "Use the top owner's structural signature to search parent-slot containers and static roots; do not promote until proof gates pass.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    lines = [
        "# Owner structural signature packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Owners: `{counts.get('ownerCount')}`",
        f"- Complete signature owners: `{counts.get('completeSignatureOwnerCount')}`",
        f"- Stable coord-candidate owners: `{counts.get('stableCoordCandidateOwnerCount')}`",
        "",
        "| Rank | Score | Owner | Matched RVAs | Missing RVAs | Coord candidate | Parent slot | Reasons |",
        "|---:|---:|---|---|---|---:|---|---|",
    ]
    for index, owner in enumerate(safe_list(summary.get("owners")), start=1):
        if not isinstance(owner, Mapping):
            continue
        parent_slot = safe_mapping(owner.get("parentSlot"))
        reasons = ", ".join(str(reason) for reason in safe_list(owner.get("scoreReasons")))
        matched = ", ".join(str(rva) for rva in safe_list(owner.get("matchedRvas")))
        missing = ", ".join(str(rva) for rva in safe_list(owner.get("missingRvas")))
        lines.append(
            f"| {index} | `{owner.get('score')}` | `{owner.get('ownerBase')}` | `{matched}` | `{missing}` | "
            f"`{str(owner.get('coordPointerIsCandidate')).lower()}` | `{parent_slot.get('ownerSlot')}` | {reasons} |"
        )
    top = safe_mapping(summary.get("topOwner"))
    if top:
        lines.extend(
            [
                "",
                "## Top owner module fields",
                "",
                "| Offset | Storage | Value | RVA |",
                "|---:|---|---|---|",
            ]
        )
        for field in safe_list(top.get("modulePointerFields")):
            if isinstance(field, Mapping):
                lines.append(f"| `{field.get('offset')}` | `{field.get('storage')}` | `{field.get('value')}` | `{field.get('rva')}` |")
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank owner objects by module-field and coord-pointer structural signatures.")
    parser.add_argument("--owner-instance-summary-json", type=Path, required=True)
    parser.add_argument("--owner-parent-graph-json", type=Path, required=True)
    parser.add_argument("--parent-slot-summary-json", type=Path, required=True)
    parser.add_argument("--module-base", required=True)
    parser.add_argument("--target-rva", action="append", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"owner-structural-signature-packet-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(
        owner_instance_path=args.owner_instance_summary_json,
        owner_graph_path=args.owner_parent_graph_json,
        parent_slot_path=args.parent_slot_summary_json,
        target_rvas=requested_rvas(args.target_rva),
        module_base=norm_hex(args.module_base),
    )
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(summary_json),
        "summaryMarkdown": str(summary_md),
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json}")
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
