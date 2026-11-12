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

- 🎨 **Apple-style UI** — pill buttons, switches, segmented controls and a
  live progress ring
- 🌈 **8 themes** — Light, Dark, Midnight, Dracula, Ocean, Sakura, plus two
  fun ones: **Matrix** (phosphor-green terminal, `auto_typer` wordmark) and
  **Retro CRT** (amber 80s monitor). Switch from the Light/Dark toggle or
  the gallery in **⚙ Settings** — applied instantly, remembered forever
- ⚙️ **Settings panel** — theme gallery with live previews, **remappable
  hotkeys** (click a chip → press a key; conflicts caught, defaults
  restorable) and sound effects
- 🎛️ **Remembered settings** — speed, typos, preset, hotkeys, theme and
  window size/position all persist between launches
- 🔁 **Repeat passes** — type the text up to 10× in one session (great for
  burn-in tests or practice)
- ⇄ **Shuffle** — randomize word order for a fresh practice text
- ⏸️ **Persistent pause & resume** — progress is continuously saved to disk,
  so you can quit the app mid-type and pick up exactly where you left off,
  even days later (an "Unfinished session" card appears on launch)
- 📚 **Snippet library** — save your texts with a name and reuse them
  anytime, right from the menu
- 📊 **Lifetime dashboard** — characters typed, typos fixed, sessions
  finished, plus an activity sparkline of your last runs
- ⚡ **Speed presets** — Chill / Balanced / Confident / Rapid, one click
- 📈 **Live stats** — current WPM, ETA to completion, typo & fix counters
- 🔔 **Sound effects** — a Glass chime on finish, Pop on stop (toggle in
  Settings)
- 📋 **Clipboard-driven** — copy anywhere, type anywhere; `⌘⏎` starts
  typing straight from the text box
- 🧬 **Human mode** — full variable-timing simulation, on by default
- 🎚️ **Tunable** — speed (WPM), typo rate, auto-fix percentage, start delay,
  repeat count
- 🌍 **Global hotkeys** — `F8` start, `F10` pause/resume, `Esc` emergency
  stop by default, all work from any app, all remappable
- 🔁 **Real self-correction** — typo → pause → backspace → correct key,
  every time (verified on real keystrokes)
- 💻 **CLI too** — headless mode for scripting: `python3 autotyper.py --wpm 65`
- 🚦 **Safe** — instant stop, tabs converted to spaces so focus never jumps,
  crash-safe atomic saves

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

In the GUI: paste into the box (or pick a snippet from **Library**), pick a
preset or tune the sliders, hit **▶ Start Typing**. **⏸ Pause** (or `F10`)
freezes it mid-text; **▶ Resume** continues exactly where it stopped — and
because progress is saved to disk every couple of seconds, you can even
**quit the app entirely** and resume from the "Unfinished session" card next
time you open it. **Esc** stops instantly but keeps your progress: nothing is
ever lost. Typos are always self-corrected — wrong key, short pause,
backspace, correct key — like a person who notices and fixes their mistakes
(lower the *Auto-fix* slider if you want a few to slip through).

Set **Repeat** to ×N to type the text N times in one session — the progress
ring and ETA account for all passes, and the counters keep accruing.

**Hotkeys:** defaults are `F8` / `F10` / `Esc`, but you can remap any of them
in **⚙ Settings** — click a key chip, press the new key, and it applies
everywhere instantly (buttons, footer, and the global listener). If an
F-key changes volume or brightness instead, enable "Use F1, F2 as standard
function keys" in System Settings → Keyboard.

Your data lives in `~/Library/Application Support/AutoTyper/`
(`session.json`, `snippets.json`, `stats.json`, plus `prefs.json` for your
theme, hotkeys, sliders and window size).

## Project layout

```
auto_typer/
├── autotyper_gui.py   # Apple-style Tkinter GUI + typing engine
├── persistence.py     # session save/resume, snippets, lifetime stats
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
