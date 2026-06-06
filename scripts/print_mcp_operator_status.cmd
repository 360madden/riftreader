@echo off
setlocal
rem Version: riftreader-print-mcp-operator-status-v0.1.0
rem Purpose: Print and write the latest operator status packet for the 360madden MCP lane.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.operator_status --repo "%CD%" --write --json
set EXITCODE=%ERRORLEVEL%
if "%EXITCODE%"=="0" (
  echo PASS: operator status written under .riftreader-local\mcp\latest
) else (
  echo FAIL: operator status failed
)
echo END_RIFTREADER_MCP_OPERATOR_STATUS_CMD
exit /b %EXITCODE%
