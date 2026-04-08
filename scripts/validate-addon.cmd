@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "ADDON_DIR=%REPO_ROOT%\addon\RiftReaderValidator"

if not exist "%ADDON_DIR%\main.lua" (
  echo [ERROR] Addon source was not found: "%ADDON_DIR%"
  exit /b 1
)

set "LUAC_EXE="
for /f "delims=" %%I in ('where luac 2^>nul') do if not defined LUAC_EXE set "LUAC_EXE=%%I"

if not defined LUAC_EXE (
  echo [ERROR] luac.exe was not found on PATH.
  echo         Install Lua or add luac.exe to PATH, then re-run this script.
  exit /b 1
)

echo [CHECK] "%ADDON_DIR%\main.lua"
"%LUAC_EXE%" -p "%ADDON_DIR%\main.lua"
if errorlevel 1 exit /b %errorlevel%

echo [OK] Lua syntax validated.
exit /b 0
