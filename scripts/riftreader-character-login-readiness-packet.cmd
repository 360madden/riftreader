@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_readiness_packet.py %*
exit /b %ERRORLEVEL%
