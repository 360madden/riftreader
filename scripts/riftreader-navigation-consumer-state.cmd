@echo off
setlocal
cd /d "%~dp0\.."
python scripts\navigation_consumer_state.py %*
exit /b %ERRORLEVEL%
