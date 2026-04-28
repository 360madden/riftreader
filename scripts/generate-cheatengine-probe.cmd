@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

set "HAS_EXPLICIT_TARGET="
for %%A in (%*) do (
    if /I "%%~A"=="--pid" set "HAS_EXPLICIT_TARGET=1"
    if /I "%%~A"=="--process-name" set "HAS_EXPLICIT_TARGET=1"
)

if defined HAS_EXPLICIT_TARGET (
    call "%REPO_ROOT%\scripts\run-reader.cmd" --cheatengine-probe --scan-context 192 --max-hits 8 %*
) else (
    call "%REPO_ROOT%\scripts\run-reader.cmd" --process-name rift_x64 --cheatengine-probe --scan-context 192 --max-hits 8 %*
)
exit /b %errorlevel%
