@echo off
cd /d "%~dp0"
if not exist "%~dp0app\audit_log.py" (
  echo BanShield's app folder is missing. Extract the complete program folder first.
  pause
  exit /b 1
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "BanShield" pythonw "%~dp0app\audit_log.py"
  exit /b 0
)
where pyw >nul 2>nul
if not errorlevel 1 (
  start "BanShield" pyw -3 "%~dp0app\audit_log.py"
  exit /b 0
)
echo Python was not found. Install Python, run Setup BanShield.bat, and try again.
pause
exit /b 1
