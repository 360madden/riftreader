@echo off
setlocal EnableExtensions
python "%~dp0static_owner_nav_route_run.py" %*
exit /b %errorlevel%
