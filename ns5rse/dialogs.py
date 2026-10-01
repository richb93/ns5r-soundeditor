"""General dialogs: name lists, remarks, MIDI setup, preferences, about, dumps, utilities."""
import tkinter as tk
from tkinter import messagebox, ttk

from . import __version__
from . import names as N
from . import params as PR
from . import ui
from .binder import combo_set, set_entry
from .forms import ModalDialog
from .ui import Scale


# =================================================================== name lists
class NameListDialog(ModalDialog):
    """NAMELIST_DLG: a multi-column list to pick from; returns the index or None."""

    def __init__(self, master, title, items, current=0, col_width=68):
        super().__init__(master, 'NAMELIST_DLG', title=title, custom={101: self._make_list})
        self.lv.col_width = col_width
        self.lv.set_items(items)
        self.lv.on_double = lambda i: self.ok()
        self.top.after_idle(lambda: (self.lv.select(current or 0), self.lv.canvas.focus_set()))

    def _make_list(self, form, it):
        self.lv = ui.ListView(form.parent, multicolumn=True, col_width=68)
        return self.lv

    def ok(self):
        self.result = self.lv.current()
        self.close()


def program_list_items(bank, lib):
    return [N.numbered(p, N.program_name(bank, p, lib)) for p in range(128)]


def fx_list_items(bank, lib):
    return [N.numbered(n, N.fx_name(bank, n, lib)) for n in range(128)]


def bank_list_items(combination=False):
    banks = [b for b in range(N.N_BANKS) if not (combination and 72 <= b <= 76)]
    return banks, [N.bank_name(b) for b in banks]


# =================================================================== remarks
class RemarkDialog(ModalDialog):
    """Edit the 10 remark labels."""

    def __init__(self, app):
        super().__init__(app.root, 'REMARK_DLG', custom={101: self._make_list})
        self.app = app
        self.form.command(1, self.ok)
        self.entry = self.form.w[102]
        self.entry.bind('<KeyRelease>', self._typed)
        self.entry.bind('<Return>', lambda e: self.ok())
        self.fill()
        self.top.after_idle(lambda: self.lv.select(0, notify=True))

    def _make_list(self, form, it):
        self.lv = ui.ListView(form.parent, on_select=self._pick)
        return self.lv

    def fill(self):
        lib = self.app.lib
        self.lv.set_items([lib.remark_label(n) or str(n) for n in range(1, 11)])

    def _pick(self, i):
        set_entry(self.entry, self.app.lib.remark_label(i + 1))
        self.entry.focus_set()
        self.entry.select_range(0, 'end')

    def _typed(self, e):
        i = self.lv.current()
        if i is not None:
            self.app.lib.set_remark_label(i + 1, self.entry.get())
            self.app.set_dirty()
            self.fill()


def remark_combo(app, combo, kind, index, on_change):
    lib = app.lib
    labels = [''] + [lib.remark_label(n) or str(n) for n in range(1, 11)]
    combo_set(combo, labels, lib.remark_of(kind, index))

    def picked(e):
        lib.set_remark_of(kind, index, combo.current())
        combo.selection_clear()
        on_change()
    combo.bind('<<ComboboxSelected>>', picked)


# =================================================================== MIDI setup
class MidiSetupDialog(ModalDialog):
    def __init__(self, app):
        super().__init__(app.root, 'MIDISETUP_DLG')
        self.app = app
        f = self.form
        midi = app.midi
        self.ins = ['None'] + midi.input_names()
        self.outs = ['None'] + midi.output_names()
        combo_set(f.w[101], self.ins, self.ins.index(midi.in_name) if midi.in_name in self.ins else 0)
        combo_set(f.w[102], self.outs, self.outs.index(midi.out_name) if midi.out_name in self.outs else 0)
        sp = f.w[103]
        sp.lo, sp.hi, sp.fmt = 0, 15, PR.plus1
        sp.set(app.settings.get('excl_channel', 0))
        f.command(3, self.make_default)
        if not midi.available:
            ttk.Label(self.frame, text=midi.error or '', foreground='#a00000').place(
                x=Scale.x(8), y=Scale.y(76))

    def apply(self):
        f = self.form
        app = self.app
        try:
            i = f.w[101].current()
            app.midi.open_input(self.ins[i] if i > 0 else None)
            o = f.w[102].current()
            app.midi.open_output(self.outs[o] if o > 0 else None)
        except Exception as e:
            messagebox.showerror('MIDI Setup', str(e), parent=self.top)
            return False
        app.settings['excl_channel'] = f.w[103].value
        app.device.target = None
        return True

    def make_default(self):
        if self.apply():
            self.app.save_settings()

    def ok(self):
        if self.apply():
            self.app.save_settings()
            self.app.refresh_status()
            super().ok()


# =================================================================== preferences
PREF_KEYS = {100: 'startup_rx', 101: 'startup_multi', 102: 'startup_prog', 103: 'startup_combi',
             104: 'startup_drum', 105: 'startup_fx', 106: 'startup_global',
             113: 'open_tx', 114: 'open_multi', 115: 'open_prog', 116: 'open_combi', 117: 'open_drum',
             118: 'open_fx', 119: 'open_global',
             108: 'auto_multi', 109: 'auto_prog', 110: 'auto_combi', 112: 'auto_fx', 120: 'fix_part_ch'}


class PreferencesDialog(ModalDialog):
    def __init__(self, app):
        super().__init__(app.root, 'PREFERENCE_DLG')
        self.app = app
        f = self.form
        prefs = app.settings.setdefault('prefs', {})
        for cid, key in PREF_KEYS.items():
            f.check(cid, 1 if prefs.get(key) else 0)
        for cid in (100, 113):
            f.command(cid, self.update_states)
        combo_set(f.w[121], ['Program', 'Combination'], prefs.get('x5_effect', 0))
        self.update_states()

    def update_states(self):
        f = self.form
        for master, subs in ((100, range(101, 107)), (113, range(114, 120))):
            on = bool(f.check(master))
            for cid in subs:
                f.enable(cid, on)

    def ok(self):
        prefs = self.app.settings.setdefault('prefs', {})
        for cid, key in PREF_KEYS.items():
            prefs[key] = bool(self.form.check(cid))
        prefs['x5_effect'] = self.form.w[121].current()
        self.app.save_settings()
        super().ok()


# =================================================================== about
class AboutDialog(ModalDialog):
    def __init__(self, app):
        super().__init__(app.root, 'ABOUT_DLG', title='About  NS5R SoundEditor')
        f = self.form
        f.set_text(301, 'KORG NS5R SoundEditor')
        f.set_text(302, f'Python port {__version__} (Windows Version 1.04)')
        ver = app.device_version
        txt = f'KORG NS5R  System Version {ver[0]}.{ver[1]:02d}' if ver else 'Dump receive is not available.'
        lab = tk.Label(self.frame, text=txt, bg=ui.FACE, bd=Scale.px(1), relief='sunken', font=ui.font())
        lab.place(x=Scale.x(6), y=Scale.y(27), width=Scale.x(154), height=Scale.y(12))


# =================================================================== dumps
DUMP_KINDS = {101: 'all_multi', 102: 'all_program', 103: 'all_combi', 104: 'all_drum', 105: 'all_effect',
              106: 'global'}


class DumpDialog(ModalDialog):
    """Choose which banks to transmit / receive (MIDI > Transmit..., Receive...)."""

    def __init__(self, app, title):
        super().__init__(app.root, 'DUMP_DLG', title=title)
        f = self.form
        for cid in DUMP_KINDS:
            f.command(cid, self.sync)
        f.command(108, self.all)
        f.check(108, 1)
        self.all()

    def all(self):
        on = self.form.check(108)
        for cid in DUMP_KINDS:
            self.form.check(cid, on)

    def sync(self):
        self.form.check(108, int(all(self.form.check(c) for c in DUMP_KINDS)))

    def ok(self):
        self.result = [k for c, k in DUMP_KINDS.items() if self.form.check(c)]
        self.close()


def ttk_text(t):
    return t.replace('&&', '\0').replace('&', '').replace('\0', '&')


class TransmitAsDialog(ModalDialog):
    def __init__(self, app, what, current):
        super().__init__(app.root, 'DUMP_GETTXNO_DLG')
        self.form.set_text(101, f' {what} ')
        sp = self.form.w[102]
        sp.lo, sp.hi, sp.fmt = 0, 127, PR.plus1
        sp.set(current)

    def ok(self):
        self.result = self.form.w[102].value
        self.close()


class ReceiveAsDialog(ModalDialog):
    """Pick a source bank/program on the NS5R to receive into the current slot."""

    def __init__(self, app, kind):
        super().__init__(app.root, 'DUMP_GETRXNO_DLG')
        self.app, self.kind = app, kind
        f = self.form
        if kind == 'program':
            self.banks = [68, 69, 70, 71]
        elif kind == 'combi':
            self.banks = [72, 73, 74, 75]
        else:
            self.banks = list(range(8))       # effect banks
        b = f.w[850]
        b.lo, b.hi = 0, len(self.banks) - 1
        b.fmt = self.bank_text
        b.on_change = lambda v: self.update()
        b.set(0)
        p = f.w[851]
        p.lo, p.hi, p.fmt = 0, 127, PR.plus1
        p.on_change = lambda v: self.update()
        p.set(0)
        f.command(104, self.bank_list)
        f.command(103, self.prog_list)
        if kind == 'effect':
            f.set_text(102, 'Fx No.')
        self.update()

    def bank_text(self, i):
        b = self.banks[i]
        if self.kind == 'effect':
            return N.FX_BANKS[b]
        return N.bank_name(b)

    def name(self, prog):
        b = self.banks[self.form.w[850].value]
        if self.kind == 'effect':
            return N.fx_name(b, prog, self.app.lib)
        return N.program_name(b, prog, self.app.lib)

    def update(self):
        set_entry(self.form.w[101], self.name(self.form.w[851].value))

    def bank_list(self):
        r = NameListDialog(self.top, 'Bank Name List', [self.bank_text(i) for i in range(len(self.banks))],
                           self.form.w[850].value, col_width=68).show()
        if r is not None:
            self.form.w[850].set(r)
            self.update()

    def prog_list(self):
        title = 'Effect Name List' if self.kind == 'effect' else 'Program Name List'
        r = NameListDialog(self.top, title, [N.numbered(p, self.name(p)) for p in range(128)],
                           self.form.w[851].value).show()
        if r is not None:
            self.form.w[851].set(r)
            self.update()

    def ok(self):
        b = self.banks[self.form.w[850].value]
        self.result = (b, self.form.w[851].value)
        self.close()


# =================================================================== exchange / copy
class ExchangeDialog(ModalDialog):
    def __init__(self, app, kind, current):
        super().__init__(app.root, 'EXCHANGE_DLG')
        self.app, self.kind = app, kind
        what = {'program': 'Program', 'combi': 'Combination', 'effect': 'Effect'}[kind]
        f = self.form
        f.set_text(100, f'Exchange following {what}s')
        f.set_text(104, f' {what} A ')
        f.set_text(108, f' {what} B ')
        for sp_id, name_id, btn, start in ((801, 802, 103, current), (805, 806, 107, (current + 1) % 128)):
            sp = f.w[sp_id]
            sp.lo, sp.hi, sp.fmt = 0, 127, PR.plus1
            sp.on_change = lambda v, n=name_id: set_entry(f.w[n], self.name(v))
            sp.set(start)
            set_entry(f.w[name_id], self.name(start))
            f.command(btn, lambda s=sp, n=name_id: self.pick(s, n))

    def name(self, i):
        lib = self.app.lib
        return {'program': lib.program_name, 'combi': lib.combi_name, 'effect': lib.effect_name}[self.kind](i)

    def pick(self, sp, name_id):
        items = [N.numbered(i, self.name(i)) for i in range(128)]
        r = NameListDialog(self.top, 'Name List', items, sp.value).show()
        if r is not None:
            sp.set(r)
            set_entry(self.form.w[name_id], self.name(r))

    def ok(self):
        self.result = (self.form.w[801].value, self.form.w[805].value)
        self.close()


class OscCopyDialog(ModalDialog):
    def __init__(self, app, current):
        super().__init__(app.root, 'OSCCOPY_DLG')
        self.app = app
        f = self.form
        for sp_id, name_id, btn, combo, start in ((801, 802, 103, 104, current),
                                                  (805, 806, 107, 108, (current + 1) % 128)):
            sp = f.w[sp_id]
            sp.lo, sp.hi, sp.fmt = 0, 127, PR.plus1
            sp.on_change = lambda v, n=name_id: set_entry(f.w[n], app.lib.program_name(v))
            sp.set(start)
            set_entry(f.w[name_id], app.lib.program_name(start))
            f.command(btn, lambda s=sp, n=name_id: self.pick(s, n))
            combo_set(f.w[combo], ['OSC1', 'OSC2'], 0)

    def pick(self, sp, name_id):
        items = [N.numbered(i, self.app.lib.program_name(i)) for i in range(128)]
        r = NameListDialog(self.top, 'Program Name List', items, sp.value).show()
        if r is not None:
            sp.set(r)
            set_entry(self.form.w[name_id], self.app.lib.program_name(r))

    def ok(self):
        f = self.form
        self.result = (f.w[801].value, f.w[104].current(), f.w[805].value, f.w[108].current())
        self.close()


EG_RANGES = {'pitch': (18, 24), 'vdf': (41, 49), 'vda': (62, 69)}   # relative OSC offsets


class EgCopyDialog(ModalDialog):
    """EG Copy and Swap between OSC1 and OSC2 of one program."""

    def __init__(self, app):
        super().__init__(app.root, 'EG_COPY_DLG')
        f = self.form
        for chk, combo in ((104, 103), (108, 107), (112, 111)):
            f.check(chk, 1)
            combo_set(f.w[combo], ['OSC1 -> OSC2', 'OSC1 <- OSC2'], 0)
        for r in (101, 105, 109):
            f.vars[r].set(r)

    def ok(self):
        f = self.form
        res = []
        for kind, chk, swap, combo in (('pitch', 104, 101, 103), ('vdf', 108, 105, 107), ('vda', 112, 109, 111)):
            if f.check(chk):
                op = 'swap' if f.vars[swap].get() == swap else ('1to2' if f.w[combo].current() == 0 else '2to1')
                res.append((kind, op))
        self.result = res
        self.close()


class EditLevelDialog(ModalDialog):
    """Edit OSC Level: change many levels at once.  Returns a function old -> new (by position)."""

    def __init__(self, master):
        super().__init__(master, 'EDIT_LEVEL_DLG')
        f = self.form
        for cid, v in ((106, 127), (107, 50), (108, 10), (109, 127), (110, 65), (111, 127)):
            set_entry(f.w[cid], str(v))
        f.vars[101].set(101)

    def num(self, cid):
        try:
            return int(self.form.w[cid].get())
        except ValueError:
            return 0

    def ok(self):
        mode = self.form.vars[101].get()
        n = self.num
        clip = lambda v: max(0, min(127, int(round(v))))  # noqa: E731
        if mode == 101:
            fn = lambda vals: [clip(n(106))] * len(vals)  # noqa: E731
        elif mode == 102:
            fn = lambda vals: [clip(v * n(107) / 100) for v in vals]  # noqa: E731
        elif mode == 103:
            fn = lambda vals: [clip(v + n(108)) for v in vals]  # noqa: E731
        elif mode == 104:
            def fn(vals):
                m = max(vals) or 1
                return [clip(v * n(109) / m) for v in vals]
        else:
            def fn(vals):
                k = len(vals)
                a, b = n(110), n(111)
                return [clip(a + (b - a) * i / max(1, k - 1)) for i in range(k)]
        self.result = fn
        self.close()


class CompareDialog(ModalDialog):
    """Compare Sound: switch between the edited data and the data before editing."""

    def __init__(self, app, on_switch):
        super().__init__(app.root, 'COMPARE_DLG')
        f = self.form
        f.vars[101].set(101)
        f.command(101, lambda: on_switch(True))
        f.command(102, lambda: on_switch(False))
        f.command(10401, app.show_keyboard)
        self.on_switch = on_switch

    def ok(self):
        self.on_switch(True)
        self.result = True
        self.close()

    def cancel(self):
        self.on_switch(False)
        self.result = False
        self.close()


class ChoiceDialog(ModalDialog):
    """IMPORT_SEL_DLG: pick one entry from a list."""

    def __init__(self, master, title, label, items, current=0):
        super().__init__(master, 'IMPORT_SEL_DLG', title=title, custom={101: self._make})
        self.form.set_text(65535, label) if 65535 in self.form.w else None
        self.lv.set_items(items)
        self.lv.on_double = lambda i: self.ok()
        self.top.after_idle(lambda: self.lv.select(current))
        lab = [w for it, w in self.form.all if it['cls'] == 'STATIC']
        if lab:
            lab[0].config(text=label)

    def _make(self, form, it):
        self.lv = ui.ListView(form.parent)
        return self.lv

    def ok(self):
        self.result = self.lv.current()
        self.close()


class StatusDialog:
    """Small non-modal status window ('Please wait...', dump progress)."""

    def __init__(self, app, text, cancel=None):
        self.top = tk.Toplevel(app.root, bg=ui.FACE)
        self.top.title('NS5R SoundEditor')
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.label = tk.Label(self.top, text=text, bg=ui.FACE, font=ui.font(), padx=Scale.px(16),
                              pady=Scale.px(10))
        self.label.pack()
        if cancel:
            ttk.Button(self.top, text='Cancel', command=cancel).pack(pady=(0, Scale.px(8)))
        self.top.protocol('WM_DELETE_WINDOW', cancel or (lambda: None))
        self.top.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - self.top.winfo_reqwidth()) // 2
        y = app.root.winfo_rooty() + app.root.winfo_height() // 3
        self.top.geometry(f'+{x}+{y}')

    def set(self, text):
        self.label.config(text=text)

    def close(self):
        if self.top.winfo_exists():
            self.top.destroy()


# =================================================================== keyboard window
class KeyboardWindow:
    """KEYBOARD_DLG: play notes on the NS5R from the mouse or the computer keyboard."""
    QWERTY = {c: i for i, c in enumerate('awsedftgyhujkolp;')}

    def __init__(self, app):
        self.app = app
        st = app.settings.setdefault('keyboard', {})
        self.base = st.get('base', 36)       # C2
        self.top = tk.Toplevel(app.root, bg=ui.FACE)
        self.top.title('Keyboard')
        self.top.resizable(False, False)
        self.top.protocol('WM_DELETE_WINDOW', self.close)
        w, h = Scale.x(181), Scale.y(114)
        frame = tk.Frame(self.top, bg=ui.FACE, width=w, height=h)
        frame.pack()
        from .forms import Form
        self.form = f = Form(frame, 'KEYBOARD_DLG', custom={
            3: lambda form, it: ui.Keyboard(frame, 0, 127, on_click=self.page_to, highlight=self.mini_hl),
            16: lambda form, it: ui.Keyboard(frame, self.base, self.base + 59, on_press=self.note_on,
                                             on_release=self.note_off),
            4: lambda form, it: ttk.Scrollbar(frame, orient='horizontal', command=self.scroll),
            17: lambda form, it: ttk.Scale(frame, orient='horizontal', from_=-8192, to=8191,
                                           command=self.bend)})
        f.command(1, self.close)
        f.command(50, self.center)
        ch = f.w[14]
        ch.lo, ch.hi, ch.fmt = 0, 15, PR.plus1
        ch.set(st.get('channel', 0))
        vel = f.w[7]
        vel.lo, vel.hi = 1, 127
        vel.set(st.get('velocity', 100))
        f.command(9, self.damper)
        self.keys, self.mini = f.w[16], f.w[3]
        self.down = {}
        self.update_range()
        for seq in ('<KeyPress>', '<KeyRelease>'):
            self.top.bind(seq, self.computer_key)
        self.top.focus_set()

    def mini_hl(self, n):
        if self.base <= n < self.base + 60:
            return '#c0c0ff' if n % 12 not in ui.BLACK else '#202080'
        return None

    def update_range(self):
        self.base = max(0, min(68, self.base))
        self.keys.set_range(self.base, self.base + 59)
        self.mini.draw()
        self.form.set_text(5, N.note_name(self.base).replace(' ', ''))
        self.form.set_text(6, N.note_name(self.base + 59).replace(' ', ''))
        lo = self.base / 128
        self.form.w[4].set(lo, (self.base + 60) / 128)

    def page_to(self, n):
        self.base = (n // 12) * 12 - 24
        self.update_range()

    def scroll(self, *a):
        if a[0] == 'moveto':
            self.base = int(float(a[1]) * 128 / 12 + 0.5) * 12
        else:
            self.base += 12 * int(a[1])
        self.update_range()

    @property
    def channel(self):
        return self.form.w[14].value

    def note_on(self, n):
        self.app.midi_safe(lambda m: m.note_on(self.channel, n, self.form.w[7].value))

    def note_off(self, n):
        self.app.midi_safe(lambda m: m.note_off(self.channel, n))

    def bend(self, v):
        v = int(float(v))
        self.form.set_text(18, f'{v * 64 // 8192:+d}')
        self.app.midi_safe(lambda m: m.pitch_bend(self.channel, v))

    def center(self):
        self.form.w[17].set(0)

    def damper(self):
        on = self.form.check(9)
        self.app.midi_safe(lambda m: m.control(self.channel, 64, 127 if on else 0))

    def computer_key(self, e):
        if isinstance(e.widget, tk.Entry):
            return
        c = e.char.lower() if e.char else ''
        if c in ('z', 'x') and e.type == tk.EventType.KeyPress:
            self.base += -12 if c == 'z' else 12
            self.update_range()
            return
        if c not in self.QWERTY:
            return
        n = self.base + 24 + self.QWERTY[c]
        if e.type == tk.EventType.KeyPress:
            if c not in self.down:
                self.down[c] = n
                self.keys.press(n)
        elif c in self.down:
            self.keys.release(self.down.pop(c))

    def close(self):
        st = self.app.settings.setdefault('keyboard', {})
        st.update(base=self.base, channel=self.channel, velocity=self.form.w[7].value)
        for n in list(self.keys.down):
            self.keys.release(n)
        self.top.destroy()
        self.app.keyboard = None

