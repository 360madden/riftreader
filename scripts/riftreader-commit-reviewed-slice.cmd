@echo off
REM Version: riftreader-commit-reviewed-slice-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for read-only commit preflight and self-test.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\commit_reviewed_slice.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
