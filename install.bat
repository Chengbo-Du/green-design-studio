@echo off
title GDS Installer
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Green Design Studio Installer
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM Try python on PATH first
python --version >nul 2>&1
if %errorlevel% == 0 (
    python install.py
    goto end
)

REM Try py launcher
py --version >nul 2>&1
if %errorlevel% == 0 (
    py install.py
    goto end
)

REM Try Ladybug Tools Python directly
if exist "%USERPROFILE%\ladybug_tools\python\python.exe" (
    "%USERPROFILE%\ladybug_tools\python\python.exe" install.py
    goto end
)

REM Try common Python locations
setlocal enabledelayedexpansion
for %%V in (313 312 311 310 39) do (
    set PY=%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe
    if exist "!PY!" (
        "!PY!" install.py
        goto end
    )
)

REM Nothing found
echo ❌ Python not found on this computer
echo.
echo Please install Python first:
echo 1. Go to python.org/downloads
echo 2. Download Python 3.9 or newer
echo 3. During install CHECK "Add Python to PATH"
echo 4. Run install.bat again
echo.

:end
pause