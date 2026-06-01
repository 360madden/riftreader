@echo off
setlocal
cd /d "%~dp0\.."
python scripts\facing_target_three_pose_gate.py %*
