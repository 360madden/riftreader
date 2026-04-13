:: Version: 1.0.0
:: TotalCharacters: 468
:: Purpose: Launch the promising actor-orientation lead capture workflow from cmd without assuming pwsh is installed.

@echo off
setlocal EnableExtensions
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0capture-promising-orientation-lead.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0capture-promising-orientation-lead.ps1" %*
)
exit /b %errorlevel%

:: End of script
