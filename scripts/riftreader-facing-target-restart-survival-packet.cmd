@echo off
setlocal
cd /d "%~dp0\.."
python scripts\facing_target_restart_survival_packet.py %*
