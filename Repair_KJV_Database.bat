@echo off
cd /d "%~dp0"
echo Bible Display Pro - KJV database repair
where py >nul 2>nul
if not errorlevel 1 (
  py -3 setup_kjv.py
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is not installed. Install it from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  python setup_kjv.py
)
pause
