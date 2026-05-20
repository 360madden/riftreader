@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_select_environment_capture.py %*
exit /b %ERRORLEVEL%
