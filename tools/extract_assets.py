"""Extract the artwork, dialog layouts and data tables from KORG's SENS5R.EXE (NS5R SoundEditor 1.04).

Usage:  python tools/extract_assets.py path/to/SENS5R.EXE
Writes ns5rse/assets/data.json, bmp_<id>.png and icon_<size>.png.  Needs Pillow.
"""
import io
import json
import os
import struct
import sys

from PIL import Image

from ne import NEFile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'ns5rse', 'assets')
CLASSES = {0x80: 'BUTTON', 0x81: 'EDIT', 0x82: 'STATIC', 0x83: 'LISTBOX', 0x84: 'SCROLLBAR', 0x85: 'COMBOBOX'}
DGROUP = 29          # the automatic data segment


def cstr(b, p):
    e = b.index(b'\0', p)
    return b[p:e].decode('cp1252'), e + 1


def parse_dialog(b):
    style, n, x, y, cx, cy = struct.unpack_from('<IBHHHH', b, 0)
    p = 13
    if b[p] == 0xFF:
        p += 3
    else:
        _, p = cstr(b, p)
    _, p = cstr(b, p)                  # class
    caption, p = cstr(b, p)
    if style & 0x40:                   # DS_SETFONT
        p += 2
        _, p = cstr(b, p)
    items = []
    for _ in range(n):
        ix, iy, iw, ih, iid, ist = struct.unpack_from('<hhhhHI', b, p)
        p += 14
        if b[p] & 0x80:
            cls = CLASSES.get(b[p], hex(b[p]))
            p += 1
        else:
            cls, p = cstr(b, p)
        if b[p] == 0xFF:
            text = struct.unpack_from('<H', b, p + 1)[0]
            p += 3
        else:
            text, p = cstr(b, p)
        p += 1 + b[p]
        items.append(dict(id=iid, cls=cls, rect=[ix, iy, iw, ih], style=ist, text=text))
    return dict(caption=caption, style=style, rect=[x, y, cx, cy], items=items)


def strings(ne):
    out = {}
    for r in ne.of_type('STRING'):
        b, p = r['data'], 0
        for i in range(16):
            n = b[p]
            p += 1
            if n:
                out[(r['id'] - 1) * 16 + i] = b[p:p + n].decode('cp1252')
            p += n
    return out


def names(blob, width=10):
    return [blob[i:i + width].decode('cp1252').rstrip() for i in range(0, len(blob) - width + 1, width)]


def dib_to_image(b):
    hs, w, h, _, bpp = struct.unpack_from('<IiiHH', b, 0)
    ncol = struct.unpack_from('<I', b, 32)[0] or (1 << bpp if bpp <= 8 else 0)
    head = b'BM' + struct.pack('<IHHI', 14 + len(b), 0, 0, 14 + hs + 4 * ncol)
    im = Image.open(io.BytesIO(head + b))
    im.load()
    return im


def icon_image(b):
    """ICON resource: a DIB with doubled height (XOR image followed by the AND mask)."""
    hs, w, h2, _, bpp = struct.unpack_from('<IiiHH', b, 0)
    h = h2 // 2
    ncol = 1 << bpp
    pal = [struct.unpack_from('<BBBx', b, hs + 4 * i) for i in range(ncol)]
    p = hs + 4 * ncol
    xor_stride = ((w * bpp + 31) // 32) * 4
    and_stride = ((w + 31) // 32) * 4
    xor, mask = b[p:p + xor_stride * h], b[p + xor_stride * h:]
    im = Image.new('RGBA', (w, h))
    for y in range(h):
        row = xor[(h - 1 - y) * xor_stride:]
        mrow = mask[(h - 1 - y) * and_stride:]
        for x in range(w):
            bit = x * bpp
            idx = (row[bit // 8] >> (8 - bpp - bit % 8)) & ((1 << bpp) - 1)
            bl, g, r = pal[idx]
            transparent = (mrow[x // 8] >> (7 - x % 8)) & 1
            im.putpixel((x, y), (r, g, bl, 0 if transparent else 255))
    return im


YELLOW, CYAN, MAGENTA, GREEN = (255, 255, 0), (0, 255, 255), (255, 0, 255), (0, 255, 0)
WHITE, BLACK, DARK, BLUE = (255, 255, 255), (0, 0, 0), (128, 128, 128), (0, 0, 255)
_osc = {CYAN: BLACK, MAGENTA: WHITE, BLUE: DARK}
_fx = {YELLOW: BLACK, WHITE: BLACK}
RECOLOR = {
    300: [('', _osc), ('_dis', {CYAN: DARK, MAGENTA: WHITE, BLUE: DARK})],
    301: [('', {YELLOW: BLACK, GREEN: WHITE, MAGENTA: WHITE})],
    500: [('', {GREEN: WHITE})],
    502: [('', {YELLOW: BLACK})],
    **{n: [('', _fx)] for n in (258, 259, 260, 261)},
    **{n: [('', {YELLOW: BLACK})] for n in range(100, 108)},
}


def recolor(im, mapping):
    im = im.convert('RGB')
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            c = px[x, y]
            if c in mapping:
                px[x, y] = mapping[c]
    return im


def main(exe):
    ne = NEFile(exe)
    os.makedirs(OUT, exist_ok=True)
    dg = ne.segment(DGROUP)
    s = strings(ne)
    data = dict(
        dialogs={str(r['id']): parse_dialog(r['data']) for r in ne.of_type('DIALOG')
                 if not str(r['id']).endswith('_4L')},
        strings=s,
        ms_names=names(ne.resource('GNRL', 1000)),
        kit_names=names(ne.resource('GNRL', 1001)),
        drum_names=names(ne.resource('GNRL', 1002))[:286],
        fx_dialog=list(ne.resource('GNRL', 1004)),
        x5_ms_map=list(struct.unpack('<432H', ne.resource('GNRL', 1005)[:864])),
        x5_drum_map=list(struct.unpack('<216H', ne.resource('GNRL', 1006)[:432])),
        default_kit=list(ne.resource('GNRL', 1010)[:1358]),
        fx_min=[list(ne.resource('ERNG', 1000 + i)[:48]) for i in range(8)],
        fx_max=[list(ne.resource('ERNG', 1010 + i)[:48]) for i in range(8)],
        fx_defaults=[list(ne.resource('FXDF', 100 + t)) for t in range(48)],
        kbdt={k: list(struct.unpack('<%dh' % (len(ne.resource('KBDT', k)) // 2), ne.resource('KBDT', k)))
              for k in (1000, 1001, 1003)},
        # bank index -> MSB/LSB tables (seg24:2505)
        bank_r_msb=list(dg[0x1A4D:0x1A4D + 22]),
        bank_y_lsb=list(dg[0x1A22:0x1A22 + 43]),
        bank_korg_msb=list(dg[0x1A63:0x1A63 + 13]),
        fx_bank_msb=list(dg[0x1A70:0x1A78]),
    )
    with open(os.path.join(OUT, 'data.json'), 'w') as f:
        json.dump(data, f, indent=0, ensure_ascii=False)
    for r in ne.of_type('BITMAP'):
        im = dib_to_image(r['data'])
        im.save(os.path.join(OUT, f"bmp_{r['id']}.png"))
        # The editor draws its panels in system colours; these are the recoloured versions.
        for suffix, mapping in RECOLOR.get(r['id'], ()):
            recolor(im, mapping).save(os.path.join(OUT, f"sys_{r['id']}{suffix}.png"))
    for r in ne.of_type('ICON'):
        im = icon_image(r['data'])
        im.save(os.path.join(OUT, f'icon_{im.width}.png'))
    print('assets written to', OUT)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'SENS5R.EXE')
