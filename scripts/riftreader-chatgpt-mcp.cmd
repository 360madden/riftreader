@echo off
REM Version: riftreader-chatgpt-mcp-wrapper-v0.1.0
REM Purpose: Thin launcher for the narrow RiftReader ChatGPT Developer Mode MCP adapter.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
