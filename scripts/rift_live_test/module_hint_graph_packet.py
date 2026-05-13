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


def module_rva(value: Any, module_base: Any) -> str | None:
    value_int = parse_int(value)
    base_int = parse_int(module_base)
    if value_int is None or base_int is None or value_int < base_int:
        return None
    delta = value_int - base_int
    if delta > 0x10000000:
        return None
    return hex_int(delta)


def node_id(kind: str, address: Any) -> str:
    return f"{kind}:{norm_hex(address) or address}"


def choose_top_rva(occurrence_summary: Mapping[str, Any], requested_rva: str | None) -> Mapping[str, Any]:
    target = norm_hex(requested_rva) if requested_rva else None
    rows = [row for row in safe_list(occurrence_summary.get("rvas")) if isinstance(row, Mapping)]
    if target:
        for row in rows:
            if norm_hex(row.get("rva")) == target:
                return row
        raise ValueError(f"RVA {target} not found in occurrence summary")
    top = occurrence_summary.get("topRva")
    if isinstance(top, Mapping):
        return top
    if rows:
        return rows[0]
    raise ValueError("occurrence summary has no top RVA")


def choose_primary_sample(rva_row: Mapping[str, Any]) -> Mapping[str, Any]:
    samples = [sample for sample in safe_list(rva_row.get("sampleOccurrences")) if isinstance(sample, Mapping)]
    if not samples:
        raise ValueError("top RVA has no sample occurrences")
    ranked = sorted(
        samples,
        key=lambda sample: (
            0 if "ownerWindowModulePointers" in safe_list(sample.get("sourceLists")) else 1,
            abs(sample.get("offsetFromOwnerInt")) if isinstance(sample.get("offsetFromOwnerInt"), int) else 1_000_000,
            str(sample.get("artifactPath")),
        ),
    )
    return ranked[0]


def find_parent_slot(parent_summary: Mapping[str, Any], owner_slot: Any) -> Mapping[str, Any] | None:
    target = norm_hex(owner_slot)
    for slot in safe_list(parent_summary.get("slots")):
        if isinstance(slot, Mapping) and norm_hex(slot.get("ownerSlot")) == target:
            return slot
    return None


def choose_exact_owner(slot: Mapping[str, Any], player_label_fragment: str) -> Mapping[str, Any] | None:
    targets = [target for target in safe_list(slot.get("exactTargets")) if isinstance(target, Mapping)]
    for target in targets:
        if player_label_fragment.lower() in str(target.get("label")).lower():
            return target
    return targets[0] if targets else None


def find_owner_graph(owner_graph_summary: Mapping[str, Any], owner_base: Any) -> Mapping[str, Any] | None:
    target = norm_hex(owner_base)
    for owner in safe_list(owner_graph_summary.get("owners")):
        if isinstance(owner, Mapping) and norm_hex(owner.get("ownerBase")) == target:
            return owner
    return None


def find_owner_instance(owner_instance_summary: Mapping[str, Any], owner_base: Any) -> Mapping[str, Any] | None:
    target = norm_hex(owner_base)
    for instance in safe_list(owner_instance_summary.get("instances")):
        if isinstance(instance, Mapping) and norm_hex(instance.get("ownerBase")) == target:
            return instance
    return None


def add_node(nodes: dict[str, dict[str, Any]], kind: str, address: Any, **fields: Any) -> str:
    nid = node_id(kind, address)
    row = nodes.setdefault(nid, {"id": nid, "kind": kind, "address": norm_hex(address)})
    for key, value in fields.items():
        if value is not None:
            row[key] = value
    return nid


def add_edge(edges: list[dict[str, Any]], source: str, target: str, kind: str, **fields: Any) -> None:
    edge = {"source": source, "target": target, "kind": kind}
    edge.update({key: value for key, value in fields.items() if value is not None})
    if edge not in edges:
        edges.append(edge)


def build_graph(
    *,
    occurrence_summary: Mapping[str, Any],
    parent_summary: Mapping[str, Any],
    owner_graph_summary: Mapping[str, Any],
    owner_instance_summary: Mapping[str, Any],
    requested_rva: str | None = None,
    player_label_fragment: str = "player",
) -> dict[str, Any]:
    rva_row = choose_top_rva(occurrence_summary, requested_rva)
    sample = choose_primary_sample(rva_row)
    module_base = sample.get("moduleBase")
    rva = norm_hex(rva_row.get("rva"))
    parent_slot = find_parent_slot(parent_summary, sample.get("ownerAddress"))
    exact_owner = choose_exact_owner(parent_slot, player_label_fragment) if parent_slot else None
    owner_base = exact_owner.get("address") if exact_owner else None
    owner_graph = find_owner_graph(owner_graph_summary, owner_base) if owner_base else None
    owner_instance = find_owner_instance(owner_instance_summary, owner_base) if owner_base else None

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    module_node = add_node(
        nodes,
        "module-rva",
        rva,
        moduleName=sample.get("moduleName"),
        moduleBase=module_base,
        occurrenceCount=rva_row.get("occurrenceCount"),
        score=rva_row.get("score"),
    )
    entry_node = add_node(
        nodes,
        "module-hint-entry",
        sample.get("entryAddress"),
        value=sample.get("entryValue"),
        offsetFromOwner=sample.get("offsetFromOwner"),
        artifactPath=sample.get("artifactPath"),
    )
    parent_node = add_node(
        nodes,
        "parent-slot",
        sample.get("ownerAddress"),
        label="selected-parent-slot",
        ownerWindowModuleRvas=parent_slot.get("ownerWindowModuleRvas") if parent_slot else None,
    )
    add_edge(edges, module_node, entry_node, "observed-at", artifactPath=sample.get("artifactPath"))
    add_edge(edges, entry_node, parent_node, "relative-to-parent-slot", offsetFromOwner=sample.get("offsetFromOwner"))

    owner_node = None
    coord_storage_node = None
    coord_node = None
    if exact_owner:
        owner_node = add_node(
            nodes,
            "owner",
            exact_owner.get("address"),
            label=exact_owner.get("label"),
            exactTargetCount=exact_owner.get("count"),
            classification=owner_graph.get("classification") if owner_graph else None,
        )
        add_edge(edges, parent_node, owner_node, "points-to-owner", evidence="exact-target")
    if owner_graph:
        coord_node = add_node(
            nodes,
            "coord-pointer",
            owner_graph.get("coordPointer"),
            label=owner_graph.get("coordPointerCandidateLabel"),
            vec3=owner_graph.get("coordPointerVec3"),
            candidate=owner_graph.get("coordPointerIsCandidate"),
        )
        coord_storage_node = add_node(nodes, "coord-pointer-storage", owner_graph.get("coordPointerStorage"))
        add_edge(edges, owner_node, coord_storage_node, "coord-pointer-field", offset="0x10")
        add_edge(edges, coord_storage_node, coord_node, "stores-pointer")
        add_edge(edges, owner_node, coord_node, "owner-to-coord-pointer", offset="0x10")

    module_field_rows: list[dict[str, Any]] = []
    if owner_instance:
        for qword in safe_list(owner_instance.get("qwords")):
            if not isinstance(qword, Mapping):
                continue
            qword_rva = module_rva(qword.get("value"), module_base)
            if not qword_rva:
                continue
            field_node = add_node(
                nodes,
                "module-rva",
                qword_rva,
                moduleName=sample.get("moduleName"),
                moduleBase=module_base,
            )
            if owner_node:
                add_edge(
                    edges,
                    owner_node,
                    field_node,
                    "owner-module-pointer-field",
                    offset=qword.get("offset"),
                    storage=qword.get("address"),
                    value=qword.get("value"),
                )
            module_field_rows.append(
                {
                    "offset": qword.get("offset"),
                    "storage": qword.get("address"),
                    "value": qword.get("value"),
                    "rva": qword_rva,
                    "matchesSelectedRva": norm_hex(qword_rva) == rva,
                }
            )

    blockers: list[str] = []
    if not parent_slot:
        blockers.append("selected-occurrence-parent-slot-not-found")
    if not exact_owner:
        blockers.append("parent-slot-owner-target-not-found")
    if not owner_graph:
        blockers.append("owner-parent-graph-row-not-found")
    if not owner_instance:
        blockers.append("owner-instance-row-not-found")
    unresolved = [
        "module-or-static-root-above-parent-slot-not-resolved",
        "restart-validation-missing",
        "api-now-vs-memory-now-proof-missing",
        "same-target-proofonly-blocked",
    ]

    return {
        "selectedRva": rva,
        "selectedOccurrence": sample,
        "parentSlot": dict(parent_slot) if parent_slot else None,
        "owner": dict(exact_owner) if exact_owner else None,
        "ownerGraph": dict(owner_graph) if owner_graph else None,
        "ownerInstance": {
            "ownerBase": owner_instance.get("ownerBase"),
            "coordPointer": owner_instance.get("coordPointer"),
            "coordPointerStorage": owner_instance.get("coordPointerStorage"),
            "coordPointerCandidate": owner_instance.get("coordPointerCandidate"),
            "modulePointerFields": module_field_rows,
        }
        if owner_instance
        else None,
        "nodes": list(nodes.values()),
        "edges": edges,
        "candidateChain": {
            "status": "candidate" if not blockers else "blocked",
            "path": [
                {"kind": "module-rva", "value": rva},
                {"kind": "module-hint-entry", "value": sample.get("entryAddress"), "offsetFromParentSlot": sample.get("offsetFromOwner")},
                {"kind": "parent-slot", "value": sample.get("ownerAddress")},
                {"kind": "owner", "value": owner_base},
                {
                    "kind": "coord-pointer",
                    "value": owner_graph.get("coordPointer") if owner_graph else None,
                    "storage": owner_graph.get("coordPointerStorage") if owner_graph else None,
                    "fieldOffset": "0x10" if owner_graph else None,
                },
            ],
        },
        "blockers": blockers,
        "unresolvedGaps": unresolved,
    }


def build_summary(
    *,
    occurrence_path: Path,
    parent_path: Path,
    owner_graph_path: Path,
    owner_instance_path: Path,
    requested_rva: str | None,
    player_label_fragment: str,
) -> dict[str, Any]:
    graph = build_graph(
        occurrence_summary=load_json_object(occurrence_path),
        parent_summary=load_json_object(parent_path),
        owner_graph_summary=load_json_object(owner_graph_path),
        owner_instance_summary=load_json_object(owner_instance_path),
        requested_rva=requested_rva,
        player_label_fragment=player_label_fragment,
    )
    blockers = list(graph.get("blockers") or [])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "module-hint-graph-packet",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": [
            "Offline graph packet only; this does not read live target memory or prove a static chain.",
            "Graph edges are candidate evidence until restart validation and API-now-vs-memory-now proof pass.",
        ],
        "inputs": {
            "occurrenceSummaryJson": str(occurrence_path.resolve()),
            "parentSlotSummaryJson": str(parent_path.resolve()),
            "ownerParentGraphJson": str(owner_graph_path.resolve()),
            "ownerInstanceSummaryJson": str(owner_instance_path.resolve()),
            "requestedRva": requested_rva,
        },
        "counts": {"nodeCount": len(graph.get("nodes") or []), "edgeCount": len(graph.get("edges") or [])},
        "graph": graph,
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
            "recommendedAction": "Use this graph to drive an offline structural-signature search for owners combining module fields and coord-pointer shape.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    graph = safe_mapping(summary.get("graph"))
    chain = safe_mapping(graph.get("candidateChain"))
    lines = [
        "# Module hint graph packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Selected RVA: `{graph.get('selectedRva')}`",
        f"- Nodes: `{safe_mapping(summary.get('counts')).get('nodeCount')}`",
        f"- Edges: `{safe_mapping(summary.get('counts')).get('edgeCount')}`",
        "",
        "## Candidate chain",
        "",
        "| Step | Kind | Value | Extra |",
        "|---:|---|---|---|",
    ]
    for index, step in enumerate(safe_list(chain.get("path")), start=1):
        if not isinstance(step, Mapping):
            continue
        extra = ", ".join(f"{key}={value}" for key, value in step.items() if key not in {"kind", "value"} and value is not None)
        lines.append(f"| {index} | `{step.get('kind')}` | `{step.get('value')}` | `{extra}` |")
    lines.extend(["", "## Edges", "", "| Source | Kind | Target | Detail |", "|---|---|---|---|"])
    for edge in safe_list(graph.get("edges")):
        if not isinstance(edge, Mapping):
            continue
        detail = ", ".join(f"{key}={value}" for key, value in edge.items() if key not in {"source", "kind", "target"})
        lines.append(f"| `{edge.get('source')}` | `{edge.get('kind')}` | `{edge.get('target')}` | `{detail}` |")
    owner_instance = safe_mapping(graph.get("ownerInstance"))
    if owner_instance.get("modulePointerFields"):
        lines.extend(["", "## Owner module-pointer fields", "", "| Offset | Storage | Value | RVA | Selected |", "|---:|---|---|---|---:|"])
        for row in safe_list(owner_instance.get("modulePointerFields")):
            if isinstance(row, Mapping):
                lines.append(
                    f"| `{row.get('offset')}` | `{row.get('storage')}` | `{row.get('value')}` | `{row.get('rva')}` | "
                    f"`{str(row.get('matchesSelectedRva')).lower()}` |"
                )
    if graph.get("unresolvedGaps"):
        lines.extend(["", "## Unresolved gaps"])
        lines.extend(f"- `{gap}`" for gap in safe_list(graph.get("unresolvedGaps")))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an offline graph packet for a module hint -> owner -> coord pointer chain.")
    parser.add_argument("--occurrence-summary-json", type=Path, required=True)
    parser.add_argument("--parent-slot-summary-json", type=Path, required=True)
    parser.add_argument("--owner-parent-graph-json", type=Path, required=True)
    parser.add_argument("--owner-instance-summary-json", type=Path, required=True)
    parser.add_argument("--rva")
    parser.add_argument("--player-label-fragment", default="player")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"module-hint-graph-packet-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(
        occurrence_path=args.occurrence_summary_json,
        parent_path=args.parent_slot_summary_json,
        owner_graph_path=args.owner_parent_graph_json,
        owner_instance_path=args.owner_instance_summary_json,
        requested_rva=args.rva,
        player_label_fragment=args.player_label_fragment,
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
