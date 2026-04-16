@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0capture-player-owner-graph.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
