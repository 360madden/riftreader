@echo off
REM Version: riftreader-operator-status-cmd-v0.1.0
REM Total-Character-Count: 0000000309
REM Purpose: Thin CMD launcher for Python-owned RiftReader operator status board.
setlocal
cd /d "%~dp0\.."
python -m tools.riftreader_workflow.operator_status %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
