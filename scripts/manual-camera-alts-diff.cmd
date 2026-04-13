@echo off
REM Manual camera Alt-S diff - reads memory, waits for YOU to press Alt-S in RIFT, reads again, diffs
pwsh -ExecutionPolicy Bypass -File "%~dp0manual-camera-alts-diff.ps1" %*
