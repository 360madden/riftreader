@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\live_test_triage.py" %*
exit /b %ERRORLEVEL%
