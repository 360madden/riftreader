@echo off
rem Version: riftreader-primary-workflow-policy-cmd-v0.1.0
rem Total-Character-Count: 367
rem Purpose: Thin launcher for the Python-owned RiftReader primary workflow policy helper. No logic lives in this wrapper.
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\primary_workflow_policy.py" %*
exit /b %ERRORLEVEL%
rem END_OF_SCRIPT_MARKER
