@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\fast_world_launch.py %*
exit /b %ERRORLEVEL%
