# Version: riftreader-primary-workflow-policy-v0.1.0
# Total-Character-Count: 8460
# Purpose: Repo-owned helper that writes RiftReader workflow policy docs. Local Python plus local git/gh CLI is primary; Google Drive and OpenCode are optional only. No Git mutation, no OpenCode run, no Drive dependency, no live RIFT action.
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POLICY_DOC = Path("docs/workflow/local-git-gh-primary-workflow.md")
NON_CODEX_DOC = Path("docs/workflow/non-codex-desktop-chatgpt-workflow.md")
OPENCODE_DOC = Path("docs/workflow/opencode-non-codex-bridge.md")
DRIVE_DOC = Path("docs/development/riftreader-drive-outbox-and-intake.md")
TARGET_DOCS = (POLICY_DOC, NON_CODEX_DOC, OPENCODE_DOC, DRIVE_DOC)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / "agents.md").exists():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def read_text_or_default(path: Path, title: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"# {title}\n"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip() + "\n"


def marker_block(name: str, title: str, body: str) -> str:
    return f"<!-- {name}-BEGIN -->\n## {title}\n\n{body.strip()}\n<!-- {name}-END -->"


def upsert_marker_block(text: str, name: str, title: str, body: str) -> str:
    begin = f"<!-- {name}-BEGIN -->"
    end = f"<!-- {name}-END -->"
    block = marker_block(name, title, body)
    if begin in text and end in text:
        before = text.split(begin, 1)[0].rstrip()
        after = text.split(end, 1)[1].lstrip()
        return normalize(before + "\n\n" + block + "\n\n" + after)
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        return normalize(lines[0] + "\n\n" + block + "\n\n" + "\n".join(lines[1:]).lstrip())
    return normalize(block + "\n\n" + text.lstrip())


def primary_policy_body() -> str:
    return """Primary workflow is now **local Python helpers + local git/gh CLI + GitHub read-only inspection**.

- Google Drive is optional archive/fallback only.
- OpenCode is optional scoped assistant only and is not default because it uses agentic/Codex quota.
- GitHub connector is read-only for ChatGPT inspection.
- Repo writes should happen locally through `git`/`gh`.
- PowerShell/CMD should remain thin launchers only.
"""


def primary_workflow_doc(generated_utc: str) -> str:
    return normalize(f"""# Local Git/GitHub CLI Primary Workflow

Generated UTC: `{generated_utc}`

## Decision

RiftReader's default workflow is now **local Python plus local git/gh CLI**.

Google Drive and OpenCode are not default control-plane tools. They remain available only for specific fallback cases.

## Tool roles

| Tool | Role |
|---|---|
| Local repo | Source of truth and execution environment |
| Repo-owned Python helpers | Primary automation and validation layer |
| PowerShell / CMD | Thin launchers only |
| Local `git` | Stage explicit files, commit, push, verify remote SHA |
| Local `gh` CLI | GitHub auth/status/API/PR/check helper when needed |
| GitHub connector | Read-only remote inspection by ChatGPT |
| Google Drive | Optional archive for large ignored artifacts |
| OpenCode | Optional scoped assistant only when explicitly authorized |

## Primary flow

```text
ChatGPT plans/reviews
-> local repo-owned Python helper
-> local validation
-> local git/gh commit-push-verify
-> ChatGPT reads GitHub read-only
```

## Hard rules

- Do not rely on GitHub connector writes.
- Do not use OpenCode by default.
- Do not use Google Drive as the normal control plane.
- Do not use `git add .`.
- Stage explicit files only.
- Verify local HEAD equals remote HEAD after push.
- Keep live RIFT input, proof promotion, CE, and x64dbg outside workflow-integration lanes unless explicitly selected.

## Fallback use

| Fallback | Allowed use |
|---|---|
| Google Drive | Large logs, screenshots, capture bundles, ignored `.riftreader-local` artifacts, archive material |
| OpenCode | Explicitly authorized scoped local assistance only |
""")


def desired_doc_contents(repo_root: Path, generated_utc: str) -> dict[Path, str]:
    non_codex = read_text_or_default(repo_root / NON_CODEX_DOC, "Non-Codex Desktop ChatGPT Workflow")
    opencode = read_text_or_default(repo_root / OPENCODE_DOC, "OpenCode Bridge for the Non-Codex Desktop ChatGPT Workflow")
    drive = read_text_or_default(repo_root / DRIVE_DOC, "RiftReader Drive Outbox Export and Intake Report")
    return {
        POLICY_DOC: primary_workflow_doc(generated_utc),
        NON_CODEX_DOC: upsert_marker_block(
            non_codex,
            "RIFTREADER-PRIMARY-WORKFLOW-POLICY",
            "Current primary workflow policy",
            primary_policy_body(),
        ),
        OPENCODE_DOC: upsert_marker_block(
            opencode,
            "RIFTREADER-OPENCODE-DEMOTION",
            "Current status: OpenCode optional only",
            "OpenCode is no longer the default RiftReader executor. Use it only when explicitly authorized for a scoped task. Normal workflow uses local Python helpers plus local `git`/`gh`.",
        ),
        DRIVE_DOC: upsert_marker_block(
            drive,
            "RIFTREADER-DRIVE-DEMOTION",
            "Current status: Drive optional archive only",
            "Google Drive is no longer the primary workflow control plane. Use it only for large ignored artifacts, screenshots, logs, captures, and archive material.",
        ),
    }


def build_summary(repo_root: Path, *, apply: bool, generated_utc: str) -> dict[str, Any]:
    desired = desired_doc_contents(repo_root, generated_utc)
    changes: list[dict[str, Any]] = []
    for rel_path, new_text in desired.items():
        full_path = repo_root / rel_path
        old_text = full_path.read_text(encoding="utf-8") if full_path.exists() else None
        old_norm = normalize(old_text) if old_text is not None else None
        new_norm = normalize(new_text)
        changed = old_norm != new_norm
        if apply and changed:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(new_norm, encoding="utf-8")
        changes.append(
            {
                "path": str(rel_path).replace("\\", "/"),
                "changed": changed,
                "existedBefore": old_text is not None,
            }
        )
    return {
        "schemaVersion": 1,
        "kind": "riftreader-primary-workflow-policy-summary",
        "generatedAtUtc": generated_utc,
        "status": "applied" if apply else "dry-run",
        "dryRun": not apply,
        "repoRoot": str(repo_root),
        "changedFiles": [item["path"] for item in changes if item["changed"]],
        "files": changes,
        "safety": {
            "gitMutation": False,
            "githubConnectorWrite": False,
            "opencodeRun": False,
            "driveDependency": False,
            "liveRiftInput": False,
            "proofPromotion": False,
            "ceOrX64dbg": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write RiftReader primary workflow policy docs.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; auto-detected by default.")
    parser.add_argument("--apply", action="store_true", help="Write docs. Default is dry-run.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    summary = build_summary(repo_root, apply=args.apply, generated_utc=utc_now())
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Status: {summary['status']}")
        print("Changed files:")
        for path in summary["changedFiles"] or ["none"]:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
