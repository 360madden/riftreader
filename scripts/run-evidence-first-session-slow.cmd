:: Version: 1.0.0
:: TotalCharacters: 504
:: Purpose: Launch the slower evidence-first runner from cmd without assuming pwsh is installed.

@echo off
setlocal EnableExtensions
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0run-evidence-first-session-slow.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0run-evidence-first-session-slow.ps1" %*
)
exit /b %errorlevel%

:: End of script
