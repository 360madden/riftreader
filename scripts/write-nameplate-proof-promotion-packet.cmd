@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0write-nameplate-proof-promotion-packet.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
