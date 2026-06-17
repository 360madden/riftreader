@echo off
setlocal
rem Version: riftreader-check-mcp-local-server-v0.2.0
rem Purpose: Print safe status for the current ChatGPT Web/Desktop MCP backend.

cd /d "%~dp0.."
python -m tools.riftreader_workflow.mcp_server_status --repo-root "%CD%" --json %*
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_MCP_LOCAL_SERVER_STATUS_CMD
exit /b %EXITCODE%
