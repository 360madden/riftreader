@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

call "%REPO_ROOT%\scripts\run-reader.cmd" --process-name rift_x64 --cheatengine-probe --scan-context 192 --max-hits 8 %*
exit /b %errorlevel%
