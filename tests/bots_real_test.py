# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""One real bot run with your own Claude Code (a few seconds of your Claude plan): it answers, and it leaves nothing
anywhere another Claude Code session reads. Compares every file under ~/.claude before and after the run; Claude Code's
own backups and debug logs are allowed, and so is an empty folder keyed to the bot's own workspace.
Run: python tests/bots_real_test.py"""
import json, os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TOP = tempfile.mkdtemp(prefix="uds_bots_real_")
READS = os.path.join(TOP, "folder")
os.makedirs(READS)
with open(os.path.join(READS, "hello.txt"), "w") as f:
    f.write("The secret word is pineapple.\n")
os.environ["UDS_BOTS_DIR"] = os.path.join(TOP, "bots")
os.environ.pop("UDS_CLAUDE_CMD", None)
os.environ.pop("UDS_BOT_WORKSPACES", None)
import bots
import ccode

CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:900]}]" if not ok else ""), flush=True)


def snap():
    files, dirs = {}, set()
    for d, ds, fs in os.walk(CLAUDE):
        ds[:] = [x for x in ds if x not in ("node_modules", "plugins", "cache", "statsig", "telemetry")]
        dirs.add(d)
        for f in fs:
            try:
                files[os.path.join(d, f)] = os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return files, dirs


def history():
    try:
        return [json.loads(x) for x in open(os.path.join(CLAUDE, "history.jsonl"), encoding="utf-8") if x.strip()]
    except (OSError, ValueError):
        return []


if not ccode.command():
    print("Claude Code isn't installed; nothing to test.")
    sys.exit(1)
b = bots.add_bot("Read hello.txt and reply with only the secret word in it.", READS, "a test", {"level": "app", "tab_kind": "realtest"})
ws = os.path.join(bots.workspaces(), b["name"])
own = os.path.join(CLAUDE, "projects", "".join(c if c.isalnum() else "-" for c in ws))
if os.path.isdir(own) and not any(fs for _, _, fs in os.walk(own)):
    shutil.rmtree(own)
before, dirs0 = snap()
hist0 = len(history())
t0 = time.time()
r = bots.run_once(b["name"])
after, dirs1 = snap()
check("the real bot ran, read the file, and answered", r["exit"] == 0 and "pineapple" in r["summary"].lower(), r)
ok_new = (os.path.join(CLAUDE, "backups") + os.sep, os.path.join(CLAUDE, "debug") + os.sep)
leaks = [f for f in after if f not in before and not f.startswith(ok_new)]
check("no new file anywhere a session reads", not leaks, leaks)
stray = [d for d in dirs1 - dirs0 if not (d == own or d.startswith(own + os.sep) or d.startswith(ok_new))]
check("no new folder but the bot's own, and it's empty", not stray and not [f for f in after if f.startswith(own + os.sep)], stray)
mine = [x for x in history()[hist0:] if "secret word" in str(x.get("display", "")) or b["name"] in str(x.get("project", ""))]
check("its job isn't in the shared prompt history", not mine, mine)
print(f"   ({round(time.time() - t0)} s; workspace {ws})")
shutil.rmtree(ws, ignore_errors=True)
if os.path.isdir(own) and not any(fs for _, _, fs in os.walk(own)):
    shutil.rmtree(own)
shutil.rmtree(TOP, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
