@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

set "LUA_CODE=local ok, result = pcall(dofile, [[%REPO_ROOT%\scripts\cheat-engine\RiftReaderProbe.lua]]); if not ok then print(result) return 0 end if RiftReaderProbe == nil then return 0 end return RiftReaderProbe.attachAndPopulate() and 1 or 0"

call "%~dp0cheatengine-exec.cmd" -Code "%LUA_CODE%"
exit /b %errorlevel%
