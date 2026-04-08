@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0post-rift-thread-command.ps1" %*
exit /b %errorlevel%
