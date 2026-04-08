@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0post-rift-command-ahk.ps1" %*
exit /b %errorlevel%
