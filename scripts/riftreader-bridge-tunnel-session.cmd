@echo off
REM Version: riftreader-bridge-tunnel-session-wrapper-v0.2.1
REM Total-Character-Count: 848
REM Purpose: Thin CMD wrapper for the repo-owned Python RiftReader bridge/tunnel session helper. Python owns all logic.
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO=%%~fI"
set "PYTHON_SCRIPT=%REPO%\tools\riftreader_workflow\bridge_tunnel_session.py"

cd /d "%REPO%" || (
  echo ERROR: Could not change directory to "%REPO%".
  exit /b 1
)

if not exist "%PYTHON_SCRIPT%" (
  echo ERROR: Missing "%PYTHON_SCRIPT%".
  exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%PYTHON_SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%PYTHON_SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

echo ERROR: Neither py nor python was found on PATH.
exit /b 1

REM END_OF_SCRIPT_MARKER
