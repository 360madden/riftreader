@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: scripts\riftreader-opencode-package-review.cmd ^<package-dir-or-zip^>
  echo Runs OpenCode package inspection only. It does not apply edits.
  exit /b 1
)
where opencode >nul 2>nul
if errorlevel 1 (
  echo OpenCode was not found on PATH.
  echo Run scripts\riftreader-package-intake.cmd --package "%~1" --compact-json directly instead.
  exit /b 1
)
set "PACKAGE_PATH=%~1"
opencode run --dir "%CD%" "Use the RiftReader package-inspection lane for the non-Codex desktop ChatGPT workflow. Do not edit files, apply files, stage, commit, push, send live input, run movement, /reloadui, screenshot hotkeys, attach CE/x64dbg, or write provider repos. Inspect package path between PACKAGE_PATH_BEGIN and PACKAGE_PATH_END: PACKAGE_PATH_BEGIN%PACKAGE_PATH%PACKAGE_PATH_END. Run .\scripts\riftreader-package-intake.cmd --package PACKAGE_PATH --compact-json, replacing PACKAGE_PATH with that exact path and quoting it if needed. Summarize package status, dryRun, changedFiles, blockers, warnings, errors, diff path, compact artifact path, safety flags, and the next safe action. If the package is valid, say that applying still requires explicit operator approval with --apply; do not apply it in this run."
exit /b %ERRORLEVEL%
