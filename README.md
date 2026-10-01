# NS5R SoundEditor (Python/Tkinter port)

A cross-platform (Windows / macOS / Linux) re-implementation of **KORG NS5R SoundEditor for
Windows 1.04** (2001), the editor/librarian for the KORG NS5R / NX5R sound module. The dialog
layouts, artwork, name tables and effect tables are read from the original `SENS5R.EXE`. The
protocol was reverse engineered from its code and checked against KORG's *NS5R/NX5R MIDI
Implementation (rev 2.1)*.

## Running

```
pip install -r requirements.txt      # mido + python-rtmidi (optional: runs without MIDI too)
python run.py [file.NS5] [--scale 1|2|3]
```

Python 3.8+ with Tk 8.6 or newer.

The window is laid out in the original's dialog units. Choose the zoom under **Options › Scale**
(*Automatic*, *1x*, *2x* or *3x*). The choice is saved, and `--scale N` overrides it for one run.

## What it does

The main window has the original's five pages:

* **Multi**: the four Multi setups (32 parts each). Double-click a part to edit it. *Edit Common*
  opens master tune / key shift / balance / volume / effect, *MIDI to Port* and *Prog to Port*.
* **Global**: the system settings (*Edit Global*).
* **User Prog**: 128 user programs. The *Common* tab shows name, OSC mode, remark and effect. The
  *OSC Parameters* tab shows the OSC1/OSC2 overview panels. *Edit OSC* (or double-clicking a panel)
  opens the ten-tab Oscillator Parameters dialog: OSC, P-LFO, P-EG, VDF, F-LFO, F-EG, VDA, A-LFO,
  A-EG and Fx.
* **User Combi**: 128 combinations. *Common*, then *T1–T8* timbre overviews (*Edit Timbre*).
* **User Effect**: 128 effect setups. Double-click a block of the placement diagram to edit
  Effect 1/2 (one dialog per effect type, with the original ranges and defaults), the Pan3/Pan4 or
  output levels, or the placement.

Drum kits (User Kit 1/2 and each Multi's four modify drums) are under **Window › Drum Kit Edit**,
and from *Edit Drum Kit* in a Drum-mode program.

Also implemented: Cut/Copy/Paste/Clear of list selections, Compare, Exchange, EG Copy & Swap, OSC
Parameter Copy, Change OSC Level, Remark List, Preferences (startup receive, send on open, auto
dump), Keyboard window (mouse or keys `A W S E D F T G Y H U J K O L P ;`, `Z`/`X` octave), Show
Exclusive Data, and the MIDI Reset submenu.

### MIDI behaviour

* **Editing** works like the original. Selecting an item to edit puts it on part 1 (bank select /
  program change via the GS/XG-style function 12) and sends a Mode Change (Prog / Combi / Drum /
  Effect Edit, or Multi). Then the item is dumped into the NS5R's edit buffer, and every further
  edit is sent as a small Parameter Change (function 08). Multi data uses the GS/XG-style
  addresses, or a re-dump where none exists.
* **Transmit / Transmit as...** dump the item and send a Write Request (41h–45h) to the chosen
  number. **Receive / Receive as...** request the current dump from the NS5R (Receive as... first
  selects any ROM bank/program as the source).
* **MIDI › Transmit... / Receive...** send or request the All-Program / Combination / Drum / Effect /
  Multi and Global dumps.
* Settings are stored in `~/.ns5rse_settings.json`.

### Files

* `.NS5` is the original's native document format: a 64-byte header with a (3-byte offset, count)
  table for programs, combinations, drum kits, global, effects, multis and the remark list. Files
  written by the original editor open directly, and files saved here open in the original.
* `.syx` and `.mid` files containing NS5R dumps can be opened or imported.
* **File › Export...** writes NS5, SMF (Format 0), raw SysEx or a text name list.

## Building a standalone app

| Platform | Command | Output |
|---|---|---|
| macOS | `./build_mac.sh` | `dist/NS5R SoundEditor.app` and a `.dmg` |
| Windows | `build_windows.bat` | `dist\NS5RSoundEditor.exe` (single file) |

The builds are not code-signed. The macOS app registers as the owner of `.NS5` documents.

## Layout

| Path | Contents |
|---|---|
| `ns5rse/sysex.py` | SysEx messages, 7-in-8 packing, checksum, parsing |
| `ns5rse/model.py` | data layouts, defaults, `.NS5` read/write |
| `ns5rse/names.py` | bank/program/multisample/drum/effect name tables |
| `ns5rse/params.py` | parameter ranges and formats, keyed by the original control IDs |
| `ns5rse/device.py` | edit-buffer selection, parameter-change mapping, transmit/receive |
| `ns5rse/forms.py`, `ui.py` | Tk widgets built from the original DIALOG templates |
| `ns5rse/pages.py`, `panels.py`, `editors.py`, `dialogs.py`, `app.py` | the editor |
| `ns5rse/assets/` | data extracted from `SENS5R.EXE` (`data.json`, bitmaps, icons) |
| `tools/` | `extract_assets.py` regenerates the assets from the EXE; `ne.py` reads 16-bit Windows executables |

## Not verified against hardware

This port was tested against a simulated NS5R on virtual MIDI ports, not a real unit.

* **Edit part.** Which part the original uses to select the item being edited. This port uses
  part 1.
* **PM boxes.** The AT/DT/ST/RT keyboard-tracking and velocity time switches cycle Off → On (+) →
  On (−). The original's three-state behaviour is a guess.
* **Effect parameter displays.** A few use the units from KORG's table where the editor's own
  formatting was not traced. Examples: Para EQ frequencies show the raw index, and Dry:Fx is
  shown as `dry:fx`.
* **X5/05R file import** from the original (via its X5 multisample map) is not implemented.
* **Fonts.** A system font stands in for MS Sans Serif.
