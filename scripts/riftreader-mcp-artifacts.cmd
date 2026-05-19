@echo off
REM Version: riftreader-mcp-artifacts-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for browsing latest MCP workflow artifacts.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_artifact_browser.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
