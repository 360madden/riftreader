@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

call "%~dp0cheatengine-exec.cmd" -LuaFile "%REPO_ROOT%\scripts\cheat-engine\RiftReaderProbe.lua"
exit /b %errorlevel%
