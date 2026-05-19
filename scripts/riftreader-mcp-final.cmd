@echo off
REM Version: riftreader-mcp-final-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for the ChatGPT MCP final readiness gate.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_final_readiness.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
