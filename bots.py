# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS: bots. Small background helpers you add with "+ Add a bot", for one tab or for the app.

A bot is a Claude Code run (your own installed Claude Code, `claude -p`) with one job, the words you typed. New bots read
and report only: they can read one folder (the tab's, or the app's) and search it, and can't change anything, unless you
give one more on its Perms tab. Each run is its own background process with its own log; every message goes on
the bus, one line per message in data/bots/bus/<date>.jsonl, and the Bots tab shows them, with each day's record.

Every bot has an ID (B001, B002, ...). Every program it runs carries a label with that ID, its name and its task, in
its command line (Task Manager's Details tab shows it under "Command line"; `ps -ef` on Linux) and in data/bots/procs.json,
so a leftover program can always be traced to its bot, and the bot asked whether it still needs it.

Every Claude Code bot runs on its own: from its own folder in your app-data folder (no CLAUDE.md above it), with no saved
session, no user settings or hooks, no connectors, only the tools its permissions allow, and none of the calling
session's Claude variables. At most MAX_PARALLEL bots run at once, none start when free memory is low, and none start
while everything is paused. Bots stop when Randis UDS closes.

  python bots.py list               every bot, its status and last result
  python bots.py run NAME           one run now, waiting for it
  python bots.py leftovers          programs bots started that are still running and no run is using
  python bots.py ask PID            ask the bot that started a leftover program whether it still needs it
"""
from __future__ import annotations

import ctypes
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

import ccode

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_PARALLEL = 2
MIN_FREE_GB = 1.0
READ_TOOLS = ["Read", "Grep", "Glob"]
# How often a bot runs: None is "when you click Start now"; the rest are minutes.
EVERY_CHOICES = (None, 5, 15, 30, 60, 180, 720, 1440)
CHAT_TURNS = 12
GROUP_TURNS = 16
REPORT_CAP = 200_000
PROC_KEEP_DAYS = 2
WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if WIN else 0
DETACHED = (0x00000008 | 0x00000200) if WIN else 0        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def home() -> str:
    """Where the registry, state, bus and logs live (UDS_BOTS_DIR in tests)."""
    return os.environ.get("UDS_BOTS_DIR") or os.path.join(HERE, "data", "bots")


def p(*parts) -> str:
    return os.path.join(home(), *parts)


def workspaces() -> str:
    """Each bot's own working folder, in the user's app-data folder, away from any project and its CLAUDE.md."""
    if os.environ.get("UDS_BOT_WORKSPACES"):
        return os.environ["UDS_BOT_WORKSPACES"]
    base = os.environ.get("LOCALAPPDATA") if WIN else (os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"))
    return os.path.join(base or os.path.expanduser("~"), "RandisUDS", "bot_workspaces")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    for _ in range(40):                                   # another process may be reading it this moment (Windows)
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def _read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _jsonl(path: str) -> list[dict]:
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def _append(path: str, row: dict) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ---------------------------------------------------------------- registry and state
def _ensure_ids(reg: dict) -> bool:
    """Give every bot without an ID (or with one another bot already has) the next free one. True if any changed."""
    used = [int(b["id"][1:]) for b in reg.get("bots", []) if re.fullmatch(r"B\d+", str(b.get("id", "")))]
    nxt, changed, seen = max(used, default=0) + 1, False, set()
    for b in reg.get("bots", []):
        if not b.get("id") or b["id"] in seen:
            b["id"], nxt, changed = f"B{nxt:03d}", nxt + 1, True
        seen.add(b["id"])
    return changed


def load_registry() -> dict:
    reg = _read_json(p("registry.json"), {"bots": []})
    if _ensure_ids(reg):
        save_registry(reg)
    return reg


def save_registry(reg: dict) -> None:
    _ensure_ids(reg)
    _write_json(p("registry.json"), reg)


def bot(name: str) -> dict:
    for b in load_registry()["bots"]:
        if b["name"] == name:
            return b
    raise KeyError(f"There's no bot named {name}.")


def _edit_bot(name: str, fn) -> dict:
    reg = load_registry()
    for b in reg["bots"]:
        if b["name"] == name:
            fn(b)
            save_registry(reg)
            return b
    raise KeyError(f"There's no bot named {name}.")


def approved(b: dict) -> bool:
    a = b.get("approved") or {}
    return b.get("status") == "approved" and bool(a.get("words")) and bool(a.get("date"))


def label(b: dict, task: str) -> str:
    """The readable tag on every program a bot runs: "B007 game_bug_hunter1: scheduled run"."""
    return f"{b.get('id') or 'B???'} {b.get('name', '?')}: {task}"


def read_state(name: str) -> dict:
    return _read_json(p("state", f"{name}.json"), {})


_state_lock = threading.Lock()


def write_state(name: str, **kw) -> dict:
    with _state_lock:
        st = read_state(name)
        st.update(kw)
        _write_json(p("state", f"{name}.json"), st)
    return st


def pid_alive(pid) -> bool:
    if not pid:
        return False
    if WIN:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259             # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    try:                                                  # a finished child that hasn't been reaped yet doesn't count
        with open(f"/proc/{int(pid)}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except OSError:
        return True


def kill_tree(pid) -> None:
    if WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        return
    for sig_target in (lambda: os.killpg(int(pid), 15), lambda: os.kill(int(pid), 15)):
        try:
            sig_target()
            return
        except OSError:
            pass


def running(name: str) -> bool:
    return pid_alive(read_state(name).get("pid"))


def in_run(name: str) -> bool:
    """Mid-run right now (a bot waiting for its next turn doesn't count toward MAX_PARALLEL)."""
    st = read_state(name)
    return pid_alive(st.get("pid")) and (not st.get("last_end") or str(st.get("last_start", "")) > str(st["last_end"]))


def busy_others(name: str) -> list[str]:
    return [x["name"] for x in load_registry()["bots"] if x["name"] != name and in_run(x["name"])]


# ---------------------------------------------------------------- the bus (every message, kept by day: it is the record)
def post(sender: str, kind: str, text: str, data=None) -> dict:
    msg = {"ts": now(), "from": sender, "kind": kind, "text": text}
    if data is not None:
        msg["data"] = data
    return _append(p("bus", datetime.now().strftime("%Y-%m-%d") + ".jsonl"), msg)


def read_bus(day: str | None = None, last: int | None = None) -> list[dict]:
    rows = _jsonl(p("bus", (day or datetime.now().strftime("%Y-%m-%d")) + ".jsonl"))
    return rows[-last:] if last else rows


def record_days() -> list[str]:
    """The days that have a record, newest first."""
    try:
        return sorted((f[:-6] for f in os.listdir(p("bus")) if re.fullmatch(r"\d{4}-\d\d-\d\d\.jsonl", f)), reverse=True)
    except OSError:
        return []


def record(day: str | None = None) -> dict:
    """One day's record, from the bus: runs, failures and tokens per bot, what needs a look, and what was said."""
    day = day or datetime.now().strftime("%Y-%m-%d")
    rows = read_bus(day)
    per = {}
    for r in rows:
        if r.get("kind") in ("result", "failure", "skipped"):
            b = per.setdefault(r.get("from", "?"), {"runs": 0, "failed": 0, "skipped": 0, "seconds": 0, "tokens": 0, "last": ""})
            b["runs" if r["kind"] != "skipped" else "skipped"] += 1
            b["failed"] += r["kind"] == "failure"
            b["seconds"] = round(b["seconds"] + ((r.get("data") or {}).get("seconds") or 0), 1)
            b["tokens"] += (r.get("data") or {}).get("tokens") or 0
            b["last"] = f"{r.get('ts', '')[11:16]} {r.get('text', '')}"
    look = [f"{r.get('ts', '')[11:16]} {r.get('from')}: {r.get('text')}" for r in rows if r.get("kind") in ("failure", "refused", "lock", "leftover")]
    said = [f"{r.get('ts', '')[11:16]} {r.get('from')}: {r.get('text')}" for r in rows if r.get("kind") in ("chat", "group", "rule", "paused", "resumed", "perms")]
    return {"day": day, "messages": len(rows), "bots": per, "look": look, "said": said}


# ---------------------------------------------------------------- guards
def free_ram_gb() -> float | None:
    if os.environ.get("UDS_BOTS_FAKE_FREE_GB"):                    # tests
        return float(os.environ["UDS_BOTS_FAKE_FREE_GB"])
    try:
        if WIN:
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 1024 ** 3
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024 ** 2
    except Exception:
        pass
    return None


def paused() -> dict | None:
    """{since} while every bot is paused (the Pause all button), else None. Kept across restarts."""
    return _read_json(p("PAUSED.json"), None) if os.path.exists(p("PAUSED.json")) else None


def why_not(name: str, scheduled: bool = False) -> str | None:
    """None if the bot may run now; otherwise why not, in plain words."""
    b = bot(name)
    if not approved(b):
        return "it's retired" if b.get("status") == "retired" else "it has no yes from you"
    if paused():
        return "every bot is paused (Resume all bots starts them again)"
    if not scheduled and running(name):
        return "it's already running"
    if not ccode.command():
        return "Claude Code isn't installed on this computer"
    busy = busy_others(name)
    if len(busy) >= MAX_PARALLEL:
        return f"{MAX_PARALLEL} bots are already running ({', '.join(busy)})"
    free = free_ram_gb()
    if free is not None and free < MIN_FREE_GB:
        return f"free memory is low ({free:.1f} GB; bots wait for {MIN_FREE_GB:.0f} GB)"
    return None


# ---------------------------------------------------------------- permissions
# Every bot reads its own folder. More is the user's to give, bot by bot, on its Perms tab: a level, or the
# switches one by one. Hold-backs block one kind of command even when the switches would allow it.
PERM_FEATURES = [
    ("read", "Read files", "Open, search and list the files in its folder", ["Read", "Grep", "Glob"]),
    ("edit", "Change files", "Change files in its folder and make new ones", ["Edit", "Write", "NotebookEdit"]),
    ("run", "Run commands", "Run programs and terminal commands (Python, Git, anything a terminal can do)", ["Bash", "PowerShell"]),
    ("web", "Use the web", "Search the web and read web pages", ["WebFetch", "WebSearch"]),
]
PERM_LEVELS = {"read": "Read only", "custom": "Custom (the switches below)", "full": "Full access (anything, without asking)"}
HOLDBACKS = [
    ("no_push", "No pushing or publishing", "Blocks git push and GitHub commands, so nothing goes online without you",
     ["Bash(git push:*)", "PowerShell(git push:*)", "Bash(gh:*)", "PowerShell(gh:*)"]),
    ("no_install", "No installs", "Blocks pip, npm, winget, apt and other installers",
     ["Bash(pip install:*)", "Bash(npm install:*)", "Bash(winget:*)", "Bash(apt:*)", "Bash(apt-get:*)", "Bash(sudo:*)",
      "PowerShell(pip install:*)", "PowerShell(npm install:*)", "PowerShell(winget:*)", "PowerShell(choco:*)"]),
    ("lock", "Locked files stay locked", "Can't change the files on the Bots tab's locked list; a change is reported", []),
]
HOLD_DEFAULTS = {"no_push": True, "no_install": True, "lock": True}
READ_FEATURES = {k: k == "read" for k, *_ in PERM_FEATURES}
FULL_FEATURES = {k: True for k, *_ in PERM_FEATURES}


def perms_of(b: dict) -> dict:
    """A bot's permissions with every switch filled in, as its level makes them. No setting: read only."""
    pm = b.get("perms") or {}
    level = pm.get("level") if pm.get("level") in PERM_LEVELS else "read"
    feats = dict(FULL_FEATURES) if level == "full" else dict(READ_FEATURES) if level == "read" else \
        {k: bool((pm.get("features") or {}).get(k)) for k, *_ in PERM_FEATURES}
    holds = {k: bool((pm.get("holds") or {}).get(k, HOLD_DEFAULTS.get(k, False))) for k, *_ in HOLDBACKS}
    return {"level": level, "features": feats, "holds": holds}


def set_perms(name: str, level: str, features: dict | None = None, holds: dict | None = None) -> dict:
    if level not in PERM_LEVELS:
        raise ValueError("Pick Read only, Custom or Full access.")
    pm = perms_of({"perms": {"level": level, "features": features or {}, "holds": holds or {}}})
    _edit_bot(name, lambda b: b.__setitem__("perms", pm))
    post("you", "perms", f"{name}: {perms_summary({'perms': pm})}")
    return pm


def perms_summary(b: dict) -> str:
    pm = perms_of(b)
    if pm["level"] == "full":
        text = "full access: any tool, anywhere, without asking"
    else:
        on = [lbl.lower() for k, lbl, *_ in PERM_FEATURES if pm["features"].get(k)]
        text = ", ".join(on) if on else "nothing"
    held = [lbl.lower() for k, lbl, *_ in HOLDBACKS if pm["holds"].get(k)]
    return text + (f"; held back: {'; '.join(held)}" if held else "")


def can_change(b: dict) -> bool:
    f = perms_of(b)["features"]
    return bool(f.get("edit") or f.get("run"))


# ---------------------------------------------------------------- locked files and the shared rules
def locked_patterns() -> list[str]:
    return [x for x in _read_json(p("settings.json"), {}).get("locked", []) if x]


def set_locked(text: str) -> list[str]:
    pats = [x.strip() for x in str(text or "").splitlines() if x.strip()][:200]
    st = _read_json(p("settings.json"), {})
    st["locked"] = pats
    _write_json(p("settings.json"), st)
    post("you", "perms", f"locked files list: {len(pats)} entr{'y' if len(pats) == 1 else 'ies'}")
    return pats


def locked_files() -> list[str]:
    """Every file the locked list names (a path, or a pattern like C:\\work\\*.py or ~/notes/**)."""
    out = set()
    for pat in locked_patterns():
        pat = os.path.expanduser(pat)
        for f in glob.glob(pat, recursive=True):
            if os.path.isfile(f):
                out.add(os.path.abspath(f))
    return sorted(out)


def lock_snapshot(b: dict) -> dict:
    """{path: bytes} of the locked files, for a bot that could change them; else {}."""
    if not can_change(b) or not perms_of(b)["holds"].get("lock"):
        return {}
    snap = {}
    for f in locked_files():
        try:
            with open(f, "rb") as fh:
                snap[f] = fh.read()
        except OSError:
            pass
    return snap


def lock_check(name: str, snap: dict) -> list[str]:
    """Report every locked file that changed while the bot worked; keep both versions. Nothing is put back: the change
    may have been yours, made at the same time."""
    hit = []
    stamp = f"{datetime.now():%Y-%m-%d_%H%M%S}_{name}"
    for path, data in snap.items():
        try:
            with open(path, "rb") as f:
                after = f.read()
        except OSError:
            after = None
        if after == data:
            continue
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", path)[-120:]
        for which, blob in (("before", data), ("after", after)):
            if blob is not None:
                keep = p("lock", stamp, which, safe)
                os.makedirs(os.path.dirname(keep), exist_ok=True)
                with open(keep, "wb") as f:
                    f.write(blob)
        hit.append(path)
    if hit:
        post(name, "lock", f"locked files changed while {name} was working: {', '.join(hit)}. Nothing was put back; "
             f"both versions are in data/bots/lock/{stamp}.")
    return hit


def rules_text() -> str:
    try:
        with open(p("bot_rules.md"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def set_rules(text: str) -> str:
    text = str(text or "")[:50_000]
    os.makedirs(home(), exist_ok=True)
    with open(p("bot_rules.md"), "w", encoding="utf-8") as f:
        f.write(text)
    post("you", "rule", "the rules every bot reads were changed")
    return text


def add_rule(text: str, from_bot: str = "") -> str:
    """A mistake becomes a rule: one line added to the rules every bot reads."""
    text = " ".join(str(text or "").split())
    if len(text) < 4:
        raise ValueError("Write the rule first.")
    line = f"- {text}" + (f" (learned from {from_bot}, {datetime.now():%m/%d/%Y})" if from_bot else "")
    old = rules_text().rstrip("\n")
    set_rules((old + "\n" if old else "") + line + "\n")
    return line


# ---------------------------------------------------------------- the card: duties, your own tabs, run reports
DUTY_KINDS = ("general", "special")
CARD_TAB_NAMES = ("card", "report", "chat", "duties", "metrics", "processes", "permissions", "+")


def _card(name: str) -> dict:
    return _read_json(p("cards", f"{name}.json"), {})


def _save_card(name: str, card: dict) -> None:
    _write_json(p("cards", f"{name}.json"), card)


def duties(name: str) -> dict:
    d = _card(name).get("duties") or {}
    return {k: d.get(k, "") for k in DUTY_KINDS}


def set_duties(name: str, kind: str, text: str) -> dict:
    if kind not in DUTY_KINDS:
        raise ValueError("Duties are general or special.")
    bot(name)
    card = _card(name)
    card.setdefault("duties", {})[kind] = str(text or "").strip()[:20000]
    _save_card(name, card)
    return duties(name)


def duties_prompt(name: str) -> str:
    d = duties(name)
    parts = [f"Your {k} duties, in the user's words:\n{d[k]}" for k in DUTY_KINDS if d.get(k)]
    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def card_tabs(name: str) -> list[dict]:
    return _card(name).get("tabs", [])


def card_tab_add(name: str, title: str) -> dict:
    bot(name)
    title = " ".join(str(title or "").split())[:40]
    if not title:
        raise ValueError("Give the new tab a name.")
    tabs = card_tabs(name)
    if title.lower() in CARD_TAB_NAMES or any(t["title"].lower() == title.lower() for t in tabs):
        raise ValueError(f"This card already has a tab called {title}.")
    tab = {"id": f"t{int(time.time() * 1000)}", "title": title, "text": ""}
    card = _card(name)
    card["tabs"] = tabs + [tab]
    _save_card(name, card)
    return tab


def card_tab_save(name: str, tab_id: str, text: str) -> dict:
    card = _card(name)
    for t in card.get("tabs", []):
        if t["id"] == tab_id:
            t["text"] = str(text or "")[:200_000]
            _save_card(name, card)
            return t
    raise KeyError("That tab isn't there any more.")


def card_tab_remove(name: str, tab_id: str) -> list[dict]:
    card = _card(name)
    card["tabs"] = [t for t in card.get("tabs", []) if t["id"] != tab_id]
    _save_card(name, card)
    return card["tabs"]


def run_reports(name: str, n: int = 30) -> list[dict]:
    """The bot's run logs, newest first."""
    d = p("logs", name)
    try:
        files = sorted((f for f in os.listdir(d) if re.fullmatch(r"\d{4}-\d\d-\d\d_\d{6}\.log", f)), reverse=True)[:n]
    except OSError:
        return []
    return [{"file": f, "when": f"{f[:10]} {f[11:13]}:{f[13:15]}:{f[15:17]}", "size": os.path.getsize(os.path.join(d, f))} for f in files]


def run_report(name: str, file: str | None = None) -> dict:
    bot(name)
    runs = run_reports(name)
    file = file or (runs[0]["file"] if runs else None)
    if not file:
        return {"runs": runs, "file": None, "text": ""}
    if not re.fullmatch(r"\d{4}-\d\d-\d\d_\d{6}\.log", str(file)) or not os.path.isfile(p("logs", name, file)):
        raise ValueError("That report isn't there.")
    with open(p("logs", name, file), encoding="utf-8", errors="replace") as f:
        text = f.read(REPORT_CAP + 1)
    if len(text) > REPORT_CAP:
        text = text[:REPORT_CAP] + "\n\n(cut here; the whole report is in data/bots/logs)"
    return {"runs": runs, "file": file, "text": text}


# ---------------------------------------------------------------- token use
TOKEN_KEYS = ("in", "out", "cache_write", "cache_read")


def read_claude_output(stdout: str) -> tuple[str, dict]:
    """claude -p --output-format json -> (the answer, its tokens). Anything else -> (the text as it is, {})."""
    try:
        d = json.loads(stdout)
    except (ValueError, TypeError):
        return stdout or "", {}
    if not isinstance(d, dict):
        return stdout or "", {}
    u = d.get("usage") or {}
    t = {"in": u.get("input_tokens") or 0, "out": u.get("output_tokens") or 0,
         "cache_write": u.get("cache_creation_input_tokens") or 0, "cache_read": u.get("cache_read_input_tokens") or 0,
         "cost_usd": d.get("total_cost_usd") or 0}
    return str(d.get("result") or ""), t


def _count_tokens(name: str, toks: dict) -> None:
    if not toks:
        return
    with _state_lock:
        st = read_state(name)
        tot = dict(st.get("tokens") or {})
        for k in (*TOKEN_KEYS, "cost_usd"):
            tot[k] = round(tot.get(k, 0) + (toks.get(k) or 0), 6)
        st.update(tokens=tot, last_tokens=toks)
        _write_json(p("state", f"{name}.json"), st)
    _append(p("usage.jsonl"), {"ts": now(), "bot": name, **{k: toks.get(k, 0) for k in TOKEN_KEYS},
                                "total": sum(toks.get(k, 0) for k in TOKEN_KEYS), "cost_usd": toks.get("cost_usd", 0)})


def usage(name: str | None = None, days: int = 14) -> dict:
    """Token use per day for the last `days` days (one bot, or all), for the Metrics chart."""
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    per = {(datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d"): 0 for i in range(days)}
    calls = cost = 0
    for r in _jsonl(p("usage.jsonl")):
        if name and r.get("bot") != name:
            continue
        d = str(r.get("ts", ""))[:10]
        if d >= start and d in per:
            per[d] += r.get("total") or 0
            calls += 1
            cost += r.get("cost_usd") or 0
    return {"days": [{"day": d, "tokens": t} for d, t in per.items()], "calls": calls, "cost_usd": round(cost, 4)}


# ---------------------------------------------------------------- the programs bots run (labelled, traceable)
_procs_lock = threading.Lock()


def _procs() -> dict:
    return _read_json(p("procs.json"), {})


def _save_procs(d: dict) -> None:
    cut = time.time() - PROC_KEEP_DAYS * 86400
    _write_json(p("procs.json"), {k: v for k, v in d.items() if not v.get("ended_t") or v["ended_t"] > cut})


def proc_add(pid: int, name: str, lbl: str, kind: str) -> None:
    b = next((x for x in load_registry()["bots"] if x["name"] == name), {})
    with _procs_lock:
        d = _procs()
        d[str(pid)] = {"pid": pid, "bot": name, "id": b.get("id"), "label": lbl, "kind": kind, "started": now(), "started_t": time.time()}
        _save_procs(d)


def proc_end(pid: int) -> None:
    with _procs_lock:
        d = _procs()
        if str(pid) in d and not d[str(pid)].get("ended"):
            d[str(pid)].update(ended=now(), ended_t=time.time())
            _save_procs(d)


def system_procs() -> list[dict]:
    """Every program on the computer: pid, parent, name, command line. Windows asks CIM; Linux reads /proc."""
    if os.environ.get("UDS_BOTS_FAKE_PROCS"):                      # tests
        return json.loads(os.environ["UDS_BOTS_FAKE_PROCS"])
    if WIN:
        ps = "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60, creationflags=NO_WINDOW)
            rows = json.loads(r.stdout or "[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return []
        rows = rows if isinstance(rows, list) else [rows]
        return [{"pid": x["ProcessId"], "ppid": x["ParentProcessId"], "name": x["Name"], "cmd": x.get("CommandLine") or ""} for x in rows]
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                stat = f.read()
            with open(f"/proc/{d}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        name, rest = stat[stat.index("(") + 1:stat.rindex(")")], stat[stat.rindex(")") + 2:].split()
        out.append({"pid": int(d), "ppid": int(rest[1]), "name": name, "cmd": cmd})
    return out


TAG_IN_CMD = re.compile(r"(B\d{3,}) ([A-Za-z0-9_]+): ([^\"\n]{0,120})")


def scan_procs(rows: list[dict] | None = None) -> list[dict]:
    """Every live program that belongs to a bot: labelled in its command line, listed in procs.json, or started by one
    of those. "leftover": the bot isn't in a run that uses it, and nobody said to keep it."""
    rows = system_procs() if rows is None else rows
    rec, live = _procs(), {r["pid"]: r for r in rows}
    reg = {b["name"]: b for b in load_registry()["bots"]}

    def own(r):
        x = rec.get(str(r["pid"]))
        if x and not x.get("ended"):
            return x["bot"], x["label"]
        m = TAG_IN_CMD.search(r.get("cmd") or "")
        if m and m.group(2) in reg and reg[m.group(2)].get("id") == m.group(1):
            return m.group(2), m.group(0).strip()
        return None

    out = []
    for r in rows:
        mine, cur, seen = own(r), r, set()
        while not mine and cur and cur["pid"] not in seen:                # walk up to the first labelled parent
            seen.add(cur["pid"])
            par = live.get(cur["ppid"])
            if par:
                mine = own(par)
                cur = par
            else:
                x = rec.get(str(cur["ppid"]))                               # its parent has ended; procs.json says whose
                if x:
                    mine = (x["bot"], x["label"] + " (what started it has ended)")
                cur = None
        if not mine or mine[0] not in reg:
            continue
        x = rec.get(str(r["pid"]), {})
        busy = in_run(mine[0]) or (x.get("kind") == "loop" and not x.get("ended"))
        out.append({"pid": r["pid"], "name": r["name"], "bot": mine[0], "id": reg[mine[0]].get("id"), "label": mine[1],
                    "cmd": (r.get("cmd") or "")[:300], "kept": bool(x.get("kept")), "ppid": r["ppid"],
                    "leftover": not busy and not x.get("kept")})
    top = {x["pid"]: x for x in out}
    for x in out:                                                           # ask about the top of a leftover tree only
        par = top.get(x["ppid"])
        if x["leftover"] and par and par["bot"] == x["bot"] and (par["leftover"] or par["kept"]):
            x["leftover"], x["under"] = False, par["pid"]
    return out


def proc_chat(name: str) -> list[dict]:
    return _jsonl(p("chats", f"{name}.procs.jsonl"))


def proc_ask(pid: int, by: str = "you") -> dict:
    """Ask the bot a leftover program belongs to whether it still needs it. It answers on its next run or chat."""
    hit = next((x for x in scan_procs() if x["pid"] == int(pid)), None)
    if not hit:
        raise KeyError(f"No bot program has the number {pid} now.")
    q = f"Program {pid} ({hit['name']}, labelled \"{hit['label']}\") is still running, but no run of yours is using it. Do you still need it?"
    row = _append(p("chats", f"{hit['bot']}.procs.jsonl"), {"ts": now(), "who": by, "text": q, "pid": int(pid), "ask": True})
    post(by, "leftover", f"asked {hit['bot']} about program {pid}")
    return row


def proc_answer(pid: int, keep: bool, why: str = "", by: str = "you") -> dict:
    """Keep: it stays, and isn't asked about again. Not keep: it's ended, with whatever it started."""
    pid = int(pid)
    hit = next((x for x in scan_procs() if x["pid"] == pid), None)
    owner = (hit or {}).get("bot") or _procs().get(str(pid), {}).get("bot")
    if not owner:
        raise KeyError(f"No bot program has the number {pid} now.")
    if keep:
        with _procs_lock:
            d = _procs()
            x = d.setdefault(str(pid), {"pid": pid, "bot": owner, "id": (hit or {}).get("id"), "label": (hit or {}).get("label", ""),
                                        "kind": "found", "started": now(), "started_t": time.time()})
            x["kept"] = True
            _save_procs(d)
    else:
        kill_tree(pid)
        proc_end(pid)
    text = f"{'Keep' if keep else 'Done with'} program {pid}" + (f": {why}" if why else "") + ("" if keep else " (ended)")
    row = _append(p("chats", f"{owner}.procs.jsonl"), {"ts": now(), "who": by, "text": text, "pid": pid, "answer": "keep" if keep else "done"})
    post(by, "leftover", f"{owner}: {text}")
    return row


def open_questions(name: str) -> list[dict]:
    rows, out = proc_chat(name), []
    for i, m in enumerate(rows):
        if m.get("ask") and not any(n.get("answer") and n.get("pid") == m.get("pid") for n in rows[i + 1:]):
            out.append(m)
    return out


def _questions_prompt(name: str) -> str:
    qs = open_questions(name)
    if not qs:
        return ""
    return ("\n\nQuestions about programs of yours that are still running:\n" + "\n".join(f"- {q['text']}" for q in qs)
            + "\nFor each one, end your answer with a line on its own: KEEP <number> <why> if you still need it, or "
              "DONE <number> if you don't (it will be ended).")


def _take_answers(name: str, text: str) -> None:
    """KEEP / DONE lines in a bot's answer settle the questions it was asked."""
    asked = {q["pid"] for q in open_questions(name)}
    for m in re.finditer(r"^\s*(KEEP|DONE)\s+(\d+)\s*(.*)$", text or "", re.M):
        pid = int(m.group(2))
        if pid in asked:
            try:
                proc_answer(pid, m.group(1) == "KEEP", m.group(3).strip()[:200], by=name)
            except KeyError:
                pass


# ---------------------------------------------------------------- running
def clean_env(b: dict | None = None, task: str = "") -> dict:
    """This environment minus anything that ties a child to a Claude Code session, plus the bot's label."""
    env = {k: v for k, v in os.environ.items()          # CLAUDE_CONFIG_DIR stays: it says where the user's own sign-in is
           if not ((k.startswith("CLAUDE") and k != "CLAUDE_CONFIG_DIR") or "cc-msg" in v)}
    env["UDS_BOTS_DIR"] = home()
    if b:
        env.update(UDS_BOT_ID=b.get("id") or "", UDS_BOT_NAME=b["name"], UDS_BOT_TASK=task)
    return env


def workspace(b: dict) -> str:
    d = os.path.join(workspaces(), b["name"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write(f"# Bot: {b['name']} ({b.get('id')})\n\nYou are a small background bot inside Randis UDS, added by its user.\n"
                f"Your one job: {b['job']}\n\nYour permissions (the user sets them on your card's Perms tab): {perms_summary(b)}.\n"
                "Do only that job, and stay in your own folder unless the user says otherwise. If something you need isn't "
                "allowed, say so in your answer instead of finding a way around it. Answer in a few short plain lines; your "
                "answer is shown in the app's Bots tab.\n"
                f"This computer runs {'Windows: use PowerShell commands' if WIN else 'Linux: use shell commands'}.\n")
        rules = rules_text().strip()
        if rules:
            f.write("\n## Rules every bot follows (written by the user)\n" + rules + "\n")
    return d


def claude_cmd(b: dict, task: str = "run") -> list[str]:
    pm = perms_of(b)
    feats = pm["features"]
    cmd = list(ccode.command() or ["claude"]) + [
        "-p", "--no-session-persistence", "--setting-sources", "project", "--strict-mcp-config", "--output-format", "json",
        "--append-system-prompt", f"[{label(b, task)}]"]           # the label, so Task Manager shows whose run it is
    if pm["level"] == "full":
        cmd += ["--permission-mode", "bypassPermissions"]
    else:
        tools = [t for k, _l, _d, ts in PERM_FEATURES if feats.get(k) for t in ts]
        cmd += ["--permission-mode", "dontAsk"] + (["--allowedTools", *tools] if tools else ["--tools", ""])
    if b.get("reads_dir"):
        cmd += ["--add-dir", b["reads_dir"]]
    for d in b.get("extra_dirs") or []:
        cmd += ["--add-dir", d]
    deny = [r for k, _l, _d, rules in HOLDBACKS if pm["holds"].get(k) for r in rules] if can_change(b) else []
    if pm["holds"].get("lock") and can_change(b):
        deny += [f"{t}({f})" for f in locked_files() for t in ("Edit", "Write")]
    if deny:
        cmd += ["--disallowedTools", *deny]
    return cmd


def _claude(b: dict, prompt: str, task: str, timeout: int) -> tuple[int, str, str, dict]:
    """One labelled Claude Code call for a bot: (exit, answer, stderr, tokens). The prompt goes in on stdin."""
    proc = subprocess.Popen(claude_cmd(b, task), cwd=workspace(b), env=clean_env(b, task), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                            creationflags=NO_WINDOW)
    proc_add(proc.pid, b["name"], label(b, task), "claude")
    try:
        out, err = proc.communicate(input=prompt, timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        kill_tree(proc.pid)
        out, err = proc.communicate()
        code, err = -1, f"timed out after {timeout} s\n{err or ''}"
    except OSError as e:
        return -1, "", f"Claude Code didn't start: {e}", {}
    finally:
        proc_end(proc.pid)
    answer, toks = read_claude_output(out or "")
    return code, answer, err or "", toks


def run_once(name: str) -> dict:
    """One run of the bot, in this process. Returns {exit, summary, seconds}."""
    b = bot(name)
    os.makedirs(p("logs", name), exist_ok=True)
    t0 = time.time()
    stamp = datetime.now()
    while os.path.exists(log := p("logs", name, stamp.strftime("%Y-%m-%d_%H%M%S") + ".log")):
        stamp += timedelta(seconds=1)                 # two runs in one second keep both reports
    open(log, "w").close()
    task = "scheduled run" if (b.get("trigger") or {}).get("every_min") else "run"
    write_state(name, last_start=now(), last_log=log)
    snap = lock_snapshot(b)
    prompt = b.get("prompt", "") + duties_prompt(name) + _questions_prompt(name)
    try:
        if b.get("service"):
            code, answer, err, toks = _service_run(b)
        else:
            code, answer, err, toks = _claude(b, prompt, task, b.get("timeout_s", 900))
    except OSError as e:
        code, answer, err, toks = -1, "", f"Claude Code didn't start: {e}", {}
    changed = lock_check(name, snap)
    out = answer + (("\n[stderr]\n" + err) if err.strip() else "")
    if changed:
        out += "\n[lock] locked files changed during this run (reported, not put back): " + ", ".join(changed)
    with open(log, "w", encoding="utf-8") as f:
        f.write(out)
    lines = [x.strip() for x in answer.splitlines() if x.strip() and not re.match(r"\s*(KEEP|DONE)\s+\d+", x)]
    if code != 0 and not lines:
        lines = [x.strip() for x in err.splitlines() if x.strip()]
    summary = (lines[-1] if lines else "(no answer)")[:300]
    secs = round(time.time() - t0, 1)
    st = read_state(name)
    write_state(name, last_end=now(), last_exit=code, last_summary=summary, last_answer=answer.strip()[:4000],
                runs=st.get("runs", 0) + 1, fails=st.get("fails", 0) + (code != 0), last_seconds=secs,
                seconds=round(st.get("seconds", 0) + secs, 1))
    _count_tokens(name, toks)
    _take_answers(name, answer)
    post(name, "result" if code == 0 else "failure", summary,
         {"exit": code, "seconds": secs, "tokens": sum(toks.get(k, 0) for k in TOKEN_KEYS)})
    return {"exit": code, "summary": summary, "seconds": secs}


def _loop(name: str, once: bool) -> None:
    write_state(name, pid=os.getpid(), mode="once" if once else "schedule", started=now())
    stop = p("state", f"{name}.stop")
    first = True
    try:
        while True:
            reason = None if first else why_not(name, scheduled=True)
            if reason:
                post(name, "skipped", f"run skipped: {reason}")
            else:
                run_once(name)
            first = False
            every = (bot(name).get("trigger") or {}).get("every_min")
            if once or not every:
                break
            end = time.time() + 60 * every
            write_state(name, next_due=datetime.fromtimestamp(end).strftime("%Y-%m-%d %H:%M:%S"))
            while time.time() < end:
                if os.path.exists(stop):
                    return
                time.sleep(2)
    finally:
        if os.path.exists(stop):
            os.remove(stop)
        write_state(name, pid=None, next_due=None)
        proc_end(os.getpid())


def launch(name: str, once: bool = True) -> dict:
    """Start a bot in its own background process. Refuses, with the reason, when a guard says no."""
    reason = why_not(name)
    if reason:
        post("bots", "refused", f"{name} didn't start: {reason}")
        return {"started": False, "reason": reason}
    if os.path.exists(p("state", f"{name}.stop")):
        os.remove(p("state", f"{name}.stop"))
    b = bot(name)
    task = "one run" if once else "on its schedule"
    kw = {"creationflags": DETACHED | NO_WINDOW} if WIN else {"start_new_session": True}
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_exec", name, "once" if once else "schedule", label(b, task)],
                            cwd=HERE, env=clean_env(b, task), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, **kw)
    proc_add(proc.pid, name, label(b, task), "loop")
    write_state(name, pid=proc.pid, mode="once" if once else "schedule", started=now(), wanted=not once)
    post("bots", "started", f"{name} started ({'one run' if once else 'on its schedule'})")
    return {"started": True, "pid": proc.pid}


def halt(name: str, why: str = "", keep_wanted: bool = False) -> dict:
    st = read_state(name)
    os.makedirs(p("state"), exist_ok=True)
    open(p("state", f"{name}.stop"), "w").close()
    killed = False
    if pid_alive(st.get("pid")):
        kill_tree(st["pid"])
        proc_end(st["pid"])
        killed = True
    write_state(name, pid=None, next_due=None, **({} if keep_wanted else {"wanted": False}))
    if os.path.exists(p("state", f"{name}.stop")):
        os.remove(p("state", f"{name}.stop"))
    if killed or why:
        post("bots", "stopped", f"{name} stopped" + (f" ({why})" if why else ""))
    return {"stopped": True, "killed": killed}


def stop_all(why: str) -> int:
    """Closing the app: every bot stops; the ones on a schedule start again next time the app opens."""
    n = 0
    for b in load_registry()["bots"]:
        if running(b["name"]):
            halt(b["name"], why, keep_wanted=True)
            n += 1
    return n


def resume_wanted() -> list[str]:
    """The bots that were on their schedule (when the app closed, or before Pause all), started again."""
    out = []
    if paused():
        return out
    for b in load_registry()["bots"]:
        if approved(b) and read_state(b["name"]).get("wanted") and not running(b["name"]):
            if launch(b["name"], once=False).get("started"):
                out.append(b["name"])
    return out


def pause_all() -> dict:
    """The Pause all bots button: every run and schedule stops now; Resume all brings back the scheduled ones."""
    _write_json(p("PAUSED.json"), {"since": now()})
    ended = [b["name"] for b in load_registry()["bots"] if running(b["name"])]
    for name in ended:
        halt(name, keep_wanted=True)
    post("you", "paused", "every bot paused" + (f"; stopped {', '.join(ended)}" if ended else ""))
    return {"paused": True, "ended": ended}


def resume_all() -> dict:
    if os.path.exists(p("PAUSED.json")):
        os.remove(p("PAUSED.json"))
    post("you", "resumed", "bots resumed")
    return {"paused": False, "started": resume_wanted()}


def set_frequency(name: str, choice) -> dict:
    """The card's How often dropdown: "off" (only when you click Start now) or minutes. A schedule starts at once."""
    every = None if str(choice) in ("off", "", "None") else int(choice)
    if every not in EVERY_CHOICES:
        raise ValueError("Pick one of the choices in the list.")
    b = _edit_bot(name, lambda x: x.__setitem__("trigger", {"every_min": every} if every else {}))
    st = read_state(name)
    if pid_alive(st.get("pid")) and st.get("mode") == "schedule":
        halt(name)
    post("you", "schedule", f"{name}: {'every ' + str(every) + ' min' if every else 'only when you click Start now'}")
    if every and approved(b):
        return launch(name, once=False)
    return {"started": False, "reason": "it runs when you click Start now"}


def retire(name: str) -> dict:
    b = _edit_bot(name, lambda x: x.__setitem__("status", "retired"))
    if running(name):
        halt(name, "retired")
    post("bots", "retired", f"{name} retired")
    return b


# ---------------------------------------------------------------- talking to bots
def chat_log(name: str) -> list[dict]:
    return _jsonl(p("chats", f"{name}.jsonl"))


def chat(name: str, text: str) -> dict:
    """You talk to one bot: a Claude Code reply from its own folder, with its own permissions, seeing its job, its latest
    result and the chat so far. Its tokens count toward the bot."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("Type a message first.")
    b = bot(name)
    if b.get("status") == "retired":
        raise ValueError(f"{name} is retired.")
    if paused():
        raise ValueError("Every bot is paused. Resume all bots to talk to them.")
    if not ccode.command():
        raise ValueError("Bots run on Claude Code, which isn't installed on this computer.")
    st = read_state(name)
    history = chat_log(name)[-CHAT_TURNS:]
    _append(p("chats", f"{name}.jsonl"), {"ts": now(), "who": "you", "text": text})
    convo = "\n".join(f"{'User' if m['who'] == 'you' else 'You'}: {m['text']}" for m in history)
    prompt = (f"You are the bot \"{name}\" ({b.get('id')}). Your job: {b.get('job', '')}\n"
              + (f"Your latest run ({st.get('last_end')}): {st.get('last_summary')}\n" if st.get("last_end") else "You haven't run yet.\n")
              + "The user is talking with you directly. Answer in short, plain words.\n"
              + duties_prompt(name) + _questions_prompt(name)
              + (f"\nThe chat so far:\n{convo}\n" if convo else "") + f"\nUser: {text}\nYou:")
    t0 = time.time()
    snap = lock_snapshot(b)
    code, answer, err, toks = _claude(b, prompt, "chat reply", 300)
    changed = lock_check(name, snap)
    reply = answer.strip() or f"(no answer; exit {code}) {err.strip()[-300:]}".strip()
    if changed:
        reply += "\n\n[Locked files changed while I was answering: " + ", ".join(changed) + ". Nothing was put back.]"
    _count_tokens(name, toks)
    _take_answers(name, answer)
    row = _append(p("chats", f"{name}.jsonl"), {"ts": now(), "who": "bot", "text": reply, "seconds": round(time.time() - t0, 1)})
    post("you", "chat", f"to {name}: {text[:120]}")
    return row


def group_log() -> list[dict]:
    return _jsonl(p("chats", "_all.jsonl"))


def group_waiting() -> list[str]:
    w = _read_json(p("chats", "_all.wait.json"), {})
    return w.get("bots", []) if w and time.time() - w.get("t", 0) < 600 else []


def group_chat(text: str) -> dict:
    """Chat with all bots: every working bot answers in turn (MAX_PARALLEL at a time), each seeing the group's recent talk.
    Runs to the end; the app calls it in the background and shows replies as they land."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("Type a message first.")
    if paused():
        raise ValueError("Every bot is paused. Resume all bots to talk to them.")
    if not ccode.command():
        raise ValueError("Bots run on Claude Code, which isn't installed on this computer.")
    members = [b["name"] for b in load_registry()["bots"] if approved(b)]
    if not members:
        raise ValueError("There are no working bots to talk to yet.")
    history = group_log()[-GROUP_TURNS:]
    _append(p("chats", "_all.jsonl"), {"ts": now(), "who": "you", "text": text})
    convo = "\n".join(f"{'User' if m['who'] == 'you' else m['who']}: {m['text']}" for m in history)
    left, queue, lock = list(members), list(members), threading.Lock()

    def wait_file():
        _write_json(p("chats", "_all.wait.json"), {"bots": left, "t": time.time()})

    wait_file()

    def one(name):
        b = bot(name)
        prompt = (f"You are the bot \"{name}\" ({b.get('id')}). Your job: {b.get('job', '')}\n"
                  f"The user is talking to all their bots at once: {', '.join(members)}. Answer for yourself only, in a few "
                  "short plain lines, from your own job's point of view. If it isn't for you, say so in one line.\n"
                  + (f"\nThe chat so far:\n{convo}\n" if convo else "") + f"\nUser: {text}\nYou:")
        t0 = time.time()
        code, answer, err, toks = _claude(b, prompt, "chat with all bots", 300)
        _count_tokens(name, toks)
        return answer.strip() or f"(no answer; exit {code})", round(time.time() - t0, 1)

    def worker():
        while True:
            with lock:
                if not queue:
                    return
                name = queue.pop(0)
            try:
                reply, secs = one(name)
            except Exception as e:                      # one bot failing doesn't stop the others
                reply, secs = f"(no answer: {e})", 0
            with lock:
                _append(p("chats", "_all.jsonl"), {"ts": now(), "who": name, "text": reply, "seconds": secs})
                left.remove(name)
                wait_file()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(min(MAX_PARALLEL, len(members)))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    try:
        os.remove(p("chats", "_all.wait.json"))
    except OSError:
        pass
    post("you", "group", f"to all bots: {text[:120]}")
    return {"members": members}


# ---------------------------------------------------------------- computer helpers: ready-made bots for everyday upkeep
# Offered on the app's own "+ Add a bot" form. Each says what it reads and what more it may do before it's made; ticking
# it is the yes. Their jobs are fixed here, not taken from the page. None deletes or installs anything: they report, and
# the ones that need a command to look (free space, updates) are told to look only.
def user_folder(kind: str) -> str:
    """The person's own folders, on Windows and Linux."""
    home = os.path.expanduser("~")
    if kind == "home":
        return home
    names = {"downloads": ("DOWNLOAD", "Downloads"), "documents": ("DOCUMENTS", "Documents")}[kind]
    if not WIN:
        try:
            r = subprocess.run(["xdg-user-dir", names[0]], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip() and os.path.isdir(r.stdout.strip()):
                return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    d = os.path.join(home, names[1])
    return d if os.path.isdir(d) else home


RUN = {"read": True, "run": True}
HELPERS = [
    {"id": "leftover_cleaner", "label": "Leftover program cleaner", "reads": "app", "perms": RUN, "every": 60,
     "job": "Find programs that bots started and forgot. Run: \"{py}\" \"{app}{sep}bots.py\" leftovers. For each leftover it lists, "
            "run: \"{py}\" \"{app}{sep}bots.py\" ask <number>, so the bot that started it is asked whether it still needs it. "
            "Never end a program yourself: the user decides on the Bots tab. Report what you asked about."},
    {"id": "backup", "label": "Backup bot", "reads": "documents", "perms": {"read": True, "edit": True, "run": True}, "every": 1440,
     "job": "Back up the folder {folder} into {dest}: copy it into a new folder named with today's date (like 2026-11-08), "
            "skipping files you can't read. Change nothing in {folder} and delete nothing anywhere. Report how many files were copied "
            "and say plainly if anything failed. If {dest} holds more than 5 dated copies, say so, so the user can remove old ones."},
    {"id": "disk", "label": "Disk space watcher", "reads": "home", "perms": RUN, "every": 1440,
     "job": "Check the free space on each drive with a command that only looks (no changes). If any drive has less than 10% free, "
            "list the 10 biggest folders in {folder} with their sizes, so the user can decide what to clear. Delete nothing."},
    {"id": "downloads", "label": "Downloads tidier", "reads": "downloads", "perms": RUN, "every": 1440,
     "job": "Look through the Downloads folder {folder} (look only, change nothing). Suggest a tidy plan: which files to sort into "
            "folders by type, and installers (.exe, .msi, .deb, .rpm, .AppImage, .dmg) older than 30 days that could be deleted, "
            "with their sizes. Move and delete nothing."},
    {"id": "duplicates", "label": "Duplicate finder", "reads": "documents", "perms": RUN, "every": 1440,
     "job": "Find files in {folder} that are exact copies of each other: same size first, then the same content hash. List each "
            "group side by side with its paths and size, biggest first, so the user can pick which to keep. Change and delete nothing."},
    {"id": "updates", "label": "Program update checker", "reads": "home", "perms": RUN, "every": 1440, "holds": {"no_install": False},
     "job": "List the installed programs that have updates waiting, using the system's own tool in look-only form "
            "(Windows: winget upgrade with no other words; Linux: apt list --upgradable, or dnf check-update). "
            "Install and update nothing. Report each program with its version now and the new one."},
    {"id": "machine", "label": "Computer health watcher", "reads": "home", "perms": RUN, "every": 60,
     "job": "Check the computer's health with commands that only look: free memory, processor load, and temperature if the system "
            "reports it. List the 5 programs using the most memory. If free memory is under 1 GB or anything runs hot, say so first."},
    {"id": "daily_brief", "label": "Morning briefing", "reads": "data", "perms": {"read": True}, "every": 1440,
     "job": "Read the notes and tabs saved in {folder} (the tabs folder holds built tabs; session.json lists the open tabs and their notes). "
            "Write a short morning briefing: what looks due today, what's waiting on the user, and anything left half done."},
    {"id": "link_checker", "label": "Link checker", "reads": "documents", "perms": {"read": True, "web": True}, "every": 1440,
     "job": "Find the web links (http and https) in the text files, notes and web pages in {folder}, check each one, and list the "
            "ones that no longer work, with the file each is in. Change nothing."},
]


def helpers(data_dir: str) -> list[dict]:
    """The helpers as the form shows them: what each reads and what more it may do."""
    out = []
    for h in HELPERS:
        pm = perms_of({"perms": {"level": "custom", "features": h["perms"], "holds": h.get("holds", {})}})
        out.append({"id": h["id"], "label": h["label"], "every": h["every"], "reads": _helper_dir(h, data_dir),
                    "can": perms_summary({"perms": pm}), "job": _helper_job(h, data_dir, "the backup folder you pick")})
    return out


def _helper_dir(h: dict, data_dir: str) -> str:
    return HERE if h["reads"] == "app" else data_dir if h["reads"] == "data" else user_folder(h["reads"])


def _helper_job(h: dict, data_dir: str, dest: str = "") -> str:
    return h["job"].format(py=sys.executable, app=HERE, sep=os.sep, folder=_helper_dir(h, data_dir), dest=dest)


def add_helper(hid: str, data_dir: str, every_min=None, folder: str = "", dest: str = "") -> dict:
    """Make one computer helper. folder/dest: the backup's source and destination (the backup only)."""
    h = next((x for x in HELPERS if x["id"] == hid), None)
    if not h:
        raise ValueError("There's no helper by that name.")
    extra = []
    if hid == "backup":
        folder = os.path.abspath(os.path.expanduser(str(folder or "").strip() or user_folder("documents")))
        dest = os.path.abspath(os.path.expanduser(str(dest or "").strip()))
        if not os.path.isdir(folder):
            raise ValueError("The folder to back up isn't there.")
        if not str(dest).strip() or dest == os.path.abspath(""):
            raise ValueError("Say where the backups go (a folder on another drive is best).")
        if os.path.normcase(dest + os.sep).startswith(os.path.normcase(folder + os.sep)):
            raise ValueError("The backups can't go inside the folder being backed up.")
        os.makedirs(dest, exist_ok=True)
        extra, reads, job = [dest], folder, h["job"].format(py=sys.executable, app=HERE, sep=os.sep, folder=folder, dest=dest)
    else:
        reads, job = _helper_dir(h, data_dir), _helper_job(h, data_dir)
    b = add_bot(job, reads, "your computer", {"level": "app"}, every_min if every_min in EVERY_CHOICES and every_min else h["every"], h["label"])
    pm = perms_of({"perms": {"level": "custom", "features": h["perms"], "holds": h.get("holds", {})}})
    def setup(x):
        x["perms"] = pm
        x["helper"] = hid
        if extra:
            x["extra_dirs"] = extra
            x["where"] = f"your computer (backs up {reads} into {extra[0]})"
    b = _edit_bot(b["name"], setup)
    post("you", "perms", f"{b['name']}: {perms_summary(b)} (a computer helper)")
    return b


# ---------------------------------------------------------------- adding a bot
def add_bot(words: str, reads_dir: str, where: str, scope: dict, every_min=None, label_: str = "", name_: str = "",
            types: list | None = None, yes: str = "") -> dict:
    """"+ Add a bot": what the person typed is the bot's job and their yes. A new bot reads and reports only.
    The Bot design suite also gives a name, the bot types it's made from, and the yes in the person's own words."""
    words = " ".join(str(words or "").split())
    if len(words) < 8:
        raise ValueError("Say what the bot should do (a sentence is enough).")
    if len(words) > 2000:
        raise ValueError("That's long for one bot's job. Keep it under 2000 characters.")
    if every_min not in EVERY_CHOICES:
        raise ValueError("How often must be one of the choices in the list.")
    if not reads_dir or not os.path.isdir(reads_dir):
        raise ValueError("The folder this bot would read isn't there.")
    if not ccode.command():
        raise ValueError("Bots run on Claude Code, which isn't installed on this computer. Install it from claude.com/claude-code, "
                         "sign in once in a terminal, then try again.")
    reg = load_registry()
    names = {b["name"] for b in reg["bots"]}
    lbl = " ".join(str(label_ or "").split())[:40]
    slug = lambda x, k: re.sub(r"[^a-z0-9]+", "_", str(x or "").lower()).strip("_")[:k]
    base = slug(scope.get("tab_title"), 24) or slug(scope.get("tab_kind"), 20) or "app"
    kind = slug(lbl, 20) or "bot"                     # e.g. randis_sound_forge_bug_hunter1
    n = 1
    while f"{base}_{kind}{n}" in names:
        n += 1
    name = f"{base}_{kind}{n}"
    want = _clean_name(name_)
    if want:
        if want in names:
            raise ValueError(f"There's already a bot called {want}. Pick another name.")
        name = want
    prompt = (f"You are a bot the user added for {where}. You may read the folder {reads_dir}.\n"
              f"The user's words, your job: {words}\n"
              "Do the job with what your permissions allow, then report in a few short plain lines. End with one line on "
              "its own that sums up what you found.")
    entry = {"name": name, "label": lbl, "job": words, "where": where, "kind": "claude", "prompt": prompt, "tools": list(READ_TOOLS),
             "reads_dir": os.path.abspath(reads_dir), "trigger": {"every_min": every_min} if every_min else {},
             "scope": scope, "writes": "nothing (it reports here)",
             "approved": {"words": " ".join(str(yes or "").split()) or words, "date": datetime.now().strftime("%m/%d/%Y")},
             "status": "approved", "timeout_s": 900}
    if types:
        entry["types"] = list(types)
    reg["bots"].append(entry)
    save_registry(reg)
    post("bots", "added", f"{name} added for {where}: \"{words}\"")
    return bot(name)


def overview() -> list[dict]:
    out = []
    for b in load_registry()["bots"]:
        st = read_state(b["name"])
        alive = pid_alive(st.get("pid"))
        out.append({**{k: b.get(k) for k in ("name", "id", "label", "job", "where", "kind", "trigger", "status", "approved", "reads_dir", "scope",
                                             "types", "service")},
                    "writes": "nothing (it reports here)" if not can_change(b) else perms_summary(b),
                    "running": alive, "in_run": alive and in_run(b["name"]), "state": st, "perms": perms_of(b),
                    "questions": len(open_questions(b["name"])), "tabs": [{"id": t["id"], "title": t["title"]} for t in card_tabs(b["name"])]})
    return out


def usage_rows() -> list[list]:
    """Every run's and chat's token count, [when, bot, tokens], for the Bots tab's charts (they zoom from minutes to years)."""
    return [[r.get("ts"), r.get("bot"), r.get("total") or 0] for r in _jsonl(p("usage.jsonl"))]


# ---------------------------------------------------------------- bot types, services and the Bot design suite
# Bot types are names only: what a bot of a type does is the user's to say, in its job. A service is a small crew of bots
# that hand work along; it unlocks when there's a bot of every type it needs, and opening it (with the user's yes) makes
# its tender, which runs the crew one stage at a time. Everything a service does stays within its bots' permissions.
BOT_TYPES = [("archivist", "Archivist", "ledger"), ("librarian", "Librarian", "book"), ("historian", "Historian", "book"),
             ("digital_archeologist", "Digital archeologist", "lens"), ("researcher", "Researcher", "lens"),
             ("subject_expert", "Subject-matter expert", "spark"), ("data_scientist", "Data scientist", "flask"),
             ("accountant", "Accountant", "ledger"), ("security_manager", "Security manager", "lock"), ("editor", "Editor", "book"),
             ("auditor", "Auditor", "ledger"), ("cartographer", "Cartographer", "layers"), ("scout", "Scout", "spark"),
             ("quartermaster", "Quartermaster", "gear"), ("translator", "Translator", "book"), ("curator", "Curator", "layers"),
             ("tester", "Tester", "bug"), ("mentor", "Mentor", "bulb")]
SERVICES = [
    {"id": "market_research", "label": "Market research", "needs": ["researcher", "data_scientist"], "hue": "#3d9bff",
     "blurb": "What's out there and what the numbers say about it.", "goal": "a short market-research brief about what's in your folder"},
    {"id": "private_investigator", "label": "Private investigator", "needs": ["archivist", "historian", "researcher"], "hue": "#b46bff",
     "blurb": "Who changed what, when and why.", "goal": "a case file: what changed most recently in your folder, when, and what it was for"},
    {"id": "resource_finder", "label": "Resource finder", "needs": ["librarian", "scout"], "hue": "#3fb950",
     "blurb": "Where things are, and what's worth getting.", "goal": "a list of what's in your folder, where it is, and what's worth adding or updating"},
    {"id": "data_mining", "label": "Data mining", "needs": ["digital_archeologist", "data_scientist"], "hue": "#e3b341",
     "blurb": "Dig up old results and see what they show.", "goal": "old results, notes and logs that were never looked at again, and what they show"},
    {"id": "data_analytics", "label": "Data analytics", "needs": ["data_scientist", "accountant"], "hue": "#ff9a2e",
     "blurb": "What the work costs and what it buys.", "goal": "what your bots cost to run (their token use) and what each one has delivered"},
    {"id": "ad_agency", "label": "Ad agency", "needs": ["researcher", "editor"], "hue": "#ff4d4d",
     "blurb": "Plain, honest copy for what you make.", "goal": "draft copy for what's in your folder, honest about what each thing does (drafts only; nothing is published)"},
    {"id": "legal", "label": "Legal", "needs": ["subject_expert", "auditor"], "hue": "#8a8f98",
     "blurb": "License and terms checks. Not legal advice.", "goal": "a license and terms check of what's in your folder, labeled 'not legal advice'"},
]


def _clean_name(s) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").lower()).strip("_")[:40]


def bot_types() -> list[dict]:
    """Every bot type: the ones Randis UDS comes with, then the ones the user named (custom: true)."""
    mine = _read_json(p("types.json"), {}).get("types", [])
    return [{"id": i, "label": l, "icon": ic} for i, l, ic in BOT_TYPES] + mine


def add_type(label_: str) -> list[dict]:
    """A bot type the user names: a name only. What it's for is theirs to say in each bot's job."""
    lbl = " ".join(str(label_ or "").split())[:40]
    tid = _clean_name(lbl)
    if len(tid) < 2:
        raise ValueError("Give the type a name (letters and numbers).")
    if any(t["id"] == tid or t["label"].lower() == lbl.lower() for t in bot_types()):
        raise ValueError(f"There's already a bot type called {lbl}.")
    data = _read_json(p("types.json"), {})
    data.setdefault("types", []).append({"id": tid, "label": lbl, "icon": "robot", "custom": True})
    _write_json(p("types.json"), data)
    post("you", "type", f"new bot type: {lbl}")
    return bot_types()


def draft(ids: list) -> dict:
    """The design suite's step 2: a name and title from the picked bot types. The job is left for the user to write."""
    by = {t["id"]: t for t in bot_types()}
    picked = [by[i] for i in ids or [] if i in by]
    if not picked or len(picked) != len(ids):
        raise ValueError("Pick one or more bot types from the list.")
    return {"name": "_".join(t["id"] for t in picked)[:40], "title": " + ".join(t["label"] for t in picked), "job": "",
            "icon": picked[0]["icon"], "types": [t["id"] for t in picked]}


def services() -> list[dict]:
    """Every service, with unlocked, the bot found for each type it needs (in stage order), what's missing, and its tender."""
    reg = load_registry()["bots"]
    crew = [b for b in reg if approved(b) and not b.get("service")]
    out = []
    for s in SERVICES:
        members, missing = [], []
        for need in s["needs"]:
            b = next((b for b in crew if need in (b.get("types") or [])), None)
            if b:
                members.append({"type": need, "bot": b["name"]})
            else:
                missing.append(need)
        tender = next((b["name"] for b in reg if b.get("service") == s["id"] and b.get("status") != "retired"), None)
        out.append({**s, "unlocked": not missing, "members": members, "missing": missing, "tender": tender})
    return out


def open_service(sid: str, words: str) -> dict:
    """Open an unlocked service: make its tender bot, with the user's yes in their own words."""
    words = " ".join(str(words or "").split())
    if len(words) < 2:
        raise ValueError("Opening a service needs your yes, in your words.")
    s = next((x for x in services() if x["id"] == sid), None)
    if not s:
        raise ValueError(f"There's no service called {sid}.")
    if not s["unlocked"]:
        raise ValueError(f"{s['label']} is locked: it still needs a bot of type {', '.join(s['missing']).replace('_', ' ')}.")
    if s["tender"]:
        raise ValueError(f"{s['label']} is already open (its tender is {s['tender']}).")
    reg = load_registry()
    names = {b["name"] for b in reg["bots"]}
    name, n = f"{sid}_tender", 1
    while name in names:
        n += 1
        name = f"{sid}_tender{n}"
    entry = {"name": name, "label": "Service tender", "kind": "service", "service": sid, "prompt": "",
             "job": f"Runs the {s['label']} service: its bots in order ({' -> '.join(m['bot'] for m in s['members'])}), each reading what "
                    f"the earlier ones found, then writes the service's report: {s['goal']}.",
             "where": f"the {s['label']} service", "trigger": {}, "scope": {"level": "app"}, "writes": "nothing (it reports here)",
             "approved": {"words": words, "date": datetime.now().strftime("%m/%d/%Y")}, "status": "approved", "timeout_s": 3600}
    reg["bots"].append(entry)
    save_registry(reg)
    post("you", "service", f"{s['label']} opened: \"{words}\"; its tender is {name}")
    return bot(name)


def _stage_prompt(b: dict, svc: dict, i: int, n: int) -> str:
    role = "gather what the service needs" if i == 0 else "write the service's result" if i == n - 1 else "analyze what was gathered"
    return (b.get("prompt", "") + duties_prompt(b["name"]) + f"\n\nYou are stage {i + 1} of {n} of the {svc['label']} service, whose goal is: "
            f"{svc['goal']}. Your part: {role}, using your job above."
            + (" The file earlier_stages.md in your working folder holds what the earlier stages reported; read it first and build "
               "on it rather than repeating it." if i else "")
            + (" Write the result as the service's report: short sections, plain words, each point with the file it came from."
               if i == n - 1 else " Report what the next stage needs, briefly."))


def _service_run(t: dict) -> tuple[int, str, str, dict]:
    """A tender's run: each of the service's bots in turn, with its own permissions, from its own folder; each reads what
    the earlier ones reported. The answer is the service's report; every stage's tokens count toward the tender."""
    svc = next((s for s in services() if s["id"] == t["service"]), None)
    if not svc or not svc["unlocked"]:
        return 1, "", f"the service is locked: it needs a bot of type {', '.join((svc or {}).get('missing', ['?']))}", {}
    seen = list(dict.fromkeys(m["bot"] for m in svc["members"]))      # one bot may cover two types: it runs once
    earlier, toks, code = [], {}, 0
    for i, name in enumerate(seen):
        b = bot(name)
        with open(os.path.join(workspace(b), "earlier_stages.md"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(earlier) or "(you are the first stage)")
        t0 = time.time()
        code, answer, err, tk = _claude(b, _stage_prompt(b, svc, i, len(seen)), f"{svc['label']} service, stage {i + 1} of {len(seen)}",
                                        b.get("timeout_s", 900))
        for k in (*TOKEN_KEYS, "cost_usd"):
            toks[k] = toks.get(k, 0) + (tk.get(k) or 0)
        text = answer.strip() if code == 0 else f"(this stage failed, exit {code}) {answer.strip()}\n{err.strip()[-800:]}"
        earlier.append(f"## Stage {i + 1}: {name} ({time.time() - t0:.0f} s)\n\n{text}")
        if code:
            break
    report = (f"# {svc['label']} service report\n\n{datetime.now().strftime('%m/%d/%Y %H:%M')}. Goal: {svc['goal']}.\n"
              f"Stages: {' -> '.join(seen)}.\n\n" + "\n\n".join(earlier)
              + f"\n\n{svc['label']}: {len(earlier) - (1 if code else 0)} of {len(seen)} stages done.")
    return code, report, "", toks


WIZARD_SYSTEM = (
    "You are the Bot Wizard in the Bot design suite of Randis UDS. The user tells you in plain words what they want a bot "
    "to do, and you fill in the form beside you: which bot types it's made from, its name, its job, and how often it runs. "
    "New bots read and report only (the user can give one more later, on its card's Perms tab), so never promise more than "
    "that. Ask at most one short question at a time, in short plain words. Never make the bot yourself: the user makes it "
    "on the last step by typing their yes. You don't know what the user wants a bot for until they say it: never make up a "
    "job, and never guess what a bot type means. The job is the user's own words (tidied only for spelling); if they haven't "
    "said it yet, leave job empty and ask them. "
    "Reply with ONE JSON object and nothing else: {\"say\": what you say to the user, \"types\": [bot type ids from the list, "
    "or [] if it's too early to pick], \"name\": a short snake_case name or \"\", \"job\": the job in the user's own words, "
    "or \"\", \"every\": one of \"\", \"15\", \"60\", \"1440\" (minutes; \"\" means only when the user clicks Start now), "
    "\"step\": 1-4, the form step to show (4 once types, name and job are all settled)}.")


def wizard_ask(msgs: list, form: dict | None = None) -> dict:
    """The Bot Wizard: a chat beside the design suite's form that fills it in. msgs is the chat so far,
    [{who: "you"|"wizard", msg}]. Returns what the wizard says and the fields it filled in. It reads nothing and runs nothing."""
    cmd = ccode.command()
    if not cmd:
        raise ValueError("The wizard talks through Claude Code, which isn't installed on this computer (claude.com/claude-code).")
    types = bot_types()
    ids = {t["id"] for t in types}
    talk = "\n".join(f"{'User' if m.get('who') == 'you' else 'Wizard'}: {' '.join(str(m.get('msg', '')).split())}" for m in (msgs or [])[-20:])
    prompt = ("Bot types (id: name):\n" + "\n".join(f"{t['id']}: {t['label']}" for t in types)
              + f"\n\nThe form right now: {json.dumps(form or {})}\n\nThe chat so far (oldest first):\n{talk}\n\nYour JSON reply:")
    os.makedirs(workspaces(), exist_ok=True)
    try:
        res = subprocess.run([*cmd, "-p", "--output-format", "text", "--tools", "", "--permission-mode", "dontAsk", "--no-session-persistence",
                              "--setting-sources", "project", "--strict-mcp-config", "--append-system-prompt", WIZARD_SYSTEM],
                             input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=workspaces(),
                             timeout=240, env=clean_env(), creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise ValueError("The wizard took longer than 4 minutes and was stopped. Try again.")
    out = res.stdout or ""
    a, b = out.find("{"), out.rfind("}")
    try:
        r = json.loads(out[a:b + 1]) if a >= 0 < b else {}
    except ValueError:
        r = {}
    if not isinstance(r, dict) or not r.get("say"):
        return {"say": out.strip() or f"(The wizard said nothing. {(res.stderr or '').strip()[:200]})", "types": [], "name": "", "job": "",
                "every": None, "step": None}
    every, step = str(r.get("every") or ""), r.get("step")
    return {"say": str(r["say"]), "types": [t for t in (r.get("types") or []) if t in ids], "name": _clean_name(r.get("name")),
            "job": " ".join(str(r.get("job") or "").split()), "every": every if every in ("", "15", "60", "1440") else None,
            "step": max(1, min(4, int(step))) if isinstance(step, (int, float)) else None}


def design(spec: dict, reads_dir: str, where: str) -> dict:
    """The design suite's last step: make the bot from its types, name, job and how often, with the user's yes in their words."""
    spec = spec or {}
    yes = " ".join(str(spec.get("yes") or "").split())
    if len(yes) < 2:
        raise ValueError("Type your yes for this bot, in your own words.")
    every = spec.get("every_min")
    every = int(every) if every not in (None, "", "0", 0) else None
    d = draft(list(spec.get("types") or []))
    return add_bot(spec.get("job", ""), reads_dir, where, {"level": "app"}, every, d["title"], spec.get("name") or d["name"], d["types"], yes)


def group_members() -> list[str]:
    """Who answers in Chat with all bots: every bot on duty (not retired)."""
    return [b["name"] for b in load_registry()["bots"] if approved(b)]


_SCAN = {"t": 0.0, "rows": []}


def view() -> dict:
    """Everything the Bots tab draws, in one call. The program scan lists every process on the computer, so it runs at
    most every 20 seconds."""
    if time.time() - _SCAN["t"] > 20:
        try:
            _SCAN.update(t=time.time(), rows=scan_procs())
        except Exception:
            _SCAN.update(t=time.time(), rows=[])
    bots_ = overview()
    names = [b["name"] for b in bots_]
    return {"bots": bots_, "max_parallel": MAX_PARALLEL, "paused": paused(), "usage": usage_rows(),
            "chats": {n: chat_log(n)[-60:] for n in names}, "duties": {n: duties(n) for n in names},
            "card_tabs": {n: card_tabs(n) for n in names}, "procs": _SCAN["rows"],
            "proc_chats": {n: proc_chat(n)[-30:] for n in names},
            "proc_open": {n: [q.get("pid") for q in open_questions(n)] for n in names},
            "groups": {"all": {"log": group_log()[-60:], "members": group_members(), "waiting": group_waiting()}},
            "types": bot_types(), "services": services(),
            "perms": {"features": [{"id": k, "label": l, "about": a} for k, l, a, *_ in PERM_FEATURES], "levels": PERM_LEVELS,
                      "holdbacks": [{"id": k, "label": l, "about": a} for k, l, a, *_ in HOLDBACKS],
                      "default": perms_of({}), "bots": [{"name": b["name"], "perms": b["perms"]} for b in bots_]}}


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "_exec":                                 # argv[4], the label, is only there to show in the command line
        _loop(argv[2], argv[3] == "once")
        return 0
    if cmd == "list":
        for o in overview():
            st = o["state"]
            print(f"{o['id']} {o['name']:16} {o['status']:9} {'RUNNING' if o['running'] else 'idle':8} runs {st.get('runs', 0)}, "
                  f"last {st.get('last_end', '-')}: {st.get('last_summary', '')}")
        return 0
    if cmd == "leftovers":
        rows = [x for x in scan_procs() if x["leftover"]]
        for x in rows:
            print(f"{x['pid']} {x['name']}: {x['label']} (bot {x['bot']})")
        print(f"{len(rows)} leftover program{'s' if len(rows) != 1 else ''}.")
        return 0
    if cmd == "ask" and len(argv) > 2:
        try:
            print(proc_ask(int(argv[2]), by=os.environ.get("UDS_BOT_NAME") or "you")["text"])
        except (KeyError, ValueError) as e:
            print(str(e).strip("'\""))
            return 1
        return 0
    if cmd == "run" and len(argv) > 2:
        reason = why_not(argv[2])
        if reason:
            print("Not run:", reason)
            return 1
        r = run_once(argv[2])
        print(r)
        return 0 if r["exit"] == 0 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
