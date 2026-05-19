@echo off
REM Version: riftreader-mcp-mission-control-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for the MCP Mission Control dashboard.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_mission_control.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
