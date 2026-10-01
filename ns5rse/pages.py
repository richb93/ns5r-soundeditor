"""The five pages of the main window: Multi, Global, User Prog, User Combi, User Effect."""
import tkinter as tk
from tkinter import ttk

from . import model as M
from . import names as N
from . import params as PR
from . import resources as R
from . import ui
from .forms import Form
from .panels import EffectDiagram, OscSummary, TimbreSummary
from .ui import Scale

PAGE_W, PAGE_H = 356, 200
SUB_RECT = (105, 4, 247, 154)          # the Common / OSC ... sub-tabs of the bank pages


def sub_notebook(parent, rect, pages):
    nb = ttk.Notebook(parent, takefocus=0)
    ui.place(nb, rect)
    forms = []
    for label, tpl, custom in pages:
        t = R.dialog(tpl)
        fr = tk.Frame(nb, bg=ui.FACE, width=Scale.x(t['rect'][2]), height=Scale.y(t['rect'][3]))
        nb.add(fr, text=label)
        forms.append(Form(fr, tpl, custom=custom))
    return nb, forms


class BankPage:
    """Common layout of User Prog / User Combi / User Effect: a name list, sub-tabs and a dump group."""
    kind = None
    template = None
    list_id = None
    title = ''

    def __init__(self, app, parent):
        self.app = app
        self.frame = tk.Frame(parent, bg=ui.FACE, width=Scale.x(PAGE_W), height=Scale.y(PAGE_H))
        self.form = f = Form(self.frame, self.template, custom={
            self.list_id: lambda form, it: ui.ListView(form.parent, extended=True, on_select=self.picked,
                                                       on_double=lambda i: self.edit())},
            skip=self.skip_ids())
        self.lv = f.w[self.list_id]
        # dump group narrowed to make room for the Keyboard button, as in the original window
        f.move(106, [105, 160, 186, 28])
        for cid, x in zip((102, 103, 104, 105), (110, 155, 200, 245)):
            f.move(cid, [x, 170, 42, 14])
        kb = ttk.Labelframe(self.frame, text='')
        ui.place(kb, (294, 160, 58, 28))
        kbtn = ttk.Button(self.frame, text='Keyboard', command=app.show_keyboard, takefocus=0)
        ui.place(kbtn, (299, 167, 48, 14))
        f.command(102, lambda: app.transmit(self.kind, self.current()))
        f.command(103, lambda: app.transmit_as(self.kind, self.current()))
        f.command(104, lambda: app.receive(self.kind, self.current()))
        f.command(105, lambda: app.receive_as(self.kind, self.current()))
        self.build()
        self.fill()
        self.lv.select(0)
        self.refresh()

    def skip_ids(self):
        return ()

    def current(self):
        return self.lv.current() or 0

    def selection(self):
        return self.lv.selection() or [self.current()]

    def item_name(self, i):
        return ''

    def fill(self):
        lib = self.app.lib
        show = self.app.settings.get('display_remark', {}).get(self.kind)
        items = []
        for i in range(128):
            txt = N.numbered(i, self.item_name(i))
            if show:
                r = lib.remark_of(self.kind, i)
                if r:
                    txt += f'  [{lib.remark_label(r) or r}]'
            items.append(txt)
        self.lv.set_items(items)

    def picked(self, i):
        self.refresh()
        self.app.item_selected(self.kind, i)

    def refresh(self):
        pass

    def set_midi_enabled(self, on):
        for cid in (102, 103, 104, 105):
            self.form.enable(cid, on)

    def edit(self):
        pass


def remark_toggle(page, form):
    """The 'Display Remark' check box: show remark labels in the name list."""
    d = page.app.settings.setdefault('display_remark', {})
    form.check(105, 1 if d.get(page.kind) else 0)

    def toggled():
        d[page.kind] = bool(form.check(105))
        page.fill()
    form.command(105, toggled)


# =================================================================== User Prog
class ProgramPage(BankPage):
    kind, template, list_id, title = 'program', 'PROGRAM_DLG', 101, 'User Prog'

    def build(self):
        app = self.app
        self.nb, (self.common, self.osc) = sub_notebook(self.frame, SUB_RECT, [
            ('Common', 'PROG_GENERAL_TAB', None), ('OSC Parameters', 'PROG_OSC_TAB', None)])
        self.common.command(100, lambda: app.edit_program_common(self.current()))
        self.osc.command(100, lambda: app.edit_osc(self.current()))
        self.osc.move(100, [188, 125, 50, 14])
        remark_toggle(self, self.common)
        parent = self.osc.parent
        self.sums = []
        for o in range(2):
            s = OscSummary(parent, o, on_click=lambda sec, o=o: app.edit_osc(
                self.current(), {'osc': 0, 'pitch': 2, 'vdf': 3, 'vda': 6}[sec], o))
            s.place(x=Scale.x(2 + 121 * o), y=Scale.y(2))
            self.sums.append(s)

    def item_name(self, i):
        return self.app.lib.program_name(i)

    def edit(self):
        if self.nb.index('current') == 0:
            self.app.edit_program_common(self.current())
        else:
            self.app.edit_osc(self.current())

    def refresh(self):
        lib, i = self.app.lib, self.current()
        p = lib.programs[i]
        c = self.common
        c.set_text(101, lib.program_name(i))
        c.set_text(102, PR.OSC_MODES[min(p[10], 2)])
        r = lib.remark_of('program', i)
        c.set_text(103, lib.remark_label(r) or (str(r) if r else ''))
        bank = N.fx_bank_index(p[11])
        c.set_text(106, N.FX_BANKS[bank])
        c.set_text(107, N.numbered(p[13], N.fx_name(bank, p[13], lib)))
        for o, s in enumerate(self.sums):
            s.set(p, o == 0 or p[10] == 1)


# =================================================================== User Combi
class CombiPage(BankPage):
    kind, template, list_id, title = 'combi', 'COMBINATION_DLG', 201, 'User Combi'

    def build(self):
        app = self.app
        pages = [('Common', 'COMBI_GENERAL_TAB', None)] + [(f'T{t + 1}', 'COMBI_TIMBRE_TAB', None)
                                                           for t in range(8)]
        self.nb, forms = sub_notebook(self.frame, SUB_RECT, pages)
        self.common, self.timbres = forms[0], forms[1:]
        self.common.command(100, lambda: app.edit_combi_common(self.current()))
        remark_toggle(self, self.common)
        self.sums = []
        for t, form in enumerate(self.timbres):
            form.command(100, lambda t=t: app.edit_timbre(self.current(), t))
            s = TimbreSummary(form.parent, app.lib, on_double=lambda t=t: app.edit_timbre(self.current(), t))
            s.place(x=Scale.x(2), y=Scale.y(4))
            self.sums.append(s)

    def item_name(self, i):
        return self.app.lib.combi_name(i)

    def edit(self):
        k = self.nb.index('current')
        if k == 0:
            self.app.edit_combi_common(self.current())
        else:
            self.app.edit_timbre(self.current(), k - 1)

    def refresh(self):
        lib, i = self.app.lib, self.current()
        c = lib.combis[i]
        f = self.common
        f.set_text(101, lib.combi_name(i))
        r = lib.remark_of('combi', i)
        f.set_text(103, lib.remark_label(r) or (str(r) if r else ''))
        bank = N.fx_bank_index(c[10])
        f.set_text(106, N.FX_BANKS[bank])
        f.set_text(107, N.numbered(c[12], N.fx_name(bank, c[12], lib)))
        for t, s in enumerate(self.sums):
            s.set(c, t)


# =================================================================== User Effect
class EffectPage(BankPage):
    kind, template, list_id, title = 'effect', 'EFFECT_DLG', 301, 'User Effect'

    def skip_ids(self):
        return tuple(range(20, 35))

    def build(self):
        items = {i['id']: i['rect'] for i in R.dialog('EFFECT_DLG')['items'] if i['cls'] == 'EffectUserItem'}
        self.diagram = EffectDiagram(self.frame, items, self.app.lib, on_double=self.part)
        self.form.w[19] = self.diagram
        ui.place(self.diagram, items[19])
        self.form.command(100, self.edit)

    def item_name(self, i):
        return self.app.lib.effect_name(i)

    def part(self, role):
        from .editors import edit_effect_part
        edit_effect_part(self.app.root, self.app, 'effect', self.current(), role)

    def edit(self):
        self.app.edit_effect(self.current())

    def refresh(self):
        i = self.current()
        self.form.set_text(107, self.app.lib.effect_name(i))
        self.diagram.set(self.app.lib.effects[i])


# =================================================================== Global
GLOBAL_VALUES = {
    202: lambda g: str(g[2] + 1), 200: lambda g: ['31.25 Kbps', '38.4 Kbps'][g[0] & 1],
    201: lambda g: ['Default Map', '05R/W Map'][g[1] & 1], 253: lambda g: ['Native', 'Emulate'][(g[3] >> 5) & 1],
    243: lambda g: PR.onoff(g[3] & 0x10), 209: lambda g: f'Part {g[9]}' if g[9] else 'OFF',
    203: lambda g: PR.onoff(g[3] & 1), 213: lambda g: PR.onoff(g[3] & 2), 223: lambda g: PR.onoff(g[3] & 4),
    233: lambda g: PR.onoff(g[3] & 8),
    205: lambda g: 'Enable' if g[5] & 1 else 'Disable', 215: lambda g: 'Enable' if g[5] & 2 else 'Disable',
    225: lambda g: 'Enable' if g[5] & 4 else 'Disable',
    206: lambda g: N.note_name(g[6] % 12)[:2].strip(), 207: lambda g: str(g[7]), 208: lambda g: str(g[8]),
}
BACKLIGHT = {204: 0, 214: 1, 224: 2}
GREEN, ORANGE = '#2f7a2f', '#f08a30'


class GlobalPage:
    kind = 'global'

    def __init__(self, app, parent):
        self.app = app
        self.frame = tk.Frame(parent, bg=ui.FACE, width=Scale.x(PAGE_W), height=Scale.y(PAGE_H))
        self.form = f = Form(self.frame, 'GLOBAL_DLG')
        f.command(101, app.edit_global)
        self.swatches = {}
        for cid in BACKLIGHT:
            x, y = f.items[cid]['rect'][:2]
            c = tk.Frame(self.frame, bd=0, bg=GREEN)
            ui.place(c, (x - 2, y - 1, 54, 9))
            self.swatches[cid] = c
        self.refresh()

    def refresh(self):
        g = self.app.lib.glob
        for cid, fn in GLOBAL_VALUES.items():
            self.form.set_text(cid, fn(g))
        for cid, bit in BACKLIGHT.items():
            self.swatches[cid].config(bg=ORANGE if g[4] & (1 << bit) else GREEN)

    def fill(self):
        self.refresh()

    def set_midi_enabled(self, on):
        pass


# =================================================================== Multi
PART_COLS = [(1, 'l'), (15, 'l'), (86, 'l'), (178, 'l'), (209, 'r'), (229, 'r'), (235, 'l'), (267, 'r'),
             (287, 'r'), (296, 'l')]


def part_row(app, buf, n):
    b = n * M.PART_SIZE
    bank = N.bank_index(buf[b], buf[b + 1])
    if bank is None:
        bname, pname = f'{buf[b]:03d}:{buf[b + 1]:03d}', f'{buf[b + 2] + 1:03d}:'
    else:
        bname, pname = N.bank_name(bank), N.numbered(buf[b + 2], N.program_name(bank, buf[b + 2], app.lib))
    return (f'{n + 1:02d}', bname, pname, PR.channel(buf[b + 3]), PR.center64(buf[b + 8]),
            str(buf[b + 0x0A]), PR.pan(buf[b + 0x0E]), str(buf[b + 0x14]), str(buf[b + 0x13]),
            str(buf[b + 0x0B]))


class MultiPage:
    kind = 'multi'

    def __init__(self, app, parent):
        self.app = app
        self.frame = tk.Frame(parent, bg=ui.FACE, width=Scale.x(PAGE_W), height=Scale.y(PAGE_H))
        self.nb = ttk.Notebook(self.frame, takefocus=0)
        ui.place(self.nb, (3, 2, 350, 196))
        self.forms = []
        for m in range(M.N_MULTIS):
            t = R.dialog('MULTI_LIST_TAB')
            fr = tk.Frame(self.nb, bg=ui.FACE, width=Scale.x(t['rect'][2]), height=Scale.y(t['rect'][3]))
            self.nb.add(fr, text=f'Multi {m + 1}')
            f = Form(fr, 'MULTI_LIST_TAB', custom={
                101: lambda form, it, m=m: ui.ListView(form.parent, columns=PART_COLS,
                                                       on_select=lambda i: app.item_selected('multi', self.current()),
                                                       on_double=lambda i, m=m: app.edit_part(m, i))})
            f.set_text(201, 'Edit Common')
            for it, w in f.all:
                if it['text'] == 'Fx Bank':
                    w.config(text='Effect Bank')
            f.move(201, [208, 155, 46, 14])
            f.command(201, lambda m=m: app.edit_multi_common(m))
            f.command(102, lambda m=m: app.transmit('multi', m))
            f.command(104, lambda m=m: app.receive('multi', m))
            self.forms.append(f)
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.app.item_selected('multi', self.current()))
        self.fill()
        for f in self.forms:
            f.w[101].select(0)

    def current(self):
        return self.nb.index('current')

    def selection(self):
        return [self.current()]

    def part(self):
        return self.forms[self.current()].w[101].current() or 0

    def fill(self):
        for m, f in enumerate(self.forms):
            buf = self.app.lib.multis[m]
            f.w[101].set_items([part_row(self.app, buf, n) for n in range(32)])
            c = M.PART_COMMON
            bank = N.fx_bank_index(buf[c + 5])
            vals = {7000: PR.master_tune((buf[c] << 8) | buf[c + 1]), 7004: PR.pan(buf[c + 4]),
                    7003: PR.key_shift(buf[c + 3]), 7002: str(buf[c + 2]),
                    7005: N.FX_BANKS[bank], 7007: N.numbered(buf[c + 7], N.fx_name(bank, buf[c + 7], self.app.lib))}
            for cid, txt in vals.items():
                f.set_text(cid, txt)

    def refresh(self):
        self.fill()

    def set_midi_enabled(self, on):
        for f in self.forms:
            for cid in (102, 104):
                f.enable(cid, on)

