@echo off
setlocal
cd /d "%~dp0\.."
python scripts\static_owner_facing_discovery.py route --json %*
