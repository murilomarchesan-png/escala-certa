@echo off
cd /d "%~dp0"
python apps\api\server.py --open
if errorlevel 1 pause
