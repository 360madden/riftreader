@echo off
REM Version: riftreader-mcp-client-cmd-v0.1.0
REM Total-Character-Count: 0000000298
REM Purpose: Thin CMD launcher for RiftReader MCP client config/smoke-test helper.
setlocal
cd /d "%~dp0\.."
python tools\riftreader_mcp\client_config.py %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
