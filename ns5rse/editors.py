"""Parameter editing dialogs (the original 'Edit ...' windows)."""
import tkinter as tk
from tkinter import ttk

from . import model as M
from . import names as N
from . import params as PR
from . import resources as R
from . import ui
from .binder import Binder, combo_set, pm_apply, pm_state, set_entry
from .dialogs import NameListDialog, RemarkDialog, bank_list_items, fx_list_items, program_list_items, remark_combo
from .forms import Form, ModalDialog
from .panels import EffectDiagram, eg_points
from .params import P
from .ui import Scale


class EditDialog(ModalDialog):
    """Modal editor of one data block; Cancel restores the data as it was on opening."""

    def __init__(self, app, template, kind, index, title=None, custom=None, size=None):
        self.app, self.kind, self.index = app, kind, index
        self.saved = bytes(self.block())
        super().__init__(app.root, template, title=title, custom=custom, size=size)

    def block(self):
        return self.app.lib.block(self.kind, self.index)

    def changed(self, offsets):
        self.app.edited(self.kind, self.index, offsets)

    def cancel(self):
        buf = self.block()
        if bytes(buf) != self.saved:
            diff = [i for i in range(len(buf)) if buf[i] != self.saved[i]]
            buf[:] = self.saved
            self.app.edited(self.kind, self.index, diff)
        super().cancel()


def notebook(dialog, rect, pages):
    """A ttk.Notebook at `rect` (DLU) holding one Form per (label, template)."""
    nb = ttk.Notebook(dialog.frame, takefocus=0)
    ui.place(nb, rect)
    forms = []
    for label, tpl, custom in pages:
        w, h = Scale.x(R.dialog(tpl)['rect'][2]), Scale.y(R.dialog(tpl)['rect'][3])
        fr = tk.Frame(nb, bg=ui.FACE, width=w, height=h)
        nb.add(fr, text=label)
        forms.append(Form(fr, tpl, custom=custom))
    return nb, forms


def fx_bank_spin(sp, on_change):
    sp.lo, sp.hi, sp.fmt = 0, 7, lambda i: N.FX_BANKS[i]
    sp.entry.config(state='readonly')
    sp.on_change = on_change


# =================================================================== program common
class ProgGeneralDialog(EditDialog):
    def __init__(self, app, index):
        super().__init__(app, 'PROG_GENERAL_DLG', 'program', index)
        f = self.form
        self.b = b = Binder(f, self.block, self.changed)
        b.bind(1010, P(10, items=PR.OSC_MODES))
        b.bind(1013, P(13, 0, 127, PR.plus1))
        self.name = f.w[1000]
        set_entry(self.name, app.lib.program_name(index))
        self.name.bind('<KeyRelease>', lambda e: self.set_name())
        fx_bank_spin(f.w[1011], self.set_bank)
        f.command(104, self.fx_list)
        remark_combo(app, f.w[103], 'program', index, app.set_dirty)
        f.command(102, lambda: (RemarkDialog(app).show(), remark_combo(app, f.w[103], 'program', index,
                                                                         app.set_dirty)))
        b.extra.append(self.show_fx)
        b.refresh()

    def set_name(self):
        M.set_text(self.block(), 0, 10, self.name.get())
        self.changed(range(10))

    def set_bank(self, i):
        buf = self.block()
        buf[11], buf[12] = N.fx_bank_msb(i), 0
        self.changed([11, 12])
        self.show_fx()

    def show_fx(self):
        buf = self.block()
        bank = N.fx_bank_index(buf[11])
        self.form.w[1011].set(bank)
        set_entry(self.form.w[101], N.fx_name(bank, buf[13], self.app.lib))

    def fx_list(self):
        buf = self.block()
        bank = N.fx_bank_index(buf[11])
        r = NameListDialog(self.top, 'Effect Name List', fx_list_items(bank, self.app.lib), buf[13]).show()
        if r is not None:
            self.b.write(1013, r)


# =================================================================== oscillator parameters
OSC_TABS = [('OSC', 'PROG_OSC_OSC_TAB', 'OSC {} Basic Parameters'),
            ('P-LFO', 'PROG_OSC_PITCHMG_TAB', 'OSC {} Pitch LFO Parameters'),
            ('P-EG', 'PROG_OSC_PITCHEG_TAB', 'OSC {} Pitch EG Parameters'),
            ('VDF', 'PROG_VDF_VDF_TAB', 'OSC {} VDF Parameters'),
            ('F-LFO', 'PROG_VDF_VDFMG_TAB', 'OSC {} VDF LFO Parameters'),
            ('F-EG', 'PROG_VDF_VDFEG_TAB', 'OSC {} VDF EG Parameters'),
            ('VDA', 'PROG_VDA_VDA_TAB', 'OSC {} VDA Parameters'),
            ('A-LFO', 'PROG_VDA_VDAMG_TAB', 'OSC {} VDA LFO Parameters'),
            ('A-EG', 'PROG_VDA_VDAEG_TAB', 'OSC {} VDA EG Parameters'),
            ('Fx', 'PROG_EFFECT_TAB', 'OSC {} Panpot / Fx Send Parameters')]
EG_KIND = {'PROG_OSC_PITCHEG_TAB': 'pitch', 'PROG_VDF_VDFEG_TAB': 'vdf', 'PROG_VDA_VDAEG_TAB': 'vda'}


class OscDialog(EditDialog):
    """'Oscillator Parameters' with ten tabs, for OSC1 or OSC2."""

    def __init__(self, app, index, tab=0, osc=0):
        super().__init__(app, 'PROG_OSC_DLG', 'program', index, title='Oscillator Parameters')
        self.osc = osc if self.double() else 0
        pages = []
        for label, tpl, _ in OSC_TABS:
            custom = {'EnvelopeBox': self._make_eg(tpl), 'PMBox': self._make_pm,
                      1083: lambda form, it: ttk.Scale(form.parent, orient='horizontal', from_=1, to=127)}
            pages.append((label, tpl, custom))
        self.nb, self.tabs = notebook(self, (3, 3, 246, 180), pages)
        self.binders = []
        for form in self.tabs:
            b = Binder(form, self.block, self.changed, base=self.base)
            b.bind_all({k: v for k, v in PR.PROGRAM.items() if k >= 1014})
            self.binders.append(b)
        osc_tab = self.tabs[0]
        set_ms = osc_tab.w[102]
        self.binders[0].extra.append(lambda: set_entry(set_ms, N.ms_name(self.binders[0].value(1014))))
        osc_tab.command(103, self.ms_list)
        osc_tab.command(104, lambda: app.edit_drum_kit_for_program(index))
        oct_combo = osc_tab.w[1016]
        combo_set(oct_combo, PR.OCTAVES, 2)
        oct_combo.bind('<<ComboboxSelected>>', lambda e: self.set_octave(oct_combo.current()))
        self.binders[0].extra.append(self.show_octave)
        self.binders[0].extra.append(self.show_vel)
        fx = self.tabs[9]
        fx.command(200, self.set_random)
        self.binders[9].extra.append(self.show_pan)
        self.form.command(101, self.toggle_osc)
        self.refresh()
        self.nb.select(tab)

    def double(self):
        return self.block()[10] == 1

    def base(self, cid):
        return M.OSC_SIZE if self.osc == 1 and cid in PR.OSC_PARAMS else 0

    def _make_eg(self, tpl):
        kind = EG_KIND.get(tpl)
        return lambda form, it: ui.EnvelopeBox(form.parent, lambda: eg_points(
            self.block(), M.OSC1 + self.osc * M.OSC_SIZE, kind), bipolar=kind != 'vda')

    def _make_pm(self, form, it):
        cid = it['id']
        group = next(g for g in PR.PM_BYTES if g <= cid < g + 4)
        j = cid - group
        off = PR.PM_BYTES[group]
        box = ui.PMBox(form.parent, it['text'])

        def change(state):
            o = off + self.osc * M.OSC_SIZE
            buf = self.block()
            buf[o] = pm_apply(buf[o], j, state)
            self.changed([o])
        box.on_change = change
        self.pms = getattr(self, 'pms', [])
        self.pms.append((box, off, j))
        return box

    def refresh(self):
        mode = self.block()[10]
        self.form.enable(101, mode == 1)
        for i, (form, b) in enumerate(zip(self.tabs, self.binders)):
            form.set_text(101, OSC_TABS[i][2].format(self.osc + 1))
            b.refresh()
            for w in form.w.values():
                if isinstance(w, ui.EnvelopeBox):
                    w.draw()
        for box, off, j in getattr(self, 'pms', []):
            box.set(pm_state(self.block()[off + self.osc * M.OSC_SIZE], j))
        self.tabs[0].show(104, mode == 2)

    def changed(self, offsets):
        super().changed(offsets)
        self.after_change()

    def after_change(self):
        for form in self.tabs:
            for w in form.w.values():
                if isinstance(w, ui.EnvelopeBox):
                    w.draw()
        self.show_vel()

    def set_octave(self, i):
        o = 16 + self.osc * M.OSC_SIZE
        self.block()[o] = PR.OCT_VALUES[i] & 0xFF
        self.changed([o])

    def show_octave(self):
        self.tabs[0].w[1016].current(PR.osc_octave_index(self.block()[16 + self.osc * M.OSC_SIZE]))

    def show_vel(self):
        o = self.osc * M.OSC_SIZE
        self.tabs[0].w[1521].set(self.block()[21 + o], self.block()[22 + o])

    def show_pan(self):
        v = self.block()[83 + self.osc * M.OSC_SIZE]
        fx = self.tabs[9]
        fx.check(200, 1 if v == 0 else 0)
        fx.set_text(1183, PR.pan(v))
        fx.enable(1083, v != 0)

    def set_random(self):
        o = 83 + self.osc * M.OSC_SIZE
        self.block()[o] = 0 if self.tabs[9].check(200) else 64
        self.changed([o])
        self.binders[9].refresh()

    def ms_list(self):
        names = [f'{n:03d}:{N.ms_name(n)}' for n in range(528)]
        cur = self.binders[0].value(1014)
        r = NameListDialog(self.top, 'Multi Sample Name List', names, cur).show()
        if r is not None:
            self.binders[0].write(1014, r)

    def toggle_osc(self):
        self.osc = 1 - self.osc
        self.refresh()


# =================================================================== combination
class CombiGeneralDialog(EditDialog):
    def __init__(self, app, index):
        super().__init__(app, 'COMBI_GENERAL_DLG', 'combi', index)
        f = self.form
        self.b = b = Binder(f, self.block, self.changed)
        b.bind(2012, P(12, 0, 127, PR.plus1))
        self.name = f.w[2000]
        set_entry(self.name, app.lib.combi_name(index))
        self.name.bind('<KeyRelease>', lambda e: (M.set_text(self.block(), 0, 10, self.name.get()),
                                                  self.changed(range(10))))
        fx_bank_spin(f.w[2010], self.set_bank)
        f.command(104, self.fx_list)
        remark_combo(app, f.w[103], 'combi', index, app.set_dirty)
        f.command(102, lambda: (RemarkDialog(app).show(), remark_combo(app, f.w[103], 'combi', index,
                                                                         app.set_dirty)))
        b.extra.append(self.show_fx)
        b.refresh()

    def set_bank(self, i):
        buf = self.block()
        buf[10], buf[11] = N.fx_bank_msb(i), 0
        self.changed([10, 11])
        self.show_fx()

    def show_fx(self):
        buf = self.block()
        bank = N.fx_bank_index(buf[10])
        self.form.w[2010].set(bank)
        set_entry(self.form.w[101], N.fx_name(bank, buf[12], self.app.lib))

    def fx_list(self):
        buf = self.block()
        bank = N.fx_bank_index(buf[10])
        r = NameListDialog(self.top, 'Effect Name List', fx_list_items(bank, self.app.lib), buf[12]).show()
        if r is not None:
            self.b.write(2012, r)


class TimbreDialog(EditDialog):
    """'Timbre n Parameters' (COMBI_TIMBRE_DLG); the list on the right switches timbre."""

    def __init__(self, app, index, timbre=0):
        self.t = timbre
        custom = {106: lambda form, it: ui.ListView(form.parent, on_select=self.pick),
                  102: lambda form, it: ui.Keyboard(form.parent, 0, 127, highlight=self.key_hl,
                                                    on_click=lambda n: None),
                  2521: lambda form, it: ui.VelWinBar(form.parent, lo_min=0)}
        super().__init__(app, 'COMBI_TIMBRE_DLG', 'combi', index, custom=custom)
        f = self.form
        self.b = b = Binder(f, self.block, self.changed, base=lambda cid: self.t * M.TIMBRE_SIZE)
        b.bind_all(PR.COMBI_TIMBRE)
        b.bind_all(PR.COMBI_SWITCHES)
        self.banks, _ = bank_list_items(combination=True)
        bs = f.w[2014]
        bs.lo, bs.hi = 0, len(self.banks) - 1
        bs.fmt = self.bank_text
        bs.entry.config(state='readonly')
        bs.on_change = lambda i: self.set_bank(self.banks[i])
        f.command(104, self.bank_list)
        f.command(103, self.prog_list)
        b.extra.append(self.show_misc)
        lv = f.w[106]
        lv.set_items([f'Timbre {i + 1}' for i in range(8)])
        lv.select(self.t)
        self.retitle()
        b.refresh()

    def retitle(self):
        self.top.title(f'Timbre {self.t + 1} Parameters')

    def tb(self):
        return M.TIMBRE0 + self.t * M.TIMBRE_SIZE

    def bank_text(self, i):
        msb, lsb = N.bank_msb_lsb(self.banks[i])
        return f'{msb:03d}:{lsb:03d}  {N.bank_name(self.banks[i])}'

    def cur_bank(self):
        buf, b = self.block(), self.tb()
        return N.bank_index(buf[b], buf[b + 1])

    def set_bank(self, bank):
        buf, b = self.block(), self.tb()
        buf[b], buf[b + 1] = N.bank_msb_lsb(bank)
        self.changed([b, b + 1])
        self.b.refresh()

    def key_hl(self, n):
        buf, b = self.block(), self.tb()
        lo, hi = buf[b + 7], buf[b + 8]
        inside = lo <= n <= hi if lo <= hi else (n >= lo or n <= hi)
        if inside:
            return None
        return '#606060' if n % 12 in ui.BLACK else '#a0a0a0'

    def show_misc(self):
        f, buf, b = self.form, self.block(), self.tb()
        bank = self.cur_bank()
        if bank in self.banks:
            f.w[2014].set(self.banks.index(bank))
        else:
            f.w[2014].var.set(f'{buf[b]:03d}:{buf[b + 1]:03d}  ?')
        set_entry(f.w[101], N.program_name(bank, buf[b + 2], self.app.lib) if bank is not None else '')
        f.w[2521].set(buf[b + 7], buf[b + 8])
        f.w[2523].set(buf[b + 9], buf[b + 10])
        f.w[102].draw()

    def pick(self, i):
        self.t = i
        self.retitle()
        self.b.refresh()

    def bank_list(self):
        banks, names = bank_list_items(combination=True)
        cur = self.cur_bank()
        r = NameListDialog(self.top, 'Bank Name List', names, banks.index(cur) if cur in banks else 0,
                           col_width=68).show()
        if r is not None:
            self.set_bank(banks[r])

    def prog_list(self):
        bank = self.cur_bank()
        if bank is None:
            return
        r = NameListDialog(self.top, 'Program Name List', program_list_items(bank, self.app.lib),
                           self.block()[self.tb() + 2]).show()
        if r is not None:
            self.b.write(2016, r)


# =================================================================== multi
class MultiCommonDialog(EditDialog):
    def __init__(self, app, m):
        super().__init__(app, 'MULTI_COMMON_DLG', 'multi', m, title='Multi Common Parameters')
        pages = [('Master', 'MULTI_COM_COM_TAB', None), ('MIDI to Port', 'MULTI_COM_MIDI_TAB', None),
                 ('Prog to Port', 'MULTI_COM_PROG_TAB',
                  {105: lambda form, it: ui.ListView(form.parent, extended=True, on_select=self.prog_pick)})]
        self.nb, self.tabs = notebook(self, (3, 3, 246, 180), pages)
        base = lambda cid: M.PART_COMMON  # noqa: E731
        self.binders = [Binder(form, self.block, self.changed, base=base) for form in self.tabs]
        for b in self.binders:
            b.bind_all(PR.COMMON)
        master = self.tabs[0]
        fx_bank_spin(master.w[7005], self.set_bank)
        master.command(104, self.fx_list)
        self.binders[0].extra.append(self.show_fx)
        prog = self.tabs[2]
        self.plist = prog.w[105]
        self.plist.set_items([N.numbered(p, N.program_name(67, p)) for p in range(128)])
        combo_set(prog.w[106], PR.PROG_PORTS, 0)
        prog.w[106].bind('<<ComboboxSelected>>', lambda e: self.set_ports(prog.w[106].current()))
        for cid, port in ((101, 0), (102, 1), (103, 2), (104, 3)):
            prog.command(cid, lambda p=port: self.set_ports(p, every=True))
        for b in self.binders:
            b.refresh()
        self.plist.select(0)
        self.prog_pick(0)

    def set_bank(self, i):
        buf, c = self.block(), M.PART_COMMON
        buf[c + 5], buf[c + 6] = N.fx_bank_msb(i), 0
        self.changed([c + 5, c + 6])
        self.show_fx()

    def show_fx(self):
        buf, c = self.block(), M.PART_COMMON
        bank = N.fx_bank_index(buf[c + 5])
        master = self.tabs[0]
        master.w[7005].set(bank)
        set_entry(master.w[101], N.fx_name(bank, buf[c + 7], self.app.lib))

    def fx_list(self):
        buf, c = self.block(), M.PART_COMMON
        bank = N.fx_bank_index(buf[c + 5])
        r = NameListDialog(self.top, 'Effect Name List', fx_list_items(bank, self.app.lib), buf[c + 7]).show()
        if r is not None:
            self.binders[0].write(7007, r)

    def prog_pick(self, i):
        self.tabs[2].w[106].current(self.block()[M.PART_COMMON + 0x18 + i] & 3)

    def set_ports(self, port, every=False):
        buf, c = self.block(), M.PART_COMMON + 0x18
        sel = range(128) if every else self.plist.selection()
        for p in sel:
            buf[c + p] = port
        self.changed([c + p for p in sel])
        self.prog_pick(self.plist.current() or 0)


class MultiPartDialog(EditDialog):
    def __init__(self, app, m, part=0):
        self.part = part
        custom = {102: lambda form, it: ui.ListView(form.parent, on_select=self.pick),
                  3014: lambda form, it: ttk.Scale(form.parent, orient='horizontal', from_=1, to=127)}
        super().__init__(app, 'MULTI_PART_EDIT_DLG', 'multi', m, custom=custom)
        f = self.form
        self.b = b = Binder(f, self.block, self.changed, base=lambda cid: self.part * M.PART_SIZE)
        b.bind_all(PR.PART)
        b.bind(3003, P(3, 0, 15, PR.plus1, mask=0x0F))
        bs = f.w[3000]
        bs.lo, bs.hi = 0, N.N_BANKS - 1
        bs.fmt = self.bank_text
        bs.entry.config(state='readonly')
        bs.on_change = self.set_bank
        combo_set(f.w[3503], ['A', 'B', 'OFF'], 0)
        f.w[3503].bind('<<ComboboxSelected>>', lambda e: self.set_port(f.w[3503].current()))
        f.command(104, self.bank_list)
        f.command(103, self.prog_list)
        f.command(200, self.set_random)
        b.extra.append(self.show_misc)
        self.fill_parts()
        f.w[102].select(part)
        self.pick(part)

    def pb(self):
        return self.part * M.PART_SIZE

    def bank_text(self, i):
        msb, lsb = N.bank_msb_lsb(i)
        return f'{msb:03d}:{lsb:03d}  {N.bank_name(i)}'

    def fill_parts(self):
        buf = self.block()
        items = []
        for p in range(32):
            b = p * M.PART_SIZE
            bank = N.bank_index(buf[b], buf[b + 1])
            name = N.program_name(bank, buf[b + 2], self.app.lib) if bank is not None else ''
            items.append(f'{p + 1:02d}  {name}')
        self.form.w[102].set_items(items)

    def pick(self, i):
        self.part = i
        self.top.title(f'Multi {self.index + 1} : Part {i + 1} Parameters')
        self.b.refresh()

    def changed(self, offsets):
        super().changed(offsets)
        self.fill_parts()

    def set_bank(self, bank):
        buf, b = self.block(), self.pb()
        buf[b], buf[b + 1] = N.bank_msb_lsb(bank)
        self.changed([b, b + 1])
        self.b.refresh()

    def set_port(self, i):
        buf, b = self.block(), self.pb() + 3
        ch = buf[b] & 0x0F
        buf[b] = 32 if i == 2 else ch + 16 * i
        self.changed([b])
        self.b.refresh()

    def set_random(self):
        b = self.pb() + 0x0E
        self.block()[b] = 0 if self.form.check(200) else 64
        self.changed([b])
        self.b.refresh()

    def show_misc(self):
        f, buf, b = self.form, self.block(), self.pb()
        bank = N.bank_index(buf[b], buf[b + 1])
        if bank is not None:
            f.w[3000].set(bank)
        set_entry(f.w[101], N.program_name(bank, buf[b + 2], self.app.lib) if bank is not None else '')
        ch = buf[b + 3]
        f.w[3503].current(2 if ch >= 32 else ch // 16)
        f.enable(3003, ch < 32)
        pan = buf[b + 0x0E]
        f.check(200, 1 if pan == 0 else 0)
        f.enable(3014, pan != 0)
        f.set_text(3114, PR.pan(pan))

    def bank_list(self):
        banks, names = bank_list_items()
        b = self.pb()
        cur = N.bank_index(self.block()[b], self.block()[b + 1])
        r = NameListDialog(self.top, 'Bank Name List', names, cur or 0, col_width=68).show()
        if r is not None:
            self.set_bank(banks[r])

    def prog_list(self):
        b = self.pb()
        bank = N.bank_index(self.block()[b], self.block()[b + 1])
        if bank is None:
            return
        r = NameListDialog(self.top, 'Program Name List', program_list_items(bank, self.app.lib),
                           self.block()[b + 2]).show()
        if r is not None:
            self.b.write(3002, r)


# =================================================================== global
class GlobalEditDialog(EditDialog):
    def __init__(self, app):
        super().__init__(app, 'GLOBAL_EDIT_DLG', 'global', 0)
        f = self.form
        self.b = b = Binder(f, self.block, self.changed)
        b.bind_all(PR.GLOBAL)
        b.bind(6019, P(9, 0, 1, mask=0xFF))
        f.command(6019, self.fx_follow)
        b.extra.append(self.show)
        b.refresh()

    def fx_follow(self):
        self.block()[9] = 1 if self.form.check(6019) else 0
        self.changed([9])
        self.b.refresh()

    def show(self):
        v = self.block()[9]
        self.form.check(6019, 1 if v else 0)
        self.form.enable(6009, v != 0)
        if v:
            self.form.w[6009].set(v)


# =================================================================== drum kits
class KitRef:
    """A drum kit inside a block: a user kit, or one of a Multi's four modify drums."""

    def __init__(self, app, kind, index, base, title):
        self.app, self.kind, self.index, self.base, self.title = app, kind, index, base, title

    def block(self):
        return self.app.lib.block(self.kind, self.index)

    def inst(self, i):
        return self.base + i * M.INST_SIZE

    def changed(self, offsets):
        self.app.edited(self.kind, self.index, offsets)


def drum_row(buf, b, key):
    s8 = lambda v: str(v - 64)  # noqa: E731
    inst = (buf[b] << 8) | buf[b + 1]
    return (N.note_name(key), f'{inst:03d}', N.drum_name(inst), s8(buf[b + 2]), s8(buf[b + 3]), str(buf[b + 4]),
            str(buf[b + 5]) if buf[b + 5] else 'Off', 'Multi' if buf[b + 6] & 4 else 'Single',
            s8(buf[b + 7]), s8(buf[b + 8]), s8(buf[b + 9]), s8(buf[b + 10]), PR.pan(buf[b + 11]),
            str(buf[b + 12]), str(buf[b + 13]))


class DrumKitWindow:
    """'Drum Kit Edit' list of the 97 instruments (C0..C8) of one kit."""
    COLS = [(1, 'l'), (19, 'l'), (34, 'l'), (59, 'r'), (82, 'r'), (105, 'r'), (128, 'r'), (130, 'l'),
            (174, 'r'), (197, 'r'), (220, 'r'), (243, 'r'), (264, 'r'), (287, 'r'), (310, 'r')]

    def __init__(self, app, ref):
        self.app, self.ref = app, ref
        self.top = tk.Toplevel(app.root, bg=ui.FACE)
        self.top.title(f'Drum Kit Edit - {ref.title}')
        self.top.resizable(False, False)
        self.top.transient(app.root)
        w, h = Scale.x(348), Scale.y(173)
        frame = tk.Frame(self.top, bg=ui.FACE, width=w, height=h)
        frame.pack()
        self.form = f = Form(frame, 'DRUMKIT_LIST_DLG', custom={
            101: lambda form, it: ui.ListView(frame, columns=self.COLS, on_double=self.edit, extended=True),
            102: lambda form, it: ui.Keyboard(frame, M.FIRST_KEY, M.FIRST_KEY + M.N_INST - 1,
                                              on_press=self.key_down, on_release=self.key_up,
                                              highlight=self.key_hl)})
        # headers: Note Smpl ... stay as in the template; the list shows instrument numbers and names
        f.command(1, self.close)
        f.command(103, self.edit_levels)
        self.lv = f.w[101]
        self.lv.on_select = lambda i: f.w[102].draw()
        self.top.protocol('WM_DELETE_WINDOW', self.close)
        self.fill()
        self.lv.select(0)
        app.windows.append(self)

    def fill(self):
        buf = self.ref.block()
        self.lv.set_items([drum_row(buf, self.ref.inst(i), M.FIRST_KEY + i) for i in range(M.N_INST)])
        self.form.w[102].draw()

    def refresh(self):
        self.fill()

    def key_hl(self, n):
        i = n - M.FIRST_KEY
        return '#7090ff' if i in self.lv.selected else None

    def key_down(self, n):
        self.lv.select(n - M.FIRST_KEY)
        ch = self.app.keyboard.channel if self.app.keyboard else 9
        self.app.midi_safe(lambda m: m.note_on(ch, n, 100))

    def key_up(self, n):
        ch = self.app.keyboard.channel if self.app.keyboard else 9
        self.app.midi_safe(lambda m: m.note_off(ch, n))

    def edit(self, i):
        DrumEditDialog(self.app, self.ref, i).show()
        self.fill()

    def edit_levels(self):
        from .dialogs import EditLevelDialog
        fn = EditLevelDialog(self.top).show()
        if not fn:
            return
        sel = self.lv.selection() or list(range(M.N_INST))
        if len(sel) == 1:
            sel = list(range(M.N_INST))
        buf = self.ref.block()
        offs = [self.ref.inst(i) + 4 for i in sel]
        for o, v in zip(offs, fn([buf[o] for o in offs])):
            buf[o] = v
        self.ref.changed(offs)
        self.fill()

    def close(self):
        if self in self.app.windows:
            self.app.windows.remove(self)
        self.top.destroy()


class DrumEditDialog(ModalDialog):
    def __init__(self, app, ref, inst):
        self.app, self.ref, self.i = app, ref, inst
        self.saved = bytes(ref.block())
        super().__init__(app.root, 'DRUMKIT_EDIT_DLG', title='Drum Kit Parameters',
                         custom={104: lambda form, it: ui.ListView(form.parent, on_select=self.pick)})
        f = self.form
        self.b = b = Binder(f, ref.block, ref.changed, base=lambda cid: ref.inst(self.i))
        b.bind_all(PR.DRUM)
        f.command(4505, self.excl_off)
        f.command(103, self.name_list)
        b.extra.append(self.show)
        f.w[104].set_items([f'{N.note_name(M.FIRST_KEY + i)}' for i in range(M.N_INST)])
        f.w[104].select(inst)
        self.pick(inst)

    def pick(self, i):
        self.i = i
        self.top.title(f'Drum Kit Parameters [Key = {N.note_name(M.FIRST_KEY + i)}]')
        self.b.refresh()

    def show(self):
        f, buf, b = self.form, self.ref.block(), self.ref.inst(self.i)
        set_entry(f.w[101], N.drum_name((buf[b] << 8) | buf[b + 1]))
        ex = buf[b + 5]
        f.check(4505, 1 if ex == 0 else 0)
        f.enable(4005, ex != 0)
        f.enable(102, ex != 0)

    def excl_off(self):
        b = self.ref.inst(self.i) + 5
        self.ref.block()[b] = 0 if self.form.check(4505) else 1
        self.ref.changed([b])
        self.b.refresh()

    def name_list(self):
        names = [f'{n:03d}:{N.drum_name(n)}' for n in range(286)]
        r = NameListDialog(self.top, 'Drum Sample Name List', names, self.b.value(4000)).show()
        if r is not None:
            self.b.write(4000, r)

    def cancel(self):
        buf = self.ref.block()
        if bytes(buf) != self.saved:
            diff = [i for i in range(len(buf)) if buf[i] != self.saved[i]]
            buf[:] = self.saved
            self.ref.changed(diff)
        super().cancel()


# =================================================================== effects
def fx_param_offset(e, i):
    return (0x11 if e == 0 else 0x1B) + i


SPEED_TYPES = {19, 20, 32, 33, 35, 36}          # Mod Speed uses the *1 table at param 1
WORD_PARAMS = {13: (0, 4), 14: (0, 4), 15: (0, 4), 16: (0, 2), 17: (0, 2), 18: (0, 2), 23: (0, 2),
               40: (0,), 41: (0,), 42: (0,), 43: (0,), 44: (0,), 45: (0,), 46: (0,), 47: (0,)}
WAVE_PARAM = {19: 2, 20: 2, 32: 2, 33: 2, 35: 2, 36: 2, 42: 6}
SHAPE_PARAM = {21: 4, 22: 4}
DECIMAL_TIME = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 40: 4, 41: 4}


def mod_speed(v):
    if v < 100:
        c = 3 * (v + 1)
        return f'{c // 100}.{c % 100:02d}'
    if v < 200:
        d = 31 + (v - 100)
        return f'{d // 10}.{d % 10}'
    return str(14 + v - 200)


def fx_spec(t, i, mins, maxs):
    """P spec for effect type t, parameter i (byte offset within the 8 parameters)."""
    lo, hi = M.s8(mins[i][t]), maxs[i][t]
    if t in WORD_PARAMS and i in WORD_PARAMS[t]:
        lo = mins[i][t] | (mins[i + 1][t] << 8)
        hi = maxs[i][t] | (maxs[i + 1][t] << 8)
        return ('word', lo, hi, str)
    if t in SPEED_TYPES and i == 1 or (t in (42, 43, 46) and i == 5):
        return ('byte', 0, maxs[i][t], mod_speed)
    if DECIMAL_TIME.get(t) == i:
        return ('byte', 0, maxs[i][t], lambda v: f'{(v + 2) // 10}.{(v + 2) % 10}')
    if t in (10, 11, 12) and i == 0:
        return ('byte', 0, maxs[i][t], lambda v: str(100 + 10 * v))
    if hi > 127 and lo >= 0:
        return ('byte', lo, hi, str)
    return ('sbyte', lo, M.s8(hi) if hi > 127 else hi, str)


class EffectParamDialog(ModalDialog):
    """Effect 1/2 parameters: one of the templates 700-725, chosen by effect type."""

    def __init__(self, master, app, kind, index, e):
        self.app, self.kind, self.index, self.e = app, kind, index, e
        buf = self.block()
        t = buf[8 + e]
        self.t = t
        tpl = 700 + R.data()['fx_dialog'][t]
        super().__init__(master, tpl, title=f'Effect {e + 1} Parameters')
        f = self.form
        d = R.data()
        mins, maxs = d['fx_min'], d['fx_max']
        self.vals = {}
        for i in range(8):
            cid = 5017 + i
            if cid not in f.w:
                continue
            w = f.w[cid]
            if isinstance(w, ttk.Combobox):
                if t in WAVE_PARAM and WAVE_PARAM[t] == i:
                    combo_set(w, ['Sine', 'Triangle'], buf[fx_param_offset(e, i)] & 1)
                    w.bind('<<ComboboxSelected>>', lambda ev, i=i, w=w: self.set_bits(i, w.current()))
                elif t in SHAPE_PARAM:
                    items = [R.strings()[12480 + k] for k in range(42)]
                    combo_set(w, items, M.s8(buf[fx_param_offset(e, i)]) + 21)
                    w.bind('<<ComboboxSelected>>', lambda ev, i=i, w=w: self.set_byte(i, w.current() - 21))
                continue
            kind_, lo, hi, fmt = fx_spec(t, i, mins, maxs)
            w.lo, w.hi, w.fmt = lo, hi, fmt
            w.on_change = lambda v, i=i, k=kind_: self.set_param(i, k, v)
            o = fx_param_offset(e, i)
            if kind_ == 'word':
                w.set(buf[o] | (buf[o + 1] << 8))
            elif kind_ == 'sbyte':
                w.set(M.s8(buf[o]))
            else:
                w.set(buf[o])
        # balances: 5010/5011 belong to effect 1, 5012/5013 to effect 2
        for cid in (5010, 5011, 5012, 5013):
            if cid not in f.w:
                continue
            mine = (cid - 5010) // 2 == e
            f.show(cid, mine)
            if mine:
                w = f.w[cid]
                o = 0x0A + (cid - 5010)
                w.lo, w.hi = 0, 100
                w.fmt = lambda v: f'{100 - v}:{v}'
                w.set(buf[o])
                w.on_change = lambda v, o=o: self.set_raw(o, v)
        mo = 0x19 if e == 0 else 0x23
        if 5025 in f.w:
            combo_set(f.w[5025], PR.FX_MOD_SOURCES, min(buf[mo], 6))
            f.w[5025].bind('<<ComboboxSelected>>', lambda ev: self.set_raw(mo, f.w[5025].current()))
            sp = f.w[5026]
            sp.lo, sp.hi = -15, 15
            sp.set(M.s8(buf[mo + 1]))
            sp.on_change = lambda v: self.set_raw(mo + 1, v & 0xFF)
        if 102 in f.w:     # effect on/off check box, labelled with the effect name
            f.set_text(102, N.fx_type_name(t))
            f.check(102, 1 if buf[0x10] & (3 << 2 * e) else 0)
            f.command(102, self.set_onoff)
        f.command(101, self.select_type)
        self.top.title(f'Effect {e + 1} : {N.fx_type_name(t)}')

    def block(self):
        return self.app.lib.block(self.kind, self.index)

    def set_raw(self, o, v):
        self.block()[o] = v & 0xFF
        self.app.edited(self.kind, self.index, [o])

    def set_param(self, i, kind, v):
        o = fx_param_offset(self.e, i)
        buf = self.block()
        if kind == 'word':
            buf[o], buf[o + 1] = v & 0xFF, (v >> 8) & 0xFF
            self.app.edited(self.kind, self.index, [o, o + 1])
        else:
            self.set_raw(o, v)

    def set_bits(self, i, v):
        o = fx_param_offset(self.e, i)
        buf = self.block()
        buf[o] = (buf[o] & ~1 & 0xFF) | (v & 1)
        self.app.edited(self.kind, self.index, [o])

    def set_byte(self, i, v):
        self.set_raw(fx_param_offset(self.e, i), v)

    def set_onoff(self):
        buf = self.block()
        bits = 3 << 2 * self.e
        buf[0x10] = (buf[0x10] | bits) if self.form.check(102) else (buf[0x10] & ~bits & 0xFF)
        self.app.edited(self.kind, self.index, [0x10])

    def select_type(self):
        r = EffectSelectDialog(self.top, self.t).show()
        if r is None or r == self.t:
            return
        set_effect_type(self.app, self.kind, self.index, self.e, r)
        self.result = 'retype'
        self.close()


def set_effect_type(app, kind, index, e, t):
    buf = app.lib.block(kind, index)
    buf[8 + e] = t
    dflt = R.data()['fx_defaults'][t]
    o = fx_param_offset(e, 0)
    buf[o:o + 8] = bytes(dflt[:8])
    buf[0x0A + 2 * e], buf[0x0B + 2 * e] = dflt[8], dflt[9]
    if t:
        buf[0x10] |= 3 << 2 * e
    app.edited(kind, index, [8 + e, 0x0A + 2 * e, 0x0B + 2 * e, 0x10] + list(range(o, o + 8)))


class EffectSelectDialog(ModalDialog):
    def __init__(self, master, current):
        super().__init__(master, 1031, custom={3: lambda form, it: ui.ListView(form.parent)})
        lv = self.form.w[3]
        lv.set_items([N.fx_type_name(t) for t in range(48)])
        lv.on_double = lambda i: self.ok()
        self.top.after_idle(lambda: (lv.select(current), lv.canvas.focus_set()))

    def ok(self):
        self.result = self.form.w[3].current()
        self.close()


class PlacementDialog(ModalDialog):
    def __init__(self, master, current):
        self.sel = current
        super().__init__(master, 'PLACEMENT_DLG', custom={'PlacePict': self._make})

    def _make(self, form, it):
        n = it['id'] - 100
        c = tk.Canvas(form.parent, bg=ui.FACE, highlightthickness=0, bd=0)
        c.bind('<Button-1>', lambda e: self.pick(n))
        c.bind('<Double-Button-1>', lambda e: (self.pick(n), self.ok()))
        c.bind('<Configure>', lambda e: self.draw(c, n))
        self.cells = getattr(self, 'cells', {})
        self.cells[n] = c
        return c

    def draw(self, c, n):
        c.delete('all')
        c.create_image(0, 0, anchor='nw', image=ui.image(f'sys_{100 + 2 * n + (1 if n == self.sel else 0)}'))
        c.create_text(c.winfo_width() // 2, c.winfo_height() - Scale.px(2), anchor='s', font=ui.font('small'), fill=ui.TEXT,
                      text=PR.PLACEMENTS[n])
        if n == self.sel:
            c.create_rectangle(1, 1, c.winfo_width() - 2, c.winfo_height() - 2, outline=ui.SEL_BG, width=2)

    def pick(self, n):
        self.sel = n
        for k, c in self.cells.items():
            self.draw(c, k)

    def ok(self):
        self.result = self.sel
        self.close()


class EffectPanDialog(ModalDialog):
    def __init__(self, master, app, kind, index):
        self.app, self.kind, self.index = app, kind, index
        super().__init__(master, 'EFFECT_PAN_DLG', custom={
            5014: lambda form, it: ttk.Scale(form.parent, orient='horizontal', from_=1, to=101),
            5015: lambda form, it: ttk.Scale(form.parent, orient='horizontal', from_=1, to=101)})
        f = self.form
        buf = app.lib.block(kind, index)
        for n, (chk, sc, txt) in enumerate(((101, 5014, 5114), (104, 5015, 5115))):
            o = 0x0E + n
            f.check(chk, 1 if buf[o] else 0)
            f.w[sc].set(102 - (buf[o] or 51))
            f.command(chk, lambda o=o, n=n: self.update(o, n))
            f.w[sc].config(command=lambda v, o=o, n=n: self.update(o, n))
            self.update(o, n, write=False)

    def update(self, o, n, write=True):
        f = self.form
        chk, sc, txt = ((101, 5014, 5114), (104, 5015, 5115))[n]
        on = f.check(chk)
        v = 102 - int(float(f.w[sc].get()) + 0.5) if on else 0
        f.enable(sc, bool(on))
        f.set_text(txt, PR.pan101(v))
        if write:
            buf = self.app.lib.block(self.kind, self.index)
            if buf[o] != v:
                buf[o] = v
                self.app.edited(self.kind, self.index, [o])


class EffectLevelDialog(ModalDialog):
    def __init__(self, master, app, kind, index):
        self.app, self.kind, self.index = app, kind, index
        super().__init__(master, 'EFFECT_LEVEL_DLG')
        f = self.form
        buf = app.lib.block(kind, index)
        for cid, o, shift in ((5514, 0x0E, 4), (5614, 0x0E, 0), (5515, 0x0F, 4), (5615, 0x0F, 0)):
            sp = f.w[cid]
            sp.lo, sp.hi = 0, 9
            sp.set((buf[o] >> shift) & 15)
            sp.on_change = lambda v, o=o, s=shift: self.write(o, s, v)

    def write(self, o, shift, v):
        buf = self.app.lib.block(self.kind, self.index)
        buf[o] = (buf[o] & ~(15 << shift) & 0xFF) | (v << shift)
        self.app.edited(self.kind, self.index, [o])


def edit_effect_part(master, app, kind, index, role):
    """Open the right editor for a double-clicked part of the placement diagram."""
    buf = app.lib.block(kind, index)
    if role in ('fx1', 'fx2'):
        e = 0 if role == 'fx1' else 1
        while EffectParamDialog(master, app, kind, index, e).show() == 'retype':
            pass
    elif role in ('pan3', 'pan4'):
        EffectPanDialog(master, app, kind, index).show()
    elif role in ('lvl1', 'lvl2'):
        EffectLevelDialog(master, app, kind, index).show()
    else:
        r = PlacementDialog(master, (buf[0x10] >> 4) & 3).show()
        if r is not None:
            old = (buf[0x10] >> 4) & 3
            buf[0x10] = (buf[0x10] & 0x0F) | (r << 4)
            if (old == 3) != (r == 3):     # bytes 0E/0F change meaning: pans <-> levels
                buf[0x0E] = buf[0x0F] = 0x99 if r == 3 else 0
            app.edited(kind, index, [0x0E, 0x0F, 0x10])


class EffectEditDialog(EditDialog):
    """EDIT_EFFECT_DLG: effect name and the clickable placement diagram."""

    def __init__(self, app, index):
        super().__init__(app, 'EDIT_EFFECT_DLG', 'effect', index, title=f'Effect {index + 1:03d} Parameters',
                         custom={19: self._make_diagram, 'EffectUserItem': lambda form, it: None})
        self.name = self.form.w[5000]
        set_entry(self.name, app.lib.effect_name(index))
        self.name.bind('<KeyRelease>', lambda e: (M.set_text(self.block(), 0, 8, self.name.get()),
                                                  self.changed(range(8))))
        self.diagram.set(self.block())

    def _make_diagram(self, form, it):
        items = {i['id']: i['rect'] for i in form.tpl['items'] if i['cls'] == 'EffectUserItem'}
        self.diagram = EffectDiagram(form.parent, items, self.app.lib, on_double=self.part)
        return self.diagram

    def part(self, role):
        edit_effect_part(self.top, self.app, 'effect', self.index, role)
        self.diagram.set(self.block())

