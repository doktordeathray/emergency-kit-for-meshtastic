@echo off
title Emergency Kit for Meshtastic
rem Double-click me on Windows.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0_system\launcher.ps1"
if errorlevel 1 pause
