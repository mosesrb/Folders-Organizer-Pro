@echo off
setlocal
echo ==========================================
echo    Folders Organizer Pro - Portable Build
echo ==========================================
echo.

:: 1. Build UI
echo [1/3] Building UI with Vite...
cd ui
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] UI build failed.
    pause
    exit /b
)
cd ..

:: 2. Check PyInstaller
echo [2/3] Verifying PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

:: 3. Build Portable EXE
echo [3/3] Compiling standalone executable...
python -m PyInstaller FoldersOrganizerPro.spec --noconfirm --clean
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b
)

echo.
echo =======================================================
echo  Build Complete!
echo  Portable Executable: dist\FoldersOrganizerPro_Portable.exe
echo =======================================================
echo.
pause
