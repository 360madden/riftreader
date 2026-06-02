@echo off
setlocal
cd /d "%~dp0\.."
python scripts\postupdate_static_access_chain.py %*
exit /b %ERRORLEVEL%
