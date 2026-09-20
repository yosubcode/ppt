@echo off
cd /d "%~dp0"
echo Installing PyInstaller if needed...
python -m pip install pyinstaller
echo.
echo Building PPT.exe ...
python -m PyInstaller ppt.spec --distpath . --workpath build\pyinstaller --clean -y
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)
echo.
echo Done: %~dp0PPT.exe
echo.
echo Place PDFs in input\ and input2\ next to the exe, then double-click PPT.exe
pause
