@echo off
setlocal
cd /d "%~dp0"

echo.
echo ==========================================
echo        Folders Organizer Pro Launcher
echo ==========================================
echo.

:: Simple direct launch
python organizer.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [X] Error: The application crashed or failed to start.
    echo [!] Please try running "python organizer.py" manually in this folder.
    pause
)

exit
