@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

dotnet build "%REPO_ROOT%\RiftReader.slnx"
exit /b %errorlevel%
