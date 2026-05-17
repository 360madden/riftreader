@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\operator_lite.py" %*
exit /b %ERRORLEVEL%
