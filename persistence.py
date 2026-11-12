#!/usr/bin/env python3
"""
persistence.py — everything AutoTyper keeps on disk.

macOS:   ~/Library/Application Support/AutoTyper/
other:   ~/.autotyper/

Files:
    session.json   — an in-progress (or paused) typing session: the text,
                     how far it got, the settings used and the session
                     stats. Lets you quit the app mid-type and resume later.
    snippets.json  — the user's saved snippet library.
    stats.json     — lifetime totals (chars typed, typos fixed, sessions).
    history.json   — last 30 finished sessions, for the activity sparkline.
    prefs.json     — UI preferences (theme).
"""

import json
import os
import time


def _app_dir() -> str:
    if os.uname().sysname == "Darwin":
        base = os.path.join(os.path.expanduser("~"),
                            "Library", "Application Support")
    else:
        base = os.path.expanduser("~")
    d = os.path.join(base, "AutoTyper")
    os.makedirs(d, exist_ok=True)
    return d


_FILES = {
    "session": "session.json",
    "snippets": "snippets.json",
    "stats": "stats.json",
    "history": "history.json",
    "prefs": "prefs.json",
}


def _path(kind: str) -> str:
    return os.path.join(_app_dir(), _FILES[kind])


def _read(kind: str, default):
    try:
        with open(_path(kind), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(kind: str, data) -> None:
    p = _path(kind)
    tmp = p + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)          # atomic swap — never corrupt on crash
    except OSError:
        pass


# ------------------------------------------------------------- session ---
def save_session(text, index, settings, stats, counted, state):
    """Persist a typing session snapshot (running or paused)."""
    _write("session", {
        "version": 1,
        "text": text,
        "index": index,
        "settings": settings,
        "stats": stats,
        "counted": counted,     # chars already added to lifetime stats
        "state": state,
        "updated": time.time(),
    })


def load_session():
    return _read("session", None)


def clear_session():
    try:
        os.remove(_path("session"))
    except OSError:
        pass


# ------------------------------------------------------------ snippets ---
def load_snippets():
    return _read("snippets", [])


def add_snippet(name, text):
    items = [s for s in load_snippets() if s.get("name") != name]
    items.insert(0, {"name": name, "text": text,
                     "created": time.strftime("%Y-%m-%d")})
    save_snippets(items)
    return items


def delete_snippet(name):
    items = [s for s in load_snippets() if s.get("name") != name]
    save_snippets(items)
    return items


def save_snippets(items):
    _write("snippets", items[:100])


# --------------------------------------------------------------- stats ---
def load_stats():
    return _read("stats", {"chars": 0, "typos": 0, "fixes": 0, "sessions": 0})


def add_stats(chars=0, typos=0, fixes=0, sessions=0):
    s = load_stats()
    s["chars"] += chars
    s["typos"] += typos
    s["fixes"] += fixes
    s["sessions"] += sessions
    _write("stats", s)
    return s


# ------------------------------------------------------------- history ---
def load_history():
    return _read("history", [])


def add_history(entry):
    h = load_history()
    h.append(entry)
    _write("history", h[-30:])
    return h


# --------------------------------------------------------------- prefs ---
def load_prefs():
    return _read("prefs", {"theme": "light"})


def save_prefs(prefs):
    _write("prefs", prefs)
