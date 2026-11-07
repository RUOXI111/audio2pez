@echo off
setlocal
set "GUI=%~dp0installer_gui.ps1"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%GUI%" (
  echo [ERROR] installer_gui.ps1 is missing. Extract the complete Audio2Phira package and try again.
  pause
  exit /b 1
)
if not exist "%PS%" (
  echo [ERROR] Windows PowerShell 5.1 is missing. Enable Windows PowerShell and try again.
  pause
  exit /b 1
)
"%PS%" -NoProfile -ExecutionPolicy Bypass -STA -File "%GUI%" %*
set "SETUP_EXIT=%ERRORLEVEL%"
if not "%SETUP_EXIT%"=="0" (
  echo [ERROR] The installer GUI could not start. See the error above.
  pause
)
exit /b %SETUP_EXIT%
