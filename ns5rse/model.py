"""The editor's document: everything the NS5R stores, plus the editor's remark list.

Layouts follow the NS5R Exclusive Data Format tables (Program 158, Combination 126,
Drum Kit 1358, Effect 38, Multi 8566, Global 10 bytes).  Multi-byte values are MSB first.
"""

PROG_SIZE, COMBI_SIZE, KIT_SIZE, FX_SIZE, MULTI_SIZE, GLOBAL_SIZE = 158, 126, 1358, 38, 8566, 10
REMARK_SIZE = 740                 # 5 x 128 remark numbers + 10 names x 10 chars
N_PROGS = N_COMBIS = N_FX = 128
N_KITS, N_MULTIS = 2, 4
OSC_SIZE, OSC1, OSC2 = 72, 14, 86
TIMBRE_SIZE, TIMBRE0 = 14, 14
PART_SIZE, PART_COMMON, MULTI_FX, MULTI_KITS = 92, 0x0B80, 0x0C18, 0x0C3E
INST_SIZE, N_INST, FIRST_KEY = 14, 97, 12      # drum kits cover C0 (12) .. C8 (108)
REMARK_KINDS = {'program': 0, 'combi': 1, 'drum': 2, 'effect': 3, 'multi': 4}


def s8(v):
    return v - 256 if v >= 128 else v


def u8(v):
    return v & 0xFF


def text(b):
    return bytes(b).decode('latin-1').rstrip(' \0')


def set_text(buf, off, n, s):
    raw = s.encode('latin-1', 'replace')[:n].ljust(n, b' ')
    buf[off:off + n] = bytes(c if 0x20 <= c < 0x7F else 0x20 for c in raw)


# ------------------------------------------------------------- defaults
def init_program():
    p = bytearray(PROG_SIZE)
    set_text(p, 0, 10, '')
    p[11], p[12], p[13] = 0x50, 0, 0              # User Effect 001
    for base in (OSC1, OSC2):
        o = bytearray(OSC_SIZE)
        o[3] = 127                                # level
        o[6] = 10                                 # pitch slope +1.0
        o[7], o[8] = 1, 127                       # velocity window
        o[29] = 127                               # cutoff
        o[63], o[65], o[67] = 127, 127, 127       # VDA EG attack level, break point, sustain
        o[69], o[70], o[71] = 64, 127, 127        # pan, C send, D send
        p[base:base + OSC_SIZE] = o
    return p


def init_combi():
    c = bytearray(COMBI_SIZE)
    set_text(c, 0, 10, '')
    c[10] = 0x50
    for t in range(8):
        b = TIMBRE0 + t * TIMBRE_SIZE
        c[b + 3] = 127            # volume
        c[b + 4] = 64             # pan
        c[b + 7], c[b + 8] = 0, 127
        c[b + 9], c[b + 10] = 1, 127
        c[b + 13] = 0x3F          # all control filter switches on
    return c


def init_effect():
    e = bytearray(FX_SIZE)
    set_text(e, 0, 8, '')
    return e


def init_kit():
    """A new document's user kit: sample 0 on every key, level 127, Note ON/OFF on, Multi
    assign, relative parameters 0 and pan centred (as the original editor shows it)."""
    inst = bytes([0, 0, 0, 0, 127, 0, 7, 0, 0, 0, 0, 64, 0, 0])
    return bytearray(inst * N_INST)


def init_part(n):
    p = bytearray(PART_SIZE)
    drum = n in (9, 25)
    p[0] = 62 if drum else 0      # KORG drum bank / GM-a
    p[3] = n                       # A01..A16, B01..B16
    p[4], p[5] = 0xFF, 0xFF
    p[6] = 1                       # poly
    p[7] = 1 if drum else 0
    p[8] = 0x40
    p[0x0A], p[0x0B] = 100, 127
    p[0x0C], p[0x0D] = 64, 64
    p[0x0E] = 64
    p[0x0F], p[0x10] = 0, 127
    p[0x11], p[0x12] = 16, 17
    p[0x13], p[0x14] = 0, 40
    p[0x15] = 1
    for off in range(0x16, 0x2E):
        p[off] = 0x40
    for grp in range(6):           # MOD, BEND, CAf, PAf, AC1, AC2
        b = 0x2A + grp * 7
        p[b:b + 4] = bytes([0x40] * 4)
    p[0x2E] = 10                   # modulation -> pitch LFO depth
    p[0x31] = 0x42                 # pitch bend +2
    p[0x54], p[0x55] = 0, 0
    p[0x56:0x5A] = bytes([0x40] * 4)
    p[0x5A], p[0x5B] = 1, 127
    return p


def init_multi():
    m = bytearray(MULTI_SIZE)
    for n in range(32):
        m[n * PART_SIZE:(n + 1) * PART_SIZE] = init_part(n)
    c = PART_COMMON
    m[c], m[c + 1] = 0x04, 0x00    # master tune 0x400 = 0 cent
    m[c + 2], m[c + 3], m[c + 4] = 127, 0x40, 0x40
    for i in range(128):
        m[c + 0x18 + i] = 3        # program change -> Ignore
    kit = init_kit()
    for k in range(4):
        b = MULTI_KITS + k * KIT_SIZE
        m[b:b + KIT_SIZE] = kit
    return m


def init_global():
    return bytearray([0, 0, 0, 0, 0b010, 0b111, 9, 100, 12, 0])


# -------------------------------------------------------------- the document
class Library:
    """All banks of one .NS5 document."""

    def __init__(self):
        self.programs = [init_program() for _ in range(N_PROGS)]
        self.combis = [init_combi() for _ in range(N_COMBIS)]
        self.kits = [init_kit() for _ in range(N_KITS)]
        self.effects = [init_effect() for _ in range(N_FX)]
        self.multis = [init_multi() for _ in range(N_MULTIS)]
        self.glob = init_global()
        self.remarks = bytearray(REMARK_SIZE)
        self.listeners = []

    # change notification: fn(kind, index)
    def changed(self, kind, index=None):
        for fn in list(self.listeners):
            fn(kind, index)

    def block(self, kind, index=0):
        return {'program': self.programs, 'combi': self.combis, 'drum': self.kits,
                'effect': self.effects, 'multi': self.multis}[kind][index] if kind != 'global' else self.glob

    def program_name(self, i):
        return text(self.programs[i][0:10])

    def combi_name(self, i):
        return text(self.combis[i][0:10])

    def effect_name(self, i):
        return text(self.effects[i][0:8])

    # remarks: 10 user-defined labels, attached per item
    def remark_label(self, n):
        if not 1 <= n <= 10:
            return ''
        b = 640 + (n - 1) * 10
        return text(self.remarks[b:b + 10])

    def set_remark_label(self, n, s):
        if 1 <= n <= 10:
            set_text(self.remarks, 640 + (n - 1) * 10, 10, s)

    def remark_of(self, kind, i):
        return self.remarks[REMARK_KINDS[kind] * 128 + i]

    def set_remark_of(self, kind, i, n):
        self.remarks[REMARK_KINDS[kind] * 128 + i] = n

    # ------------------------------------------------------- .NS5 files
    SECTIONS = [  # header slot, attribute, item size
        (0x10, 'programs', PROG_SIZE), (0x14, 'combis', COMBI_SIZE), (0x18, 'kits', KIT_SIZE),
        (0x1C, 'glob', GLOBAL_SIZE), (0x20, 'effects', FX_SIZE), (0x24, 'multis', MULTI_SIZE),
        (0x28, 'remarks', REMARK_SIZE)]

    def to_bytes(self):
        """Native SENS5R document: 64-byte header with (3-byte offset, 1-byte count) per section."""
        head = bytearray(0x40)
        head[0:3] = b'\x72\x05\x00'
        body = bytearray()
        for slot, attr, size in self.SECTIONS:
            items = getattr(self, attr)
            items = items if isinstance(items, list) else [items]
            off = 0x40 + len(body)
            head[slot:slot + 4] = bytes([off & 0xFF, (off >> 8) & 0xFF, off >> 16, len(items) & 0xFF])
            for it in items:
                body += it
        return bytes(head + body)

    @classmethod
    def from_bytes(cls, b):
        if len(b) < 0x40 or b[0] != 0x72:
            raise ValueError('not an NS5R SoundEditor (.NS5) file')
        lib = cls()
        for slot, attr, size in cls.SECTIONS:
            off = b[slot] | (b[slot + 1] << 8) | (b[slot + 2] << 16)
            count = b[slot + 3] or (128 if attr in ('programs', 'combis', 'effects') else 0)
            if not off:
                continue
            cur = getattr(lib, attr)
            if isinstance(cur, list):
                for i in range(min(count, len(cur))):
                    chunk = b[off + i * size:off + (i + 1) * size]
                    if len(chunk) == size:
                        cur[i] = bytearray(chunk)
            else:
                chunk = b[off:off + size]
                if len(chunk) == size:
                    setattr(lib, attr, bytearray(chunk))
        return lib

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.to_bytes())

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            return cls.from_bytes(f.read())

    def copy_from(self, other):
        for attr in ('programs', 'combis', 'kits', 'effects', 'multis', 'glob', 'remarks'):
            v = getattr(other, attr)
            setattr(self, attr, [bytearray(x) for x in v] if isinstance(v, list) else bytearray(v))
