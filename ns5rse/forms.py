"""Builds Tk widgets from the original DIALOG templates (positions in dialog units)."""
import tkinter as tk
from tkinter import ttk

from . import resources as R
from . import ui
from .ui import Scale

WS_VISIBLE, WS_DISABLED = 0x10000000, 0x08000000


def clean(text):
    """Dialog text: '&' marks the mnemonic, '&&' is a literal '&'."""
    if not isinstance(text, str):
        return ''
    return text.replace('&&', '\0').replace('&', '').replace('\0', '&')


class Form:
    """The controls of one dialog template, created inside `parent` at offset `origin` (DLU)."""

    def __init__(self, parent, template, origin=(0, 0), skip=(), custom=None):
        self.parent = parent
        self.tpl = template if isinstance(template, dict) else R.dialog(template)
        self.origin = origin
        self.w = {}          # id -> widget
        self.items = {}      # id -> template item
        self.vars = {}       # id -> tk variable (check boxes / radio buttons)
        self.all = []
        custom = custom or {}
        items = [it for it in self.tpl['items'] if it['id'] not in skip]
        # group boxes and frames first so they stay underneath
        groups = [it for it in items if it['cls'] == 'BUTTON' and it['style'] & 0xF == 7]
        frames = [it for it in items if self.is_frame(it) and it not in groups]
        others = [it for it in items if not self.is_frame(it)]
        for it in groups + frames + others:
            maker = custom.get(it['id']) or custom.get(it['cls'])
            w = maker(self, it) if maker else self.make(it)
            if w is None:
                continue
            self.all.append((it, w))
            if it['id'] != 0xFFFF:
                self.w[it['id']] = w
                self.items[it['id']] = it
            if it['cls'] == 'COMBOBOX':      # the template height includes the drop-down list
                it = dict(it, rect=it['rect'][:3] + [min(it['rect'][3], 13)])
                if it['id'] != 0xFFFF:
                    self.items[it['id']] = it
            if it['style'] & WS_VISIBLE:
                self.place(w, it['rect'])
            if it['style'] & WS_DISABLED:
                self.enable(it['id'], False)

    @staticmethod
    def is_frame(it):
        st = it['style']
        return (it['cls'] == 'BUTTON' and st & 0xF == 7) or (it['cls'] == 'STATIC' and st & 0x1F in (7, 8, 9))

    def place(self, w, rect, dx=0, dy=0):
        x, y, cx, cy = rect
        ox, oy = self.origin
        w.place(x=Scale.x(x + ox + dx), y=Scale.y(y + oy + dy), width=Scale.x(cx), height=Scale.y(cy))
        return w

    def show(self, cid, on=True):
        w = self.w.get(cid)
        if w is None:
            return
        if on:
            self.place(w, self.items[cid]['rect'])
        else:
            w.place_forget()

    def move(self, cid, rect):
        self.items[cid] = dict(self.items[cid], rect=rect)
        self.place(self.w[cid], rect)

    def enable(self, cid, on=True):
        w = self.w.get(cid)
        if w is None:
            return
        if isinstance(w, ui.SpinBox) or isinstance(w, ui.PMBox):
            w.enable(on)
        elif isinstance(w, ttk.Widget):
            w.state(['!disabled'] if on else ['disabled'])
            if isinstance(w, ttk.Combobox) and on:
                w.state(['readonly'])
        elif isinstance(w, (tk.Label, tk.Entry, tk.Button)):
            w.config(state='normal' if on else 'disabled')
        elif hasattr(w, 'enable'):
            w.enable(on)

    def set_text(self, cid, text):
        w = self.w.get(cid)
        if isinstance(w, tk.Entry):
            st = w.cget('state')
            w.config(state='normal')
            w.delete(0, 'end')
            w.insert(0, text)
            w.config(state=st)
        elif isinstance(w, ttk.Labelframe):
            w.config(text=text)
        elif w is not None:
            w.config(text=text)

    def get_text(self, cid):
        w = self.w[cid]
        return w.get() if isinstance(w, tk.Entry) else w.cget('text')

    def check(self, cid, value=None):
        var = self.vars[cid]
        if value is None:
            return var.get()
        var.set(value)

    def command(self, cid, fn):
        w = self.w.get(cid)
        if w is not None:
            w.config(command=fn)

    # --------------------------------------------------------------- factory
    def make(self, it):
        cls, st, text = it['cls'], it['style'], clean(it['text'])
        p = self.parent
        if cls == 'STATIC':
            kind = st & 0x1F
            if kind in (7, 8):          # value boxes: sunken frame
                return tk.Frame(p, bg=ui.FACE, bd=Scale.px(1), relief='sunken', highlightthickness=0)
            if kind == 9:
                return tk.Frame(p, bg=ui.FACE, bd=Scale.px(2), relief='groove', highlightthickness=0)
            if kind == 3:               # icon
                lab = tk.Label(p, image=ui.image('icon_32', 1 if Scale.s == 1 else Scale.s), bg=ui.FACE, bd=0)
                return lab
            anchor = {0: 'w', 1: 'center', 2: 'e'}.get(kind, 'w')
            return tk.Label(p, text=text, anchor=anchor, justify={'w': 'left', 'e': 'right'}.get(anchor, 'center'),
                            bg=ui.FACE, fg=ui.TEXT, bd=0, padx=0, pady=0, font=ui.font(),
                            disabledforeground=ui.GREYTEXT, wraplength=Scale.x(it['rect'][2]) if '\n' not in text and it['rect'][3] > 12 else 0)
        if cls == 'BUTTON':
            kind = st & 0xF
            if kind == 7:
                return ttk.Labelframe(p, text=' ' + text.strip() + ' ' if text.strip() else '')
            if kind in (2, 3, 5, 6):
                var = tk.IntVar()
                self.vars[it['id']] = var
                return ttk.Checkbutton(p, text=text, variable=var, takefocus=0)
            if kind in (4, 9):
                var = self.radio_var(it)
                return ttk.Radiobutton(p, text=text, variable=var, value=it['id'], takefocus=0)
            return ttk.Button(p, text=text, takefocus=0)
        if cls == 'EDIT':
            ro = bool(st & 0x0800)
            e = tk.Entry(p, bd=Scale.px(2), relief='sunken', bg=ui.WINDOW, fg=ui.TEXT, highlightthickness=0,
                         font=ui.font(), readonlybackground=ui.WINDOW, disabledbackground=ui.FACE,
                         insertwidth=Scale.px(1))
            if ro:
                e.config(state='readonly')
            return e
        if cls == 'COMBOBOX':
            return ttk.Combobox(p, state='readonly', font=ui.font(), takefocus=0)
        if cls == 'LISTBOX':
            multicol = bool(st & 0x0200)
            return ui.ListView(p, multicolumn=multicol, extended=bool(st & 0x0800))
        if cls == 'SCROLLBAR':
            return ttk.Scale(p, orient='horizontal' if not st & 1 else 'vertical', from_=0, to=127)
        if cls == 'SpinBox':
            return ui.SpinBox(p)
        if cls == 'PMBox':
            return ui.PMBox(p, text)
        if cls == 'VelWinBar':
            return ui.VelWinBar(p)
        return None

    _radio_groups = None

    def radio_var(self, it):
        """Auto radio buttons share a variable per WS_GROUP run in template order."""
        if self._radio_groups is None:
            self._radio_groups = {}
            var = None
            for t in self.tpl['items']:
                if t['cls'] == 'BUTTON' and t['style'] & 0xF in (4, 9):
                    if var is None or t['style'] & 0x00020000:
                        var = tk.IntVar()
                    self._radio_groups[t['id']] = var
                elif t['style'] & 0x00020000:
                    var = None
        var = self._radio_groups[it['id']]
        self.vars[it['id']] = var
        return var


def dialog_size(template):
    t = R.dialog(template)
    return Scale.x(t['rect'][2]), Scale.y(t['rect'][3])


class ModalDialog:
    """A Toplevel built from a template, with OK (1) / Cancel (2) handling."""

    def __init__(self, master, template, title=None, custom=None, skip=(), size=None, modal=True):
        self.master = master
        self.top = tk.Toplevel(master, bg=ui.FACE)
        self.top.withdraw()
        tpl = R.dialog(template)
        self.top.title(title if title is not None else tpl['caption'] or 'NS5R SoundEditor')
        self.top.resizable(False, False)
        w, h = size or dialog_size(template)
        self.frame = tk.Frame(self.top, bg=ui.FACE, width=w, height=h)
        self.frame.pack()
        self.form = Form(self.frame, template, custom=custom, skip=skip)
        self.result = None
        if 1 in self.form.w:
            self.form.command(1, self.ok)
        if 2 in self.form.w:
            self.form.command(2, self.cancel)
        self.top.protocol('WM_DELETE_WINDOW', self.cancel)
        self.top.bind('<Escape>', lambda e: self.cancel())
        self.modal = modal
        self.top.transient(master.winfo_toplevel())

    def show(self, wait=True):
        t = self.top
        t.update_idletasks()
        m = self.master.winfo_toplevel()
        x = m.winfo_rootx() + (m.winfo_width() - t.winfo_reqwidth()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - t.winfo_reqheight()) // 3
        t.geometry(f'+{max(0, x)}+{max(0, y)}')
        t.deiconify()
        t.lift()
        if self.modal:
            try:
                t.grab_set()
            except tk.TclError:
                pass
        t.focus_set()
        if wait and self.modal:
            self.master.wait_window(t)
        return self.result

    def ok(self):
        self.result = True
        self.close()

    def cancel(self):
        self.result = None
        self.close()

    def close(self):
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        self.top.destroy()
