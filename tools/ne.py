"""Minimal reader for 16-bit Windows (NE) executables: segments and resources."""
import struct

RT_NAMES = {1: 'CURSOR', 2: 'BITMAP', 3: 'ICON', 4: 'MENU', 5: 'DIALOG', 6: 'STRING', 7: 'FONTDIR',
            8: 'FONT', 9: 'ACCEL', 10: 'RCDATA', 12: 'GROUP_CURSOR', 14: 'GROUP_ICON', 16: 'VERSION'}
HEADER = '<2sBBHHIHHHHHHHHHHHHHHHHIHHHB'
FIELDS = ('magic ver rev enttab cbenttab crc flags autodata heap stack ip cs sp ss cseg cmod cbnres '
          'segtab rsrctab restab modtab imptab nrestab cmovent align cres exetyp').split()


class NEFile:
    def __init__(self, path):
        with open(path, 'rb') as f:
            d = self.data = f.read()
        o = self.offset = struct.unpack_from('<I', d, 0x3C)[0]
        if d[o:o + 2] != b'NE':
            raise ValueError('not an NE executable')
        self.header = h = dict(zip(FIELDS, struct.unpack_from(HEADER, d, o)))
        self.segments = []
        for i in range(h['cseg']):
            so, sl, sf, _ = struct.unpack_from('<HHHH', d, o + h['segtab'] + 8 * i)
            self.segments.append(dict(offset=so << h['align'], length=sl or 0x10000, flags=sf))
        self.resources = self._resources()

    def _name(self, v):
        if v & 0x8000:
            return v & 0x7FFF
        p = self.offset + self.header['rsrctab'] + v
        return self.data[p + 1:p + 1 + self.data[p]].decode('latin-1')

    def _resources(self):
        d = self.data
        r = self.offset + self.header['rsrctab']
        shift = struct.unpack_from('<H', d, r)[0]
        r += 2
        out = []
        while True:
            tid, cnt = struct.unpack_from('<HH', d, r)
            if tid == 0:
                break
            r += 8
            tname = RT_NAMES.get(tid & 0x7FFF, tid & 0x7FFF) if tid & 0x8000 else self._name(tid)
            for _ in range(cnt):
                off, ln, _, rid = struct.unpack_from('<HHHH', d, r)
                r += 12
                out.append(dict(type=tname, id=self._name(rid),
                                data=d[off << shift:(off << shift) + (ln << shift)]))
        return out

    def resource(self, rtype, rid):
        for res in self.resources:
            if res['type'] == rtype and res['id'] == rid:
                return res['data']
        raise KeyError((rtype, rid))

    def of_type(self, rtype):
        return [r for r in self.resources if r['type'] == rtype]

    def segment(self, n):
        """Raw bytes of segment n (1-based)."""
        s = self.segments[n - 1]
        return self.data[s['offset']:s['offset'] + s['length']]
