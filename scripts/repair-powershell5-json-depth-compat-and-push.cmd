:: Version: 1.0.0
:: TotalCharacters: 541
:: Purpose: Launch the PowerShell 5 JSON depth compatibility repair workflow from cmd without assuming pwsh is installed.

@echo off
setlocal EnableExtensions
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0repair-powershell5-json-depth-compat-and-push.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0repair-powershell5-json-depth-compat-and-push.ps1" %*
)
exit /b %errorlevel%

:: End of script
