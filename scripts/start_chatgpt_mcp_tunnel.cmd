@echo off
setlocal
rem Version: riftreader-start-chatgpt-mcp-tunnel-v0.1.0
rem Purpose: Start OpenAI tunnel-client for ChatGPT Web/Desktop after local profile prerequisites are ready.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.openai_tunnel_status --repo "%CD%" --write-profile --write-status --json
if not "%ERRORLEVEL%"=="0" (
  echo BLOCKED: fix the listed tunnel prerequisites before starting tunnel-client
  echo END_RIFTREADER_CHATGPT_MCP_TUNNEL_START_CMD
  exit /b 2
)
tunnel-client doctor --profile-file ".riftreader-local\mcp\openai-tunnel\riftreader-chatgpt.yaml" --explain
if not "%ERRORLEVEL%"=="0" (
  echo BLOCKED: tunnel-client doctor failed
  echo END_RIFTREADER_CHATGPT_MCP_TUNNEL_START_CMD
  exit /b 2
)
tunnel-client run --profile-file ".riftreader-local\mcp\openai-tunnel\riftreader-chatgpt.yaml"
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_CHATGPT_MCP_TUNNEL_START_CMD
exit /b %EXITCODE%
