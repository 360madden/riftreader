from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_snapshot_diff import BLOCKED_OPERATIONS, SOURCE_LINKS, int_hex


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_WATCH_SIZE = 12
DEFAULT_POSE_COUNT = 3


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: str) -> int:
    return int(value, 0)


def normalize_hwnd(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return f"0x{int(value, 0):X}"
    except ValueError:
        return value.strip()


def build_safety(*, allow_live_debugger: bool) -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "githubConnectorWrites": False,
        "providerWrites": False,
        "codexMcpConfigured": False,
        "codexMcpServerStarted": False,
        "x64dbgLiveDebuggerApprovedForFutureSession": allow_live_debugger,
        "x64dbgLiveAttachStarted": False,
        "x64dbgCommandsExecuted": False,
        "processAttachOrMemoryReadStarted": False,
        "targetMutationAllowed": False,
        "movementAllowed": False,
        "candidateOnly": True,
        "writeClassOperationsBlocked": True,
        "blockedOperations": list(BLOCKED_OPERATIONS),
    }


def process_identity(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "name": args.process_name,
        "pid": args.target_pid,
        "hwnd": normalize_hwnd(args.target_hwnd),
        "startTimeUtc": args.process_start_time_utc,
    }


def truth_surface(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "kind": "api-now",
        "source": args.api_source,
        "sampledAtUtc": args.api_sampled_at_utc,
        "x": args.api_x,
        "y": args.api_y,
        "z": args.api_z,
    }


def candidate_template(args: argparse.Namespace) -> dict[str, Any]:
    address = args.candidate_address
    axis_offsets = {"x": "0x0", "y": "0x4", "z": "0x8"}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "candidate-template",
        "tool": "x64dbg",
        "capturedAtUtc": None,
        "candidateId": args.candidate_id,
        "process": process_identity(args),
        "truthSurface": truth_surface(args),
        "memoryNow": {
            "address": int_hex(address) if address is not None else None,
            "axisOrder": args.axis_order,
            "x": None,
            "y": None,
            "z": None,
            "sampledAtUtc": None,
        },
        "watchWindow": {
            "baseAddress": int_hex(address) if address is not None else None,
            "sizeBytes": args.watch_size,
            "axisOffsets": axis_offsets,
            "access": "read | write | access",
            "plannedOnly": True,
        },
        "observedAccessEvents": [],
        "instruction": {
            "module": "rift_x64.exe",
            "moduleBase": None,
            "address": None,
            "rva": None,
            "bytes": None,
            "disassembly": None,
            "access": None,
            "registers": {},
            "derivedObjectPointer": None,
            "fieldOffset": None,
        },
        "derivedChain": {
            "rootKind": "pending-module-rva-or-static-owner",
            "module": "rift_x64.exe",
            "moduleBase": None,
            "rootRva": None,
            "offsets": [],
            "fieldOffsets": axis_offsets,
            "chainExpression": None,
        },
        "validation": {
            "sameTarget": False,
            "apiNowVsChainNow": False,
            "multiPose": False,
            "poseCountRequired": args.pose_count,
            "restartValidated": False,
            "runtimeHelperReadback": False,
            "proofOnlyPassed": False,
            "movementProofEligible": False,
        },
        "blockers": [
            "no-x64dbg-access-events-recorded",
            "not-module-relative-rooted",
            "not-multi-pose-validated",
            "not-restart-validated",
            "not-promoted-through-api-now-vs-chain-now",
        ],
    }


def planned_phases(args: argparse.Namespace) -> list[dict[str, Any]]:
    address = int_hex(args.candidate_address) if args.candidate_address is not None else "<candidate-address>"
    return [
        {
            "phase": 0,
            "name": "preflight-no-attach",
            "goal": "Confirm exact target identity, fresh API coordinate, current coordinate candidate, and no other debugger.",
            "allowedNow": True,
        },
        {
            "phase": 1,
            "name": "approved-x64dbg-attach",
            "goal": "After explicit current-turn approval, attach x64dbg only to the recorded PID/HWND/process-start target.",
            "allowedNow": bool(args.allow_live_debugger),
        },
        {
            "phase": 2,
            "name": "12-byte-coordinate-watch-window",
            "goal": f"Set x64dbg data watch/breakpoint over {address}..{address}+0x{args.watch_size - 1:X} for X/Y/Z lane access evidence.",
            "allowedNow": bool(args.allow_live_debugger),
        },
        {
            "phase": 3,
            "name": "multi-pose-access-capture",
            "goal": f"Capture at least {args.pose_count} pose-separated access events with same-target API-now coordinates.",
            "allowedNow": bool(args.allow_live_debugger),
        },
        {
            "phase": 4,
            "name": "module-relative-chain-hypothesis",
            "goal": "Derive module/RVA/static-owner root, offsets, field offsets, and instruction provenance.",
            "allowedNow": False,
        },
        {
            "phase": 5,
            "name": "runtime-readback-without-x64dbg",
            "goal": "Implement repo-owned readback for chain-now vs API-now comparison without debugger dependency.",
            "allowedNow": False,
        },
        {
            "phase": 6,
            "name": "restart-validation-and-proofonly",
            "goal": "Validate chain across restart/client epoch and pass same-target ProofOnly before movement use.",
            "allowedNow": False,
        },
    ]


def validate_args(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if args.candidate_address is None:
        blockers.append("missing-candidate-address")
    if args.target_pid is None:
        blockers.append("missing-target-pid")
    if not args.target_hwnd:
        blockers.append("missing-target-hwnd")
    if not args.process_start_time_utc:
        blockers.append("missing-process-start-time-utc")
    if args.api_x is None or args.api_y is None or args.api_z is None:
        blockers.append("missing-api-coordinate")
    if not args.api_sampled_at_utc:
        blockers.append("missing-api-sampled-at-utc")
    if args.watch_size < 12:
        blockers.append("watch-size-must-cover-12-byte-xyz-triplet")
    if args.pose_count < 3:
        blockers.append("pose-count-must-be-at-least-3")
    return blockers


def build_plan(args: argparse.Namespace, repo_root: Path, run_dir: Path) -> dict[str, Any]:
    blockers = [] if args.self_test else validate_args(args)
    warnings: list[str] = []
    if args.process_name.lower() == "rift_x64" and not args.allow_live_debugger:
        warnings.append("x64dbg live RIFT attach is not authorized in this plan; request explicit current-turn approval before any attach/watchpoint session")
    if args.self_test:
        warnings.append("self-test only; no x64dbg session, RIFT process, watchpoint, memory read, or movement touched")

    summary_json = run_dir / "coord-chain-plan-summary.json"
    summary_md = run_dir / "coord-chain-plan.md"
    template_json = run_dir / "x64dbg-coordinate-chain-candidate-template.json"
    checklist_md = run_dir / "x64dbg-coordinate-chain-session-checklist.md"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "x64dbg-static-coord-chain-plan",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "planned",
        "repoRoot": str(repo_root),
        "process": process_identity(args),
        "truthSurface": truth_surface(args),
        "candidate": {
            "candidateId": args.candidate_id,
            "address": int_hex(args.candidate_address) if args.candidate_address is not None else None,
            "axisOrder": args.axis_order,
            "watchSizeBytes": args.watch_size,
            "poseCountRequired": args.pose_count,
        },
        "plannedPhases": planned_phases(args),
        "promotionGates": [
            "same PID/HWND/process-start target for all samples",
            "fresh API/runtime coordinate sampled close to each chain read",
            "same chain tracks X/Y/Z across at least three displaced poses",
            "module-relative or static-owner root, not heap-only",
            "restart/client-epoch validation",
            "repo-owned runtime readback without x64dbg",
            "same-target ProofOnly pass before movement",
        ],
        "blockers": blockers,
        "warnings": warnings,
        "errors": [],
        "sources": list(SOURCE_LINKS),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "candidateTemplateJson": str(template_json),
            "sessionChecklistMarkdown": str(checklist_md),
        },
        "safety": build_safety(allow_live_debugger=bool(args.allow_live_debugger)),
        "next": {
            "recommendedAction": (
                "Fill the candidate template from an explicitly approved x64dbg watchpoint session, then validate chain-now vs API-now outside x64dbg."
                if not blockers
                else "Provide the missing target/candidate/API fields, then regenerate the coord-chain plan."
            )
        },
    }
    return summary


def markdown_summary(summary: dict[str, Any]) -> str:
    candidate = summary["candidate"]
    safety = summary["safety"]
    lines = [
        "# x64dbg static coordinate pointer-chain plan",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated UTC: `{summary['generatedAtUtc']}`",
        f"- Candidate: `{candidate.get('candidateId')}` at `{candidate.get('address')}`",
        f"- Movement allowed: `{str(safety.get('movementAllowed')).lower()}`",
        f"- x64dbg live attach started: `{str(safety.get('x64dbgLiveAttachStarted')).lower()}`",
        f"- x64dbg commands executed: `{str(safety.get('x64dbgCommandsExecuted')).lower()}`",
        "",
        "## Planned phases",
        "",
        "| Phase | Name | Allowed now | Goal |",
        "|---:|---|---|---|",
    ]
    for phase in summary["plannedPhases"]:
        lines.append(
            f"| `{phase['phase']}` | `{phase['name']}` | `{str(phase['allowedNow']).lower()}` | {phase['goal']} |"
        )
    if summary["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "## Promotion gates",
            "",
        ]
    )
    lines.extend(f"- {gate}" for gate in summary["promotionGates"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This plan creates artifacts only. It does not attach x64dbg, set watchpoints,",
            "read live memory, configure MCP, send input, or authorize movement.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def checklist_markdown(summary: dict[str, Any]) -> str:
    candidate = summary["candidate"]
    process = summary["process"]
    truth = summary["truthSurface"]
    lines = [
        "# x64dbg coordinate-chain session checklist",
        "",
        "Use only after explicit current-turn approval for a live debugger session.",
        "",
        "## Target",
        "",
        f"- Process: `{process.get('name')}`",
        f"- PID: `{process.get('pid')}`",
        f"- HWND: `{process.get('hwnd')}`",
        f"- Process start UTC: `{process.get('startTimeUtc')}`",
        f"- Candidate address: `{candidate.get('address')}`",
        f"- API coordinate: `X={truth.get('x')}`, `Y={truth.get('y')}`, `Z={truth.get('z')}` at `{truth.get('sampledAtUtc')}`",
        "",
        "## Required capture per access event",
        "",
        "- pose label and fresh API coordinate;",
        "- instruction address, module, module base, RVA, bytes, disassembly;",
        "- read/write/access type;",
        "- registers used to address the coordinate field;",
        "- derived object pointer and field offset;",
        "- memory X/Y/Z read at the candidate/derived chain;",
        "- confirmation that PID/HWND/process-start still match.",
        "",
        "## Stop immediately if",
        "",
        "- target PID/HWND/process-start changes;",
        "- API/runtime coordinate is stale or missing;",
        "- x64dbg or RIFT becomes unstable;",
        "- another debugger-class tool is attached;",
        "- the workflow would require patching or write-class operations.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    run_dir = Path(summary["artifacts"]["runDirectory"])
    template = candidate_template(argparse.Namespace(**{
        "candidate_address": int(summary["candidate"]["address"], 16) if summary["candidate"].get("address") else None,
        "candidate_id": summary["candidate"]["candidateId"],
        "process_name": summary["process"]["name"],
        "target_pid": summary["process"]["pid"],
        "target_hwnd": summary["process"]["hwnd"],
        "process_start_time_utc": summary["process"]["startTimeUtc"],
        "api_source": summary["truthSurface"]["source"],
        "api_sampled_at_utc": summary["truthSurface"]["sampledAtUtc"],
        "api_x": summary["truthSurface"]["x"],
        "api_y": summary["truthSurface"]["y"],
        "api_z": summary["truthSurface"]["z"],
        "axis_order": summary["candidate"]["axisOrder"],
        "watch_size": summary["candidate"]["watchSizeBytes"],
        "pose_count": summary["candidate"]["poseCountRequired"],
    }))
    write_json(Path(summary["artifacts"]["candidateTemplateJson"]), template)
    write_text_atomic(Path(summary["artifacts"]["sessionChecklistMarkdown"]), checklist_markdown(summary))
    write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
    write_json(Path(summary["artifacts"]["summaryJson"]), summary)
    run_dir.mkdir(parents=True, exist_ok=True)


def apply_self_test_defaults(args: argparse.Namespace) -> None:
    args.process_name = "rift_x64"
    args.target_pid = 12345
    args.target_hwnd = "0xABCDEF"
    args.process_start_time_utc = "2026-05-12T20:00:00Z"
    args.candidate_id = "x64dbg-coord-chain-self-test"
    args.candidate_address = 0x20005B30800
    args.api_source = "synthetic-api-now"
    args.api_sampled_at_utc = "2026-05-12T20:00:10Z"
    args.api_x = 7376.87
    args.api_y = 863.82
    args.api_z = 2990.35


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a safe x64dbg static pointer-chain workflow for coordinate data.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--process-start-time-utc", default=None)
    parser.add_argument("--candidate-id", default="x64dbg-coord-chain-candidate-000001")
    parser.add_argument("--candidate-address", type=parse_int, default=None)
    parser.add_argument("--axis-order", choices=["xyz"], default="xyz")
    parser.add_argument("--watch-size", type=int, default=DEFAULT_WATCH_SIZE)
    parser.add_argument("--pose-count", type=int, default=DEFAULT_POSE_COUNT)
    parser.add_argument("--api-source", default="fresh-api-runtime-coordinate")
    parser.add_argument("--api-sampled-at-utc", default=None)
    parser.add_argument("--api-x", type=float, default=None)
    parser.add_argument("--api-y", type=float, default=None)
    parser.add_argument("--api-z", type=float, default=None)
    parser.add_argument("--allow-live-debugger", action="store_true")
    return parser


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-coord-chain-plan-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        apply_self_test_defaults(args)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    summary = build_plan(args, repo_root, run_dir)
    write_outputs(summary)

    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "candidateTemplateJson": summary["artifacts"]["candidateTemplateJson"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"summaryMarkdown={summary['artifacts']['summaryMarkdown']}")
        if summary["blockers"]:
            print("blockers=" + ";".join(summary["blockers"]))
        if summary["warnings"]:
            print("warnings=" + ";".join(summary["warnings"]))
    return 2 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
