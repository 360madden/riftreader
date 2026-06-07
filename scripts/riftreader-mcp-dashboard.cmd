@echo off
REM Version: riftreader-mcp-dashboard-wrapper-v0.1.0
REM Purpose: Thin launcher for localhost-only ChatGPT MCP status dashboard.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_dashboard.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
