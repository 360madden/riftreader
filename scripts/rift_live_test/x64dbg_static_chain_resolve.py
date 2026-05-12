from __future__ import annotations

import argparse
import json
import struct
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_access_event_ingest import normalize_hex, number_value, parse_int_value, string_value
from .x64dbg_snapshot_diff import BLOCKED_OPERATIONS, SOURCE_LINKS, int_hex


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_FIELD_OFFSETS = {"x": "0x0", "y": "0x4", "z": "0x8"}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def add_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def parse_offset_list(value: Any) -> list[int] | None:
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    offsets: list[int] = []
    for item in value:
        parsed = parse_int_value(item)
        if parsed is None:
            return None
        offsets.append(parsed)
    return offsets


def make_safety() -> dict[str, Any]:
    return {
        "offlineOnly": True,
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "githubConnectorWrites": False,
        "providerWrites": False,
        "codexMcpConfigured": False,
        "codexMcpServerStarted": False,
        "x64dbgLiveAttachStarted": False,
        "x64dbgCommandsExecuted": False,
        "processAttachOrMemoryReadStarted": False,
        "nativeLiveMemoryReadStarted": False,
        "movementAllowed": False,
        "candidateOnly": True,
        "writeClassOperationsBlocked": True,
        "blockedOperations": list(BLOCKED_OPERATIONS),
    }


def default_artifacts(run_dir: Path) -> dict[str, str | None]:
    return {
        "runDirectory": str(run_dir),
        "summaryJson": str(run_dir / "summary.json"),
        "summaryMarkdown": str(run_dir / "summary.md"),
        "resolvedChainJson": str(run_dir / "resolved-chain.json"),
    }


def build_summary_base(
    *,
    repo_root: Path,
    run_dir: Path,
    candidate_json: Path | None,
    module_map_json: Path | None,
    memory_image_json: Path | None,
    status: str,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "x64dbg-static-chain-resolve",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "inputs": {
            "candidateJson": str(candidate_json) if candidate_json else None,
            "moduleMapJson": str(module_map_json) if module_map_json else None,
            "memoryImageJson": str(memory_image_json) if memory_image_json else None,
        },
        "blockers": blockers or [],
        "warnings": warnings or [],
        "errors": errors or [],
        "sources": list(SOURCE_LINKS),
        "artifacts": default_artifacts(run_dir),
        "safety": make_safety(),
        "next": {
            "recommendedAction": "Provide a real x64dbg-derived module/RVA/static-owner chain and rerun the resolver.",
        },
    }


def load_json_object(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def normalize_process(candidate: Mapping[str, Any]) -> dict[str, Any]:
    raw = candidate.get("process") if isinstance(candidate.get("process"), Mapping) else {}
    return {
        "name": string_value(raw.get("name")) or DEFAULT_PROCESS_NAME,
        "pid": parse_int_value(raw.get("pid")),
        "hwnd": normalize_hex(raw.get("hwnd")),
        "startTimeUtc": string_value(raw.get("startTimeUtc")),
    }


def normalize_truth(candidate: Mapping[str, Any]) -> dict[str, Any]:
    raw = candidate.get("truthSurface") if isinstance(candidate.get("truthSurface"), Mapping) else {}
    return {
        "kind": raw.get("kind"),
        "source": raw.get("source"),
        "sampledAtUtc": raw.get("sampledAtUtc"),
        "x": number_value(raw.get("x")),
        "y": number_value(raw.get("y")),
        "z": number_value(raw.get("z")),
    }


def normalize_derived_chain(candidate: Mapping[str, Any], blockers: list[str]) -> dict[str, Any]:
    raw = candidate.get("derivedChain") if isinstance(candidate.get("derivedChain"), Mapping) else {}
    if not raw:
        add_unique(blockers, "missing-derived-chain")
    module = string_value(raw.get("module"))
    root_rva = parse_int_value(raw.get("rootRva"))
    offsets = parse_offset_list(raw.get("offsets"))
    field_offsets_raw = raw.get("fieldOffsets") if isinstance(raw.get("fieldOffsets"), Mapping) else {}
    field_offsets = {
        "x": normalize_hex(field_offsets_raw.get("x")),
        "y": normalize_hex(field_offsets_raw.get("y")),
        "z": normalize_hex(field_offsets_raw.get("z")),
    }
    if not module:
        add_unique(blockers, "missing-derived-chain-module")
    if root_rva is None:
        add_unique(blockers, "missing-derived-chain-root-rva")
    if offsets is None:
        add_unique(blockers, "invalid-derived-chain-offsets")
        offsets = []
    if field_offsets != DEFAULT_FIELD_OFFSETS:
        add_unique(blockers, "unexpected-field-offsets")
    return {
        "rootKind": raw.get("rootKind") or "module-rva-pointer-chain",
        "module": module,
        "moduleBase": normalize_hex(raw.get("moduleBase")),
        "rootRva": int_hex(root_rva) if root_rva is not None else None,
        "rootRvaInt": root_rva,
        "offsets": [int_hex(offset) for offset in offsets],
        "offsetInts": offsets,
        "fieldOffsets": field_offsets,
        "chainExpression": raw.get("chainExpression"),
    }


def module_base_from_map(
    module_name: str | None,
    module_map: Mapping[str, Any] | None,
    module_base_arg: int | None,
    blockers: list[str],
) -> int | None:
    if module_base_arg is not None:
        return module_base_arg
    if not module_name:
        add_unique(blockers, "missing-module-name-for-base-resolution")
        return None
    if not module_map:
        add_unique(blockers, "missing-current-module-base")
        return None
    modules = module_map.get("modules")
    if isinstance(modules, list):
        for module in modules:
            if not isinstance(module, Mapping):
                continue
            name = string_value(module.get("name")) or string_value(module.get("moduleName"))
            if name and name.lower() == module_name.lower():
                parsed = parse_int_value(module.get("baseAddress") or module.get("base") or module.get("moduleBase"))
                if parsed is not None:
                    return parsed
    direct = module_map.get(module_name)
    parsed_direct = parse_int_value(direct)
    if parsed_direct is not None:
        return parsed_direct
    add_unique(blockers, "current-module-base-not-found")
    return None


class OfflineMemoryImage:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.qwords = self._load_values(payload.get("qword") or payload.get("qwords"))
        self.floats = self._load_values(payload.get("float") or payload.get("floats"))
        self.bytes = self._load_bytes(payload.get("bytes"))

    @staticmethod
    def _load_values(raw: Any) -> dict[int, Any]:
        values: dict[int, Any] = {}
        if not isinstance(raw, Mapping):
            return values
        for key, value in raw.items():
            address = parse_int_value(key)
            if address is not None:
                values[address] = value
        return values

    @staticmethod
    def _load_bytes(raw: Any) -> dict[int, bytes]:
        values: dict[int, bytes] = {}
        if not isinstance(raw, Mapping):
            return values
        for key, value in raw.items():
            address = parse_int_value(key)
            if address is None or not isinstance(value, str):
                continue
            try:
                values[address] = bytes.fromhex(value.replace(" ", ""))
            except ValueError:
                continue
        return values

    def read_qword(self, address: int) -> int | None:
        value = self.qwords.get(address)
        parsed = parse_int_value(value)
        if parsed is not None:
            return parsed
        data = self.bytes.get(address)
        if data is not None and len(data) >= 8:
            return struct.unpack("<Q", data[:8])[0]
        return None

    def read_float(self, address: int) -> float | None:
        value = self.floats.get(address)
        parsed = number_value(value)
        if parsed is not None:
            return parsed
        data = self.bytes.get(address)
        if data is not None and len(data) >= 4:
            return float(struct.unpack("<f", data[:4])[0])
        return None


def resolve_pointer_chain(
    *,
    module_base: int,
    root_rva: int,
    offsets: list[int],
    memory_image: OfflineMemoryImage,
    blockers: list[str],
) -> tuple[int | None, list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    root_address = module_base + root_rva
    current = memory_image.read_qword(root_address)
    steps.append(
        {
            "kind": "root-deref",
            "address": int_hex(root_address),
            "value": int_hex(current) if current is not None else None,
        }
    )
    if current is None:
        add_unique(blockers, "root-pointer-read-failed")
        return None, steps
    if not offsets:
        return current, steps
    for index, offset in enumerate(offsets):
        target = current + offset
        if index == len(offsets) - 1:
            steps.append(
                {
                    "kind": "final-offset",
                    "base": int_hex(current),
                    "offset": int_hex(offset),
                    "address": int_hex(target),
                }
            )
            return target, steps
        next_value = memory_image.read_qword(target)
        steps.append(
            {
                "kind": "offset-deref",
                "base": int_hex(current),
                "offset": int_hex(offset),
                "address": int_hex(target),
                "value": int_hex(next_value) if next_value is not None else None,
            }
        )
        if next_value is None:
            add_unique(blockers, "pointer-chain-read-failed")
            return None, steps
        current = next_value
    return current, steps


def read_coord_triplet(
    *,
    coord_base: int,
    field_offsets: Mapping[str, str | None],
    memory_image: OfflineMemoryImage,
    blockers: list[str],
) -> dict[str, Any]:
    coords: dict[str, Any] = {
        "baseAddress": int_hex(coord_base),
        "axisOrder": "xyz",
    }
    for axis in ("x", "y", "z"):
        offset = parse_int_value(field_offsets.get(axis))
        if offset is None:
            add_unique(blockers, f"missing-{axis}-field-offset")
            coords[axis] = None
            continue
        address = coord_base + offset
        value = memory_image.read_float(address)
        if value is None:
            add_unique(blockers, f"{axis}-float-read-failed")
        coords[f"{axis}Address"] = int_hex(address)
        coords[axis] = value
    coords["sampledAtUtc"] = utc_iso()
    return coords


def coordinate_deltas(truth: Mapping[str, Any], memory: Mapping[str, Any]) -> dict[str, float | None]:
    deltas: dict[str, float | None] = {}
    for axis in ("x", "y", "z"):
        truth_value = number_value(truth.get(axis))
        memory_value = number_value(memory.get(axis))
        deltas[axis] = None if truth_value is None or memory_value is None else abs(memory_value - truth_value)
    values = [delta for delta in deltas.values() if delta is not None]
    deltas["maxAbs"] = max(values) if values else None
    return deltas


def build_resolved_chain(
    *,
    candidate: Mapping[str, Any],
    module_map: Mapping[str, Any] | None,
    memory_image: OfflineMemoryImage | None,
    module_base_arg: int | None,
    max_delta: float,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any] | None:
    process = normalize_process(candidate)
    truth = normalize_truth(candidate)
    derived = normalize_derived_chain(candidate, blockers)
    module_base = module_base_from_map(derived["module"], module_map, module_base_arg, blockers)
    if module_base is None or derived["rootRvaInt"] is None:
        return None
    root_address = module_base + int(derived["rootRvaInt"])
    resolved: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-static-chain-resolved-candidate",
        "generatedAtUtc": utc_iso(),
        "candidateId": candidate.get("candidateId"),
        "process": process,
        "truthSurface": truth,
        "derivedChain": {
            "rootKind": derived["rootKind"],
            "module": derived["module"],
            "currentModuleBase": int_hex(module_base),
            "capturedModuleBase": derived["moduleBase"],
            "rootRva": derived["rootRva"],
            "rootAddress": int_hex(root_address),
            "offsets": derived["offsets"],
            "fieldOffsets": derived["fieldOffsets"],
            "chainExpression": derived["chainExpression"],
            "resolverConvention": "coordBase = deref(moduleBase + rootRva); for each offset except the final offset, deref(current + offset); final offset is added to produce coordBase",
        },
        "readback": None,
        "validation": {
            "apiNowVsChainNow": False,
            "maxDelta": max_delta,
            "movementProofEligible": False,
        },
        "promotionBlockers": [
            "not-multi-pose-validated-in-this-resolver",
            "not-restart-validated",
            "proofonly-not-passed",
        ],
    }
    if memory_image is None:
        add_unique(blockers, "no-readback-source")
        add_unique(warnings, "resolved-address-only-no-memory-image-or-live-readback")
        return resolved
    coord_base, steps = resolve_pointer_chain(
        module_base=module_base,
        root_rva=int(derived["rootRvaInt"]),
        offsets=list(derived["offsetInts"]),
        memory_image=memory_image,
        blockers=blockers,
    )
    resolved["derivedChain"]["resolutionSteps"] = steps
    if coord_base is None:
        return resolved
    readback = read_coord_triplet(
        coord_base=coord_base,
        field_offsets=derived["fieldOffsets"],
        memory_image=memory_image,
        blockers=blockers,
    )
    deltas = coordinate_deltas(truth, readback)
    readback["deltas"] = deltas
    max_abs = deltas.get("maxAbs")
    if max_abs is None:
        add_unique(blockers, "api-now-vs-chain-now-delta-unavailable")
    elif max_abs > max_delta:
        add_unique(blockers, "api-now-vs-chain-now-delta-exceeded")
    else:
        resolved["validation"]["apiNowVsChainNow"] = True
    resolved["readback"] = readback
    return resolved


def markdown_summary(summary: dict[str, Any], resolved: dict[str, Any] | None = None) -> str:
    safety = summary["safety"]
    lines = [
        "# x64dbg static-chain resolver summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated UTC: `{summary['generatedAtUtc']}`",
        f"- Movement allowed: `{str(safety.get('movementAllowed')).lower()}`",
        f"- x64dbg live attach started: `{str(safety.get('x64dbgLiveAttachStarted')).lower()}`",
        f"- Native live memory read started: `{str(safety.get('nativeLiveMemoryReadStarted')).lower()}`",
    ]
    if resolved:
        chain = resolved["derivedChain"]
        lines.extend(
            [
                "",
                "## Resolved chain",
                "",
                f"- Candidate id: `{resolved.get('candidateId')}`",
                f"- Module: `{chain.get('module')}`",
                f"- Current module base: `{chain.get('currentModuleBase')}`",
                f"- Root RVA: `{chain.get('rootRva')}`",
                f"- Root address: `{chain.get('rootAddress')}`",
                f"- API-now vs chain-now: `{str(resolved.get('validation', {}).get('apiNowVsChainNow')).lower()}`",
                f"- Movement proof eligible: `{str(resolved.get('validation', {}).get('movementProofEligible')).lower()}`",
            ]
        )
        readback = resolved.get("readback")
        if isinstance(readback, Mapping):
            lines.append(
                f"- Chain coord: `X={readback.get('x')}`, `Y={readback.get('y')}`, `Z={readback.get('z')}`"
            )
    if summary["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    if summary["errors"]:
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{error}`" for error in summary["errors"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This helper resolves candidate chain shape without x64dbg or MCP. The",
            "current implementation performs offline memory-image readback only and",
            "keeps movement disabled. Live process readback must be added as a",
            "separate gated extension.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(summary: dict[str, Any], resolved: dict[str, Any] | None) -> None:
    artifacts = summary["artifacts"]
    run_dir = Path(str(artifacts["runDirectory"]))
    run_dir.mkdir(parents=True, exist_ok=True)
    if resolved:
        write_json(Path(str(artifacts["resolvedChainJson"])), resolved)
    else:
        artifacts["resolvedChainJson"] = None
    write_text_atomic(Path(str(artifacts["summaryMarkdown"])), markdown_summary(summary, resolved))
    write_json(Path(str(artifacts["summaryJson"])), summary)


def synthetic_candidate() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": "candidate",
        "tool": "x64dbg",
        "kind": "x64dbg-coordinate-chain-candidate",
        "candidateId": "x64dbg-static-chain-resolve-self-test",
        "process": {
            "name": "rift_x64",
            "pid": 63412,
            "hwnd": "0xB70082",
            "startTimeUtc": "2026-05-12T15:53:24Z",
        },
        "truthSurface": {
            "kind": "api-now",
            "source": "synthetic-api-now",
            "sampledAtUtc": "2026-05-12T22:55:00Z",
            "x": 7376.87,
            "y": 863.82,
            "z": 2990.35,
        },
        "derivedChain": {
            "rootKind": "module-rva-pointer-chain",
            "module": "rift_x64.exe",
            "moduleBase": "0x140000000",
            "rootRva": "0x1000",
            "offsets": ["0x20", "0x30"],
            "fieldOffsets": DEFAULT_FIELD_OFFSETS,
            "chainExpression": "deref(deref(rift_x64.exe+0x1000)+0x20)+0x30",
        },
    }


def synthetic_module_map() -> dict[str, Any]:
    return {
        "modules": [
            {
                "name": "rift_x64.exe",
                "baseAddress": "0x140000000",
            }
        ]
    }


def synthetic_memory_image() -> dict[str, Any]:
    return {
        "qword": {
            "0x140001000": "0x200000000",
            "0x200000020": "0x300000000",
        },
        "float": {
            "0x300000030": 7376.88,
            "0x300000034": 863.81,
            "0x300000038": 2990.35,
        },
    }


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-static-chain-resolve-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve an x64dbg-derived static coord chain candidate without x64dbg.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--candidate-json", type=Path, default=None)
    parser.add_argument("--module-map-json", type=Path, default=None)
    parser.add_argument("--memory-image-json", type=Path, default=None)
    parser.add_argument("--module-base", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--max-delta", type=float, default=1.0)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    candidate_json = args.candidate_json.resolve() if args.candidate_json else None
    module_map_json = args.module_map_json.resolve() if args.module_map_json else None
    memory_image_json = args.memory_image_json.resolve() if args.memory_image_json else None

    if args.dry_run:
        summary = build_summary_base(
            repo_root=repo_root,
            run_dir=run_dir,
            candidate_json=candidate_json,
            module_map_json=module_map_json,
            memory_image_json=memory_image_json,
            status="blocked",
            blockers=["dry-run-no-chain-resolved"],
            warnings=[],
            errors=[],
        )
        resolved = None
        result_code = 2
    else:
        try:
            candidate = synthetic_candidate() if args.self_test else load_json_object(candidate_json) if candidate_json else None
            if candidate is None:
                raise ValueError("--candidate-json is required unless --self-test or --dry-run is used")
            module_map = synthetic_module_map() if args.self_test else load_json_object(module_map_json) if module_map_json else None
            memory_payload = synthetic_memory_image() if args.self_test else load_json_object(memory_image_json) if memory_image_json else None
            memory_image = OfflineMemoryImage(memory_payload) if memory_payload is not None else None
            blockers: list[str] = []
            warnings: list[str] = []
            resolved = build_resolved_chain(
                candidate=candidate,
                module_map=module_map,
                memory_image=memory_image,
                module_base_arg=args.module_base,
                max_delta=args.max_delta,
                blockers=blockers,
                warnings=warnings,
            )
            status = "blocked" if blockers else "passed"
            summary = build_summary_base(
                repo_root=repo_root,
                run_dir=run_dir,
                candidate_json=candidate_json,
                module_map_json=module_map_json,
                memory_image_json=memory_image_json,
                status=status,
                blockers=blockers,
                warnings=warnings,
                errors=[],
            )
            summary["resolved"] = {
                "candidateId": resolved.get("candidateId") if resolved else None,
                "hasReadback": bool(resolved and resolved.get("readback")),
                "apiNowVsChainNow": bool(resolved and resolved.get("validation", {}).get("apiNowVsChainNow")),
                "movementProofEligible": False,
            }
            summary["next"]["recommendedAction"] = (
                "Use this resolved candidate only as proof-candidate scaffolding; add live readback, multi-pose, restart validation, and ProofOnly before promotion."
                if not blockers
                else "Fix the resolver blockers before using the static chain candidate for any proof-candidate work."
            )
            result_code = 2 if blockers else 0
        except Exception as exc:  # noqa: BLE001 - CLI must preserve failure details.
            summary = build_summary_base(
                repo_root=repo_root,
                run_dir=run_dir,
                candidate_json=candidate_json,
                module_map_json=module_map_json,
                memory_image_json=memory_image_json,
                status="failed",
                blockers=[],
                warnings=[],
                errors=[f"{type(exc).__name__}: {exc}"],
            )
            resolved = None
            result_code = 1

    write_outputs(summary, resolved)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "resolvedChainJson": summary["artifacts"].get("resolvedChainJson"),
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                    "errors": summary["errors"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"summaryMarkdown={summary['artifacts']['summaryMarkdown']}")
        resolved_path = summary["artifacts"].get("resolvedChainJson")
        if resolved_path:
            print(f"resolvedChainJson={resolved_path}")
        if summary["blockers"]:
            print("blockers=" + ";".join(summary["blockers"]))
        if summary["warnings"]:
            print("warnings=" + ";".join(summary["warnings"]))
        if summary["errors"]:
            print("errors=" + ";".join(summary["errors"]))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
