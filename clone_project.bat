@echo off
setlocal
echo ==========================================
echo    Folders Organizer Pro - Cloner
echo ==========================================
echo.

set REPO_URL=https://github.com/mosesrb/Folders-Organizer-Pro.git

echo [1/3] Cloning Repository...
git clone %REPO_URL% FoldersOrganizerPro
if %errorlevel% neq 0 (
    echo [ERROR] Clone failed. Make sure git is installed and you have access.
    pause
    exit /b
)

cd FoldersOrganizerPro

echo [2/3] Repository Cloned. running Setup...
call setup.bat

echo [3/3] Done! Folders Organizer Pro is ready.
echo.
pause
