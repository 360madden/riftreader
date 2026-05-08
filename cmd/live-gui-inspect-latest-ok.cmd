@echo off
cd /d "C:\RIFT MODDING\RiftReader"
python scripts\live_test_gui.py --latest --inspect-progress --fail-on-warning --require-ok-run %*
