@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building ow_guard.exe...
pyinstaller --onefile --windowed --name ow_guard --icon=NONE ow_guard.py

echo.
echo Done! Your exe is at: dist\ow_guard.exe
pause
