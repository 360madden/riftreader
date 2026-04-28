@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0write-nameplate-artifact-audit-report.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
