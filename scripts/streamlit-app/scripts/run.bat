@echo off
REM Env Extractor launcher (Windows). Double-click this file.
REM It will: find Python 3.10+, create a .venv, install deps, launch the app.

setlocal enabledelayedexpansion

REM cd to the app directory regardless of how this was invoked.
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%.."
pushd "%APP_DIR%"

echo ------------------------------------------------------------
echo  Env Extractor
echo  app dir: %CD%
echo ------------------------------------------------------------

REM --- 1. Find Python ------------------------------------------------------
set "PYTHON_BIN="
for %%P in (python py python3) do (
    if not defined PYTHON_BIN (
        %%P --version >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=2 delims= " %%V in ('%%P --version 2^>^&1') do (
                set "VER=%%V"
                for /f "tokens=1,2 delims=." %%a in ("!VER!") do (
                    if "%%a"=="3" if %%b GEQ 10 set "PYTHON_BIN=%%P"
                )
            )
        )
    )
)

if not defined PYTHON_BIN (
    echo.
    echo ERROR: Python 3.10 or newer is required and we couldn't find it.
    echo.
    echo Install Python from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add Python to PATH" during install.
    echo Then double-click this file again.
    echo.
    pause
    exit /b 1
)

echo Using %PYTHON_BIN%
%PYTHON_BIN% --version

REM --- 2. Create venv ------------------------------------------------------
if not exist ".venv" (
    echo First run: creating local virtual environment in .venv ...
    %PYTHON_BIN% -m venv .venv
)

call .venv\Scripts\activate.bat

REM --- 3. Install deps -----------------------------------------------------
set "NEEDS_INSTALL=0"
if not exist ".venv\.installed" set "NEEDS_INSTALL=1"

if "%NEEDS_INSTALL%"=="1" (
    echo Installing dependencies (one-time, ~30 seconds)...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency install failed. Try running this file again.
        pause
        exit /b 1
    )
    echo. > .venv\.installed
)

REM --- 4. Launch -----------------------------------------------------------
echo.
echo Starting Env Extractor at http://localhost:8501
echo (Close this window to stop the app.)
echo.

start "" "http://localhost:8501"
streamlit run app.py --server.headless true --browser.gatherUsageStats false

popd
endlocal
