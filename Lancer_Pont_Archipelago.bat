@echo off
title NieR: Automata - Archipelago MultiWorld Bridge
cd /d "%~dp0"
echo =========================================================
echo   NieR: Automata - Archipelago MultiWorld Bridge
echo =========================================================
echo.
set "PY=python"
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
"%PY%" --version >nul 2>&1
if errorlevel 1 (
    echo [-] Python 3 was not found. Install it from https://www.python.org/downloads/
    echo     and tick "Add python.exe to PATH" during the install.
    pause
    exit /b 1
)
"%PY%" -c "import websockets, certifi" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing the 'websockets' and 'certifi' Python packages...
    "%PY%" -m pip install --user websockets certifi
)
"%PY%" nier_archipelago_bridge.py
pause
