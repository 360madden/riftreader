@echo off
setlocal EnableExtensions
python "%~dp0static_owner_turn_stimulus_capture.py" %*
exit /b %errorlevel%
