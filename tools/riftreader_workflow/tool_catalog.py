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
TOOL_VERSION = "riftreader-tool-catalog-v0.1.0"
DEFAULT_EXTERNAL_TOOLS_ROOT = Path(r"C:\RIFT MODDING\Tools")
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "tool-catalog"

RISK_SORT = {
    "safe-read-only": 0,
    "offline-static-analysis": 1,
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
            label="Ghidra headless analyzer wrapper",
            kind="offline-static-analysis",
            rel_path="ghidra-headless.bat",
            risk="offline-static-analysis",
            default_use="default offline static-analysis lane for pointer-chain research",
            allowed=True,
            approval=False,
            notes=["plan commands first; do not attach to live RIFT"],
        ),
        external_tool(
            external_root,
            key="ghidra-gui",
            label="Ghidra GUI launcher",
            kind="offline-static-analysis",
            rel_path="ghidra_12.1_PUBLIC/ghidraRun.bat",
            risk="offline-static-analysis",
            default_use="manual offline reverse-engineering review",
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


def build_ghidra_static_lane(repo_root: Path, external_tools_root: Path, *, binary_path: Path | None = None) -> dict[str, Any]:
    wrapper = external_tools_root / "ghidra-headless.bat"
    output_root = repo_root / DEFAULT_OUTPUT_ROOT / "ghidra-static"
    project_dir = output_root / "project"
    project_name = "riftreader-offline-static-analysis"
    import_arg = str(binary_path) if binary_path else "<offline-binary-path>"
    command = [str(wrapper), str(project_dir), project_name, "-import", import_arg, "-analysisTimeoutPerFile", "300"]
    blockers: list[str] = []
    if not wrapper.is_file():
        blockers.append("ghidra-headless-wrapper-missing")
    if binary_path is not None and not binary_path.is_file():
        blockers.append("offline-binary-path-missing")
    return {
        "key": "ghidra-static-pointer-chain-plan",
        "status": "ready" if not blockers else "blocked-safe",
        "blockers": blockers,
        "wrapper": str(wrapper),
        "outputRoot": repo_rel(repo_root, output_root),
        "projectDirectory": repo_rel(repo_root, project_dir),
        "projectName": project_name,
        "targetBinary": str(binary_path) if binary_path else None,
        "commandTemplate": command,
        "doesRun": False,
        "safety": {
            **safety_flags(),
            "offlineOnly": True,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "next": [
            "choose an offline RIFT binary or dump artifact explicitly",
            "run the generated headless command only against offline files",
            "write Ghidra outputs under .riftreader-local/tool-catalog/ghidra-static",
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
        {"step": "workflow-status", "command": "scripts\\riftreader-workflow-status.cmd --compact-json"},
        {"step": "navigation-pointer-discovery", "command": "scripts\\riftreader-navigation-pointer-discovery.cmd --json --write"},
        {"step": "current-truth-refresh-plan", "command": "scripts\\riftreader-current-truth-refresh-plan.cmd --json --write"},
        {"step": "validation-ledger-smoke", "command": "scripts\\riftreader-validation-ledger.cmd --tier smoke"},
        {"step": "offline-static-first", "command": "scripts\\riftreader-tool-catalog.cmd --ghidra-static-plan --json"},
        {"step": "actor-chain-status-separate", "command": "scripts\\riftreader-actor-chain-no-debug-status.cmd --json"},
        {
            "step": "static-chain-readback-before-nav",
            "command": "scripts\\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json",
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
            "live-input-surface-audit",
            "ghidra-headless",
            "actor-chain-no-debug-status",
            "static-owner-coordinate-chain-readback",
            "static-owner-turn-aware-plan",
            "static-owner-camera-yaw-classification",
            "static-owner-route-run-report",
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
        return {
            "status": compact.get("status"),
            "toolVersion": compact.get("toolVersion"),
            "externalToolsRoot": compact.get("externalToolsRoot"),
            "counts": compact.get("counts"),
            "canonicalToolKeys": compact.get("canonicalToolKeys"),
            "gatedToolKeys": compact.get("gatedToolKeys"),
            "ghidraStaticLane": compact.get("ghidraStaticLane"),
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
            "scripts/riftreader-policy-lint.cmd",
            "scripts/riftreader-sensitive-artifact-scan.cmd",
            "scripts/riftreader-live-input-surface-audit.cmd",
            "scripts/riftreader-actor-chain-no-debug-status.cmd",
            "scripts/static-owner-coordinate-chain-readback.cmd",
            "scripts/static-owner-nav-now.cmd",
            "scripts/static-owner-turn-aware-route-plan.cmd",
            "scripts/static-owner-camera-yaw-classification.cmd",
            "scripts/static-owner-turn-forward-experiment.cmd",
            "scripts/static-owner-nav-route-step.cmd",
            "scripts/static-owner-nav-route-run.cmd",
            "scripts/riftscan_milestone_review.py",
            "tools/riftreader_workflow/opencode_bridge.py",
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
                {"name": "x64dbg-gated", "pass": "x64dbg-gui" in catalog["gatedToolKeys"]},
                {"name": "tool-catalog-canonical", "pass": "tool-catalog" in compact["canonicalToolKeys"]},
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
