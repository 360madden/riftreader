@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0run-actor-yaw-debug-scan.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
