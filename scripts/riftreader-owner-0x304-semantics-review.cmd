@echo off
setlocal EnableExtensions
python "%~dp0owner_0x304_semantics_review.py" %*
exit /b %errorlevel%
