@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_login_executor_contract.py %*
exit /b %ERRORLEVEL%
