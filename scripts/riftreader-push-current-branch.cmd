@echo off
REM Version: riftreader-push-current-branch-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for read-only push preflight and self-test.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\push_current_branch.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
