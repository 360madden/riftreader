@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_play_executor_gate.py %*
exit /b %ERRORLEVEL%
