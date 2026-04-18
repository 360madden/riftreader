from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class RecoveryTruthStatus:
    area: str
    status: str


@dataclass(slots=True)
class RecoveryArtifactStatus:
    tier: str
    label: str
    path_text: str | None
    exists: bool
    updated_at: str | None


@dataclass(slots=True)
class RecoverySnapshot:
    repo_root: Path
    current_truth_path: Path
    runbook_path: Path
    artifact_tiers_path: Path
    current_truth_last_updated: str | None
    current_truth_last_updated_iso: str | None
    truth_statuses: list[RecoveryTruthStatus]
    artifact_statuses: list[RecoveryArtifactStatus]
    surviving_baselines_text: str
    broken_or_stale_text: str
    canonical_scripts_text: str
    runbook_text: str
    warnings: list[str]


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _find_heading_index(lines: list[str], heading: str) -> int:
    pattern = re.compile(r"^\s*#{1,6}\s+" + re.escape(heading) + r"\s*$")
    for index, line in enumerate(lines):
        if pattern.match(line):
            return index
    return -1


def _split_markdown_row(line: str) -> list[str]:
    trimmed = line.strip().strip("|")
    if not trimmed:
        return []
    return [part.strip() for part in trimmed.split("|")]


def _get_markdown_table_after_heading(lines: list[str], heading: str) -> list[dict[str, str]]:
    heading_index = _find_heading_index(lines, heading)
    if heading_index < 0:
        return []

    table_lines: list[str] = []
    for line in lines[heading_index + 1 :]:
        if re.match(r"^\s*\|", line):
            table_lines.append(line)
            continue
        if table_lines:
            break

    if len(table_lines) < 3:
        return []

    headers = _split_markdown_row(table_lines[0])
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = _split_markdown_row(line)
        if not cells:
            continue
        row: dict[str, str] = {}
        for index, header in enumerate(headers):
            row[header] = cells[index] if index < len(cells) else ""
        rows.append(row)

    return rows


def _extract_last_updated(text: str) -> str | None:
    match = re.search(r"_Last updated:\s*(.+?)_", text)
    if not match:
        return None
    return match.group(1).strip()


def _normalize_updated_iso(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s*\(.+?\)\s*$", "", value).strip()
    try:
        return datetime.strptime(cleaned, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _resolve_artifact_path(repo_root: Path, label: str) -> str | None:
    cleaned = label.strip().strip("`").rstrip(".")
    if not cleaned:
        return None

    if re.match(r"^[A-Za-z]:\\", cleaned) or cleaned.startswith("\\\\"):
        return cleaned

    if "." not in Path(cleaned).name:
        return None

    return str((repo_root / "scripts" / "captures" / cleaned).resolve())


def _load_artifact_statuses(repo_root: Path, artifact_tiers_path: Path) -> list[RecoveryArtifactStatus]:
    lines = _read_lines(artifact_tiers_path)
    statuses: list[RecoveryArtifactStatus] = []
    current_tier = "Uncategorized"

    for line in lines:
        heading_match = re.match(r"^\s*##\s+(Tier\s+\d+\s*-\s*.+?)\s*$", line)
        if heading_match:
            current_tier = heading_match.group(1).strip()
            continue

        bullet_match = re.match(r"^\s*-\s+(.+?)\s*$", line)
        if not bullet_match:
            continue

        label = bullet_match.group(1).strip()
        resolved_path = _resolve_artifact_path(repo_root, label)
        exists = False
        updated_at = None
        if resolved_path:
            candidate_path = Path(resolved_path)
            exists = candidate_path.exists()
            if exists:
                updated_at = datetime.fromtimestamp(candidate_path.stat().st_mtime).astimezone().isoformat()

        statuses.append(
            RecoveryArtifactStatus(
                tier=current_tier,
                label=label,
                path_text=resolved_path,
                exists=exists,
                updated_at=updated_at,
            )
        )

    return statuses


def _get_section_text(lines: list[str], heading: str) -> str:
    heading_index = _find_heading_index(lines, heading)
    if heading_index < 0:
        return ""

    base_line = lines[heading_index]
    base_level_match = re.match(r"^\s*(#{1,6})\s+", base_line)
    base_level = len(base_level_match.group(1)) if base_level_match else 2

    section_lines: list[str] = []
    for line in lines[heading_index + 1 :]:
        heading_match = re.match(r"^\s*(#{1,6})\s+", line)
        if heading_match and len(heading_match.group(1)) <= base_level:
            break
        section_lines.append(line.rstrip())

    return "\n".join(section_lines).strip()


def load_recovery_snapshot(repo_root: Path) -> RecoverySnapshot:
    root = repo_root.resolve()
    current_truth_path = root / "docs" / "recovery" / "current-truth.md"
    runbook_path = root / "docs" / "recovery" / "rebuild-runbook.md"
    artifact_tiers_path = root / "docs" / "recovery" / "artifact-tiers.md"

    warnings: list[str] = []
    for path in (current_truth_path, runbook_path, artifact_tiers_path):
        if not path.exists():
            warnings.append(f"Recovery file missing: {path}")

    current_truth_text = _read_text(current_truth_path)
    current_truth_lines = _read_lines(current_truth_path)
    truth_rows = _get_markdown_table_after_heading(current_truth_lines, "Current status")
    truth_statuses = [
        RecoveryTruthStatus(area=row.get("Area", ""), status=row.get("Status", ""))
        for row in truth_rows
    ]

    artifact_statuses = _load_artifact_statuses(root, artifact_tiers_path)
    runbook_text = _read_text(runbook_path)
    current_truth_last_updated = _extract_last_updated(current_truth_text)

    return RecoverySnapshot(
        repo_root=root,
        current_truth_path=current_truth_path,
        runbook_path=runbook_path,
        artifact_tiers_path=artifact_tiers_path,
        current_truth_last_updated=current_truth_last_updated,
        current_truth_last_updated_iso=_normalize_updated_iso(current_truth_last_updated),
        truth_statuses=truth_statuses,
        artifact_statuses=artifact_statuses,
        surviving_baselines_text=_get_section_text(current_truth_lines, "Surviving baselines"),
        broken_or_stale_text=_get_section_text(current_truth_lines, "Broken or stale right now"),
        canonical_scripts_text=_get_section_text(current_truth_lines, "Canonical scripts on `main`"),
        runbook_text=runbook_text,
        warnings=warnings,
    )
