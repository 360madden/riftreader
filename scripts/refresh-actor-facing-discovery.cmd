@echo off
setlocal
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0refresh-actor-facing-discovery.ps1" %*
exit /b %errorlevel%
