@echo off
setlocal EnableExtensions
python "%~dp0navigation_sequence_summary_contract.py" %*
exit /b %errorlevel%
