@echo off
setlocal
cd /d "%~dp0.."
where opencode >nul 2>nul
if errorlevel 1 (
  echo OpenCode was not found on PATH. Run scripts\riftreader-workflow-status.cmd directly instead.
  exit /b 1
)
if "%RIFTREADER_OPENCODE_MODEL%"=="" set "RIFTREADER_OPENCODE_MODEL=openai/gpt-5.5"
echo Using OpenCode model: %RIFTREADER_OPENCODE_MODEL%
opencode run --dir "%CD%" -m "%RIFTREADER_OPENCODE_MODEL%" "Use the RiftReader read-only non-Codex bridge. Do not edit files, stage, commit, push, send live input, run movement, /reloadui, screenshot hotkeys, attach CE/x64dbg, or write provider repos. Run .\scripts\riftreader-workflow-status.cmd --compact-json --write, then summarize current branch, HEAD, latest handoff, OpenCode version, OpenCode requested model/model visibility, liveTarget verdict/livePids/artifactPid/artifactHwnd, current proof status, movement permission, blockers, warnings, stale proof reuse policy, validation status, and next safe action for desktop ChatGPT. If liveTarget is artifact-pid-stale, say clearly that a rift_x64 process is visible but the proof artifact is historical, process visibility is not same-target/in-world proof, and movement remains blocked."
exit /b %ERRORLEVEL%
