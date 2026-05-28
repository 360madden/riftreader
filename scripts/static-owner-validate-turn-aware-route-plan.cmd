@echo off
setlocal
cd /d "%~dp0\.."
python scripts\static_owner_turn_aware_route_plan.py --validate-plan-summary-json %*
