@echo off
setlocal EnableExtensions
python "%~dp0static_owner_nav_route_run.py" --report-route-run-summary-json %*
exit /b %errorlevel%
