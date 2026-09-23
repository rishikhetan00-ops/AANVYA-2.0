@echo off
title [AANVYA / JARVIS - DEV TESTING SANDBOX]
echo ========================================================
echo  Starting AANVYA / JARVIS in DEV / EXPERIMENTAL MODE
echo  All changes here are isolated and will NOT affect Main.
echo ========================================================
cd /d "%~dp0"
python main.py
pause
