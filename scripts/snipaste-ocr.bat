@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0snipaste-ocr.ps1"
pause
