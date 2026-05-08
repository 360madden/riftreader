@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

python "%REPO_ROOT%\scripts\summarize_actor_yaw_discovery.py" %*
exit /b %errorlevel%
