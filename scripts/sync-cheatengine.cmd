@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

call "%REPO_ROOT%\scripts\generate-cheatengine-probe.cmd" %*
if errorlevel 1 exit /b %errorlevel%

call "%REPO_ROOT%\scripts\install-cheatengine-autorun.cmd"
exit /b %errorlevel%
