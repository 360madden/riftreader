@echo off
setlocal EnableExtensions
python "%~dp0turn_rate_promotion_apply.py" %*
exit /b %errorlevel%
