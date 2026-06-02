@echo off
setlocal EnableExtensions
python "%~dp0navigation_schema_validate.py" %*
exit /b %errorlevel%
