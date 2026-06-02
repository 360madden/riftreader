@echo off
setlocal EnableExtensions
python "%~dp0navigation_consumer_demo.py" %*
exit /b %errorlevel%
