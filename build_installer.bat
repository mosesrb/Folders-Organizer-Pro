@echo off
setlocal
echo ==========================================
echo    Folders Organizer Pro - Installer Build
echo ==========================================
echo.

:: 1. Ensure Portable EXE exists
if not exist "dist\FoldersOrganizerPro_Portable.exe" (
    echo [!] Portable EXE not found. Building it first...
    call build_portable.bat
)

:: 2. Find Inno Setup Compiler (ISCC.exe)
set "ISCC="
where ISCC.exe >nul 2>&1
if %errorlevel% equ 0 set "ISCC=ISCC.exe"

if "%ISCC%"=="" (
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    )
)

if "%ISCC%"=="" (
    if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
    )
)

if "%ISCC%"=="" (
    echo [!] Inno Setup Compiler (ISCC.exe) was not found on your system.
    echo.
    echo To build the Setup.exe installer:
    echo  1. Download and install Inno Setup (free) from: https://jrsoftware.org/isdl.php
    echo  2. Re-run this script, or open 'installer.iss' in Inno Setup and click 'Compile'.
    echo.
    echo Your standalone portable executable is already available at:
    echo  dist\FoldersOrganizerPro_Portable.exe
    echo.
    pause
    exit /b
)

:: 3. Compile Installer
echo Compiling Windows Setup Installer with Inno Setup...
"%ISCC%" installer.iss
if %errorlevel% neq 0 (
    echo [ERROR] Inno Setup compilation failed.
    pause
    exit /b
)

echo.
echo =======================================================
echo  Installer Build Complete!
echo  Setup File: dist\FoldersOrganizerPro_Setup.exe
echo =======================================================
echo.
pause
