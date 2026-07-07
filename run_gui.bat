@echo off
cd /d "%~dp0"
if exist "WorshipPPT.exe" (
    start "" "WorshipPPT.exe"
) else (
    python src\gui_app.py
)
