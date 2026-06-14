@echo off
REM Launch the KDP Cover Editor web app and open it in the browser.
cd /d "%~dp0\.."
start "" http://127.0.0.1:5050
python CoverPage_sizer\app.py
pause
