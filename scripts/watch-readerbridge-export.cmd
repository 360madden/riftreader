@echo off
setlocal EnableExtensions

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch-readerbridge-export.ps1" %*
exit /b %errorlevel%
