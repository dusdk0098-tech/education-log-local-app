@echo off
cd /d "%~dp0"
if exist "%~dp0PEDIT-EDU.exe" (
  start "" "%~dp0PEDIT-EDU.exe"
  exit /b
)
py -3 server.py
