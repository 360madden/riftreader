@echo off
rem Version: riftreader-transport-probe-wrapper-v0.1.3
rem Total-Character-Count: 322
rem Purpose: Thin CMD convenience launcher for the Python-owned RiftReader transport probe helper.
setlocal
cd /d "%~dp0\.."
python tools\riftreader_workflow\transport_probe.py %*
exit /b %ERRORLEVEL%
rem END_OF_SCRIPT_MARKER
