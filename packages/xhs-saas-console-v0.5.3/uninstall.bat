@echo off
REM ============================================================
REM  xhs-saas-console (onefile) - uninstaller
REM ============================================================
setlocal
chcp 65001 >NUL
title xhs-saas-console uninstaller

set "APP_NAME=xhs-saas-console"
set "INSTALL_ROOT=%LOCALAPPDATA%\%APP_NAME%"

echo.
echo ============================================================
echo   %APP_NAME% uninstaller
echo   Will remove: %INSTALL_ROOT%
echo   Will remove: %INSTALL_ROOT%\runtime\  (extraction cache)
echo   Will remove: desktop + start-menu shortcuts
echo ============================================================
echo.
choice /C YN /M "Proceed?"
if errorlevel 2 ( echo Cancelled. & pause & exit /b 0 )

if exist "%USERPROFILE%\Desktop\xhs-saas-console.lnk" del /F /Q "%USERPROFILE%\Desktop\xhs-saas-console.lnk"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\xhs-saas-console" rmdir /S /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\xhs-saas-console"

if exist "%INSTALL_ROOT%" (
    echo Removing %INSTALL_ROOT% ...
    rmdir /S /Q "%INSTALL_ROOT%"
    echo   done.
) else ( echo Install dir not found - already clean. )

echo.
echo Uninstalled.
pause
endlocal
