#!/usr/bin/env python3
"""NS5R SoundEditor - Python/Tkinter port of KORG's NS5R SoundEditor for Windows 1.04."""
import argparse

from ns5rse.app import App


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('file', nargs='?', help='document to open (.NS5, or .syx / .mid with NS5R dumps)')
    ap.add_argument('--scale', type=int, choices=(1, 2, 3), help='GUI zoom for this run')
    args = ap.parse_args()
    App(scale=args.scale, path=args.file).run()


if __name__ == '__main__':
    main()
