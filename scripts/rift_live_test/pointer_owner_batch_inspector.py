from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .pointer_family_scan import int_hex, validate_target
from .pointer_owner_neighborhood_inspector import run as run_owner_inspector
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
DEFAULT_TARGET_WINDOW_ALIGN = 0x10000
DEFAULT_TARGET_WINDOW_SIZE = 0x10000
DEFAULT_OWNER_LIMIT = 32
DEFAULT_TOP_RVA_LIMIT = 12


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip(), 0)
        except ValueError:
            return None
    return None


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def compact_hex(value: str | None) -> str:
    if not value:
        return "unknown"
    return value.removeprefix("0x").removeprefix("0X")


def infer_target_pid(pointer_summary: dict[str, Any], explicit_pid: int | None) -> int | None:
    if explicit_pid is not None:
        return explicit_pid
    return parse_int(safe_dict(pointer_summary.get("target")).get("pid"))


def infer_target_hwnd(pointer_summary: dict[str, Any], explicit_hwnd: str | None) -> str | None:
    if explicit_hwnd:
        return explicit_hwnd
    target = safe_dict(pointer_summary.get("target"))
    return target.get("hwndHex") or target.get("hwnd")


def target_entries_from_pointer_summary(pointer_summary: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in safe_list(pointer_summary.get("rankedTargets")):
        target = safe_dict(item)
        address = parse_int(target.get("target"))
        if address is None or address in seen:
            continue
        seen.add(address)
        targets.append(
            {
                "address": address,
                "addressHex": int_hex(address),
                "label": str(target.get("targetLabel") or target.get("target") or int_hex(address)),
            }
        )
    return targets


def target_address_args(targets: list[dict[str, Any]]) -> list[str]:
    return [f"{target['addressHex']}:{target.get('label') or target['addressHex']}" for target in targets]


def infer_module_range(
    pointer_summary: dict[str, Any],
    *,
    module_name: str,
) -> tuple[str | None, int]:
    summary_target = safe_dict(pointer_summary.get("target"))
    base = summary_target.get("moduleBaseAddressHex")
    size = parse_int(summary_target.get("moduleMemorySize")) or 0
    module_list = safe_dict(pointer_summary.get("moduleList"))
    artifact = module_list.get("artifactPath")
    if artifact:
        path = Path(str(artifact))
        if path.exists():
            try:
                document = load_json_object(path)
                for module in safe_list(document.get("Modules") or document.get("modules")):
                    module_row = safe_dict(module)
                    if str(module_row.get("ModuleName") or module_row.get("moduleName") or "").lower() != module_name.lower():
                        continue
                    base = module_row.get("BaseAddressHex") or module_row.get("baseAddressHex") or base
                    size = parse_int(module_row.get("ModuleMemorySize") or module_row.get("moduleMemorySize")) or size
                    break
            except OSError:
                pass
    return str(base) if base else None, int(size or 0)


def choose_target_window_base(
    targets: list[dict[str, Any]],
    *,
    explicit_base: str | None,
    align_bytes: int,
) -> int | None:
    explicit = parse_int(explicit_base)
    if explicit is not None:
        return explicit
    for target in targets:
        label = str(target.get("label") or "").lower()
        address = parse_int(target.get("address"))
        if address is not None and "family-base" in label:
            return address
    addresses = [int(target["address"]) for target in targets if parse_int(target.get("address")) is not None]
    if not addresses:
        return None
    align = max(1, int(align_bytes))
    return min(addresses) & ~(align - 1) if align & (align - 1) == 0 else (min(addresses) // align) * align


def extract_owner_probes(
    pointer_summary: dict[str, Any],
    *,
    max_owners: int,
    include_module_hits: bool,
) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    seen: set[int] = set()
    per_target_counter: Counter[str] = Counter()
    for target_row in safe_list(pointer_summary.get("rankedTargets")):
        target = safe_dict(target_row)
        target_address = parse_int(target.get("target"))
        target_hex = int_hex(target_address)
        if target_address is None or not target_hex:
            continue
        for hit in safe_list(target.get("hits")):
            hit_row = safe_dict(hit)
            if hit_row.get("module") and not include_module_hits:
                continue
            owner_address = parse_int(hit_row.get("address"))
            if owner_address is None or owner_address in seen:
                continue
            seen.add(owner_address)
            per_target_counter[target_hex] += 1
            probes.append(
                {
                    "ownerAddress": owner_address,
                    "ownerAddressHex": int_hex(owner_address),
                    "label": f"ref-to-{compact_hex(target_hex)}-{per_target_counter[target_hex]:02d}",
                    "sourceTarget": target_hex,
                    "sourceTargetLabel": target.get("targetLabel"),
                    "sourceRegionBase": hit_row.get("regionBase"),
                    "sourceModule": hit_row.get("module"),
                    "asciiPreview": hit_row.get("asciiPreview"),
                }
            )
            if len(probes) >= max_owners:
                return probes
    return probes


def score_probe_result(row: dict[str, Any], targets: list[dict[str, Any]]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    exact_counts = safe_dict(row.get("exactTargetCounts"))
    target_labels = {target["addressHex"]: str(target.get("label") or "").lower() for target in targets}
    exact_total = 0
    for address_hex, count_value in exact_counts.items():
        try:
            count = int(count_value)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        exact_total += count
        label = target_labels.get(str(address_hex), "")
        if "exact-reference-match-x" in label:
            score += 100 * count
            reasons.append(f"exact-coordinate-target-ref:{address_hex}x{count}")
        elif "family-base" in label:
            score += 30 * count
            reasons.append(f"family-base-ref:{address_hex}x{count}")
        else:
            score += 15 * count
            reasons.append(f"target-ref:{address_hex}x{count}")
    owner_window_module_count = int(row.get("ownerWindowModulePointerCount") or 0)
    if owner_window_module_count:
        score += min(owner_window_module_count * 5, 40)
        reasons.append(f"owner-window-module-pointers:{owner_window_module_count}")
    module_count = int(row.get("modulePointerCount") or 0)
    if module_count:
        score += min(module_count, 25)
        reasons.append(f"region-module-pointers:{module_count}")
    if exact_total == 0 and not owner_window_module_count:
        reasons.append("low-signal:no-exact-target-or-owner-window-module-pointer")
    if row.get("status") != "passed":
        score -= 100
        reasons.append(f"non-passing-child-status:{row.get('status')}")
    return score, reasons


def module_rva_rollup(rows: list[dict[str, Any]], *, top_limit: int) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    owners_by_rva: dict[str, set[str]] = defaultdict(set)
    examples_by_rva: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        summary = safe_dict(row.get("childSummary"))
        analysis = safe_dict(summary.get("analysis"))
        for entry in safe_list(analysis.get("ownerWindowModulePointers")):
            item = safe_dict(entry)
            pointer = safe_dict(safe_dict(item.get("classification")).get("modulePointer"))
            rva = pointer.get("rva")
            if not rva:
                continue
            counts[str(rva)] += 1
            owners_by_rva[str(rva)].add(str(row.get("owner")))
            if len(examples_by_rva[str(rva)]) < 5:
                examples_by_rva[str(rva)].append(
                    {
                        "owner": row.get("owner"),
                        "storageAddress": item.get("address"),
                        "offsetFromOwner": item.get("offsetFromOwner"),
                        "value": item.get("value"),
                    }
                )
    ranked: list[dict[str, Any]] = []
    for rva, count in counts.most_common(top_limit):
        owners = sorted(owners_by_rva[rva])
        ranked.append(
            {
                "rva": rva,
                "ownerWindowHitCount": count,
                "ownerCount": len(owners),
                "owners": owners[:8],
                "examples": examples_by_rva[rva],
                "candidateOnly": True,
                "promotionEligible": False,
            }
        )
    return ranked


def build_root_sweep_commands(
    *,
    script_path: Path,
    target_pid: int | None,
    target_hwnd: str | None,
    expected_start_time_utc: str | None,
    expected_module_base: str | None,
    root_signature_json: Path | None,
    module_rvas: list[dict[str, Any]],
) -> list[list[str]]:
    if target_pid is None or not target_hwnd or not root_signature_json:
        return []
    commands: list[list[str]] = []
    for row in module_rvas:
        rva = row.get("rva")
        if not rva:
            continue
        command = [
            "python",
            str(script_path),
            "--target-pid",
            str(target_pid),
            "--target-hwnd",
            str(target_hwnd),
            "--root-signature-json",
            str(root_signature_json),
            "--selected-rva",
            str(rva),
            "--json",
        ]
        if expected_start_time_utc:
            command.extend(["--expected-start-time-utc", expected_start_time_utc])
        if expected_module_base:
            command.extend(["--expected-module-base", expected_module_base])
        commands.append(command)
    return commands


def make_child_args(
    *,
    repo_root: Path,
    output_root: Path,
    pid: int,
    hwnd: str,
    owner_address: int,
    target_addresses: list[str],
    target_window_base: int | None,
    target_window_size: int,
    near_target_bytes: int,
    module_base: str | None,
    module_size: int,
    module_name: str,
    include_module_pointers: bool,
    owner_window_bytes: int,
    max_region_bytes: int,
    stride: int,
    max_matches: int,
) -> argparse.Namespace:
    return SimpleNamespace(
        repo_root=repo_root,
        output_root=output_root,
        pid=pid,
        hwnd=hwnd,
        owner_address=int_hex(owner_address),
        target_address=target_addresses,
        target_window_base=int_hex(target_window_base),
        target_window_size=target_window_size,
        near_target_bytes=near_target_bytes,
        module_base=module_base,
        module_size=module_size,
        module_name=module_name,
        include_module_pointers=include_module_pointers,
        owner_window_bytes=owner_window_bytes,
        max_region_bytes=max_region_bytes,
        stride=stride,
        max_matches=max_matches,
        self_test=False,
        json=False,
    )


def summarize_child(row: dict[str, Any], child_summary: dict[str, Any], elapsed_seconds: float) -> dict[str, Any]:
    analysis = safe_dict(child_summary.get("analysis"))
    return {
        "owner": row["ownerAddressHex"],
        "label": row["label"],
        "sourceTarget": row.get("sourceTarget"),
        "sourceTargetLabel": row.get("sourceTargetLabel"),
        "status": child_summary.get("status"),
        "elapsedSeconds": round(elapsed_seconds, 3),
        "summaryJson": safe_dict(child_summary.get("artifacts")).get("summaryJson"),
        "regionMatchCount": analysis.get("regionMatchCount", 0),
        "modulePointerCount": analysis.get("modulePointerCount", 0),
        "ownerWindowModulePointerCount": analysis.get("ownerWindowModulePointerCount", 0),
        "exactTargetCounts": analysis.get("exactTargetCounts", {}),
        "warnings": child_summary.get("warnings", []),
        "blockers": child_summary.get("blockers", []),
        "childSummary": child_summary,
    }


def synthetic_pointer_summary() -> dict[str, Any]:
    return {
        "status": "passed",
        "target": {"pid": 1234, "hwndHex": "0x9999", "moduleBaseAddressHex": "0x700000", "moduleMemorySize": 0x100000},
        "rankedTargets": [
            {
                "target": "0x5000",
                "targetLabel": "exact-reference-match-family-base-64k",
                "hits": [{"address": "0x4100", "regionBase": "0x4000", "module": None, "asciiPreview": "synthetic"}],
            },
            {"target": "0x50D0", "targetLabel": "exact-reference-match-x", "hits": []},
        ],
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Pointer owner batch inspector",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{safe_dict(summary.get('artifacts')).get('runDirectory')}`",
        f"- Movement sent: `{str(safe_dict(summary.get('safety')).get('movementSent')).lower()}`",
        f"- Cheat Engine used: `{str(not safe_dict(summary.get('safety')).get('noCheatEngine')).lower()}`",
        f"- x64dbg attached: `{str(safe_dict(summary.get('safety')).get('x64dbgAttached')).lower()}`",
        "",
        "## Inputs",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Pointer family summary | `{safe_dict(summary.get('inputs')).get('pointerFamilySummary')}` |",
        f"| Owner probes requested | `{safe_dict(summary.get('counts')).get('ownerProbeCount')}` |",
        f"| Target count | `{safe_dict(summary.get('counts')).get('targetCount')}` |",
        f"| Target window | `{safe_dict(summary.get('inputs')).get('targetWindowBase')}` / `{safe_dict(summary.get('inputs')).get('targetWindowSize')}` |",
    ]
    ranked_rows = safe_list(summary.get("rankedRows"))
    if ranked_rows:
        lines.extend(
            [
                "",
                "## Ranked owner/ref-storage probes",
                "",
                "| # | Score | Owner/ref storage | Source target | Exact target counts | Owner-window module ptrs | Summary |",
                "|---:|---:|---|---|---|---:|---|",
            ]
        )
        for index, row in enumerate(ranked_rows[:20], 1):
            exact_counts = ", ".join(
                f"{address}={count}" for address, count in safe_dict(row.get("exactTargetCounts")).items() if int(count or 0)
            ) or "-"
            lines.append(
                f"| {index} | `{row.get('score')}` | `{row.get('owner')}` | "
                f"`{row.get('sourceTargetLabel') or row.get('sourceTarget')}` | `{exact_counts}` | "
                f"`{row.get('ownerWindowModulePointerCount')}` | `{row.get('summaryJson')}` |"
            )
    module_rvas = safe_list(summary.get("moduleRvaHints"))
    if module_rvas:
        lines.extend(
            [
                "",
                "## Owner-window module RVA hints",
                "",
                "| # | RVA | Owner-window hits | Owners | Example storage |",
                "|---:|---|---:|---:|---|",
            ]
        )
        for index, row in enumerate(module_rvas[:20], 1):
            examples = safe_list(row.get("examples"))
            example = safe_dict(examples[0]) if examples else {}
            lines.append(
                f"| {index} | `{row.get('rva')}` | `{row.get('ownerWindowHitCount')}` | "
                f"`{row.get('ownerCount')}` | `{example.get('storageAddress')}` |"
            )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in safe_list(summary.get("warnings")))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Read-only batch owner/ref-storage inspection. No movement, no input, no memory writes, no Cheat Engine, no x64dbg attach, and no coordinate truth promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    pointer_summary_path = args.from_pointer_family_summary.resolve() if args.from_pointer_family_summary else None
    pointer_summary = synthetic_pointer_summary() if args.self_test else load_json_object(pointer_summary_path)  # type: ignore[arg-type]
    target_pid = infer_target_pid(pointer_summary, args.target_pid)
    target_hwnd = infer_target_hwnd(pointer_summary, args.target_hwnd)
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root
        / "scripts"
        / "captures"
        / f"pointer-owner-batch-currentpid-{target_pid or 'unknown'}-{utc_stamp()}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    blockers: list[str] = []
    warnings: list[str] = []
    target: dict[str, Any] | None = None

    targets = target_entries_from_pointer_summary(pointer_summary)
    target_window_base = choose_target_window_base(
        targets,
        explicit_base=args.target_window_base,
        align_bytes=int(args.target_window_align),
    )
    target_address_values = target_address_args(targets)
    owner_probes = extract_owner_probes(
        pointer_summary,
        max_owners=max(1, int(args.max_owners)),
        include_module_hits=bool(args.include_module_hits),
    )

    if not targets:
        blockers.append("no-pointer-targets-in-family-summary")
    if not owner_probes:
        blockers.append("no-owner-probes-in-family-summary")
    if target_pid is None:
        blockers.append("target-pid-missing")
    if not target_hwnd:
        blockers.append("target-hwnd-missing")

    if not args.self_test and target_pid is not None and target_hwnd:
        validation_args = SimpleNamespace(
            target_pid=target_pid,
            target_hwnd=target_hwnd,
            process_name=args.process_name,
            title_contains=args.title_contains,
            expected_start_time_utc=args.expected_start_time_utc,
            start_time_tolerance_seconds=args.start_time_tolerance_seconds,
            expected_module_base=args.expected_module_base,
        )
        target, validation_blockers, validation_warnings = validate_target(validation_args)
        blockers.extend(validation_blockers)
        warnings.extend(validation_warnings)

    rows: list[dict[str, Any]] = []
    target_memory_bytes_read = False
    if not blockers:
        if args.self_test:
            rows.append(
                {
                    "owner": "0x4100",
                    "label": "self-test",
                    "sourceTarget": "0x5000",
                    "sourceTargetLabel": "exact-reference-match-family-base-64k",
                    "status": "passed",
                    "elapsedSeconds": 0.0,
                    "summaryJson": str(run_dir / "self-test-child-summary.json"),
                    "regionMatchCount": 4,
                    "modulePointerCount": 1,
                    "ownerWindowModulePointerCount": 1,
                    "exactTargetCounts": {"0x5000": 1, "0x50D0": 0},
                    "warnings": [],
                    "blockers": [],
                    "childSummary": {
                        "analysis": {
                            "ownerWindowModulePointers": [
                                {
                                    "address": "0x40F0",
                                    "offsetFromOwner": "-0x10",
                                    "value": "0x700020",
                                    "classification": {"modulePointer": {"rva": "0x20"}},
                                }
                            ]
                        },
                        "safety": {"targetMemoryBytesRead": False},
                    },
                }
            )
        else:
            inferred_module_base, inferred_module_size = infer_module_range(
                pointer_summary,
                module_name=str(args.module_name),
            )
            module_base = (
                args.module_base
                or args.expected_module_base
                or safe_dict(safe_dict(target).get("processDetails")).get("moduleBaseAddressHex")
                or inferred_module_base
            )
            module_size = int(args.module_size or safe_dict(target).get("moduleMemorySize") or inferred_module_size or 0)
            if not module_size:
                module_size = int(safe_dict(safe_dict(target).get("processDetails")).get("moduleMemorySize") or 0)
            for probe in owner_probes:
                row_dir = run_dir / str(probe["label"])
                child_args = make_child_args(
                    repo_root=repo_root,
                    output_root=row_dir,
                    pid=int(target_pid),  # type: ignore[arg-type]
                    hwnd=str(target_hwnd),
                    owner_address=int(probe["ownerAddress"]),
                    target_addresses=target_address_values,
                    target_window_base=target_window_base,
                    target_window_size=int(args.target_window_size),
                    near_target_bytes=int(args.near_target_bytes),
                    module_base=module_base,
                    module_size=module_size,
                    module_name=str(args.module_name),
                    include_module_pointers=bool(args.include_module_pointers),
                    owner_window_bytes=int(args.owner_window_bytes),
                    max_region_bytes=int(args.max_region_bytes),
                    stride=int(args.stride),
                    max_matches=int(args.max_matches),
                )
                started = time.monotonic()
                child_summary = run_owner_inspector(child_args)
                elapsed = time.monotonic() - started
                row = summarize_child(probe, child_summary, elapsed)
                target_memory_bytes_read = target_memory_bytes_read or bool(
                    safe_dict(child_summary.get("safety")).get("targetMemoryBytesRead")
                )
                rows.append(row)

    for row in rows:
        score, reasons = score_probe_result(row, targets)
        row["score"] = score
        row["scoreReasons"] = reasons
    ranked_rows = sorted(rows, key=lambda row: (-int(row.get("score") or 0), str(row.get("owner"))))
    module_rvas = module_rva_rollup(ranked_rows, top_limit=int(args.top_rva_limit))
    root_signature_json = args.root_signature_json.resolve() if args.root_signature_json else None
    next_commands = build_root_sweep_commands(
        script_path=repo_root / "scripts" / "root_signature_module_hint_sweep.py",
        target_pid=target_pid,
        target_hwnd=target_hwnd,
        expected_start_time_utc=args.expected_start_time_utc,
        expected_module_base=args.expected_module_base,
        root_signature_json=root_signature_json,
        module_rvas=module_rvas,
    )
    child_statuses = Counter(str(row.get("status")) for row in rows)
    if rows and child_statuses and any(status != "passed" for status in child_statuses):
        warnings.append(f"child-nonpassed-statuses:{dict(child_statuses)}")
    if rows and not module_rvas:
        warnings.append("no-owner-window-module-rva-hints")
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "pointer-owner-batch-inspector",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else ("passed" if not child_statuses or not any(status == "failed" for status in child_statuses) else "failed"),
        "repoRoot": str(repo_root),
        "target": target or safe_dict(pointer_summary.get("target")),
        "inputs": {
            "pointerFamilySummary": str(pointer_summary_path) if pointer_summary_path else "self-test",
            "rootSignatureJson": str(root_signature_json) if root_signature_json else None,
            "targetWindowBase": int_hex(target_window_base),
            "targetWindowSize": int(args.target_window_size),
            "nearTargetBytes": int(args.near_target_bytes),
            "maxOwners": int(args.max_owners),
            "includeModuleHits": bool(args.include_module_hits),
            "includeModulePointers": bool(args.include_module_pointers),
        },
        "counts": {
            "targetCount": len(targets),
            "ownerProbeCount": len(owner_probes),
            "inspectedOwnerCount": len(rows),
            "childStatuses": dict(child_statuses),
            "moduleRvaHintCount": len(module_rvas),
        },
        "targets": [{"address": target["addressHex"], "label": target.get("label")} for target in targets],
        "ownerProbes": [
            {key: value for key, value in probe.items() if key not in {"asciiPreview"}}
            for probe in owner_probes
        ],
        "rankedRows": [{key: value for key, value in row.items() if key != "childSummary"} for row in ranked_rows],
        "moduleRvaHints": module_rvas,
        "nextRootSweepCommands": next_commands,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "targetMemoryBytesRead": target_memory_bytes_read,
            "savedVariablesUsedAsLiveTruth": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "x64dbgAttached": False,
            "memoryWrites": False,
            "proofPromoted": False,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "next": {
            "recommendedAction": "Use top owner-window module RVA hints for root-signature sweeps, or escalate to access-chain tracing if batch owner evidence stays heap-only.",
        },
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch read-only owner/ref-storage inspection from a pointer-family scan.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--from-pointer-family-summary", type=Path, default=None)
    parser.add_argument("--root-signature-json", type=Path, default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--start-time-tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--module-base", default=None)
    parser.add_argument("--module-size", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--module-name", default="rift_x64.exe")
    parser.add_argument("--target-window-base", default=None)
    parser.add_argument("--target-window-align", type=lambda value: int(value, 0), default=DEFAULT_TARGET_WINDOW_ALIGN)
    parser.add_argument("--target-window-size", type=lambda value: int(value, 0), default=DEFAULT_TARGET_WINDOW_SIZE)
    parser.add_argument("--near-target-bytes", type=lambda value: int(value, 0), default=0x80)
    parser.add_argument("--max-owners", type=int, default=DEFAULT_OWNER_LIMIT)
    parser.add_argument("--top-rva-limit", type=int, default=DEFAULT_TOP_RVA_LIMIT)
    parser.add_argument("--owner-window-bytes", type=lambda value: int(value, 0), default=0x200)
    parser.add_argument("--max-region-bytes", type=lambda value: int(value, 0), default=0x200000)
    parser.add_argument("--stride", type=int, default=8)
    parser.add_argument("--max-matches", type=int, default=256)
    parser.add_argument("--include-module-hits", action="store_true")
    parser.add_argument("--include-module-pointers", action="store_true", default=True)
    parser.add_argument("--no-module-pointers", dest="include_module_pointers", action="store_false")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.self_test and not args.from_pointer_family_summary:
        raise SystemExit("--from-pointer-family-summary is required unless --self-test is used")
    summary = run(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "inspectedOwnerCount": summary["counts"]["inspectedOwnerCount"],
                    "moduleRvaHintCount": summary["counts"]["moduleRvaHintCount"],
                    "topModuleRva": (summary.get("moduleRvaHints") or [{}])[0].get("rva"),
                    "blockers": summary.get("blockers", []),
                    "warnings": summary.get("warnings", []),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"inspectedOwnerCount={summary['counts']['inspectedOwnerCount']}")
        print(f"moduleRvaHintCount={summary['counts']['moduleRvaHintCount']}")
    return 2 if summary["status"] == "blocked" else (1 if summary["status"] == "failed" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
