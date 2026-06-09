@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0get-rift-window-targets.ps1" %*
exit /b %ERRORLEVEL%
