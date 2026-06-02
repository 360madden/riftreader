@echo off
setlocal EnableExtensions
python "%~dp0navigation_waypoint_readiness.py" %*
exit /b %errorlevel%
