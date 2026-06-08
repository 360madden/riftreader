@echo off
REM Version: riftreader-desktop-control-readiness-v0.1.0
REM Purpose: Thin launcher for read-only Browser/Computer Use readiness.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\desktop_control_readiness.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
