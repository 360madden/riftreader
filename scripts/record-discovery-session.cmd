@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0record-discovery-session.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
