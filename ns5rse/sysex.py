"""NS5R system exclusive messages (KORG NS5R/NX5R MIDI Implementation, Part 2).

    F0 42 3n 42 cc [rr] [dd... ss] F7        n = exclusive channel 0-15

Dump data uses KORG's 7-in-8 packing (one byte holding bit 7 of the next seven bytes,
bit k for byte k) followed by a checksum: ((sum of packed bytes) * -1) & 0x7F.
"""

KORG, NS5R = 0x42, 0x42

# function codes
MODE_CHANGE = 0x00
MAP_CHANGE = 0x01
PARAM_CHANGE = 0x08
REPLY = 0x0E
MODE_REQUEST = 0x10
XG_GS_PARAM = 0x12
REQUEST = {'global': 0x20, 'program': 0x21, 'combi': 0x22, 'drum': 0x23, 'effect': 0x24, 'multi': 0x25,
           'all_program': 0x26, 'all_combi': 0x27, 'all_drum': 0x28, 'all_effect': 0x29,
           'all_multi': 0x2A}
DUMP = {k: v + 0x10 for k, v in REQUEST.items()}
DUMP_NAMES = {v: k for k, v in DUMP.items()}
WRITE = {'program': 0x41, 'combi': 0x42, 'drum': 0x43, 'effect': 0x44, 'multi': 0x45}

# editing modes (Mode Change rr)
MODE_GLOBAL, MODE_MULTI, MODE_PROG_EDIT, MODE_COMBI_EDIT, MODE_DRUM_EDIT, MODE_EFFECT_EDIT = range(6)

# unpacked sizes of each dump
SIZES = {'global': 10, 'program': 158, 'combi': 126, 'drum': 1358, 'effect': 38, 'multi': 8566,
         'all_program': 158 * 128, 'all_combi': 126 * 128, 'all_drum': 1358 * 2,
         'all_effect': 38 * 128, 'all_multi': 8566 * 4}

REPLY_TEXT = {0: 'Success', 1: 'Checksum error', 2: 'Invalid conditions (write protected?)',
              3: 'Invalid value'}


def pack(data):
    out = bytearray()
    for i in range(0, len(data), 7):
        group = data[i:i + 7]
        out.append(sum(((b >> 7) & 1) << k for k, b in enumerate(group)))
        out.extend(b & 0x7F for b in group)
    return bytes(out)


def unpack(data, size=None):
    out = bytearray()
    for i in range(0, len(data), 8):
        msb = data[i]
        for k, b in enumerate(data[i + 1:i + 8]):
            out.append((b & 0x7F) | (((msb >> k) & 1) << 7))
    return bytes(out[:size] if size is not None else out)


def packed_length(size):
    return size + (size + 6) // 7


def checksum(packed):
    return (-sum(packed)) & 0x7F


def header(ch, func):
    return bytes([0xF0, KORG, 0x30 | (ch & 0x0F), NS5R, func])


def mode_change(ch, mode):
    return header(ch, MODE_CHANGE) + bytes([mode, 0xF7])


def request(ch, kind):
    return header(ch, REQUEST[kind]) + b'\xF7'


def write_request(ch, kind, number):
    return header(ch, WRITE[kind]) + bytes([number & 0x7F, 0xF7])


def dump(ch, kind, data):
    p = pack(bytes(data))
    return header(ch, DUMP[kind]) + p + bytes([checksum(p), 0xF7])


def param_change(ch, lsb, msb, value):
    """Edit-mode parameter change (function 08); value is sent as 14 bits (two's complement)."""
    v = value & 0x3FFF
    return header(ch, PARAM_CHANGE) + bytes([lsb & 0x7F, msb & 0x7F, v & 0x7F, v >> 7, 0xF7])


def part_param(ch, a1, a2, a3, values):
    """GS/XG-compatible parameter (function 12): Multi part / drum / system addresses."""
    return header(ch, XG_GS_PARAM) + bytes([a1, a2, a3]) + bytes(v & 0x7F for v in values) + b'\xF7'


def device_inquiry():
    return bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])


def parse(msg):
    """Classify a received message.  Returns (kind, payload) or None.

    kinds: ('dump', name, data)  ('reply', code, command)  ('identity', (major, minor))
    """
    m = bytes(msg)
    if len(m) >= 6 and m[0] == 0xF0 and m[1] == 0x7E and m[3] == 0x06 and m[4] == 0x02:
        if len(m) >= 15 and m[5] == KORG and m[6] == NS5R:
            return ('identity', (m[12], m[10]))
        return None
    if len(m) < 6 or m[0] != 0xF0 or m[1] != KORG or (m[2] & 0xF0) != 0x30 or m[3] != NS5R:
        return None
    func = m[4]
    if func == REPLY and len(m) >= 8:
        return ('reply', m[5], m[6])
    if func in DUMP_NAMES:
        name = DUMP_NAMES[func]
        size = SIZES[name]
        body = m[5:-1] if m[-1] == 0xF7 else m[5:]
        n = packed_length(size)
        if len(body) < n:
            return None
        return ('dump', name, unpack(body[:n], size))
    if func == MODE_CHANGE and len(m) >= 7:
        return ('mode', m[5])
    return None
