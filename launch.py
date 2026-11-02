# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python launch.py   (what the shortcuts open)
"""Runs first and watches the app start. About 1 start in 14-25 used to stall on a cut-off file; that's random, and a new start clears it.
The app's page says when it has really come up (Api.page_ready). No word in time: close that copy and start another, waiting longer each time.
The last try is never closed, so a slow PC is never locked out. A WORKAROUND: why the stall happens isn't known. Standard library only, so
this file still runs if the app's own packages are broken. Every start goes in data/launch.log, so the real stall rate can be read off."""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TRIES = (15, 30, 90)      # seconds to wait on each try; a normal start here is well under the first (launch_test prints it)
LOG_LINES = 300
NO_WINDOW = 0x08000000
DETACHED = 0x00000008


def write_log(path, text):
    """Keeps the last few hundred lines. A log that can't be written never stops the app starting."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        lines.append(time.strftime("%Y-%m-%d %H:%M:%S ") + text)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-LOG_LINES:]) + "\n")
    except OSError:
        pass


def kill_tree(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, creationflags=NO_WINDOW)
        return
    import signal
    try:
        os.killpg(pid, signal.SIGKILL)        # the app runs in its own session, so this ends it and what it started
    except OSError:
        pass


def message_box(text):
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, text, "Randis UDS", 0x40)
        return
    for cmd in (["zenity", "--info", "--title=Randis UDS", "--text=" + text], ["notify-send", "Randis UDS", text]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=600)
            return
        except (OSError, subprocess.TimeoutExpired):
            continue
    print("Randis UDS: " + text, file=sys.stderr)


def detached():
    """How a started copy is cut loose from this one: no console window on Windows, its own session elsewhere."""
    return {"creationflags": DETACHED | NO_WINDOW} if os.name == "nt" else {"start_new_session": True}


def watch(cmd, cwd, env, tries=TRIES, log=lambda text: None, say=message_box, poll=0.1):
    """Starts cmd until its page reports in. Returns what happened: ready, problems, closed, crashed or slow."""
    fd, ready = tempfile.mkstemp(prefix="uds_ready_")
    os.close(fd)
    try:
        for number, limit in enumerate(tries, 1):
            last = number == len(tries)
            if os.path.exists(ready):
                os.remove(ready)
            began = time.time()
            child = subprocess.Popen(cmd, cwd=cwd, env=dict(env, UDS_READY_FILE=ready), **detached())
            why = None
            while why is None:
                time.sleep(poll)
                took = time.time() - began
                if os.path.exists(ready):
                    try:
                        with open(ready, encoding="utf-8") as f:
                            problems = json.load(f)
                    except ValueError:         # caught mid-write
                        continue
                    if not problems:
                        log(f"try {number}: ready in {took:.1f} s (pid {child.pid})")
                        return "ready"
                    why = f"page reported script errors after {took:.1f} s: {str(problems)[:300]}"
                    if last:
                        log(f"try {number}: {why}; left open")
                        return "problems"
                elif child.poll() is not None:
                    if child.returncode == 0:      # the user closed it
                        log(f"try {number}: closed after {took:.1f} s, before the page came up")
                        return "closed"
                    why = f"stopped with code {child.returncode} after {took:.1f} s"
                    if last:
                        log(f"try {number}: {why}; giving up")
                        say("Randis UDS couldn't start after " + str(len(tries)) + " tries. Try opening it again.\n\nDetails: " + os.path.join("data", "launch.log"))
                        return "crashed"
                elif took > limit:
                    why = f"no word after {limit} s"
                    if last:
                        log(f"try {number}: {why}; left open")
                        say("Randis UDS is taking a long time to start. It's been left open. If it never comes up, close it and open it again.")
                        return "slow"
            log(f"try {number}: {why}; starting again")
            kill_tree(child.pid)
    finally:
        try:
            os.remove(ready)
        except OSError:
            pass


def gui_python():
    """pythonw (no console window) next to this Python, if there is one."""
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


def main():
    log_file = os.path.join(HERE, "data", "launch.log")
    tries = tuple(float(s) for s in os.environ["UDS_LAUNCH_TRIES"].split(",")) if os.environ.get("UDS_LAUNCH_TRIES") else TRIES
    return watch([gui_python(), os.path.join(HERE, "app.py")], HERE, dict(os.environ), tries, lambda text: write_log(log_file, text))


if __name__ == "__main__":
    main()
