@echo off
REM Version: riftreader-chatgpt-mcp-eval-suite-v0.1.0
REM Purpose: Thin launcher for the Stage 48 ChatGPT MCP eval-suite checklist generator.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\chatgpt_mcp_eval_suite.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
