# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS: bots. Small background helpers you add with "+ Add a bot", for one tab or for the app.

A bot is a Claude Code run (your own installed Claude Code, `claude -p`) with one job, the words you typed. New bots read
and report only: they can read one folder (the tab's, or the app's) and search it, and can't change anything. Each run is
its own background process with its own log; every message goes on the bus, one line per message in data/bots/bus/<date>.jsonl,
and the Bots tab shows them, with today's record.

Every Claude Code bot runs on its own: from its own folder in your app-data folder (no CLAUDE.md above it), with no saved
session, no user settings or hooks, no connectors, only the read tools, and none of the calling session's Claude variables.
At most MAX_PARALLEL bots run at once, and none start when free memory is low. Bots stop when Randis UDS closes.

  python bots.py list               every bot, its status and last result
  python bots.py run NAME           one run now, waiting for it
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import ccode

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_PARALLEL = 2
MIN_FREE_GB = 1.0
READ_TOOLS = ["Read", "Grep", "Glob"]
EVERY_CHOICES = (None, 15, 60, 1440)
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
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------- registry and state
def load_registry() -> dict:
    try:
        with open(p("registry.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"bots": []}


def save_registry(reg: dict) -> None:
    _write_json(p("registry.json"), reg)


def bot(name: str) -> dict:
    for b in load_registry()["bots"]:
        if b["name"] == name:
            return b
    raise KeyError(f"There's no bot named {name}.")


def approved(b: dict) -> bool:
    a = b.get("approved") or {}
    return b.get("status") == "approved" and bool(a.get("words")) and bool(a.get("date"))


def read_state(name: str) -> dict:
    try:
        with open(p("state", f"{name}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_state(name: str, **kw) -> dict:
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
    os.makedirs(p("bus"), exist_ok=True)
    with open(p("bus", datetime.now().strftime("%Y-%m-%d") + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def read_bus(day: str | None = None, last: int | None = None) -> list[dict]:
    day = day or datetime.now().strftime("%Y-%m-%d")
    rows = []
    try:
        with open(p("bus", day + ".jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows[-last:] if last else rows


def record(day: str | None = None) -> dict:
    """Today's record, from the bus: runs and failures per bot, and what needs a look."""
    rows = read_bus(day)
    per = {}
    for r in rows:
        if r.get("kind") in ("result", "failure", "skipped"):
            b = per.setdefault(r.get("from", "?"), {"runs": 0, "failed": 0, "skipped": 0, "last": ""})
            b["runs" if r["kind"] != "skipped" else "skipped"] += 1
            b["failed"] += r["kind"] == "failure"
            b["last"] = f"{r.get('ts', '')[11:16]} {r.get('text', '')}"
    look = [f"{r.get('ts', '')[11:16]} {r.get('from')}: {r.get('text')}" for r in rows if r.get("kind") in ("failure", "refused")]
    return {"messages": len(rows), "bots": per, "look": look}


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


def why_not(name: str, scheduled: bool = False) -> str | None:
    """None if the bot may run now; otherwise why not, in plain words."""
    b = bot(name)
    if not approved(b):
        return "it's retired" if b.get("status") == "retired" else "it has no yes from you"
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


# ---------------------------------------------------------------- running
def clean_env() -> dict:
    """This environment minus anything that ties a child to a Claude Code session, so a bot can't reach another one."""
    env = {k: v for k, v in os.environ.items()          # CLAUDE_CONFIG_DIR stays: it says where the user's own sign-in is
           if not ((k.startswith("CLAUDE") and k != "CLAUDE_CONFIG_DIR") or "cc-msg" in v)}
    env["UDS_BOTS_DIR"] = home()
    return env


def workspace(b: dict) -> str:
    d = os.path.join(workspaces(), b["name"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write(f"# Bot: {b['name']}\n\nYou are a small background bot inside Randis UDS, added by its user.\n"
                f"Your one job: {b['job']}\n\nDo only that job. You can read and search, and you can't change anything. "
                "Answer in a few short plain lines; your answer is shown in the app's Bots tab.\n")
    return d


def claude_cmd(b: dict) -> list[str]:
    cmd = list(ccode.command() or ["claude"]) + [
        "-p", "--no-session-persistence", "--setting-sources", "project", "--strict-mcp-config",
        "--permission-mode", "dontAsk", "--output-format", "text", "--allowedTools", *READ_TOOLS]
    if b.get("reads_dir"):
        cmd += ["--add-dir", b["reads_dir"]]
    return cmd


def run_once(name: str) -> dict:
    """One run of the bot, in this process. Returns {exit, summary, seconds}."""
    b = bot(name)
    os.makedirs(p("logs", name), exist_ok=True)
    log = p("logs", name, datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".log")
    t0 = time.time()
    write_state(name, last_start=now(), last_log=log)
    try:
        r = subprocess.run(claude_cmd(b), input=b["prompt"], cwd=workspace(b), env=clean_env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=b.get("timeout_s", 900), creationflags=NO_WINDOW)
        code, out = r.returncode, (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
    except subprocess.TimeoutExpired as e:
        code, out = -1, f"timed out after {b.get('timeout_s', 900)} s\n{e.stdout or ''}"
    except OSError as e:
        code, out = -1, f"Claude Code didn't start: {e}"
    with open(log, "w", encoding="utf-8") as f:
        f.write(out)
    lines = [x.strip() for x in out.split("[stderr]")[0].splitlines() if x.strip()]
    if code != 0 and not lines:
        lines = [x.strip() for x in out.splitlines() if x.strip() and x.strip() != "[stderr]"]
    summary = (lines[-1] if lines else "(no answer)")[:300]
    secs = round(time.time() - t0, 1)
    st = read_state(name)
    write_state(name, last_end=now(), last_exit=code, last_summary=summary, last_answer=out.split("[stderr]")[0].strip()[:4000],
                runs=st.get("runs", 0) + 1, fails=st.get("fails", 0) + (code != 0), last_seconds=secs)
    post(name, "result" if code == 0 else "failure", summary, {"exit": code, "seconds": secs})
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


def launch(name: str, once: bool = True) -> dict:
    """Start a bot in its own background process. Refuses, with the reason, when a guard says no."""
    reason = why_not(name)
    if reason:
        post("bots", "refused", f"{name} didn't start: {reason}")
        return {"started": False, "reason": reason}
    if os.path.exists(p("state", f"{name}.stop")):
        os.remove(p("state", f"{name}.stop"))
    kw = {"creationflags": DETACHED | NO_WINDOW} if WIN else {"start_new_session": True}
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_exec", name, "once" if once else "schedule"],
                            cwd=HERE, env=clean_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **kw)
    write_state(name, pid=proc.pid, mode="once" if once else "schedule", started=now())
    post("bots", "started", f"{name} started ({'one run' if once else 'on its schedule'})")
    return {"started": True, "pid": proc.pid}


def halt(name: str, why: str = "") -> dict:
    st = read_state(name)
    os.makedirs(p("state"), exist_ok=True)
    open(p("state", f"{name}.stop"), "w").close()
    killed = False
    if pid_alive(st.get("pid")):
        if WIN:
            subprocess.run(["taskkill", "/PID", str(st["pid"]), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        else:
            try:
                os.killpg(int(st["pid"]), 15)
            except OSError:
                pass
        killed = True
    write_state(name, pid=None, next_due=None)
    if os.path.exists(p("state", f"{name}.stop")):
        os.remove(p("state", f"{name}.stop"))
    if killed or why:
        post("bots", "stopped", f"{name} stopped" + (f" ({why})" if why else ""))
    return {"stopped": True, "killed": killed}


def stop_all(why: str) -> int:
    n = 0
    for b in load_registry()["bots"]:
        if running(b["name"]):
            halt(b["name"], why)
            n += 1
    return n


def retire(name: str) -> dict:
    reg = load_registry()
    for b in reg["bots"]:
        if b["name"] == name:
            b["status"] = "retired"
            save_registry(reg)
            if running(name):
                halt(name, "retired")
            post("bots", "retired", f"{name} retired")
            return b
    raise KeyError(f"There's no bot named {name}.")


# ---------------------------------------------------------------- adding a bot
def add_bot(words: str, reads_dir: str, where: str, scope: dict, every_min=None, label: str = "") -> dict:
    """"+ Add a bot": what the person typed is the bot's job and their yes. A new bot reads and reports only."""
    words = " ".join(str(words or "").split())
    if len(words) < 8:
        raise ValueError("Say what the bot should do (a sentence is enough).")
    if len(words) > 2000:
        raise ValueError("That's long for one bot's job. Keep it under 2000 characters.")
    if every_min not in EVERY_CHOICES:
        raise ValueError("How often must be: when you click Run once, every 15 minutes, every hour, or once a day.")
    if not reads_dir or not os.path.isdir(reads_dir):
        raise ValueError("The folder this bot would read isn't there.")
    if not ccode.command():
        raise ValueError("Bots run on Claude Code, which isn't installed on this computer. Install it from claude.com/claude-code, "
                         "sign in once in a terminal, then try again.")
    reg = load_registry()
    names = {b["name"] for b in reg["bots"]}
    label = " ".join(str(label or "").split())[:40]
    slug = lambda x, k: re.sub(r"[^a-z0-9]+", "_", str(x or "").lower()).strip("_")[:k]
    base = slug(scope.get("tab_title"), 24) or slug(scope.get("tab_kind"), 20) or "app"
    kind = slug(label, 20) or "bot"                   # e.g. randis_sound_forge_bug_hunter1
    n = 1
    while f"{base}_{kind}{n}" in names:
        n += 1
    name = f"{base}_{kind}{n}"
    prompt = (f"You are a bot the user added for {where}. You may read the folder {reads_dir}.\n"
              f"The user's words, your job: {words}\n"
              "You can read and search files but you can't change anything. Do the job by reading and checking, then report "
              "in a few short plain lines. End with one line on its own that sums up what you found.")
    entry = {"name": name, "label": label, "job": words, "where": where, "kind": "claude", "prompt": prompt, "tools": list(READ_TOOLS),
             "reads_dir": os.path.abspath(reads_dir), "trigger": {"every_min": every_min} if every_min else {},
             "scope": scope, "writes": "nothing (it reports here)",
             "approved": {"words": words, "date": datetime.now().strftime("%m/%d/%Y")},
             "status": "approved", "timeout_s": 900}
    reg["bots"].append(entry)
    save_registry(reg)
    post("bots", "added", f"{name} added for {where}: \"{words}\"")
    return entry


def overview() -> list[dict]:
    out = []
    for b in load_registry()["bots"]:
        st = read_state(b["name"])
        out.append({**{k: b.get(k) for k in ("name", "label", "job", "where", "kind", "trigger", "status", "approved", "reads_dir", "writes", "scope")},
                    "running": pid_alive(st.get("pid")), "state": st})
    return out


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "_exec":
        _loop(argv[2], argv[3] == "once")
        return 0
    if cmd == "list":
        for o in overview():
            st = o["state"]
            print(f"{o['name']:16} {o['status']:9} {'RUNNING' if o['running'] else 'idle':8} runs {st.get('runs', 0)}, "
                  f"last {st.get('last_end', '-')}: {st.get('last_summary', '')}")
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
