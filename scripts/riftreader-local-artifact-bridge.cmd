@echo off
REM Version: riftreader-local-artifact-bridge-wrapper-v0.1.0
REM Total-Character-Count: 402
REM Purpose: Thin CMD wrapper that changes to the RiftReader repo root and delegates all logic to the Python local artifact bridge helper.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\local_artifact_bridge.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
