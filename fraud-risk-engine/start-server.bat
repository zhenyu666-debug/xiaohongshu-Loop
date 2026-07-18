@echo off
REM fraud-risk-engine startup script
REM Run this from the fraud-risk-engine/ directory.
REM
REM Usage:
REM   start-server.bat           # default port 8765
REM   start-server.bat 8888      # custom port
setlocal

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8765"

cd /d "%~dp0"

echo [fraud-risk-engine] Starting server on port %PORT% ...
echo.
echo    http://localhost:%PORT%/ui/
echo    http://localhost:%PORT%/api/health
echo.
echo Press Ctrl+C to stop.
echo.

python -c "import sys; sys.path.insert(0, '.'); import uvicorn; uvicorn.run('app.api:app', host='0.0.0.0', port=%PORT%, log_level='info')"

endlocal
