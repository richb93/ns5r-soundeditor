"""Bank / program / sample / effect names, taken from the original string tables.

Banks are numbered as in the editor (seg14:080d, seg24:2505):
    0 GM-a | 1-21 GS variations | 22 C/M | 23-65 XG banks | 66 XG SFX | 67 GM-b
    68 User Program | 69-71 Program A-C | 72 User Combination | 73-75 Combination A-C
    76 XG SFX kits | 77 XG kits | 78 GS kits | 79 KORG kits | 80 (unused, "Mute")
The NS5R's own Combination "Bank No." parameter (0-74) skips 72-76 (see combi_bank_index).
"""
from . import resources as R

NOTE_NAMES = ['C ', 'C#', 'D ', 'D#', 'E ', 'F ', 'F#', 'G ', 'G#', 'A ', 'A#', 'B ']
N_BANKS = 81
USER_PROG, USER_COMBI = 68, 72
DRUM_BANKS = (76, 77, 78, 79)


def note_name(n):
    """0-127 -> 'C -1' ... 'G 9' (the editor's style)."""
    return f'{NOTE_NAMES[n % 12].strip():<2}{n // 12 - 1}'


def bank_msb_lsb(i):
    d = R.data()
    if i == 0:
        return 0, 0
    if 1 <= i <= 22:
        return d['bank_r_msb'][i - 1], 0
    if 23 <= i <= 65:
        return 0, d['bank_y_lsb'][i - 23]
    if i == 66:
        return 64, 0
    if i == 67:
        return 56, 0
    if 68 <= i <= 80:
        return d['bank_korg_msb'][i - 68], 0
    return 0, 0


_lookup = None


def bank_index(msb, lsb):
    """(MSB, LSB) -> bank index, or None if the NS5R has no such bank."""
    global _lookup
    if _lookup is None:
        _lookup = {}
        for i in range(N_BANKS):
            _lookup.setdefault(bank_msb_lsb(i), i)
    return _lookup.get((msb, lsb))


def bank_name(i):
    """Long name used in the Bank Name List and the Multi part list."""
    s = R.strings()
    if i == 0:
        return s[800]
    if i <= 21:
        return f'{s[801]}{i}'
    if i == 22:
        return s[846]
    if i <= 50:
        return s[i + 0x30B]
    if i <= 65:
        return f'{s[830]}{i - 50}'
    return s.get(i + 0x2FD, '')


def combi_bank_index(n):
    """Combination timbre 'Bank No.' parameter value (0-74) -> bank index."""
    return n + 5 if n >= 72 else n


def program_name(bank, prog, lib=None):
    """Name of program `prog` (0-127) in bank index `bank`.  User banks come from `lib`."""
    s = R.strings()
    if bank == 0:
        return s.get(12800 + prog, '')
    if bank == 22:
        return s.get(4201 + prog, '')
    if 1 <= bank <= 65:
        return s.get((bank - (bank >= 23)) * 1000 + prog + 1, '')
    base = {66: 65001, 67: 1800, 69: 2400, 70: 1600, 71: 1400, 73: 200, 74: 560, 75: 860,
            77: 3200, 78: 3400, 79: 3600}
    if bank in base:
        return s.get(base[bank] + prog, '')
    if bank == USER_PROG:
        return lib.program_name(prog) if lib else ''
    if bank == USER_COMBI:
        return lib.combi_name(prog) if lib else ''
    if bank == 76:
        return f'SFX {prog + 1}' if prog < 2 else ''
    return '----------'


def numbered(prog, name):
    return f'{prog + 1:03d}:{name}'


# ---------------------------------------------------------------- effects
FX_BANKS = ['GM', 'Prog A', 'Prog B', 'Prog C', 'Combi A', 'Combi B', 'Combi C', 'User Effect']
FX_USER = 7
_FX_NAME_BASE = [5200, 5400, 5600, 5800, 6400, 6600, 6800, None]


def fx_bank_index(msb):
    msbs = R.data()['fx_bank_msb']
    if msb == 0x58:              # CmbU uses the same user effects as PrgU
        return FX_USER
    return msbs.index(msb) if msb in msbs else 0


def fx_bank_msb(i):
    return R.data()['fx_bank_msb'][i]


def fx_name(bank, n, lib=None):
    if bank == FX_USER:
        return lib.effect_name(n) if lib else ''
    return R.strings().get(_FX_NAME_BASE[bank] + n + 1, '')


def fx_type_name(t, short=False):
    return R.strings().get((12600 if short else 12400) + t, '')


def ms_name(n):
    names = R.data()['ms_names']
    return names[n] if 0 <= n < len(names) else ''


def drum_name(n):
    names = R.data()['drum_names']
    return names[n] if 0 <= n < len(names) else ''
