@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "ADDON_ROOT=%REPO_ROOT%\addon"

if not exist "%ADDON_ROOT%" (
  echo [ERROR] Addon source root was not found: "%ADDON_ROOT%"
  exit /b 1
)

set "LUAC_EXE="
for /f "delims=" %%I in ('where luac 2^>nul') do if not defined LUAC_EXE set "LUAC_EXE=%%I"

if not defined LUAC_EXE (
  echo [ERROR] luac.exe was not found on PATH.
  echo         Install Lua or add luac.exe to PATH, then re-run this script.
  exit /b 1
)

set /a ADDON_COUNT=0

for /d %%D in ("%ADDON_ROOT%\*") do (
  if exist "%%~fD\main.lua" (
    set /a ADDON_COUNT+=1
    echo [CHECK] "%%~fD\main.lua"
    "%LUAC_EXE%" -p "%%~fD\main.lua"
    if errorlevel 1 exit /b !errorlevel!
  )
)

if !ADDON_COUNT! EQU 0 (
  echo [ERROR] No addon directories with main.lua were found under "%ADDON_ROOT%".
  exit /b 1
)

echo [OK] Lua syntax validated for !ADDON_COUNT! addon(s).
exit /b 0
