@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0open-x64dbg.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
