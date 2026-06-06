@echo off
setlocal
rem Version: riftreader-check-chatgpt-mcp-tunnel-readiness-v0.1.0
rem Purpose: Secret-safe readiness check for ChatGPT Web/Desktop via OpenAI Secure MCP Tunnel.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.openai_tunnel_status --repo "%CD%" --write-status --json
set EXITCODE=%ERRORLEVEL%
if "%EXITCODE%"=="0" (
  echo PASS: ChatGPT MCP tunnel profile is ready for tunnel-client doctor
) else (
  echo BLOCKED: ChatGPT MCP tunnel setup is missing one or more prerequisites
)
echo END_RIFTREADER_CHATGPT_MCP_TUNNEL_READINESS_CMD
exit /b %EXITCODE%
