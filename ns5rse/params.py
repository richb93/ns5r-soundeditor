"""Parameter definitions, keyed by the original control IDs.

Control IDs encode the data offset: 1000+n Program (OSC1; OSC2 is +72 in the data),
2000+n Combination (timbre 1; timbre t is +14*t), 3000+n Multi part, 4000+n drum instrument,
5000+n Effect, 6000+n Global, 7000+n Multi part common.  Ranges follow the editor's own
SpinBox set-up code (seg15/16/20), which in a few places differs from KORG's printed table.
"""
from .names import note_name


class P:
    """One parameter: a byte (or bit field / 16-bit MSB-first word) in a data block."""

    def __init__(self, off, lo=0, hi=127, fmt=str, signed=None, mask=0xFF, shift=0, word=False,
                 items=None, label=''):
        self.off, self.lo, self.hi, self.fmt = off, lo, hi, fmt
        self.signed = lo < 0 if signed is None else signed
        self.mask, self.shift, self.word, self.items, self.label = mask, shift, word, items, label
        if items is not None:
            self.lo, self.hi = 0, len(items) - 1

    def get(self, buf, base=0):
        o = base + self.off
        if self.word:
            return (buf[o] << 8) | buf[o + 1]
        v = (buf[o] & self.mask) >> self.shift
        if self.signed and self.mask == 0xFF and v >= 128:
            v -= 256
        return v

    def put(self, buf, v, base=0):
        o = base + self.off
        v = max(self.lo, min(self.hi, int(v)))
        if self.word:
            buf[o], buf[o + 1] = (v >> 8) & 0xFF, v & 0xFF
        else:
            buf[o] = (buf[o] & ~self.mask & 0xFF) | (((v & 0xFF) << self.shift) & self.mask)

    def text(self, v):
        if self.items is not None:
            return self.items[v] if 0 <= v < len(self.items) else '?'
        return self.fmt(v)


# ------------------------------------------------------------------ formats
def signed(v):
    return f'{v:+d}' if v else '0'


def pan(v):
    """1..64..127 -> L63 .. CNT .. R63 (0 = random where allowed)."""
    if v == 0:
        return 'RND'
    if v == 64:
        return 'CNT'
    return f'L{64 - v}' if v < 64 else f'R{v - 64}'


def pan101(v):
    """Effect output pan: 0=OFF, 1=R ... 101=L (R:L ratio)."""
    if v == 0:
        return 'Off'
    if v == 1:
        return 'Right'
    if v == 101:
        return 'Left'
    return f'{v - 1}:{101 - v}'


def note(v):
    return note_name(v)


def slope(v):
    return f'{v / 10:+.1f}'


def center64(v):
    return str(v - 64)


def center64_signed(v):
    return f'{v - 64:+d}' if v != 64 else '0'


def master_tune(v):
    c = v - 1024
    return f"{'+' if c >= 0 else '-'}{abs(c) // 10:03d}.{abs(c) % 10}"


def key_shift(v):
    return f'{v - 64:+03d}' if v != 64 else '+00'


def channel(v):
    if v >= 32:
        return 'OFF'
    return f"{'AB'[v // 16]}{v % 16 + 1:02d}"


def plus1(v):
    return str(v + 1)


def onoff(v):
    return 'ON' if v else 'OFF'


OCTAVES = ["32'", "16'", "8'", "4'"]
OCT_VALUES = [-24, -12, 0, 12]
WAVES = ['Triangle', 'Saw Up', 'Saw Down', 'Square 1', 'Square 2', 'Random']
KBD_MODES = ['Off', 'Low', 'High', 'All']
OSC_MODES = ['Single', 'Double', 'Drum']
PORTS = ['Synth A', 'Synth B', 'External']
PROG_PORTS = ['Synth A', 'Synth B', 'External', 'Ignore']
FX_MOD_SOURCES = ['None', 'Joy Stick(+Y)', 'Joy Stick(-Y)', 'After Touch', 'Ass Pedal 1', 'Ass Pedal 2',
                  'VDA EG']
PLACEMENTS = ['Serial', 'Parallel 1', 'Parallel 2', 'Parallel 3']


# ------------------------------------------------------------------ program (offsets for OSC1)
def _s(off):
    return P(off, -128, 127)


PROGRAM = {
    1010: P(10, items=OSC_MODES),
    1013: P(13, 0, 127, plus1),
    1014: P(14, 0, 527, word=True),
    1016: P(16, items=OCTAVES),          # stored as -24/-12/0/12, see osc_octave()
    1017: P(17), 1018: P(18, -12, 12), 1019: P(19, -99, 99), 1020: P(20, -10, 20, slope),
    1021: P(21, 1, 127), 1022: P(22, 1, 127), 1023: P(23),
    1024: P(24, items=WAVES), 1025: P(25), 1026: P(26), 1027: P(27), 1028: P(28),
    1029: _s(29), 1030: _s(30), 1031: _s(31), 1032: _s(32), 1033: P(33), 1034: _s(34), 1035: P(35),
    1036: P(36), 1037: _s(37),
    1038: P(38, items=WAVES), 1039: P(39), 1040: P(40), 1041: P(41), 1042: P(42),
    1043: P(43), 1044: P(44, 0, 127, note), 1045: P(45, items=KBD_MODES), 1046: _s(46), 1047: _s(47),
    1049: P(49), 1050: _s(50), 1051: _s(51), 1052: _s(52), 1053: P(53),
    1055: P(55), 1056: _s(56), 1057: P(57), 1058: _s(58), 1059: P(59), 1060: _s(60), 1061: P(61),
    1062: _s(62),
    1063: P(63, items=WAVES), 1064: P(64), 1065: P(65), 1066: P(66), 1067: P(67),
    1068: P(68, 0, 127, note), 1069: P(69, items=KBD_MODES), 1070: _s(70), 1071: _s(71),
    1073: _s(73), 1074: P(74), 1076: P(76), 1077: P(77), 1078: P(78), 1079: P(79), 1080: P(80),
    1081: P(81), 1082: P(82),
    1083: P(83, 0, 127, pan), 1084: P(84), 1085: P(85),
}
# time switch bytes (PMBox): byte offset for each group of AT/DT/ST/RT boxes
PM_BYTES = {1548: 48, 1554: 54, 1572: 72, 1375: 75}
OSC_PARAMS = {k for k in PROGRAM if k >= 1014}


def osc_octave_index(raw):
    v = raw - 256 if raw >= 128 else raw
    return OCT_VALUES.index(v) if v in OCT_VALUES else 2


# ------------------------------------------------------------------ combination timbre (timbre 1)
COMBI_TIMBRE = {
    2016: P(16, 0, 127, plus1), 2017: P(17), 2018: P(18, 0, 127, pan), 2019: P(19), 2020: P(20),
    2021: P(21, 0, 127, note), 2022: P(22, 0, 127, note), 2023: P(23, 1, 127), 2024: P(24, 1, 127),
    2025: P(25, -24, 24), 2026: P(26, -50, 50),
}
COMBI_SWITCHES = {2527 + b: P(27, 0, 1, mask=1 << b, shift=b) for b in range(6)}
COMBI_SWITCH_NAMES = ['Note ON/OFF', 'Control Change', 'Pitch Bend', 'After Touch', 'Damper', 'Portament']

# ------------------------------------------------------------------ drum instrument (14 bytes)
DRUM_SIGNED = (2, 3, 7, 8, 9, 10)
DRUM = {
    # relative parameters are signed bytes centred on 0 (the editor's SpinBox range is -64..63)
    4000: P(0, 0, 285, word=True), 4002: P(2, -64, 63), 4003: P(3, -64, 63),
    4004: P(4), 4005: P(5, 1, 127), 4007: P(7, -64, 63), 4008: P(8, -64, 63),
    4009: P(9, -64, 63), 4010: P(10, -64, 63), 4011: P(11, 1, 127, pan),
    4012: P(12), 4013: P(13),
    4506: P(6, 0, 1, mask=1, shift=0), 4507: P(6, 0, 1, mask=2, shift=1),
    4508: P(6, 0, 1, mask=4, shift=2, items=['Single', 'Multi']),
}

# ------------------------------------------------------------------ global
GLOBAL = {
    6000: P(0, items=['31.25 Kbps', '38.4 Kbps']),
    6001: P(1, items=['Default', '05R/W']),
    6002: P(2, 0, 15, plus1),
    6006: P(6, 0, 11, lambda v: note_name(v)[:2].strip()),
    6007: P(7, 1, 127), 6008: P(8, 0, 31), 6009: P(9, 1, 32),
    6053: P(3, 0, 1, mask=0x20, shift=5, items=['Native', 'Emulate']),
}
for _b in range(5):
    GLOBAL[6003 + 10 * _b] = P(3, 0, 1, mask=1 << _b, shift=_b)
for _b in range(3):
    GLOBAL[6004 + 10 * _b] = P(4, 0, 1, mask=1 << _b, shift=_b, items=['Green', 'Orange'])
    GLOBAL[6005 + 10 * _b] = P(5, 0, 1, mask=1 << _b, shift=_b)

# ------------------------------------------------------------------ multi part (92 bytes)
PART = {
    3002: P(2, 0, 127, plus1), 3003: P(3, 0, 32, channel), 3008: P(8, 0x28, 0x58, center64),
    3010: P(0x0A), 3011: P(0x0B), 3014: P(0x0E, 0, 127, pan), 3019: P(0x13), 3020: P(0x14),
}
# ------------------------------------------------------------------ multi part common (152 bytes)
COMMON = {
    7000: P(0, 0, 2047, master_tune, word=True), 7002: P(2), 7003: P(3, 0x28, 0x58, center64),
    7004: P(4, 1, 127, pan), 7007: P(7, 0, 127, plus1),
}
for _c in range(16):
    COMMON[7008 + _c] = P(8 + _c, items=PORTS)
