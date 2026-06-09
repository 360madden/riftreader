@echo off
setlocal EnableExtensions DisableDelayedExpansion
REM Version: riftreader-root-chatgpt-mcp-launcher-v0.1.0
REM Purpose: Root-level launcher for the local RiftReader ChatGPT Web/Desktop MCP adapter.
REM Scope: Starts only the repo-owned narrow MCP adapter on 127.0.0.1:8770.
REM Safety: Does not start tunnels, mutate Git, send RIFT input, or launch CE/x64dbg.

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
cd /d "%REPO_ROOT%" || (
  echo FAIL: could not cd to repo root: %REPO_ROOT%
  exit /b 1
)

set "ADAPTER=tools\riftreader_workflow\riftreader_chatgpt_mcp.py"
if not exist "%ADAPTER%" (
  echo FAIL: missing %ADAPTER%
  echo This launcher must be run from the RiftReader repo root.
  exit /b 1
)

if defined RIFTREADER_PYTHON (
  set "PY_CMD=%RIFTREADER_PYTHON%"
  goto PYTHON_READY
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3"
  goto PYTHON_READY
)

python --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python"
  goto PYTHON_READY
)

echo FAIL: no Python launcher found.
echo Tried: RIFTREADER_PYTHON, py -3, python
echo Set RIFTREADER_PYTHON to a Python executable path, then retry.
exit /b 1

:PYTHON_READY
if "%~1"=="" goto SERVE_FULL
if /I "%~1"=="serve" goto SERVE_FULL
if /I "%~1"=="full" goto SERVE_FULL
if /I "%~1"=="readonly" goto SERVE_READONLY
if /I "%~1"=="read-only" goto SERVE_READONLY
if /I "%~1"=="selftest" goto SELF_TEST
if /I "%~1"=="self-test" goto SELF_TEST
if /I "%~1"=="validate" goto VALIDATE
if /I "%~1"=="smoke" goto SMOKE
if /I "%~1"=="proposal-smoke" goto PROPOSAL_SMOKE
if /I "%~1"=="plan" goto PLAN
if /I "%~1"=="help" goto HELP
if /I "%~1"=="/?" goto HELP

echo RiftReader ChatGPT MCP root launcher: forwarding custom arguments to adapter.
echo Repo: %CD%
echo Python: %PY_CMD%
echo Adapter: %ADAPTER%
%PY_CMD% "%ADAPTER%" %*
goto EXIT_WITH_CODE

:SERVE_FULL
echo RiftReader ChatGPT MCP local server - FULL 12-tool profile
echo Repo: %CD%
echo Local backend: http://127.0.0.1:8770/mcp
echo ChatGPT Server URL: https://mcp.360madden.com/mcp
echo Auth: No Authentication
echo Stop with Ctrl+C in this window.
echo END_RIFTREADER_CHATGPT_MCP_LAUNCH_BEGIN_SERVER
%PY_CMD% "%ADAPTER%" --serve --tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
goto EXIT_WITH_CODE

:SERVE_READONLY
echo RiftReader ChatGPT MCP local server - PUBLIC READ-ONLY profile
echo Repo: %CD%
echo Local backend: http://127.0.0.1:8770/mcp
echo ChatGPT Server URL: https://mcp.360madden.com/mcp
echo Auth: No Authentication
echo Stop with Ctrl+C in this window.
echo END_RIFTREADER_CHATGPT_MCP_READONLY_LAUNCH_BEGIN_SERVER
%PY_CMD% "%ADAPTER%" --serve --tool-profile public-read-only --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
goto EXIT_WITH_CODE

:SELF_TEST
%PY_CMD% "%ADAPTER%" --self-test --json
goto EXIT_WITH_CODE

:VALIDATE
%PY_CMD% "%ADAPTER%" --validate-sdk --json
goto EXIT_WITH_CODE

:SMOKE
%PY_CMD% "%ADAPTER%" --transport-smoke --json
goto EXIT_WITH_CODE

:PROPOSAL_SMOKE
%PY_CMD% "%ADAPTER%" --proposal-transport-smoke --json
goto EXIT_WITH_CODE

:PLAN
%PY_CMD% "%ADAPTER%" --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
goto EXIT_WITH_CODE

:HELP
echo RiftReader ChatGPT MCP root launcher
echo.
echo Usage:
echo   START_RIFTREADER_CHATGPT_MCP.cmd
echo   START_RIFTREADER_CHATGPT_MCP.cmd serve
echo   START_RIFTREADER_CHATGPT_MCP.cmd readonly
echo   START_RIFTREADER_CHATGPT_MCP.cmd self-test
echo   START_RIFTREADER_CHATGPT_MCP.cmd validate
echo   START_RIFTREADER_CHATGPT_MCP.cmd smoke
echo   START_RIFTREADER_CHATGPT_MCP.cmd proposal-smoke
echo   START_RIFTREADER_CHATGPT_MCP.cmd plan
echo   START_RIFTREADER_CHATGPT_MCP.cmd --call health --json
echo.
echo Default/serve starts:
echo   tools\riftreader_workflow\riftreader_chatgpt_mcp.py --serve --tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
echo.
echo The canonical ChatGPT Server URL remains:
echo   https://mcp.360madden.com/mcp
echo.
echo This launcher does not start Cloudflared, edit ChatGPT, mutate Git, send RIFT input, or expose shell/CE/x64dbg tools.
set "EXITCODE=0"
goto FINAL_EXIT

:EXIT_WITH_CODE
set "EXITCODE=%ERRORLEVEL%"

:FINAL_EXIT
echo END_RIFTREADER_CHATGPT_MCP_ROOT_LAUNCHER exit=%EXITCODE%
if not "%EXITCODE%"=="0" (
  if not "%RIFTREADER_MCP_NO_PAUSE%"=="1" pause
)
exit /b %EXITCODE%
