@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0measure-csharp-sendinput-current.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
