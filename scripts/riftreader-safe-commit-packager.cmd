@echo off
REM Version: riftreader-safe-commit-packager-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for generating explicit-path commit plans.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\safe_commit_packager.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
