@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0post-rift-key.ps1" %*
exit /b %errorlevel%
