@echo off
setlocal EnableExtensions

set "SCRIPT_PATH=%RIFTREADER_PS1%"
if not defined SCRIPT_PATH (
  echo [RiftReader] Missing PowerShell script path.
  exit /b 2
)

set "PWSH_EXE="
where /q pwsh && set "PWSH_EXE=pwsh"
if not defined PWSH_EXE if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"

if not defined PWSH_EXE (
  echo [RiftReader] PowerShell 7+ ^(pwsh^) is required for repo scripts.
  echo [RiftReader] Windows PowerShell 5.1 is no longer the default repo shell.
  exit /b 1
)

"%PWSH_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%" %*
exit /b %errorlevel%
