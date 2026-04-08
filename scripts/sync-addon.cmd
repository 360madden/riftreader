@echo off
setlocal EnableExtensions

call "%~dp0validate-addon.cmd"
if errorlevel 1 exit /b %errorlevel%

call "%~dp0deploy-addon.cmd"
if errorlevel 1 exit /b %errorlevel%

exit /b 0
