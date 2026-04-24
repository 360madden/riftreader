@echo off
setlocal EnableExtensions
set "RIFTREADER_PS1=%~dp0compare-nameplate-projection-proof-runs.ps1"
call "%~dp0_run-pwsh.cmd" %*
exit /b %errorlevel%
