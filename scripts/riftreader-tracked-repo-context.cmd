@echo off
REM Version: riftreader-tracked-repo-context-cmd-v0.1.0
REM Total-Character-Count: 0000000320
REM Purpose: Thin launcher for the read-only git-tracked RiftReader context helper.
setlocal
cd /d "%~dp0\.."
python tools\riftreader_workflow\tracked_repo_context.py %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
