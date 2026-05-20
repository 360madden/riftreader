@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_screen_state.py %*
exit /b %ERRORLEVEL%
