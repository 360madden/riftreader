@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "SOURCE_ROOT=%REPO_ROOT%\addon"

if not exist "%SOURCE_ROOT%" (
  echo [ERROR] Addon source root was not found: "%SOURCE_ROOT%"
  exit /b 1
)

set "ADDONS_ROOT="

if defined RIFT_ADDONS_DIR if exist "%RIFT_ADDONS_DIR%" set "ADDONS_ROOT=%RIFT_ADDONS_DIR%"
if not defined ADDONS_ROOT if exist "%USERPROFILE%\OneDrive\Documents\RIFT\Interface\AddOns" set "ADDONS_ROOT=%USERPROFILE%\OneDrive\Documents\RIFT\Interface\AddOns"
if not defined ADDONS_ROOT if exist "%USERPROFILE%\Documents\RIFT\Interface\AddOns" set "ADDONS_ROOT=%USERPROFILE%\Documents\RIFT\Interface\AddOns"
if not defined ADDONS_ROOT if defined OneDrive if exist "%OneDrive%\Documents\RIFT\Interface\AddOns" set "ADDONS_ROOT=%OneDrive%\Documents\RIFT\Interface\AddOns"

if not defined ADDONS_ROOT (
  echo [ERROR] Could not locate the Rift Interface\AddOns folder.
  echo         Set RIFT_ADDONS_DIR to the AddOns root and re-run.
  exit /b 1
)

set /a ADDON_COUNT=0

for /d %%D in ("%SOURCE_ROOT%\*") do (
  if exist "%%~fD\main.lua" (
    set /a ADDON_COUNT+=1
    set "TARGET_DIR=%ADDONS_ROOT%\%%~nxD"

    if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!" >nul 2>&1
    if errorlevel 1 (
      echo [ERROR] Could not create the target folder: "!TARGET_DIR!"
      exit /b 1
    )

    robocopy "%%~fD" "!TARGET_DIR!" /E /NFL /NDL /NJH /NJS /NC /NS /NP
    set "ROBOCOPY_EXIT=!errorlevel!"

    if !ROBOCOPY_EXIT! GEQ 8 (
      echo [ERROR] Addon deployment failed for "%%~nxD" with robocopy exit code !ROBOCOPY_EXIT!.
      exit /b !ROBOCOPY_EXIT!
    )

    echo [OK] Addon deployed to "!TARGET_DIR!".
  )
)

if !ADDON_COUNT! EQU 0 (
  echo [ERROR] No addon directories with main.lua were found under "%SOURCE_ROOT%".
  exit /b 1
)

echo [OK] Deployment completed for !ADDON_COUNT! addon(s).
exit /b 0
