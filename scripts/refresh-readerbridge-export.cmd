@echo off
setlocal EnableExtensions

where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -ExecutionPolicy Bypass -File "%~dp0refresh-readerbridge-export.ps1" %*
) else (
  powershell -ExecutionPolicy Bypass -File "%~dp0refresh-readerbridge-export.ps1" %*
)
exit /b %errorlevel%
