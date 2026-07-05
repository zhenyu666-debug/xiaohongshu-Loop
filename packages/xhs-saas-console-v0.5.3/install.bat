@echo off
REM ============================================================
REM  xhs-saas-console v0.5.3 (onefile) - one-click installer
REM  Copies SINGLE .exe (195 MB) to %LOCALAPPDATA% + shortcuts.
REM ============================================================
setlocal EnableDelayedExpansion
chcp 65001 >NUL
title xhs-saas-console onefile installer v0.5.3

set "APP_NAME=xhs-saas-console"
set "APP_VERSION=0.5.3"
set "INSTALL_ROOT=%LOCALAPPDATA%\%APP_NAME%"
set "RUNTIME_DIR=%INSTALL_ROOT%\runtime"
set "SOURCE_DIR=%~dp0"

echo.
echo ============================================================
echo   %APP_NAME% v%APP_VERSION% (onefile build)
echo   Source : %SOURCE_DIR%
echo   Target : %INSTALL_ROOT%
echo   Note   : This is a SINGLE-FILE build (195 MB).
echo            No _internal/, no extra files needed.
echo ============================================================
echo.

where powershell >NUL 2>&1
if errorlevel 1 (
    echo [ERR] PowerShell not found.  Need PS 5+.
    pause & exit /b 1
)

if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%"
if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%"
echo [1/3] Created install/runtime dirs.

echo [2/3] Copying xhs-saas-console.exe ...  (single 195 MB file, ~30-60s)
copy /Y "%SOURCE_DIR%xhs-saas-console.exe" "%INSTALL_ROOT%\xhs-saas-console.exe" >NUL
if errorlevel 1 (
    echo [ERR] Copy failed.
    pause & exit /b 2
)
copy /Y "%SOURCE_DIR%manifest.json" "%INSTALL_ROOT%\manifest.json" >NUL
copy /Y "%SOURCE_DIR%README.md" "%INSTALL_ROOT%\README.md" >NUL
echo       done.

echo [3/3] Creating shortcuts...
powershell -NoProfile -Command "$s = (New-Object -COM WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\xhs-saas-console.lnk'); $s.TargetPath = '%INSTALL_ROOT%\xhs-saas-console.exe'; $s.WorkingDirectory = '%INSTALL_ROOT%'; $s.IconLocation = '%INSTALL_ROOT%\xhs-saas-console.exe,0'; $s.Description = 'xhs-saas-console v%APP_VERSION%'; $s.Save()"

set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\xhs-saas-console"
if not exist "%START_MENU%" mkdir "%START_MENU%"
powershell -NoProfile -Command "$s = (New-Object -COM WScript.Shell).CreateShortcut('%START_MENU%\xhs-saas-console.lnk'); $s.TargetPath = '%INSTALL_ROOT%\xhs-saas-console.exe'; $s.WorkingDirectory = '%INSTALL_ROOT%'; $s.IconLocation = '%INSTALL_ROOT%\xhs-saas-console.exe,0'; $s.Description = 'xhs-saas-console v%APP_VERSION%'; $s.Save()" >NUL 2>&1

echo.
echo ============================================================
echo   Installation complete.
echo.
echo   Launch  :  Double-click the desktop icon, or run:
echo              "%INSTALL_ROOT%\xhs-saas-console.exe"
echo   Status  :  http://127.0.0.1:8765
echo   GUI     :  http://127.0.0.1:8766  (auto-opens in WebView2)
echo   First launch: 2-4s  (extracts python+qt to runtime/)
echo   Subsequent :  1-2s
echo   Uninstall :  run uninstall.bat in %INSTALL_ROOT%
echo ============================================================
echo.
pause
endlocal
