@echo off
REM Version: riftreader-stage38-consideration-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for the local-only Stage 38 consideration gate.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\stage38_consideration.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
