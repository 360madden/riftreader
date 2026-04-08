@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0smart-capture-player-family.ps1" %*
exit /b %errorlevel%
