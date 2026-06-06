@echo off
setlocal
rem Version: riftreader-test-mcp-local-v0.1.0
rem Purpose: Run local read-only HTTP MCP smoke tests without printing secrets.

cd /d "%~dp0.."
echo RiftReader MCP local smoke test
python -m tools.riftreader_mcp.smoke_http --repo "%CD%" --json
set EXITCODE=%ERRORLEVEL%
if "%EXITCODE%"=="0" (
  echo PASS: RiftReader MCP local smoke passed
) else (
  echo FAIL: RiftReader MCP local smoke failed
)
echo END_RIFTREADER_MCP_LOCAL_TEST
exit /b %EXITCODE%
