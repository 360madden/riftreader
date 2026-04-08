@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0cheatengine-capture-best.ps1" %*
exit /b %errorlevel%
