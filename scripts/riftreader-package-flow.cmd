@echo off
REM Version: riftreader-package-flow-wrapper-v0.1.1
REM Total-Character-Count: 297
REM Purpose: Thin CMD launcher for Python-owned RiftReader package flow orchestration.
cd /d "%~dp0\.."
python "tools\riftreader_workflow\package_flow.py" %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
