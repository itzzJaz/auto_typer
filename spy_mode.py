#!/usr/bin/env python3
"""
spy_mode.py — the full-variation session layer, on top of HumanMode.

HumanMode models the *keystroke*: log-normal latency, drifting speed,
phases, typo clusters. SpyMode models the *session* — the part a fixed
macro can never fake:

  · A fresh persona every run. Base speed ±10 %, accuracy ±40 %, an
    individual spacebar habit, a personal Shift style. Two runs never
    share a profile.
  · A fatigue arc. Pace warms up, sags over the minutes, gets a random
    "second wind", sags again.
  · Word rhythm. Some words come out in a burst, unfamiliar words are
    typed carefully; common digraphs (th, he, in…) and double letters
    run faster than average.
  · Real breaks — never on a fixed cycle. Every 25–75 s of *typing
    time* the typist pauses at a natural seam (end of a word, a line,
    after a sentence): usually 1.5–5 s ("re-reads, sips"), sometimes
    7–16 s ("checked the phone"), rarely 18–40 s ("someone called").
    After every break the first few characters come out slower, like
    re-orienting.
  · Double-space slips: occasionally a space is doubled and immediately
    corrected with backspace (the typing loop handles that part).

API (drop-in compatible with HumanMode):
    delay(ch, prev)      seconds to wait before typing ch
    typo_prob()          current per-character mistake probability
    on_typo()            call after a typo (composure, clustering)
    speed_ratio          current effective WPM / base WPM
    check_break(ch, prev)  call at each character boundary BEFORE typing
                           ch; returns seconds to pause now, or 0.0
"""

import math
import random

from human_mode import HumanMode, SHIFT_CHARS

# bigrams real typists hit noticeably faster (common English pairs)
DIGRAPHS = {
    "th", "he", "in", "er", "an", "re", "on", "at", "en", "nd", "ti",
    "es", "or", "te", "ed", "is", "it", "al", "ar", "st", "ou", "le",
    "ea", "se", "io", "ve", "me", "de", "hi", "ri", "ro", "ne", "co",
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# Breaks genuinely reduce throughput; this factor compensates so the
# slider's WPM stays truthful *including* break time — the same deal
# HumanMode's _CALIBRATION strikes for its pauses. Empirically tuned.
_SPY_CAL = 0.90


class SpyMode:
    def __init__(self, wpm: float, typo_rate: float):
        # ---- fresh persona: the "same" typist, but a new day --------
        self.base_wpm = max(10.0, wpm * random.uniform(0.90, 1.10))
        self.base_typo = max(0.0, typo_rate * random.uniform(0.70, 1.40))
        self.hm = HumanMode(self.base_wpm, self.base_typo)

        # personal motor habits
        self.space_mult = random.uniform(0.88, 1.18)
        self.shift_mult = random.uniform(0.90, 1.30)

        # fatigue arc: sag builds per minute, second winds interrupt it
        self.fatigue_per_min = random.uniform(0.008, 0.035)
        self.next_wind_t = random.uniform(150.0, 420.0)
        self.wind = 0.0
        self.session_t = 0.0

        # breaks: measured in *typing time*, re-randomized every time
        self.typed_time = 0.0
        self.until_break = random.uniform(40.0, 100.0)
        self.long_p = random.uniform(0.10, 0.22)   # 7–16 s phone check
        self.epic_p = random.uniform(0.02, 0.05)   # 18–40 s real absence

        # word rhythm
        self.word_len = 0
        self.word_fast = False
        self.word_slow = False

        # re-orienting after a break: first chars come out slower
        self.post_break = 0
        self.prev = ""

    # ------------------------------------------------------- passthrough ---
    def typo_prob(self) -> float:
        return self.hm.typo_prob()

    def on_typo(self):
        self.hm.on_typo()

    @property
    def speed_ratio(self) -> float:
        return self.hm.speed_ratio

    # ------------------------------------------------------------- breaks ---
    def check_break(self, ch: str, prev: str) -> float:
        """Call at every character boundary, BEFORE typing `ch`.

        Returns seconds to pause now (0.0 = no break). Breaks only fire
        at natural seams — after a word, a line, or a sentence — and
        only when enough *typing time* has piled up since the last one.
        """
        if self.typed_time < self.until_break:
            return 0.0
        at_seam = (prev in " \n" or
                   (prev and prev in ".!?,;:") or
                   ch == "\n")
        if not at_seam:
            return 0.0          # finish the word first, like a person
        r = random.random()
        if r < self.epic_p:
            dur = random.uniform(18.0, 40.0)   # "someone called my name"
        elif r < self.epic_p + self.long_p:
            dur = random.uniform(7.0, 16.0)    # phone check, stood up
        else:
            dur = random.uniform(1.5, 5.5)     # re-read, sip, glance
        # reset the break clock, freshly randomized
        self.typed_time = 0.0
        self.until_break = random.uniform(40.0, 100.0)
        self.post_break = random.randint(2, 5)
        return dur

    # ------------------------------------------------------------- timing ---
    def delay(self, ch: str, prev: str) -> float:
        """Seconds to wait before typing `ch`."""
        d = self.hm.delay(ch, prev)

        # ---- fatigue arc ----
        sag = min(0.16, (self.session_t / 60.0) * self.fatigue_per_min)
        if self.wind > 0.0:
            self.wind = max(0.0, self.wind - d / 80.0)   # fades over ~80 s
        elif self.session_t >= self.next_wind_t:
            self.wind = random.uniform(0.03, 0.09)
            self.next_wind_t = self.session_t + random.uniform(200.0, 500.0)
        d *= 1.0 + max(0.0, sag - self.wind)
        self.session_t += d

        # ---- word rhythm ----
        if ch == " ":
            self.word_len = 0
            r = random.random()
            self.word_fast = r < 0.13            # familiar word — a burst
            self.word_slow = 0.13 <= r < 0.18    # unfamiliar — careful
        else:
            self.word_len += 1
        if self.word_fast and self.word_len <= 5:
            d *= random.uniform(0.84, 0.93)
        elif self.word_slow:
            d *= random.uniform(1.08, 1.22)

        # ---- digraphs & double letters run faster ----
        pair = (prev + ch).lower()
        if len(pair) == 2 and (pair in DIGRAPHS or ch == prev):
            d *= random.uniform(0.80, 0.93)

        # ---- personal habits ----
        if ch == " ":
            d *= self.space_mult
        elif ch.isupper() or ch in SHIFT_CHARS:
            d *= self.shift_mult

        # mid-word flinch — the "wait, is that right?" hitch
        if random.random() < 0.006:
            d += random.uniform(0.08, 0.45)

        # first characters after a break: re-orienting
        if self.post_break > 0:
            d *= random.uniform(1.25, 1.65)
            self.post_break -= 1

        # a little per-run noise on top of everything
        d *= math.exp(random.gauss(0, 0.05))

        d *= _SPY_CAL            # keep the slider's WPM truthful incl. breaks
        self.typed_time += d
        self.prev = ch
        return max(0.012, d)
