@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_supervisor.py %*
exit /b %ERRORLEVEL%
