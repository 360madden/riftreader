from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


SUMMARY_NAME = "turn-key-profile-summary.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _read_nav_state(*, root: Path, current_truth_json: str, timeout_seconds: float = 30.0) -> dict[str, Any]:
    """Run the promoted static resolver with --nav-state as a read-only subprocess.

    Returns nav-state dict or empty dict on failure.
    """
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_coordinate_chain_readback.py"),
        "--repo-root", str(root),
        "--current-truth-json", current_truth_json,
        "--use-current-truth",
        "--nav-state",
        "--json",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        if result.stdout.strip():
            parsed = json.loads(result.stdout)
            if isinstance(parsed, dict):
                nav = safe_mapping(parsed.get("navState"))
                return {
                    "ok": parsed.get("status") not in ("unavailable", "readback-failed", "parse-error"),
                    "yawDegrees": nav.get("yawDegrees"),
                    "turnRate0x304": nav.get("turnRate0x304"),
                    "turnRateClassification": nav.get("turnRateClassification"),
                    "pitchDegrees": nav.get("pitchDegrees"),
                    "facingTargetCoordinate": nav.get("facingTargetCoordinate"),
                    "status": parsed.get("status"),
                    "error": None,
                }
        return {"ok": False, "error": "nav-state-parse-failed"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def relative(path_text: str | None, root: Path) -> str:
    if not path_text:
        return ""
    try:
        path = Path(path_text)
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path_text)


def summarize_attempts(summary: dict[str, Any]) -> dict[str, Any]:
    classifications: Counter[str] = Counter()
    deliveries: Counter[str] = Counter()
    yaw_deltas: list[float] = []
    coord_deltas: list[float] = []
    notable: list[str] = []

    for attempt in summary.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        classification = str(attempt.get("classification") or "unknown")
        classifications[classification] += 1

        input_command = attempt.get("inputCommand") or {}
        if isinstance(input_command, dict):
            delivery = input_command.get("inputDelivery") or {}
            if isinstance(delivery, dict):
                deliveries[str(delivery.get("effectiveMode") or "unknown")] += 1
            elif input_command.get("exitCode") is not None:
                deliveries["legacy-helper"] += 1

        yaw = attempt.get("yawDeltaDegrees")
        if isinstance(yaw, (int, float)):
            yaw_deltas.append(float(yaw))
        coord = attempt.get("coordDelta") or {}
        if isinstance(coord, dict) and isinstance(coord.get("planarDistance"), (int, float)):
            coord_deltas.append(float(coord["planarDistance"]))

        if classification != "no-turn" or input_command.get("exitCode") not in (None, 0):
            key = attempt.get("key")
            mode = attempt.get("inputMode")
            notable.append(f"{attempt.get('attemptId')} {key}/{mode}: {classification}, yaw={yaw}")

    return {
        "attemptCount": sum(classifications.values()),
        "classifications": dict(sorted(classifications.items())),
        "deliveries": dict(sorted(deliveries.items())),
        "maxAbsYawDeltaDegrees": max((abs(value) for value in yaw_deltas), default=0.0),
        "maxCoordPlanarDelta": max(coord_deltas, default=0.0),
        "notableAttempts": notable[:6],
    }


def _enrich_with_nav_state(row: dict[str, Any], nav_state: dict[str, Any]) -> dict[str, Any]:
    """Attach live pointer-chain nav-state data to a turn-key profile row."""
    if not nav_state or not nav_state.get("ok"):
        row["navStateAvailable"] = False
        row["navStateError"] = nav_state.get("error") if nav_state else "nav-state-not-requested"
        return row
    row["navStateAvailable"] = True
    row["navStateYawDegrees"] = nav_state.get("yawDegrees")
    row["navStateTurnRate0x304"] = nav_state.get("turnRate0x304")
    row["navStateTurnRateClassification"] = nav_state.get("turnRateClassification")
    row["navStatePitchDegrees"] = nav_state.get("pitchDegrees")
    row["navStateError"] = None
    return row


def summarize_file(path: Path, repo_root: Path) -> dict[str, Any]:
    summary = load_json(path)
    attempts = summarize_attempts(summary)
    return {
        "generatedAtUtc": summary.get("generatedAtUtc"),
        "status": summary.get("status"),
        "ok": summary.get("ok"),
        "processId": summary.get("processId"),
        "targetWindowHandle": summary.get("targetWindowHandle"),
        "keys": summary.get("keys") or [],
        "inputModes": summary.get("inputModes") or [],
        "holdMilliseconds": summary.get("holdMilliseconds"),
        "repeatCount": summary.get("repeats"),
        "inputSent": summary.get("inputSent"),
        "movementDetected": summary.get("movementDetected"),
        "promotedCandidateCount": len(summary.get("promotedCandidates") or []),
        "promotedCandidates": summary.get("promotedCandidates") or [],
        "issues": summary.get("issues") or [],
        "summaryFile": str(path),
        "summaryFileRelative": relative(str(path), repo_root),
        **attempts,
    }


def find_summaries(captures_root: Path) -> list[Path]:
    return sorted(captures_root.glob(f"turn-key-profile-currentpid-*/*{SUMMARY_NAME}"))


def format_counter(value: dict[str, Any]) -> str:
    if not value:
        return "-"
    return ", ".join(f"{key}:{count}" for key, count in sorted(value.items()))


def format_markdown(rows: list[dict[str, Any]], repo_root: Path) -> str:
    lines = [
        "# Turn key profile evidence",
        "",
        "_Generated from `scripts/summarize_turn_key_profiles.py`. This report is compact evidence only; individual run summaries remain authoritative._",
        "",
        "| Generated UTC | Run | Keys | Modes | Hold | Attempts | Classifications | Delivery | Max abs yaw | Max coord delta | Promoted | Issues |",
        "|---|---|---|---|---:|---:|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        issues = row.get("issues") or []
        issue_text = "-" if not issues else "<br>".join(f"`{issue}`" for issue in issues[:3])
        run = row.get("summaryFileRelative") or row.get("summaryFile")
        lines.append(
            "| {generated} | `{run}` | `{keys}` | `{modes}` | {hold} | {attempts} | `{classes}` | `{delivery}` | {yaw:.4f} | {coord:.4f} | {promoted} | {issues} |".format(
                generated=row.get("generatedAtUtc") or "",
                run=run,
                keys=",".join(str(key) for key in row.get("keys") or []),
                modes=",".join(str(mode) for mode in row.get("inputModes") or []),
                hold=row.get("holdMilliseconds") if row.get("holdMilliseconds") is not None else "",
                attempts=row.get("attemptCount") or 0,
                classes=format_counter(row.get("classifications") or {}),
                delivery=format_counter(row.get("deliveries") or {}),
                yaw=float(row.get("maxAbsYawDeltaDegrees") or 0.0),
                coord=float(row.get("maxCoordPlanarDelta") or 0.0),
                promoted=row.get("promotedCandidateCount") or 0,
                issues=issue_text,
            )
        )

    lines.extend(["", "## Notable attempts", ""])
    any_notable = False
    for row in rows:
        notable = row.get("notableAttempts") or []
        if not notable:
            continue
        any_notable = True
        lines.append(f"- `{row.get('summaryFileRelative')}`")
        for item in notable:
            lines.append(f"  - {item}")
    if not any_notable:
        lines.append("- None; all attempts were no-turn/no-movement or blocked before input.")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize turn-key profile run summaries.")
    parser.add_argument("--captures-root", type=Path, default=None, help="Captures root. Defaults to scripts/captures.")
    parser.add_argument("--output-json", type=Path, default=None, help="Optional compact JSON output path.")
    parser.add_argument("--output-markdown", type=Path, default=None, help="Optional Markdown output path.")
    parser.add_argument("--process-id", type=int, default=None, help="Only include a process id.")
    parser.add_argument("--limit", type=int, default=0, help="Keep only the newest N summaries after filtering.")
    parser.add_argument("--nav-state", action="store_true", help="Read live pointer-chain nav-state (yaw, turn rate) and embed alongside turn-key stimulus evidence")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = repo_root_from_script()
    captures_root = args.captures_root or (repo_root / "scripts" / "captures")
    if not captures_root.exists():
        raise SystemExit(f"captures root not found: {captures_root}")

    rows = [summarize_file(path, repo_root) for path in find_summaries(captures_root)]
    if args.process_id is not None:
        rows = [row for row in rows if row.get("processId") == args.process_id]
    rows.sort(key=lambda row: str(row.get("generatedAtUtc") or ""))
    if args.limit and args.limit > 0:
        rows = rows[-args.limit :]

    nav_state: dict[str, Any] = {}
    if args.nav_state:
        nav_state = _read_nav_state(
            root=repo_root,
            current_truth_json="docs/recovery/current-truth.json",
            timeout_seconds=30.0,
        )
        for row in rows:
            _enrich_with_nav_state(row, nav_state)

    payload = {"schemaVersion": 1, "summaryCount": len(rows), "summaries": rows}
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown = format_markdown(rows, repo_root)
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
