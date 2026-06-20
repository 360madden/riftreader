@echo off
REM Version: riftreader-release-demo-packet-wrapper-v0.1.0
REM Purpose: Thin launcher for the safe RiftReader MCP release/demo packet.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\release_demo_packet.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
