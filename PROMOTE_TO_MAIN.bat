@echo off
title [PROMOTE DEV CHANGES TO PRODUCTION MAIN]
echo ========================================================
echo  Promoting Dev Changes to Stable Main App...
echo ========================================================
cd /d "%~dp0"
git add -A
git diff-index --quiet HEAD || git commit -m "Promote verified features from dev to main"
git push origin dev
echo.
echo Updating Main directory...
cd /d "C:\Users\BIT\OneDrive\Desktop\Mark-LIV-main\Mark-LIV-main"
git checkout main
git pull origin dev
git push origin main
echo.
echo ========================================================
echo  SUCCESS! Dev updates have been merged into Main.
echo ========================================================
pause
