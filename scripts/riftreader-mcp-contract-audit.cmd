@echo off
REM Version: riftreader-mcp-contract-audit-wrapper-v0.1.0
REM Purpose: Thin launcher for the read-only RiftReader MCP contract/timing audit.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\mcp_contract_audit.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
