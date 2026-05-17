@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: scripts\riftreader-opencode-package-review.cmd ^<package-dir-or-zip^>
  echo Runs adaptive OpenCode package inspection only. It does not apply edits.
  exit /b 1
)
python "%~dp0..\tools\riftreader_workflow\opencode_bridge.py" --lane package-review --package "%~1" --run
exit /b %ERRORLEVEL%
