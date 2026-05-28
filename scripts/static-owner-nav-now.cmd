@echo off
setlocal
cd /d "%~dp0\.."
python scripts\static_owner_facing_discovery.py state --samples 3 --interval-seconds 0.1 --json %*
