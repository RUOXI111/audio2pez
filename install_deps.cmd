@echo off
REM audio2pez dependency installer launcher (bypasses PowerShell execution policy).
REM Keep this file ASCII-only: cmd.exe mangles non-ASCII lines even inside REM.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_deps.ps1"
