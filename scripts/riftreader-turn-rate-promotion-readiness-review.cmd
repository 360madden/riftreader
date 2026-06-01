@echo off
setlocal EnableExtensions
python "%~dp0turn_rate_promotion_readiness_review.py" %*
exit /b %errorlevel%
