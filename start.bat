@echo off
chcp 65001 >nul
title 闲鱼助手 - 安全开发启动器
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0dev-start.ps1" %*
exit /b %errorlevel%
