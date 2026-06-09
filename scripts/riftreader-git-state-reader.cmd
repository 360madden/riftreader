@echo off
REM Version: riftreader-git-state-reader-cmd-v0.1.0
REM Total-Character-Count: 0000000315
REM Purpose: Thin CMD wrapper for the read-only Git state reader helper.
setlocal
cd /d "%~dp0\.."
python tools\riftreader_workflow\git_state_reader.py %*
set "RIFTREADER_EXIT_CODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %RIFTREADER_EXIT_CODE%
