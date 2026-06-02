@echo off
setlocal
cd /d "%~dp0.."
python scripts\dashboard_live_data.py %*
