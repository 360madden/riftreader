@echo off
setlocal
cd /d "%~dp0.."
where opencode >nul 2>nul
if errorlevel 1 (
  echo OpenCode was not found on PATH.
  echo Run scripts\riftreader-live-triage.cmd --json --write and scripts\riftreader-workflow-status.cmd --compact-json --write directly instead.
  exit /b 1
)
opencode run --dir "%CD%" "Use the RiftReader no-input live observer lane for the non-Codex desktop ChatGPT workflow. Do not edit files, stage, commit, push, send live input, click, run movement, /reloadui, screenshot hotkeys, attach CE/x64dbg, promote stale proof, or write provider repos. Run .\scripts\riftreader-live-triage.cmd --json --write, then run .\scripts\riftreader-workflow-status.cmd --compact-json --write. Summarize live target verdict, live PID(s), artifact PID/HWND, current proof status, movement permission, blockers, warnings, safety flags, and next safe action. If liveTarget is artifact-pid-stale, state that RIFT is online but the proof artifact is historical and movement remains blocked."
exit /b %ERRORLEVEL%
