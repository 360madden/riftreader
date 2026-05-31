#!/usr/bin/env python3
"""Analyze current-PID coordinate-family candidate neighborhoods offline.

This helper reads existing `api-family-vec3-candidates.jsonl` files and reports
family/adjacent-family survival around a known anchor. It performs no live
process reads, sends no input, and does not promote movement truth.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

try:
    from .workflow_common import utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import utc_iso, utc_stamp, write_json  # type: ignore

SCHEMA_VERSION = 1
DEFAULT_CANDIDATE_GLOB = "scripts/captures/family-scan-currentpid-{pid}-*/api-family-vec3-candidates.jsonl"
DEFAULT_CURRENT_TRUTH = Path("docs/recovery/current-truth.json")
DEFAULT_OUTPUT_ROOT = Path("scripts/captures")
FAMILY_SPAN_16MIB = 0x1000000
MEGAPAGE_SPAN_1MIB = 0x100000
PAGE_SPAN_4KIB = 0x1000


def family_base(value: int, span: int) -> int:
    return value - (value % span)


def parse_int(value: Any, *, label: str) -> int:
    try:
        return int(str(value), 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {label}: {value!r}") from exc


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "docs" / "recovery").exists():
            return candidate
    return current


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_current_truth(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = load_json(path)
    return value if isinstance(value, dict) else {}


def current_truth_defaults(document: dict[str, Any]) -> dict[str, Any]:
    target = document.get("target") if isinstance(document.get("target"), dict) else {}
    candidate = document.get("bestCurrentCandidate") if isinstance(document.get("bestCurrentCandidate"), dict) else {}
    return {
        "pid": target.get("processId") or target.get("pid"),
        "hwnd": target.get("targetWindowHandle") or target.get("hwnd") or target.get("hwndHex"),
        "anchorAddress": candidate.get("addressHex") or candidate.get("absoluteAddressHex") or candidate.get("address"),
        "anchorCandidateId": candidate.get("candidateId") or candidate.get("candidate_id"),
        "candidateFile": candidate.get("candidateFile"),
    }


def normalize_candidate_files(repo_root: Path, values: list[str] | None, pid: int | None) -> list[Path]:
    paths: list[Path] = []
    if values:
        for value in values:
            path = Path(value)
            paths.append(path if path.is_absolute() else repo_root / path)
    elif pid is not None:
        paths = sorted(repo_root.glob(DEFAULT_CANDIDATE_GLOB.format(pid=pid)))
    return [path.resolve() for path in paths]


def candidate_address(item: dict[str, Any]) -> int | None:
    raw = item.get("absolute_address_hex") or item.get("absoluteAddressHex") or item.get("addressHex") or item.get("address")
    if raw in (None, ""):
        return None
    try:
        return int(str(raw), 0)
    except ValueError:
        return None


def load_candidate_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"candidate-jsonl-parse-failed:{path}:{line_number}:{exc.msg}") from exc
        if not isinstance(item, dict):
            continue
        address = candidate_address(item)
        if address is None:
            continue
        item = dict(item)
        item["_addressInt"] = address
        rows.append(item)
    return rows


def compact_candidate(item: dict[str, Any], anchor_address: int, family_span: int) -> dict[str, Any]:
    address = int(item["_addressInt"])
    return {
        "candidateId": item.get("candidate_id") or item.get("candidateId"),
        "addressHex": f"0x{address:X}",
        "familyBaseHex": f"0x{family_base(address, family_span):X}",
        "deltaFromAnchor": address - anchor_address,
        "supportCount": item.get("support_count") or item.get("supportCount"),
        "axisOrder": item.get("axis_order") or item.get("axisOrder"),
        "maxAbsDistance": item.get("best_max_abs_distance") or item.get("maxAbsDistance"),
    }


def analyze_candidate_files(candidate_files: list[Path], anchor_address: int, *, adjacent_family_radius: int = 3) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    all_by_address: dict[int, list[str]] = defaultdict(list)
    address_sets: dict[str, set[int]] = {}
    anchor_family = family_base(anchor_address, FAMILY_SPAN_16MIB)

    for path in candidate_files:
        rows = load_candidate_jsonl(path)
        run_id = path.parent.name
        addresses = {int(item["_addressInt"]) for item in rows}
        address_sets[run_id] = addresses
        families = Counter(family_base(address, FAMILY_SPAN_16MIB) for address in addresses)
        megapages = Counter(family_base(address, MEGAPAGE_SPAN_1MIB) for address in addresses)
        pages = Counter(family_base(address, PAGE_SPAN_4KIB) for address in addresses)
        for address in addresses:
            all_by_address[address].append(run_id)

        anchor_family_rows = [item for item in rows if family_base(int(item["_addressInt"]), FAMILY_SPAN_16MIB) == anchor_family]
        nearest = sorted(rows, key=lambda item: abs(int(item["_addressInt"]) - anchor_address))[:12]
        adjacent_counts = {
            f"{delta:+d}": families.get(anchor_family + delta * FAMILY_SPAN_16MIB, 0)
            for delta in range(-adjacent_family_radius, adjacent_family_radius + 1)
        }
        runs.append(
            {
                "runId": run_id,
                "path": str(path),
                "candidateCount": len(rows),
                "family16MiBCount": len(families),
                "megaPage1MiBCount": len(megapages),
                "page4KiBCount": len(pages),
                "anchorFamilyBaseHex": f"0x{anchor_family:X}",
                "anchorAdjacentFamilyCandidateCounts": adjacent_counts,
                "anchorFamilyCandidateCount": len(anchor_family_rows),
                "anchorFamilyCandidates": [
                    compact_candidate(item, anchor_address, FAMILY_SPAN_16MIB)
                    for item in sorted(anchor_family_rows, key=lambda item: abs(int(item["_addressInt"]) - anchor_address))[:20]
                ],
                "nearestCandidatesToAnchor": [
                    compact_candidate(item, anchor_address, FAMILY_SPAN_16MIB)
                    for item in nearest
                ],
                "topFamilies": [
                    {
                        "familyBaseHex": f"0x{base:X}",
                        "candidateCount": count,
                        "deltaFamiliesFromAnchor": (base - anchor_family) // FAMILY_SPAN_16MIB,
                    }
                    for base, count in families.most_common(12)
                ],
            }
        )

    pairwise_overlap = []
    for run_a, run_b in combinations(address_sets, 2):
        shared = address_sets[run_a] & address_sets[run_b]
        pairwise_overlap.append(
            {
                "runA": run_a,
                "runB": run_b,
                "sharedAddressCount": len(shared),
                "shared4KiBPageCount": len({family_base(address, PAGE_SPAN_4KIB) for address in shared}),
                "shared1MiBPageCount": len({family_base(address, MEGAPAGE_SPAN_1MIB) for address in shared}),
                "shared16MiBFamilyCount": len({family_base(address, FAMILY_SPAN_16MIB) for address in shared}),
                "sharedAddressSample": [f"0x{address:X}" for address in sorted(shared)[:40]],
            }
        )

    shared_addresses = {address: runs for address, runs in all_by_address.items() if len(set(runs)) > 1}
    return {
        "anchor": {
            "addressHex": f"0x{anchor_address:X}",
            "family16MiBBaseHex": f"0x{anchor_family:X}",
            "megaPage1MiBBaseHex": f"0x{family_base(anchor_address, MEGAPAGE_SPAN_1MIB):X}",
            "page4KiBBaseHex": f"0x{family_base(anchor_address, PAGE_SPAN_4KIB):X}",
        },
        "runs": runs,
        "pairwiseOverlap": pairwise_overlap,
        "crossRunSharedAddressCount": len(shared_addresses),
        "crossRunSharedAddressesSample": [
            {"addressHex": f"0x{address:X}", "runCount": len(set(run_ids)), "runs": sorted(set(run_ids))}
            for address, run_ids in sorted(shared_addresses.items())[:50]
        ],
        "classification": {
            "anchorFamilySurvived": any(run["anchorFamilyCandidateCount"] for run in runs),
            "adjacentFamiliesHaveCandidates": any(
                any(count for delta, count in run["anchorAdjacentFamilyCandidateCounts"].items() if delta != "+0")
                for run in runs
            ),
            "policy": "offline evidence only; does not promote new movement truth without current API-now/memory-now and ProofOnly gates",
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Current PID family neighborhood analysis",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Anchor: `{summary.get('anchor', {}).get('candidateId')} @ {summary.get('anchor', {}).get('addressHex')}`",
        f"- Anchor 16MiB family: `{summary.get('anchor', {}).get('family16MiBBaseHex')}`",
        f"- Cross-run shared addresses: `{summary.get('crossRunSharedAddressCount')}`",
        "- Safety: no input, no movement, no live memory read, no CE/x64dbg.",
        "- Note: offline evidence only; not a new proof promotion.",
        "",
        "| Run | Candidates | 16MiB families | Anchor family hits | Adjacent -1/+1 hits |",
        "|---|---:|---:|---:|---:|",
    ]
    for run in summary.get("runs", []):
        adjacent = run.get("anchorAdjacentFamilyCandidateCounts") or {}
        lines.append(
            f"| `{run.get('runId')}` | {run.get('candidateCount')} | {run.get('family16MiBCount')} | "
            f"{run.get('anchorFamilyCandidateCount')} | {adjacent.get('-1', 0)} / {adjacent.get('+1', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Pairwise overlap",
            "",
            "| Run A | Run B | Shared addresses | Shared 4KiB pages | Shared 1MiB pages | Shared 16MiB families |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for item in summary.get("pairwiseOverlap", []):
        lines.append(
            f"| `{item.get('runA')}` | `{item.get('runB')}` | {item.get('sharedAddressCount')} | "
            f"{item.get('shared4KiBPageCount')} | {item.get('shared1MiBPageCount')} | {item.get('shared16MiBFamilyCount')} |"
        )

    lines.extend(["", "## Top families by run", ""])
    for run in summary.get("runs", []):
        lines.append(f"### `{run.get('runId')}`")
        lines.append("| Family base | Count | Delta families from anchor |")
        lines.append("|---|---:|---:|")
        for family in (run.get("topFamilies") or [])[:8]:
            lines.append(
                f"| `{family.get('familyBaseHex')}` | {family.get('candidateCount')} | {family.get('deltaFamiliesFromAnchor')} |"
            )
        lines.append("")
    return "\n".join(lines)


def self_test() -> dict[str, Any]:
    sample = {
        "absolute_address_hex": "0x1010",
        "candidate_id": "hit-1",
        "support_count": 2,
        "axis_order": "xyz",
    }
    compact = compact_candidate({**sample, "_addressInt": 0x1010}, 0x1000, FAMILY_SPAN_16MIB)
    errors = []
    if family_base(0x12345, 0x1000) != 0x12000:
        errors.append("family-base-page-align-failed")
    if compact["deltaFromAnchor"] != 0x10:
        errors.append("compact-candidate-delta-failed")
    return {"status": "passed" if not errors else "failed", "errors": errors}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze existing current-PID family candidate neighborhood overlap offline.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--current-truth-json", type=Path, default=DEFAULT_CURRENT_TRUTH)
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--anchor-address", default=None)
    parser.add_argument("--anchor-candidate-id", default=None)
    parser.add_argument("--candidate-jsonl", action="append", default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--adjacent-family-radius", type=int, default=3)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.self_test:
        result = self_test()
        return (0 if result["status"] == "passed" else 1), result

    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    current_truth_path = args.current_truth_json if args.current_truth_json.is_absolute() else repo_root / args.current_truth_json
    defaults = current_truth_defaults(read_current_truth(current_truth_path))
    pid = args.pid if args.pid is not None else (parse_int(defaults.get("pid"), label="pid") if defaults.get("pid") else None)
    anchor_raw = args.anchor_address or defaults.get("anchorAddress")
    if not anchor_raw:
        return 2, {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "riftreader-current-pid-family-neighborhood-analysis",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "blockers": ["anchor-address-required"],
            "warnings": [],
            "errors": [],
            "safety": default_safety(),
        }
    anchor_address = parse_int(anchor_raw, label="anchor-address")
    candidate_files = normalize_candidate_files(repo_root, args.candidate_jsonl, pid)
    missing = [str(path) for path in candidate_files if not path.exists()]
    if missing or not candidate_files:
        return 2, {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "riftreader-current-pid-family-neighborhood-analysis",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "blockers": [*(f"candidate-jsonl-not-found:{path}" for path in missing), *( ["candidate-jsonl-required"] if not candidate_files else [])],
            "warnings": [],
            "errors": [],
            "safety": default_safety(),
            "pid": pid,
            "candidateFiles": [str(path) for path in candidate_files],
        }

    analysis = analyze_candidate_files(candidate_files, anchor_address, adjacent_family_radius=max(1, args.adjacent_family_radius))
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-current-pid-family-neighborhood-analysis",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "currentTruthJson": str(current_truth_path),
        "pid": pid,
        "targetWindowHandle": defaults.get("hwnd"),
        "candidateFiles": [str(path) for path in candidate_files],
        "safety": default_safety(),
        **analysis,
    }
    summary["anchor"]["candidateId"] = args.anchor_candidate_id or defaults.get("anchorCandidateId")

    output_root = args.output_root.resolve() if args.output_root else repo_root / DEFAULT_OUTPUT_ROOT
    run_dir = output_root / f"current-pid-family-neighborhood-analysis-{pid or 'unknown'}-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(summary_path),
        "summaryMarkdown": str(markdown_path),
    }
    write_json(summary_path, summary)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return 0, summary


def default_safety() -> dict[str, bool]:
    return {
        "movementSent": False,
        "inputSent": False,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "providerWrites": False,
        "gitMutation": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "savedVariablesUsedAsLiveTruth": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code, summary = run(args)
    except Exception as exc:  # noqa: BLE001
        exit_code = 1
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "riftreader-current-pid-family-neighborhood-analysis",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "blockers": [],
            "warnings": [],
            "errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "safety": default_safety(),
        }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps({"status": summary.get("status"), "blockers": summary.get("blockers"), "summaryJson": summary.get("artifacts", {}).get("summaryJson")}))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
