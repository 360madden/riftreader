@echo off
REM Version: riftreader-workflow-router-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for routing to the next safest workflow action.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\workflow_router.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
