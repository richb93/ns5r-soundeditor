"""Talking to the NS5R: selecting what it edits, parameter changes, dumps and writes.

Editing works like the original editor: the item being edited is selected on the NS5R
(bank select / program change on part 1, then a Mode Change), its data is dumped into the
edit buffer, and each edit is then sent as a small Parameter Change (function 08), or as a
GS/XG-style part parameter (function 12) for Multi data.  Parameters without a message are
sent by re-dumping the whole block.
"""
from . import model as M
from . import names as N
from . import sysex as X

KIND_MODE = {'program': X.MODE_PROG_EDIT, 'combi': X.MODE_COMBI_EDIT, 'drum': X.MODE_DRUM_EDIT,
             'effect': X.MODE_EFFECT_EDIT, 'multi': X.MODE_MULTI, 'global': X.MODE_GLOBAL}


def s14(v):
    return v & 0x3FFF


# ----------------------------------------------------------------- Program parameter numbers
def _osc_table():
    """relative OSC offset -> parameter number (LSB), or ('bits', first) for switch bytes."""
    t = {0: 0, 1: 0, 2: 1}
    for rel in range(3, 10):
        t[rel] = rel - 1
    for rel in range(10, 34):
        t[rel] = rel - 1
    t[34] = ('bits', 33)
    for rel in range(35, 40):
        t[rel] = rel + 2
    t[40] = ('bits', 42)
    for rel in range(41, 58):
        t[rel] = rel + 5
    t[58] = ('bits', 63)
    t[59], t[60] = 67, 68
    t[61] = ('bits', 69)
    for rel in range(62, 72):
        t[rel] = rel + 11
    return t


OSC_PARAM = _osc_table()
PM_RELS = {34, 40, 58, 61}
SIGNED_OSC = {r - M.OSC1 for r in (18, 19, 20, 29, 30, 31, 32, 34, 37, 46, 47, 50, 51, 52, 56, 58, 60,
                                     62, 70, 71, 73)}


def switch_value(byte, j):
    if not byte & (1 << j):
        return 0
    return 2 if byte & (0x10 << j) else 1


def program_params(buf, off):
    if off < 10:
        return [(0, off, buf[off])]
    if off < 14:
        return [(0, off, buf[off] if off != 10 else min(buf[off], 2))]
    osc = 1 if off < M.OSC2 else 2
    base = M.OSC1 if osc == 1 else M.OSC2
    rel = off - base
    if rel in (0, 1):
        return [(osc, 0, (buf[base] << 8) | buf[base + 1])]
    if rel == 2:
        v = M.s8(buf[off])
        return [(osc, 1, {-24: 0, -12: 1, 0: 2, 12: 3}.get(v, 2))]
    p = OSC_PARAM[rel]
    if isinstance(p, tuple):
        return [(osc, p[1] + j, switch_value(buf[off], j)) for j in range(4)]
    v = M.s8(buf[off]) if rel in SIGNED_OSC else buf[off]
    return [(osc, p, v)]


def combi_params(buf, off):
    if off < 13:
        return [(0, off, buf[off])]
    if off == 13:
        return []
    t, rel = divmod(off - M.TIMBRE0, M.TIMBRE_SIZE)
    b = M.TIMBRE0 + t * M.TIMBRE_SIZE
    if rel in (0, 1):
        idx = N.bank_index(buf[b], buf[b + 1])
        if idx is None:
            return None
        return [(t + 1, 0, idx - 5 if idx >= 77 else idx)]
    if rel == 13:
        return [(t + 1, 12 + j, (buf[off] >> j) & 1) for j in range(6)]
    v = buf[off]
    if rel in (11, 12):
        v = M.s8(v)
    return [(t + 1, rel - 1, v)]


def drum_params(buf, off, base=0):
    i, rel = divmod(off - base, M.INST_SIZE)
    key = M.FIRST_KEY + i
    b = base + i * M.INST_SIZE
    if rel in (0, 1):
        return [(key, 0, (buf[b] << 8) | buf[b + 1])]
    if rel == 6:
        v = buf[b + 6]
        return [(key, 5, v & 1), (key, 6, (v >> 1) & 1), (key, 7, (v >> 2) & 1)]
    lsb = {2: 1, 3: 2, 4: 3, 5: 4, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 14}[rel]
    v = M.s8(buf[off]) if rel in (2, 3, 7, 8, 9, 10) else buf[off]
    return [(key, lsb, v)]


def effect_params(buf, off):
    if off < 10:
        return [(0, off, buf[off])]
    if 0x0A <= off <= 0x0D:
        e, lr = divmod(off - 0x0A, 2)
        return [(e + 1, 2 + lr, buf[off])]
    placement = (buf[0x10] >> 4) & 3
    if off in (0x0E, 0x0F):
        if placement == 3:
            k = (off - 0x0E) * 2
            return [(0, 14 + k, buf[off] >> 4), (0, 15 + k, buf[off] & 0x0F)]
        return [(0, 12 + off - 0x0E, buf[off])]
    if off == 0x10:
        v = buf[off]
        return [(0, 10, 1 if v & 3 else 0), (0, 11, 1 if v & 12 else 0), (0, 18, placement)]
    if 0x11 <= off <= 0x18:
        return [(1, 4 + off - 0x11, buf[off])]
    if 0x1B <= off <= 0x22:
        return [(2, 4 + off - 0x1B, buf[off])]
    if off in (0x19, 0x23):
        return [((off - 0x19) // 10 + 1, 0, buf[off])]
    if off in (0x1A, 0x24):
        return [((off - 0x1A) // 10 + 1, 1, M.s8(buf[off]))]
    return []


def global_params(buf, off):
    if off < 3:
        return [(0, off, buf[off])]
    if off == 3:
        return [(0, 3 + j, (buf[3] >> j) & 1) for j in range(6)]
    if off in (4, 5):
        first = 9 if off == 4 else 12
        return [(0, first + j, (buf[off] >> j) & 1) for j in range(3)]
    return [(0, 9 + off, buf[off])]


# ----------------------------------------------------------------- Multi: function 12 addresses
_PART_ADDR = {0: 0x00, 1: 0x01, 2: 0x02, 3: 0x08, 6: 0x09, 7: 0x0A, 8: 0x0B, 0x0A: 0x10, 0x0B: 0x11,
              0x0C: 0x12, 0x0D: 0x13, 0x0E: 0x14, 0x0F: 0x15, 0x10: 0x16, 0x11: 0x3E, 0x12: 0x3F,
              0x13: 0x17, 0x14: 0x18, 0x15: 0x31, 0x54: 0x70, 0x55: 0x71, 0x5A: 0x76, 0x5B: 0x77}
for _o in range(0x16, 0x1E):
    _PART_ADDR[_o] = 0x19 + _o - 0x16
for _o in range(0x1E, 0x2A):
    _PART_ADDR[_o] = 0x32 + _o - 0x1E
for _g, _a in enumerate((0x40, 0x48, 0x50, 0x58, 0x60, 0x68)):
    for _k in range(7):
        _PART_ADDR[0x2A + _g * 7 + _k] = _a + _k
for _o in range(0x56, 0x5A):
    _PART_ADDR[_o] = 0x72 + _o - 0x56
_RX_BITS = {4: (0x26, 0x24, 0x21, 0x22, 0x2D, 0x2E, 0x23, 0x25), 5: (0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2F, 0x30)}
_DRUM_ADDR = {2: 0x00, 3: 0x01, 4: 0x02, 5: 0x03, 11: 0x04, 12: 0x05, 13: 0x06, 7: 0x0B, 8: 0x0C,
              9: 0x0D, 10: 0x0E}


def multi_addresses(buf, off):
    """[(a1, a2, a3, [values])] for a Multi byte, or None if only a dump will do."""
    if off < M.PART_COMMON:
        n, rel = divmod(off, M.PART_SIZE)
        if rel in _RX_BITS:
            return [(0x01, n, a, [(buf[off] >> j) & 1]) for j, a in enumerate(_RX_BITS[rel])]
        if rel == 9:
            v = buf[off] ^ 0x80
            return [(0x01, n, 0x0C, [v >> 4]), (0x01, n, 0x0D, [v & 0x0F])]
        if rel in _PART_ADDR:
            return [(0x01, n, _PART_ADDR[rel], [buf[off]])]
        return None
    c = off - M.PART_COMMON
    if off < M.MULTI_FX:
        cb = M.PART_COMMON
        if c in (0, 1):
            v = (buf[cb] << 8) | buf[cb + 1]
            return [(0, 0, 0, [(v >> 12) & 15, (v >> 8) & 15, (v >> 4) & 15, v & 15])]
        if 2 <= c <= 7:
            return [(0, 0, {2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9}[c], [buf[off]])]
        if 8 <= c < 0x18:
            return [(0, 1, c - 8, [buf[off]])]
        return [(0, 2, c - 0x18, [buf[off]])]
    if off >= M.MULTI_KITS:
        k, rest = divmod(off - M.MULTI_KITS, M.KIT_SIZE)
        i, rel = divmod(rest, M.INST_SIZE)
        key = M.FIRST_KEY + i
        if rel == 6:
            v = buf[off]
            return [(0x30 + k, key, 0x0A, [v & 1]), (0x30 + k, key, 0x09, [(v >> 1) & 1]),
                    (0x30 + k, key, 0x08, [(v >> 2) & 1])]
        if rel in _DRUM_ADDR:
            v = buf[off]
            if rel in (2, 3, 7, 8, 9, 10):     # function-12 drum values are centred on 64
                v = max(0, min(127, M.s8(v) + 64))
            return [(0x30 + k, key, _DRUM_ADDR[rel], [v])]
    return None


# ----------------------------------------------------------------- the link
class Device:
    def __init__(self, app):
        self.app = app
        self.target = None         # what the NS5R edit buffer currently holds: (kind, index)
        self.mode = None
        self.pending_dumps = {}    # kind -> deadline for a full re-dump

    @property
    def ch(self):
        return self.app.settings.get('excl_channel', 0)

    def send(self, data):
        try:
            self.app.midi.send_bytes(data)
        except Exception as e:
            self.app.status(f'MIDI error: {e}')

    def connected(self):
        return self.app.midi.out is not None

    # ------------------------------------------------------- selecting what the NS5R edits
    def set_mode(self, mode):
        self.send(X.mode_change(self.ch, mode))
        self.mode = mode

    def select_part_program(self, msb, lsb, prog, part=0):
        self.send(X.part_param(self.ch, 0x01, part, 0x00, [msb]))
        self.send(X.part_param(self.ch, 0x01, part, 0x01, [lsb]))
        self.send(X.part_param(self.ch, 0x01, part, 0x02, [prog]))

    def select(self, kind, index, dump=True):
        """Make the NS5R edit `kind` number `index` and load our data into its edit buffer."""
        lib = self.app.lib
        if kind == 'program':
            self.select_part_program(0x50, 0, index)
        elif kind == 'combi':
            self.select_part_program(0x58, 0, index)
        elif kind == 'drum' and index < M.N_KITS:
            self.select_part_program(0x3E, 0, 72 + index)
        if kind == 'multi':
            self.set_mode(X.MODE_MULTI)
            self.send(X.param_change(self.ch, 1, 0, index))
        else:
            self.set_mode(KIND_MODE[kind])
        self.target = (kind, index)
        if dump:
            self.send(X.dump(self.ch, kind, lib.block(kind, index)))

    def ensure(self, kind, index):
        if self.target != (kind, index):
            self.select(kind, index)
            return True
        return False

    # ------------------------------------------------------- edits
    def edited(self, kind, index, offsets):
        """The editor changed bytes `offsets` of block (kind, index): tell the NS5R."""
        if not self.connected():
            return
        if self.ensure(kind, index):
            return                            # the fresh dump already carries the change
        buf = self.app.lib.block(kind, index)
        msgs = []
        for off in sorted(set(offsets)):
            if kind == 'multi':
                addrs = multi_addresses(buf, off)
                if addrs is None:
                    return self.redump(kind, index)
                msgs += [X.part_param(self.ch, a1, a2, a3, v) for a1, a2, a3, v in addrs]
                continue
            fn = {'program': program_params, 'combi': combi_params, 'drum': drum_params,
                  'effect': effect_params, 'global': global_params}[kind]
            params = fn(buf, off)
            if params is None:
                return self.redump(kind, index)
            msgs += [X.param_change(self.ch, lsb, msb, s14(v)) for msb, lsb, v in params]
        seen = set()
        for m in msgs:
            if m not in seen:
                seen.add(m)
                self.send(m)

    def redump(self, kind, index):
        self.send(X.dump(self.ch, kind, self.app.lib.block(kind, index)))

    # ------------------------------------------------------- transmit / write / receive
    def transmit(self, kind, index, dest=None):
        """Send one item into the NS5R's edit buffer and store it at `dest` (default: same number)."""
        self.select(kind, index)
        if kind in X.WRITE:
            self.send(X.write_request(self.ch, kind, index if dest is None else dest))

    def transmit_all(self, what):
        lib = self.app.lib
        blob = {'all_program': b''.join(lib.programs), 'all_combi': b''.join(lib.combis),
                'all_drum': b''.join(lib.kits), 'all_effect': b''.join(lib.effects),
                'all_multi': b''.join(lib.multis), 'global': bytes(lib.glob)}[what]
        if what == 'all_multi':
            self.set_mode(X.MODE_MULTI)
        self.send(X.dump(self.ch, what, blob))
        self.target = None

    def request(self, kind):
        self.send(X.request(self.ch, kind))

    def all_notes_off(self):
        for ch in range(16):
            self.app.midi.control(ch, 0x7B, 0)

    def gm_on(self):
        self.send(bytes([0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]))

    def reset(self, which):
        addr = {'all': 0x7C, 'drum': 0x7D, 'xg': 0x7E, 'gs': 0x7F}[which]
        self.send(X.part_param(self.ch, 0, 0, addr, [0]))
        self.target = None
