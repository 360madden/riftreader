@echo off
setlocal
set "RIFTREADER_PS1=%~dp0assert-actor-facing-truth.ps1"
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%RIFTREADER_PS1%" %*
exit /b %ERRORLEVEL%
