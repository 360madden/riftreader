@echo off
setlocal
rem Version: riftreader-start-mcp-local-v0.1.0
rem Purpose: Generate local untracked MCP config if needed, then start the read-only RiftReader HTTP MCP server.

cd /d "%~dp0.."
echo RiftReader MCP local server launcher
echo Repo: %CD%

python -m tools.riftreader_mcp.http_server --init-local-config --json
if errorlevel 1 (
  echo FAIL: could not create or read .riftreader-local\mcp\config.json
  exit /b 1
)

echo Local URL: http://127.0.0.1:8765
echo Health URL: http://127.0.0.1:8765/health
echo MCP URL: http://127.0.0.1:8765/mcp
echo Auth: bearer token from .riftreader-local\mcp\config.json or RIFTREADER_MCP_TOKEN
echo END_RIFTREADER_MCP_LOCAL_STARTUP_BEGIN_SERVER

python -m tools.riftreader_mcp.http_server --repo "%CD%"
endlocal
