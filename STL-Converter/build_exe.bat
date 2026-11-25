@echo off
rem Build STL-Converter.exe (STL + STEP) from stl_converter.py (a double click is enough).
title Build STL-Converter.exe
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python from https://www.python.org
    goto fehler
)

echo Installing or updating PyInstaller and the STEP library ...
rem cascadio tessellates STEP files (OpenCASCADE) and needs numpy internally
python -m pip install --upgrade pyinstaller cascadio numpy
if errorlevel 1 goto fehler

echo.
echo Building STL-Converter.exe ...
python -m PyInstaller --onefile --console --clean --noconfirm --name STL-Converter --collect-all cascadio stl_converter.py
if errorlevel 1 goto fehler

copy /y "dist\STL-Converter.exe" "STL-Converter.exe" >nul
if errorlevel 1 goto fehler
rmdir /s /q build
rmdir /s /q dist
del /q STL-Converter.spec

echo.
echo Done: STL-Converter.exe is in the folder %~dp0
if /i not "%~1"=="--ohne-pause" if /i not "%~1"=="--no-pause" pause
exit /b 0

:fehler
echo.
echo An error occurred while building.
if /i not "%~1"=="--ohne-pause" if /i not "%~1"=="--no-pause" pause
exit /b 1
