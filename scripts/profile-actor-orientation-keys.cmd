@echo off
setlocal EnableExtensions
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0profile-actor-orientation-keys.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0profile-actor-orientation-keys.ps1" %*
)
exit /b %errorlevel%
