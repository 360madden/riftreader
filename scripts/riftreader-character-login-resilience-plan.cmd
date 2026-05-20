@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_resilience_plan.py %*
exit /b %ERRORLEVEL%
