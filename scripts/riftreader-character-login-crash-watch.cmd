@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_crash_watch.py %*
exit /b %ERRORLEVEL%
