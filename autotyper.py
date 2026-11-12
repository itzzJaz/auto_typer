#!/usr/bin/env python3
"""
AutoTyper — types your clipboard text into whatever window is focused,
like a human: random speed, pauses at punctuation/newlines, and
occasional typos (some self-corrected with backspace, a few left in).

Usage:
    python3 autotyper.py            # type whatever is on the clipboard
    python3 autotyper.py file.py    # type the contents of a file
    python3 autotyper.py --wpm 70   # tune speed
    pbpaste | python3 autotyper.py -   # type from stdin

Hotkeys (global, work while another app is focused):
    F8   -> start typing the loaded text
    F9   -> reload text from the clipboard
    Esc  -> stop typing immediately (emergency brake)

macOS: the first run will ask for Accessibility + Input Monitoring
permission in System Settings -> Privacy & Security. Grant both,
then restart the script.
"""

import argparse
import random
import subprocess
import sys
import threading
import time
from pynput import keyboard
from pynput.keyboard import Controller, KeyCode

from human_mode import HumanMode

# ---------------------------------------------------------------- config ---
DEFAULT_WPM = 55          # average typing speed
JITTER = 0.55             # how much per-key delay randomly varies (0..1)
TYPO_RATE = 0.012         # chance each character is mistyped (~1 per 80 chars)
TYPO_CORRECT_CHANCE = 0.75  # chance a typo is noticed and backspaced away
TYPED_START_DELAY = 2.0   # countdown after pressing F8 (gives you time to click into the site)
START_HOTKEY = keyboard.Key.f8
RELOAD_HOTKEY = keyboard.Key.f9
STOP_KEY = keyboard.Key.esc
# ---------------------------------------------------------------------------


# Neighbouring keys on a QWERTY keyboard, used to make typos believable.
NEIGHBORS = {
    'q': 'wa', 'w': 'qse', 'e': 'wrd', 'r': 'etf', 't': 'ryg', 'y': 'tuh',
    'u': 'yij', 'i': 'uok', 'o': 'ipl', 'p': 'ol',
    'a': 'qsz', 's': 'awdx', 'd': 'sefc', 'f': 'drgv', 'g': 'fthb',
    'h': 'gyjn', 'j': 'hukm', 'k': 'jilm', 'l': 'kop',
    'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn',
    'n': 'bhjm', 'm': 'njk',
    '1': '2q', '2': '13w', '3': '24e', '4': '35r', '5': '46t',
    '6': '57y', '7': '68u', '8': '79i', '9': '80o', '0': '9p',
    '-': '0', '=': '-', '[': 'p', ']': '[', ';': 'l', "'": ';',
    ',': 'm', '.': ',', '/': '.',
}


def base_delay(wpm: float) -> float:
    """Average seconds between keystrokes for the given speed."""
    return 60.0 / (wpm * 5.5)  # 5.5 keystrokes per "word" incl. spaces


def human_delay(wpm: float, jitter: float, ch: str, prev: str) -> float:
    """Per-key delay with realistic jitter and pauses."""
    d = base_delay(wpm)
    d *= 1.0 + random.uniform(-jitter, jitter)          # speed jitter
    d *= random.choice((0.6, 0.8, 1.0, 1.0, 1.0, 1.3))  # bursty rhythm
    if ch in '.!?':
        d += random.uniform(0.25, 0.9)   # thinking after a sentence
    elif ch in ',;:':
        d += random.uniform(0.1, 0.4)
    elif ch == '\n':
        d += random.uniform(0.3, 1.1)    # line change pause
    elif ch == ' ':
        d *= 1.15                        # spaces are slightly slower
    if prev == '\n':
        d += random.uniform(0.2, 0.8)    # settling in on a new line
    return max(0.012, d)


def make_typo(ch: str):
    """Return a believable wrong character for ch, or None."""
    low = ch.lower()
    if low in NEIGHBORS and random.random() < 0.8:
        wrong = random.choice(NEIGHBORS[low])
    elif ch.isupper():
        # forget the shift, type the lowercase letter
        return ch.lower()
    elif ch.isalpha():
        wrong = random.choice('etaoinshrdlu')  # fat-finger a common letter
    else:
        return None
    if ch.isupper():
        wrong = wrong.upper()
    return wrong if wrong != ch else None


class AutoTyper:
    def __init__(self, wpm: float):
        self.kb = Controller()
        self.wpm = wpm
        self.human_mode = True   # variable human-like timing by default
        self.text = ''
        self.stop_flag = threading.Event()
        self.typing = threading.Event()

    # ---- text loading -----------------------------------------------------
    def load_clipboard(self) -> None:
        try:
            out = subprocess.run(['pbpaste'], capture_output=True, text=True)
            text = out.stdout
        except FileNotFoundError:
            print('pbpaste not available (macOS only). Use: python3 autotyper.py file')
            return
        if not text.strip():
            print('Clipboard is empty — copy some text first.')
            return
        self.text = text.replace('\t', '    ').replace('\r\n', '\n').replace('\r', '\n')
        print(f'Loaded {len(self.text)} characters from clipboard '
              f'(~{len(self.text.splitlines())} lines).')

    def load_source(self, src: str) -> None:
        if src == '-':
            self.text = sys.stdin.read()
        else:
            with open(src, 'r', encoding='utf-8') as f:
                self.text = f.read()
        self.text = self.text.replace('\t', '    ').replace('\r\n', '\n').replace('\r', '\n')
        print(f'Loaded {len(self.text)} characters '
              f'(~{len(self.text.splitlines())} lines).')

    # ---- the typing loop ----------------------------------------------------
    def type_text(self, human: bool = True) -> None:
        print(f'Typing starts in {TYPED_START_DELAY:.0f}s — click into the website NOW...',
              flush=True)
        self.stop_flag.clear()
        time.sleep(TYPED_START_DELAY)
        if self.stop_flag.is_set():
            print('Cancelled.')
            return

        hm = HumanMode(self.wpm, TYPO_RATE) if human else None
        wobble_wpm = self.wpm
        prev = ''
        typed = 0
        typos = 0
        fixes = 0
        for i, ch in enumerate(self.text):
            if self.stop_flag.is_set():
                print(f'\nStopped by Esc at character {i}/{len(self.text)}.')
                return

            if hm is not None:
                # ---- human mode: variable speed, bursts, clustered typos ----
                d = hm.delay(ch, prev)
                if ch != '\n' and random.random() < hm.typo_prob():
                    wrong = make_typo(ch)
                    if wrong is not None:
                        hm.on_typo()
                        typos += 1
                        self.kb.type(wrong)
                        time.sleep(d * random.uniform(1.5, 3.0))
                        if random.random() < TYPO_CORRECT_CHANCE:
                            self.kb.tap(keyboard.Key.backspace)
                            time.sleep(base_delay(self.wpm) * random.uniform(0.5, 1.2))
                            fixes += 1
                        else:
                            typed += 1
                            prev = wrong
                            continue
                self.kb.type(ch)
                typed += 1
                prev = ch
                time.sleep(d)
                continue

            # ---- flat mode: constant-ish speed, light jitter ----
            if random.random() < 0.02:
                wobble_wpm = self.wpm * random.uniform(0.85, 1.2)

            # ---- typo simulation ----
            if ch not in '\n' and random.random() < TYPO_RATE:
                wrong = make_typo(ch)
                if wrong is not None:
                    typos += 1
                    self.kb.type(wrong)
                    time.sleep(human_delay(wobble_wpm, JITTER, ch, prev) * random.uniform(1.5, 3.0))
                    if random.random() < TYPO_CORRECT_CHANCE:
                        self.kb.tap(keyboard.Key.backspace)
                        time.sleep(base_delay(wobble_wpm) * random.uniform(0.5, 1.2))
                        fixes += 1
                    else:
                        # typo left in the text — keep going like you didn't notice
                        typed += 1
                        prev = wrong
                        continue

            self.kb.type(ch)
            typed += 1
            prev = ch
            time.sleep(human_delay(wobble_wpm, JITTER, ch, prev))

        print(f'Done — typed {typed} characters, {typos} typos ({fixes} fixed).')

    # ---- hotkey handling ------------------------------------------------------
    def on_press(self, key) -> None:
        if key == STOP_KEY and self.typing.is_set():
            self.stop_flag.set()
        elif key == START_HOTKEY and not self.typing.is_set():
            if not self.text:
                print('No text loaded. Copy something and press F9.')
                return
            self.typing.set()
            threading.Thread(target=self._run_typing, daemon=True).start()
        elif key == RELOAD_HOTKEY:
            if self.typing.is_set():
                return
            self.load_clipboard()

    def _run_typing(self) -> None:
        try:
            self.type_text(human=self.human_mode)
        finally:
            self.typing.clear()

    def run(self) -> None:
        print(__doc__.split('Usage:')[0])
        print(f'Hotkeys: F8 = type clipboard  |  F9 = reload clipboard  '
              f'|  Esc = stop\nSpeed: ~{self.wpm:.0f} WPM, typos ~{TYPO_RATE*100:.1f}% '
              f'({TYPO_CORRECT_CHANCE*100:.0f}% self-corrected)\n'
              f'Mode: {"human (variable)" if self.human_mode else "flat"}\n'
              'Waiting for F8... (Ctrl+C in this terminal to quit)\n')
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()


def main() -> None:
    ap = argparse.ArgumentParser(description='Human-like autotyper for pasted text.')
    ap.add_argument('source', nargs='?', default=None,
                    help='file to type, or - for stdin (default: clipboard)')
    ap.add_argument('--wpm', type=float, default=DEFAULT_WPM, help='base speed (default 55)')
    ap.add_argument('--flat', action='store_true',
                    help='old constant-speed mode instead of human mode')
    args = ap.parse_args()

    typer = AutoTyper(args.wpm)
    if args.source:
        try:
            typer.load_source(args.source)
        except OSError as e:
            sys.exit(f'Cannot read {args.source}: {e}')
    else:
        typer.load_clipboard()
    typer.human_mode = not args.flat
    typer.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nBye.')
