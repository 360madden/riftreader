from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from .coordinate_proof_preflight import run_command
from .pointer_owner_batch_inspector import parse_int
from .pointer_family_scan import int_hex
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
DEFAULT_MAX_RVAS = 8
DEFAULT_CONTEXT_BYTES = 288
DEFAULT_MAX_HITS = 2048
DEFAULT_TIMEOUT_SECONDS = 180


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


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_hex(value: Any) -> str | None:
    parsed = parse_int(value)
    return int_hex(parsed) if parsed is not None else None


def same_path(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return str(left).lower() == str(right).lower()


def infer_target_pid(owner_batch: dict[str, Any], explicit_pid: int | None) -> int | None:
    if explicit_pid is not None:
        return explicit_pid
    return parse_int(safe_dict(owner_batch.get("target")).get("pid"))


def infer_target_hwnd(owner_batch: dict[str, Any], explicit_hwnd: str | None) -> str | None:
    if explicit_hwnd:
        return normalize_hex(explicit_hwnd)
    target = safe_dict(owner_batch.get("target"))
    return normalize_hex(target.get("hwndHex") or target.get("hwnd"))


def infer_expected_start(owner_batch: dict[str, Any], explicit_value: str | None) -> str | None:
    if explicit_value:
        return explicit_value
    target = safe_dict(owner_batch.get("target"))
    process_details = safe_dict(target.get("processDetails"))
    return process_details.get("startTimeUtc") or target.get("startTimeUtc")


def infer_expected_module_base(owner_batch: dict[str, Any], explicit_value: str | None) -> str | None:
    if explicit_value:
        return normalize_hex(explicit_value)
    target = safe_dict(owner_batch.get("target"))
    process_details = safe_dict(target.get("processDetails"))
    return normalize_hex(process_details.get("moduleBaseAddressHex") or target.get("moduleBaseAddressHex"))


def infer_root_signature(owner_batch: dict[str, Any], explicit_path: Path | None) -> Path | None:
    if explicit_path:
        return explicit_path
    value = safe_dict(owner_batch.get("inputs")).get("rootSignatureJson")
    return Path(str(value)) if value else None


def root_signature_field_rvas(root_signature: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for field in safe_list(safe_dict(root_signature.get("signature")).get("ownerModuleFields")):
        rva = normalize_hex(safe_dict(field).get("rva"))
        if rva:
            result.add(rva)
    return result


def rank_owner_batch_hints(
    owner_batch: dict[str, Any],
    *,
    root_signature_rvas: set[str] | None = None,
    include_signature_rvas: bool = False,
    min_owner_count: int = 1,
    min_owner_window_hits: int = 1,
    include_rvas: set[str] | None = None,
    exclude_rvas: set[str] | None = None,
) -> list[dict[str, Any]]:
    root_signature_rvas = root_signature_rvas or set()
    include_rvas = include_rvas or set()
    exclude_rvas = exclude_rvas or set()
    ranked: list[dict[str, Any]] = []
    for index, raw_hint in enumerate(safe_list(owner_batch.get("moduleRvaHints"))):
        hint = safe_dict(raw_hint)
        rva = normalize_hex(hint.get("rva"))
        if not rva:
            continue
        owner_count = int(hint.get("ownerCount") or 0)
        owner_window_hit_count = int(hint.get("ownerWindowHitCount") or 0)
        is_root_signature_rva = rva in root_signature_rvas
        skip_reasons: list[str] = []
        if exclude_rvas and rva in exclude_rvas:
            skip_reasons.append("explicitly-excluded-rva")
        if include_rvas and rva not in include_rvas:
            skip_reasons.append("not-in-explicit-include-list")
        if owner_count < min_owner_count:
            skip_reasons.append(f"below-min-owner-count:{owner_count}<{min_owner_count}")
        if owner_window_hit_count < min_owner_window_hits:
            skip_reasons.append(f"below-min-owner-window-hits:{owner_window_hit_count}<{min_owner_window_hits}")
        if is_root_signature_rva and not include_signature_rvas:
            skip_reasons.append("root-signature-field-rva")
        score = owner_window_hit_count * 100 + owner_count * 50 - index
        if is_root_signature_rva:
            score -= 1000
        ranked.append(
            {
                "rva": rva,
                "score": score,
                "ownerWindowHitCount": owner_window_hit_count,
                "ownerCount": owner_count,
                "owners": safe_list(hint.get("owners")),
                "examples": safe_list(hint.get("examples")),
                "rootSignatureFieldRva": is_root_signature_rva,
                "skipReasons": skip_reasons,
                "candidateOnly": True,
                "promotionEligible": False,
            }
        )
    return sorted(ranked, key=lambda row: (-int(row.get("score") or 0), str(row.get("rva"))))


def sweep_summaries(repo_root: Path) -> Iterable[Path]:
    captures = repo_root / "scripts" / "captures"
    yield from captures.glob("root-signature-module-hint-sweep-*/summary.json")


def existing_sweeps_by_rva(
    repo_root: Path,
    *,
    target_pid: int | None,
    target_hwnd: str | None,
    expected_start_time_utc: str | None,
    expected_module_base: str | None,
    root_signature_json: Path | None,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for path in sweep_summaries(repo_root):
        try:
            summary = load_json_object(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        rva = normalize_hex(safe_dict(summary.get("inputs")).get("selectedRva"))
        if not rva:
            continue
        if root_signature_json and not same_path(
            str(safe_dict(summary.get("inputs")).get("rootSignatureJson") or ""),
            str(root_signature_json),
        ):
            continue
        target = safe_dict(summary.get("target"))
        process_details = safe_dict(target.get("processDetails"))
        summary_pid = parse_int(target.get("pid"))
        summary_hwnd = normalize_hex(target.get("hwndHex") or target.get("hwnd"))
        summary_start = process_details.get("startTimeUtc") or target.get("startTimeUtc")
        summary_module_base = normalize_hex(process_details.get("moduleBaseAddressHex") or target.get("moduleBaseAddressHex"))
        if target_pid is not None and summary_pid != target_pid:
            continue
        if target_hwnd and summary_hwnd != target_hwnd:
            continue
        if expected_start_time_utc and summary_start != expected_start_time_utc:
            continue
        if expected_module_base and summary_module_base != expected_module_base:
            continue
        grouped.setdefault(rva, []).append(
            {
                "path": str(path),
                "status": summary.get("status"),
                "generatedAtUtc": summary.get("generatedAtUtc"),
                "counts": summary.get("counts"),
                "topOwnerScore": safe_dict(summary.get("topOwnerFieldCandidate")).get("score"),
                "topParentScore": safe_dict(summary.get("topParentSlotCandidate")).get("score"),
            }
        )
    return grouped


def select_sweep_rvas(
    ranked_hints: Sequence[dict[str, Any]],
    *,
    existing_by_rva: dict[str, list[dict[str, Any]]],
    skip_existing: bool,
    max_rvas: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for hint in ranked_hints:
        row = dict(hint)
        reasons = list(row.get("skipReasons") or [])
        rva = str(row.get("rva"))
        existing = existing_by_rva.get(rva) or []
        if skip_existing and existing:
            reasons.append("already-swept-for-current-target")
            row["existingSweeps"] = existing
        if reasons:
            row["skipReasons"] = reasons
            skipped.append(row)
            continue
        if len(selected) < max_rvas:
            selected.append(row)
        else:
            row["skipReasons"] = ["max-rvas-limit"]
            skipped.append(row)
    return selected, skipped


def build_command(
    *,
    repo_root: Path,
    target_pid: int,
    target_hwnd: str,
    root_signature_json: Path,
    rva: str,
    expected_start_time_utc: str | None,
    expected_module_base: str | None,
    context_bytes: int,
    max_hits: int,
    report_limit: int,
    timeout_seconds: int,
) -> list[str]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "root_signature_module_hint_sweep.py"),
        "--target-pid",
        str(target_pid),
        "--target-hwnd",
        target_hwnd,
        "--root-signature-json",
        str(root_signature_json),
        "--selected-rva",
        rva,
        "--context-bytes",
        str(context_bytes),
        "--max-hits",
        str(max_hits),
        "--report-limit",
        str(report_limit),
        "--timeout-seconds",
        str(timeout_seconds),
        "--json",
    ]
    if expected_start_time_utc:
        command.extend(["--expected-start-time-utc", expected_start_time_utc])
    if expected_module_base:
        command.extend(["--expected-module-base", expected_module_base])
    return command


def summarize_child_command(command: dict[str, Any], rva: str) -> dict[str, Any]:
    stdout_json = safe_dict(command.get("stdoutJson"))
    counts = safe_dict(stdout_json.get("counts"))
    return {
        "rva": rva,
        "status": stdout_json.get("status") or command.get("status"),
        "exitCode": command.get("exitCode"),
        "durationSeconds": command.get("durationSeconds"),
        "summaryJson": stdout_json.get("summaryJson"),
        "summaryMarkdown": stdout_json.get("summaryMarkdown"),
        "counts": counts,
        "topOwnerFieldCandidate": stdout_json.get("topOwnerFieldCandidate"),
        "topParentSlotCandidate": stdout_json.get("topParentSlotCandidate"),
        "blockers": stdout_json.get("blockers", []),
        "warnings": stdout_json.get("warnings", []),
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Root-signature batch sweep",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{safe_dict(summary.get('artifacts')).get('runDirectory')}`",
        f"- Dry run: `{str(safe_dict(summary.get('inputs')).get('dryRun')).lower()}`",
        f"- Movement sent: `{str(safe_dict(summary.get('safety')).get('movementSent')).lower()}`",
        f"- Cheat Engine used: `{str(not safe_dict(summary.get('safety')).get('noCheatEngine')).lower()}`",
        f"- x64dbg attached: `{str(safe_dict(summary.get('safety')).get('x64dbgAttached')).lower()}`",
        "",
        "## Selection",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Owner batch summary | `{safe_dict(summary.get('inputs')).get('ownerBatchSummary')}` |",
        f"| Root signature | `{safe_dict(summary.get('inputs')).get('rootSignatureJson')}` |",
        f"| Selected RVAs | `{safe_dict(summary.get('counts')).get('selectedRvaCount')}` |",
        f"| Skipped RVAs | `{safe_dict(summary.get('counts')).get('skippedRvaCount')}` |",
    ]
    selected = safe_list(summary.get("selectedRvas"))
    if selected:
        lines.extend(["", "## Selected sweeps", "", "| # | RVA | Score | Owners | Hits | Command/status |", "|---:|---|---:|---:|---:|---|"])
        for index, row in enumerate(selected, 1):
            lines.append(
                f"| {index} | `{row.get('rva')}` | `{row.get('score')}` | "
                f"`{row.get('ownerCount')}` | `{row.get('ownerWindowHitCount')}` | `{row.get('status') or 'planned'}` |"
            )
    skipped = safe_list(summary.get("skippedRvas"))
    if skipped:
        lines.extend(["", "## Skipped RVAs", "", "| RVA | Reasons | Existing sweeps |", "|---|---|---:|"])
        for row in skipped[:30]:
            lines.append(
                f"| `{row.get('rva')}` | `{', '.join(safe_list(row.get('skipReasons')))}` | "
                f"`{len(safe_list(row.get('existingSweeps')))} ` |"
            )
    results = safe_list(summary.get("results"))
    if results:
        lines.extend(["", "## Results", "", "| RVA | Status | Module hits | Top owner score | Top parent score | Summary |", "|---|---|---:|---:|---:|---|"])
        for row in results:
            counts = safe_dict(row.get("counts"))
            owner = safe_dict(row.get("topOwnerFieldCandidate"))
            parent = safe_dict(row.get("topParentSlotCandidate"))
            lines.append(
                f"| `{row.get('rva')}` | `{row.get('status')}` | `{counts.get('modulePointerHitCount')}` | "
                f"`{owner.get('score')}` | `{parent.get('score')}` | `{row.get('summaryJson')}` |"
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
            "Read-only root-signature sweep orchestration. No movement, no input, no memory writes, no Cheat Engine, no x64dbg attach, and no coordinate truth promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    owner_batch_summary = args.from_owner_batch_summary.resolve() if args.from_owner_batch_summary else None
    owner_batch = synthetic_owner_batch() if args.self_test else load_json_object(owner_batch_summary)  # type: ignore[arg-type]
    target_pid = infer_target_pid(owner_batch, args.target_pid)
    target_hwnd = infer_target_hwnd(owner_batch, args.target_hwnd)
    expected_start_time_utc = infer_expected_start(owner_batch, args.expected_start_time_utc)
    expected_module_base = infer_expected_module_base(owner_batch, args.expected_module_base)
    root_signature_json = infer_root_signature(owner_batch, args.root_signature_json)
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root
        / "scripts"
        / "captures"
        / f"root-signature-batch-sweep-currentpid-{target_pid or 'unknown'}-{utc_stamp()}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    blockers: list[str] = []
    warnings: list[str] = []

    if target_pid is None:
        blockers.append("target-pid-missing")
    if not target_hwnd:
        blockers.append("target-hwnd-missing")
    if not root_signature_json:
        blockers.append("root-signature-json-missing")
    elif not args.self_test and not root_signature_json.exists():
        blockers.append(f"root-signature-json-not-found:{root_signature_json}")

    root_signature_rvas: set[str] = set()
    if root_signature_json and root_signature_json.exists():
        root_signature_rvas = root_signature_field_rvas(load_json_object(root_signature_json))

    include_rvas = {normalize_hex(value) for value in args.include_rva}
    include_rvas.discard(None)
    exclude_rvas = {normalize_hex(value) for value in args.exclude_rva}
    exclude_rvas.discard(None)
    ranked_hints = rank_owner_batch_hints(
        owner_batch,
        root_signature_rvas=root_signature_rvas,
        include_signature_rvas=bool(args.include_signature_rvas),
        min_owner_count=int(args.min_owner_count),
        min_owner_window_hits=int(args.min_owner_window_hits),
        include_rvas=set(include_rvas),
        exclude_rvas=set(exclude_rvas),
    )
    if not ranked_hints:
        blockers.append("no-module-rva-hints-in-owner-batch")

    existing_by_rva = {} if args.self_test else existing_sweeps_by_rva(
        repo_root,
        target_pid=target_pid,
        target_hwnd=target_hwnd,
        expected_start_time_utc=expected_start_time_utc,
        expected_module_base=expected_module_base,
        root_signature_json=root_signature_json,
    )
    selected, skipped = select_sweep_rvas(
        ranked_hints,
        existing_by_rva=existing_by_rva,
        skip_existing=not bool(args.include_existing),
        max_rvas=max(0, int(args.max_rvas)),
    )
    if not selected and not blockers:
        warnings.append("no-rvas-selected-after-filters")

    command_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    if not blockers:
        for row in selected:
            command = build_command(
                repo_root=repo_root,
                target_pid=int(target_pid),  # type: ignore[arg-type]
                target_hwnd=str(target_hwnd),
                root_signature_json=root_signature_json,  # type: ignore[arg-type]
                rva=str(row["rva"]),
                expected_start_time_utc=expected_start_time_utc,
                expected_module_base=expected_module_base,
                context_bytes=int(args.context_bytes),
                max_hits=int(args.max_hits),
                report_limit=int(args.report_limit),
                timeout_seconds=int(args.timeout_seconds),
            )
            if args.dry_run or args.self_test:
                command_row = {
                    "name": f"root-signature-module-hint-sweep:{row['rva']}",
                    "status": "planned",
                    "args": command,
                    "cwd": str(repo_root),
                    "exitCode": None,
                    "durationSeconds": 0.0,
                    "stdoutJson": None,
                }
            else:
                command_row = run_command(
                    name=f"root-signature-module-hint-sweep:{row['rva']}",
                    args=command,
                    cwd=repo_root,
                    timeout_seconds=int(args.timeout_seconds) + 15,
                    expected_exit_codes={0},
                    blocked_exit_codes={2},
                )
            command_rows.append(command_row)
            row["status"] = command_row.get("status")
            row["commandIndex"] = len(command_rows) - 1
            if command_row.get("stdoutJson"):
                results.append(summarize_child_command(command_row, str(row["rva"])))

    command_statuses = Counter(str(command.get("status")) for command in command_rows)
    if any(status == "failed" for status in command_statuses):
        status = "failed"
    elif any(status == "blocked" for status in command_statuses) or blockers:
        status = "blocked"
    else:
        status = "passed"

    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "root-signature-batch-sweep",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "target": {
            "processName": args.process_name,
            "pid": target_pid,
            "hwnd": target_hwnd,
            "expectedStartTimeUtc": expected_start_time_utc,
            "expectedModuleBase": expected_module_base,
        },
        "inputs": {
            "ownerBatchSummary": str(owner_batch_summary) if owner_batch_summary else "self-test",
            "rootSignatureJson": str(root_signature_json) if root_signature_json else None,
            "dryRun": bool(args.dry_run or args.self_test),
            "skipExisting": not bool(args.include_existing),
            "includeSignatureRvas": bool(args.include_signature_rvas),
            "maxRvas": int(args.max_rvas),
            "minOwnerCount": int(args.min_owner_count),
            "minOwnerWindowHits": int(args.min_owner_window_hits),
            "contextBytes": int(args.context_bytes),
            "maxHits": int(args.max_hits),
        },
        "counts": {
            "rankedRvaCount": len(ranked_hints),
            "selectedRvaCount": len(selected),
            "skippedRvaCount": len(skipped),
            "existingRvaCount": len(existing_by_rva),
            "commandStatuses": dict(command_statuses),
            "resultCount": len(results),
        },
        "selectedRvas": selected,
        "skippedRvas": skipped,
        "existingSweepsByRva": existing_by_rva,
        "commands": command_rows,
        "results": results,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "targetMemoryBytesRead": bool(command_rows) and not bool(args.dry_run or args.self_test),
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
            "recommendedAction": "If selected high-signal RVAs still stay heap-only, stop repeating module-hint sweeps and escalate to access-chain tracing or a fresh multi-pose family snapshot.",
        },
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def synthetic_owner_batch() -> dict[str, Any]:
    return {
        "target": {
            "pid": 2928,
            "hwndHex": "0xC0994",
            "processDetails": {
                "startTimeUtc": "2026-05-13T16:17:56.208370Z",
                "moduleBaseAddressHex": "0x7FF71CD90000",
            },
        },
        "inputs": {"rootSignatureJson": "synthetic-root.json"},
        "moduleRvaHints": [
            {"rva": "0x270FE10", "ownerWindowHitCount": 3, "ownerCount": 3, "owners": ["0x1", "0x2", "0x3"]},
            {"rva": "0x26AAE70", "ownerWindowHitCount": 1, "ownerCount": 1, "owners": ["0x4"]},
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run root-signature module-hint sweeps from an owner-batch summary.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--from-owner-batch-summary", type=Path, default=None)
    parser.add_argument("--root-signature-json", type=Path, default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--max-rvas", type=int, default=DEFAULT_MAX_RVAS)
    parser.add_argument("--min-owner-count", type=int, default=1)
    parser.add_argument("--min-owner-window-hits", type=int, default=1)
    parser.add_argument("--include-rva", action="append", default=[])
    parser.add_argument("--exclude-rva", action="append", default=[])
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--include-signature-rvas", action="store_true")
    parser.add_argument("--context-bytes", type=int, default=DEFAULT_CONTEXT_BYTES)
    parser.add_argument("--max-hits", type=int, default=DEFAULT_MAX_HITS)
    parser.add_argument("--report-limit", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.self_test and not args.from_owner_batch_summary:
        raise SystemExit("--from-owner-batch-summary is required unless --self-test is used")
    summary = run(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "selectedRvaCount": summary["counts"]["selectedRvaCount"],
                    "skippedRvaCount": summary["counts"]["skippedRvaCount"],
                    "commandStatuses": summary["counts"]["commandStatuses"],
                    "blockers": summary.get("blockers", []),
                    "warnings": summary.get("warnings", []),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"selectedRvaCount={summary['counts']['selectedRvaCount']}")
        print(f"skippedRvaCount={summary['counts']['skippedRvaCount']}")
    return 2 if summary["status"] == "blocked" else (1 if summary["status"] == "failed" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
