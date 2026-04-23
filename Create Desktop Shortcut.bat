@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%Start Organizer.bat"
set "ICON_PATH=%SCRIPT_DIR%icon.ico"
set "SHORTCUT_NAME=Folders Organizer Pro.lnk"
set "DESKTOP_PATH=%USERPROFILE%\Desktop"

echo.
echo ==========================================
echo      Creating Desktop Shortcut...
echo ==========================================
echo.

:: Create VBScript to generate shortcut
set "VBS_FILE=%TEMP%\CreateShortcut.vbs"
echo Set oWS = CreateObject("WScript.Shell") > "%VBS_FILE%"
echo sLinkFile = "%DESKTOP_PATH%\%SHORTCUT_NAME%" >> "%VBS_FILE%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_FILE%"
echo oLink.TargetPath = "cmd.exe" >> "%VBS_FILE%"
echo oLink.Arguments = "/c """ ^& "%EXE_PATH%" ^& """" >> "%VBS_FILE%"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%VBS_FILE%"
echo oLink.Description = "Professional Folders Organizer" >> "%VBS_FILE%"
echo oLink.IconLocation = "%ICON_PATH%" >> "%VBS_FILE%"
echo oLink.Save >> "%VBS_FILE%"

:: Execute VBScript
cscript //nologo "%VBS_FILE%"
del "%VBS_FILE%"

echo [OK] Shortcut created on your Desktop!
echo.
pause
exit
