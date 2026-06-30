@echo off
cd /d "%~dp0\.."
python scripts\navigation_offline_simulator.py %*
