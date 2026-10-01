"""NS5R SoundEditor main window and application logic."""
import json
import os
import queue
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import device as D
from . import dialogs as DL
from . import editors as E
from . import fileio
from . import model as M
from . import names as N
from . import pages as PG
from . import sysex as X
from . import ui
from .midi_io import Midi
from .ui import Scale

APP_NAME = 'NS5R SoundEditor'
SETTINGS = os.path.join(os.path.expanduser('~'), '.ns5rse_settings.json')
SCALE_CHOICES = [(0, 'Automatic'), (1, '1x'), (2, '2x'), (3, '3x')]
KIND_TITLE = {'program': 'Program', 'combi': 'Combination', 'effect': 'Effect', 'multi': 'Multi',
              'drum': 'Drum Kit', 'global': 'Global'}
ALL_TITLE = {'all_multi': 'All Multi', 'all_program': 'All Program', 'all_combi': 'All Combination',
             'all_drum': 'All Drum Kit', 'all_effect': 'All Effect', 'global': 'Global'}
FILETYPES = [('NS5 Files', '*.NS5 *.ns5'), ('SysEx / SMF', '*.syx *.SYX *.mid *.MID'), ('All Files', '*')]


def enable_windows_dpi_awareness():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


class App:
    def __init__(self, scale=None, path=None):
        enable_windows_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()
        self.settings = self.load_settings()
        self.scale_choice = scale or self.settings.get('scale')
        Scale.s = self.scale_choice or self.auto_scale()
        ui.reset_caches()
        ui.setup_style(self.root)
        self.lib = M.Library()
        self.midi = Midi()
        self.device = D.Device(self)
        self.device_version = None
        self.path = None
        self.untitled = 1
        self.dirty = False
        self.keyboard = None
        self.windows = []          # non-modal editors to refresh (drum kit lists)
        self.clipboard = None      # (kind, [blocks])
        self.compare_base = {}
        self.expect = []           # pending dump requests
        self.status_dialog = None
        self.exclusive_log = None
        self.redump_jobs = {}
        self.mod = 'Command' if sys.platform == 'darwin' else 'Control'
        self.build_menu()
        self.build_window()
        self.set_icon()
        self.open_saved_ports()
        if path:
            self.load(path)
        self.update_title()
        self.root.deiconify()
        self.root.after(50, self.poll_midi)
        self.root.after(300, self.startup)

    # ------------------------------------------------------------ settings
    def load_settings(self):
        try:
            with open(SETTINGS) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        self.settings.update(out=self.midi.out_name, inp=self.midi.in_name)
        try:
            with open(SETTINGS, 'w') as f:
                json.dump(self.settings, f, indent=1)
        except OSError:
            pass

    def prefs(self):
        return self.settings.get('prefs', {})

    def open_saved_ports(self):
        try:
            if self.settings.get('out') in self.midi.output_names():
                self.midi.open_output(self.settings['out'])
            if self.settings.get('inp') in self.midi.input_names():
                self.midi.open_input(self.settings['inp'])
        except Exception as e:
            self.status(f'MIDI: {e}')
        self.refresh_status()

    def auto_scale(self):
        h = self.root.winfo_screenheight()
        return 3 if h >= 2000 else 2 if h >= 900 else 1

    # ------------------------------------------------------------ menus
    def build_menu(self):
        root, mod = self.root, self.mod
        acc = 'Cmd' if mod == 'Command' else 'Ctrl'
        mb = tk.Menu(root)

        def add(menu, label, cmd, key=None, shortcut=True):
            menu.add_command(label=label, command=cmd, accelerator=f'{acc}+{key}' if key else None)
            if key and shortcut:
                root.bind_all(f'<{mod}-{key.lower()}>', lambda e: (cmd(), 'break')[1])

        if sys.platform == 'darwin':
            apple = tk.Menu(mb, name='apple', tearoff=0)
            apple.add_command(label='About NS5R SoundEditor', command=self.about)
            mb.add_cascade(menu=apple)
            root.createcommand('tk::mac::Quit', self.quit)
            root.createcommand('::tk::mac::OpenDocument', self.open_documents)
            root.createcommand('::tk::mac::ShowPreferences', self.preferences)
        f = tk.Menu(mb, tearoff=0)
        add(f, 'New', self.new, 'N')
        add(f, 'Open...', self.open, 'O')
        f.add_separator()
        add(f, 'Close', self.close_doc)
        add(f, 'Save', self.save, 'S')
        add(f, 'Save as...', self.save_as)
        f.add_separator()
        add(f, 'Import...', self.import_file)
        add(f, 'Export...', self.export_file)
        f.add_separator()
        add(f, 'Quit' if sys.platform == 'darwin' else 'Exit', self.quit, 'Q')
        mb.add_cascade(label='File', menu=f)
        e = tk.Menu(mb, tearoff=0)
        add(e, 'Cut', self.cut, 'X', shortcut=False)
        add(e, 'Copy', self.copy, 'C', shortcut=False)
        add(e, 'Paste', self.paste, 'V', shortcut=False)
        add(e, 'Clear', self.clear)
        e.add_separator()
        add(e, 'Compare...', self.compare)
        add(e, 'Exchange...', self.exchange)
        add(e, 'EG Copy & Swap...', self.eg_copy)
        add(e, 'OSC Parameter Copy...', self.osc_copy)
        add(e, 'Change OSC Level...', self.change_levels)
        self.edit_menu = e
        mb.add_cascade(label='Edit', menu=e)
        for key, fn in (('x', self.cut), ('c', self.copy), ('v', self.paste)):
            root.bind_all(f'<{mod}-{key}>', lambda ev, fn=fn: None if isinstance(ev.widget, tk.Entry) else fn())
        m = tk.Menu(mb, tearoff=0)
        add(m, 'MIDI Setup...', self.midi_setup, 'M')
        m.add_separator()
        add(m, 'Receive...', self.receive_all, 'R')
        add(m, 'Transmit...', self.transmit_all, 'T')
        m.add_separator()
        reset = tk.Menu(m, tearoff=0)
        add(reset, 'All Parameter Reset', lambda: self.device.reset('all'))
        add(reset, 'Drum Setup Reset', lambda: self.device.reset('drum'))
        add(reset, 'System Reset 1 (XG)', lambda: self.device.reset('xg'))
        add(reset, 'System Reset 2 (GS)', lambda: self.device.reset('gs'))
        add(reset, 'GM Mode ON', self.device.gm_on)
        m.add_cascade(label='Reset', menu=reset)
        add(m, 'All Notes Off', self.device.all_notes_off)
        mb.add_cascade(label='MIDI', menu=m)
        o = tk.Menu(mb, tearoff=0)
        self.show_excl = tk.BooleanVar(value=False)
        o.add_checkbutton(label='Show Exclusive Data', variable=self.show_excl, command=self.toggle_excl)
        o.add_separator()
        add(o, 'Remark List...', lambda: (DL.RemarkDialog(self).show(), self.refresh_all()))
        o.add_separator()
        if sys.platform != 'darwin':
            add(o, 'Preferences...', self.preferences)
            sc = tk.Menu(o, tearoff=0)
            self.scale_var = tk.IntVar(value=self.scale_choice or 0)
            for value, label in SCALE_CHOICES:
                sc.add_radiobutton(label=label, value=value, variable=self.scale_var,
                                   command=lambda: self.set_scale(self.scale_var.get() or None))
            o.add_cascade(label='Scale', menu=sc)
        else:
            sc = tk.Menu(o, tearoff=0)
            self.scale_var = tk.IntVar(value=self.scale_choice or 0)
            for value, label in SCALE_CHOICES:
                sc.add_radiobutton(label=label, value=value, variable=self.scale_var,
                                   command=lambda: self.set_scale(self.scale_var.get() or None))
            o.add_cascade(label='Scale', menu=sc)
        mb.add_cascade(label='Options', menu=o)
        w = tk.Menu(mb, tearoff=0)
        add(w, 'Keyboard', self.show_keyboard, 'K')
        w.add_separator()
        kits = tk.Menu(w, tearoff=0)
        for k in range(M.N_KITS):
            kits.add_command(label=f'User Kit {k + 1}', command=lambda k=k: self.edit_user_kit(k))
        kits.add_separator()
        for mm in range(M.N_MULTIS):
            for d in range(4):
                kits.add_command(label=f'Multi {mm + 1}: Modify Drum {d + 1}',
                                 command=lambda mm=mm, d=d: self.edit_multi_kit(mm, d))
        w.add_cascade(label='Drum Kit Edit', menu=kits)
        mb.add_cascade(label='Window', menu=w)
        h = tk.Menu(mb, tearoff=0, name='help' if sys.platform == 'darwin' else None)
        add(h, 'About...', self.about)
        mb.add_cascade(label='Help', menu=h)
        root.config(menu=mb)

    def set_icon(self):
        self._icons = [tk.PhotoImage(file=ui.R.image_path('icon_32')), tk.PhotoImage(file=ui.R.image_path('icon_16'))]
        if sys.platform != 'darwin':
            self.root.iconphoto(True, *self._icons)

    # ------------------------------------------------------------ window
    def build_window(self):
        root = self.root
        root.resizable(False, False)
        root.protocol('WM_DELETE_WINDOW', self.quit)
        self.main = tk.Frame(root, bg=ui.FACE, width=Scale.x(364), height=Scale.y(222))
        self.main.pack()
        self.nb = ttk.Notebook(self.main, takefocus=0)
        ui.place(self.nb, (3, 3, 358, 216))
        self.pages = {}
        for key, cls, title in (('multi', PG.MultiPage, 'Multi'), ('global', PG.GlobalPage, 'Global'),
                                ('program', PG.ProgramPage, 'User Prog'), ('combi', PG.CombiPage, 'User Combi'),
                                ('effect', PG.EffectPage, 'User Effect')):
            page = cls(self, self.nb)
            self.pages[key] = page
            self.nb.add(page.frame, text=title)
        self.nb.select(self.settings.get('tab', 2))
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.update_edit_menu())
        self.statusbar = tk.Label(root, anchor='w', bg=ui.FACE, fg=ui.TEXT, font=ui.font('small'), bd=Scale.px(1),
                                  relief='sunken', padx=Scale.px(4))
        self.statusbar.pack(fill='x', side='bottom')
        self.refresh_status()
        self.update_edit_menu()

    def current_page(self):
        return self.pages[list(self.pages)[self.nb.index('current')]]

    def set_scale(self, choice):
        self.scale_choice = choice
        self.settings['scale'] = choice
        self.save_settings()
        if hasattr(self, 'scale_var'):
            self.scale_var.set(choice or 0)
        s = choice or self.auto_scale()
        if s == Scale.s:
            return
        self.settings['tab'] = self.nb.index('current')
        if self.keyboard:
            self.keyboard.close()
        for w in list(self.windows):
            w.close()
        Scale.s = s
        ui.reset_caches()
        ui.setup_style(self.root)
        self.main.destroy()
        self.statusbar.destroy()
        self.build_window()

    def update_title(self):
        name = os.path.basename(self.path) if self.path else f'Untitled-{self.untitled}'
        self.root.title(f"{APP_NAME} [{name}]{' *' if self.dirty else ''}")

    def status(self, text):
        self.statusbar.config(text=text)

    def refresh_status(self):
        midi = self.midi
        on = midi.out is not None
        out = midi.out_name or 'no MIDI output (MIDI > MIDI Setup...)'
        inp = f'   In: {midi.in_name}' if midi.in_name else ''
        if not midi.available:
            out = midi.error
        self.status(f'Out: {out}{inp}   Exclusive Channel: {self.settings.get("excl_channel", 0) + 1}')
        for p in getattr(self, 'pages', {}).values():
            p.set_midi_enabled(on)

    def update_edit_menu(self):
        kind = self.current_page().kind
        e = self.edit_menu
        bank = kind in ('program', 'combi', 'effect')
        for label in ('Cut', 'Copy', 'Paste', 'Clear', 'Exchange...'):
            e.entryconfig(label, state='normal' if bank else 'disabled')
        for label in ('EG Copy & Swap...', 'OSC Parameter Copy...', 'Change OSC Level...'):
            e.entryconfig(label, state='normal' if kind == 'program' else 'disabled')
        e.entryconfig('Compare...', state='normal' if kind != 'global' else 'disabled')

    # ------------------------------------------------------------ data changes
    def set_dirty(self):
        if not self.dirty:
            self.dirty = True
            self.update_title()

    def edited(self, kind, index, offsets):
        """Called by every editor after it changed bytes of a block."""
        offsets = list(offsets)
        self.set_dirty()
        self.refresh_kind(kind, names=any(o < 10 for o in offsets) or kind == 'multi')
        try:
            self.device.edited(kind, index, offsets)
        except Exception as e:
            self.status(f'MIDI error: {e}')

    def refresh_kind(self, kind, names=False):
        page = self.pages.get(kind)
        if kind == 'drum':
            for p in ('multi',):
                self.pages[p].fill()
        if page is not None:
            if names:
                page.fill()
            page.refresh()
        if kind == 'program':          # combis / multis show user program names
            self.pages['combi'].refresh()
            self.pages['multi'].fill()
        if kind == 'combi':
            self.pages['multi'].fill()
        if kind == 'effect':
            for k in ('program', 'combi', 'multi'):
                self.pages[k].refresh()
        for w in list(self.windows):
            w.refresh()

    def refresh_all(self):
        for p in self.pages.values():
            p.fill()
            p.refresh()
        for w in list(self.windows):
            w.refresh()

    def item_selected(self, kind, index):
        self.compare_base.setdefault((kind, index), bytes(self.lib.block(kind, index)))
        auto = {'program': 'auto_prog', 'combi': 'auto_combi', 'effect': 'auto_fx', 'multi': 'auto_multi'}
        if self.midi.out and self.prefs().get(auto.get(kind, ''), False):
            self.device.select(kind, index)

    # ------------------------------------------------------------ editors
    def edit_program_common(self, i):
        E.ProgGeneralDialog(self, i).show()

    def edit_osc(self, i, tab=0, osc=0):
        E.OscDialog(self, i, tab, osc).show()

    def edit_combi_common(self, i):
        E.CombiGeneralDialog(self, i).show()

    def edit_timbre(self, i, t):
        E.TimbreDialog(self, i, t).show()

    def edit_effect(self, i):
        E.EffectEditDialog(self, i).show()

    def edit_multi_common(self, m):
        E.MultiCommonDialog(self, m).show()

    def edit_part(self, m, part):
        E.MultiPartDialog(self, m, part).show()

    def edit_global(self):
        E.GlobalEditDialog(self).show()

    def edit_user_kit(self, k):
        E.DrumKitWindow(self, E.KitRef(self, 'drum', k, 0, f'User Kit {k + 1}'))

    def edit_multi_kit(self, m, d):
        E.DrumKitWindow(self, E.KitRef(self, 'multi', m, M.MULTI_KITS + d * M.KIT_SIZE,
                                       f'Multi {m + 1} Modify Drum {d + 1}'))

    def edit_drum_kit_for_program(self, i):
        p = self.lib.programs[i]
        k = ((p[M.OSC1] << 8) | p[M.OSC1 + 1]) & 1
        self.edit_user_kit(k)

    def show_keyboard(self):
        if self.keyboard:
            self.keyboard.top.lift()
        else:
            self.keyboard = DL.KeyboardWindow(self)

    def midi_safe(self, fn):
        try:
            fn(self.midi)
        except Exception as e:
            self.status(f'MIDI error: {e}')

    # ------------------------------------------------------------ Edit menu
    def bank_selection(self):
        page = self.current_page()
        if page.kind not in ('program', 'combi', 'effect'):
            return None, []
        return page.kind, page.selection()

    def blocks(self, kind):
        return {'program': self.lib.programs, 'combi': self.lib.combis, 'effect': self.lib.effects}[kind]

    def copy(self):
        kind, sel = self.bank_selection()
        if kind:
            self.clipboard = (kind, [bytes(self.blocks(kind)[i]) for i in sel])

    def cut(self):
        self.copy()
        self.clear()

    def paste(self):
        kind, sel = self.bank_selection()
        if not kind or not self.clipboard or self.clipboard[0] != kind:
            self.root.bell()
            return
        start = sel[0]
        items = self.clipboard[1]
        blocks = self.blocks(kind)
        for k, data in enumerate(items):
            if start + k < 128:
                blocks[start + k][:] = data
        self.set_dirty()
        self.refresh_kind(kind, names=True)

    def clear(self):
        kind, sel = self.bank_selection()
        if not kind:
            return
        init = {'program': M.init_program, 'combi': M.init_combi, 'effect': M.init_effect}[kind]
        for i in sel:
            self.blocks(kind)[i][:] = init()
        self.set_dirty()
        self.refresh_kind(kind, names=True)

    def compare(self):
        page = self.current_page()
        kind = page.kind
        index = page.current()
        if kind == 'multi':
            index = page.current()
        buf = self.lib.block(kind, index)
        cur = bytes(buf)
        prev = self.compare_base.get((kind, index), cur)

        def switch(current):
            buf[:] = cur if current else prev
            self.refresh_kind(kind, names=True)
            if self.midi.out:
                self.device.select(kind, index)
        r = DL.CompareDialog(self, switch).show()
        if r:
            self.compare_base[(kind, index)] = cur
        else:
            self.set_dirty()

    def exchange(self):
        kind, sel = self.bank_selection()
        if not kind:
            return
        r = DL.ExchangeDialog(self, kind, sel[0]).show()
        if r:
            a, b = r
            blocks = self.blocks(kind)
            blocks[a], blocks[b] = blocks[b], blocks[a]
            self.set_dirty()
            self.refresh_kind(kind, names=True)

    def eg_copy(self):
        i = self.pages['program'].current()
        r = DL.EgCopyDialog(self).show()
        if not r:
            return
        p = self.lib.programs[i]
        offs = []
        for kind, op in r:
            lo, hi = DL.EG_RANGES[kind]
            a, b = M.OSC1 + lo, M.OSC2 + lo
            n = hi - lo
            if op == 'swap':
                p[a:a + n], p[b:b + n] = p[b:b + n], p[a:a + n]
            elif op == '1to2':
                p[b:b + n] = p[a:a + n]
            else:
                p[a:a + n] = p[b:b + n]
            offs += list(range(a, a + n)) + list(range(b, b + n))
        self.edited('program', i, offs)

    def osc_copy(self):
        i = self.pages['program'].current()
        r = DL.OscCopyDialog(self, i).show()
        if not r:
            return
        src, so, dst, do = r
        a = M.OSC1 + so * M.OSC_SIZE
        b = M.OSC1 + do * M.OSC_SIZE
        self.lib.programs[dst][b:b + M.OSC_SIZE] = self.lib.programs[src][a:a + M.OSC_SIZE]
        self.edited('program', dst, range(b, b + M.OSC_SIZE))

    def change_levels(self):
        page = self.pages['program']
        sel = page.selection()
        if len(sel) == 1:
            sel = list(range(128))
        fn = DL.EditLevelDialog(self.root).show()
        if not fn:
            return
        for osc in (M.OSC1, M.OSC2):
            vals = [self.lib.programs[i][osc + 3] for i in sel]
            for i, v in zip(sel, fn(vals)):
                self.lib.programs[i][osc + 3] = v
        self.set_dirty()
        self.refresh_kind('program')
        self.device.target = None

    # ------------------------------------------------------------ MIDI: transmit / receive
    def require_out(self):
        if self.midi.out is None:
            messagebox.showinfo(APP_NAME, 'Select a MIDI output first (MIDI > MIDI Setup...).', parent=self.root)
            return False
        return True

    def transmit(self, kind, index):
        if not self.require_out():
            return
        self.device.transmit(kind, index)
        self.status(f'Transmitted {KIND_TITLE[kind]} {index + 1:03d} and wrote it to the NS5R')

    def transmit_as(self, kind, index):
        if not self.require_out():
            return
        dest = DL.TransmitAsDialog(self, KIND_TITLE[kind], index).show()
        if dest is not None:
            self.device.transmit(kind, index, dest)
            self.status(f'Transmitted {KIND_TITLE[kind]} {index + 1:03d} as {dest + 1:03d}')

    def receive(self, kind, index):
        if not self.require_out():
            return
        dev = self.device
        if kind == 'program':
            dev.select_part_program(0x50, 0, index)
        elif kind == 'combi':
            dev.select_part_program(0x58, 0, index)
        elif kind == 'effect':
            self.select_fx_on_device(N.FX_USER, index)
        if kind == 'multi':
            dev.set_mode(X.MODE_MULTI)
            dev.send(X.param_change(dev.ch, 1, 0, index))
        else:
            dev.set_mode(D.KIND_MODE[kind])
        dev.target = None
        self.expect_dumps([(kind, lambda data, k=kind, i=index: self.store(k, i, data))],
                          f'Receive {KIND_TITLE[kind]} Dump')

    def receive_as(self, kind, index):
        if not self.require_out():
            return
        r = DL.ReceiveAsDialog(self, kind).show()
        if r is None:
            return
        bank, prog = r
        dev = self.device
        if kind == 'effect':
            self.select_fx_on_device(bank, prog)
        else:
            dev.select_part_program(*N.bank_msb_lsb(bank), prog)
        dev.set_mode(D.KIND_MODE[kind])
        dev.target = None
        self.expect_dumps([(kind, lambda data: self.store(kind, index, data))], f'Receive {KIND_TITLE[kind]} Dump')

    def select_fx_on_device(self, bank, n):
        dev = self.device
        for a3, v in ((7, N.fx_bank_msb(bank)), (8, 0), (9, n)):
            dev.send(X.part_param(dev.ch, 0, 0, a3, [v]))

    def store(self, kind, index, data):
        self.lib.block(kind, index)[:] = data
        self.set_dirty()
        self.refresh_kind(kind, names=True)

    def store_all(self, what, data):
        lib = self.lib
        size = X.SIZES[what.replace('all_', '')] if what != 'global' else 10
        if what == 'global':
            lib.glob[:] = data
            self.refresh_kind('global')
        else:
            target = {'all_program': lib.programs, 'all_combi': lib.combis, 'all_drum': lib.kits,
                      'all_effect': lib.effects, 'all_multi': lib.multis}[what]
            for i in range(len(target)):
                target[i][:] = data[i * size:(i + 1) * size]
            self.refresh_all()
        self.set_dirty()

    def receive_all(self):
        if not self.require_out():
            return
        what = DL.DumpDialog(self, 'Dump Receive').show()
        if what:
            self.request_all(what)

    def request_all(self, what):
        jobs = [(w, lambda data, w=w: self.store_all(w, data)) for w in what]
        self.expect_dumps(jobs, 'Receive ' + ', '.join(ALL_TITLE[w] for w in what))

    def transmit_all(self):
        if not self.require_out():
            return
        what = DL.DumpDialog(self, 'Dump Transmit').show()
        if what:
            self.send_all(what)

    def send_all(self, what):
        for w in what:
            self.status(f'Transmitting {ALL_TITLE[w]} Dump...')
            self.root.update_idletasks()
            self.device.transmit_all(w)
        self.status('Transmitted ' + ', '.join(ALL_TITLE[w] for w in what))

    def expect_dumps(self, jobs, title):
        """Request the dumps in `jobs` one after the other; `jobs` is [(kind, store_fn)]."""
        self.expect = list(jobs)
        self.status_dialog = DL.StatusDialog(self, title, cancel=self.cancel_receive)
        self.next_request()

    def next_request(self):
        if not self.expect:
            if self.status_dialog:
                self.status_dialog.close()
                self.status_dialog = None
            self.status('Dump received')
            return
        kind = self.expect[0][0]
        self.expect_deadline = time.monotonic() + (8 if kind.startswith('all') else 3)
        self.status_dialog.set(f'Waiting for {ALL_TITLE.get(kind, KIND_TITLE.get(kind, kind))} Dump...')
        self.device.request(kind)

    def cancel_receive(self, message='Receive cancelled'):
        self.expect = []
        if self.status_dialog:
            self.status_dialog.close()
            self.status_dialog = None
        self.status(message)

    def poll_midi(self):
        try:
            while True:
                try:
                    msg = self.midi.incoming.get_nowait()
                except queue.Empty:
                    break
                if msg.type != 'sysex':
                    continue
                self.handle_sysex(bytes([0xF0]) + bytes(msg.data) + bytes([0xF7]))
            if self.expect and time.monotonic() > self.expect_deadline:
                self.cancel_receive('Receive Error: no answer from the NS5R (check cables, ports and '
                                    'the exclusive channel)')
        finally:
            self.root.after(30, self.poll_midi)

    def handle_sysex(self, m):
        r = X.parse(m)
        if not r:
            return
        if r[0] == 'identity':
            self.device_version = r[1]
            return
        if r[0] == 'reply':
            code, cmd = r[1], r[2]
            if code:
                self.status(f'NS5R: {X.REPLY_TEXT.get(code, code)} (command {cmd:02X}h)')
            return
        if r[0] != 'dump':
            return
        name, data = r[1], r[2]
        if self.expect and self.expect[0][0] == name:
            _, store = self.expect.pop(0)
            store(data)
            self.next_request()
            return
        # unsolicited dump (e.g. sent from the NS5R's own MIDI dump function)
        if name.startswith('all_') or name == 'global':
            self.store_all(name, data)
            self.status(f'Received {ALL_TITLE[name]} Dump')
        elif name in self.pages:
            page = self.pages[name]
            self.store(name, page.current(), data)
            self.status(f'Received {KIND_TITLE[name]} Dump into {page.current() + 1:03d}')

    def midi_setup(self):
        DL.MidiSetupDialog(self).show()
        self.refresh_status()

    def toggle_excl(self):
        if self.show_excl.get():
            top = tk.Toplevel(self.root, bg=ui.FACE)
            top.title('Exclusive Data')
            txt = tk.Text(top, width=72, height=12, font=('Courier', 10 * Scale.s), wrap='char')
            txt.pack(fill='both', expand=True)
            self.exclusive_log = (top, txt)
            top.protocol('WM_DELETE_WINDOW', lambda: (self.show_excl.set(False), self.toggle_excl()))

            def log(data):
                if len(data) > 48:
                    line = 'Data: ' + ' '.join(f'{b:02X}' for b in data[:24]) + f' ... ({len(data)} bytes)'
                else:
                    line = 'Data: ' + ' '.join(f'{b:02X}' for b in data)
                txt.insert('end', line + '\n')
                txt.see('end')
            self.midi.monitor = log
        else:
            self.midi.monitor = None
            if self.exclusive_log:
                self.exclusive_log[0].destroy()
                self.exclusive_log = None

    def startup(self):
        prefs = self.prefs()
        if self.midi.out:
            try:
                self.midi.send_bytes(X.device_inquiry())
            except Exception:
                pass
        if prefs.get('startup_rx') and self.midi.out:
            keys = [('startup_multi', 'all_multi'), ('startup_prog', 'all_program'),
                    ('startup_combi', 'all_combi'), ('startup_drum', 'all_drum'), ('startup_fx', 'all_effect'),
                    ('startup_global', 'global')]
            what = [w for k, w in keys if prefs.get(k)]
            if what:
                self.request_all(what)

    # ------------------------------------------------------------ files
    def confirm_discard(self, action):
        if not self.dirty:
            return True
        name = os.path.basename(self.path) if self.path else f'Untitled-{self.untitled}'
        ans = messagebox.askyesnocancel(APP_NAME, f'Do you want to save changes to:\n{name}\nbefore {action} ?',
                                        parent=self.root)
        if ans is None:
            return False
        return self.save() if ans else True

    def replace_library(self, lib, path):
        self.lib.copy_from(lib)
        self.path = path
        self.dirty = False
        self.compare_base.clear()
        self.device.target = None
        self.refresh_all()
        self.update_title()

    def new(self):
        if self.confirm_discard('closing'):
            self.untitled += 1
            self.replace_library(M.Library(), None)

    def close_doc(self):
        self.new()

    def open(self):
        if not self.confirm_discard('opening another file'):
            return
        path = filedialog.askopenfilename(parent=self.root, title='Open', filetypes=FILETYPES,
                                          initialdir=self.settings.get('dir'))
        if path:
            self.load(path)

    def open_documents(self, *paths):
        if paths and self.confirm_discard('opening another file'):
            self.load(paths[0])

    def load(self, path):
        try:
            with open(path, 'rb') as f:
                head = f.read(4)
            if head[:1] == b'\x72':
                lib = M.Library.load(path)
                self.replace_library(lib, path)
            else:
                lib = M.Library()
                n = self.apply_messages(lib, fileio.read_messages(path))
                if not n:
                    raise ValueError('no NS5R dump data found')
                self.replace_library(lib, None)
                self.dirty = True
                self.update_title()
        except (OSError, ValueError) as e:
            messagebox.showerror(APP_NAME, f'Read Error : {os.path.basename(path)}\n{e}', parent=self.root)
            return
        self.settings['dir'] = os.path.dirname(path)
        prefs = self.prefs()
        if prefs.get('open_tx') and self.midi.out:
            keys = [('open_multi', 'all_multi'), ('open_prog', 'all_program'), ('open_combi', 'all_combi'),
                    ('open_drum', 'all_drum'), ('open_fx', 'all_effect'), ('open_global', 'global')]
            self.send_all([w for k, w in keys if prefs.get(k)])

    def apply_messages(self, lib, messages):
        """Store NS5R dumps from a list of SysEx messages into `lib`; returns how many were used."""
        n = 0
        for m in messages:
            r = X.parse(m)
            if not r or r[0] != 'dump':
                continue
            name, data = r[1], r[2]
            if name == 'global':
                lib.glob[:] = data
            elif name.startswith('all_'):
                kind = name[4:]
                size = X.SIZES[kind]
                target = {'program': lib.programs, 'combi': lib.combis, 'drum': lib.kits,
                          'effect': lib.effects, 'multi': lib.multis}[kind]
                for i in range(len(target)):
                    target[i][:] = data[i * size:(i + 1) * size]
            else:
                lib.block(name, 0)[:] = data
            n += 1
        return n

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            self.lib.save(self.path)
        except OSError as e:
            messagebox.showerror(APP_NAME, f'Error : Write Error\n{e}', parent=self.root)
            return False
        self.dirty = False
        self.update_title()
        return True

    def save_as(self):
        path = filedialog.asksaveasfilename(parent=self.root, title='Save as', defaultextension='.NS5',
                                            filetypes=[('NS5 Files', '*.NS5')], initialdir=self.settings.get('dir'),
                                            initialfile=os.path.basename(self.path) if self.path
                                            else f'Untitled-{self.untitled}.NS5')
        if not path:
            return False
        self.path = path
        self.settings['dir'] = os.path.dirname(path)
        return self.save()

    def import_file(self):
        """Copy items from another file (NS5, SysEx or SMF) into the current bank selection."""
        page = self.current_page()
        kind = page.kind
        path = filedialog.askopenfilename(parent=self.root, title='Import Data', filetypes=FILETYPES,
                                          initialdir=self.settings.get('dir'))
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                head = f.read(1)
            if head == b'\x72':
                src = M.Library.load(path)
            else:
                src = M.Library()
                if not self.apply_messages(src, fileio.read_messages(path)):
                    raise ValueError('no NS5R dump data found')
        except (OSError, ValueError) as e:
            messagebox.showerror(APP_NAME, f'Read Error : {e}', parent=self.root)
            return
        if kind == 'global':
            self.lib.glob[:] = src.glob
        elif kind == 'multi':
            m = page.current()
            items = [f'Multi {i + 1}' for i in range(M.N_MULTIS)]
            r = DL.ChoiceDialog(self.root, 'Import Multi', 'Import from:', items).show()
            if r is None:
                return
            self.lib.multis[m][:] = src.multis[r]
        else:
            names = {'program': src.program_name, 'combi': src.combi_name, 'effect': src.effect_name}[kind]
            items = [N.numbered(i, names(i)) for i in range(128)]
            r = DL.NameListDialog(self.root, f'Import {KIND_TITLE[kind]}', items, 0).show()
            if r is None:
                return
            self.blocks(kind)[page.current()][:] = src.block(kind, r)
        self.set_dirty()
        self.refresh_all()

    def export_file(self):
        page = self.current_page()
        kind = page.kind
        modes = ['All Data (NS5)', 'SMF (Format 0)', 'SysEx (.syx)', 'Text (name list)']
        r = DL.ChoiceDialog(self.root, 'Export', 'Export Data as:', modes).show()
        if r is None:
            return
        ext = ['.NS5', '.MID', '.syx', '.TXT'][r]
        path = filedialog.asksaveasfilename(parent=self.root, title='Export Data', defaultextension=ext,
                                            initialdir=self.settings.get('dir'))
        if not path:
            return
        lib, ch = self.lib, self.settings.get('excl_channel', 0)
        try:
            if r == 0:
                lib.save(path)
                return
            if r == 3:
                with open(path, 'w') as f:
                    for title, names in (('Program', lib.program_name), ('Combination', lib.combi_name),
                                         ('Effect', lib.effect_name)):
                        f.write(f'[User {title}]\n')
                        for i in range(128):
                            f.write(f'{N.numbered(i, names(i))}\n')
                        f.write('\n')
                return
            msgs = []
            if kind == 'global':
                msgs.append(X.dump(ch, 'global', lib.glob))
            elif kind == 'multi':
                msgs.append(X.dump(ch, 'all_multi', b''.join(lib.multis)))
            else:
                sel = page.selection()
                if len(sel) == 128:
                    msgs.append(X.dump(ch, 'all_' + kind, b''.join(self.blocks(kind))))
                else:
                    for i in sel:
                        msgs.append(X.mode_change(ch, D.KIND_MODE[kind]))
                        msgs.append(X.dump(ch, kind, lib.block(kind, i)))
                        msgs.append(X.write_request(ch, kind, i))
            data = fileio.smf_bytes(msgs) if r == 1 else b''.join(msgs)
            with open(path, 'wb') as f:
                f.write(data)
        except OSError as e:
            messagebox.showerror(APP_NAME, f'Error : Write Error\n{e}', parent=self.root)

    # ------------------------------------------------------------ misc
    def preferences(self):
        DL.PreferencesDialog(self).show()

    def about(self):
        DL.AboutDialog(self).show()

    def quit(self):
        if not self.confirm_discard('quitting'):
            return
        try:
            self.settings['tab'] = self.nb.index('current')
        except tk.TclError:
            pass
        self.save_settings()
        self.midi.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
