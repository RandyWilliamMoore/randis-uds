# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/launch_test.py   (hidden windows only, on a throwaway copy)
"""launch.py, the watcher that restarts a stalled start. First stand-in apps that stall, crash or get closed, then the real app in a hidden
window with app.js cut off the way the real failure cuts it, mended while the first copy sits dead."""
import json, os, shutil, stat, subprocess, sys, tempfile, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import launch

TOP = tempfile.mkdtemp(prefix="uds_launch_")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""), flush=True)

# A stand-in app. It counts its starts; its behavior per start comes from the plan. It also starts a helper, as the real app starts WebView2.
FAKE = r"""
import json, os, subprocess, sys, time
top, plan = sys.argv[1], sys.argv[2].split(",")
n = len([f for f in os.listdir(top) if f.startswith("start_")])
open(os.path.join(top, f"start_{n}"), "w").write(str(os.getpid()))
act = plan[min(n, len(plan) - 1)]
helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open(os.path.join(top, f"helper_{n}"), "w").write(str(helper.pid))
def ready(v):
    with open(os.environ["UDS_READY_FILE"] + ".t", "w") as f: json.dump(v, f)
    os.replace(os.environ["UDS_READY_FILE"] + ".t", os.environ["UDS_READY_FILE"])
if act == "ok": ready([])
elif act == "bad": ready(["app.js SyntaxError"])
elif act == "crash": helper.kill(); sys.exit(3)
elif act == "closed": helper.kill(); sys.exit(0)
elif act == "env": open(os.path.join(top, "env"), "w").write(os.environ.get("KEEP_ME", ""))
if act == "env": ready([])
time.sleep(120)   # stays open, or hangs: "stall" does nothing else
"""
fake = os.path.join(TOP, "fake.py")
open(fake, "w").write(FAKE)


def alive(pid):
    return launch.subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=launch.NO_WINDOW).stdout.count(str(pid)) > 0


def read_pid(folder, name):
    with open(os.path.join(folder, name)) as f:
        return int(f.read())


def scene(name, plan, tries=(1.5, 2.5, 3)):
    folder = os.path.join(TOP, name)
    os.makedirs(folder)
    said, logged = [], []
    env = dict(os.environ, KEEP_ME="kept")
    got = launch.watch([sys.executable, fake, folder, plan], folder, env, tries, logged.append, said.append)
    starts = len([f for f in os.listdir(folder) if f.startswith("start_")])
    return got, starts, said, logged, folder


def clean(folder):
    for f in os.listdir(folder):
        if f.startswith(("start_", "helper_")):
            launch.kill_tree(read_pid(folder, f))


try:
    got, starts, said, logged, f = scene("normal", "ok")
    check("a normal start: one try, no message", got == "ready" and starts == 1 and not said, (got, starts, said))
    check("it's still open after the watcher is done", alive(read_pid(f, "start_0")))
    check("the time it took is logged", "ready in" in logged[-1], logged)
    clean(f)

    got, starts, said, logged, f = scene("stall_once", "stall,ok")
    check("a stall: closed and started again, comes up", got == "ready" and starts == 2 and not said, (got, starts, said, logged))
    time.sleep(0.5)
    check("the stalled copy is gone", not alive(read_pid(f, "start_0")))
    check("and its helper with it", not alive(read_pid(f, "helper_0")))
    check("the good copy is still open", alive(read_pid(f, "start_1")))
    check("the stall is logged", "no word after" in logged[0], logged)
    clean(f)

    got, starts, said, logged, f = scene("stall_twice", "stall,stall,ok")
    check("two stalls: the third try comes up", got == "ready" and starts == 3 and not said, (got, starts, said))
    clean(f)

    got, starts, said, logged, f = scene("always_slow", "stall")
    check("never comes up: the last try is left open and the user is told", got == "slow" and starts == 3 and alive(read_pid(f, "start_2")) and len(said) == 1, (got, starts, said))
    clean(f)

    got, starts, said, logged, f = scene("crash_once", "crash,ok")
    check("a crash: started again", got == "ready" and starts == 2 and not said, (got, starts, said))
    clean(f)

    got, starts, said, logged, f = scene("crash_always", "crash")
    check("always crashes: stops after the tries, and says so", got == "crashed" and starts == 3 and len(said) == 1, (got, starts, said))

    got, starts, said, logged, f = scene("closed", "closed")
    check("the user closes it while it's starting: no restart, no message", got == "closed" and starts == 1 and not said, (got, starts, said))

    got, starts, said, logged, f = scene("cut_once", "bad,ok")
    check("a page reporting a cut-off script: started again", got == "ready" and starts == 2, (got, starts, logged))
    clean(f)

    got, starts, said, logged, f = scene("bad_always", "bad")
    check("script errors every time (say a user's own edit): left open, no scary message", got == "problems" and starts == 3 and alive(read_pid(f, "start_2")) and not said, (got, starts, said))
    clean(f)

    got, starts, said, logged, f = scene("env", "env")
    check("the app gets the caller's settings", open(os.path.join(f, "env")).read() == "kept")
    clean(f)

    log = os.path.join(TOP, "logdir", "launch.log")
    for i in range(launch.LOG_LINES + 20):
        launch.write_log(log, f"line {i}")
    lines = open(log, encoding="utf-8").read().splitlines()
    check("the log stays short", len(lines) == launch.LOG_LINES and lines[-1].endswith(f"line {launch.LOG_LINES + 19}"), len(lines))

    # ---------- the real app, hidden, on a copy ----------
    real = os.path.join(TOP, "real")
    shutil.copytree(APP, real, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests", "packaging", "docs", "session.json", "snapshots", "app.lock", "launch.log", "workspace"))
    js = os.path.join(real, "ui", "app.js")
    whole = open(js, "rb").read()
    env = {k: v for k, v in os.environ.items() if k != "UDS_READY_FILE"}
    env.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_LAUNCH_TRIES="40,40,60")
    log = os.path.join(real, "data", "launch.log")

    def run_launch(tries):
        return subprocess.Popen([sys.executable, os.path.join(real, "launch.py")], cwd=real, env=dict(env, UDS_LAUNCH_TRIES=tries))

    def app_pid():
        with open(os.path.join(real, "data", "app.lock"), encoding="utf-8") as f:
            return int(f.read().strip())

    p = run_launch("40,40,60")
    p.wait(timeout=130)
    text = open(log, encoding="utf-8").read() if os.path.exists(log) else ""
    check("the real app reports in", "ready in" in text, text)      # try 1 normally; a real stall here just takes another try
    print("normal start:", text.strip().splitlines()[-1] if text.strip() else "no log", flush=True)
    launch.kill_tree(app_pid())
    time.sleep(1)

    with open(js, "wb") as f:
        f.write(whole[:81920])
    open(log, "w").close()
    p = run_launch("12,40,60")
    time.sleep(6)            # the first copy has it cut: its reloads run out and it sits dead
    with open(js, "wb") as f:
        f.write(whole)       # the next start finds it whole, as with the real random stall
    p.wait(timeout=130)
    text = open(log, encoding="utf-8").read()
    lines = text.strip().splitlines()
    check("the real app with app.js cut off: closed after its wait", len(lines) == 2 and "try 1:" in lines[0] and "starting again" in lines[0], text)
    check("the second start comes up", len(lines) == 2 and "try 2: ready in" in lines[1], text)
    pid = app_pid()
    check("that copy stays open", alive(pid), pid)
    launch.kill_tree(pid)
    time.sleep(1)
except Exception as e:
    check("test crashed", False, repr(e)[:500])
finally:
    time.sleep(0.5)
    shutil.rmtree(TOP, onerror=lambda f, q, e: (os.chmod(q, stat.S_IWRITE), f(q)))

print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
