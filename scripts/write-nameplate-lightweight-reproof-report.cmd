@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0write-nameplate-lightweight-reproof-report.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
