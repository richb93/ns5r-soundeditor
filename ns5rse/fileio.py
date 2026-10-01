"""SysEx in .syx and Standard MIDI Files (the editor's 'SMF (Format 0)' export)."""
import struct


def split_sysex(data):
    """Raw bytes containing F0 ... F7 messages -> list of messages."""
    out, i = [], 0
    while True:
        s = data.find(b'\xF0', i)
        if s < 0:
            return out
        e = data.find(b'\xF7', s)
        if e < 0:
            return out
        out.append(bytes(data[s:e + 1]))
        i = e + 1


def _varlen(n):
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(b)


def _read_varlen(d, p):
    v = 0
    while True:
        c = d[p]
        p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def smf_bytes(messages, gap_ticks=48):
    """Format 0 SMF with one SysEx event per message (96 ticks per quarter note)."""
    track = bytearray()
    for i, m in enumerate(messages):
        track += _varlen(0 if i == 0 else gap_ticks) + b'\xF0' + _varlen(len(m) - 1) + m[1:]
    track += b'\x00\xFF\x2F\x00'
    return (b'MThd' + struct.pack('>IHHH', 6, 0, 1, 96) + b'MTrk' + struct.pack('>I', len(track)) + bytes(track))


def smf_sysex(data):
    """All SysEx messages of a Standard MIDI File."""
    if data[:4] != b'MThd':
        raise ValueError('not a Standard MIDI File')
    out = []
    p = 8 + struct.unpack('>I', data[4:8])[0]
    while p + 8 <= len(data):
        cid, ln = data[p:p + 4], struct.unpack('>I', data[p + 4:p + 8])[0]
        p += 8
        end = p + ln
        if cid == b'MTrk':
            q, status, pending = p, 0, bytearray()
            while q < end:
                _, q = _read_varlen(data, q)
                b = data[q]
                if b in (0xF0, 0xF7):
                    n, q2 = _read_varlen(data, q + 1)
                    chunk = data[q2:q2 + n]
                    if b == 0xF0:
                        pending = bytearray(b'\xF0')
                    pending += chunk
                    if pending and pending[-1] == 0xF7:
                        out.append(bytes(pending))
                        pending = bytearray()
                    q = q2 + n
                elif b == 0xFF:
                    n, q2 = _read_varlen(data, q + 2)
                    q = q2 + n
                else:
                    if b & 0x80:
                        status = b
                        q += 1
                    hi = status & 0xF0
                    q += 1 if hi in (0xC0, 0xD0) else 2
        p = end
    return out


def read_messages(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] == b'MThd':
        return smf_sysex(data)
    return split_sysex(data)
