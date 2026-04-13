:: Version: 1.0.0
:: TotalCharacters: 445
:: Purpose: Launch the evidence-first RiftReader session workflow from cmd without assuming pwsh is installed.

@echo off
setlocal EnableExtensions
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0run-evidence-first-session.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0run-evidence-first-session.ps1" %*
)
exit /b %errorlevel%

:: End of script
