@echo off
REM Automated camera Alt-S stimulus test
REM Uses SendInput key injection (requires focus)
REM Falls back to manual stimulus if key injection doesn't work
pwsh -ExecutionPolicy Bypass -File "%~dp0auto-camera-alts-diff.ps1" %*
