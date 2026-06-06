@echo off
setlocal
rem Version: riftreader-restart-mcp-local-v0.1.0
rem Purpose: Safely restart the local ChatGPT Web/Desktop HTTP MCP server without touching unrelated listeners.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.local_server_control restart --repo "%CD%" --json
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_MCP_LOCAL_RESTART_CMD
exit /b %EXITCODE%
