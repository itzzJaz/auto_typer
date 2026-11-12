#!/usr/bin/env python3
"""
AutoTyper GUI — human-like typing simulator with a window.

Paste (or load from clipboard) your text, click into the target website,
press Start (or F8 anywhere). It types everything like a person:
variable speed, pauses, and believable neighbor-key typos, some of
which it "notices" and fixes with backspace.

Global hotkeys (work while any other app is focused):
    F8  -> start typing
    Esc -> stop typing immediately
"""

import queue
import random
import threading
import time
import subprocess
import tkinter as tk
from tkinter import ttk

from pynput import keyboard
from pynput.keyboard import Controller

from autotyper import human_delay, base_delay, make_typo
from human_mode import HumanMode

# ----------------------------------------------------------------------
BG      = "#16161e"   # window
PANEL   = "#1e1e2a"   # boxes
FG      = "#e8e8ef"   # main text
DIM     = "#8b8b9e"   # secondary text
ACCENT  = "#7aa2f7"   # blue
GREEN   = "#9ece6a"
RED     = "#f7768e"
FONT    = ("Menlo", 12)
FONT_SM = ("Menlo", 10)
FONT_UI = ("Helvetica Neue", 12)
FONT_UI_B = ("Helvetica Neue", 13, "bold")
# ----------------------------------------------------------------------


class TypingEngine(threading.Thread):
    """Types self.text with human behavior, reporting progress to a queue."""

    def __init__(self, text, wpm, typo_rate, correct_chance, start_delay, events,
                 human=True):
        super().__init__(daemon=True)
        self.text = text
        self.wpm = wpm
        self.typo_rate = typo_rate
        self.correct_chance = correct_chance
        self.start_delay = start_delay
        self.events = events          # queue of (kind, payload)
        self.human = human            # variable mode
        self.kb = Controller()
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def run(self):
        for sec in range(int(self.start_delay), 0, -1):
            if self.stop_event.is_set():
                self.emit("stopped", "Cancelled")
                return
            self.emit("countdown", sec)
            time.sleep(1)
        if self.stop_event.is_set():
            self.emit("stopped", "Cancelled")
            return
        self.emit("countdown", 0)
        self.typos = 0
        self.fixes = 0
        if self.human:
            self._run_variable()
        else:
            self._run_flat()

    def _handle_typo(self, ch, wrong, notice_delay):
        """Type a wrong char; maybe backspace it. Returns True if corrected."""
        self.kb.type(wrong)
        time.sleep(notice_delay)
        if random.random() < self.correct_chance:
            self.kb.tap(keyboard.Key.backspace)
            time.sleep(base_delay(self.wpm) * random.uniform(0.5, 1.2))
            self.fixes += 1
            return True
        return False

    def _run_variable(self):
        """Human mode — drifting speed, bursts, pauses, clustered typos."""
        hm = HumanMode(self.wpm, self.typo_rate)
        total = len(self.text)
        typed = 0
        prev = ""
        for i, ch in enumerate(self.text):
            if self.stop_event.is_set():
                self.emit("stopped", f"Stopped at {i}/{total}")
                return
            d = hm.delay(ch, prev)
            if ch != "\n" and random.random() < hm.typo_prob():
                wrong = make_typo(ch)
                if wrong is not None:
                    hm.on_typo()
                    self.typos += 1
                    if not self._handle_typo(ch, wrong, d * random.uniform(1.5, 3.0)):
                        # typo stayed in the text
                        typed += 1
                        prev = wrong
                        self.emit("progress", (i + 1, total, self.typos, self.fixes, hm.speed_ratio))
                        time.sleep(hm.delay(wrong, prev))
                        continue
                    # corrected — now type the right char (fall through)
            self.kb.type(ch)
            typed += 1
            prev = ch
            self.emit("progress", (i + 1, total, self.typos, self.fixes, hm.speed_ratio))
            time.sleep(d)
        self.emit("done", f"Done — {typed} chars typed, {self.typos} typos "
                          f"({self.fixes} fixed), variable mode")

    def _run_flat(self):
        """Classic mode — same average speed, only light uniform jitter."""
        total = len(self.text)
        typed = 0
        wobble = self.wpm
        prev = ""
        for i, ch in enumerate(self.text):
            if self.stop_event.is_set():
                self.emit("stopped", f"Stopped at {i}/{total}")
                return
            if random.random() < 0.02:
                wobble = self.wpm * random.uniform(0.85, 1.2)
            if ch != "\n" and random.random() < self.typo_rate:
                wrong = make_typo(ch)
                if wrong is not None:
                    self.typos += 1
                    if not self._handle_typo(ch, wrong,
                                             human_delay(wobble, 0.55, ch, prev) *
                                             random.uniform(1.5, 3.0)):
                        typed += 1
                        prev = wrong
                        self.emit("progress", (i + 1, total, self.typos, self.fixes, 1.0))
                        time.sleep(human_delay(wobble, 0.55, ch, prev))
                        continue
                    # corrected — now type the right char (fall through)
            self.kb.type(ch)
            typed += 1
            prev = ch
            self.emit("progress", (i + 1, total, self.typos, self.fixes, 1.0))
            time.sleep(human_delay(wobble, 0.55, ch, prev))
        self.emit("done", f"Done — {typed} chars typed, {self.typos} typos "
                          f"({self.fixes} fixed)")


class AutoTyperGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = queue.Queue()
        self.engine = None
        self.listener = None

        root.title("AutoTyper")
        root.configure(bg=BG)
        root.geometry("640x640")
        root.minsize(560, 560)

        self._build_ui()
        self._start_hotkey_listener()
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(100, self._poll_events)

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        pad = {"padx": 14, "pady": 4}

        header = tk.Label(self.root, text="⌨️  AutoTyper", font=("Helvetica Neue", 20, "bold"),
                          bg=BG, fg=FG)
        header.pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(self.root, text="Paste your text, click into the website, press Start.",
                 font=FONT_UI, bg=BG, fg=DIM).pack(anchor="w", padx=14, pady=(0, 8))

        # ---- text box ----
        frame = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                         highlightbackground="#2a2a3a")
        frame.pack(fill="both", expand=True, **pad)
        self.textbox = tk.Text(frame, bg=PANEL, fg=FG, insertbackground=ACCENT,
                               font=FONT, wrap="none", relief="flat",
                               undo=True, padx=10, pady=10,
                               selectbackground="#33467c")
        ysb = ttk.Scrollbar(frame, orient="vertical", command=self.textbox.yview)
        xsb = ttk.Scrollbar(frame, orient="horizontal", command=self.textbox.xview)
        self.textbox.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")
        self.textbox.pack(fill="both", expand=True)

        # ---- clipboard buttons ----
        row = tk.Frame(self.root, bg=BG)
        row.pack(fill="x", padx=14)
        tk.Button(row, text="📋 Paste from Clipboard", font=FONT_UI, command=self.paste_clipboard,
                  bg=PANEL, fg=FG, activebackground="#2a2a3a", activeforeground=FG,
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left")
        tk.Button(row, text="Clear", font=FONT_UI, command=self.clear_text,
                  bg=PANEL, fg=DIM, activebackground="#2a2a3a", activeforeground=FG,
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left", padx=8)
        self.charlabel = tk.Label(row, text="", font=FONT_SM, bg=BG, fg=DIM)
        self.charlabel.pack(side="right")

        # ---- settings ----
        s = tk.Frame(self.root, bg=BG)
        s.pack(fill="x", padx=14, pady=(8, 0))
        s.columnconfigure((0, 1), weight=1, uniform="col")

        self.wpm = self._slider(s, 0, "⌨️ Speed", 20, 120, 55, " WPM")
        self.typo = self._slider(s, 1, "🤥 Typo rate", 0, 50, 12, "‰", div=10)
        self.fix = self._slider(s, 2, "✅ Auto-fix typos", 0, 100, 75, "%")
        self.delay = self._slider(s, 3, "⏱ Start delay", 1, 8, 3, " s")

        # ---- human mode toggle ----
        self.human_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.root, text="🧬 Human mode — variable speed, bursts, "
                       "hesitation, distractions & typo clusters",
                       variable=self.human_var, font=FONT_UI, bg=BG, fg=FG,
                       selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       highlightthickness=0, relief="flat", cursor="hand2").pack(
            anchor="w", padx=14, pady=(8, 0))

        # ---- start / stop ----
        btns = tk.Frame(self.root, bg=BG)
        btns.pack(fill="x", padx=14, pady=(10, 2))
        self.start_btn = tk.Button(btns, text="▶  Start Typing  (F8)", font=FONT_UI_B,
                                   command=self.start_typing, bg=GREEN, fg="#101010",
                                   activebackground="#b5d97a", relief="flat",
                                   padx=18, pady=9, cursor="hand2")
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(btns, text="⏹  Stop  (Esc)", font=FONT_UI_B,
                                  command=self.stop_typing, bg=RED, fg="#101010",
                                  activebackground="#ff9aa8", relief="flat",
                                  padx=18, pady=9, cursor="hand2", state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        # ---- progress ----
        self.bar = ttk.Progressbar(self.root, length=400, mode="determinate")
        self.bar.pack(fill="x", padx=14, pady=(8, 0))
        self.status = tk.Label(self.root, text="Ready.", font=FONT_UI, bg=BG, fg=DIM,
                               anchor="w")
        self.status.pack(fill="x", padx=14, pady=(4, 10))
        self._update_char_count()

    def _slider(self, parent, col, label, lo, hi, default, unit, div=1):
        cell = tk.Frame(parent, bg=BG)
        cell.grid(row=col // 2, column=col % 2, sticky="nsew", padx=(0, 18), pady=4)
        lab = tk.Label(cell, text=f"{label}:  {default}{unit}", font=FONT_UI, bg=BG, fg=FG,
                       anchor="w")
        lab.pack(fill="x")

        def on_move(v):
            val = float(v) / div
            shown = f"{val:g}{unit}"
            lab.configure(text=f"{label}:  {shown}")

        slider = tk.Scale(cell, from_=lo, to=hi, orient="horizontal", showvalue=False,
                          command=on_move, bg=BG, fg=FG, troughcolor=PANEL,
                          highlightthickness=0, relief="flat", bd=0, sliderrelief="flat",
                          font=FONT_SM, length=230)
        slider.set(default)
        slider.pack(fill="x")
        return slider

    # ------------------------------------------------------------ actions ---
    def _get_text(self):
        return self.textbox.get("1.0", "end-1c").replace("\t", "    ")

    def _update_char_count(self):
        t = self._get_text()
        self.charlabel.configure(text=f"{len(t)} chars · {len(t.splitlines())} lines")

    def paste_clipboard(self):
        try:
            out = subprocess.run(["pbpaste"], capture_output=True, text=True)
            text = out.stdout.replace("\t", "    ")
        except FileNotFoundError:
            self._set_status("Clipboard not available on this system.", RED)
            return
        if not text.strip():
            self._set_status("Clipboard is empty — copy something first.", RED)
            return
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self._update_char_count()
        self._set_status(f"Loaded {len(text)} characters from clipboard.", ACCENT)

    def clear_text(self):
        self.textbox.delete("1.0", "end")
        self._update_char_count()
        self._set_status("Cleared.", DIM)

    def start_typing(self):
        if self.engine and self.engine.is_alive():
            return
        text = self._get_text()
        if not text.strip():
            self._set_status("Nothing to type — paste some text first.", RED)
            return
        self.bar.configure(value=0, maximum=len(text))
        self.engine = TypingEngine(
            text=text,
            wpm=self.wpm.get(),
            typo_rate=self.typo.get() / 1000.0,
            correct_chance=self.fix.get() / 100.0,
            start_delay=self.delay.get(),
            events=self.events,
            human=self.human_var.get(),
        )
        self.engine.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def stop_typing(self):
        if self.engine:
            self.engine.stop()

    # ---------------------------------------------------- background glue ---
    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "countdown":
                    if payload > 0:
                        self._set_status(f"⏳ Typing starts in {payload}s — click into the "
                                         "website NOW...", ACCENT)
                    else:
                        self._set_status("Typing…", GREEN)
                elif kind == "progress":
                    done, total, typos, fixes = payload[:4]
                    self.bar.configure(value=done)
                    pct = done * 100 // total if total else 100
                    extra = ""
                    if len(payload) >= 5 and payload[4] != 1.0:
                        extra = f" · now {self.wpm.get() * payload[4]:.0f} WPM"
                    self._set_status(f"Typing… {done}/{total} ({pct}%) · "
                                     f"{typos} typos, {fixes} fixed{extra}", DIM)
                elif kind == "done":
                    self._set_status("✔ " + payload, GREEN)
                elif kind == "stopped":
                    self._set_status("⏹ " + payload, RED)
        except queue.Empty:
            pass
        finally:
            if self.engine and not self.engine.is_alive() and \
               (self.events.qsize() == 0):
                self.start_btn.configure(state="normal")
                self.stop_btn.configure(state="disabled")
            self.root.after(100, self._poll_events)

    def _set_status(self, msg, color=DIM):
        self.status.configure(text=msg, fg=color)

    # ---------------------------------------------------------- hotkeys ----
    def _start_hotkey_listener(self):
        def on_press(key):
            if key == keyboard.Key.f8:
                self.root.after(0, self.start_typing)
            elif key == keyboard.Key.esc:
                self.root.after(0, self.stop_typing)

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()

    def _close(self):
        self.stop_typing()
        if self.listener:
            self.listener.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoTyperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
