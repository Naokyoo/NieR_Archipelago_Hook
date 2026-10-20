@echo off
title NieR: Automata - Archipelago MultiWorld Bridge
cd /d "%~dp0"
echo =========================================================
echo   NieR: Automata - Archipelago MultiWorld Bridge
echo =========================================================
echo.
rem The release ships its own Python in the "python" folder. Without it (running from the sources),
rem use the installed Python and install the packages the bridge needs.
set "PY=python\python.exe"
if not exist "%PY%" set "PY=python"
if "%PY%"=="python" if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not exist "python\python.exe" (
    "%PY%" --version >nul 2>&1
    if errorlevel 1 (
        echo [-] The "python" folder is missing. Copy everything from the zip's "NieRAutomata folder"
        echo     into the game folder again.
        pause
        exit /b 1
    )
    "%PY%" -c "import websockets, certifi" >nul 2>&1
    if errorlevel 1 (
        echo [*] Installing the 'websockets' and 'certifi' Python packages...
        "%PY%" -m pip install --user websockets certifi
    )
)
"%PY%" nier_archipelago_bridge.py
pause
