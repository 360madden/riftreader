@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0capture-player-source-accessor-family.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
