"""The graphical summary panels of the main window: OSC overview, timbre overview and
the effect placement diagram.  Positions are those used by the original drawing code
(seg22 for the OSC panel), in pixels of the panel bitmaps."""
import tkinter as tk

from . import model as M
from . import names as N
from . import params as PR
from . import ui
from .ui import Scale


def eg_points(prog, base, kind):
    """Envelope corner points [(time, level)] for an oscillator's pitch/VDF/VDA EG."""
    b = prog
    s8 = M.s8

    def t(v):
        return 4 + v

    if kind == 'pitch':
        start, at, al, dt, rt, rl = (s8(b[base + 18]), b[base + 19], s8(b[base + 20]), b[base + 21],
                                     b[base + 22], s8(b[base + 23]))
        x = [0, t(at), t(at) + t(dt), t(at) + t(dt) + 80, t(at) + t(dt) + 80 + t(rt)]
        y = [start, al, 0, 0, rl]
        return [(xx, yy / 128) for xx, yy in zip(x, y)]
    if kind == 'vdf':
        at, al, dt, bp, st, sl, rt, rl = (b[base + 41], s8(b[base + 42]), b[base + 43], s8(b[base + 44]),
                                          b[base + 45], s8(b[base + 46]), b[base + 47], s8(b[base + 48]))
        x = [0]
        for d in (at, dt, st):
            x.append(x[-1] + t(d))
        x.append(x[-1] + 80)
        x.append(x[-1] + t(rt))
        y = [0, al, bp, sl, sl, rl]
        return [(xx, yy / 128) for xx, yy in zip(x, y)]
    at, al, dt, bp, st, sl, rt = (b[base + 62], b[base + 63], b[base + 64], b[base + 65], b[base + 66],
                                  b[base + 67], b[base + 68])
    x = [0]
    for d in (at, dt, st):
        x.append(x[-1] + t(d))
    x.append(x[-1] + 80)
    x.append(x[-1] + t(rt))
    y = [0, al, bp, sl, sl, 0]
    return [(xx, yy / 127) for xx, yy in zip(x, y)]


class OscSummary(tk.Canvas):
    """'OSC Parameters' overview of one oscillator (bitmap 300 plus values)."""
    W, H = 210, 192
    # data offset (OSC1 absolute) -> (x, y, align, format)
    VALUES = {
        17: (54, 36, 'e', str), 16: (92, 36, 'e', None), 18: (150, 36, 'e', PR.signed),
        19: (206, 36, 'e', PR.signed), 20: (150, 23, 'e', PR.slope), 23: (206, 23, 'e', str),
        29: (150, 51, 'e', PR.signed), 30: (150, 77, 'e', PR.signed), 31: (150, 90, 'e', PR.signed),
        25: (206, 64, 'e', str), 26: (206, 77, 'e', str), 28: (206, 90, 'e', str),
        43: (150, 105, 'e', str), 51: (150, 118, 'e', PR.signed), 45: (150, 144, 'e', None),
        39: (206, 118, 'e', str), 42: (206, 131, 'e', str), 49: (206, 144, 'e', str),
        67: (206, 174, 'e', str), 69: (150, 174, 'e', None),
    }
    WAVES = {24: 51, 38: 105, 63: 158}
    GRAPHS = {'pitch': (10, 54, 93, 98), 'vdf': (10, 108, 93, 152), 'vda': (10, 162, 93, 185)}

    def __init__(self, parent, osc, on_click=None):
        super().__init__(parent, width=self.W * Scale.s, height=self.H * Scale.s, bg=ui.FACE,
                         highlightthickness=0, bd=0)
        self.osc = osc
        self.prog = None
        self.active = True
        if on_click:
            self.bind('<Double-Button-1>', lambda e: on_click(self.section_at(e.x, e.y)))

    def section_at(self, x, y):
        y //= Scale.s
        if y < 50:
            return 'osc'
        if y < 104:
            return 'pitch'
        return 'vdf' if y < 158 else 'vda'

    def set(self, prog, active):
        self.prog, self.active = prog, active
        self.draw()

    def draw(self):
        s = Scale.s
        self.delete('all')
        self.create_image(0, 0, anchor='nw', image=ui.image('sys_300' if self.active else 'sys_300_dis'))
        self.create_text(59 * s, 7 * s - 1, anchor='nw', text=str(self.osc + 1), font=ui.font(),
                         fill=ui.TEXT if self.active else ui.GREYTEXT)
        if not self.active or self.prog is None:
            return
        p, base = self.prog, (M.OSC1 if self.osc == 0 else M.OSC2)
        d = base - M.OSC1
        f = ui.font()
        ms = (p[base] << 8) | p[base + 1]
        self.create_text(8 * s, 23 * s, anchor='nw', text=N.ms_name(ms), font=f, fill=ui.TEXT)
        for off, (x, y, al, fmt) in self.VALUES.items():
            v = p[off + d]
            if off == 16:
                txt = PR.OCTAVES[PR.osc_octave_index(v)]
            elif off in (45, 69):
                txt = PR.KBD_MODES[v & 3]
            else:
                sp = PR.PROGRAM.get(1000 + off)
                txt = fmt(sp.get(p, d) if sp else v)
            self.create_text(x * s, y * s, anchor='n' + al, text=txt, font=f, fill=ui.TEXT)
        for off, y in self.WAVES.items():
            w = min(p[off + d] & 7, 5)
            self.create_image(187 * s, (y + 1) * s, anchor='nw', image=self.wave_icon(w))
        lo, hi = p[base + 7], p[base + 8]
        x0, y0, x1, y1 = 138, 12, 203, 18
        self.create_rectangle(x0 * s, y0 * s, (x1 + 1) * s, (y1 + 1) * s, fill=ui.WINDOW, outline='')
        if hi >= lo:
            self.create_rectangle((x0 + 1 + lo // 2) * s, (y0 + 1) * s, (x0 + 1 + (hi + 1) // 2) * s,
                                  y1 * s, fill=ui.TEXT, outline='')
        for kind, (gx0, gy0, gx1, gy1) in self.GRAPHS.items():
            self.mini_eg(kind, base, gx0, gy0, gx1, gy1)

    def wave_icon(self, w):
        key = f'_wave{w}'
        img = getattr(self, key, None)
        if img is None:
            full = ui.image('sys_500')
            img = tk.PhotoImage()
            s = Scale.s
            img.tk.call(img, 'copy', full, '-from', w * 20 * s, 0, (w + 1) * 20 * s, 12 * s)
            setattr(self, key, img)
        return img

    def mini_eg(self, kind, base, x0, y0, x1, y1):
        s = Scale.s
        pts = eg_points(self.prog, base, kind)
        bip = kind != 'vda'
        total = max(1, pts[-1][0])
        w, h = (x1 - x0 - 6) * s, (y1 - y0 - 6) * s
        ox, oy = (x0 + 3) * s, (y0 + 3) * s
        mid = oy + (h / 2 if bip else h)
        span = h / 2 if bip else h
        coords = []
        for t, lv in pts:
            coords += [ox + w * t / total, mid - lv * span]
        self.create_line(*coords, fill=ui.TEXT, width=s)


class TimbreSummary(tk.Canvas):
    """Combination 'T1'..'T8' overview (bitmap 301 plus values and check boxes)."""
    W, H = 320, 210

    def __init__(self, parent, lib, on_double=None):
        super().__init__(parent, width=self.W * Scale.s, height=self.H * Scale.s, bg=ui.FACE,
                         highlightthickness=0, bd=0)
        self.lib = lib
        self.combi = None
        self.t = 0
        if on_double:
            self.bind('<Double-Button-1>', lambda e: on_double())

    def set(self, combi, t):
        self.combi, self.t = combi, t
        self.draw()

    def draw(self):
        s = Scale.s
        self.delete('all')
        self.create_image(0, 0, anchor='nw', image=ui.image('sys_301'))
        c = self.combi
        if c is None:
            return
        b = M.TIMBRE0 + self.t * M.TIMBRE_SIZE
        f = ui.font()
        bank = N.bank_index(c[b], c[b + 1])
        prog = c[b + 2]
        rows = [(f'{c[b]:03d}:{c[b + 1]:03d}  {N.bank_name(bank) if bank is not None else "?"}', 33),
                (N.numbered(prog, N.program_name(bank, prog, self.lib)) if bank is not None else '', 47),
                (str(c[b + 3]), 59), (PR.pan(c[b + 4]), 73), (str(c[b + 5]), 112), (str(c[b + 6]), 125)]
        for txt, y in rows:
            self.create_text(76 * s, y * s, anchor='w', text=txt, font=f, fill=ui.TEXT)
        self.create_text(186 * s, 112 * s, anchor='w', text=str(M.s8(c[b + 11])), font=f, fill=ui.TEXT)
        self.create_text(186 * s, 125 * s, anchor='w', text=str(M.s8(c[b + 12])), font=f, fill=ui.TEXT)
        for j in range(6):
            y = 32 + 17 * j
            ui.draw_check_box(self, 214 * s, (y - 1) * s, 11 * s, bool(c[b + 13] & (1 << j)))
        # key window
        lo, hi = c[b + 7], c[b + 8]
        x0, y0, x1, y1 = 10, 162, 309, 180
        keys = ui.key_layout(0, 127, (x1 - x0) * s, (y1 - y0) * s)
        for black in (False, True):
            for n, (kx0, ky0, kx1, ky1, bl) in keys.items():
                if bl != black:
                    continue
                inside = lo <= n <= hi if lo <= hi else (n >= lo or n <= hi)
                col = ('#000000' if bl else '#ffffff') if inside else ('#606060' if bl else '#a0a0a0')
                self.create_rectangle(x0 * s + kx0, y0 * s + ky0, x0 * s + kx1, y0 * s + ky1, fill=col,
                                      outline='#000000')
        # velocity window
        vlo, vhi = c[b + 9], c[b + 10]
        self.create_text(125 * s, 198 * s, anchor='e', text=str(vlo), font=f, fill=ui.TEXT)
        self.create_text(275 * s, 198 * s, anchor='w', text=str(vhi), font=f, fill=ui.TEXT)
        bx0, by0, bx1, by1 = 139, 193, 269, 201
        self.create_rectangle(bx0 * s, by0 * s, (bx1 + 1) * s, (by1 + 1) * s, fill=ui.WINDOW, outline=ui.TEXT)
        if vhi >= vlo:
            w = bx1 - bx0 - 3
            self.create_rectangle((bx0 + 2 + w * (vlo - 1) / 127) * s, (by0 + 2) * s,
                                  (bx0 + 2 + w * vhi / 127) * s, (by1 - 1) * s, fill=ui.TEXT, outline='')


class EffectDiagram(tk.Canvas):
    """Effect placement diagram (bitmaps 258-261) with the original 'EffectUserItem' hot spots.

    Item rectangles are in DLU relative to the diagram (item 19's origin)."""
    # placement -> {item: role}; roles: fx1, fx2, pan3, pan4, lvl1, lvl2
    ROLES = {
        0: {20: 'fx1', 21: 'fx2', 22: 'pan3', 23: 'pan4'},
        1: {20: 'fx1', 24: 'fx2', 25: 'pan3', 26: 'pan4'},
        2: {34: 'fx1', 27: 'fx2', 28: 'pan3', 29: 'pan4'},
        3: {30: 'fx1', 31: 'fx2', 32: 'lvl1', 33: 'lvl2'},
    }

    def __init__(self, parent, items, lib, on_double=None):
        super().__init__(parent, bg=ui.FACE, highlightthickness=0, bd=0)
        self.items, self.lib, self.on_double = items, lib, on_double
        self.fx = None
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Double-Button-1>', self._double)

    def set(self, fx):
        self.fx = fx
        self.draw()

    def placement(self):
        return (self.fx[0x10] >> 4) & 3 if self.fx else 0

    def rect(self, item):
        ox, oy = self.items[19][:2]
        x, y, w, h = self.items[item]
        return Scale.x(x - ox), Scale.y(y - oy), Scale.x(x - ox + w), Scale.y(y - oy + h)

    def role_at(self, x, y):
        for item, role in self.ROLES[self.placement()].items():
            x0, y0, x1, y1 = self.rect(item)
            if x0 <= x < x1 and y0 <= y < y1:
                return role
        return 'placement'

    def _double(self, e):
        if self.on_double and self.fx is not None:
            self.on_double(self.role_at(e.x, e.y))

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if self.fx is None or w < 4:
            return
        pl = self.placement()
        img = ui.image(f'sys_{258 + pl}')
        iw, ih = img.width(), img.height()
        # crop the bitmap's own bevel and draw an etched frame instead
        self.create_image((w - iw) // 2, (h - ih) // 2, anchor='nw', image=img)
        self.create_rectangle(0, 0, w - 1, h - 1, outline=ui.FACE, width=4 * Scale.s)
        self.create_rectangle(0, 0, w - 2, h - 2, outline=ui.SHADOW)
        self.create_rectangle(1, 1, w - 1, h - 1, outline=ui.LIGHT)
        self.create_rectangle(1, 1, w - 2, h - 2, outline=ui.SHADOW)
        fx = self.fx
        f = ui.font()
        for item, role in self.ROLES[pl].items():
            x0, y0, x1, y1 = self.rect(item)
            if role in ('fx1', 'fx2'):
                e = 0 if role == 'fx1' else 1
                t = fx[8 + e]
                self.create_rectangle(x0, y0, x1, y1, fill=ui.FACE, outline=ui.TEXT, width=2 * Scale.s)
                self.create_text(x0 + Scale.px(8), y0 + Scale.px(4), anchor='nw', font=f, fill=ui.TEXT,
                                 text=f'Effect {e + 1}\n{N.fx_type_name(t, short=True)}')
            elif role in ('pan3', 'pan4'):
                n = 3 if role == 'pan3' else 4
                v = fx[0x0E + n - 3]
                self.create_rectangle(x0, y0, x1, y1, fill=ui.FACE, outline=ui.TEXT)
                txt = f'Pan{n}  ' + ('Off' if v == 0 else PR.pan101(v))
                self.create_text(x0 + Scale.px(4), (y0 + y1) // 2, anchor='w', font=f, fill=ui.TEXT, text=txt)
            else:
                n = 1 if role == 'lvl1' else 2
                v = fx[0x0E + n - 1]
                self.create_rectangle(x0, y0, x1, y1, fill=ui.FACE, outline=ui.TEXT)
                self.create_text((x0 + x1) // 2, (y0 + y1) // 2, font=f, fill=ui.TEXT, justify='center',
                                 text=f'L{v >> 4}\nR{v & 15}')
