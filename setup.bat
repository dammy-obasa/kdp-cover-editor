@echo off
REM Install Python dependencies for CoverPage_sizer.
cd /d "%~dp0"

echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo Installing CoverPage_sizer requirements...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Setup complete.
pause
exit /b 0

:error
echo.
echo Setup failed. See the error above.
pause
exit /b 1
