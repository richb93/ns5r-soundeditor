"""Import of KORG X5 / 05R/W SoundEditor files (*.X5, *.05R): a straight translation of the
original's converter (SENS5R.EXE seg2:312F programs, :39C1 combinations, :3CB2 drum kits).

File layout: 0x000 global data (drum kits at 0x16, 2 x 60 notes x 7 bytes), 0x35E 100
combinations x 136 bytes, 0x387E 100 programs x 164 bytes, then the 05R/W multi set-up.
"""
from . import model as M
from . import resources as R

COMBI_OFF, PROG_OFF, KIT_OFF = 0x35E, 0x387E, 0x16
X5_PROG, X5_COMBI, X5_KIT = 164, 136, 0x1A4
MIN_SIZE = PROG_OFF + 100 * X5_PROG

# DS:0056 - X5 LFO frequency -> NS5R LFO frequency
LFO_FREQ = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 6, 6, 7, 8, 9, 9, 10, 11, 12, 13, 14, 15,
            16, 18, 19, 20, 21, 23, 24, 25, 27, 28, 30, 31, 33, 34, 36, 37, 39, 41, 43, 45, 46, 48, 50, 52, 54,
            56, 58, 60, 63, 65, 67, 69, 71, 74, 76, 78, 81, 83, 86, 88, 91, 93, 96, 98, 99, 100, 101, 102, 103,
            104, 105, 107, 108, 109, 110, 112, 113, 114, 115, 117, 118, 119, 121, 122, 124, 125, 126, 127, 127]
# X5 GM drum programs 128-135 -> KORG drum kit program numbers (seg2:3CA2)
DRUM_PROGS = [0x00, 0x10, 0x19, 0x20, 0x28, 0x40, 0x18, 0x30]


def s8(v):
    return v - 256 if v & 0x80 else v


def idiv(a, b):
    """C (8086 IDIV) division: truncates toward zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def irem(a, b):
    return a - idiv(a, b) * b


def wrap16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def scale129(v):          # seg2:2FB2  (-99..99 -> -127..127)
    return idiv(s8(v) * 129, 100) & 0xFF


def scale65(v):           # seg2:2FD7
    return idiv(s8(v) * 65, 100) & 0xFF


def wave(v):              # seg2:2FFB: X5 and NS5R order the two square waves differently
    return {4: 5, 5: 4}.get(v, v)


def lfo_freq(v):          # seg2:3026
    return LFO_FREQ[v] if v < len(LFO_FREQ) else 127


def pan(v):               # seg2:3057: X5 pan (0-30, 31 = random/off) -> NS5R 1-127
    if v == 0xFF:
        return 0
    if v == 0x1F:
        return 0x40
    p = idiv(wrap16((v - 15) * 427), 100) + 64      # 16-bit arithmetic, as in the original
    if p == 0:
        p = 1
    if p == 128:
        p = 127
    return p & 0xFF


def ms_map(n):            # GNRL 1005: X5 multisound -> NS5R multisample
    t = R.data()['x5_ms_map']
    return t[n] if 0 <= n < len(t) else n


def drum_map(n):          # GNRL 1006: X5 drum sample -> NS5R drum instrument
    t = R.data()['x5_drum_map']
    return t[n] if 0 <= n < len(t) else n


def send_level(nibble):   # 0-9 -> 0-127
    return idiv(nibble * 142, 10)


def name_bytes(n, fmt):
    return (fmt % (n + 1)).encode('latin-1')[:8].ljust(8, b' ')


# ----------------------------------------------------------------- programs
def convert_program(dst, src):
    d = dst
    d[0:10] = src[0:10]
    mode = src[0x0A]
    d[0x0A] = mode
    ms = src[0x0C] | (src[0x0D] << 8)
    if mode == 2:                                     # drum program: kit number
        ms = ms + 0x25 if ms < 2 else ms - 2
    else:
        ms = ms_map(ms)
    d[0x0F], d[0x0E] = ms & 0xFF, (ms >> 8) & 0xFF
    d[0x10] = (src[0x0E] * 12) & 0xFF
    ms2 = ms_map(src[0x0F] | (src[0x10] << 8))
    d[0x57], d[0x56] = ms2 & 0xFF, (ms2 >> 8) & 0xFF
    d[0x58] = (src[0x11] * 12) & 0xFF
    d[0x5A], d[0x5B], d[0x5F] = src[0x12], src[0x13], src[0x14]
    # the X5's single pitch EG goes to both oscillators
    for base in (0x1E, 0x66):
        d[base + 0] = scale129(src[0x1C])
        d[base + 1] = scale129(src[0x1B])
        for k in range(6):
            d[base + 2 + k] = scale129(src[0x15 + k])
    w = wave(src[0x1D] & 7)
    d[0x26] = d[0x6E] = w
    f = lfo_freq(src[0x1E])
    d[0x27] = d[0x6F] = d[0x40] = d[0x88] = f
    d[0x28] = d[0x70] = scale129(src[0x1F])
    mg = scale129(src[0x20])
    flags = src[0x1D]
    if flags & 0x20:
        d[0x2A] = mg
    if flags & 0x40:
        d[0x72] = mg
    for osc in range(2):
        o, s = 0x48 * osc, 0x2F * osc
        d[o + 0x53] = pan(src[s + 0x56])
        d[o + 0x54] = send_level((src[s + 0x52] >> 4) & 0x0F) & 0xFF
        d[o + 0x55] = send_level(src[s + 0x52] & 0x0F) & 0xFF
        d[o + 0x1D] = scale129(src[s + 0x28])
        d[o + 0x18] = wave(src[s + 0x29] & 7)
        d[o + 0x19] = lfo_freq(src[s + 0x2A])
        d[o + 0x1A] = scale129(src[s + 0x2B])
        d[o + 0x1B] = scale129(src[s + 0x2C])
        d[o + 0x1C] = scale129(src[s + 0x2D])
        d[o + 0x2B] = scale129(src[s + 0x32])
        d[o + 0x2C] = src[s + 0x33]
        d[o + 0x2D] = src[s + 0x55] & 3
        d[o + 0x2E] = scale129(src[s + 0x34])
        d[o + 0x2F] = scale129(src[s + 0x36])
        d[o + 0x30] = src[s + 0x4E]
        d[o + 0x31] = scale129(src[s + 0x53])
        d[o + 0x32] = scale129(src[s + 0x54])
        d[o + 0x33] = scale129(src[s + 0x35])
        d[o + 0x34] = scale129(src[s + 0x38])
        d[o + 0x35] = scale129(src[s + 0x37])
        d[o + 0x36] = src[s + 0x4F]
        for k in range(8):
            d[o + 0x37 + k] = scale129(src[s + 0x39 + k])
        d[o + 0x44] = src[s + 0x42]
        d[o + 0x45] = (src[s + 0x55] >> 4) & 3
        d[o + 0x46] = scale129(src[s + 0x43])
        d[o + 0x47] = scale129(src[s + 0x45])
        d[o + 0x48] = src[s + 0x50]
        d[o + 0x11] = scale129(src[s + 0x41])
        d[o + 0x49] = scale129(src[s + 0x44])
        d[o + 0x4A] = scale129(src[s + 0x46])
        d[o + 0x4B] = src[s + 0x51]
        for k in range(7):
            d[o + 0x4C + k] = scale129(src[s + 0x47 + k])


# ----------------------------------------------------------------- combinations
def convert_combi(dst, src):
    dst[0:10] = src[0:10]
    for t in range(8):
        s = src[0x28 + 12 * t:0x28 + 12 * (t + 1)]
        b = M.TIMBRE0 + t * M.TIMBRE_SIZE
        prog = s[0]
        bank = 0x3800 if (s[0x0A] >> 6) & 3 else 0x5000      # GM-b or User Program
        if bank == 0x3800 and prog > 0x7F:
            bank = 0x3E00                                      # KORG drum kits
            if prog - 0x80 < len(DRUM_PROGS):
                prog = DRUM_PROGS[prog - 0x80]
        dst[b + 0], dst[b + 1], dst[b + 2] = bank >> 8, bank & 0xFF, prog & 0xFF
        dst[b + 3] = s[1]
        dst[b + 4] = pan(s[4])
        c = send_level((s[5] >> 4) & 0x0F)
        dst[b + 5] = 0 if c > 0x7F else c
        c = send_level(s[5] & 0x0F)
        dst[b + 6] = 0 if c > 0x7F else c
        dst[b + 8], dst[b + 7] = s[6], s[7]
        dst[b + 10], dst[b + 9] = s[8], s[9]
        dst[b + 11], dst[b + 12] = s[2], s[3]
        sw = 0x24
        sw |= 0 if (s[0x0B] >> 4) & 1 else 1
        sw |= ((s[0x0A] >> 3) & 1) << 1
        sw |= ((s[0x0A] >> 2) & 1) << 3
        sw |= ((s[0x0A] >> 1) & 1) << 4
        dst[b + 13] = sw


# ----------------------------------------------------------------- drum kits
def convert_kits(kits, glob):
    for kit in kits:
        for i in range(M.N_INST):
            kit[i * M.INST_SIZE + 6] &= 0xFC
    for k, kit in enumerate(kits):
        for e in range(60):
            p = KIT_OFF + k * X5_KIT + 7 * e
            src = glob[p:p + 7]
            key = src[1]
            if not 12 <= key <= 108:
                continue
            b = (key - 12) * M.INST_SIZE
            d = kit
            sample = src[0]
            if sample:
                n = drum_map(sample - 1)
                d[b], d[b + 1] = (n >> 8) & 0xFF, n & 0xFF
            t = s8(src[3]) * 10
            coarse, fine = idiv(t, 100), irem(t, 100)
            if fine > 50:
                coarse, fine = coarse + 1, fine - 100
            elif fine < -50:
                coarse, fine = coarse - 1, fine + 100
            d[b + 2], d[b + 3] = coarse & 0xFF, fine & 0xFF
            d[b + 4] = scale129(idiv(s8(src[4]) + 99, 2) & 0xFF)
            grp = src[2] >> 5
            if grp == 7:
                d[b + 6] &= 0xFB
                grp = 0
            d[b + 5] = grp
            d[b + 10] = scale65(src[5])
            d[b + 6] |= 1
            if not sample:
                d[b + 6] &= 0xFC
            pv = src[2] & 0x1F
            if pv == 0x1F:
                d[b + 6] &= 0xFC
                pv = 0x40
            else:
                pv = (pv - 15) * 4 + 0x40
            d[b + 11] = pv & 0xFF
            d[b + 12] = ((src[6] >> 4) * 14) & 0xFF
            d[b + 13] = ((src[6] & 0x0F) * 14) & 0xFF


# ----------------------------------------------------------------- whole file
def is_x5_file(data):
    return len(data) >= MIN_SIZE and data[0] != 0x72


def convert(data, lib, effects_from='program'):
    """Convert an X5/05R file into `lib` (programs/combinations 1-100, user kits, and the
    effects of the programs or of the combinations into user effects 1-100)."""
    if len(data) < MIN_SIZE:
        raise ValueError('not an X5 / 05R/W data file (too short)')
    convert_kits(lib.kits, data[:COMBI_OFF])
    for i in range(100):
        src = data[COMBI_OFF + i * X5_COMBI:COMBI_OFF + (i + 1) * X5_COMBI]
        convert_combi(lib.combis[i], src)
        if effects_from == 'combi':
            fx = lib.effects[i]
            fx[0:8] = name_bytes(i, 'CmbFx%03d')
            fx[8:8 + 0x1D] = src[0x0B:0x0B + 0x1D]
    for i in range(100):
        src = data[PROG_OFF + i * X5_PROG:PROG_OFF + (i + 1) * X5_PROG]
        convert_program(lib.programs[i], src)
        if effects_from == 'program':
            fx = lib.effects[i]
            fx[0:8] = name_bytes(i, 'PrgFx%03d')
            fx[8:8 + 0x1D] = src[0x87:0x87 + 0x1D]
    return lib
