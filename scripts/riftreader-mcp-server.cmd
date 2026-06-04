@echo off
REM Version: riftreader-mcp-server-cmd-v0.1.0
REM Total-Character-Count: 0000000276
REM Purpose: Thin CMD launcher for the RiftReader MCP stdio server.
setlocal
cd /d "%~dp0\.."
python tools\riftreader_mcp\server.py %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
