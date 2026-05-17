@echo off
setlocal
cd /d "%~dp0.."
where opencode >nul 2>nul
if errorlevel 1 (
  echo OpenCode was not found on PATH.
  echo Run scripts\riftreader-live-triage.cmd --json --write and scripts\riftreader-workflow-status.cmd --compact-json --write directly instead.
  exit /b 1
)
if "%RIFTREADER_OPENCODE_MODEL%"=="" set "RIFTREADER_OPENCODE_MODEL=openai/gpt-5.5"
echo Using OpenCode model: %RIFTREADER_OPENCODE_MODEL%
opencode run --dir "%CD%" -m "%RIFTREADER_OPENCODE_MODEL%" "Use the RiftReader no-input live observer lane for the non-Codex desktop ChatGPT workflow. Do not edit files, stage, commit, push, send live input, click, run movement, /reloadui, screenshot hotkeys, attach CE/x64dbg, promote stale proof, or write provider repos. Run .\scripts\riftreader-live-triage.cmd --json --write, then run .\scripts\riftreader-workflow-status.cmd --compact-json --write. Summarize live target verdict, live PID(s), artifact PID/HWND, current proof status, movement permission, blockers, warnings, OpenCode requested model/model visibility, safety flags, and next safe action. If liveTarget is artifact-pid-stale, state that a rift_x64 process is visible but the proof artifact is historical, process visibility is not same-target/in-world proof, and movement remains blocked."
exit /b %ERRORLEVEL%
