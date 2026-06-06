@echo off
setlocal
rem Version: riftreader-prepare-chatgpt-mcp-tunnel-profile-v0.1.0
rem Purpose: Generate local-only tunnel-client profile and auth-header file without printing secrets.

cd /d "%~dp0.."
python -m tools.riftreader_mcp.openai_tunnel_status --repo "%CD%" --write-profile --write-status --json
set EXITCODE=%ERRORLEVEL%
if "%EXITCODE%"=="0" (
  echo PASS: ChatGPT MCP tunnel profile is ready for tunnel-client doctor
) else (
  echo BLOCKED: ChatGPT MCP tunnel profile written if possible, but prerequisites are incomplete
)
echo END_RIFTREADER_CHATGPT_MCP_TUNNEL_PROFILE_CMD
exit /b %EXITCODE%
