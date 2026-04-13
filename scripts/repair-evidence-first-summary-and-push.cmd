:: Version: 1.0.0
:: TotalCharacters: 530
:: Purpose: Launch the automated evidence-first summary repair workflow from cmd without assuming pwsh is installed.

@echo off
setlocal EnableExtensions
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0repair-evidence-first-summary-and-push.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0repair-evidence-first-summary-and-push.ps1" %*
)
exit /b %errorlevel%

:: End of script
