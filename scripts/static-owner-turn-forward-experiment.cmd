@echo off
setlocal
cd /d "%~dp0\.."
python scripts\static_owner_turn_forward_experiment.py %*
