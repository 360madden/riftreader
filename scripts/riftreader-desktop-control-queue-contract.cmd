@echo off
REM Version: riftreader-desktop-control-queue-contract-v0.1.0
REM Purpose: Thin launcher for the inert Browser/Computer command queue contract.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\desktop_control_queue_contract.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
