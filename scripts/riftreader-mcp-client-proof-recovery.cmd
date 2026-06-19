@echo off
setlocal
rem Version: riftreader-mcp-client-proof-recovery-cmd-v0.1.0
rem Purpose: Thin launcher for stale ChatGPT MCP actual-client proof recovery.

cd /d "%~dp0.."
python -m tools.riftreader_workflow.mcp_client_proof_recovery --repo-root "%CD%" %*
exit /b %ERRORLEVEL%
