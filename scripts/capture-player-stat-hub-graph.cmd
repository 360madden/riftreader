@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "POWERSHELL_EXE=pwsh"
where /q "%POWERSHELL_EXE%" || set "POWERSHELL_EXE=powershell"

"%POWERSHELL_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%capture-player-stat-hub-graph.ps1" %*
exit /b %ERRORLEVEL%
