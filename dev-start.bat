@echo off
chcp 65001 >nul
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0dev-start.ps1" %*
exit /b %errorlevel%
