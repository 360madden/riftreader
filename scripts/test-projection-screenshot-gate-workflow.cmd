@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0test-projection-screenshot-gate-workflow.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
