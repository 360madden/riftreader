#!/usr/bin/env python3
"""Catalog repo and external RiftReader tools without running live tooling.

The catalog is a read-only routing helper. It inventories known repo-owned
helpers plus selected tools under ``C:\\RIFT MODDING\\Tools`` and classifies each
entry by default workflow risk. It does not launch Ghidra/x64dbg/Sysinternals,
attach a debugger, read target memory, send input, mutate Git, or write provider
repositories. Optional writes are summaries under ignored ``.riftreader-local``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    from .common import find_repo_root, repo_rel, safety_flags, timestamped_output_dir, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, timestamped_output_dir, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-tool-catalog-v0.1.2"
DEFAULT_EXTERNAL_TOOLS_ROOT = Path(r"C:\RIFT MODDING\Tools")
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "tool-catalog"
DEFAULT_RIFT_X64_BINARY_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"),
    Path(r"C:\Program Files\Glyph\Games\RIFT\Live\rift_x64.exe"),
)
GHIDRA_RECOMMENDED_TRIGGERS = [
    "navigation-pointer-discovery",
    "facing-yaw-turn-rate-candidate-review",
    "restart-survival-failure",
    "owner-layout-offset-semantics",
    "static-root-or-xref-discovery",
]
GHIDRA_TARGET_OFFSETS = [
    "rift_x64+0x32EBC80",
    "owner+0x300",
    "owner+0x304",
    "owner+0x30C",
    "owner+0x310",
    "owner+0x314",
    "owner+0x320",
    "owner+0x324",
    "owner+0x328",
    "owner+0x438",
    "owner+0x43C",
    "owner+0x440",
]
GHIDRA_WHY_USE_MORE_OFTEN = [
    "Ghidra is an industry-grade reverse-engineering platform, not a simple reader: decompiler, xrefs, control-flow, data-flow, and type/structure recovery",
    "offline xrefs/writers can explain whether an offset is persistent state or transient derived state before live probes",
    "use Ghidra as the primary static-analysis pass; debugger/watchpoints should answer narrowed questions after static evidence",
]
GHIDRA_CAPABILITIES = [
    "decompiler",
    "cross-references",
    "writer-site discovery",
    "control-flow analysis",
    "data-flow analysis",
    "type-and-structure recovery",
    "offline binary import",
]

RISK_SORT = {
    "safe-read-only": 0,
    "offline-static-analysis": 1,
    "truth-write-gated": 2,
    "process-inspection-gated": 2,
    "guarded-live-input": 3,
    "debugger-gated": 4,
    "retired": 5,
    "missing": 6,
}


class ToolCatalogError(RuntimeError):
    """Raised for controlled catalog failures."""


@dataclass(frozen=True)
class ToolEntry:
    key: str
    label: str
    kind: str
    path: Path
    exists: bool
    risk: str
    defaultUse: str
    allowedInAutonomy: bool
    requiresExplicitApproval: bool
    command: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    replacementKey: str | None = None

    def as_dict(self, repo_root: Path | None = None) -> dict[str, Any]:
        rendered_path = repo_rel(repo_root, self.path) if repo_root is not None else str(self.path)
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "path": rendered_path,
            "exists": self.exists,
            "risk": self.risk,
            "defaultUse": self.defaultUse,
            "allowedInAutonomy": self.allowedInAutonomy,
            "requiresExplicitApproval": self.requiresExplicitApproval,
            "command": self.command,
            "notes": self.notes,
            "replacementKey": self.replacementKey,
        }


def safe_count(items: Iterable[Any]) -> int:
    return sum(1 for _ in items)


def count_files(root: Path, suffixes: set[str] | None = None) -> int:
    if not root.exists():
        return 0
    total = 0
    for item in root.glob("*"):
        if item.is_file() and (suffixes is None or item.suffix.lower() in suffixes):
            total += 1
    return total


def repo_tool(
    repo_root: Path,
    *,
    key: str,
    label: str,
    kind: str,
    rel_path: str,
    risk: str,
    default_use: str,
    allowed: bool,
    approval: bool,
    command: list[str] | None = None,
    notes: list[str] | None = None,
    replacement_key: str | None = None,
) -> ToolEntry:
    path = repo_root / rel_path
    return ToolEntry(
        key=key,
        label=label,
        kind=kind,
        path=path,
        exists=path.exists(),
        risk=risk if path.exists() else "missing",
        defaultUse=default_use,
        allowedInAutonomy=allowed and path.exists(),
        requiresExplicitApproval=approval,
        command=command or [],
        notes=notes or [],
        replacementKey=replacement_key,
    )


def external_tool(
    external_root: Path,
    *,
    key: str,
    label: str,
    kind: str,
    rel_path: str,
    risk: str,
    default_use: str,
    allowed: bool,
    approval: bool,
    notes: list[str] | None = None,
    replacement_key: str | None = None,
) -> ToolEntry:
    path = external_root / rel_path
    exists = path.exists()
    return ToolEntry(
        key=key,
        label=label,
        kind=kind,
        path=path,
        exists=exists,
        risk=risk if exists else "missing",
        defaultUse=default_use,
        allowedInAutonomy=allowed and exists,
        requiresExplicitApproval=approval,
        command=[str(path)] if exists else [],
        notes=notes or [],
        replacementKey=replacement_key,
    )


def build_repo_entries(repo_root: Path) -> list[ToolEntry]:
    return [
        repo_tool(
            repo_root,
            key="decision-packet",
            label="Decision packet",
            kind="control-plane",
            rel_path="scripts/riftreader-decision-packet.cmd",
            risk="safe-read-only",
            default_use="first command before choosing a lane",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-decision-packet.cmd", "--compact-json", "--write"],
        ),
        repo_tool(
            repo_root,
            key="workflow-status",
            label="Compact workflow status",
            kind="control-plane",
            rel_path="scripts/riftreader-workflow-status.cmd",
            risk="safe-read-only",
            default_use="refresh compact local truth",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-workflow-status.cmd", "--compact-json"],
        ),
        repo_tool(
            repo_root,
            key="tool-catalog",
            label="Tool catalog",
            kind="control-plane",
            rel_path="scripts/riftreader-tool-catalog.cmd",
            risk="safe-read-only",
            default_use="route repo and external tools by risk before use",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-tool-catalog.cmd", "--compact-json"],
        ),
        repo_tool(
            repo_root,
            key="ghidra-static-evidence",
            label="Ghidra static evidence runner",
            kind="offline-static-analysis",
            rel_path="scripts/riftreader-ghidra-static-evidence.cmd",
            risk="offline-static-analysis",
            default_use="run or plan the primary offline Ghidra decompiler/xref/writer evidence lane with Windows path fixups",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-ghidra-static-evidence.cmd", "--plan", "--json"],
            notes=["actual --run writes ignored scripts/captures artifacts only; no live process attach/read/write"],
        ),
        repo_tool(
            repo_root,
            key="static-field-access-matrix",
            label="Static field access matrix",
            kind="offline-static-analysis",
            rel_path="scripts/riftreader-static-field-access-matrix.cmd",
            risk="offline-static-analysis",
            default_use="quick bounded Capstone scan of owner-relative fields before Phase 1 actor/stat or target probes",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-static-field-access-matrix.cmd", "--json"],
            notes=[
                "offline installed-binary scan only; no live process access, input, debugger, provider write, or promotion",
                "default run is instruction-bounded; use --full-scan or --rva-window for deeper static coverage",
            ],
        ),
        repo_tool(
            repo_root,
            key="phase1-target-entity-snapshot",
            label="Phase 1 target entity snapshot",
            kind="phase1-target-discovery",
            rel_path="scripts/riftreader-phase1-target-entity-snapshot.cmd",
            risk="safe-read-only",
            default_use="capture post-flush selected-target export and current target-reader blocker for Phase 1 target entity discovery",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-phase1-target-entity-snapshot.cmd",
                "--pid",
                "<current-pid>",
                "--hwnd",
                "<current-hwnd>",
                "--json",
            ],
            notes=[
                "does not select a target, send input, reload UI, attach a debugger, write provider repos, or promote truth",
                "reads post-flush SavedVariables as a snapshot only and records target-current reader failures as blockers",
            ],
        ),
        repo_tool(
            repo_root,
            key="policy-lint",
            label="Policy lint",
            kind="validation",
            rel_path="scripts/riftreader-policy-lint.cmd",
            risk="safe-read-only",
            default_use="changed-scope workflow policy validation",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-policy-lint.cmd",
                "--json",
                "validate-repo",
                "--scope",
                "changed",
                "--no-write-summary",
            ],
        ),
        repo_tool(
            repo_root,
            key="validation-ledger",
            label="Timestamped validation ledger",
            kind="validation",
            rel_path="scripts/riftreader-validation-ledger.cmd",
            risk="safe-read-only",
            default_use="timestamped validation runs with command durations and slow-command warnings",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-validation-ledger.cmd", "--tier", "smoke"],
        ),
        repo_tool(
            repo_root,
            key="navigation-pointer-discovery",
            label="Navigation pointer discovery dashboard",
            kind="navigation-report",
            rel_path="scripts/riftreader-navigation-pointer-discovery.cmd",
            risk="safe-read-only",
            default_use="index latest coordinate/facing/turn-rate discovery artifacts before choosing the next navigation lane",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-navigation-pointer-discovery.cmd", "--json", "--write"],
            notes=["artifact index only; no live process read, live input, debugger attach, or proof promotion"],
        ),
        repo_tool(
            repo_root,
            key="current-truth-refresh-plan",
            label="Current truth refresh dry-run plan",
            kind="navigation-report",
            rel_path="scripts/riftreader-current-truth-refresh-plan.cmd",
            risk="safe-read-only",
            default_use="build ignored proposed current-truth JSON/diff from dashboard evidence without applying it",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-current-truth-refresh-plan.cmd", "--json", "--write"],
            notes=["dry-run only; tracked current-truth updates remain an explicit gate"],
        ),
        repo_tool(
            repo_root,
            key="current-truth-refresh-apply",
            label="Current truth refresh apply gate",
            kind="truth-refresh-gate",
            rel_path="scripts/riftreader-current-truth-refresh-apply.cmd",
            risk="truth-write-gated",
            default_use="validate the latest ignored current-truth proposal; --apply writes tracked current-truth after deliberate review",
            allowed=False,
            approval=True,
            command=["scripts\\riftreader-current-truth-refresh-apply.cmd", "--json"],
            notes=[
                "without --apply this is dry-run validation only",
                "--apply writes docs/recovery/current-truth.json but performs no live input, target memory access, Git mutation, or promotion",
            ],
        ),
        repo_tool(
            repo_root,
            key="facing-target-three-pose-gate",
            label="Facing-target three-pose gate",
            kind="navigation-report",
            rel_path="scripts/riftreader-facing-target-three-pose-gate.cmd",
            risk="safe-read-only",
            default_use="package existing route-step summaries into a formal candidate-facing three-pose gate",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-facing-target-three-pose-gate.cmd", "--json"],
            notes=["report-only; sends no new input and never promotes facing truth"],
        ),
        repo_tool(
            repo_root,
            key="facing-target-restart-survival-packet",
            label="Facing-target restart survival packet",
            kind="navigation-report",
            rel_path="scripts/riftreader-facing-target-restart-survival-packet.cmd",
            risk="safe-read-only",
            default_use="compare existing pre/post nav-state readbacks for candidate-facing restart/relog survival",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-facing-target-restart-survival-packet.cmd", "--json"],
            notes=["report-only; does not restart the game and never promotes facing truth"],
        ),
        repo_tool(
            repo_root,
            key="facing-target-promotion-readiness-review",
            label="Facing-target promotion-readiness review",
            kind="navigation-report",
            rel_path="scripts/riftreader-facing-target-promotion-readiness-review.cmd",
            risk="safe-read-only",
            default_use="review existing three-pose, restart/relog, turn-forward, and static-source evidence without promoting",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-facing-target-promotion-readiness-review.cmd", "--json"],
            notes=["report-only; explicit promotion gate and fresh readbacks still required after this review"],
        ),
        repo_tool(
            repo_root,
            key="facing-target-promotion-apply",
            label="Facing-target promotion apply gate",
            kind="truth-refresh-gate",
            rel_path="scripts/riftreader-facing-target-promotion-apply.cmd",
            risk="truth-write-gated",
            default_use="write the explicit static-owner facing/yaw promotion artifact after readiness review and fresh readbacks pass",
            allowed=True,
            approval=True,
            command=["scripts\\riftreader-facing-target-promotion-apply.cmd", "--json"],
            notes=["--apply writes tracked promotion/current-truth docs; sends no input and performs no proof/actor-chain promotion"],
        ),
        repo_tool(
            repo_root,
            key="turn-rate-promotion-readiness-review",
            label="Turn-rate promotion-readiness review",
            kind="navigation-report",
            rel_path="scripts/riftreader-turn-rate-promotion-readiness-review.cmd",
            risk="safe-read-only",
            default_use="review existing owner+0x304 turn-rate evidence without promoting",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-turn-rate-promotion-readiness-review.cmd", "--json"],
            notes=["report-only; explicit promotion gate and fresh readbacks still required after this review"],
        ),
        repo_tool(
            repo_root,
            key="owner-0x304-semantics-review",
            label="Owner +0x304 semantics review",
            kind="navigation-report",
            rel_path="scripts/riftreader-owner-0x304-semantics-review.cmd",
            risk="safe-read-only",
            default_use="classify existing owner+0x304 camera-yaw and turn-rate contrast evidence without promoting",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-owner-0x304-semantics-review.cmd", "--json"],
            notes=["report-only; keeps 0x304 candidate-only when evidence shows yaw-adjacent scalar rather than active turn rate"],
        ),
        repo_tool(
            repo_root,
            key="turn-rate-promotion-apply",
            label="Turn-rate promotion apply gate",
            kind="truth-refresh-gate",
            rel_path="scripts/riftreader-turn-rate-promotion-apply.cmd",
            risk="truth-write-gated",
            default_use="write the explicit static-owner turn-rate promotion artifact after readiness review and fresh readbacks pass",
            allowed=True,
            approval=True,
            command=["scripts\\riftreader-turn-rate-promotion-apply.cmd", "--json"],
            notes=["--apply writes tracked promotion/current-truth docs; sends no input and performs no proof/actor-chain/navigation-control promotion"],
        ),
        repo_tool(
            repo_root,
            key="sensitive-artifact-scan",
            label="Sensitive artifact scan",
            kind="validation",
            rel_path="scripts/riftreader-sensitive-artifact-scan.cmd",
            risk="safe-read-only",
            default_use="pre-commit/staged safety scan",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-sensitive-artifact-scan.cmd", "--staged", "--json"],
        ),
        repo_tool(
            repo_root,
            key="live-input-surface-audit",
            label="Live input surface audit",
            kind="safety-audit",
            rel_path="scripts/riftreader-live-input-surface-audit.cmd",
            risk="safe-read-only",
            default_use="classify live-input-capable repo surfaces without touching the game",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-live-input-surface-audit.cmd", "--json"],
        ),
        repo_tool(
            repo_root,
            key="actor-chain-no-debug-status",
            label="Actor-chain no-debug status",
            kind="actor-chain-status",
            rel_path="scripts/riftreader-actor-chain-no-debug-status.cmd",
            risk="safe-read-only",
            default_use="separate actor/stat chain status gate; never promotes candidate evidence",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-actor-chain-no-debug-status.cmd", "--json"],
            notes=["keeps actor/stat chain evidence candidate-only until explicit proof gates pass"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-coordinate-chain-readback",
            label="Static-owner coordinate-chain readback",
            kind="navigation-readback",
            rel_path="scripts/static-owner-coordinate-chain-readback.cmd",
            risk="safe-read-only",
            default_use="fresh exact-target promoted coordinate-chain readback before navigation",
            allowed=True,
            approval=False,
            command=[
                "scripts\\static-owner-coordinate-chain-readback.cmd",
                "--use-current-truth",
                "--samples",
                "3",
                "--interval-seconds",
                "0.20",
                "--expect-stationary",
                "--json",
            ],
            notes=["reads target memory for the promoted coordinate chain; sends no input and performs no debugger attach"],
        ),
        repo_tool(
            repo_root,
            key="navigation-consumer-state",
            label="Navigation consumer state",
            kind="navigation-readback",
            rel_path="scripts/riftreader-navigation-consumer-state.cmd",
            risk="safe-read-only",
            default_use="emit stable read-only current position/yaw JSON for external navigation consumers",
            allowed=True,
            approval=False,
            command=["scripts\\riftreader-navigation-consumer-state.cmd", "--json", "--write"],
            notes=[
                "reads promoted coordinate + facing/yaw state only; sends no input and performs no debugger attach",
                "turn-rate/support fields are diagnostic-only and do not authorize route control",
            ],
        ),
        repo_tool(
            repo_root,
            key="static-owner-nav-now",
            label="Static-owner current readback",
            kind="navigation-readback",
            rel_path="scripts/static-owner-nav-now.cmd",
            risk="safe-read-only",
            default_use="fresh exact-target static-chain readback before movement",
            allowed=True,
            approval=False,
            command=["scripts\\static-owner-nav-now.cmd", "--json"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-turn-aware-plan",
            label="Static-owner turn-aware route plan",
            kind="navigation-plan",
            rel_path="scripts/static-owner-turn-aware-route-plan.cmd",
            risk="safe-read-only",
            default_use="dry-run turn decision; never promotes candidate yaw",
            allowed=True,
            approval=False,
            command=["scripts\\static-owner-turn-aware-route-plan.cmd", "--json"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-camera-yaw-classification",
            label="Static-owner camera/yaw classification",
            kind="navigation-live-gated",
            rel_path="scripts/static-owner-camera-yaw-classification.cmd",
            risk="guarded-live-input",
            default_use="candidate-only visual-vs-static-yaw classification before any turn-dependent route",
            allowed=False,
            approval=True,
            command=["scripts\\static-owner-camera-yaw-classification.cmd", "--stimulus-approved", "--json"],
            notes=[
                "sends one approved exact-target mouse-look stimulus",
                "records visual screenshot/raw-diff, nav-state, and owner-window deltas",
                "report-only --aggregate-summary-json mode compares existing summaries without live input",
                "never promotes facing, turn-rate, actor chains, or proof",
            ],
        ),
        repo_tool(
            repo_root,
            key="static-owner-turn-forward-experiment",
            label="Static-owner turn-forward experiment",
            kind="navigation-live-gated",
            rel_path="scripts/static-owner-turn-forward-experiment.cmd",
            risk="guarded-live-input",
            default_use="single gated turn then delegated forward pulse after explicit approval",
            allowed=False,
            approval=True,
            command=["scripts\\static-owner-turn-forward-experiment.cmd", "--json"],
            notes=["requires exact target, fresh readback, turn approval, and movement approval"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-route-step",
            label="Static-owner route step",
            kind="navigation-live-gated",
            rel_path="scripts/static-owner-nav-route-step.cmd",
            risk="guarded-live-input",
            default_use="one bounded forward movement primitive after explicit movement approval",
            allowed=False,
            approval=True,
            command=["scripts\\static-owner-nav-route-step.cmd", "--json"],
            notes=["delegates input to repo-owned C# ScanCode path"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-route-run",
            label="Static-owner route runner",
            kind="navigation-live-gated",
            rel_path="scripts/static-owner-nav-route-run.cmd",
            risk="guarded-live-input",
            default_use="conservative multi-step run only after one-step and turn-forward validation",
            allowed=False,
            approval=True,
            command=["scripts\\static-owner-nav-route-run.cmd", "--json"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-route-run-report",
            label="Static-owner route-run report",
            kind="navigation-report",
            rel_path="scripts/static-owner-nav-report-route-run.cmd",
            risk="safe-read-only",
            default_use="review saved route-run summaries with optional turn and turn-forward evidence",
            allowed=True,
            approval=False,
            command=["scripts\\static-owner-nav-report-route-run.cmd", "<route-run-summary.json>", "--json"],
            notes=["saved-summary review only; sends no input and reads no live target memory"],
        ),
        repo_tool(
            repo_root,
            key="static-owner-route-sequence-contract",
            label="Static-owner route sequence dry-run contract",
            kind="navigation-report",
            rel_path="scripts/static-owner-continuous-route-sequence-contract.cmd",
            risk="safe-read-only",
            default_use="validate saved continuous route sequence dry-run summaries for external consumers",
            allowed=True,
            approval=False,
            command=[
                "scripts\\static-owner-continuous-route-sequence-contract.cmd",
                "<sequence-summary.json>",
                "--json",
            ],
            notes=[
                "saved-summary contract only; sends no input and reads no live target memory",
                "requires dryRun=true, no movement/input, and no simulated multi-waypoint arrival claims",
            ],
        ),
        repo_tool(
            repo_root,
            key="navigation-waypoint-readiness",
            label="Navigation waypoint readiness",
            kind="navigation-report",
            rel_path="scripts/riftreader-navigation-waypoint-readiness.cmd",
            risk="safe-read-only",
            default_use="lint/normalize waypoint files, run a no-input sequence dry-run, and validate the saved contract report",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-navigation-waypoint-readiness.cmd",
                "--waypoint-sequence-json",
                "<waypoints.json>",
                "--json",
            ],
            notes=[
                "no input/movement; dry-run may perform read-only current-target memory reads",
                "use --skip-dry-run for offline lint-only normalization",
                "writes normalized waypoints, sequence dry-run summary, and contract report artifacts",
            ],
        ),
        repo_tool(
            repo_root,
            key="navigation-schema-validate",
            label="Navigation consumer schema validator",
            kind="navigation-report",
            rel_path="scripts/riftreader-navigation-schema-validate.cmd",
            risk="safe-read-only",
            default_use="validate saved navigation JSON artifacts against tracked consumer schemas",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-navigation-schema-validate.cmd",
                "--input",
                "<summary.json>",
                "--json",
            ],
            notes=[
                "saved JSON only; no live target reads, input, movement, debugger attach, provider write, or promotion",
                "infers schema from kind or provenance.kind unless --schema-key is supplied",
            ],
        ),
        repo_tool(
            repo_root,
            key="navigation-consumer-demo",
            label="Navigation consumer demo report",
            kind="navigation-report",
            rel_path="scripts/riftreader-navigation-consumer-demo.cmd",
            risk="safe-read-only",
            default_use="summarize saved consumer-state, waypoint readiness, dry-run, contract, and schema artifacts for downstream projects",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-navigation-consumer-demo.cmd",
                "--waypoint-readiness-json",
                "<readiness-summary.json>",
                "--json",
            ],
            notes=[
                "saved JSON only; no live target reads, input, movement, debugger attach, provider write, or promotion",
                "reports render/dry-run readiness separately from gated live-navigation execution",
            ],
        ),
        repo_tool(
            repo_root,
            key="navigation-consumer-refresh",
            label="Navigation consumer refresh",
            kind="navigation-readback",
            rel_path="scripts/riftreader-navigation-consumer-refresh.cmd",
            risk="safe-read-only",
            default_use="refresh consumer pose and rerun downstream consumer demo without sending input or authorizing live execution",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-navigation-consumer-refresh.cmd",
                "--waypoint-readiness-json",
                "<readiness-summary.json>",
                "--json",
            ],
            notes=[
                "performs read-only target memory read through navigation-consumer-state; no input, movement, debugger attach, provider write, or promotion",
                "live route execution remains gated even when canQueueGatedLiveRunRequest is true",
            ],
        ),
        repo_tool(
            repo_root,
            key="navigation-route-preview",
            label="Navigation route preview",
            kind="navigation-report",
            rel_path="scripts/riftreader-navigation-route-preview.cmd",
            risk="safe-read-only",
            default_use="build a saved-artifact route preview with per-leg distance, bearing, yaw delta, and arrival radius for downstream map/UI consumers",
            allowed=True,
            approval=False,
            command=[
                "scripts\\riftreader-navigation-route-preview.cmd",
                "--waypoint-readiness-json",
                "<readiness-summary.json>",
                "--json",
            ],
            notes=[
                "saved JSON only; no live target reads, input, movement, debugger attach, provider write, or promotion",
                "live route execution remains gated even when preview says a request can be queued",
            ],
        ),
        repo_tool(
            repo_root,
            key="sendinput-primitive",
            label="Repo-owned C# SendInput primitive",
            kind="input-primitive",
            rel_path="tools/RiftReader.SendInput/Program.cs",
            risk="guarded-live-input",
            default_use="primitive only; caller owns exact target and approval gates",
            allowed=False,
            approval=True,
            notes=["do not call directly for route logic"],
        ),
        repo_tool(
            repo_root,
            key="window-tools",
            label="Repo-owned WindowTools primitive",
            kind="window-primitive",
            rel_path="tools/RiftReader.WindowTools/Program.cs",
            risk="guarded-live-input",
            default_use="inspect/resize/click primitive; clicks require explicit gate",
            allowed=False,
            approval=True,
        ),
        repo_tool(
            repo_root,
            key="riftscan-milestone-review",
            label="RiftScan milestone review",
            kind="provider-coordination",
            rel_path="scripts/riftscan_milestone_review.py",
            risk="safe-read-only",
            default_use="read-only strategy gate after major milestones",
            allowed=True,
            approval=False,
            command=["python", "scripts\\riftscan_milestone_review.py", "--json"],
        ),
        repo_tool(
            repo_root,
            key="opencode-retired",
            label="OpenCode bridge surface",
            kind="retired-surface",
            rel_path="tools/riftreader_workflow/opencode_bridge.py",
            risk="retired",
            default_use="historical maintenance only; not active workflow",
            allowed=False,
            approval=True,
            replacement_key="decision-packet",
            notes=["requires explicit reauthorization before any active OpenCode work"],
        ),
    ]


def build_external_entries(external_root: Path) -> list[ToolEntry]:
    return [
        external_tool(
            external_root,
            key="ghidra-headless",
            label="Ghidra headless decompiler/static analyzer wrapper",
            kind="offline-static-analysis",
            rel_path="ghidra-headless.bat",
            risk="offline-static-analysis",
            default_use="primary offline reverse-engineering/decompiler lane for pointer-chain research, xrefs, writers, and owner-layout recovery",
            allowed=True,
            approval=False,
            notes=[
                "treat as a strong worldwide RE platform, not a simple reader",
                "plan commands first; do not attach to live RIFT",
            ],
        ),
        external_tool(
            external_root,
            key="ghidra-gui",
            label="Ghidra GUI launcher",
            kind="offline-static-analysis",
            rel_path="ghidra_12.1_PUBLIC/ghidraRun.bat",
            risk="offline-static-analysis",
            default_use="manual full Ghidra reverse-engineering session: decompiler, xrefs, function/data type recovery",
            allowed=True,
            approval=False,
        ),
        external_tool(
            external_root,
            key="x64dbg-gui",
            label="x64dbg GUI",
            kind="debugger",
            rel_path="x64dbg/release/x64/x64dbg.exe",
            risk="debugger-gated",
            default_use="only for a narrow approved provenance question after offline evidence",
            allowed=False,
            approval=True,
            replacement_key="ghidra-headless",
            notes=["debugger attach/breakpoints/watchpoints are gated"],
        ),
        external_tool(
            external_root,
            key="x64dbg-headless",
            label="x64dbg headless",
            kind="debugger",
            rel_path="x64dbg/release/x64/headless.exe",
            risk="debugger-gated",
            default_use="not default; requires explicit current debugger approval",
            allowed=False,
            approval=True,
            replacement_key="ghidra-headless",
        ),
        external_tool(
            external_root,
            key="sysinternals-listdlls",
            label="Sysinternals ListDLLs",
            kind="process-inspection",
            rel_path="SysinternalsSuite/Listdlls64.exe",
            risk="process-inspection-gated",
            default_use="read-only module inventory when process evidence is needed",
            allowed=True,
            approval=False,
            notes=["prefer wrapper/planned command before live-process use"],
        ),
        external_tool(
            external_root,
            key="sysinternals-handle",
            label="Sysinternals Handle",
            kind="process-inspection",
            rel_path="SysinternalsSuite/handle64.exe",
            risk="process-inspection-gated",
            default_use="read-only handle inventory when needed",
            allowed=True,
            approval=False,
            notes=["do not close handles from automation"],
        ),
        external_tool(
            external_root,
            key="sysinternals-procdump",
            label="Sysinternals ProcDump",
            kind="process-dump",
            rel_path="SysinternalsSuite/procdump64.exe",
            risk="process-inspection-gated",
            default_use="dump planning only unless explicitly approved",
            allowed=False,
            approval=True,
            notes=["dump creation can be intrusive and writes large artifacts"],
        ),
        external_tool(
            external_root,
            key="sysinternals-vmmap",
            label="Sysinternals VMMap",
            kind="process-inspection",
            rel_path="SysinternalsSuite/vmmap64.exe",
            risk="process-inspection-gated",
            default_use="manual memory map inspection after exact target confirmation",
            allowed=False,
            approval=True,
        ),
    ]


def count_by(entries: Iterable[ToolEntry], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = str(getattr(entry, field_name))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (RISK_SORT.get(item[0], 99), item[0])))


def build_inventory(repo_root: Path, external_tools_root: Path) -> dict[str, Any]:
    scripts_root = repo_root / "scripts"
    repo_tools_root = repo_root / "tools"
    root_items = []
    if external_tools_root.exists():
        for child in sorted(external_tools_root.iterdir(), key=lambda item: item.name.lower()):
            root_items.append({"name": child.name, "type": "dir" if child.is_dir() else "file", "path": str(child)})
    return {
        "repoScripts": {
            "path": repo_rel(repo_root, scripts_root),
            "exists": scripts_root.exists(),
            "topLevelFileCount": count_files(scripts_root),
            "pythonCount": count_files(scripts_root, {".py"}),
            "powershellCount": count_files(scripts_root, {".ps1"}),
            "cmdCount": count_files(scripts_root, {".cmd"}),
        },
        "repoTools": {
            "path": repo_rel(repo_root, repo_tools_root),
            "exists": repo_tools_root.exists(),
            "topLevelDirectoryCount": safe_count(item for item in repo_tools_root.iterdir() if item.is_dir())
            if repo_tools_root.exists()
            else 0,
        },
        "externalTools": {"path": str(external_tools_root), "exists": external_tools_root.exists(), "rootItems": root_items},
    }


def build_default_ghidra_binary_candidates() -> list[dict[str, Any]]:
    return [
        {
            "label": "installed-rift-live-x64",
            "path": str(path),
            "exists": path.is_file(),
            "recommended": path.is_file(),
        }
        for path in DEFAULT_RIFT_X64_BINARY_CANDIDATES
    ]


def first_existing_binary_path(candidates: list[dict[str, Any]]) -> Path | None:
    for item in candidates:
        path = Path(str(item.get("path") or ""))
        if item.get("exists") and path.is_file():
            return path
    return None


def build_ghidra_static_lane(repo_root: Path, external_tools_root: Path, *, binary_path: Path | None = None) -> dict[str, Any]:
    wrapper = external_tools_root / "ghidra-headless.bat"
    output_root = repo_root / "scripts" / "captures" / "ghidra-static-analysis-<timestamp>"
    project_dir = repo_root / "scripts" / "captures" / "ghidra-static-projects" / "project-<timestamp>"
    project_name = "riftreader-offline-static-analysis"
    default_binary_candidates = build_default_ghidra_binary_candidates()
    suggested_binary = binary_path or first_existing_binary_path(default_binary_candidates)
    import_arg = str(binary_path) if binary_path else "<offline-binary-path>"
    command = ["scripts\\riftreader-ghidra-static-evidence.cmd", "--run", "--binary-path", import_arg, "--json"]
    plan_command = ["scripts\\riftreader-ghidra-static-evidence.cmd", "--plan", "--json"]
    suggested_import_arg = str(suggested_binary) if suggested_binary else "<offline-binary-path>"
    suggested_command = ["scripts\\riftreader-ghidra-static-evidence.cmd", "--run", "--binary-path", suggested_import_arg, "--json"]
    headless_command = [
        str(wrapper),
        str(project_dir),
        project_name,
        "-import",
        suggested_import_arg,
        "-analysisTimeoutPerFile",
        "300",
    ]
    blockers: list[str] = []
    if not wrapper.is_file():
        blockers.append("ghidra-headless-wrapper-missing")
    if binary_path is not None and not binary_path.is_file():
        blockers.append("offline-binary-path-missing")
    return {
        "key": "ghidra-static-pointer-chain-plan",
        "priority": "default-offline-static-first-for-pointer-chain-discovery",
        "status": "ready" if not blockers else "blocked-safe",
        "blockers": blockers,
        "wrapper": str(wrapper),
        "outputRoot": repo_rel(repo_root, output_root),
        "projectDirectory": repo_rel(repo_root, project_dir),
        "projectName": project_name,
        "targetBinary": str(binary_path) if binary_path else None,
        "suggestedTargetBinary": str(suggested_binary) if suggested_binary else None,
        "defaultBinaryCandidates": default_binary_candidates,
        "commandTemplate": command,
        "planCommand": plan_command,
        "suggestedRunCommand": suggested_command,
        "headlessCommandTemplate": headless_command,
        "doesRun": False,
        "recommendedTriggers": list(GHIDRA_RECOMMENDED_TRIGGERS),
        "targetOffsets": list(GHIDRA_TARGET_OFFSETS),
        "capabilities": list(GHIDRA_CAPABILITIES),
        "whyUseMoreOften": list(GHIDRA_WHY_USE_MORE_OFTEN),
        "safety": {
            **safety_flags(),
            "offlineOnly": True,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "next": [
            "choose an offline RIFT binary or dump artifact explicitly",
            "run the generated helper command only against offline files",
            "review xrefs/writers/types around rift_x64+0x32EBC80 and owner offsets 0x300/0x304/0x30C/0x438 before another live stimulus lane",
            "use decompiler/control-flow/data-flow output to label persistent fields versus transient derived state",
            "write Ghidra outputs under ignored scripts/captures/ghidra-static-analysis-* and project-* folders",
            "feed candidate pointer-chain evidence back into current-truth only through proof gates",
        ],
    }


def build_sysinternals_plan(external_tools_root: Path) -> dict[str, Any]:
    suite = external_tools_root / "SysinternalsSuite"
    listdlls = suite / "Listdlls64.exe"
    handle = suite / "handle64.exe"
    procdump = suite / "procdump64.exe"
    return {
        "key": "sysinternals-read-only-process-inspection-plan",
        "status": "ready" if listdlls.is_file() and handle.is_file() else "blocked-safe",
        "safeReadOnlyCommands": [[str(listdlls), "-accepteula", "rift_x64.exe"], [str(handle), "-accepteula", "-p", "<rift_x64-pid>"]],
        "gatedCommands": [
            {
                "command": [str(procdump), "-accepteula", "-ma", "<rift_x64-pid>", "<output.dmp>"],
                "requiresExplicitApproval": True,
                "why": "dump creation writes a large artifact and can perturb the target process",
            }
        ],
        "doesRun": False,
        "safety": safety_flags(),
    }


def build_input_surface_policy() -> dict[str, Any]:
    return {
        "sourceOfTruthCommand": ["scripts\\riftreader-live-input-surface-audit.cmd", "--json"],
        "defaultClassificationRules": [
            {
                "class": "critical-forbidden",
                "examples": ["x64dbg stimulus capture", "debugger plus allow-game-input"],
                "policy": "requires explicit current debugger and live-input approval",
            },
            {
                "class": "guarded-live-input",
                "examples": [
                    "static-owner route step",
                    "turn-forward experiment",
                    "camera/yaw classification",
                    "C# SendInput primitive",
                ],
                "policy": "requires exact target, fresh readback, and explicit movement/turn approval",
            },
            {
                "class": "legacy-review-required",
                "examples": ["PostMessage helpers", "older PowerShell send-key helpers"],
                "policy": "do not use autonomously until promoted to guarded or retired",
            },
            {
                "class": "read-only-safe",
                "examples": ["live input surface audit", "decision packet", "workflow status"],
                "policy": "safe in autonomous continuation mode",
            },
        ],
        "reviewReductionGoal": "move every review-required surface to guarded-live-input, legacy-retired, or forbidden",
    }


def build_recommended_workflow() -> list[dict[str, str]]:
    return [
        {"step": "decision-packet", "command": "scripts\\riftreader-decision-packet.cmd --compact-json --write"},
        {"step": "tool-catalog", "command": "scripts\\riftreader-tool-catalog.cmd --compact-json"},
        {"step": "offline-static-first", "command": "scripts\\riftreader-tool-catalog.cmd --ghidra-static-plan --json"},
        {"step": "ghidra-static-evidence-plan", "command": "scripts\\riftreader-ghidra-static-evidence.cmd --plan --json"},
        {"step": "static-field-access-matrix-quick", "command": "scripts\\riftreader-static-field-access-matrix.cmd --json"},
        {
            "step": "phase1-target-entity-snapshot",
            "command": "scripts\\riftreader-phase1-target-entity-snapshot.cmd --pid <current-pid> --hwnd <current-hwnd> --json",
        },
        {"step": "workflow-status", "command": "scripts\\riftreader-workflow-status.cmd --compact-json"},
        {"step": "navigation-pointer-discovery", "command": "scripts\\riftreader-navigation-pointer-discovery.cmd --json --write"},
        {"step": "current-truth-refresh-plan", "command": "scripts\\riftreader-current-truth-refresh-plan.cmd --json --write"},
        {"step": "current-truth-refresh-apply-dry-run", "command": "scripts\\riftreader-current-truth-refresh-apply.cmd --json"},
        {"step": "validation-ledger-smoke", "command": "scripts\\riftreader-validation-ledger.cmd --tier smoke"},
        {"step": "actor-chain-status-separate", "command": "scripts\\riftreader-actor-chain-no-debug-status.cmd --json"},
        {"step": "facing-three-pose-gate-report", "command": "scripts\\riftreader-facing-target-three-pose-gate.cmd --json"},
        {
            "step": "facing-restart-survival-report",
            "command": "scripts\\riftreader-facing-target-restart-survival-packet.cmd --json",
        },
        {
            "step": "facing-promotion-readiness-review",
            "command": "scripts\\riftreader-facing-target-promotion-readiness-review.cmd --json",
        },
        {
            "step": "facing-promotion-apply-dry-run",
            "command": "scripts\\riftreader-facing-target-promotion-apply.cmd --json",
        },
        {
            "step": "turn-rate-promotion-readiness-review",
            "command": "scripts\\riftreader-turn-rate-promotion-readiness-review.cmd --json",
        },
        {
            "step": "owner-0x304-semantics-review",
            "command": "scripts\\riftreader-owner-0x304-semantics-review.cmd --json",
        },
        {
            "step": "turn-rate-promotion-apply-dry-run",
            "command": "scripts\\riftreader-turn-rate-promotion-apply.cmd --json",
        },
        {
            "step": "static-chain-readback-before-nav",
            "command": "scripts\\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json",
        },
        {
            "step": "navigation-consumer-state",
            "command": "scripts\\riftreader-navigation-consumer-state.cmd --json --write",
        },
        {"step": "live-input-audit-before-live", "command": "scripts\\riftreader-live-input-surface-audit.cmd --json"},
        {"step": "turn-plan-before-input", "command": "scripts\\static-owner-turn-aware-route-plan.cmd --json"},
        {
            "step": "camera-yaw-classification-before-turn-route",
            "command": "scripts\\static-owner-camera-yaw-classification.cmd --stimulus-approved --json",
        },
        {"step": "single-gated-turn-forward", "command": "scripts\\static-owner-turn-forward-experiment.cmd --json"},
        {
            "step": "route-run-report-before-rerun",
            "command": "scripts\\static-owner-nav-report-route-run.cmd <route-run-summary.json> --json",
        },
        {
            "step": "route-sequence-contract-for-consumer",
            "command": "scripts\\static-owner-continuous-route-sequence-contract.cmd <sequence-summary.json> --json",
        },
        {
            "step": "waypoint-readiness-for-consumer",
            "command": "scripts\\riftreader-navigation-waypoint-readiness.cmd --waypoint-sequence-json <waypoints.json> --json",
        },
        {
            "step": "navigation-schema-validate-for-consumer",
            "command": "scripts\\riftreader-navigation-schema-validate.cmd --input <summary.json> --json",
        },
        {
            "step": "navigation-consumer-demo-for-downstream",
            "command": "scripts\\riftreader-navigation-consumer-demo.cmd --waypoint-readiness-json <readiness-summary.json> --json",
        },
        {
            "step": "navigation-consumer-refresh-for-downstream",
            "command": "scripts\\riftreader-navigation-consumer-refresh.cmd --waypoint-readiness-json <readiness-summary.json> --json",
        },
        {
            "step": "navigation-route-preview-for-downstream",
            "command": "scripts\\riftreader-navigation-route-preview.cmd --waypoint-readiness-json <readiness-summary.json> --json",
        },
        {"step": "route-run-after-fixtures", "command": "scripts\\static-owner-nav-route-run.cmd --json"},
    ]


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build_tool_catalog(repo_root: Path, external_tools_root: Path = DEFAULT_EXTERNAL_TOOLS_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    external_tools_root = external_tools_root.resolve()
    entries = build_repo_entries(repo_root) + build_external_entries(external_tools_root)
    entries = sorted(entries, key=lambda entry: (RISK_SORT.get(entry.risk, 99), entry.kind, entry.key))
    missing = [entry.key for entry in entries if not entry.exists]
    gated = [entry.key for entry in entries if entry.requiresExplicitApproval]
    blockers: list[str] = []
    warnings: list[str] = []
    if not external_tools_root.exists():
        warnings.append("external-tools-root-missing")
    if "ghidra-headless" in missing:
        warnings.append("ghidra-headless-unavailable-offline-static-lane-blocked")
    if "tool-catalog" in missing:
        blockers.append("tool-catalog-launcher-missing")
    ghidra_lane = build_ghidra_static_lane(repo_root, external_tools_root)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-tool-catalog",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else ("passed-with-warnings" if warnings else "passed"),
        "repoRoot": str(repo_root),
        "externalToolsRoot": str(external_tools_root),
        "inventory": build_inventory(repo_root, external_tools_root),
        "counts": {
            "total": len(entries),
            "exists": len([entry for entry in entries if entry.exists]),
            "missing": len(missing),
            "requiresExplicitApproval": len(gated),
            "byRisk": count_by(entries, "risk"),
            "byKind": count_by(entries, "kind"),
        },
        "entries": [entry.as_dict(repo_root if path_is_relative_to(entry.path, repo_root) else None) for entry in entries],
        "canonicalToolKeys": [
            "decision-packet",
            "workflow-status",
            "tool-catalog",
            "policy-lint",
            "validation-ledger",
            "navigation-pointer-discovery",
            "current-truth-refresh-plan",
            "current-truth-refresh-apply",
            "facing-target-three-pose-gate",
            "facing-target-restart-survival-packet",
            "facing-target-promotion-readiness-review",
            "facing-target-promotion-apply",
            "turn-rate-promotion-readiness-review",
            "owner-0x304-semantics-review",
            "turn-rate-promotion-apply",
            "live-input-surface-audit",
            "ghidra-headless",
            "ghidra-static-evidence",
            "static-field-access-matrix",
            "phase1-target-entity-snapshot",
            "actor-chain-no-debug-status",
            "static-owner-coordinate-chain-readback",
            "navigation-consumer-state",
            "static-owner-turn-aware-plan",
            "static-owner-camera-yaw-classification",
            "static-owner-route-run-report",
            "static-owner-route-sequence-contract",
            "navigation-waypoint-readiness",
            "navigation-schema-validate",
            "navigation-consumer-demo",
            "navigation-consumer-refresh",
            "navigation-route-preview",
            "static-owner-turn-forward-experiment",
        ],
        "gatedToolKeys": gated,
        "retiredToolKeys": [entry.key for entry in entries if entry.risk == "retired"],
        "lanes": {
            "ghidraStatic": ghidra_lane,
            "sysinternalsProcessInspection": build_sysinternals_plan(external_tools_root),
            "inputSurfacePolicy": build_input_surface_policy(),
        },
        "recommendedWorkflow": build_recommended_workflow(),
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            **safety_flags(),
            "readOnlyToolCatalog": True,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "artifacts": {},
    }


def build_compact_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    lanes = catalog.get("lanes") if isinstance(catalog.get("lanes"), dict) else {}
    ghidra_lane = lanes.get("ghidraStatic") if isinstance(lanes.get("ghidraStatic"), dict) else {}
    input_policy = lanes.get("inputSurfacePolicy") if isinstance(lanes.get("inputSurfacePolicy"), dict) else {}
    return {
        "schemaVersion": catalog.get("schemaVersion"),
        "kind": "riftreader-tool-catalog-compact",
        "toolVersion": catalog.get("toolVersion"),
        "generatedAtUtc": catalog.get("generatedAtUtc"),
        "status": catalog.get("status"),
        "externalToolsRoot": catalog.get("externalToolsRoot"),
        "counts": catalog.get("counts"),
        "canonicalToolKeys": catalog.get("canonicalToolKeys"),
        "gatedToolKeys": catalog.get("gatedToolKeys"),
        "retiredToolKeys": catalog.get("retiredToolKeys"),
        "ghidraStaticLane": {
            "status": ghidra_lane.get("status"),
            "wrapper": ghidra_lane.get("wrapper"),
            "commandTemplate": ghidra_lane.get("commandTemplate"),
            "planCommand": ghidra_lane.get("planCommand"),
            "suggestedRunCommand": ghidra_lane.get("suggestedRunCommand"),
            "headlessCommandTemplate": ghidra_lane.get("headlessCommandTemplate"),
            "defaultBinaryCandidates": ghidra_lane.get("defaultBinaryCandidates"),
            "recommendedTriggers": ghidra_lane.get("recommendedTriggers"),
            "targetOffsets": ghidra_lane.get("targetOffsets"),
            "capabilities": ghidra_lane.get("capabilities"),
            "priority": ghidra_lane.get("priority"),
            "doesRun": False,
        },
        "inputSurfacePolicyCommand": input_policy.get("sourceOfTruthCommand"),
        "recommendedWorkflow": catalog.get("recommendedWorkflow"),
        "blockers": catalog.get("blockers"),
        "warnings": catalog.get("warnings"),
        "safety": catalog.get("safety"),
    }


def build_decision_packet_tool_catalog(repo_root: Path) -> dict[str, Any]:
    """Return a bounded catalog summary suitable for embedding in decision packets."""

    try:
        compact = build_compact_catalog(build_tool_catalog(repo_root))
        ghidra_lane = compact.get("ghidraStaticLane") if isinstance(compact.get("ghidraStaticLane"), dict) else {}
        recommended_command = [".\\scripts\\riftreader-ghidra-static-evidence.cmd", "--plan", "--json"]
        recommended_run_command = [".\\scripts\\riftreader-ghidra-static-evidence.cmd", "--run", "--json"]
        for item in ghidra_lane.get("defaultBinaryCandidates") or []:
            if isinstance(item, dict) and item.get("exists") and item.get("path"):
                recommended_run_command = [
                    ".\\scripts\\riftreader-ghidra-static-evidence.cmd",
                    "--run",
                    "--binary-path",
                    str(item["path"]),
                    "--json",
                ]
                break
        return {
            "status": compact.get("status"),
            "toolVersion": compact.get("toolVersion"),
            "externalToolsRoot": compact.get("externalToolsRoot"),
            "counts": compact.get("counts"),
            "canonicalToolKeys": compact.get("canonicalToolKeys"),
            "gatedToolKeys": compact.get("gatedToolKeys"),
            "ghidraStaticLane": compact.get("ghidraStaticLane"),
            "recommendedGhidraAction": {
                "key": "ghidra-static-plan",
                "command": recommended_command,
                "why": (
                    "Plan an offline Ghidra static pass before new pointer-chain discovery/promotion, "
                    "restart-survival failure analysis, or debugger/live-stimulus escalation."
                ),
                "doesRun": False,
                "safety": {
                    **safety_flags(),
                    "offlineOnly": True,
                    "x64dbgAttach": False,
                    "targetMemoryBytesRead": False,
                    "targetMemoryBytesWritten": False,
                },
            },
            "recommendedGhidraEvidenceRun": {
                "key": "ghidra-static-evidence-run",
                "command": recommended_run_command,
                "why": "Run the actual offline Ghidra import/xref/writer evidence extractor; writes ignored scripts/captures artifacts only.",
                "doesRun": True,
                "safety": {
                    **safety_flags(),
                    "offlineOnly": True,
                    "x64dbgAttach": False,
                    "targetMemoryBytesRead": False,
                    "targetMemoryBytesWritten": False,
                },
            },
            "safeRefreshCommand": [".\\scripts\\riftreader-tool-catalog.cmd", "--compact-json"],
            "warnings": compact.get("warnings") or [],
            "blockers": compact.get("blockers") or [],
            "safety": compact.get("safety"),
        }
    except Exception as exc:  # noqa: BLE001 - decision packet must remain usable.
        return {
            "status": "failed",
            "toolVersion": TOOL_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
            "safeRefreshCommand": [".\\scripts\\riftreader-tool-catalog.cmd", "--compact-json"],
            "warnings": ["tool-catalog-build-failed"],
            "blockers": [],
            "safety": safety_flags(),
        }


def write_outputs(repo_root: Path, payload: dict[str, Any], output_root: Path) -> dict[str, str]:
    base = output_root if output_root.is_absolute() else repo_root / output_root
    output_dir = timestamped_output_dir(base)
    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"
    artifacts = {
        "runDirectory": repo_rel(repo_root, output_dir) or str(output_dir),
        "summaryJson": repo_rel(repo_root, json_path) or str(json_path),
        "summaryMarkdown": repo_rel(repo_root, md_path) or str(md_path),
    }
    payload["artifacts"] = artifacts
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    return artifacts


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return lines


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RiftReader Tool Catalog",
        "",
        f"Generated UTC: {payload.get('generatedAtUtc')}",
        f"Status: {payload.get('status')}",
        f"External tools root: `{payload.get('externalToolsRoot', '')}`",
        "",
        "## Counts",
        "",
        "```json",
        json.dumps(payload.get("counts", {}), indent=2, sort_keys=True),
        "```",
        "",
    ]
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    if entries:
        rows = [
            {
                "key": item.get("key"),
                "risk": item.get("risk"),
                "exists": item.get("exists"),
                "approval": item.get("requiresExplicitApproval"),
                "defaultUse": item.get("defaultUse"),
            }
            for item in entries[:40]
            if isinstance(item, dict)
        ]
        lines.extend(["## Catalog entries", ""])
        lines.extend(markdown_table(rows, ["key", "risk", "exists", "approval", "defaultUse"]))
        lines.append("")
    lanes = payload.get("lanes") if isinstance(payload.get("lanes"), dict) else {}
    ghidra_lane = lanes.get("ghidraStatic") if isinstance(lanes.get("ghidraStatic"), dict) else {}
    if ghidra_lane:
        lines.extend(
            [
                "## Ghidra offline static lane",
                "",
                f"- Status: `{ghidra_lane.get('status')}`",
                f"- Priority: `{ghidra_lane.get('priority')}`",
                f"- Suggested command: `{' '.join(str(part) for part in ghidra_lane.get('suggestedRunCommand') or [])}`",
                f"- Capabilities: `{', '.join(str(item) for item in ghidra_lane.get('capabilities') or [])}`",
                f"- Triggers: `{', '.join(str(item) for item in ghidra_lane.get('recommendedTriggers') or [])}`",
                f"- Target offsets: `{', '.join(str(item) for item in ghidra_lane.get('targetOffsets') or [])}`",
                "- Safety: offline files only; no live input, target memory read/write, x64dbg, CE, provider write, or promotion.",
                "",
            ]
        )
    if payload.get("recommendedWorkflow"):
        lines.extend(["## Recommended workflow", ""])
        lines.extend(markdown_table(payload["recommendedWorkflow"], ["step", "command"]))
        lines.append("")
    lines.extend(["## Safety", "", "```json", json.dumps(payload.get("safety", {}), indent=2, sort_keys=True), "```", ""])
    lines.append("# END_OF_RIFTREADER_TOOL_CATALOG")
    return "\n".join(lines) + "\n"


def build_self_test() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="riftreader-tool-catalog-selftest-") as temp_name:
        root = Path(temp_name)
        repo = root / "repo"
        external = root / "Tools"
        repo.mkdir()
        (repo / "agents.md").write_text("# test\n", encoding="utf-8")
        for rel in [
            "scripts/riftreader-decision-packet.cmd",
            "scripts/riftreader-workflow-status.cmd",
            "scripts/riftreader-tool-catalog.cmd",
            "scripts/riftreader-ghidra-static-evidence.cmd",
            "scripts/riftreader-static-field-access-matrix.cmd",
            "scripts/riftreader-phase1-target-entity-snapshot.cmd",
            "scripts/riftreader-policy-lint.cmd",
            "scripts/riftreader-validation-ledger.cmd",
            "scripts/riftreader-navigation-pointer-discovery.cmd",
            "scripts/riftreader-current-truth-refresh-plan.cmd",
            "scripts/riftreader-current-truth-refresh-apply.cmd",
            "scripts/riftreader-facing-target-three-pose-gate.cmd",
            "scripts/riftreader-facing-target-restart-survival-packet.cmd",
            "scripts/riftreader-facing-target-promotion-readiness-review.cmd",
            "scripts/riftreader-facing-target-promotion-apply.cmd",
            "scripts/riftreader-sensitive-artifact-scan.cmd",
            "scripts/riftreader-live-input-surface-audit.cmd",
            "scripts/riftreader-actor-chain-no-debug-status.cmd",
            "scripts/static-owner-coordinate-chain-readback.cmd",
            "scripts/riftreader-navigation-consumer-state.cmd",
            "scripts/static-owner-nav-now.cmd",
            "scripts/static-owner-turn-aware-route-plan.cmd",
            "scripts/static-owner-camera-yaw-classification.cmd",
            "scripts/static-owner-turn-forward-experiment.cmd",
            "scripts/static-owner-nav-route-step.cmd",
            "scripts/static-owner-nav-route-run.cmd",
            "scripts/static-owner-nav-report-route-run.cmd",
            "scripts/static-owner-continuous-route-sequence-contract.cmd",
            "scripts/riftreader-navigation-waypoint-readiness.cmd",
            "scripts/riftreader-navigation-schema-validate.cmd",
            "scripts/riftreader-navigation-consumer-demo.cmd",
            "scripts/riftreader-navigation-consumer-refresh.cmd",
            "scripts/riftreader-navigation-route-preview.cmd",
            "scripts/riftscan_milestone_review.py",
            "tools/riftreader_workflow/opencode_bridge.py",
            "tools/riftreader_workflow/ghidra_scripts/RiftReaderPointerEvidence.java",
            "tools/RiftReader.SendInput/Program.cs",
            "tools/RiftReader.WindowTools/Program.cs",
        ]:
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# test\n", encoding="utf-8")
        for rel in [
            "ghidra-headless.bat",
            "ghidra_12.1_PUBLIC/ghidraRun.bat",
            "x64dbg/release/x64/x64dbg.exe",
            "x64dbg/release/x64/headless.exe",
            "SysinternalsSuite/Listdlls64.exe",
            "SysinternalsSuite/handle64.exe",
            "SysinternalsSuite/procdump64.exe",
            "SysinternalsSuite/vmmap64.exe",
        ]:
            path = external / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test\n", encoding="utf-8")
        catalog = build_tool_catalog(repo, external)
        compact = build_compact_catalog(catalog)
        checks.extend(
            [
                {"name": "catalog-passes", "pass": catalog["status"] == "passed"},
                {"name": "ghidra-lane-ready", "pass": catalog["lanes"]["ghidraStatic"]["status"] == "ready"},
                {"name": "ghidra-static-evidence-canonical", "pass": "ghidra-static-evidence" in compact["canonicalToolKeys"]},
                {
                    "name": "static-field-access-matrix-canonical",
                    "pass": "static-field-access-matrix" in compact["canonicalToolKeys"],
                },
                {
                    "name": "phase1-target-entity-snapshot-canonical",
                    "pass": "phase1-target-entity-snapshot" in compact["canonicalToolKeys"],
                },
                {"name": "current-truth-apply-gated", "pass": "current-truth-refresh-apply" in catalog["gatedToolKeys"]},
                {"name": "facing-three-pose-canonical", "pass": "facing-target-three-pose-gate" in compact["canonicalToolKeys"]},
                {
                    "name": "facing-promotion-review-canonical",
                    "pass": "facing-target-promotion-readiness-review" in compact["canonicalToolKeys"],
                },
                {
                    "name": "facing-promotion-apply-gated",
                    "pass": "facing-target-promotion-apply" in catalog["gatedToolKeys"],
                },
                {"name": "x64dbg-gated", "pass": "x64dbg-gui" in catalog["gatedToolKeys"]},
                {"name": "tool-catalog-canonical", "pass": "tool-catalog" in compact["canonicalToolKeys"]},
                {
                    "name": "navigation-consumer-state-canonical",
                    "pass": "navigation-consumer-state" in compact["canonicalToolKeys"],
                },
                {
                    "name": "navigation-schema-validate-canonical",
                    "pass": "navigation-schema-validate" in compact["canonicalToolKeys"],
                },
                {
                    "name": "navigation-consumer-demo-canonical",
                    "pass": "navigation-consumer-demo" in compact["canonicalToolKeys"],
                },
                {
                    "name": "navigation-consumer-refresh-canonical",
                    "pass": "navigation-consumer-refresh" in compact["canonicalToolKeys"],
                },
                {
                    "name": "navigation-route-preview-canonical",
                    "pass": "navigation-route-preview" in compact["canonicalToolKeys"],
                },
                {"name": "safety-no-input", "pass": catalog["safety"]["inputSent"] is False},
            ]
        )
    ok = all(item["pass"] for item in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-tool-catalog-self-test",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "ok": ok,
        "status": "passed" if ok else "failed",
        "checks": checks,
        "safety": safety_flags(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--external-tools-root", type=Path, default=DEFAULT_EXTERNAL_TOOLS_ROOT)
    parser.add_argument("--json", action="store_true", help="Print full JSON catalog.")
    parser.add_argument("--compact-json", action="store_true", help="Print compact JSON catalog.")
    parser.add_argument("--write", action="store_true", help="Write ignored summary artifacts under .riftreader-local.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--ghidra-static-plan", action="store_true", help="Print only the offline Ghidra plan; does not run Ghidra.")
    parser.add_argument("--binary-path", type=Path, help="Optional offline binary path to include in the Ghidra plan.")
    parser.add_argument("--sysinternals-plan", action="store_true", help="Print only the Sysinternals process-inspection plan.")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic self-test.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            result = build_self_test()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("ok") else 1
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
        external_root = args.external_tools_root.resolve()
        if args.ghidra_static_plan:
            payload = build_ghidra_static_lane(repo_root, external_root, binary_path=args.binary_path)
            payload.update({"schemaVersion": SCHEMA_VERSION, "kind": "riftreader-ghidra-static-plan", "toolVersion": TOOL_VERSION})
        elif args.sysinternals_plan:
            payload = build_sysinternals_plan(external_root)
            payload.update({"schemaVersion": SCHEMA_VERSION, "kind": "riftreader-sysinternals-plan", "toolVersion": TOOL_VERSION})
        else:
            payload = build_tool_catalog(repo_root, external_root)
            if args.compact_json:
                payload = build_compact_catalog(payload)
        payload.setdefault("generatedAtUtc", utc_iso())
        if args.write:
            write_outputs(repo_root, payload, args.output_root)
        if args.json or args.compact_json or args.ghidra_static_plan or args.sysinternals_plan:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(build_markdown(payload), end="")
        return 0 if not payload.get("blockers") else 2
    except ToolCatalogError as exc:
        print(json.dumps({"status": "failed", "error": str(exc), "safety": safety_flags()}, indent=2, sort_keys=True))
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI must emit structured failure for operators.
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}", "safety": safety_flags()}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    raise SystemExit(main())
