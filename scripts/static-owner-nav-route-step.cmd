@echo off
setlocal EnableExtensions
python "%~dp0static_owner_nav_route_step.py" %*
exit /b %errorlevel%
