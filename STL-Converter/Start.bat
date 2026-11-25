@echo off
rem Start the STL/STEP -> DAE converter from source (a double click is enough).
rem On the first start a private Python environment (.venv) is created and everything is installed; after that it starts immediately.
setlocal
cd /d "%~dp0"
title STL/STEP to DAE Converter

if exist ".venv\Scripts\python.exe" goto start

set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python was not found.
  echo Please install Python: https://www.python.org/downloads/
  echo ^(tick "Add python.exe to PATH" during installation^) and double-click Start.bat again.
  echo.
  echo Or download the ready-made STL-Converter.exe from the Releases page, which needs no Python.
  pause
  exit /b 1
)

echo First start: setting up ^(about 1 minute, needs internet^) ...
%PY% -m venv .venv
if errorlevel 1 goto fehler
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fehler

:start
".venv\Scripts\python.exe" stl_converter.py %*
endlocal
exit /b 0

:fehler
echo.
echo Setup failed. Delete the ".venv" folder and try Start.bat again.
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1
