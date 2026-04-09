@echo off
setlocal

set "PWSH="
where pwsh >nul 2>nul && set "PWSH=pwsh"
if not defined PWSH set "PWSH=powershell"

"%PWSH%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0capture-player-trace-cluster.ps1" %*
exit /b %errorlevel%
