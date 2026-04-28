@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0write-nameplate-replacement-readiness-checklist.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
