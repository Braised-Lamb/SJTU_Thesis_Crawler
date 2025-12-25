@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting GUI application...
python gui_downloader.py
pause
