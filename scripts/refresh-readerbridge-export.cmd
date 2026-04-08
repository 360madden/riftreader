@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0refresh-readerbridge-export.ps1" %*
exit /b %errorlevel%
