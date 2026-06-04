@echo off
REM Version: riftreader-mcp-call-cmd-v0.1.2
REM Total-Character-Count: 0000000288
REM Purpose: Thin CMD launcher for calling one RiftReader MCP tool over stdio.
setlocal
cd /d "%~dp0\.."
python tools\riftreader_mcp\call_tool.py %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
