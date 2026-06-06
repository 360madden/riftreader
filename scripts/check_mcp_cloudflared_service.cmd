@echo off
setlocal
rem Version: riftreader-check-mcp-cloudflared-service-v0.1.0
rem Purpose: Print secret-safe cloudflared service/process status for the 360madden MCP lane.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.cloudflared_status --repo "%CD%" --write --json
set EXITCODE=%ERRORLEVEL%
if "%EXITCODE%"=="0" (
  echo PASS: cloudflared connector process detected
) else (
  echo BLOCKED: cloudflared connector process not detected
)
echo END_RIFTREADER_MCP_CLOUDFLARED_STATUS_CMD
exit /b %EXITCODE%
