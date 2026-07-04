@echo off
title 实时湖仓分析项目 - 一键启动
cd /d "%~dp0.."
echo ====================================
echo   实时湖仓分析项目 - 一键启动
echo ====================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\startup.ps1"
echo.
echo 按任意键退出...
pause >nul
