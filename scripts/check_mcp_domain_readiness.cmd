@echo off
setlocal
rem Version: riftreader-check-mcp-domain-readiness-v0.1.0
rem Purpose: Check whether bought-only 360madden.com is ready for the MCP Cloudflare Tunnel route.

cd /d "%~dp0.."
echo RiftReader MCP domain readiness check
python -m tools.riftreader_mcp.domain_preflight --repo "%CD%" --write --json
set EXITCODE=%ERRORLEVEL%
echo END_RIFTREADER_MCP_DOMAIN_READINESS_CMD
exit /b %EXITCODE%
