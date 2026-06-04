@echo off
REM Version: riftreader-operator-status-publisher-cmd-v0.1.0
REM Total-Character-Count: 0000000335
REM Purpose: Thin CMD launcher for publishing operator status to GitHub transport branch.
setlocal
cd /d "%~dp0\.."
python -m tools.riftreader_workflow.operator_status_publisher %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
