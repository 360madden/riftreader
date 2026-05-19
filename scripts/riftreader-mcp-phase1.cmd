@echo off
REM Version: riftreader-mcp-phase1-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for the ChatGPT MCP Phase 1 completion gate.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_phase1_completion.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
