@echo off
setlocal
rem Version: riftreader-mcp-server-status-cmd-v0.1.0
rem Purpose: Read-only status for the current ChatGPT Web/Desktop MCP backend.

cd /d "%~dp0.."
python -m tools.riftreader_workflow.mcp_server_status --repo-root "%CD%" --json %*
exit /b %ERRORLEVEL%
