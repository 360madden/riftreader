@echo off
setlocal
rem Version: riftreader-stop-mcp-local-v0.1.0
rem Purpose: Safely stop the local ChatGPT Web/Desktop HTTP MCP server without touching unrelated listeners.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.local_server_control stop --repo "%CD%" --json
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_MCP_LOCAL_STOP_CMD
exit /b %EXITCODE%
