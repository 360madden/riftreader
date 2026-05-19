@echo off
REM Version: riftreader-mcp-phase2-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for the ChatGPT MCP Phase 2 status gate.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_phase2_status.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
