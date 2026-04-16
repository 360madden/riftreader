@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0smart-capture-player-family.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
