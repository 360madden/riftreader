@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0test-player-movement-stimulus.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
