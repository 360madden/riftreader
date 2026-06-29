@echo off
REM Version: riftreader-status-cmd-v0.1.0
REM Total-Character-Count: 0000000310
REM Purpose: Thin CMD launcher for the Stage 51 unified RiftReader operator status packet.
setlocal
cd /d "%~dp0\.."
python -m tools.riftreader_workflow.operator_status %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
