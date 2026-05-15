@echo off
cd /d "%~dp0\.."
python "%~dp0recover_current_pid_coord_anchor_fast.py" %*
