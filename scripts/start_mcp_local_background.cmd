@echo off
setlocal
rem Version: riftreader-start-mcp-local-background-v0.1.0
rem Purpose: Start the local ChatGPT Web/Desktop HTTP MCP server in the background with safe process checks.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.local_server_control start --repo "%CD%" --json
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_MCP_LOCAL_BACKGROUND_START_CMD
exit /b %EXITCODE%
