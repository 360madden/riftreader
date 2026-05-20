@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\sensitive_artifact_scan.py %*
exit /b %ERRORLEVEL%
