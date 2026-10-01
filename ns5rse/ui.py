"""Windows 9x-style widgets for Tk, sized in dialog units (DLU) like the original resources.

The original dialogs use MS Sans Serif 8: one horizontal DLU is 7/4 px and one vertical
DLU 13/8 px.  Everything is multiplied by the integer GUI scale.
"""
import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

from . import resources as R

FACE = '#d4d0c8'
SHADOW = '#808080'
DARK = '#404040'
LIGHT = '#ffffff'
WINDOW = '#ffffff'
TEXT = '#000000'
GREYTEXT = '#808080'
SEL_BG = '#0a246a'
SEL_FG = '#ffffff'
BAR = '#0a246a'


class Scale:
    """Converts dialog units to pixels for the current GUI scale."""
    s = 1

    @classmethod
    def x(cls, v):
        return int(round(v * 7 * cls.s / 4))

    @classmethod
    def y(cls, v):
        return int(round(v * 13 * cls.s / 8))

    @classmethod
    def px(cls, v):
        return int(round(v * cls.s))


_fonts = {}


def font(kind='normal'):
    """The dialog font (stand-in for MS Sans Serif 8)."""
    key = (kind, Scale.s)
    if key not in _fonts:
        fam = 'Tahoma' if sys.platform == 'win32' else 'Helvetica' if sys.platform == 'darwin' else 'DejaVu Sans'
        size = {'normal': -11, 'small': -10, 'big': -13, 'bold': -11}[kind]
        _fonts[key] = tkfont.Font(family=fam, size=size * Scale.s,
                                  weight='bold' if kind == 'bold' else 'normal')
    return _fonts[key]


_images = {}


def image(name, zoom=None):
    """PhotoImage of an extracted bitmap, zoomed by the GUI scale."""
    z = zoom or Scale.s
    key = (name, z)
    if key not in _images:
        im = tk.PhotoImage(file=R.image_path(name))
        _images[key] = im.zoom(z) if z > 1 else im
    return _images[key]


def reset_caches():
    _fonts.clear()
    _images.clear()


def setup_style(root):
    root.option_add('*Font', font())
    root.option_add('*Background', FACE)
    root.configure(bg=FACE)
    st = ttk.Style(root)
    st.theme_use('alt')
    f = font()
    st.configure('.', background=FACE, foreground=TEXT, font=f, troughcolor='#e8e6e2',
                 selectbackground=SEL_BG, selectforeground=SEL_FG, fieldbackground=WINDOW,
                 bordercolor=SHADOW, lightcolor=LIGHT, darkcolor=SHADOW)
    st.configure('TButton', padding=(Scale.px(2), 0), anchor='center', borderwidth=Scale.px(2))
    st.map('TButton', foreground=[('disabled', GREYTEXT)])
    st.configure('TCheckbutton', padding=0, indicatormargin=(0, 0, Scale.px(3), 0))
    st.configure('TRadiobutton', padding=0, indicatormargin=(0, 0, Scale.px(3), 0))
    st.map('TCheckbutton', foreground=[('disabled', GREYTEXT)], indicatorcolor=[('disabled', FACE)])
    st.map('TRadiobutton', foreground=[('disabled', GREYTEXT)], indicatorcolor=[('disabled', FACE)])
    st.configure('TLabelframe', borderwidth=Scale.px(2), relief='groove', labelmargins=(Scale.px(6), 0, 0, 0))
    st.configure('TLabelframe.Label', font=f)
    st.configure('TNotebook', tabmargins=(Scale.px(2), Scale.px(2), 0, 0), borderwidth=Scale.px(2))
    st.configure('TNotebook.Tab', padding=(Scale.px(4), Scale.px(1)), font=f)
    st.map('TNotebook.Tab', padding=[('selected', (Scale.px(5), Scale.px(2)))])
    st.configure('TCombobox', padding=(Scale.px(2), 0), arrowsize=Scale.px(12))
    st.map('TCombobox', fieldbackground=[('readonly', WINDOW), ('disabled', FACE)],
           foreground=[('disabled', GREYTEXT)], selectbackground=[('readonly', WINDOW)],
           selectforeground=[('readonly', TEXT)])
    st.configure('TScrollbar', arrowsize=Scale.px(14))
    root.option_add('*TCombobox*Listbox.font', f)
    root.option_add('*TCombobox*Listbox.selectBackground', SEL_BG)


def place(w, rect):
    x, y, cx, cy = rect
    w.place(x=Scale.x(x), y=Scale.y(y), width=Scale.x(cx), height=Scale.y(cy))
    return w


# =================================================================== SpinBox
class SpinBox(tk.Frame):
    """Edit field with up/down arrows (the original's custom 'SpinBox' class).

    The model is an integer in [lo, hi]; `fmt` turns it into text and `parse` back.
    `on_change(value)` is called on every change made by the user.
    """

    def __init__(self, parent, lo=0, hi=127, fmt=str, parse=None, on_change=None, step=1, editable=True):
        super().__init__(parent, bg=FACE, bd=0, highlightthickness=0)
        self.lo, self.hi, self.fmt, self.parse_fn = lo, hi, fmt, parse
        self.on_change, self.step = on_change, step
        self.value = lo
        self.enabled = True
        self.var = tk.StringVar()
        self.entry = tk.Entry(self, textvariable=self.var, bd=Scale.px(2), relief='sunken', bg=WINDOW,
                              fg=TEXT, highlightthickness=0, font=font(), insertwidth=Scale.px(1),
                              disabledbackground=FACE, disabledforeground=GREYTEXT,
                              state='normal' if editable else 'readonly', readonlybackground=WINDOW)
        aw = Scale.x(8)
        self.arrows = tk.Canvas(self, width=aw, bg=FACE, highlightthickness=0, bd=0)
        self.arrows.pack(side='right', fill='y', padx=(Scale.px(2), 0))
        self.entry.pack(side='left', fill='both', expand=True)
        self.arrows.bind('<Configure>', lambda e: self.draw_arrows())
        self.arrows.bind('<ButtonPress-1>', self._press)
        self.arrows.bind('<ButtonRelease-1>', self._release)
        self.entry.bind('<Return>', self._commit)
        self.entry.bind('<FocusOut>', self._commit)
        self.entry.bind('<Up>', lambda e: self.bump(1))
        self.entry.bind('<Down>', lambda e: self.bump(-1))
        self.entry.bind('<Prior>', lambda e: self.bump(10))
        self.entry.bind('<Next>', lambda e: self.bump(-10))
        for w in (self.entry, self.arrows):
            w.bind('<MouseWheel>', self._wheel)
            w.bind('<Button-4>', lambda e: self.bump(1))
            w.bind('<Button-5>', lambda e: self.bump(-1))
        self._repeat = None
        self._pressed = 0

    def draw_arrows(self):
        c = self.arrows
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if w < 2 or h < 2:
            return
        mid = h // 2
        fg = TEXT if self.enabled else GREYTEXT
        for i, (y0, y1) in enumerate(((0, mid), (mid, h))):
            down = self._pressed == (1 if i == 0 else -1)
            tl, br = (SHADOW, LIGHT) if down else (LIGHT, DARK)
            c.create_rectangle(0, y0, w - 1, y1 - 1, fill=FACE, outline=br)
            c.create_line(0, y1 - 2, 0, y0, w - 2, y0, fill=tl)
            cx, cy = w // 2 + (1 if down else 0), (y0 + y1) // 2 + (1 if down else 0)
            s = max(2, (w - 4) // 3)
            if i == 0:
                c.create_polygon(cx - s, cy + s // 2, cx + s, cy + s // 2, cx, cy - s // 2 - 1, fill=fg, outline=fg)
            else:
                c.create_polygon(cx - s, cy - s // 2, cx + s, cy - s // 2, cx, cy + s // 2 + 1, fill=fg, outline=fg)

    def _press(self, e):
        if not self.enabled:
            return
        self._pressed = 1 if e.y < self.arrows.winfo_height() / 2 else -1
        self.draw_arrows()
        self.bump(self._pressed)
        self._repeat = self.after(400, self._auto)

    def _auto(self):
        if self._pressed:
            self.bump(self._pressed)
            self._repeat = self.after(60, self._auto)

    def _release(self, e):
        self._pressed = 0
        if self._repeat:
            self.after_cancel(self._repeat)
            self._repeat = None
        self.draw_arrows()

    def _wheel(self, e):
        if self.enabled:
            self.bump(1 if e.delta > 0 else -1)
        return 'break'

    def bump(self, n):
        if not self.enabled:
            return 'break'
        self.set_user(self.value + n * self.step)
        return 'break'

    def set_user(self, v):
        v = max(self.lo, min(self.hi, int(v)))
        changed = v != self.value
        self.set(v)
        if changed and self.on_change:
            self.on_change(v)

    def _commit(self, e=None):
        if not self.enabled:
            return
        txt = self.var.get().strip()
        if txt == self.fmt(self.value):
            return
        v = None
        if self.parse_fn:
            v = self.parse_fn(txt)
        if v is None:
            for cand in range(self.lo, self.hi + 1):
                if self.fmt(cand).strip().lower() == txt.lower():
                    v = cand
                    break
        if v is None:
            try:
                v = int(float(txt))
            except ValueError:
                v = self.value
        self.set_user(v)

    def set(self, v):
        self.value = max(self.lo, min(self.hi, int(v)))
        self.var.set(self.fmt(self.value))

    def set_range(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.set(self.value)

    def enable(self, on=True):
        self.enabled = on
        self.entry.config(state='normal' if on else 'disabled')
        self.draw_arrows()


# =================================================================== check boxes
class PMBox(tk.Canvas):
    """Keyboard-tracking / velocity time switch: Off, On (+), On (-).

    Drawn like a checkbox; a check mark means '+', a dash means '-'.
    """

    def __init__(self, parent, label, on_change=None):
        super().__init__(parent, bg=FACE, highlightthickness=0, bd=0)
        self.label, self.on_change, self.state = label, on_change, 0
        self.enabled = True
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Button-1>', self._click)

    def _click(self, e):
        if self.enabled:
            self.state = (self.state + 1) % 3
            self.draw()
            if self.on_change:
                self.on_change(self.state)

    def set(self, st):
        self.state = st
        self.draw()

    def draw(self):
        self.delete('all')
        h = self.winfo_height()
        b = Scale.px(13)
        y0 = (h - b) // 2
        draw_check_box(self, 0, y0, b, self.state == 1, self.enabled, dash=self.state == 2)
        self.create_text(b + Scale.px(5), h // 2, text=self.label, anchor='w', font=font(),
                         fill=TEXT if self.enabled else GREYTEXT)


def draw_check_box(c, x, y, b, checked, enabled=True, dash=False):
    c.create_rectangle(x, y, x + b - 1, y + b - 1, fill=WINDOW if enabled else FACE, outline=LIGHT)
    c.create_line(x, y + b - 1, x, y, x + b - 1, y, fill=SHADOW)
    c.create_line(x + 1, y + b - 2, x + 1, y + 1, x + b - 2, y + 1, fill=DARK)
    fg = TEXT if enabled else GREYTEXT
    s = Scale.s
    if checked:
        c.create_line(x + 3 * s, y + 6 * s, x + 5 * s, y + 9 * s, x + 10 * s, y + 3 * s, fill=fg, width=2 * s)
    if dash:
        c.create_line(x + 3 * s, y + b // 2, x + b - 3 * s, y + b // 2, fill=fg, width=2 * s)


# =================================================================== list view
class ListView(tk.Frame):
    """Owner-drawn list box: optional columns, multi-column wrapping, multiple selection.

    items: list of row tuples (one string per column).
    columns: x positions (DLU, relative to the list) with optional ('r') alignment.
    """

    def __init__(self, parent, columns=None, multicolumn=False, col_width=None, extended=False,
                 on_select=None, on_double=None, item_height=None):
        super().__init__(parent, bg=FACE, bd=Scale.px(2), relief='sunken', highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=WINDOW, highlightthickness=0, bd=0, takefocus=1)
        self.multicolumn = multicolumn
        orient = 'horizontal' if multicolumn else 'vertical'
        self.sb = ttk.Scrollbar(self, orient=orient, command=self._scroll)
        if multicolumn:
            self.sb.pack(side='bottom', fill='x')
        else:
            self.sb.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.columns = columns or [(1, 'l')]
        self.col_width = col_width
        self.extended = extended
        self.on_select, self.on_double = on_select, on_double
        self.items = []
        self.selected = set()
        self.cursor = 0
        self.anchor = 0
        self.top = 0
        self.row_h = item_height or font().metrics('linespace')
        self.canvas.bind('<Configure>', lambda e: self.redraw())
        self.canvas.bind('<Button-1>', self._click)
        self.canvas.bind('<Shift-Button-1>', lambda e: self._click(e, shift=True))
        self.canvas.bind('<Control-Button-1>', lambda e: self._click(e, ctrl=True))
        self.canvas.bind('<Command-Button-1>' if sys.platform == 'darwin' else '<Control-Button-1>',
                         lambda e: self._click(e, ctrl=True))
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<Double-Button-1>', self._double)
        self.canvas.bind('<Key>', self._key)
        for w in (self.canvas, self.sb):
            w.bind('<MouseWheel>', self._wheel)
            w.bind('<Button-4>', lambda e: self.scroll_by(-3))
            w.bind('<Button-5>', lambda e: self.scroll_by(3))

    # geometry
    def rows_visible(self):
        return max(1, self.canvas.winfo_height() // self.row_h)

    def per_page(self):
        if self.multicolumn:
            return self.rows_visible() * self.cols_visible()
        return self.rows_visible()

    def cols_visible(self):
        return max(1, self.canvas.winfo_width() // self.col_px())

    def col_px(self):
        return Scale.x(self.col_width or 60)

    def unit_count(self):
        """Scroll units: rows, or columns when multicolumn."""
        if self.multicolumn:
            r = self.rows_visible()
            return (len(self.items) + r - 1) // r
        return len(self.items)

    def view_units(self):
        return self.cols_visible() if self.multicolumn else self.rows_visible()

    def _scroll(self, *args):
        if args[0] == 'moveto':
            self.top = int(float(args[1]) * self.unit_count() + 0.5)
        elif args[0] == 'scroll':
            n = int(args[1])
            self.top += n * (self.view_units() if args[2] == 'pages' else 1)
        self.clamp_top()
        self.redraw()

    def clamp_top(self):
        self.top = max(0, min(self.top, self.unit_count() - self.view_units()))

    def scroll_by(self, n):
        self.top += n
        self.clamp_top()
        self.redraw()

    def _wheel(self, e):
        self.scroll_by(-1 if e.delta > 0 else 1)
        return 'break'

    def index_at(self, x, y):
        r = y // self.row_h
        if self.multicolumn:
            c = x // self.col_px() + self.top
            i = c * self.rows_visible() + r
        else:
            i = self.top + r
        return i if 0 <= i < len(self.items) else None

    def item_pos(self, i):
        """(x, y) of item i on the canvas, or None when scrolled out of view."""
        if self.multicolumn:
            rows = self.rows_visible()
            c, r = divmod(i, rows)
            c -= self.top
            if 0 <= c < self.cols_visible() + 1:
                return c * self.col_px(), r * self.row_h
            return None
        r = i - self.top
        if 0 <= r <= self.rows_visible():
            return 0, r * self.row_h
        return None

    def redraw(self):
        c = self.canvas
        c.delete('all')
        w = c.winfo_width()
        f = font()
        focus = c.focus_get() == c
        for i in range(len(self.items)):
            pos = self.item_pos(i)
            if pos is None:
                continue
            x, y = pos
            width = self.col_px() if self.multicolumn else w
            sel = i in self.selected
            if sel:
                c.create_rectangle(x, y, x + width - 1, y + self.row_h - 1, fill=SEL_BG, outline=SEL_BG)
            if focus and i == self.cursor:
                c.create_rectangle(x, y, x + width - 1, y + self.row_h - 1, outline='#888888', dash=(1, 1))
            row = self.items[i]
            row = row if isinstance(row, (list, tuple)) else (row,)
            for (cx, al), txt in zip(self.columns, row):
                px = x + Scale.x(cx)
                c.create_text(px, y + self.row_h // 2, text=txt, anchor='e' if al == 'r' else 'w', font=f,
                              fill=SEL_FG if sel else TEXT)
        n, v = self.unit_count(), self.view_units()
        if n <= v:
            self.sb.set(0, 1)
        else:
            self.sb.set(self.top / n, (self.top + v) / n)

    def set_items(self, items, keep=True):
        self.items = list(items)
        if not keep:
            self.selected = set()
            self.top = 0
        self.selected = {i for i in self.selected if i < len(self.items)}
        self.clamp_top()
        self.redraw()

    def select(self, i, notify=False, see=True):
        if not self.items:
            return
        i = max(0, min(len(self.items) - 1, i))
        self.selected = {i}
        self.cursor = self.anchor = i
        if see:
            self.see(i)
        self.redraw()
        if notify and self.on_select:
            self.on_select(i)

    def see(self, i):
        if self.multicolumn:
            u = i // self.rows_visible()
        else:
            u = i
        if u < self.top:
            self.top = u
        elif u >= self.top + self.view_units():
            self.top = u - self.view_units() + 1
        self.clamp_top()

    def current(self):
        return self.cursor if self.items else None

    def selection(self):
        return sorted(self.selected)

    def _click(self, e, shift=False, ctrl=False):
        self.canvas.focus_set()
        i = self.index_at(e.x, e.y)
        if i is None:
            return
        if self.extended and shift:
            a, b = sorted((self.anchor, i))
            self.selected = set(range(a, b + 1))
            self.cursor = i
        elif self.extended and ctrl:
            self.selected ^= {i}
            self.cursor = self.anchor = i
        else:
            self.selected = {i}
            self.cursor = self.anchor = i
        self.redraw()
        if self.on_select:
            self.on_select(i)

    def _drag(self, e):
        if not self.extended:
            return self._click(e)
        i = self.index_at(e.x, max(0, min(e.y, self.canvas.winfo_height() - 1)))
        if i is not None and i != self.cursor:
            a, b = sorted((self.anchor, i))
            self.selected = set(range(a, b + 1))
            self.cursor = i
            self.redraw()
            if self.on_select:
                self.on_select(i)

    def _double(self, e):
        i = self.index_at(e.x, e.y)
        if i is not None and self.on_double:
            self.on_double(i)

    def _key(self, e):
        step = {'Up': -1, 'Down': 1, 'Prior': -self.per_page(), 'Next': self.per_page(),
                'Home': -10 ** 6, 'End': 10 ** 6}
        if self.multicolumn:
            step.update(Left=-self.rows_visible(), Right=self.rows_visible())
        if e.keysym in step and self.items:
            self.select(self.cursor + step[e.keysym], notify=True)
            return 'break'
        if e.keysym in ('Return', 'KP_Enter') and self.on_double and self.items:
            self.on_double(self.cursor)
            return 'break'


# =================================================================== velocity window bar
class VelWinBar(tk.Canvas):
    """Shows a window lo..hi of 1/0..127 as a dark bar on white."""

    def __init__(self, parent, lo_min=1):
        super().__init__(parent, bg=WINDOW, highlightthickness=0, bd=0)
        self.lo, self.hi, self.lo_min = lo_min, 127, lo_min
        self.bind('<Configure>', lambda e: self.draw())

    def set(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.draw()

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        sunken(self, 0, 0, w, h)
        span = 127 - self.lo_min + 1
        x0 = 2 + (w - 4) * (self.lo - self.lo_min) / span
        x1 = 2 + (w - 4) * (self.hi - self.lo_min + 1) / span
        if self.hi >= self.lo:
            self.create_rectangle(x0, 2, x1 - 1, h - 3, fill=BAR, outline=BAR)
        else:  # crossed window: two bars
            self.create_rectangle(2, 2, x1 - 1, h - 3, fill=BAR, outline=BAR)
            self.create_rectangle(x0, 2, w - 3, h - 3, fill=BAR, outline=BAR)


def sunken(c, x0, y0, x1, y1):
    c.create_line(x0, y1 - 1, x0, y0, x1 - 1, y0, fill=SHADOW)
    c.create_line(x0 + 1, y1 - 2, x0 + 1, y0 + 1, x1 - 2, y0 + 1, fill=DARK)
    c.create_line(x0, y1 - 1, x1 - 1, y1 - 1, x1 - 1, y0, fill=LIGHT)
    c.create_line(x0 + 1, y1 - 2, x1 - 2, y1 - 2, x1 - 2, y0 + 1, fill=FACE)


def raised(c, x0, y0, x1, y1, fill=FACE):
    c.create_rectangle(x0, y0, x1 - 1, y1 - 1, fill=fill, outline=fill)
    c.create_line(x0, y1 - 1, x0, y0, x1 - 1, y0, fill=LIGHT)
    c.create_line(x0, y1 - 1, x1 - 1, y1 - 1, x1 - 1, y0, fill=DARK)
    c.create_line(x0 + 1, y1 - 2, x1 - 2, y1 - 2, x1 - 2, y0 + 1, fill=SHADOW)


# =================================================================== keyboards
BLACK = {1, 3, 6, 8, 10}
WHITE_INDEX = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}


def key_layout(first, last, width, height):
    """Rectangles for keys first..last across `width` px: {note: (x0, y0, x1, y1, black)}."""
    whites = [n for n in range(first, last + 1) if n % 12 not in BLACK]
    ww = width / len(whites)
    keys = {}
    for i, n in enumerate(whites):
        keys[n] = (i * ww, 0, (i + 1) * ww, height, False)
    bw = ww * 0.6
    for n in range(first, last + 1):
        if n % 12 in BLACK and n - 1 in keys:
            x = keys[n - 1][2]
            keys[n] = (x - bw / 2, 0, x + bw / 2, height * 0.62, True)
    return keys


class Keyboard(tk.Canvas):
    """Piano keyboard first..last.  `highlight` returns the colour for a note (or None).

    on_press(note) / on_release(note) are called for mouse play.
    """

    def __init__(self, parent, first=0, last=127, on_press=None, on_release=None, highlight=None,
                 on_click=None):
        super().__init__(parent, bg=WINDOW, highlightthickness=0, bd=0)
        self.first, self.last = first, last
        self.on_press, self.on_release, self.highlight, self.on_click = on_press, on_release, highlight, on_click
        self.down = set()
        self.mouse = None
        self.keys = {}
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<B1-Motion>', self._motion)
        self.bind('<ButtonRelease-1>', self._release)

    def set_range(self, first, last):
        self.first, self.last = first, last
        self.draw()

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        self.keys = key_layout(self.first, self.last, w - 1, h - 1)
        for black in (False, True):
            for n, (x0, y0, x1, y1, b) in self.keys.items():
                if b != black:
                    continue
                col = '#000000' if b else '#ffffff'
                hl = self.highlight(n) if self.highlight else None
                if n in self.down:
                    col = '#808080' if b else '#c0c0c0'
                elif hl:
                    col = hl
                self.create_rectangle(x0, y0, x1, y1, fill=col, outline='#000000')

    def note_at(self, x, y):
        for black in (True, False):
            for n, (x0, y0, x1, y1, b) in self.keys.items():
                if b == black and x0 <= x < x1 and y0 <= y < y1:
                    return n
        return None

    def _press(self, e):
        n = self.note_at(e.x, e.y)
        if self.on_click:
            if n is not None:
                self.on_click(n)
            return
        if n is not None:
            self.mouse = n
            self.press(n)

    def _motion(self, e):
        if self.on_click:
            return
        n = self.note_at(e.x, e.y)
        if n != self.mouse:
            if self.mouse is not None:
                self.release(self.mouse)
            self.mouse = n
            if n is not None:
                self.press(n)

    def _release(self, e):
        if self.mouse is not None:
            self.release(self.mouse)
            self.mouse = None

    def press(self, n):
        self.down.add(n)
        self.draw()
        if self.on_press:
            self.on_press(n)

    def release(self, n):
        self.down.discard(n)
        self.draw()
        if self.on_release:
            self.on_release(n)


# =================================================================== envelope graph
class EnvelopeBox(tk.Canvas):
    """EG graph: `points()` returns [(time, level)] with time in arbitrary units and
    level in -1..1 (bipolar) or 0..1."""

    def __init__(self, parent, points, bipolar=True, sustain_index=None):
        super().__init__(parent, bg=WINDOW, highlightthickness=0, bd=0)
        self.points, self.bipolar, self.sustain_index = points, bipolar, sustain_index
        self.bind('<Configure>', lambda e: self.draw())

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        sunken(self, 0, 0, w, h)
        m = Scale.px(6)
        x0, x1, y0, y1 = m + Scale.px(4), w - m, m, h - m
        ymid = (y0 + y1) / 2 if self.bipolar else y1
        # axes with arrow heads
        self.create_line(x0, y1 + Scale.px(2), x0, y0 - Scale.px(2), arrow='both', arrowshape=(4 * Scale.s, 4 * Scale.s, 2 * Scale.s), fill=TEXT)
        self.create_line(x0, ymid, x1, ymid, arrow='last', arrowshape=(4 * Scale.s, 4 * Scale.s, 2 * Scale.s), fill=TEXT)
        pts = self.points()
        if not pts:
            return
        total = max(1, pts[-1][0])
        span = (y1 - y0) / 2 if self.bipolar else (y1 - y0)
        coords = [(x0 + (x1 - x0 - Scale.px(6)) * t / total, ymid - lv * span) for t, lv in pts]
        flat = [v for p in coords for v in p]
        if len(coords) > 1:
            self.create_line(*flat, width=2 * Scale.s, fill=TEXT)
        r = Scale.px(2)
        for x, y in coords:
            self.create_rectangle(x - r, y - r, x + r, y + r, fill=TEXT, outline=TEXT)
