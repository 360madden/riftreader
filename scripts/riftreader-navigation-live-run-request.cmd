@echo off
cd /d "%~dp0\.."
python scripts\navigation_live_run_request.py %*
