@echo off
REM Version: riftreader-chatgpt-trial-recorder-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for recording ChatGPT actual-client proof facts.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\chatgpt_trial_recorder.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
