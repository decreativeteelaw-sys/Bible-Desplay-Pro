@echo off
setlocal
cd /d "%~dp0"
title Bible Display Pro

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 was not found.
    echo Install Python from https://www.python.org/downloads/windows/
    echo During installation, enable Add Python to PATH.
    pause
    exit /b 1
  )
  set "PYTHON=python"
)

if not exist "data\kjv.json" (
  echo.
  echo The full KJV database is not in this folder yet.
  echo The first-time installer needs internet access.
  echo If you have a working copy, copy its data\kjv.json into this folder instead.
  echo.
  %PYTHON% setup_kjv.py
  if errorlevel 1 (
    echo.
    echo KJV setup did not complete. See the message above.
    pause
    exit /b 1
  )
)

%PYTHON% validate_kjv.py
if errorlevel 1 (
  echo.
  echo The KJV database is missing, incomplete, or invalid.
  echo Use Repair_KJV_Database.bat or copy a validated data\kjv.json into this folder.
  pause
  exit /b 1
)

if not exist "assets\fonts\fonts-installed.json" (
  echo.
  echo First-time font setup: downloading 20 open-licensed font families.
  echo This step needs internet once. Installed fonts will work offline afterward.
  %PYTHON% setup_fonts.py
  if errorlevel 1 (
    echo Font setup was interrupted. The app can still start with system fonts.
    echo You can retry later by running setup_fonts.py.
  )
)

start "Bible Display Pro Controller" "http://127.0.0.1:8765/index.html"
%PYTHON% server.py
pause
