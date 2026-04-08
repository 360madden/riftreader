@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

dotnet run --project "%REPO_ROOT%\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- %*
exit /b %errorlevel%
