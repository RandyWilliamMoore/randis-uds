# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""First start and the Claude Code terminal link: the popup, the history hook, undo, the shortcut's taskbar identity, the guides."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = tempfile.mkdtemp(prefix="uds_first_run_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_TEST_FIRST_RUN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_KEYS_DIR=os.path.join(TOP, "keys"))
os.environ.pop("UDS_IN_APP", None)
sys.path.insert(0, APP)
import webview
import app
import ccode
import cli_setup
import projects

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


# ---- the guides a stranger gets
for name in ("CLAUDE.md", "CLAUDE_CODE_SETUP.md"):
    text = open(os.path.join(APP, name), encoding="utf-8").read()
    check(f"{name} attributes in its first lines", "Randy Moore" in text[:200] and "ko-fi.com" in text[:300])
guide = open(os.path.join(APP, "CLAUDE_CODE_SETUP.md"), encoding="utf-8").read()
for piece in ("irm https://claude.ai/install.ps1 | iex", "free plan doesn't", "/login", "trust this folder", "restore.py --undo-last", "PATH"):
    check(f"the guide covers: {piece}", piece in guide)
start = open(os.path.join(APP, "CLAUDE.md"), encoding="utf-8").read()
check("CLAUDE.md starts Claude on setup and names its finish line", "Setup comes first" in start and "data/claude_setup.json" in start)
settings = json.load(open(os.path.join(APP, ".claude", "settings.json"), encoding="utf-8"))
check("the folder starts Claude Code able to edit, asking for the rest", settings["permissions"]["defaultMode"] == "acceptEdits")

# ---- the hook file keeps what's already there
root = os.path.join(TOP, "hookroot")
os.makedirs(os.path.join(root, ".claude"))
with open(os.path.join(root, ".claude", "settings.local.json"), "w", encoding="utf-8") as f:
    json.dump({"permissions": {"allow": ["Bash(git status)"]}, "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "mine"}]}]}}, f)
check("the hook gets written", cli_setup.write_hook(root))
cli_setup.write_hook(root)
s = json.load(open(os.path.join(root, ".claude", "settings.local.json"), encoding="utf-8"))
flat = [h for g in s["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
check("the user's own settings and hooks stay", s["permissions"]["allow"] == ["Bash(git status)"] and any(h["command"] == "mine" for h in flat), s)
own = [h for h in flat if "cli_history.py" in " ".join(h.get("args", []))]
check("writing twice leaves one copy of ours", len(own) == 1, flat)
check("it runs this Python directly, needing no shell", os.path.exists(own[0]["command"]) and own[0]["args"][0].endswith("/cli_history.py"), own)
bad = os.path.join(TOP, "badroot")
os.makedirs(os.path.join(bad, ".claude"))
with open(os.path.join(bad, ".claude", "settings.local.json"), "w") as f:
    f.write("{not json")
check("an unreadable settings file is left alone", cli_setup.write_hook(bad) is False and open(os.path.join(bad, ".claude", "settings.local.json")).read() == "{not json")

# ---- history for a turn in a terminal, on a copy of the code
copy = os.path.join(TOP, "copy")
os.makedirs(os.path.join(copy, "data"))
for n in ("cli_history.py", "restore.py", "snapshots.py"):
    shutil.copy(os.path.join(APP, n), copy)
page = os.path.join(copy, "page.txt")
with open(page, "w") as f:
    f.write("before")


def hook(payload='{"prompt": "change the page"}', **env):
    return subprocess.run([sys.executable, os.path.join(copy, "cli_history.py")], input=payload, capture_output=True, text=True, env={**os.environ, **env}, cwd=TOP)


r = hook()
check("the hook runs quietly", r.returncode == 0 and not r.stdout.strip() and not r.stderr.strip(), r.stdout + r.stderr)
with open(page, "w") as f:
    f.write("after")
with open(os.path.join(copy, "new.txt"), "w") as f:
    f.write("new")
r = subprocess.run([sys.executable, "restore.py", "--undo-last"], cwd=copy, capture_output=True, text=True)
check("restore.py undoes a terminal turn", open(page).read() == "before" and not os.path.exists(os.path.join(copy, "new.txt")), r.stdout + r.stderr)
r = subprocess.run([sys.executable, "restore.py"], cwd=copy, capture_output=True, text=True)
check("restore.py lists it with what was asked", "change the page" in r.stdout, r.stdout + r.stderr)
count = len(open(os.path.join(copy, "data", "claude_code_log.jsonl")).readlines())
hook(UDS_IN_APP="1")
check("a chat inside the app adds no terminal snapshot", len(open(os.path.join(copy, "data", "claude_code_log.jsonl")).readlines()) == count)
check("the app's Claude Code runs are marked", ccode.child_env().get("UDS_IN_APP") == "1")
r = hook(payload="not json")
check("odd input still saves a snapshot", r.returncode == 0 and not r.stdout.strip(), r.stdout + r.stderr)
shutil.rmtree(os.path.join(copy, "data", "snapshots"))
with open(os.path.join(copy, "data", "snapshots"), "w") as f:
    f.write("in the way")
r = hook()
check("a failed snapshot doesn't block the prompt, and says so", r.returncode == 0 and "no snapshot" in r.stdout, r.stdout + r.stderr)

# ---- the shortcut's taskbar identity, on a real .lnk
lnk = os.path.join(TOP, "t.lnk")
subprocess.run(["powershell", "-NoProfile", "-Command", f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{sys.executable}';$s.Save()"], check=True, capture_output=True)
check("a new shortcut has no identity", cli_setup.get_app_id(lnk) is None, cli_setup.get_app_id(lnk))
cli_setup.set_app_id(lnk, "RandisUDS.Base")
check("the shortcut carries the window's identity", cli_setup.get_app_id(lnk) == "RandisUDS.Base", cli_setup.get_app_id(lnk))
check("a source copy isn't taken for an install", cli_setup.installed_here(os.path.join(TOP, "copy")) is False)

# ---- instructions stay off the command line, tried through a real .cmd
stub_dir = os.path.join(TOP, "stub")
os.makedirs(stub_dir)
stub = os.path.join(stub_dir, "claude.cmd")
with open(stub, "w") as f:
    f.write("@echo %*> args.txt\n@more > stdin.txt\n")
os.environ["UDS_CLAUDE_CMD"] = json.dumps([stub])
payload = 'open file text "&echo hacked>ESCAPED.txt&rem '
turn = ccode.ClaudeCode({"cwd": stub_dir, "mode": "acceptEdits"})
job = type("J", (), {"stop": False, "status": "", "proc": None, "text": "", "extra": {}})()
try:
    turn._turn([{"role": "system", "content": payload}, {"role": "user", "content": "hello"}], job, {"save_session": lambda s: None}, None)
except Exception:
    pass                     # the stand-in gives no reply; only what it was handed matters here
del os.environ["UDS_CLAUDE_CMD"]
args = open(os.path.join(stub_dir, "args.txt"), errors="replace").read()
given = open(os.path.join(stub_dir, "stdin.txt"), errors="replace").read()
check("a file's text never reaches the command line", "open file text" not in args and "--append-system-prompt" in args, args[:200])
check("it arrives on stdin instead", payload in given and "hello" in given, given[:200])
check("nothing escaped into a command", not os.path.exists(os.path.join(stub_dir, "ESCAPED.txt")))
check("what's left on the command line has no quote to break out with", '"' not in ccode.SYSTEM.format(cwd=stub_dir))

# ---- the popup, in the real page
calls = []
real_create, real_start, real_action = webview.create_window, webview.start, app.Api.setup_action
windows = []
app.Api.setup_action = lambda self, which: calls.append(which) or True
app.Api.setup_info = (lambda f: lambda self: {**f(self), "shortcut": True})(app.Api.setup_info)
projects_name = projects.name_of
projects.name_of = lambda r: "Base"


def hidden_create(*a, **k):
    k["hidden"] = True
    w = real_create(*a, **k)
    windows.append(w)
    return w


def fake_start(func=None, *a, **k):
    def run():
        func()
        try:
            checks(windows[0])
        except Exception as e:
            check("test crashed", False, repr(e)[:300])
        finally:
            windows[0].destroy()
    real_start(run, *a, **k)


def checks(w):
    def js(s):
        return w.evaluate_js(s)

    def until(cond, secs=25):
        end = time.time() + secs
        while time.time() < end:
            try:
                if js(cond):
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False
    body = "document.querySelector('#modal .modal-body').innerText"
    click = lambda act: js(f"document.querySelector('#modal [data-act={act}]').click()")
    check("a new install opens the setup window", until("!document.getElementById('modal').hidden"))
    check("it offers the taskbar pin, and says Windows keeps that for the user", until(f"{body}.includes('Pin it to your taskbar') && {body}.includes('Windows only lets you')"), js(body))
    click("setup-pin")
    check("Show me the icon goes to the shortcut", until("true") and "pin" in calls, calls)
    # Claude Code found
    real_version = ccode.version
    ccode.version = lambda: "9.9.9 (Claude Code)"
    click("setup-pin")
    js("showSetup()")
    check("found: it says so, with the folder", until(f"{body}.includes('Found 9.9.9') && {body}.includes('It\\'s ready for this folder')") and app.HERE in js(body), js(body))
    check("found: it says what comes next", "Please set up Randis UDS" in js(body) and "sign in" in js(body), js(body))
    click("setup-claude")
    click("setup-guide")
    check("found: its buttons work", until("true") and "claude" in calls and "guide" in calls, calls)
    # not found
    def none():
        raise ValueError("no")
    ccode.version = none
    js("showSetup()")
    check("missing: it says so and what you need", until(f"{body}.includes('isn\\'t on this computer') && {body}.includes('free plan')"), js(body))
    click("setup-install")
    check("missing: Install runs from the button", until("true") and "install" in calls, calls)
    ccode.version = lambda: "9.9.9 (Claude Code)"
    click("setup-recheck")
    check("missing: Check again finds it", until(f"{body}.includes('Found 9.9.9')"), js(body))
    ccode.version = real_version
    click("setup-close")
    check("Done closes it", until("document.getElementById('modal').hidden"))
    check("the welcome page can bring it back", js("!!document.querySelector('.pane:not([hidden]) [data-act=setup-help]')"))
    js("document.querySelector('.pane:not([hidden]) [data-act=setup-help]').click()")
    check("and does", until("!document.getElementById('modal').hidden"))
    check("no script errors", not js("(window.__errs || []).length"))
    # file drops
    from System import Func, Boolean
    allowed = w.native.Invoke(Func[Boolean](lambda: w.native.browser.webview.AllowExternalDrop))
    check("the window refuses files dropped from outside", allowed is False or str(allowed) == "False", allowed)
    drop = """(() => { const d = new DataTransfer(); %s; const e = new DragEvent('%s', {bubbles: true, cancelable: true, dataTransfer: d});
              document.body.dispatchEvent(e); return e.defaultPrevented; })()"""
    with_file = "d.items.add(new File(['x'], 'x.html', {type: 'text/html'}))"
    check("the page stops a dropped file", js(drop % (with_file, "drop")) is True)
    check("the page stops a file dragged over it", js(drop % (with_file, "dragover")) is True)
    check("dragging text still works", js(drop % ("d.setData('text/plain', 'x')", "drop")) is False)


webview.create_window, webview.start = hidden_create, fake_start
app.main()
webview.create_window, webview.start = real_create, real_start
app.Api.setup_action = real_action

api = app.Api()
check("the second start shows nothing", api.first_run() is False)
os.remove(os.path.join(D, "first_run.json"))
with open(app.SESSION_FILE, "w") as f:
    f.write("{}")
check("a copy that's been used shows nothing", api.first_run() is False)
os.remove(os.path.join(D, "first_run.json"))
os.remove(app.SESSION_FILE)
projects.name_of = lambda r: "Some project"
check("a project shows nothing", api.first_run() is False)
projects.name_of = projects_name
os.environ.pop("UDS_TEST_FIRST_RUN")
check("other tests' windows stay clear", api.first_run() is False)

shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
