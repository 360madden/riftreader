@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0cheatengine-exec.ps1" %*
exit /b %errorlevel%
