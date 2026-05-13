from __future__ import annotations

import argparse
import json
from collections import Counter
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


def parse_offset(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value), 0)
    except ValueError:
        return None


def exact_target_labels(slot: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    for target in safe_list(slot.get("exactTargets")):
        if isinstance(target, Mapping):
            label = target.get("label")
            if label:
                labels.append(str(label))
    return labels


def classify_hint(*, slot: Mapping[str, Any], offset_from_owner: int | None, player_label_fragment: str) -> str:
    labels = exact_target_labels(slot)
    is_player_slot = any(player_label_fragment.lower() in label.lower() for label in labels)
    near_owner = offset_from_owner is not None and abs(offset_from_owner) <= 0x80
    if is_player_slot and near_owner:
        return "player-candidate-near-owner"
    if is_player_slot:
        return "player-candidate-module-hint"
    if near_owner:
        return "sibling-near-owner-module-hint"
    return "sibling-module-hint"


def extract_module_hints(
    parent_summary: Mapping[str, Any],
    *,
    player_label_fragment: str = "player",
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for slot in safe_list(parent_summary.get("slots")):
        if not isinstance(slot, Mapping):
            continue
        labels = exact_target_labels(slot)
        for entry in safe_list(slot.get("ownerWindowInteresting")):
            if not isinstance(entry, Mapping):
                continue
            classification = safe_mapping(entry.get("classification"))
            module_pointer = safe_mapping(classification.get("modulePointer"))
            rva = module_pointer.get("rva")
            if not rva:
                continue
            offset_from_owner = parse_offset(entry.get("offsetFromOwner"))
            hints.append(
                {
                    "rva": str(rva),
                    "moduleName": module_pointer.get("moduleName"),
                    "moduleBase": module_pointer.get("moduleBase"),
                    "ownerSlot": slot.get("ownerSlot"),
                    "ownerRegionBase": slot.get("ownerRegionBase"),
                    "targetWindowBase": slot.get("targetWindowBase"),
                    "slotClassification": slot.get("classification"),
                    "exactTargetLabels": labels,
                    "entryAddress": entry.get("address"),
                    "entryValue": entry.get("value"),
                    "offsetFromOwner": entry.get("offsetFromOwner"),
                    "offsetFromOwnerInt": offset_from_owner,
                    "offsetFromReadBase": entry.get("offsetFromReadBase"),
                    "hintClassification": classify_hint(
                        slot=slot,
                        offset_from_owner=offset_from_owner,
                        player_label_fragment=player_label_fragment,
                    ),
                }
            )
    return hints


def score_hint(
    hint: Mapping[str, Any],
    rva_counts: Mapping[str, int],
    *,
    player_label_fragment: str = "player",
    near_owner_bytes: int = 0x80,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    labels = [str(label).lower() for label in safe_list(hint.get("exactTargetLabels"))]
    if any(player_label_fragment.lower() in label for label in labels):
        score += 100
        reasons.append("player-candidate-slot")
    if hint.get("slotClassification") == "owner-slot-with-module-hint":
        score += 30
        reasons.append("slot-has-exact-owner-and-module-hint")
    offset = hint.get("offsetFromOwnerInt")
    if isinstance(offset, int) and abs(offset) <= near_owner_bytes:
        score += 25
        reasons.append(f"near-owner-slot<=0x{near_owner_bytes:X}")
    if rva_counts.get(str(hint.get("rva")), 0) > 1:
        score += 20
        reasons.append("rva-repeats-across-slots")
    if hint.get("hintClassification") == "player-candidate-near-owner":
        score += 25
        reasons.append("player-near-owner-combined")
    return score, reasons


def build_summary(
    parent_summary_path: Path,
    parent_summary: Mapping[str, Any],
    *,
    player_label_fragment: str = "player",
    near_owner_bytes: int = 0x80,
) -> dict[str, Any]:
    hints = extract_module_hints(parent_summary, player_label_fragment=player_label_fragment)
    rva_counts = Counter(str(hint.get("rva")) for hint in hints)
    ranked: list[dict[str, Any]] = []
    for hint in hints:
        score, reasons = score_hint(
            hint,
            rva_counts,
            player_label_fragment=player_label_fragment,
            near_owner_bytes=near_owner_bytes,
        )
        row = dict(hint)
        row["score"] = score
        row["scoreReasons"] = reasons
        row["rvaObservedSlotCount"] = rva_counts[str(hint.get("rva"))]
        ranked.append(row)
    ranked.sort(
        key=lambda row: (
            -int(row.get("score") or 0),
            abs(row.get("offsetFromOwnerInt")) if isinstance(row.get("offsetFromOwnerInt"), int) else 1_000_000,
            str(row.get("rva")),
            str(row.get("ownerSlot")),
        )
    )
    top = ranked[0] if ranked else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "parent-slot-module-hint-rank",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ranked else "blocked",
        "blockers": [] if ranked else ["no-module-hints-found"],
        "warnings": [
            "Offline artifact ranking only; this does not resolve a static chain or promote movement truth.",
            "High scores identify source-chain investigation priority, not proof.",
        ],
        "source": {
            "parentSummaryJson": str(parent_summary_path.resolve()),
            "parentSummaryGeneratedAtUtc": parent_summary.get("generatedAtUtc"),
        },
        "counts": {
            "hintCount": len(ranked),
            "uniqueRvaCount": len(rva_counts),
            "sharedRvaCount": sum(1 for count in rva_counts.values() if count > 1),
            "playerCandidateHintCount": sum(
                1
                for row in ranked
                if any(player_label_fragment.lower() in str(label).lower() for label in safe_list(row.get("exactTargetLabels")))
            ),
        },
        "topHint": top,
        "hints": ranked,
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
            "recommendedAction": "Inspect the highest-ranked module RVA neighborhood and matching owner-slot layout offline before any live proof attempt.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    lines = [
        "# Parent slot module-hint rank",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Hints: `{counts.get('hintCount')}`",
        f"- Unique RVAs: `{counts.get('uniqueRvaCount')}`",
        f"- Player-candidate hints: `{counts.get('playerCandidateHintCount')}`",
        "",
        "| Rank | Score | RVA | Owner slot | Target labels | Offset from owner | Reasons |",
        "|---:|---:|---|---|---|---:|---|",
    ]
    for index, hint in enumerate(safe_list(summary.get("hints")), start=1):
        if not isinstance(hint, Mapping):
            continue
        labels = ", ".join(str(label) for label in safe_list(hint.get("exactTargetLabels")))
        reasons = ", ".join(str(reason) for reason in safe_list(hint.get("scoreReasons")))
        lines.append(
            f"| {index} | `{hint.get('score')}` | `{hint.get('rva')}` | `{hint.get('ownerSlot')}` | "
            f"`{labels}` | `{hint.get('offsetFromOwner')}` | {reasons} |"
        )
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in summary.get("warnings", []))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary.get("blockers", []))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank module-pointer hints found near parent owner slots.")
    parser.add_argument("--parent-summary-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--player-label-fragment", default="player")
    parser.add_argument("--near-owner-bytes", type=lambda value: int(value, 0), default=0x80)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"parent-slot-module-hint-rank-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(
        args.parent_summary_json,
        load_json_object(args.parent_summary_json),
        player_label_fragment=args.player_label_fragment,
        near_owner_bytes=args.near_owner_bytes,
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
