@echo off
REM Version: riftreader-mcp-domain-diagnostics-wrapper-v0.1.0
REM Purpose: Thin launcher for status-only ChatGPT MCP domain/proxy diagnostics.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_domain_diagnostics.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
