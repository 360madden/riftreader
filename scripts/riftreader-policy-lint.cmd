@echo off
REM Version: riftreader-policy-lint-wrapper-v0.1.2
REM Total-Character-Count: 377
REM Purpose: Thin CMD launcher for Python-owned RiftReader policy lint helper; preserves backslashes literally and forwards all args.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\policy_lint.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
