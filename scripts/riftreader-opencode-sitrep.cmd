@echo off
setlocal
cd /d "%~dp0.."
where opencode >nul 2>nul
if errorlevel 1 (
  echo OpenCode was not found on PATH. Run scripts\riftreader-workflow-status.cmd directly instead.
  exit /b 1
)
opencode run --dir "%CD%" "Use the RiftReader read-only non-Codex bridge. Do not edit files, stage, commit, push, send live input, run movement, attach CE/x64dbg, or write provider repos. Run .\scripts\riftreader-workflow-status.cmd --json --write, then summarize current branch, HEAD, latest handoff, current proof status, movement permission, blockers, stale proof reuse policy, validation status, and next safe action for desktop ChatGPT."
exit /b %ERRORLEVEL%
