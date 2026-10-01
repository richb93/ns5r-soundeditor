#!/bin/bash
# Build "NS5R SoundEditor.app" (and a .dmg) with PyInstaller.
# Usage: ./build_mac.sh            (uses python3 on PATH; set PYTHON=... to override)
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"

"$PYTHON" -c 'import tkinter' || { echo "This Python has no Tk support (brew install python-tk)"; exit 1; }
"$PYTHON" -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt pyinstaller pillow

python tools/make_icons.py
pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/ns5rse.spec

APP="dist/NS5R SoundEditor.app"
DMG="dist/NS5R-SoundEditor-$(python -c 'import ns5rse; print(ns5rse.__version__)')-mac-$(uname -m).dmg"
rm -f "$DMG"
hdiutil create -quiet -volname "NS5R SoundEditor" -srcfolder "$APP" -ov -format UDZO "$DMG"
echo
echo "Built: $APP"
echo "       $DMG"
