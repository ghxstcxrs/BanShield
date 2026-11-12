@echo off
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
  python -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 goto failed
  goto success
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 goto failed
  goto success
)
echo Install Python first, then run this setup again.
goto finish
:failed
echo Setup did not finish. Keep the error above for troubleshooting.
goto finish
:success
echo Setup complete. You can now use Open BanShield.bat.
:finish
pause
