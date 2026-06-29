@echo off
REM Version: riftreader-mcp-recovery-plan-cmd-v0.1.0
REM Total-Character-Count: 0000000317
REM Purpose: Thin CMD launcher for the Stage 52 Python MCP readiness recovery plan.
setlocal
cd /d "%~dp0\.."
python -m tools.riftreader_workflow.mcp_recovery_plan %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER

