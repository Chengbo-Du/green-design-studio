@echo off
title GDS Installer
echo.
echo ----------------------------------------
echo   Green Design Studio Installer
echo ----------------------------------------
echo.

REM Try python on PATH first
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Found Python on PATH
    python install.py
    goto end
)

REM Try py launcher
py --version >nul 2>&1
if %errorlevel% == 0 (
    echo Found Python via py launcher
    py install.py
    goto end
)

REM Search AppData using USERPROFILE (handles domain accounts)
setlocal enabledelayedexpansion
for %%V in (313 312 311 310 39) do (
    set PY=%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe
    if exist "!PY!" (
        echo Found Python %%V
        "!PY!" install.py
        goto end
    )
)

REM Try Microsoft Store Python
set WSPY=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe
if exist "%WSPY%" (
    echo Found Python in WindowsApps
    "%WSPY%" install.py
    goto end
)

REM Nothing found
echo.
echo Python not found on this machine.
echo Please install Python 3.9+ from python.org
echo During install, CHECK "Add Python to PATH"
echo Then run install.bat again.
echo.

:end
pause