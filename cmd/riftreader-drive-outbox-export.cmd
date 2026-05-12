@echo off
REM Version: riftreader-drive-outbox-export-launcher-v0.2.0
REM Total-Character-Count: 271
REM Purpose: Dumb launcher for the Python RiftReader Drive outbox export helper.

cd /d "C:\RIFT MODDING\RiftReader"
python scripts\riftreader_drive_outbox_export.py %*

REM End of script.
