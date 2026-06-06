@echo off
setlocal
rem Version: riftreader-check-mcp-local-server-v0.1.0
rem Purpose: Print safe status for the local ChatGPT Web/Desktop HTTP MCP server.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.local_server_control status --repo "%CD%" --json
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_MCP_LOCAL_SERVER_STATUS_CMD
exit /b %EXITCODE%
