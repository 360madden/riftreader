@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\launcher_inspection.py %*
exit /b %ERRORLEVEL%
