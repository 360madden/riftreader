@echo off
REM Version: riftreader-recovery-classifier-cmd-v0.1.0
REM Total-Character-Count: 0000000319
REM Purpose: Thin CMD launcher for the Python-owned RiftReader recovery classifier.
setlocal
cd /d "%~dp0\.."
python -m tools.riftreader_workflow.recovery_classifier %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
