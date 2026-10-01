"""MIDI output/input via mido + python-rtmidi (optional: the editor works offline without it)."""
import queue

try:
    import mido
except ImportError:
    mido = None


class Midi:
    def __init__(self):
        self.out = None
        self.inp = None
        self.out_name = None
        self.in_name = None
        self.incoming = queue.Queue()
        self.monitor = None          # fn(bytes) called for every message sent (Show Exclusive Data)
        self.error = None if mido else 'mido / python-rtmidi not installed'

    @property
    def available(self):
        return mido is not None

    def output_names(self):
        if not mido:
            return []
        try:
            return mido.get_output_names()
        except Exception as e:
            self.error = str(e)
            return []

    def input_names(self):
        if not mido:
            return []
        try:
            return mido.get_input_names()
        except Exception as e:
            self.error = str(e)
            return []

    def open_output(self, name):
        if self.out:
            self.out.close()
            self.out = None
        self.out_name = None
        if mido and name:
            self.out = mido.open_output(name)
            self.out_name = name

    def open_input(self, name):
        if self.inp:
            self.inp.close()
            self.inp = None
        self.in_name = None
        if mido and name:
            self.inp = mido.open_input(name, callback=self.incoming.put)
            self.in_name = name

    def send_bytes(self, data):
        """Send one complete MIDI message given as raw bytes."""
        data = bytes(data)
        if self.monitor and data and data[0] == 0xF0:
            self.monitor(data)
        if not self.out:
            return False
        self.out.send(mido.Message.from_bytes(list(data)))
        return True

    def send(self, *status_and_data):
        return self.send_bytes(bytes(status_and_data))

    def note_on(self, ch, note, vel):
        self.send(0x90 | ch, note & 0x7F, vel & 0x7F)

    def note_off(self, ch, note):
        self.send(0x80 | ch, note & 0x7F, 0)

    def control(self, ch, cc, value):
        self.send(0xB0 | ch, cc, value & 0x7F)

    def program_change(self, ch, msb, lsb, prog):
        self.control(ch, 0x00, msb)
        self.control(ch, 0x20, lsb)
        self.send(0xC0 | ch, prog & 0x7F)

    def pitch_bend(self, ch, value):
        v = max(0, min(16383, value + 8192))
        self.send(0xE0 | ch, v & 0x7F, v >> 7)

    def all_notes_off(self):
        for ch in range(16):
            self.control(ch, 0x7B, 0)

    def close(self):
        try:
            self.all_notes_off()
        except Exception:
            pass
        self.open_output(None)
        self.open_input(None)
