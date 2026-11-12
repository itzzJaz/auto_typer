# ⌨️ AutoTyper

**Types your code into any website — like a human, not a paste.**

Copy. Click. Press F8. AutoTyper types your clipboard out character by character
with real human timing: drifting speed, bursts, hesitation, occasional
believable typos — some of which it "notices" and fixes with backspace.

Because sites that block pasting detect a paste event, not keystrokes —
AutoTyper sends real keystrokes.

---

## Why it exists

Every developer has hit this: a coding platform, an online judge, a CMS form
that refuses `⌘V` but happily accepts typed input. Retyping 200 lines by hand
is not a solution. AutoTyper turns a paste into *performance typing* —
the same output, delivered through real keyboard events, at human cadence.

**The difference is in the timing.** Naive "typing macros" emit keystrokes at
fixed intervals — a pattern no human produces. AutoTyper is built on a
behavioral model of typing (`human_mode.py`):

| Behavior | What it simulates |
|---|---|
| **Speed drift** | pace wanders ±15–30% over tens of seconds (random walk + slow wave) |
| **Phases** | alternates *flow* / *steady* / *hesitant* stretches, like focus coming and going |
| **Warm-up** | first 30–80 characters come out slower, like a person settling in |
| **Log-normal latency** | keystroke gaps have a heavy tail, matching real typing data (≈2.2× spread between fast and slow moments at 55 WPM) |
| **Key difficulty** | capitals, digits and brackets take longer — they need Shift or an awkward reach |
| **Thinking pauses** | occasional 0.3–1.6 s "hmm" moments, rare 2–5 s distractions, a beat after every newline to "read the next line" |
| **Typo clusters** | mistakes get likelier at speed, and cluster together — people rush, then recover |
| **Composure** | after a typo, typing slows briefly, then recovers |
| **Believable typos** | wrong keys are always *neighboring* keys on QWERTY, never random characters |

The speed slider is calibrated so 55 WPM really averages 55 WPM — the
variability rides on top of a truthful average.

## Features

- 📋 **Clipboard-driven** — copy anywhere, type anywhere
- 🧬 **Human mode** — full variable-timing simulation, on by default
- 🎚️ **Tunable** — speed (WPM), typo rate, auto-fix percentage, start delay
- 🌍 **Global hotkeys** — `F8` start, `Esc` emergency stop, work from any app
- 🖥️ **Clean dark GUI** — paste box, live progress bar, real-time WPM readout
- 💻 **CLI too** — headless mode for scripting: `python3 autotyper.py --wpm 65`
- 🚦 **Safe** — instant stop, tabs converted to spaces so focus never jumps

## Quick start

```bash
git clone https://github.com/jazlaanjamsheer/auto_typer.git
cd auto_typer
pip3 install -r requirements.txt
python3 autotyper_gui.py        # GUI
python3 autotyper.py            # CLI (types the clipboard)
```

**macOS:** grant your terminal **Accessibility** and **Input Monitoring**
permission (System Settings → Privacy & Security) on first run — that's what
lets it send keystrokes to other apps.

**Windows / Linux:** `pynput` supports both; on Windows nothing extra is
needed, on Linux install `python3-tk` and an X server.

## Usage

1. Copy your text (`⌘C`)
2. Click into the target website's input box
3. Press **F8** → short countdown → it types everything out
4. **Esc** stops instantly, **F9** reloads from the clipboard (CLI)

In the GUI: paste into the box, tune the sliders, hit **▶ Start Typing**.

## Project layout

```
auto_typer/
├── autotyper_gui.py   # dark-themed Tkinter GUI + typing engine
├── autotyper.py       # CLI version (hotkeys: F8 / F9 / Esc)
├── human_mode.py      # the behavioral typing model (drift, phases, typos)
├── AutoTyper.command  # double-click launcher for macOS
├── requirements.txt
└── README.md
```

## Honest note

AutoTyper exists to save your hands from re-typing your own code where paste
is blocked. Don't use it to cheat on exams or assessments — the point is
comfort, not fraud.

---

*Built with Python 3 + pynput + Tkinter. No dependencies beyond one small
library; everything else is stdlib.*
