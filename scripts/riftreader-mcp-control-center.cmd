@echo off
REM Version: riftreader-mcp-control-center-wrapper-v0.1.0
REM Purpose: Start the localhost-only RiftReader ChatGPT MCP Control Center GUI.
REM Safety: No arbitrary shell, Git mutation, RIFT input, CE/x64dbg, ChatGPT registration, or Cloudflare mutation endpoint.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_control_center.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
