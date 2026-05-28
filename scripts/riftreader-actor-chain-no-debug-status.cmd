@echo off
setlocal
cd /d "%~dp0\.."
python scripts\actor_chain_no_debug_status.py %*
exit /b %ERRORLEVEL%
