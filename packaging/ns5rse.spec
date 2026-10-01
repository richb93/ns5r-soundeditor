# PyInstaller spec for NS5R SoundEditor.
#   macOS  : dist/NS5R SoundEditor.app   (windowed .app bundle)
#   Windows: dist/NS5RSoundEditor.exe    (single-file windowed .exe)
# Run through build_mac.sh / build_windows.bat, which create the icons first.
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
sys.path.insert(0, ROOT)
from ns5rse import __version__  # noqa: E402

NAME = 'NS5R SoundEditor'
ICONS = os.path.join(ROOT, 'build', 'icons')

a = Analysis(
    [os.path.join(ROOT, 'run.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'ns5rse', 'assets'), os.path.join('ns5rse', 'assets'))],
    # mido picks its backend at runtime, so PyInstaller cannot see it
    hiddenimports=['mido.backends.rtmidi', 'rtmidi'],
    excludes=['PIL', 'numpy'],   # Pillow is only needed by the build tools
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False,
              icon=os.path.join(ICONS, 'NS5RSoundEditor.icns'))
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
    app = BUNDLE(
        coll,
        name=NAME + '.app',
        icon=os.path.join(ICONS, 'NS5RSoundEditor.icns'),
        bundle_identifier='local.ns5rsoundeditor',
        version=__version__,
        info_plist={
            'CFBundleName': NAME,
            'CFBundleDisplayName': NAME,
            'CFBundleShortVersionString': __version__,
            'NSHighResolutionCapable': True,
            'NSHumanReadableCopyright': 'Original software (c) 1996-2001 KORG Inc.',
            'CFBundleDocumentTypes': [{
                'CFBundleTypeName': 'NS5R SoundEditor Document',
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Owner',
                'CFBundleTypeExtensions': ['ns5', 'NS5'],
                'CFBundleTypeIconFile': 'NS5RSoundEditor.icns',
            }, {
                'CFBundleTypeName': 'NS5R SysEx Data',
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Alternate',
                'CFBundleTypeExtensions': ['syx', 'mid'],
            }],
        },
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='NS5RSoundEditor', console=False,
              icon=os.path.join(ICONS, 'NS5RSoundEditor.ico'))
