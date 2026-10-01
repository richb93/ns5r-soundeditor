"""Build .icns (macOS) and .ico (Windows) from the original 16/32 px program icons.

Larger sizes are pixel-doubled (nearest neighbour) so the artwork stays crisp.
Output: build/icons/NS5RSoundEditor.{icns,ico}
"""
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ASSETS = os.path.join(ROOT, 'ns5rse', 'assets')
OUT = os.path.join(ROOT, 'build', 'icons')


def sized(size):
    src = Image.open(os.path.join(ASSETS, f'icon_{16 if size <= 16 else 32}.png')).convert('RGBA')
    return src if src.width == size else src.resize((size, size), Image.NEAREST)


def make_icns(path):
    if sys.platform == 'darwin' and shutil.which('iconutil'):
        tmp = tempfile.mkdtemp()
        iconset = os.path.join(tmp, 'icon.iconset')
        os.mkdir(iconset)
        for s in (16, 32, 128, 256, 512):
            sized(s).save(os.path.join(iconset, f'icon_{s}x{s}.png'))
            sized(s * 2).save(os.path.join(iconset, f'icon_{s}x{s}@2x.png'))
        subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', path], check=True)
        shutil.rmtree(tmp)
    else:
        sized(1024).save(path, append_images=[sized(s) for s in (16, 32, 64, 128, 256, 512)])


def make_ico(path):
    sizes = (16, 24, 32, 48, 64, 128, 256)
    sized(256).save(path, sizes=[(s, s) for s in sizes], append_images=[sized(s) for s in sizes[:-1]])


def main():
    os.makedirs(OUT, exist_ok=True)
    make_icns(os.path.join(OUT, 'NS5RSoundEditor.icns'))
    make_ico(os.path.join(OUT, 'NS5RSoundEditor.ico'))
    print('icons written to', OUT)


if __name__ == '__main__':
    main()
