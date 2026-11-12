#!/usr/bin/env python3
"""
AutoTyper Pro — a human-like typing simulator with an Apple-style window.

Paste (or pick from your snippet library) some text, click into the target
website, press Start (or F8 anywhere). It types everything like a person:
variable speed, bursts, hesitation, and believable neighbor-key typos —
some of which it "notices" and fixes with backspace.

What's new in 2.1:
    · 🕶 Spy mode — full variation: a fresh random persona every run,
      fatigue arcs, word rhythm, digraph speed-ups, double-space slips
      and real irregular breaks (micro-pauses, occasional long
      distractions). Comes with a black & red "Spy" theme and a
      radar-sweep start animation (click to skip, Esc to cancel)

What's new in 2.0:
    · 8 hand-tuned themes — Light, Dark, Midnight, Dracula, Ocean, Sakura,
      plus two fun ones: Matrix (phosphor-green terminal) and Retro CRT
      (amber 80s monitor)
    · Settings panel (⚙ Settings): a theme gallery with live previews, and
      every global hotkey is remappable on the fly (click a chip, press a
      key — conflicts are caught, everything is remembered)
    · Repeat passes — type the text up to 10 times in one session
    · ⇄ Shuffle — randomize word order for practice texts
    · Sound effects (Glass on finish, Pop on stop) with a toggle
    · Your speed, hotkeys, theme, preset and window size now persist
      between launches; ⌘⏎ starts typing from the text box

Global hotkeys (work while any other app is focused — defaults, remappable
in ⚙ Settings):
    F8  -> start / resume typing
    F10 -> pause / resume
    Esc -> stop typing immediately (progress is kept, not lost)
"""

import math
import queue
import random
import re
import threading
import time
import subprocess
import tkinter as tk
import tkinter.font as tkfont
import tkinter.simpledialog as simpledialog

from pynput import keyboard
from pynput.keyboard import Controller

from autotyper import human_delay, base_delay, make_typo
from human_mode import HumanMode
from spy_mode import SpyMode
import persistence

# ==================================================================== theme
# Each theme: the UI palette plus a few meta keys:
#   label  — name shown in the settings gallery
#   dark   — True for dark palettes (drives the header Light/Dark toggle)
#   title  — optional window-title wordmark override
#   badge  — optional text for the little badge next to the title
#   mono   — draw the wordmark in the mono font (terminal-ish themes)
THEMES = {
    "light": {
        "label": "Light", "dark": False,
        "bg": "#f5f5f7", "card": "#ffffff", "inset": "#f0f0f2",
        "fg": "#1d1d1f", "dim": "#6e6e73", "sep": "#e3e3e8",
        "field": "#f5f5f7", "field_border": "#dcdce1",
        "accent": "#0071e3", "accent_soft": "#eaf3ff",
        "green": "#34c759", "green_dark": "#248a3d",
        "red": "#ff3b30", "orange": "#ff9500",
        "select": "#cfe3ff", "trough": "#e8e8ec",
        "seg_bg": "#ececee",
    },
    "dark": {
        "label": "Dark", "dark": True,
        "bg": "#1e1e20", "card": "#2a2a2c", "inset": "#242426",
        "fg": "#f5f5f7", "dim": "#98989d", "sep": "#3a3a3c",
        "field": "#242426", "field_border": "#3c3c3e",
        "accent": "#0a84ff", "accent_soft": "#1c3a5e",
        "green": "#30d158", "green_dark": "#30d158",
        "red": "#ff453a", "orange": "#ff9f0a",
        "select": "#274a75", "trough": "#3c3c3e",
        "seg_bg": "#38383a",
    },
    "midnight": {
        "label": "Midnight", "dark": True,
        "bg": "#0b1220", "card": "#141c2e", "inset": "#101727",
        "fg": "#e8eefb", "dim": "#8b95ad", "sep": "#24314c",
        "field": "#0e1524", "field_border": "#243049",
        "accent": "#4f8ef7", "accent_soft": "#1c2c52",
        "green": "#2dd4a7", "green_dark": "#1fa87f",
        "red": "#ff5d73", "orange": "#ffb454",
        "select": "#24406e", "trough": "#24314c",
        "seg_bg": "#1b2539",
    },
    "dracula": {
        "label": "Dracula", "dark": True,
        "bg": "#282a36", "card": "#33354a", "inset": "#2c2e40",
        "fg": "#f8f8f2", "dim": "#a4a8c4", "sep": "#44475a",
        "field": "#2b2d3d", "field_border": "#44475a",
        "accent": "#bd93f9", "accent_soft": "#443d66",
        "green": "#50fa7b", "green_dark": "#3ad06a",
        "red": "#ff5555", "orange": "#ffb86c",
        "select": "#4a4d68", "trough": "#44475a",
        "seg_bg": "#3b3e52",
    },
    "matrix": {
        "label": "Matrix", "dark": True,
        "title": "auto_typer", "badge": "ROOT", "mono": True,
        "bg": "#040806", "card": "#0a130d", "inset": "#071009",
        "fg": "#4dff88", "dim": "#2f9e54", "sep": "#0f3520",
        "field": "#060c08", "field_border": "#0f3520",
        "accent": "#00ff41", "accent_soft": "#06301a",
        "green": "#00ff41", "green_dark": "#00b32d",
        "red": "#ff4141", "orange": "#e5ff00",
        "select": "#0b4d24", "trough": "#0f3520",
        "seg_bg": "#0d2013",
    },
    "crt": {
        "label": "Retro CRT", "dark": True,
        "title": "AUTOTYPER", "badge": "CRT", "mono": True,
        "bg": "#171106", "card": "#221a0c", "inset": "#1c150a",
        "fg": "#ffc94d", "dim": "#97793a", "sep": "#3d3115",
        "field": "#130e06", "field_border": "#3d3115",
        "accent": "#ffb000", "accent_soft": "#40330e",
        "green": "#ffd23f", "green_dark": "#b8860b",
        "red": "#ff5c33", "orange": "#ff8c00",
        "select": "#4a3a12", "trough": "#3d3115",
        "seg_bg": "#2b2213",
    },
    "spy": {
        "label": "Spy", "dark": True,
        "title": "auto_typer", "badge": "SPY", "mono": True,
        "bg": "#0a0a0d", "card": "#141418", "inset": "#101014",
        "fg": "#f4f4f6", "dim": "#8f8f98", "sep": "#2a2a31",
        "field": "#0e0e12", "field_border": "#2c2c34",
        "accent": "#ff2436", "accent_soft": "#38121a",
        "green": "#e0263a", "green_dark": "#b81e2f",
        "red": "#ff8080", "orange": "#ffb35c",
        "select": "#4a141c", "trough": "#26262d",
        "seg_bg": "#1c1c21",
    },
    "ocean": {
        "label": "Ocean", "dark": True,
        "bg": "#0a1a26", "card": "#11293b", "inset": "#0d2231",
        "fg": "#dceef7", "dim": "#7fa8bc", "sep": "#20445a",
        "field": "#0d2433", "field_border": "#20445a",
        "accent": "#2fc8ef", "accent_soft": "#123d52",
        "green": "#2dd4bf", "green_dark": "#17a398",
        "red": "#ff6b6b", "orange": "#ffd166",
        "select": "#175a75", "trough": "#20445a",
        "seg_bg": "#163649",
    },
    "sakura": {
        "label": "Sakura", "dark": False,
        "bg": "#fff4f6", "card": "#ffffff", "inset": "#fdf0f4",
        "fg": "#4a2b36", "dim": "#a77f8d", "sep": "#f2dbe1",
        "field": "#fdf3f5", "field_border": "#f0d7de",
        "accent": "#ee5b8d", "accent_soft": "#ffe4ee",
        "green": "#3fc08e", "green_dark": "#2fa377",
        "red": "#ef476f", "orange": "#ff9770",
        "select": "#ffd3e2", "trough": "#f2dbe1",
        "seg_bg": "#f6e3ea",
    },
}
LIGHT = THEMES["light"]
DARK = THEMES["dark"]


# ------------------------------------------------------------ hotkey utils
DEFAULT_HOTKEYS = {"start": "f8", "pause": "f10", "stop": "esc"}

_HK_LABEL = {
    "esc": "Esc", "space": "Space", "enter": "Enter", "tab": "Tab",
    "backspace": "⌫", "delete": "Del", "page_up": "PgUp", "page_down": "PgDn",
    "home": "Home", "end": "End", "insert": "Ins",
    "left": "←", "right": "→", "up": "↑", "down": "↓",
}

# tk modifier-only keysyms — pressing these during a capture changes nothing
_MODS = {
    "shift_l", "shift_r", "control_l", "control_r", "meta_l", "meta_r",
    "alt_l", "alt_r", "super_l", "super_r", "hyper_l", "hyper_r",
    "caps_lock", "num_lock", "scroll_lock", "shift_lock", "menu",
    "iso_level3_shift", "iso_level5_shift",
}


def hk_label(name):
    """Human-friendly label for a stored hotkey name ('f8' -> 'F8')."""
    if not name:
        return "—"
    if name in _HK_LABEL:
        return _HK_LABEL[name]
    if len(name) == 1:
        return name.upper()
    return name.upper()


def tk_key_to_name(sym, ch):
    """Map a tk <KeyPress> event (keysym + char) to our hotkey name scheme.

    Names are either pynput Key attribute names ('f8', 'esc', 'page_up') or
    single printable characters ('a', '1', '-').
    """
    if ch and len(ch) == 1:
        if ch == " ":
            return "space"
        if ch.isprintable():
            return ch.lower()
    s = (sym or "").lower()
    special = {
        "escape": "esc", "return": "enter", "enter": "enter", "tab": "tab",
        "backspace": "backspace", "delete": "delete", "home": "home",
        "end": "end", "prior": "page_up", "next": "page_down",
        "left": "left", "right": "right", "up": "up", "down": "down",
        "insert": "insert", "clear": "clear",
    }
    if s in special:
        return special[s]
    if s.startswith("kp_") and s[3:].isdigit():
        return s[3:]
    if len(s) > 1 and s[0] == "f" and s[1:].isdigit():
        n = int(s[1:])
        if 1 <= n <= 12:
            return s
    return None


def mix(c1, c2, t):
    """Blend two #rrggbb colors. t=0 -> c1, t=1 -> c2."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r, g, b = (round(a + (b - a) * t) for a, b in zip((r1, g1, b1), (r2, g2, b2)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _ease_out(x):
    """Fast start, gentle landing (Apple-style deceleration)."""
    x = _clamp01(x)
    return 1.0 - (1.0 - x) ** 3


def _ease_io(x):
    """Smoothstep — symmetric ease-in-out for reversible sweeps."""
    x = _clamp01(x)
    return x * x * (3.0 - 2.0 * x)


# fonts are initialised once a root window exists
UI = UI_B = UI_T = UI_SM = UI_XS = MONO = None


def init_fonts(root):
    global UI, UI_B, UI_T, UI_SM, UI_XS, MONO
    fams = set(tkfont.families(root))
    ui = "SF Pro Text" if "SF Pro Text" in fams else "Helvetica Neue"
    mono = "SF Mono" if "SF Mono" in fams else "Menlo"
    UI = tkfont.Font(root=root, family=ui, size=13)
    UI_B = tkfont.Font(root=root, family=ui, size=13, weight="bold")
    UI_T = tkfont.Font(root=root, family=ui, size=22, weight="bold")
    UI_SM = tkfont.Font(root=root, family=ui, size=12)
    UI_XS = tkfont.Font(root=root, family=ui, size=10)
    MONO = tkfont.Font(root=root, family=mono, size=12)


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ================================================================= widgets
class PillButton(tk.Canvas):
    """An Apple-style rounded (pill) button drawn on a canvas."""

    def __init__(self, parent, text, command=None, bg="#0071e3", fg="#ffffff",
                 font=None, pad=16, filled=True, **_):
        self.font = font or UI_B
        self._text = text
        self._command = command
        self._bg, self._fg = bg, fg
        self._filled = filled
        self._pad = pad
        self._disabled = False
        w = self.font.measure(text) + pad * 2
        h = pad * 2 + 6
        super().__init__(parent, width=w, height=h, bg=parent["bg"],
                         highlightthickness=0, bd=0,
                         cursor="pointinghand" if command else "arrow")
        self._draw()
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._set_halo(True))
        self.bind("<Leave>", lambda e: self._set_halo(False))

    def _colors(self):
        if self._disabled:
            return mix(self._bg, self.master["bg"], 0.6), \
                   mix(self._fg, self.master["bg"], 0.5)
        return self._bg, self._fg

    def _draw(self, halo=False, pressed=False):
        self.delete("all")
        bg, fg = self._colors()
        if halo and not self._disabled:
            bg = mix(bg, self.master["bg"], 0.25 if self._filled else 0.0)
            if not self._filled:
                bg = mix(self._fg, self.master["bg"], 0.92)
                fg = self._fg
        if pressed and not self._disabled:
            bg = mix(bg, self.master["bg"], 0.25)
            fg = mix(fg, self.master["bg"], 0.35)
        w, h = int(self["width"]), int(self["height"])
        if self._filled:
            round_rect(self, 1, 1, w - 2, h - 2, (h - 2) // 2,
                       fill=bg, outline="")
        else:
            round_rect(self, 1, 1, w - 2, h - 2, (h - 2) // 2,
                       fill=bg if halo else self.master["bg"],
                       outline=mix(self._fg, self.master["bg"], 0.55))
            fg = self._fg
        self.create_text(w // 2, h // 2, text=self._text, fill=fg,
                         font=self.font)

    def set_text(self, text):
        """Swap the label (and resize) — used when hotkeys are remapped."""
        self._text = text
        try:
            self.configure(width=self.font.measure(text) + self._pad * 2,
                           height=self._pad * 2 + 6)
        except tk.TclError:
            return
        self._draw()

    def set_colors(self, bg, fg="#ffffff"):
        """Recolor the pill in place (e.g. red while Spy mode is on)."""
        self._bg, self._fg = bg, fg
        self._draw()

    def _set_halo(self, on):
        if not self._disabled:
            self._draw(on)

    def _release_draw(self):
        try:
            self._draw()
        except tk.TclError:
            pass

    def _click(self, _):
        if not self._disabled and self._command:
            self._draw(pressed=True)
            self.after(110, self._release_draw)
            self._command()

    def set_disabled(self, disabled):
        self._disabled = disabled
        self.configure(cursor="arrow" if disabled else "pointinghand")
        self._draw()


class Toggle(tk.Canvas):
    """An Apple-style switch."""

    def __init__(self, parent, command=None, on_color="#34c759", value=True):
        super().__init__(parent, width=44, height=26, bg=parent["bg"],
                         highlightthickness=0, bd=0, cursor="pointinghand")
        self._on_color = on_color
        self._command = command
        self.value = value
        self._draw()
        self.bind("<Button-1>", self._flip)

    def _draw(self):
        self.delete("all")
        off = mix(self._on_color, self.master["bg"], 0.82)
        round_rect(self, 1, 2, 43, 24, 11,
                   fill=self._on_color if self.value else off, outline="")
        kx = 30 if self.value else 14
        self.create_oval(kx - 9, 4, kx + 9, 22, fill="#ffffff", outline="")

    def _flip(self, _):
        self.value = not self.value
        self._draw()
        if self._command:
            self._command()

    def set(self, v):
        self.value = bool(v)
        self._draw()


class Segmented(tk.Frame):
    """An Apple-style segmented control."""

    def __init__(self, parent, options, selected=0, on_change=None,
                 bg="#ececee", card="#ffffff", fg="#1d1d1f", dim="#6e6e73"):
        super().__init__(parent, bg=bg, padx=2, pady=2)
        self._opts, self._sel, self._on_change = options, selected, on_change
        self._colors = dict(bg=bg, card=card, fg=fg, dim=dim)
        self._labels = []
        for i, text in enumerate(options):
            lab = tk.Label(self, text=text, font=UI_SM, padx=12, pady=4,
                           cursor="pointinghand")
            lab.bind("<Button-1>", lambda e, i=i: self.select(i))
            lab.pack(side="left")
            self._labels.append(lab)
        self.select(selected, fire=False)

    def select(self, i, fire=True):
        self._sel = i
        c = self._colors
        for j, lab in enumerate(self._labels):
            if j == i:
                lab.configure(bg=c["card"], fg=c["fg"])
            else:
                lab.configure(bg=c["bg"], fg=c["dim"])
        if fire and self._on_change:
            self._on_change(i)

    @property
    def selected(self):
        return self._sel


class LabeledSlider(tk.Frame):
    """A slider with a name on the left and its live value on the right."""

    def __init__(self, parent, label, lo, hi, default, fmt, on_change=None,
                 bg="#ffffff", trough="#e8e8ec", accent="#0071e3",
                 fg="#1d1d1f", dim="#6e6e73", res=0.1):
        super().__init__(parent, bg=bg)
        self._fmt, self._on_change = fmt, on_change
        head = tk.Frame(self, bg=bg)
        head.pack(fill="x")
        tk.Label(head, text=label, font=UI_SM, bg=bg, fg=fg,
                 anchor="w").pack(side="left")
        self.vallab = tk.Label(head, text=fmt(default), font=UI_SM, bg=bg,
                               fg=dim, anchor="e")
        self.vallab.pack(side="right")
        self.scale = tk.Scale(self, from_=lo, to=hi, orient="horizontal",
                              showvalue=False, resolution=res,
                              command=self._moved, bg=bg, fg=dim,
                              troughcolor=trough, highlightthickness=0,
                              bd=0, sliderrelief="flat",
                              activebackground=accent, font=UI_XS, length=200)
        self.scale.set(default)
        self.scale.pack(fill="x")

    def _moved(self, _):
        self.vallab.configure(text=self._fmt(self.scale.get()))
        if self._on_change:
            self._on_change()

    def get(self):
        return float(self.scale.get())

    def set(self, v):
        self.scale.set(v)


class Donut(tk.Canvas):
    """A circular progress ring, Apple activity-ring style."""

    def __init__(self, parent, size=132, accent="#0071e3", sep="#e3e3e8",
                 fg="#1d1d1f"):
        super().__init__(parent, width=size, height=size, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.size, self._accent, self._sep, self._fg = size, accent, sep, fg
        self.set(0, "")

    def set(self, pct, sub=""):
        self.delete("all")
        s = self.size
        m, wdt = 8, 10
        self.create_oval(m, m, s - m, s - m, outline=self._sep, width=wdt)
        if pct > 0.005:  # full circle via oval when ~complete
            self.create_arc(m, m, s - m, s - m, start=90, extent=359.9,
                            style="arc", outline=self._accent, width=wdt)
        self.create_arc(m, m, s - m, s - m, start=90,
                        extent=-min(pct, 1.0) * 359.9, style="arc",
                        outline=self._accent, width=wdt)
        self.create_text(s // 2, s // 2 - 8, text=f"{pct * 100:.0f}%",
                         font=(UI_T.actual("family"), 22, "bold"),
                         fill=self._fg)
        self.create_text(s // 2, s // 2 + 16, text=sub or " ", font=UI_XS,
                         fill=mix(self._fg, self._sep, 0.1))


def card(parent, T, pad=14):
    """A flat Apple-style card with a hairline border."""
    f = tk.Frame(parent, bg=T["card"], highlightthickness=1,
                 highlightbackground=T["sep"])
    f.inner = tk.Frame(f, bg=T["card"])
    f.inner.pack(fill="both", expand=True, padx=pad, pady=pad)
    return f


def card_title(parent, T, text, right=None):
    row = tk.Frame(parent, bg=T["card"])
    row.pack(fill="x")
    tk.Label(row, text=text.upper(), font=UI_XS, bg=T["card"], fg=T["dim"],
             anchor="w").pack(side="left")
    if right is not None:
        right.configure(bg=T["card"])
        right.pack(side="right")
    return row


def stat_row(parent, T, name):
    row = tk.Frame(parent, bg=T["card"])
    row.pack(fill="x", pady=2)
    tk.Label(row, text=name, font=UI_SM, bg=T["card"], fg=T["dim"],
             anchor="w").pack(side="left")
    val = tk.Label(row, text="—", font=UI_SM, bg=T["card"], fg=T["fg"],
                   anchor="e")
    val.pack(side="right")
    return val


# ================================================================= engine
class TypingEngine(threading.Thread):
    """Types self.text with human behavior, reporting progress to a queue."""

    def __init__(self, text, wpm, typo_rate, correct_chance, start_delay,
                 events, human=True, start_index=0, repeat=1, spy=False):
        super().__init__(daemon=True)
        self.text = text
        self.wpm = wpm
        self.typo_rate = typo_rate
        self.correct_chance = correct_chance
        self.start_delay = start_delay
        self.events = events          # queue of (kind, payload)
        self.human = human            # variable mode
        self.spy = spy                # full-variation mode (implies human)
        self.start_index = max(0, min(int(start_index), len(text)))
        self.repeat = max(1, int(repeat))   # how many times to type the text
        self.kb = Controller()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def pause(self):
        self.pause_event.set()

    def resume(self):
        self.pause_event.clear()

    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def run(self):
        for sec in range(int(self.start_delay), 0, -1):
            if self.stop_event.is_set():
                self.emit("stopped", "Cancelled")
                return
            self.emit("countdown", sec)
            time.sleep(1)
            self._wait_if_paused(0, len(self.text), 1)
        if self.stop_event.is_set():
            self.emit("stopped", "Cancelled")
            return
        self.emit("countdown", 0)
        self.typos = 0
        self.fixes = 0
        if self.human or self.spy:
            self._run_variable()
        else:
            self._run_flat()

    def _wait_if_paused(self, i, total, rep=1):
        """Sleep while paused; report it once, and report the resume."""
        if not self.pause_event.is_set():
            return
        self.emit("paused", (i, total, rep))
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.1)
        if not self.stop_event.is_set():
            self.emit("resumed", None)

    def _sleep_interruptible(self, seconds, i, total, rep):
        """Sleep 'away' (a spy break), honoring pause and stop the whole time."""
        end = time.monotonic() + max(0.0, seconds)
        while not self.stop_event.is_set():
            self._wait_if_paused(i, total, rep)
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.1, remaining))

    def _handle_typo(self, ch, wrong, notice_delay):
        """Type a wrong char, notice it, backspace, then it gets fixed."""
        self.kb.type(wrong)
        time.sleep(notice_delay)
        if random.random() < self.correct_chance:
            # press-release with a short hold — more reliable across apps
            # than an instant tap, and how humans actually hit backspace
            self.kb.press(keyboard.Key.backspace)
            time.sleep(random.uniform(0.03, 0.09))
            self.kb.release(keyboard.Key.backspace)
            time.sleep(base_delay(self.wpm) * random.uniform(0.5, 1.2))
            self.fixes += 1
            return True
        return False

    def _run_variable(self):
        """Human mode — drifting speed, bursts, pauses, clustered typos.

        With spy=True it goes further: a fresh persona every run, a
        fatigue arc, word rhythm, irregular real breaks at natural
        seams, and corrected double-space slips. Nothing is on a cycle.
        """
        if self.spy:
            hm = SpyMode(self.wpm, self.typo_rate)
        else:
            hm = HumanMode(self.wpm, self.typo_rate)
        total = len(self.text)
        typed = 0
        for rep in range(1, self.repeat + 1):
            if self.stop_event.is_set():
                self.emit("stopped", f"Stopped before pass {rep}")
                return
            self.emit("pass", (rep, self.repeat))
            start = self.start_index if rep == 1 else 0
            prev = self.text[start - 1] if start > 0 else ""
            for i in range(start, total):
                if self.stop_event.is_set():
                    self.emit("stopped", f"Stopped at {i}/{total}")
                    return
                self._wait_if_paused(i, total, rep)
                ch = self.text[i]
                if self.spy:
                    # breaks fire at natural seams, before the next char
                    brk = hm.check_break(ch, prev)
                    if brk > 0:
                        self.emit("break", round(brk, 1))
                        self._sleep_interruptible(brk, i, total, rep)
                        if self.stop_event.is_set():
                            self.emit("stopped", f"Stopped at {i}/{total}")
                            return
                        self.emit("break_done", None)
                d = hm.delay(ch, prev)
                if ch != "\n" and random.random() < hm.typo_prob():
                    wrong = make_typo(ch)
                    if wrong is not None:
                        hm.on_typo()
                        self.typos += 1
                        if not self._handle_typo(ch, wrong,
                                                 d * random.uniform(1.5, 3.0)):
                            # typo stayed in the text
                            typed += 1
                            prev = wrong
                            self.emit("progress",
                                      (i + 1, total, self.typos, self.fixes,
                                       hm.speed_ratio, rep))
                            time.sleep(hm.delay(wrong, prev))
                            continue
                        # corrected — now type the right char (fall through)
                self.kb.type(ch)
                typed += 1
                prev = ch
                if self.spy and self.typo_rate > 0 and ch == " " and \
                        random.random() < 0.011:
                    # a doubled space, noticed and immediately corrected
                    self.typos += 1
                    self.kb.type(" ")
                    time.sleep(random.uniform(0.12, 0.4))
                    self.kb.press(keyboard.Key.backspace)
                    time.sleep(random.uniform(0.03, 0.09))
                    self.kb.release(keyboard.Key.backspace)
                    self.fixes += 1
                    time.sleep(random.uniform(0.08, 0.3))
                self.emit("progress", (i + 1, total, self.typos, self.fixes,
                                       hm.speed_ratio, rep))
                time.sleep(d)
            if rep < self.repeat:
                self.emit("pass_done", (rep, self.repeat))
                # a human breather between passes — longer in spy mode
                time.sleep(random.uniform(2.5, 8.0) if self.spy
                           else random.uniform(0.8, 1.8))
        self.emit("done", {"typed": typed,
                           "msg": f"Done — {typed} chars typed, "
                                  f"{self.typos} typos ({self.fixes} fixed), "
                                  + ("spy mode (fully randomized)"
                                     if self.spy else "variable mode")})

    def _run_flat(self):
        """Classic mode — same average speed, only light uniform jitter."""
        total = len(self.text)
        typed = 0
        wobble = self.wpm
        for rep in range(1, self.repeat + 1):
            if self.stop_event.is_set():
                self.emit("stopped", f"Stopped before pass {rep}")
                return
            self.emit("pass", (rep, self.repeat))
            start = self.start_index if rep == 1 else 0
            prev = self.text[start - 1] if start > 0 else ""
            for i in range(start, total):
                if self.stop_event.is_set():
                    self.emit("stopped", f"Stopped at {i}/{total}")
                    return
                self._wait_if_paused(i, total, rep)
                ch = self.text[i]
                if random.random() < 0.02:
                    wobble = self.wpm * random.uniform(0.85, 1.2)
                if ch != "\n" and random.random() < self.typo_rate:
                    wrong = make_typo(ch)
                    if wrong is not None:
                        self.typos += 1
                        if not self._handle_typo(
                                ch, wrong,
                                human_delay(wobble, 0.55, ch, prev) *
                                random.uniform(1.5, 3.0)):
                            typed += 1
                            prev = wrong
                            self.emit("progress",
                                      (i + 1, total, self.typos, self.fixes,
                                       1.0, rep))
                            time.sleep(human_delay(wobble, 0.55, ch, prev))
                            continue
                        # corrected — now type the right char (fall through)
                self.kb.type(ch)
                typed += 1
                prev = ch
                self.emit("progress", (i + 1, total, self.typos, self.fixes,
                                       1.0, rep))
                time.sleep(human_delay(wobble, 0.55, ch, prev))
            if rep < self.repeat:
                self.emit("pass_done", (rep, self.repeat))
                time.sleep(random.uniform(0.8, 1.8))
        self.emit("done", {"typed": typed,
                           "msg": f"Done — {typed} chars typed, "
                                  f"{self.typos} typos ({self.fixes} fixed)"})


# ==================================================================== gui
class AutoTyperGUI:
    PRESETS = [  # (name, wpm, typo %, auto-fix %, start delay)
        ("Chill",     35, 1.8, 100, 4),
        ("Balanced",  55, 1.2, 100, 3),
        ("Confident", 75, 0.8,  85, 2),
        ("Rapid",     95, 0.4,  60, 2),
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = queue.Queue()
        self.engine = None
        self.listener = None

        # --- state -------------------------------------------------------
        prefs = persistence.load_prefs() or {}

        def valid_theme(n):
            return isinstance(n, str) and n in THEMES

        self._theme_name = prefs.get("theme", "light")
        if not valid_theme(self._theme_name):
            self._theme_name = "light"
        self.T = THEMES[self._theme_name]
        # the header Light/Dark toggle flips between the two most recent
        rl = prefs.get("recent_light", "light")
        self._recent_light = (rl if valid_theme(rl) and not THEMES[rl]["dark"]
                              else "light")
        rd = prefs.get("recent_dark", "dark")
        self._recent_dark = (rd if valid_theme(rd) and THEMES[rd]["dark"]
                             else "dark")
        if THEMES[self._theme_name]["dark"]:
            self._recent_dark = self._theme_name
        else:
            self._recent_light = self._theme_name

        self._hotkeys = dict(DEFAULT_HOTKEYS)
        saved_hk = prefs.get("hotkeys", {})
        if isinstance(saved_hk, dict):
            for k in DEFAULT_HOTKEYS:
                v = saved_hk.get(k)
                if isinstance(v, str) and 0 < len(v) <= 12:
                    self._hotkeys[k] = v
        self._sound = bool(prefs.get("sound", True))

        self._text_cache = ""          # survives theme rebuilds
        self._settings = dict(wpm=55, typo=1.2, fix=100, delay=3, human=True,
                              spy=False, repeat=1)
        saved_st = prefs.get("settings", {})
        if isinstance(saved_st, dict):
            for k, (lo, hi) in (("wpm", (20, 130)), ("typo", (0, 5)),
                                ("fix", (0, 100)), ("delay", (0, 8)),
                                ("repeat", (1, 10))):
                v = saved_st.get(k)
                if isinstance(v, (int, float)):
                    self._settings[k] = min(hi, max(lo, v))
            if isinstance(saved_st.get("human"), bool):
                self._settings["human"] = saved_st["human"]
            if isinstance(saved_st.get("spy"), bool):
                self._settings["spy"] = saved_st["spy"]
        self._preset_idx = prefs.get("preset", 1)
        if not isinstance(self._preset_idx, int) or \
                not 0 <= self._preset_idx < len(self.PRESETS):
            self._preset_idx = 1

        # settings panel / hotkey capture
        self._settings_win = None
        self._hk_chips = {}
        self._swatches = []
        self._capturing = False

        # spy-mode start animation state
        self._spy_intro_active = False
        self._spy_intro = None
        self._spy_intro_done = None
        self._spy_job = None
        self._spy_t0 = 0.0
        self._spy_reduced = False

        # prefs write-behind (sliders would spam the disk otherwise)
        self._prefs_dirty = False
        self._last_prefs_save = 0.0

        # session bookkeeping
        self._session_text = None
        self._last_done = 0            # within the current pass
        self._last_abs = 0             # across all passes
        self._s_typos = 0              # cumulative for the current session
        self._s_fixes = 0
        self._r_typos = 0              # fresh this engine run
        self._r_fixes = 0
        self._counted = 0              # chars already added to lifetime stats
        self._last_save = 0.0
        self._run_start = None
        self._rate_samples = []        # (time, done) for live WPM / ETA
        self._live_wpm = None

        root.title("AutoTyper Pro")
        root.configure(bg=self.T["bg"])
        geo = prefs.get("geometry", "")
        if isinstance(geo, str) and re.match(r"^\d+x\d+([+-]\d+){2}$", geo):
            root.geometry(geo)
        else:
            root.geometry("940x760")
        root.minsize(880, 700)

        self._build_ui()
        self._start_hotkey_listener()
        self._refresh_resume_card()
        self._refresh_lifetime()
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(100, self._poll_events)

    # ---------------------------------------------------------------- ui ---
    def _build_ui(self):
        T = self.T
        self.root.configure(bg=T["bg"])

        # ------------------------------- header --------------------------
        head = tk.Frame(self.root, bg=T["bg"])
        head.pack(fill="x", padx=22, pady=(16, 10))

        ttl = tk.Frame(head, bg=T["bg"])
        ttl.pack(side="left")
        title_text = T.get("title", "AutoTyper")
        if T.get("mono"):
            tk.Label(ttl, text=title_text, bg=T["bg"], fg=T["accent"],
                     font=(MONO.actual("family"), 19, "bold")
                     ).pack(side="left")
        else:
            tk.Label(ttl, text=title_text, font=UI_T, bg=T["bg"], fg=T["fg"]
                     ).pack(side="left")
        btext = T.get("badge", "PRO")
        bw = UI_XS.measure(btext) + 18
        badge = tk.Canvas(ttl, width=bw, height=22, bg=T["bg"],
                          highlightthickness=0, bd=0)
        badge.pack(side="left", padx=(10, 0), pady=(6, 0))
        round_rect(badge, 1, 1, bw - 1, 21, 10, fill=T["accent"], outline="")
        badge.create_text(bw // 2, 11, text=btext,
                          font=(UI_XS.actual("family"), 10, "bold"),
                          fill=T["bg"])

        right = tk.Frame(head, bg=T["bg"])
        right.pack(side="right")
        self._theme_seg = Segmented(
            right, ["Light", "Dark"],
            selected=1 if T["dark"] else 0,
            on_change=self._on_quick_theme, bg=T["seg_bg"], card=T["card"],
            fg=T["fg"], dim=T["dim"])
        self._theme_seg.pack(side="left")
        PillButton(right, "⚙  Settings", self._open_settings, bg=T["card"],
                   fg=T["dim"], filled=False, font=UI_SM, pad=8
                   ).pack(side="left", padx=(10, 0))

        # ------------------------------- body ----------------------------
        body = tk.Frame(self.root, bg=T["bg"])
        body.pack(fill="both", expand=True, padx=22)
        body.columnconfigure(0, weight=5, uniform="cols")
        body.columnconfigure(1, weight=4, uniform="cols")
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=T["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        side = tk.Frame(body, bg=T["bg"])
        side.grid(row=0, column=1, sticky="nsew")

        # ---- text card ----
        tc = card(left, T)
        tc.pack(fill="both", expand=True)
        self.charlabel = tk.Label(tc.inner, text="", font=UI_XS, bg=T["card"],
                                  fg=T["dim"])
        card_title(tc.inner, T, "Your text", right=self.charlabel)
        self.textbox = tk.Text(tc.inner, bg=T["field"], fg=T["fg"],
                               insertbackground=T["accent"], font=MONO,
                               wrap="word", relief="flat", undo=True,
                               padx=12, pady=10, height=10,
                               highlightthickness=1,
                               highlightbackground=T["field_border"],
                               highlightcolor=T["accent"],
                               selectbackground=T["select"])
        self.textbox.pack(fill="both", expand=True, pady=(8, 8))
        self.textbox.tag_configure("ph", foreground=T["dim"])
        self.textbox.bind("<FocusIn>", self._on_text_focus_in)
        self.textbox.bind("<FocusOut>", self._on_text_focus_out)
        self.textbox.bind("<KeyRelease>", self._on_text_change)
        self.textbox.bind("<Command-Return>", self._start_from_box)
        self._ph_active = False
        if self._text_cache:
            self._ph_active = False
            self.textbox.insert("1.0", self._text_cache)
        else:
            self._show_placeholder()

        btnrow = tk.Frame(tc.inner, bg=T["card"])
        btnrow.pack(fill="x")
        PillButton(btnrow, "Paste", self.paste_clipboard, bg=T["accent_soft"],
                   fg=T["accent"], font=UI_SM, pad=8).pack(side="left")
        PillButton(btnrow, "⇄ Shuffle", self.shuffle_words, bg=T["card"],
                   fg=T["dim"], filled=False, font=UI_SM, pad=8
                   ).pack(side="left", padx=8)
        PillButton(btnrow, "Clear", self.clear_text, bg=T["card"],
                   fg=T["dim"], filled=False, font=UI_SM, pad=8
                   ).pack(side="left")
        self._build_library_button(btnrow)
        self._update_char_count()

        # ---- settings card ----
        sc = card(left, T, pad=12)
        sc.pack(fill="x", pady=(12, 0))
        card_title(sc.inner, T, "Behavior")

        seg_holder = tk.Frame(sc.inner, bg=T["card"])
        seg_holder.pack(fill="x", pady=(8, 4))
        self._preset_seg = Segmented(
            seg_holder, [p[0] for p in self.PRESETS],
            selected=self._preset_idx, on_change=self._on_preset,
            bg=T["seg_bg"], card=T["card"], fg=T["fg"], dim=T["dim"])
        self._preset_seg.pack()

        grid = tk.Frame(sc.inner, bg=T["card"])
        grid.pack(fill="x", pady=(6, 0))
        grid.columnconfigure((0, 1), weight=1, uniform="g")
        self._sliders = {}

        def mk(col, label, lo, hi, key, fmt, res=0.1):
            s = LabeledSlider(grid, label, lo, hi, self._settings[key], fmt,
                              bg=T["card"], trough=T["trough"],
                              accent=T["accent"], fg=T["fg"], dim=T["dim"],
                              res=res,
                              on_change=lambda k=key: self._on_slider(k))
            s.grid(row=col // 2, column=col % 2, sticky="nsew",
                   padx=(0, 14), pady=2)
            self._sliders[key] = s

        mk(0, "Speed", 20, 130, "wpm", lambda v: f"{v:.0f} WPM")
        mk(1, "Typo rate", 0, 5, "typo", lambda v: f"{v:.1f}%")
        mk(2, "Auto-fix typos", 0, 100, "fix", lambda v: f"{v:.0f}%")
        mk(3, "Start delay", 0, 8, "delay", lambda v: f"{v:.0f} s")
        mk(4, "Repeat", 1, 10, "repeat", lambda v: f"×{v:.0f}", res=1)

        human_row = tk.Frame(sc.inner, bg=T["card"])
        human_row.pack(fill="x", pady=(8, 0))
        self._human_toggle = Toggle(human_row, on_color=T["green"],
                                    command=self._on_human,
                                    value=self._settings["human"])
        self._human_toggle.pack(side="left")
        ht = tk.Frame(human_row, bg=T["card"])
        ht.pack(side="left", padx=(10, 0))
        tk.Label(ht, text="Human mode", font=UI_SM, bg=T["card"], fg=T["fg"],
                 anchor="w").pack(anchor="w")
        tk.Label(ht, text="Variable speed, bursts, hesitation, typo clusters",
                 font=UI_XS, bg=T["card"], fg=T["dim"], anchor="w"
                 ).pack(anchor="w")

        spy_row = tk.Frame(sc.inner, bg=T["card"])
        spy_row.pack(fill="x", pady=(10, 0))
        self._spy_toggle = Toggle(spy_row, on_color=T["accent"],
                                  command=self._on_spy,
                                  value=bool(self._settings.get("spy")))
        self._spy_toggle.pack(side="left")
        st = tk.Frame(spy_row, bg=T["card"])
        st.pack(side="left", padx=(10, 0))
        tk.Label(st, text="Spy mode", font=UI_SM, bg=T["card"], fg=T["fg"],
                 anchor="w").pack(anchor="w")
        tk.Label(st, text="Everything randomized: fresh persona every run, "
                          "fatigue, rhythm, irregular breaks",
                 font=UI_XS, bg=T["card"], fg=T["dim"], anchor="w"
                 ).pack(anchor="w")

        # ---- action buttons ----
        acts = tk.Frame(left, bg=T["bg"])
        acts.pack(fill="x", pady=(14, 0))
        self.start_btn = PillButton(
            acts, f"▶  Start Typing   {hk_label(self._hotkeys['start'])}",
            self.start_typing, bg=T["green"], font=UI_B, pad=11)
        self.start_btn.pack(side="left")
        self.pause_btn = PillButton(
            acts, f"⏸  Pause   {hk_label(self._hotkeys['pause'])}",
            self.toggle_pause, bg=T["accent"], font=UI_B, pad=11)
        self.pause_btn.pack(side="left", padx=10)
        self.pause_btn.set_disabled(True)
        self.stop_btn = PillButton(
            acts, f"⏹  Stop   {hk_label(self._hotkeys['stop'])}",
            self.stop_typing, bg=T["card"], fg=T["red"], filled=False,
            font=UI_B, pad=11)
        self.stop_btn.pack(side="left")
        self.stop_btn.set_disabled(True)
        self._style_start_btn()

        # ---- session card (right) ----
        sess = card(side, T, pad=14)
        sess.pack(fill="x")
        card_title(sess.inner, T, "Current session")
        ring_holder = tk.Frame(sess.inner, bg=T["card"])
        ring_holder.pack(pady=(10, 2))
        self.donut = Donut(ring_holder, accent=T["accent"], sep=T["trough"],
                           fg=T["fg"])
        self.donut.pack()
        self.status = tk.Label(sess.inner, text="Ready.", font=UI_SM,
                               bg=T["card"], fg=T["dim"], anchor="center")
        self.status.pack(fill="x", pady=(4, 8))
        self.lbl_progress = stat_row(sess.inner, T, "Progress")
        self.lbl_typos = stat_row(sess.inner, T, "Typos")
        self.lbl_speed = stat_row(sess.inner, T, "Speed now")
        self.lbl_eta = stat_row(sess.inner, T, "ETA")

        # ---- resume card (right, optional) ----
        self.resume_holder = tk.Frame(side, bg=T["bg"])
        self.resume_holder.pack(fill="x", pady=(12, 0))

        # ---- lifetime card (right) ----
        life = card(side, T, pad=14)
        life.pack(fill="both", expand=True, pady=(12, 0))
        card_title(life.inner, T, "Lifetime")
        self.lt_chars = stat_row(life.inner, T, "Characters typed")
        self.lt_fixes = stat_row(life.inner, T, "Typos fixed")
        self.lt_sessions = stat_row(life.inner, T, "Sessions finished")
        self.spark = tk.Canvas(life.inner, height=46, bg=T["card"],
                               highlightthickness=0, bd=0)
        self.spark.pack(fill="x", pady=(10, 0))
        self._draw_sparkline()

        # ---- footer ----
        self.footer = tk.Label(self.root, text=self._footer_text(),
                               font=UI_XS, bg=T["bg"], fg=T["dim"])
        self.footer.pack(fill="x", pady=(8, 12))

    def _footer_text(self):
        h = self._hotkeys
        return (f"{hk_label(h['start'])} Start · {hk_label(h['pause'])} "
                "Pause / Resume · " + hk_label(h['stop']) + " Stop — hotkeys "
                "work in any app · progress is saved automatically")

    def _build_library_button(self, parent):
        T = self.T
        self._library_mb = tk.Menubutton(parent, text="Library  ▾",
                                         font=UI_SM, bg=T["card"],
                                         fg=T["accent"], relief="flat", bd=0,
                                         cursor="pointinghand",
                                         activebackground=T["card"],
                                         activeforeground=T["accent"])
        self._library_mb.pack(side="right")
        self._library_menu = tk.Menu(self._library_mb, tearoff=0,
                                     postcommand=self._fill_library_menu)
        self._library_mb.configure(menu=self._library_menu)

    def _fill_library_menu(self):
        m = self._library_menu
        m.delete(0, "end")
        m.add_command(label="✚  Save current text as snippet…",
                      command=self._save_snippet)
        snips = persistence.load_snippets()
        if snips:
            m.add_separator()
            for s in snips:
                name = s["name"]
                preview = s["text"][:40].replace("\n", " ")
                if len(s["text"]) > 40:
                    preview += "…"
                m.add_command(label=f"    {name}  —  {preview}",
                              command=lambda n=name: self._load_snippet(n))
            m.add_separator()
            dm = tk.Menu(m, tearoff=0)
            for s in snips:
                dm.add_command(label=s["name"],
                               command=lambda n=s["name"]: self._delete_snippet(n))
            m.add_cascade(label="Delete snippet…", menu=dm)
        else:
            m.add_separator()
            m.add_command(label="    No snippets yet — save one!",
                          state="disabled")

    # ------------------------------------------------------- theme rebuild --
    def _on_quick_theme(self, i):
        """The header Light/Dark toggle — flips between the two recent themes."""
        target = self._recent_light if i == 0 else self._recent_dark
        if target != self._theme_name:
            self._apply_theme(target)

    def _apply_theme(self, name):
        th = THEMES.get(name)
        if not th or name == self._theme_name:
            return
        self._theme_name = name
        self.T = th
        if th["dark"]:
            self._recent_dark = name
        else:
            self._recent_light = name
        self._save_prefs_now()
        self._text_cache = self._get_text()
        had_settings = self._settings_win is not None
        if had_settings:
            try:
                self._settings_win.destroy()
            except tk.TclError:
                pass
            self._settings_win = None
        self._rebuild()
        if had_settings:
            self._open_settings()

    def _rebuild(self):
        for w in self.root.winfo_children():
            w.destroy()
        self._settings_win = None
        self._build_ui()
        self._sync_buttons()
        self._refresh_resume_card()
        self._refresh_lifetime()
        self._update_char_count()
        self.donut.set(self._last_pct() if self._session_text else 0, "")

    # ------------------------------------------------------------- themes ---
    def _redraw_swatches(self):
        T = self.T
        for cv, lab, name in self._swatches:
            try:
                th = THEMES[name]
                cv.delete("all")
                w, h = 118, 60
                sel = name == self._theme_name
                round_rect(cv, 1, 1, w - 1, h - 1, 10, fill=th["bg"],
                           outline=th["accent"] if sel else th["sep"],
                           width=2 if sel else 1)
                round_rect(cv, 12, 10, w - 12, h - 10, 6, fill=th["card"],
                           outline=th["sep"])
                cv.create_oval(18, 16, 24, 22, fill=th["accent"], outline="")
                round_rect(cv, 30, 15, w - 18, 23, 4, fill=th["inset"],
                           outline="")
                cv.create_rectangle(18, 30, 70, 33, fill=th["fg"], outline="")
                cv.create_rectangle(18, 39, w - 34, 42, fill=th["dim"],
                                    outline="")
                round_rect(cv, 18, h - 22, 58, h - 14, 4, fill=th["green"],
                           outline="")
                lab.configure(fg=T["fg"] if sel else T["dim"])
            except (tk.TclError, KeyError):
                pass

    # ------------------------------------------------------------- presets --
    def _on_preset(self, i):
        self._preset_idx = i
        self._prefs_dirty = True
        name, wpm, typo, fix, delay = self.PRESETS[i]
        self._settings.update(wpm=wpm, typo=typo, fix=fix, delay=delay)
        for k, v in (("wpm", wpm), ("typo", typo), ("fix", fix),
                     ("delay", delay)):
            self._sliders[k].set(v)
        self._set_status(f"“{name}” preset applied — {wpm} WPM.",
                         self.T["accent"])

    def _on_slider(self, key):
        try:
            self._settings[key] = float(self._sliders[key].get())
            self._prefs_dirty = True
        except (KeyError, AttributeError, tk.TclError):
            pass

    def _on_human(self):
        self._settings["human"] = self._human_toggle.value
        self._prefs_dirty = True

    def _on_spy(self):
        self._settings["spy"] = bool(self._spy_toggle.value)
        self._prefs_dirty = True
        if self._settings["spy"]:
            if self._theme_name != "spy":
                # black & red — the theme is part of the mode
                self._apply_theme("spy")
                self._set_status("Spy mode on — black/red theme applied. "
                                 "Every run is randomized fresh.",
                                 self.T["accent"])
                return
            self._style_start_btn()
            self._set_status("Spy mode on — every run randomized fresh.",
                             self.T["accent"])
        else:
            self._style_start_btn()
            self._set_status("Spy mode off — standard human mode.",
                             self.T["dim"])

    def _style_start_btn(self):
        """The start pill turns red and relabels while Spy mode is on."""
        try:
            T = self.T
            if self._settings.get("spy"):
                self.start_btn.set_colors(T["accent"], "#ffffff")
                self.start_btn.set_text(
                    f"▶  Start Spy Mode   {hk_label(self._hotkeys['start'])}")
            else:
                self.start_btn.set_colors(T["green"], "#ffffff")
                self.start_btn.set_text(
                    f"▶  Start Typing   {hk_label(self._hotkeys['start'])}")
        except (AttributeError, tk.TclError):
            pass

    # ------------------------------------------------------------ actions ---
    PLACEHOLDER = ("Paste or type the text to auto-type…\n\n"
                   "⌘⏎ starts typing · ⇄ Shuffle randomizes the words")

    def _show_placeholder(self):
        self._ph_active = True
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", self.PLACEHOLDER, "ph")

    def _on_text_focus_in(self, _=None):
        if self._ph_active:
            self._ph_active = False
            try:
                self.textbox.delete("1.0", "end")
                self._update_char_count()
            except tk.TclError:
                pass

    def _on_text_focus_out(self, _=None):
        try:
            if not self.textbox.get("1.0", "end-1c").strip():
                self._show_placeholder()
                self._update_char_count()
        except tk.TclError:
            pass

    def _on_text_change(self, _=None):
        try:
            self._ph_active = \
                (self.textbox.get("1.0", "end-1c") == self.PLACEHOLDER)
            self._update_char_count()
        except tk.TclError:
            pass

    def _start_from_box(self, _=None):
        self.start_typing()
        return "break"

    def _get_text(self):
        if self._ph_active:
            return ""
        try:
            return self.textbox.get("1.0", "end-1c").replace("\t", "    ")
        except (AttributeError, tk.TclError):
            return self._text_cache

    def _update_char_count(self):
        try:
            if self._ph_active:
                self.charlabel.configure(text="")
                return
            t = self._get_text()
            self.charlabel.configure(
                text=f"{len(t):,} chars · {len(t.split()):,} words · "
                     f"{len(t.splitlines()):,} lines")
        except (AttributeError, tk.TclError):
            pass

    def _replace_text(self, text):
        self._ph_active = False
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self._update_char_count()

    def paste_clipboard(self):
        try:
            out = subprocess.run(["pbpaste"], capture_output=True, text=True)
            text = out.stdout.replace("\t", "    ")
        except FileNotFoundError:
            self._set_status("Clipboard not available on this system.",
                             self.T["red"])
            return
        if not text.strip():
            self._set_status("Clipboard is empty — copy something first.",
                             self.T["red"])
            return
        self._replace_text(text)
        self._set_status(f"Loaded {len(text):,} characters from clipboard.",
                         self.T["accent"])

    def clear_text(self):
        self._ph_active = False
        self.textbox.delete("1.0", "end")
        self._on_text_focus_out()
        self._set_status("Cleared.", self.T["dim"])

    def shuffle_words(self):
        t = self._get_text()
        if not t.strip():
            self._set_status("Nothing to shuffle — the text box is empty.",
                             self.T["red"])
            return
        lines = []
        for line in t.split("\n"):
            words = line.split()
            random.shuffle(words)
            lines.append(" ".join(words))
        self._replace_text("\n".join(lines))
        self._set_status("Shuffled — word order randomized (fun for "
                         "practice).", self.T["accent"])

    # ---- snippet library ----
    def _save_snippet(self):
        text = self._get_text()
        if not text.strip():
            self._set_status("Nothing to save — the text box is empty.",
                             self.T["red"])
            return
        name = simpledialog.askstring(
            "Save snippet", "Name this snippet:",
            initialvalue=text.strip().splitlines()[0][:32], parent=self.root)
        if not name:
            return
        persistence.add_snippet(name, text)
        self._set_status(f"Snippet “{name}” saved to your library.",
                         self.T["green"])

    def _load_snippet(self, name):
        for s in persistence.load_snippets():
            if s["name"] == name:
                self._replace_text(s["text"].replace("\t", "    "))
                self._set_status(f"Loaded snippet “{name}”.", self.T["accent"])
                return

    def _delete_snippet(self, name):
        persistence.delete_snippet(name)
        self._set_status(f"Snippet “{name}” deleted.", self.T["dim"])

    # ------------------------------------------------------------- settings --
    def _open_settings(self):
        T = self.T
        if self._settings_win is not None and \
                self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("Settings — AutoTyper Pro")
        win.configure(bg=T["bg"])
        win.transient(self.root)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self._close_settings)

        head = tk.Frame(win, bg=T["bg"])
        head.pack(fill="x", padx=22, pady=(16, 8))
        tk.Label(head, text="Settings", font=UI_T, bg=T["bg"], fg=T["fg"]
                 ).pack(side="left")
        PillButton(head, "Done", self._close_settings, bg=T["accent"],
                   font=UI_B, pad=9).pack(side="right")

        body = tk.Frame(win, bg=T["bg"])
        body.pack(fill="both", expand=True, padx=22, pady=(0, 16))

        # ---- appearance ----
        ap = card(body, T, pad=14)
        ap.pack(fill="x")
        card_title(ap.inner, T, "Appearance")
        tk.Label(ap.inner,
                 text="9 themes, applied instantly and remembered.",
                 font=UI_XS, bg=T["card"], fg=T["dim"], anchor="w"
                 ).pack(fill="x")
        grid = tk.Frame(ap.inner, bg=T["card"])
        grid.pack(fill="x", pady=(8, 0))
        for i in range(4):
            grid.columnconfigure(i, weight=1)
        self._swatches = []
        for idx, name in enumerate(THEMES):
            cell = tk.Frame(grid, bg=T["card"])
            cell.grid(row=idx // 4, column=idx % 4, padx=4, pady=4,
                      sticky="nsew")
            cv = tk.Canvas(cell, width=118, height=60, bg=T["card"],
                           highlightthickness=0, bd=0, cursor="pointinghand")
            cv.pack()
            lab = tk.Label(cell, text=THEMES[name]["label"], font=UI_XS,
                           bg=T["card"], fg=T["dim"], cursor="pointinghand")
            lab.pack()
            self._swatches.append((cv, lab, name))
            cv.bind("<Button-1>", lambda e, n=name: self._apply_theme(n))
            lab.bind("<Button-1>", lambda e, n=name: self._apply_theme(n))
        self._redraw_swatches()

        # ---- hotkeys ----
        hkc = card(body, T, pad=14)
        hkc.pack(fill="x", pady=(12, 0))
        card_title(hkc.inner, T, "Hotkeys")
        self._hk_status = tk.Label(hkc.inner, text="", font=UI_XS,
                                   bg=T["card"], fg=T["dim"], anchor="w")
        self._hk_status.pack(fill="x")
        rows = tk.Frame(hkc.inner, bg=T["card"])
        rows.pack(fill="x", pady=(4, 0))
        for action, label in (("start", "Start / resume typing"),
                              ("pause", "Pause / resume"),
                              ("stop", "Stop typing")):
            row = tk.Frame(rows, bg=T["card"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=UI_SM, bg=T["card"], fg=T["fg"],
                     anchor="w").pack(side="left")
            chip = PillButton(
                row, hk_label(self._hotkeys[action]),
                command=lambda a=action: self._begin_capture(a),
                bg=T["card"], fg=T["accent"], filled=False, font=UI_SM,
                pad=8)
            chip.pack(side="right")
            self._hk_chips[action] = chip
        tk.Label(hkc.inner,
                 text="Click a key chip, then press the new key. Esc cancels "
                      "(to use Esc itself as a hotkey, use Reset below). "
                      "F-keys are safest — plain letters fire in every app. "
                      "If F-keys change volume instead, turn on “Use F1, F2 "
                      "as standard function keys” in System Settings → "
                      "Keyboard.",
                 font=UI_XS, bg=T["card"], fg=T["dim"], anchor="w",
                 wraplength=520, justify="left").pack(fill="x", pady=(8, 0))
        PillButton(hkc.inner, "Reset to defaults", self._reset_hotkeys,
                   bg=T["card"], fg=T["red"], filled=False, font=UI_SM,
                   pad=7).pack(anchor="e", pady=(6, 0))

        # ---- general ----
        gen = card(body, T, pad=14)
        gen.pack(fill="x", pady=(12, 0))
        card_title(gen.inner, T, "General")
        row = tk.Frame(gen.inner, bg=T["card"])
        row.pack(fill="x")
        self._sound_toggle = Toggle(row, on_color=T["green"],
                                    command=self._on_sound_toggle,
                                    value=self._sound)
        self._sound_toggle.pack(side="left")
        gt = tk.Frame(row, bg=T["card"])
        gt.pack(side="left", padx=(10, 0))
        tk.Label(gt, text="Sound effects", font=UI_SM, bg=T["card"],
                 fg=T["fg"], anchor="w").pack(anchor="w")
        tk.Label(gt, text="Chime when a session finishes or is stopped",
                 font=UI_XS, bg=T["card"], fg=T["dim"], anchor="w"
                 ).pack(anchor="w")

        win.update_idletasks()
        try:
            x = self.root.winfo_rootx() + \
                (self.root.winfo_width() - win.winfo_width()) // 2
            y = self.root.winfo_rooty() + 60
            win.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        win.lift()

    def _close_settings(self):
        self._capturing = False
        win = self._settings_win
        self._settings_win = None
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass

    def _set_hk_status(self, msg, color=None):
        try:
            self._hk_status.configure(text=msg, fg=color or self.T["dim"])
        except (AttributeError, tk.TclError):
            pass

    def _refresh_hk_chips(self):
        for action, chip in self._hk_chips.items():
            try:
                chip.set_text(hk_label(self._hotkeys[action]))
            except (AttributeError, tk.TclError):
                pass

    def _begin_capture(self, action):
        if self._capturing:
            return
        self._capturing = action
        self._refresh_hk_chips()
        try:
            self._hk_chips[action].set_text("press a key…")
            self._settings_win.focus_force()
            self._settings_win.bind("<KeyPress>", self._capture_key)
        except (AttributeError, tk.TclError, KeyError):
            self._capturing = False
        self._set_hk_status("Press any key now…  (Esc cancels)",
                            self.T["accent"])

    def _capture_key(self, e):
        action = self._capturing
        if not action:
            return
        if (e.keysym or "").lower() in _MODS:
            return  # ignore modifier-only presses
        try:
            self._settings_win.unbind("<KeyPress>")
        except (AttributeError, tk.TclError):
            pass
        self._capturing = False
        if e.keysym == "Escape":
            self._refresh_hk_chips()
            self._set_hk_status("Capture cancelled.", self.T["dim"])
            return
        name = tk_key_to_name(e.keysym, e.char)
        if not name:
            self._set_hk_status(f"“{e.keysym}” can't be used as a hotkey.",
                                self.T["red"])
            self._refresh_hk_chips()
            return
        for other, hn in self._hotkeys.items():
            if other != action and hn == name:
                self._set_hk_status(
                    f"“{hk_label(name)}” is already used for "
                    f"{other.title()} — pick another key.", self.T["red"])
                self._refresh_hk_chips()
                return
        self._hotkeys[action] = name
        self._save_prefs_now()
        self._restart_listener()
        self._refresh_hk_chips()
        self._sync_hotkey_labels()
        self._set_hk_status(f"{action.title()} hotkey set to "
                            f"{hk_label(name)}.", self.T["green"])
        self._set_status(f"{action.title()} hotkey is now "
                         f"{hk_label(name)}.", self.T["accent"])

    def _reset_hotkeys(self):
        self._capturing = False
        self._hotkeys = dict(DEFAULT_HOTKEYS)
        self._save_prefs_now()
        self._restart_listener()
        self._refresh_hk_chips()
        self._sync_hotkey_labels()
        self._set_hk_status("Hotkeys reset to F8 / F10 / Esc.",
                            self.T["green"])

    def _on_sound_toggle(self):
        self._sound = self._sound_toggle.value
        self._save_prefs_now()
        if self._sound:
            self._play_sound("Pop")

    # ---- session persistence ----
    def _persist(self, state, index=None):
        if self._session_text is None:
            return
        index = self._last_done if index is None else index
        persistence.save_session(
            text=self._session_text,
            index=index,
            settings=dict(self._settings),
            stats={"typos": self._s_typos, "fixes": self._s_fixes},
            counted=self._counted,
            state=state,
        )

    def _refresh_resume_card(self):
        for w in self.resume_holder.winfo_children():
            w.destroy()
        if self.engine and self.engine.is_alive():
            return
        sess = persistence.load_session()
        if not sess or sess.get("state") not in ("running", "paused"):
            return
        text = sess.get("text", "")
        index, total = sess.get("index", 0), len(text)
        if not text or index >= total:
            return
        T = self.T
        c = card(self.resume_holder, T, pad=14)
        c.pack(fill="x")
        card_title(c.inner, T, "Unfinished session")
        tk.Label(c.inner, text="⏯", font=("Helvetica Neue", 22),
                 bg=T["card"], fg=T["accent"]).pack(anchor="w", pady=(6, 0))
        tk.Label(c.inner,
                 text=f"{index:,} / {total:,} chars "
                      f"({index * 100 // total if total else 0}%) typed",
                 font=UI_SM, bg=T["card"], fg=T["fg"], anchor="w"
                 ).pack(anchor="w")
        tk.Label(c.inner,
                 text=f"Saved {_ago(sess.get('updated', time.time()))} · "
                      f"{sess.get('state', 'paused')}",
                 font=UI_XS, bg=T["card"], fg=T["dim"], anchor="w"
                 ).pack(anchor="w")
        row = tk.Frame(c.inner, bg=T["card"])
        row.pack(fill="x", pady=(10, 0))
        PillButton(row, "▶  Resume session", self._resume_session,
                   bg=T["accent"], font=UI_B, pad=9).pack(side="left")
        PillButton(row, "Discard", self._discard_session, bg=T["card"],
                   fg=T["dim"], filled=False, font=UI_SM, pad=9
                   ).pack(side="left", padx=8)

    def _resume_session(self):
        sess = persistence.load_session()
        if not sess or (self.engine and self.engine.is_alive()):
            return
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", sess["text"])
        self._update_char_count()
        st = sess.get("settings", {})
        for k in ("wpm", "typo", "fix", "delay", "repeat"):
            if k in st and k in self._sliders:
                self._sliders[k].set(st[k])
                self._settings[k] = st[k]
        self._settings["human"] = st.get("human", True)
        self._human_toggle.set(self._settings["human"])
        self._settings["spy"] = bool(st.get("spy", False))
        if hasattr(self, "_spy_toggle"):
            self._spy_toggle.set(self._settings["spy"])
        self._style_start_btn()
        self._s_typos = sess.get("stats", {}).get("typos", 0)
        self._s_fixes = sess.get("stats", {}).get("fixes", 0)
        self._counted = sess.get("counted", 0)
        idx = sess.get("index", 0)
        if self._settings["spy"]:
            self._set_status("Resuming spy session…", self.T["accent"])
            self._play_spy_intro(lambda: self._start_engine(resume_from=idx))
        else:
            self._start_engine(resume_from=idx)
            self._set_status("Resumed from where you left off.",
                             self.T["accent"])

    def _discard_session(self):
        persistence.clear_session()
        self._refresh_resume_card()
        self._set_status("Saved session discarded.", self.T["dim"])

    # ---- start / stop / pause ----
    def start_typing(self):
        if self._spy_intro_active:
            return                      # the intro is already running
        if self.engine and self.engine.is_alive():
            return
        text = self._get_text()
        if not text.strip():
            self._set_status("Nothing to type — paste some text first.",
                             self.T["red"])
            self._play_sound("Basso")
            return
        if self._settings.get("spy"):
            if self._settings_win is not None:
                self._close_settings()
            self._play_spy_intro(self._begin_session)
        else:
            self._begin_session()

    def _begin_session(self):
        self._s_typos = 0
        self._s_fixes = 0
        self._counted = 0
        self._start_engine(resume_from=0)

    def _start_engine(self, resume_from=0):
        text = self._get_text()
        self._session_text = text
        self._last_done = resume_from
        self._last_abs = resume_from
        self._r_typos = 0
        self._r_fixes = 0
        self._rate_samples = []
        self._live_wpm = None
        self._run_start = time.time()
        self._last_save = time.time()
        self.engine = TypingEngine(
            text=text,
            wpm=self._settings["wpm"],
            typo_rate=self._settings["typo"] / 100.0,
            correct_chance=self._settings["fix"] / 100.0,
            start_delay=self._settings["delay"],
            events=self.events,
            human=self._settings["human"],
            start_index=resume_from,
            repeat=int(self._settings["repeat"]),
            spy=bool(self._settings.get("spy")),
        )
        self.engine.start()
        self._persist("running", resume_from)
        self._refresh_resume_card()
        self._sync_buttons()

    def stop_typing(self):
        if self.engine:
            self.engine.stop()

    def toggle_pause(self):
        eng = self.engine
        if not eng or not eng.is_alive():
            return
        hk = hk_label(self._hotkeys["pause"])
        if eng.pause_event.is_set():
            eng.resume()
            self.pause_btn.set_text(f"⏸  Pause   {hk}")
        else:
            eng.pause()
            self.pause_btn.set_text(f"▶  Resume   {hk}")

    def _sync_buttons(self):
        running = self.engine is not None and self.engine.is_alive()
        self.start_btn.set_disabled(running)
        self.pause_btn.set_disabled(not running)
        self.stop_btn.set_disabled(not running)
        if not running:
            self.pause_btn.set_text(
                f"⏸  Pause   {hk_label(self._hotkeys['pause'])}")

    def _sync_hotkey_labels(self):
        """Refresh every button/footer/chip that displays a hotkey."""
        hk = self._hotkeys
        try:
            self._style_start_btn()
            running = self.engine is not None and self.engine.is_alive()
            paused = running and self.engine.pause_event.is_set()
            self.pause_btn.set_text(
                f"{'▶  Resume' if paused else '⏸  Pause'}   "
                f"{hk_label(hk['pause'])}")
            self.stop_btn.set_text(f"⏹  Stop   {hk_label(hk['stop'])}")
            self.footer.configure(text=self._footer_text())
        except (AttributeError, tk.TclError):
            pass
        for action, chip in self._hk_chips.items():
            try:
                chip.set_text(hk_label(hk[action]))
            except (AttributeError, tk.TclError):
                pass

    # ---------------------------------------------------- background glue ---
    def _last_pct(self):
        if not self._session_text:
            return 0.0
        grand = len(self._session_text) * max(1, int(self._settings["repeat"]))
        return min(1.0, self._last_abs / grand) if grand else 0.0

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                try:
                    self._dispatch(kind, payload)
                except (AttributeError, tk.TclError, KeyError):
                    pass  # widgets mid-rebuild (theme switch) — drop the event
        except queue.Empty:
            pass
        finally:
            try:
                running = self.engine and self.engine.is_alive()
                if running and time.time() - self._last_save > 2.0:
                    # crash-safe autosave while typing
                    self._persist("running")
                    self._last_save = time.time()
                if not running and self.events.qsize() == 0:
                    self._sync_buttons()
                if self._prefs_dirty and \
                        time.time() - self._last_prefs_save > 2.0:
                    self._save_prefs_now()
                    self._prefs_dirty = False
            except (AttributeError, tk.TclError):
                pass
            self.root.after(100, self._poll_events)

    def _dispatch(self, kind, payload):
        if kind == "countdown":
            if payload and payload > 0:
                self._set_status(
                    f"Typing starts in {payload}s — click into the "
                    "target window NOW…", self.T["orange"])
            else:
                self._set_status("Typing…", self.T["green"])
        elif kind == "progress":
            self._on_progress(payload)
        elif kind == "done":
            self._on_done(payload)
        elif kind == "stopped":
            self._on_stopped(payload)
        elif kind == "pass":
            rep, n = payload
            if n > 1:
                self._set_status(f"Pass {rep}/{n} — typing it again…",
                                 self.T["accent"])
        elif kind == "pass_done":
            rep, n = payload
            if n > 1:
                self._set_status(
                    f"Pass {rep}/{n} complete ✓ — short breather, "
                    "then again.", self.T["green"])
        elif kind == "paused":
            i, total, rep = payload
            n = max(1, int(self._settings["repeat"]))
            self._last_done = i
            self._last_abs = (rep - 1) * total + i
            self._set_status(
                f"Paused at {self._last_abs:,}/{total * n:,}"
                + (f" (pass {rep}/{n})" if n > 1 else "")
                + f" — press {hk_label(self._hotkeys['pause'])} to resume.",
                self.T["accent"])
            self._persist("paused", i)
            self._refresh_resume_card()
        elif kind == "resumed":
            self._set_status("Typing…", self.T["green"])
        elif kind == "break":
            self._set_status(
                f"🕶  Micro-break — {payload:.0f}s. Re-reading, hands off "
                "the keys…", self.T["accent"])
            self.donut.set(self._last_pct(), "break")
        elif kind == "break_done":
            self._set_status("Typing…", self.T["green"])

    def _on_progress(self, payload):
        done, total, typos, fixes, _ratio, rep = payload[:6]
        n = max(1, int(self._settings["repeat"]))
        abs_done = (rep - 1) * total + done
        abs_total = n * total
        self._last_done = done
        self._last_abs = abs_done
        self._r_typos, self._r_fixes = typos, fixes
        now = time.time()
        self._rate_samples.append((now, abs_done))
        # keep ~4 s of samples
        while self._rate_samples and now - self._rate_samples[0][0] > 4.0:
            self._rate_samples.pop(0)
        if len(self._rate_samples) >= 2:
            t0, d0 = self._rate_samples[0]
            dt, dd = now - t0, abs_done - d0
            if dt > 0.5 and dd >= 0:
                self._live_wpm = (dd / dt) * 60.0 / 5.5
        self.donut.set(abs_done / abs_total if abs_total else 1.0,
                       f"{self._live_wpm:.0f} WPM" if self._live_wpm else "")
        s_typos = self._s_typos + typos
        s_fixes = self._s_fixes + fixes
        prog = (f"{abs_done:,} / {abs_total:,}  "
                f"({abs_done * 100 // abs_total if abs_total else 100}%)")
        if n > 1:
            prog += f"  ·  pass {rep}/{n}"
        self.lbl_progress.configure(text=prog)
        self.lbl_typos.configure(text=f"{s_typos}  ·  {s_fixes} fixed")
        self.lbl_speed.configure(
            text=(f"~{self._live_wpm:.0f} WPM" if self._live_wpm
                  else f"~{self._settings['wpm']:.0f} WPM"))
        self.lbl_eta.configure(text=self._eta(abs_total, abs_done))
        self._set_status(
            f"Typing… {abs_done:,}/{abs_total:,}"
            + (f" · pass {rep}/{n}" if n > 1 else "")
            + f" · {s_typos} typos, {s_fixes} fixed", self.T["green"])

    def _eta(self, total, done):
        if not self._live_wpm or self._live_wpm <= 0:
            return "—"
        remaining = (total - done) * 5.5 / (self._live_wpm * 60)
        m, s = divmod(int(remaining + 0.5), 60)
        return f"{m}:{s:02d}"

    def _on_done(self, payload):
        total = len(self._session_text)
        n = max(1, int(self._settings["repeat"]))
        grand = total * n
        if self._last_abs < grand:
            self._last_abs = grand
        # add this session's fresh counters to lifetime stats
        persistence.add_stats(chars=grand - self._counted,
                              typos=self._r_typos, fixes=self._r_fixes,
                              sessions=1)
        persistence.add_history({
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "chars": grand - self._counted,
            "wpm": self._settings["wpm"],
            "secs": int(time.time() - (self._run_start or time.time())),
        })
        persistence.clear_session()
        self._counted = grand
        self._s_typos += self._r_typos
        self._s_fixes += self._r_fixes
        self.donut.set(1.0, "done")
        self.lbl_progress.configure(text=f"{grand:,} / {grand:,}  (100%)")
        self._set_status("✓  " + payload.get("msg", "Done.") +
                         (f"  ({n} passes)" if n > 1 else ""), self.T["green"])
        self._play_sound("Glass")
        self._refresh_resume_card()
        self._draw_sparkline()
        self._refresh_lifetime()

    def _on_stopped(self, payload):
        # stopping is non-destructive: keep everything so it can be resumed
        if self._session_text is not None and self._last_abs > 0:
            persistence.add_stats(chars=self._last_abs - self._counted,
                                  typos=self._r_typos, fixes=self._r_fixes)
            self._counted = self._last_abs
            self._s_typos += self._r_typos
            self._s_fixes += self._r_fixes
            self._r_typos = 0
            self._r_fixes = 0
            if self._last_done < len(self._session_text):
                self._persist("paused")
                self._set_status(
                    f"⏹  {payload} — progress saved. Resume anytime "
                    f"({hk_label(self._hotkeys['start'])} or the sidebar).",
                    self.T["orange"])
                self._play_sound("Pop")
            else:
                persistence.clear_session()
        else:
            self._set_status("⏹  " + str(payload), self.T["red"])
        self._refresh_resume_card()
        self._refresh_lifetime()

    def _refresh_lifetime(self):
        s = persistence.load_stats()
        self.lt_chars.configure(text=f"{s.get('chars', 0):,}")
        self.lt_fixes.configure(text=f"{s.get('fixes', 0):,}")
        self.lt_sessions.configure(text=f"{s.get('sessions', 0):,}")

    def _draw_sparkline(self):
        T = self.T
        cv = self.spark
        cv.delete("all")
        hist = persistence.load_history()[-8:]
        w = max(cv.winfo_width() or 220, 60)
        h = 46
        if not hist:
            cv.create_text(w // 2, h // 2,
                           text="no sessions yet — type something!",
                           font=UI_XS, fill=T["dim"])
            return
        vals = [max(1, e.get("chars", 1)) for e in hist]
        vmax = max(vals)
        gap = 6
        bw = (w - gap * (len(vals) - 1)) / len(vals)
        for i, v in enumerate(vals):
            x = i * (bw + gap)
            bh = max(6, (v / vmax) * (h - 14))
            round_rect(cv, x, h - 4 - bh, x + bw, h - 4, 3,
                       fill=T["accent"] if i == len(vals) - 1 else T["trough"],
                       outline="")
        cv.configure(width=w, height=h)

    def _set_status(self, msg, color=None):
        try:
            self.status.configure(text=msg, fg=color or self.T["dim"])
        except (AttributeError, tk.TclError):
            pass

    # ------------------------------------------------- spy mode animation ---
    SPY_BG = "#050506"
    SPY_RED = "#ff2436"
    SPY_DIM = "#9a9aa0"
    SPY_TITLE = "SPY MODE"
    SPY_SUB = "EVERYTHING RANDOMIZED · IRREGULAR BREAKS · FRESH EVERY RUN"
    SPY_SCRAMBLE = "!<>-_\\/[]{}=+*^?#01"
    SPY_TOTAL = 2.6          # seconds; skippable with a click / Return

    def _macos_reduce_motion(self):
        """Honor the system Reduce Motion setting on macOS."""
        try:
            out = subprocess.run(
                ["defaults", "read", "com.apple.universalaccess",
                 "reduceMotion"],
                capture_output=True, text=True, timeout=1.5)
            return out.stdout.strip() == "1"
        except Exception:
            return False

    def _play_spy_intro(self, done):
        """Black-out overlay: reticle, radar sweep, decoded 'SPY MODE'.

        Interruptible by design — a click skips it, Esc cancels the
        start entirely, and with Reduce Motion it degrades to a calm
        static card. `done` runs only when the start should proceed.
        """
        if self._spy_intro_active:
            return
        self._spy_intro_active = True
        self._spy_intro_done = done
        ov = tk.Canvas(self.root, bg=self.SPY_BG, highlightthickness=0, bd=0,
                       cursor="hand2")
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        # Canvas overrides lift() to mean "raise a canvas item" — use the
        # window-level Tcl command instead to get above every sibling.
        self.root.tk.call("raise", ov._w)
        self.root.update_idletasks()
        self._spy_intro = ov
        self._spy_reduced = self._macos_reduce_motion()
        self._spy_t0 = time.monotonic()
        self._spy_job = None
        ov.bind("<Button-1>", lambda e: self._end_spy_intro(start=True))
        self.root.bind_all("<Escape>",
                           lambda e: self._end_spy_intro(start=False),
                           add="+")
        self.root.bind_all("<Return>",
                           lambda e: self._end_spy_intro(start=True), add="+")
        self._play_sound("Tink")
        self._spy_intro_frame()

    def _spy_intro_frame(self):
        if not self._spy_intro_active:
            return
        cv = self._spy_intro
        try:
            w = max(cv.winfo_width(), 1)
            h = max(cv.winfo_height(), 1)
        except tk.TclError:
            return
        if self._spy_reduced:
            # no sweep, no decode — one calm locked frame, then go
            self._draw_spy_static(cv, w, h)
            if time.monotonic() - self._spy_t0 >= 0.9:
                self._end_spy_intro(start=True)
                return
        else:
            t = time.monotonic() - self._spy_t0
            self._draw_spy_frame(cv, w, h, t)
            if t >= self.SPY_TOTAL:
                self._end_spy_intro(start=True)
                return
        self._spy_job = self.root.after(16, self._spy_intro_frame)

    def _draw_spy_static(self, cv, w, h):
        """Reduced-motion variant: a quiet, steady spy card."""
        cv.delete("all")
        RED, BG = self.SPY_RED, self.SPY_BG
        cx, cy = w / 2, h / 2
        R = min(w, h) * 0.30
        cv.create_oval(cx - R, cy - R, cx + R, cy + R, outline=RED, width=2)
        cv.create_oval(cx - R * 0.72, cy - R * 0.72, cx + R * 0.72,
                       cy + R * 0.72, outline=mix(BG, RED, 0.5), width=1)
        fam = MONO.actual("family")
        cv.create_text(cx, cy - 8, text=self.SPY_TITLE,
                       font=(fam, 30, "bold"), fill=RED)
        cv.create_text(cx, cy + 32, text="EVERYTHING RANDOMIZED",
                       font=(fam, 11), fill=self.SPY_DIM)
        cv.create_text(cx, h - 40, text="starting…",
                       font=(fam, 10), fill="#7a7a80")

    def _draw_spy_frame(self, cv, w, h, t):
        cv.delete("all")
        RED, BG, DIM = self.SPY_RED, self.SPY_BG, self.SPY_DIM
        fam = MONO.actual("family")
        cx, cy = w / 2, h / 2
        R = min(w, h) * 0.30

        # everything dissolves toward the background at the end
        q = 1.0 if t < 2.2 else _clamp01(1.0 - (t - 2.2) / 0.4)

        def C(color, k=1.0):
            return mix(BG, color, _clamp01(k * q))

        # the lock pulse gently contracts the reticle at the end
        pulse = _ease_out((t - 2.05) / 0.25)
        r1 = R * (1.0 - 0.05 * pulse)
        cv.create_oval(cx - r1, cy - r1, cx + r1, cy + r1,
                       outline=C(RED), width=2)

        g2 = _ease_out((t - 0.15) / 0.5)
        r2 = R * 0.72 * (0.6 + 0.4 * g2)
        cv.create_oval(cx - r2, cy - r2, cx + r2, cy + r2,
                       outline=C(RED, 0.55), width=1)

        # compass ticks fade in around the outer ring
        gt = _ease_out((t - 0.4) / 0.4)
        for ang in (0, 90, 180, 270):
            a = math.radians(ang)
            x1 = cx + (R + 6) * math.cos(a)
            y1 = cy - (R + 6) * math.sin(a)
            x2 = cx + (R + 14) * math.cos(a)
            y2 = cy - (R + 14) * math.sin(a)
            cv.create_line(x1, y1, x2, y2, fill=C(RED, 0.8 * gt), width=2)

        # faint crosshair
        gc = _ease_out((t - 0.3) / 0.6)
        cv.create_line(0, cy, w, cy, fill=C(RED, 0.10 * gc))
        cv.create_line(cx, 0, cx, h, fill=C(RED, 0.10 * gc))

        # radar sweep — three stacked slices, bright leading edge
        if 0.45 <= t <= 2.1:
            ang = (t - 0.45) * 420.0
            r = R * 0.98
            for ext, k in ((30, 0.14), (16, 0.08), (7, 0.04)):
                cv.create_arc(cx - r, cy - r, cx + r, cy + r,
                              start=90 - ang - ext, extent=ext,
                              style="pieslice", fill=C(RED, k), outline="")

        # title decodes character by character out of the noise
        if t > 0.75:
            parts = []
            for i, c in enumerate(self.SPY_TITLE):
                lt = 0.85 + i * 0.075
                if t >= lt:
                    parts.append(c)
                elif t > lt - 0.35:
                    parts.append(random.choice(self.SPY_SCRAMBLE))
                else:
                    parts.append(" ")
            cv.create_text(cx, cy - 8, text="".join(parts),
                           font=(fam, 30, "bold"), fill=C(RED))

        # red underline draws itself once the title has locked
        uw = _ease_io((t - 1.6) / 0.4)
        if uw > 0:
            tw = MONO.measure(self.SPY_TITLE) + 26
            cv.create_line(cx - tw / 2 * uw, cy + 26, cx + tw / 2 * uw,
                           cy + 26, fill=C(RED, 0.9), width=2)

        # subline: typewriter with a live caret
        sub_t0 = 1.5
        n = int(max(0.0, t - sub_t0) / 0.011)
        if n > 0:
            sub = self.SPY_SUB[:min(n, len(self.SPY_SUB))]
            if n < len(self.SPY_SUB):
                sub += "▌"
            cv.create_text(cx, cy + 48, text=sub, font=(fam, 11),
                           fill=C(DIM, 0.95))

        # one scanline sweep down the window
        sp = _ease_io((t - 1.75) / 0.4)
        if sp > 0:
            y = h * 0.16 + sp * (h * 0.68)
            for k in range(6):
                yy = y - k * 5
                cv.create_rectangle(0, yy - 3, w, yy + 3,
                                    fill=C(RED, 0.12 * (1 - k / 6)),
                                    outline="")
            cv.create_rectangle(0, y - 1, w, y + 1, fill=C(RED), outline="")

        # skip hint, gently pulsing
        if t > 1.0:
            a = 0.55 + 0.25 * math.sin(t * 4.0)
            cv.create_text(cx, h - 40, text="click to skip · esc to cancel",
                           font=(fam, 10), fill=C("#7a7a80", a))

    def _end_spy_intro(self, start=True):
        """Tear down the overlay. start=False (Esc) cancels the launch."""
        if not self._spy_intro_active:
            return
        self._spy_intro_active = False
        if self._spy_job is not None:
            try:
                self.root.after_cancel(self._spy_job)
            except Exception:
                pass
            self._spy_job = None
        for seq in ("<Escape>", "<Return>"):
            try:
                self.root.unbind_all(seq)
            except Exception:
                pass
        ov, self._spy_intro = self._spy_intro, None
        if ov is not None:
            try:
                ov.destroy()
            except tk.TclError:
                pass
        cb, self._spy_intro_done = self._spy_intro_done, None
        if start and cb:
            cb()
        elif not start:
            self._set_status("Spy start cancelled.", self.T["dim"])

    # ------------------------------------------------------------ hotkeys ---
    @staticmethod
    def _key_match(key, name):
        """Does a pynput key event match a stored hotkey name?"""
        if not name:
            return False
        special = getattr(keyboard.Key, name, None)
        if special is not None:
            return key == special
        if len(name) == 1:
            ch = getattr(key, "char", None)
            return bool(ch) and ch.lower() == name
        return False

    def _start_hotkey_listener(self):
        def on_press(key):
            try:
                if self._capturing:
                    return  # a capture dialog is listening — stay quiet
                for action, fn in (("start", self.start_typing),
                                   ("pause", self.toggle_pause),
                                   ("stop", self.stop_typing)):
                    if self._key_match(key, self._hotkeys.get(action)):
                        self.root.after(0, fn)
                        return
            except Exception:
                pass

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()

    def _restart_listener(self):
        try:
            if self.listener:
                self.listener.stop()
        except Exception:
            pass
        self._start_hotkey_listener()

    # -------------------------------------------------------------- sounds --
    def _play_sound(self, name):
        """Play a macOS system sound (Glass / Pop / Basso…) if enabled."""
        if not self._sound:
            return
        try:
            subprocess.Popen(
                ["afplay", f"/System/Library/Sounds/{name}.aiff"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # --------------------------------------------------------------- prefs --
    def _collect_prefs(self):
        return {
            "theme": self._theme_name,
            "recent_light": self._recent_light,
            "recent_dark": self._recent_dark,
            "hotkeys": dict(self._hotkeys),
            "sound": self._sound,
            "settings": dict(self._settings),
            "preset": self._preset_idx,
            "geometry": self.root.geometry(),
        }

    def _save_prefs_now(self):
        try:
            p = persistence.load_prefs()
            p.update(self._collect_prefs())
            persistence.save_prefs(p)
            self._last_prefs_save = time.time()
        except Exception:
            pass

    def _close(self):
        self._capturing = False
        if self._spy_intro_active:
            self._end_spy_intro(start=False)
        self._save_prefs_now()
        if self.engine and self.engine.is_alive():
            # quitting mid-type? everything is kept, resumable next launch
            self._persist("paused")
            self.engine.stop()
        if self.listener:
            self.listener.stop()
        self.root.destroy()


def _ago(ts):
    d = time.time() - ts
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    return f"{int(d // 86400)}d ago"


def main():
    root = tk.Tk()
    init_fonts(root)
    AutoTyperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
