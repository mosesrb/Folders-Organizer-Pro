@echo off
setlocal
echo ==========================================
echo    Folders Organizer Pro - Setup
echo ==========================================
echo.

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b
)

echo [1/4] Installing Python dependencies...
python -m pip install pywebview >nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install pywebview.
    pause
    exit /b
)

:: 2. Check for UI dependencies
if not exist "ui\package.json" (
    echo [ERROR] UI folder not found.
    pause
    exit /b
)

echo [2/4] Installing UI dependencies (npm)...
cd ui
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed.
    echo Make sure you have Node.js and npm installed.
    pause
    exit /b
)

echo [3/4] Building UI...
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] UI build failed.
    pause
    exit /b
)
cd ..

echo [4/4] Finalizing...
echo.
echo ==========================================
echo    Setup Complete!
echo    Run 'python organizer.py' to start.
echo ==========================================
echo.
pause
