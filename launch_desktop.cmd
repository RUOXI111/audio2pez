@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo [ERROR] Local Python is missing: .venv\Scripts\python.exe
  echo Run this launcher from the original audio2pez folder.
  pause
  exit /b 1
)
if not exist "%~dp0desktop_app.py" (
  echo [ERROR] desktop_app.py is missing.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0desktop_app.py" %*
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
  echo.
  echo [ERROR] Desktop exited with code %APP_EXIT%.
  echo Diagnostics: .desktop\startup.log
  pause
)
exit /b %APP_EXIT%
