"""Connects template controls to bytes of a data block through `params.P` specs."""
import tkinter as tk
from tkinter import ttk

from . import ui


class Binder:
    """form: forms.Form; block(): the bytearray; base(cid): byte offset added for a control;
    changed(offsets): called after the user edits."""

    def __init__(self, form, block, changed, base=lambda cid: 0):
        self.form, self.block, self.changed, self.base = form, block, changed, base
        self.specs = {}
        self.extra = []          # (fn) refreshers for custom displays

    def bind(self, cid, spec, widget=None):
        w = widget or self.form.w.get(cid)
        if w is None:
            return
        self.specs[cid] = (spec, w)
        if isinstance(w, ui.SpinBox):
            w.lo, w.hi, w.fmt = spec.lo, spec.hi, spec.text
            w.on_change = lambda v, c=cid: self.write(c, v)
        elif isinstance(w, ttk.Combobox):
            w.config(values=list(spec.items), state='readonly',
                     height=len(spec.items))
            w.bind('<<ComboboxSelected>>', lambda e, c=cid, cw=w: (self.write(c, cw.current()),
                                                                   cw.selection_clear()))
        elif isinstance(w, ttk.Checkbutton):
            var = self.form.vars[cid]
            w.config(command=lambda c=cid, v=var: self.write(c, v.get()))
        elif isinstance(w, ttk.Scale):
            w.config(from_=spec.lo, to=spec.hi, command=lambda s, c=cid: self.write(c, int(float(s) + 0.5)))
        elif isinstance(w, ui.PMBox):
            pass

    def bind_all(self, specs):
        for cid, spec in specs.items():
            if cid in self.form.w:
                self.bind(cid, spec)

    def value(self, cid):
        spec, _ = self.specs[cid]
        return spec.get(self.block(), self.base(cid))

    def write(self, cid, v, refresh=True):
        spec, _ = self.specs[cid]
        buf = self.block()
        b = self.base(cid)
        if spec.get(buf, b) == v:
            return
        spec.put(buf, v, b)
        offs = [b + spec.off] + ([b + spec.off + 1] if spec.word else [])
        if refresh:
            self.refresh()
        self.changed(offs)

    def refresh(self):
        buf = self.block()
        for cid, (spec, w) in self.specs.items():
            v = spec.get(buf, self.base(cid))
            if isinstance(w, ui.SpinBox):
                if w.focus_get() is not w.entry or w.value != v:
                    w.set(v)
            elif isinstance(w, ttk.Combobox):
                if spec.items and 0 <= v < len(spec.items):
                    w.current(v)
            elif isinstance(w, ttk.Checkbutton):
                self.form.vars[cid].set(1 if v else 0)
            elif isinstance(w, ttk.Scale):
                cmd = w.cget('command')
                w.config(command='')
                w.set(v)
                w.config(command=cmd)
        for fn in self.extra:
            fn()


def entry_bind(entry, on_commit):
    """Call on_commit(text) when an Entry is confirmed (Return or focus out)."""
    entry.bind('<Return>', lambda e: on_commit(entry.get()))
    entry.bind('<FocusOut>', lambda e: on_commit(entry.get()))


def set_entry(entry, text):
    if entry.focus_get() is entry:
        return
    st = entry.cget('state')
    entry.config(state='normal')
    entry.delete(0, 'end')
    entry.insert(0, text)
    entry.config(state=st)


def pm_state(byte, j):
    if not byte & (1 << j):
        return 0
    return 2 if byte & (0x10 << j) else 1


def pm_apply(byte, j, state):
    byte &= ~((1 << j) | (0x10 << j)) & 0xFF
    if state:
        byte |= 1 << j
        if state == 2:
            byte |= 0x10 << j
    return byte


def combo_set(w, values, index):
    w.config(values=values, state='readonly', height=min(len(values), 16))
    if 0 <= index < len(values):
        w.current(index)


tk  # noqa: B018 (kept for type hints in callers)
