@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "POWERSHELL_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if exist "%POWERSHELL_EXE%" (
  "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%trace-player-selector-owner.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%trace-player-selector-owner.ps1" %*
)
