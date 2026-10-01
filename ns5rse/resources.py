"""Access to the data and artwork extracted from SENS5R.EXE (see tools/extract_assets.py)."""
import json
import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
_data = None
_strings = None


def data():
    global _data
    if _data is None:
        with open(os.path.join(ASSETS, 'data.json'), encoding='utf-8') as f:
            _data = json.load(f)
    return _data


def strings():
    global _strings
    if _strings is None:
        _strings = {int(k): v for k, v in data()['strings'].items()}
    return _strings


def dialog(name):
    return data()['dialogs'][str(name)]


def image_path(name):
    return os.path.join(ASSETS, name + '.png')
