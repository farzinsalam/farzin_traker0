@echo off
title BottleVision AI - Live Web Streamer
set "PATH=C:\Program Files\Git\cmd;C:\Program Files\Git\bin;%PATH%"
cd /d "%~dp0"

echo ====================================================================
echo        BOTTLEVISION AI: ANTI-THEFT GUARDIAN WEB SERVER
echo ====================================================================
echo.
echo Starting Python Flask Server on http://localhost:5000 ...
echo Connecting to free OpenSSH tunnel for public HTTPS web link...
echo.

start http://localhost:5000
.venv\Scripts\python.exe web_app.py

pause
