@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0print-live-actor-yaw.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
