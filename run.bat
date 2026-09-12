@echo off
title BottleVision AI Launcher
echo ========================================================
echo       BottleVision AI - Bottle Detection System
echo ========================================================
echo.

:: Detect Python executable
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=".venv\Scripts\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    set PYTHON_EXE=python
)

echo Starting BottleVision AI GUI...
%PYTHON_EXE% main.py

if %errorlevel% neq 0 (
    echo.
    echo Application closed with an error.
    pause
)
