#!/usr/bin/env python3
"""
human_mode.py — realistic typing dynamics.

Real humans don't type at a constant speed with uniform random jitter.
Their keystroke latencies are log-normal, their speed drifts in waves,
they type in bursts, hesitate, get distracted, slow down after mistakes
and warm up at the start. This module models all of that.

HumanMode.delay(ch, prev) returns the pause before pressing `ch`.
HumanMode.typo_prob() returns the *current* mistake probability —
it rises when the simulated typist is going fast, and clusters mistakes
together, the way real people rush then recover.
"""

import math
import random

# characters that need Shift (US layout) or an awkward reach
SHIFT_CHARS = set('~!@#$%^&*()_+{}|:"<>?')
SYMBOLS = set('{}[]()<>/\\|=+-*')


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# The pauses, hesitation and warm-up below add overhead on top of raw
# keystroke speed; this constant keeps the *average* at the target WPM.
_CALIBRATION = 1.15


class HumanMode:
    def __init__(self, wpm: float, typo_rate: float):
        self.base_wpm = max(10.0, wpm)
        self.base_typo = typo_rate

        # slow speed drift — a mean-reverting random walk around 1.0
        self.drift = random.uniform(0.9, 1.08)
        # plus one long "energy wave" (e.g. warming up, getting tired)
        self.sine_phase = random.uniform(0, 2 * math.pi)
        self.sine_step = 2 * math.pi / (random.uniform(15, 40) *
                                        max(1.0, self.base_wpm * 5.5 / 60.0))

        # people start slower and speed up
        self.warmup_chars = random.uniform(30, 80)

        # typing phases: flow / steady / hesitant
        self.state = "steady"
        self.state_mult = 1.0
        self.state_left = random.randint(10, 25)

        # confidence after mistakes (0.45 = shaken, 1.0 = normal)
        self.composure = 1.0
        # mistakes cluster: right after one typo the next is likelier
        self.typo_momentum = 1.0

        self.chars = 0
        self.speed_ratio = 1.0  # current effective wpm / base wpm

    # ------------------------------------------------------------- phases ---
    def _next_state(self):
        r = random.random()
        if r < 0.45:
            self.state = "flow"          # in the zone, quick and steady
            self.state_mult = random.uniform(0.82, 0.97)
            self.state_left = random.randint(10, 35)
        elif r < 0.78:
            self.state = "steady"        # cruising
            self.state_mult = random.uniform(0.97, 1.10)
            self.state_left = random.randint(12, 40)
        else:
            self.state = "hesitant"      # unsure, re-reading, slower
            self.state_mult = random.uniform(1.22, 1.70)
            self.state_left = random.randint(3, 12)

    # ------------------------------------------------------------- timing ---
    def delay(self, ch: str, prev: str) -> float:
        """Seconds to wait before typing `ch`."""
        self.chars += 1

        # phase transitions
        self.state_left -= 1
        if self.state_left <= 0:
            # more likely to hesitate right after a newline (reading next line)
            if prev == "\n" and random.random() < 0.45:
                self.state, self.state_mult = "hesitant", random.uniform(1.25, 1.7)
                self.state_left = random.randint(4, 12)
            else:
                self._next_state()

        # effective speed: drift * wave * warm-up * phase
        self.drift += random.gauss(0, 0.008) + (1.0 - self.drift) * 0.004
        self.drift = _clamp(self.drift, 0.78, 1.30)
        self.sine_phase += self.sine_step
        warm = min(1.0, 0.80 + 0.20 * self.chars / self.warmup_chars)
        wpm = (_CALIBRATION * self.base_wpm * self.drift *
               (1.0 + 0.10 * math.sin(self.sine_phase)) * warm * self.state_mult)
        self.speed_ratio = wpm / self.base_wpm

        d = 60.0 / (wpm * 5.5)

        # keystroke latency is log-normal in real data — heavy tail
        d *= math.exp(random.gauss(0, 0.30))

        # harder keys take longer (Shift reach, digits, brackets)
        if ch.isupper() or ch in SHIFT_CHARS:
            d *= random.uniform(1.3, 2.1)
        elif ch.isdigit():
            d *= random.uniform(1.1, 1.5)
        elif ch in SYMBOLS:
            d *= random.uniform(1.15, 1.6)

        # natural pauses
        if ch in ".!?":
            d += random.uniform(0.2, 0.7)
        elif ch in ",;:":
            d += random.uniform(0.08, 0.3)
        if ch == "\n":
            d += random.uniform(0.25, 0.9)
        if prev == "\n":
            d *= random.uniform(1.2, 1.8)  # eyes jump to the next line first

        # recovering after a mistake
        d *= 1.0 + (1.0 - self.composure) * 0.9
        self.composure = min(1.0, self.composure + 0.10)

        # occasional "hmm" pauses and rare real distractions
        r = random.random()
        if r < 0.005:
            d += random.uniform(0.3, 1.6)
        elif r < 0.0062:
            d += random.uniform(2.0, 5.0)
        if ch in "{;}" and random.random() < 0.03:
            d += random.uniform(0.2, 0.8)

        return max(0.015, d)

    # -------------------------------------------------------------- typos ---
    def typo_prob(self) -> float:
        """Current per-character mistake probability."""
        p = self.base_typo * (self.speed_ratio ** 2) * self.typo_momentum
        if self.state == "hesitant":
            p *= 1.25
        elif self.state == "flow":
            p *= 0.80
        # momentum relaxes back toward 1.0
        self.typo_momentum += (1.0 - self.typo_momentum) * 0.07
        return p

    def on_typo(self):
        """Called when a typo happens — mistakes shake you up and cluster."""
        self.composure = max(0.45, self.composure - 0.4)
        self.typo_momentum = random.uniform(1.6, 2.6)
        if random.random() < 0.5:
            self.state, self.state_mult = "hesitant", random.uniform(1.25, 1.7)
            self.state_left = random.randint(5, 14)
