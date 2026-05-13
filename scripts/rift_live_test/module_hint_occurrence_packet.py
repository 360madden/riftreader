from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
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


def norm_hex(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text.upper()


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value), 0)
    except ValueError:
        return None


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def target_labels(doc: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    for target in safe_list(doc.get("targets")):
        if isinstance(target, Mapping):
            label = target.get("label")
            if label:
                labels.append(str(label))
    return labels


def module_pointer_from_entry(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    return safe_mapping(safe_mapping(entry.get("classification")).get("modulePointer"))


def entry_to_occurrence(
    *,
    entry: Mapping[str, Any],
    source_list: str,
    path: Path,
    repo_root: Path,
    doc: Mapping[str, Any],
) -> dict[str, Any] | None:
    module_pointer = module_pointer_from_entry(entry)
    rva = norm_hex(module_pointer.get("rva"))
    if not rva:
        return None
    offset_from_owner = entry.get("offsetFromOwner")
    labels = target_labels(doc)
    return {
        "rva": rva,
        "moduleName": module_pointer.get("moduleName"),
        "moduleBase": norm_hex(module_pointer.get("moduleBase")),
        "moduleAddress": norm_hex(entry.get("value")),
        "artifactPath": relpath(path, repo_root),
        "artifactKind": doc.get("kind") or doc.get("mode"),
        "generatedAtUtc": doc.get("generatedAtUtc"),
        "runName": path.parent.name,
        "sourceLists": [source_list],
        "ownerAddress": safe_mapping(doc.get("owner")).get("address"),
        "targetLabels": labels,
        "entryAddress": entry.get("address"),
        "entryValue": entry.get("value"),
        "offsetFromOwner": offset_from_owner,
        "offsetFromOwnerInt": parse_int(offset_from_owner),
        "offsetFromReadBase": entry.get("offsetFromReadBase"),
    }


def merge_occurrences(left: dict[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    sources = list(left.get("sourceLists") or [])
    for source in safe_list(right.get("sourceLists")):
        if source not in sources:
            sources.append(str(source))
    left["sourceLists"] = sources
    return left


def occurrences_from_doc(path: Path, repo_root: Path, doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    analysis = safe_mapping(doc.get("analysis"))
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source_list in ("ownerWindowModulePointers", "regionMatches", "ownerWindow"):
        for entry in safe_list(analysis.get(source_list)):
            if not isinstance(entry, Mapping):
                continue
            occurrence = entry_to_occurrence(
                entry=entry,
                source_list=source_list,
                path=path,
                repo_root=repo_root,
                doc=doc,
            )
            if occurrence is None:
                continue
            key = (
                str(occurrence.get("rva")),
                str(occurrence.get("entryAddress")),
                str(occurrence.get("artifactPath")),
            )
            if key in candidates:
                merge_occurrences(candidates[key], occurrence)
            else:
                candidates[key] = occurrence
    return list(candidates.values())


def iter_summary_json(captures_roots: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in captures_roots:
        if root.is_file():
            candidates = [root]
        elif root.exists():
            candidates = list(root.rglob("summary.json"))
        else:
            candidates = []
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def filter_occurrences(
    occurrences: Iterable[dict[str, Any]],
    *,
    rvas: set[str],
    module_addresses: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for occurrence in occurrences:
        rva = norm_hex(occurrence.get("rva"))
        module_address = norm_hex(occurrence.get("moduleAddress"))
        if (rvas and rva in rvas) or (module_addresses and module_address in module_addresses):
            selected.append(occurrence)
    return selected


def score_rva(rva: str, rows: Sequence[Mapping[str, Any]], *, player_label_fragment: str) -> tuple[int, list[str]]:
    unique_artifacts = {str(row.get("artifactPath")) for row in rows}
    unique_owners = {str(row.get("ownerAddress")) for row in rows}
    owner_window_count = sum(1 for row in rows if "ownerWindowModulePointers" in safe_list(row.get("sourceLists")))
    near_owner_count = sum(
        1
        for row in rows
        if isinstance(row.get("offsetFromOwnerInt"), int) and abs(int(row["offsetFromOwnerInt"])) <= 0x80
    )
    player_count = sum(
        1
        for row in rows
        if any(player_label_fragment.lower() in str(label).lower() for label in safe_list(row.get("targetLabels")))
    )
    score = len(unique_artifacts) * 5 + len(unique_owners) * 3 + owner_window_count * 10 + near_owner_count * 15 + player_count * 50
    reasons: list[str] = []
    if player_count:
        reasons.append(f"artifact-target-player-label-occurrences={player_count}")
    if near_owner_count:
        reasons.append(f"near-owner-occurrences={near_owner_count}")
    if owner_window_count:
        reasons.append(f"owner-window-occurrences={owner_window_count}")
    if len(unique_artifacts) > 1:
        reasons.append(f"artifacts={len(unique_artifacts)}")
    if len(unique_owners) > 1:
        reasons.append(f"owners={len(unique_owners)}")
    if not reasons:
        reasons.append("single-module-hint-occurrence")
    return score, reasons


def group_by_rva(occurrences: Sequence[dict[str, Any]], *, player_label_fragment: str) -> list[dict[str, Any]]:
    rows_by_rva: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for occurrence in occurrences:
        rows_by_rva[str(occurrence.get("rva"))].append(occurrence)
    grouped: list[dict[str, Any]] = []
    for rva, rows in rows_by_rva.items():
        score, reasons = score_rva(rva, rows, player_label_fragment=player_label_fragment)
        offsets = [row.get("offsetFromOwnerInt") for row in rows if isinstance(row.get("offsetFromOwnerInt"), int)]
        grouped.append(
            {
                "rva": rva,
                "score": score,
                "scoreReasons": reasons,
                "occurrenceCount": len(rows),
                "uniqueArtifactCount": len({str(row.get("artifactPath")) for row in rows}),
                "uniqueOwnerCount": len({str(row.get("ownerAddress")) for row in rows}),
                "ownerWindowOccurrenceCount": sum(
                    1 for row in rows if "ownerWindowModulePointers" in safe_list(row.get("sourceLists"))
                ),
                "nearOwnerOccurrenceCount": sum(1 for value in offsets if abs(value) <= 0x80),
                "minAbsOffsetFromOwner": min((abs(value) for value in offsets), default=None),
                "sampleOccurrences": sorted(
                    rows,
                    key=lambda row: (
                        0
                        if any(player_label_fragment.lower() in str(label).lower() for label in safe_list(row.get("targetLabels")))
                        else 1,
                        abs(row.get("offsetFromOwnerInt")) if isinstance(row.get("offsetFromOwnerInt"), int) else 1_000_000,
                        str(row.get("artifactPath")),
                    ),
                )[:12],
            }
        )
    grouped.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("rva"))))
    return grouped


def build_summary(
    *,
    repo_root: Path,
    captures_roots: Sequence[Path],
    rvas: set[str],
    module_addresses: set[str],
    player_label_fragment: str,
) -> dict[str, Any]:
    errors: list[str] = []
    skipped_non_object_files: list[str] = []
    scanned_files = 0
    all_occurrences: list[dict[str, Any]] = []
    for path in iter_summary_json(captures_roots):
        scanned_files += 1
        try:
            all_occurrences.extend(occurrences_from_doc(path, repo_root, load_json_object(path)))
        except ValueError as exc:
            if "must contain a JSON object" in str(exc):
                skipped_non_object_files.append(relpath(path, repo_root))
                continue
            errors.append(f"{relpath(path, repo_root)}:{type(exc).__name__}:{exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{relpath(path, repo_root)}:{type(exc).__name__}:{exc}")
    selected = filter_occurrences(all_occurrences, rvas=rvas, module_addresses=module_addresses)
    grouped = group_by_rva(selected, player_label_fragment=player_label_fragment)
    warnings = [
        "Offline artifact scan only; this does not read live target memory or prove a static chain.",
        "Occurrences are source-chain clues and may repeat within generated summaries.",
    ]
    if skipped_non_object_files:
        warnings.append(f"Skipped {len(skipped_non_object_files)} summary.json files that were not JSON objects.")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "module-hint-occurrence-packet",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if selected and not errors else "blocked" if not selected else "passed-with-warnings",
        "blockers": [] if selected else ["no-requested-module-hint-occurrences-found"],
        "warnings": warnings,
        "errors": errors[:50],
        "query": {
            "rvas": sorted(rvas),
            "moduleAddresses": sorted(module_addresses),
            "capturesRoots": [relpath(root, repo_root) if root.exists() else str(root) for root in captures_roots],
            "playerLabelFragment": player_label_fragment,
        },
        "counts": {
            "summaryJsonFilesScanned": scanned_files,
            "skippedNonObjectSummaryJsonFiles": len(skipped_non_object_files),
            "allModulePointerOccurrences": len(all_occurrences),
            "selectedOccurrenceCount": len(selected),
            "selectedRvaCount": len(grouped),
        },
        "topRva": grouped[0] if grouped else None,
        "rvas": grouped,
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
            "recommendedAction": "Use the highest-scoring RVA occurrence cluster as the next offline static-owner search seed.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    lines = [
        "# Module hint occurrence packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Summary JSON files scanned: `{counts.get('summaryJsonFilesScanned')}`",
        f"- Selected occurrences: `{counts.get('selectedOccurrenceCount')}`",
        "",
        "| Rank | Score | RVA | Occurrences | Artifacts | Owners | Owner-window hits | Near-owner hits | Reasons |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for index, row in enumerate(safe_list(summary.get("rvas")), start=1):
        if not isinstance(row, Mapping):
            continue
        reasons = ", ".join(str(reason) for reason in safe_list(row.get("scoreReasons")))
        lines.append(
            f"| {index} | `{row.get('score')}` | `{row.get('rva')}` | `{row.get('occurrenceCount')}` | "
            f"`{row.get('uniqueArtifactCount')}` | `{row.get('uniqueOwnerCount')}` | "
            f"`{row.get('ownerWindowOccurrenceCount')}` | `{row.get('nearOwnerOccurrenceCount')}` | {reasons} |"
        )
    for row in safe_list(summary.get("rvas")):
        if not isinstance(row, Mapping):
            continue
        lines.extend(["", f"## Samples for `{row.get('rva')}`", "", "| Artifact | Owner | Entry | Offset | Labels | Sources |", "|---|---|---|---:|---|---|"])
        for sample in safe_list(row.get("sampleOccurrences")):
            if not isinstance(sample, Mapping):
                continue
            labels = ", ".join(str(label) for label in safe_list(sample.get("targetLabels")))
            sources = ", ".join(str(source) for source in safe_list(sample.get("sourceLists")))
            lines.append(
                f"| `{sample.get('artifactPath')}` | `{sample.get('ownerAddress')}` | `{sample.get('entryAddress')}` | "
                f"`{sample.get('offsetFromOwner')}` | `{labels}` | `{sources}` |"
            )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    if summary.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{error}`" for error in safe_list(summary.get("errors")))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an offline occurrence packet for module-pointer RVA hints.")
    parser.add_argument("--captures-root", action="append", type=Path)
    parser.add_argument("--rva", action="append", default=[])
    parser.add_argument("--module-address", action="append", default=[])
    parser.add_argument("--player-label-fragment", default="player")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    captures_roots = args.captures_root or [repo_root / "scripts" / "captures"]
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"module-hint-occurrence-packet-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(
        repo_root=repo_root,
        captures_roots=[root if root.is_absolute() else repo_root / root for root in captures_roots],
        rvas={norm_hex(value) or str(value) for value in args.rva},
        module_addresses={norm_hex(value) or str(value) for value in args.module_address},
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
    return 0 if str(summary.get("status")).startswith("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
