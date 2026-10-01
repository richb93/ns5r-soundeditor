@echo off
rem Build dist\NS5RSoundEditor.exe with PyInstaller.
rem Usage: build_windows.bat        (uses the "py" launcher or python on PATH)
setlocal
cd /d "%~dp0"

set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
%PY% -c "import tkinter" || (echo This Python has no Tk support - reinstall with "tcl/tk and IDLE" enabled & exit /b 1)

%PY% -m venv .build-venv || exit /b 1
call .build-venv\Scripts\activate.bat || exit /b 1
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt pyinstaller pillow || exit /b 1

python tools\make_icons.py || exit /b 1
pyinstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\ns5rse.spec || exit /b 1

echo.
echo Built: dist\NS5RSoundEditor.exe
