# Third-party workflow tools

This is the durable catalog of third-party tools that are intentionally part of
the RiftReader development workflow. Do not remove these tools, wrappers,
configs, hooks, or CI setup just to make a local check pass. If one breaks,
repair or replace it with an equivalent tool and document the replacement here.

Last verified locally: 2026-06-03.

## Preservation policy

| Rule | Required behavior |
|---|---|
| Dedicated installs | Keep machine-local installs under dedicated subfolders in `C:\RIFT MODDING\tools\`. Do not flatten tools into the repo or into sibling tool folders. |
| Repo wrappers | Keep Python wrappers under `scripts\` for tools that need stable path resolution. Prefer fixing wrappers over deleting hooks. |
| Default hooks | Do not disable default pre-commit hooks unless the replacement is equal or stronger and validated locally plus in CI. |
| Manual hooks | Keep heavier/noisier checks manual until the repo has a clean all-files baseline and the user explicitly approves default gating. |
| CI parity | Any default hook that needs a binary must be available in CI. For example, CI installs actionlint before running pre-commit. |
| Missing local tool | Treat a missing tool as a setup issue. Reinstall or point the wrapper at it with the documented environment variable. |
| PSScriptAnalyzer | Intentionally not installed or configured. Do not add it unless the user explicitly asks. |
| Live safety | Never put live RIFT input, movement, debugger attach, Cheat Engine, provider writes, proof promotion, Git push, or remote mutation inside automatic hooks. |

## Tool inventory

| Tool | Local install / source | Repo-owned integration | Stage | Why it stays |
|---|---|---|---|---|
| pre-commit | `C:\RIFT MODDING\tools\pre-commit\` | `.pre-commit-config.yaml`, `scripts\install_precommit_hook.py`, `.git\hooks\pre-commit` locally | Default gate runner | Provides the fast deterministic commit gate and shared hook cache under `PRE_COMMIT_HOME`. |
| pre-commit-hooks | Managed by pre-commit cache | `.pre-commit-config.yaml` remote repo `pre-commit/pre-commit-hooks` | Default | Basic syntax, merge-conflict, case-conflict, and private-key checks. |
| Ruff | `C:\RIFT MODDING\tools\ruff\` plus pre-commit hook env | `.pre-commit-config.yaml` remote repo `astral-sh/ruff-pre-commit` | Default | Fast critical Python lint for parse/pyflakes failures without formatting churn. |
| actionlint | `C:\RIFT MODDING\tools\actionlint\` | `scripts\actionlint_check.py`, `.pre-commit-config.yaml`, `.github\workflows\riftreader-policy.yml` | Default for workflow files | Catches GitHub Actions mistakes before CI. CI installs pinned actionlint for parity. |
| EditorConfig | Repo config, no binary required for current verifier | `.editorconfig`, `scripts\editorconfig_verify.py`, `.pre-commit-config.yaml` | Default for `.editorconfig` | Preserves baseline whitespace/final-newline intent across editors and agents. |
| Gitleaks | `C:\RIFT MODDING\tools\gitleaks\` | `.gitleaksignore`, `scripts\gitleaks_history_scan.py`, `.pre-commit-config.yaml` | Manual | Scans Git history for secrets before publish/PR without slowing every commit. |
| Pyright | `C:\RIFT MODDING\tools\pyright\` | `pyrightconfig.json`, `scripts\pyright_manual_gate.py`, `.pre-commit-config.yaml` | Manual | Type-checks the current safe Python bootstrap scope while broad repo typing is still a cleanup campaign. |
| Semgrep CE | `C:\RIFT MODDING\tools\semgrep\` | `semgrep.yml`, `scripts\semgrep_manual_scan.py`, `.pre-commit-config.yaml` | Manual | Encodes repo safety rules for workflow Python, currently no `shell=True` / `os.system` in workflow helpers. |
| OSV-Scanner | `C:\RIFT MODDING\tools\osv-scanner\` | `scripts\osv_scanner_manual_scan.py`, `.pre-commit-config.yaml` | Manual | Finds known dependency vulnerabilities without making every commit depend on advisory/network state. |
| Renovate | `C:\RIFT MODDING\tools\renovate\` | `renovate.json`, `scripts\renovate_config_validate.py`, `.pre-commit-config.yaml` | Manual config validation | Keeps dependency update automation configured conservatively before any hosted Renovate enablement. |
| markdownlint-cli2 | `C:\RIFT MODDING\tools\markdownlint-cli2\` | `.markdownlint-cli2.yaml`, `scripts\markdownlint_manual.py`, `.pre-commit-config.yaml` | Manual | Allows scoped Markdown quality checks without blocking on existing docs-wide lint debt. |

## Supporting third-party runtimes and services

| Tool/service | Where used | Notes |
|---|---|---|
| Python | Hook wrappers, validation helpers, pre-commit, Semgrep venv | Prefer Python for workflow automation and wrappers. |
| Node/npm | Renovate, markdownlint-cli2, Pyright, `tools\rift-game-mcp` dependency validation | Keep Node package installs scoped to their tool/repo folders. |
| GitHub Actions | `.github\workflows\*.yml` | `riftreader-policy.yml` runs pre-commit and installs actionlint for CI parity. |
| npm audit | `tools\rift-game-mcp` validation | Used to verify lockfile vulnerability cleanup after OSV findings. |

## Verification commands

Run from the repo root:

```powershell
Set-Location "C:\RIFT MODDING\RiftReader"
pre-commit run --all-files --show-diff-on-failure
pre-commit run riftreader-semgrep-manual --hook-stage manual
pre-commit run riftreader-osv-scanner-manual --hook-stage manual
pre-commit run riftreader-renovate-config-validate --hook-stage manual --all-files
pre-commit run riftreader-markdownlint-manual --hook-stage manual --files docs/workflow/pre-commit-local-gates.md docs/workflow/third-party-workflow-tools.md
python scripts\pyright_manual_gate.py
python scripts\gitleaks_history_scan.py
```

If `pre-commit` is not on PATH in the current terminal, use:

```powershell
& "C:\RIFT MODDING\tools\pre-commit\pre-commit.cmd" run --all-files --show-diff-on-failure
```

## Wrapper environment overrides

Use these only when a tool is intentionally installed somewhere other than the
standard `C:\RIFT MODDING\tools\` location:

| Wrapper | Override variable |
|---|---|
| `scripts\actionlint_check.py` | `RIFTREADER_ACTIONLINT` |
| `scripts\gitleaks_history_scan.py` | `RIFTREADER_GITLEAKS` |
| `scripts\install_precommit_hook.py` | `RIFTREADER_PRE_COMMIT` |
| `scripts\markdownlint_manual.py` | `RIFTREADER_MARKDOWNLINT` |
| `scripts\osv_scanner_manual_scan.py` | `RIFTREADER_OSV_SCANNER` |
| `scripts\pyright_manual_gate.py` | `RIFTREADER_PYRIGHT` |
| `scripts\renovate_config_validate.py` | `RIFTREADER_RENOVATE_CONFIG_VALIDATOR` |
| `scripts\semgrep_manual_scan.py` | `RIFTREADER_SEMGREP` |

## Known intentional boundaries

- Markdown linting is manual because existing docs have historical style debt.
- Pyright is manual and scoped because broad Python type checking previously
  produced a large existing baseline.
- OSV-Scanner is manual because vulnerability advisory checks can require
  network/advisory triage and should not block ordinary local commits.
- Semgrep is manual while its repo-specific ruleset is still small and targeted.
- Gitleaks history scanning is manual because it is heavier and intentionally
  uses narrow reviewed fingerprints in `.gitleaksignore`.
