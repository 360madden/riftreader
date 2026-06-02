@echo off
setlocal EnableExtensions
python "%~dp0navigation_consumer_refresh.py" %*
exit /b %errorlevel%
