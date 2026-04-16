@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "SOURCE_ROOT=%REPO_ROOT%\addon"

if not exist "%SOURCE_ROOT%" (
  echo [ERROR] Addon source root was not found: "%SOURCE_ROOT%"
  exit /b 1
)

set "ADDONS_ROOTS="

if defined RIFT_ADDONS_DIR (
  call :AddRootsFromList "%RIFT_ADDONS_DIR%"
) else (
  call :AddRoot "%USERPROFILE%\OneDrive\Documents\RIFT\Interface\AddOns"
  call :AddRoot "%USERPROFILE%\Documents\RIFT\Interface\AddOns"
  if defined OneDrive call :AddRoot "%OneDrive%\Documents\RIFT\Interface\AddOns"
)

if not defined ADDONS_ROOTS (
  echo [ERROR] Could not locate any Rift Interface\AddOns folder.
  echo         Set RIFT_ADDONS_DIR to one or more AddOns roots and re-run.
  exit /b 1
)

set /a ADDON_COUNT=0
set /a ROOT_COUNT=0
set /a DEPLOYMENT_COUNT=0

for %%R in ("%ADDONS_ROOTS:|=" "%") do (
  set /a ROOT_COUNT+=1
)

for /d %%D in ("%SOURCE_ROOT%\*") do (
  if exist "%%~fD\main.lua" (
    set /a ADDON_COUNT+=1
    for %%R in ("%ADDONS_ROOTS:|=" "%") do (
      call :DeployAddon "%%~fD" "%%~nxD" "%%~fR"
      if errorlevel 1 exit /b !errorlevel!
      set /a DEPLOYMENT_COUNT+=1
    )
  ) else if exist "%%~fD\RiftAddon.toc" (
    set /a ADDON_COUNT+=1
    for %%R in ("%ADDONS_ROOTS:|=" "%") do (
      call :DeployAddon "%%~fD" "%%~nxD" "%%~fR"
      if errorlevel 1 exit /b !errorlevel!
      set /a DEPLOYMENT_COUNT+=1
    )
  )
)

if !ADDON_COUNT! EQU 0 (
  echo [ERROR] No addon directories with main.lua or RiftAddon.toc were found under "%SOURCE_ROOT%".
  exit /b 1
)

echo [OK] Deployment completed for !ADDON_COUNT! addon(s) across !ROOT_COUNT! addon root(s) (!DEPLOYMENT_COUNT! copy operations).
exit /b 0

:AddRootsFromList
set "ROOT_LIST=%~1"
if not defined ROOT_LIST exit /b 0
set "ROOT_LIST=%ROOT_LIST:;=" "%"
for %%R in ("%ROOT_LIST%") do (
  call :AddRoot "%%~R"
)
exit /b 0

:AddRoot
set "CANDIDATE=%~1"
if not defined CANDIDATE exit /b 0
if not exist "%CANDIDATE%" exit /b 0
if not defined ADDONS_ROOTS (
  set "ADDONS_ROOTS=%~f1"
  exit /b 0
)
for %%R in ("%ADDONS_ROOTS:|=" "%") do (
  if /I "%%~fR"=="%~f1" exit /b 0
)
set "ADDONS_ROOTS=%ADDONS_ROOTS%|%~f1"
exit /b 0

:DeployAddon
set "SOURCE_DIR=%~1"
set "ADDON_NAME=%~2"
set "TARGET_ROOT=%~3"
set "TARGET_DIR=%TARGET_ROOT%\%ADDON_NAME%"

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Could not create the target folder: "%TARGET_DIR%"
  exit /b 1
)

robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /NFL /NDL /NJH /NJS /NC /NS /NP
set "ROBOCOPY_EXIT=%errorlevel%"

if %ROBOCOPY_EXIT% GEQ 8 (
  echo [ERROR] Addon deployment failed for "%ADDON_NAME%" with robocopy exit code %ROBOCOPY_EXIT%.
  exit /b %ROBOCOPY_EXIT%
)

echo [OK] Addon deployed to "%TARGET_DIR%".
exit /b 0
