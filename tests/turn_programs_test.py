# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""What a Claude Code turn leaves running: hidden programs stop when the turn ends, however it ends; windows stay, with what they started.
Uses the stand-in for Claude, and a real hidden Edge when Edge is installed."""
import json, os, shutil, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TOP = tempfile.mkdtemp(prefix="uds_turn_test_")
os.environ.update(UDS_CLAUDE_CMD=json.dumps([sys.executable, os.path.join(HERE, "tests", "fake_claude.py")]),
                  FAKE_CLAUDE_LOG=os.path.join(TOP, "log.jsonl"), FAKE_PACE="0")
import ccode
import llm
import turn_programs
results = []
NO_WINDOW = subprocess.CREATE_NO_WINDOW
EDGE = next((p for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if os.path.exists(p)), None)


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


def alive(pid):
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=NO_WINDOW)
    return str(pid) in r.stdout


def read_pid(name, secs=20):
    p = os.path.join(TOP, name)
    end = time.time() + secs
    while time.time() < end:
        if os.path.exists(p) and open(p).read().strip():
            return int(open(p).read().strip())
        time.sleep(0.1)
    return None


def script(name, body):
    p = os.path.join(TOP, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)
    return p


HIDDEN = script("hidden.py", "import os,sys,time\nopen(sys.argv[1],'w').write(str(os.getpid()))\ntime.sleep(120)\n")
WINDOWED = script("windowed.py", f"""import os,subprocess,sys,tkinter
open(sys.argv[1],'w').write(str(os.getpid()))
subprocess.Popen([sys.executable,{HIDDEN!r},sys.argv[2]],creationflags=subprocess.CREATE_NO_WINDOW)
r=tkinter.Tk();r.geometry('120x60+-3000+-3000');r.after(120000,r.destroy);r.mainloop()
""")


def edge_count(folder):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", f"@(Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object {{ $_.CommandLine -like '*{os.path.basename(folder)}*' }}).Count"], capture_output=True, text=True, creationflags=NO_WINDOW)
    return int(r.stdout.strip() or 0)


def turn(ask, leave, stop_after=None):
    os.environ["FAKE_LEAVE"] = json.dumps(leave)
    job = llm.Job()
    ctx = {"before": lambda j: None, "after": lambda j: None, "save_session": lambda s: None, "session": None}
    cc = ccode.ClaudeCode({"cwd": TOP})
    if stop_after:
        threading.Timer(stop_after, lambda: setattr(job, "stop", True)).start()
    err = None
    try:
        cc.stream([{"role": "user", "content": ask}], job, ctx=ctx)
    except ValueError as e:
        err = str(e)
    return job, err


# the rule itself: only members count, and what a window started stays with it
stop = turn_programs.to_stop
check("no window: stopped", stop([1, 2], set(), {}) == [1, 2])
check("a window stays", stop([1], {1}, {}) == [])
check("what a window started stays, however deep", stop([1, 2, 3], {1}, {2: 1, 3: 2}) == [])
check("what started a window doesn't stay", stop([1, 2], {2}, {2: 1}) == [1])
check("a parent outside the job doesn't count", stop([2], {1}, {2: 1}) == [2])
check("a loop in reused ids doesn't hang", stop([1, 2], set(), {1: 2, 2: 1}) == [1, 2])

# an ordinary turn
hid, win, kid = os.path.join(TOP, "hid"), os.path.join(TOP, "win"), os.path.join(TOP, "kid")
leave = [[sys.executable, HIDDEN, hid], [sys.executable, WINDOWED, win, kid]]
seen = {}
edge_dir = None
if EDGE:
    edge_dir = os.path.join(TOP, "edgetest")
    leave.append([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=0", f"--user-data-dir={edge_dir}", "about:blank"])


def watch():
    end = time.time() + 15
    while time.time() < end and not seen.get("edge"):
        seen["edge"] = edge_count(edge_dir)
        time.sleep(0.3)


if EDGE:
    threading.Thread(target=watch, daemon=True).start()
job, err = turn("leave programs", leave)
check("the turn still answers", not err and "Hi from Claude Code" in job.text, (err, job.text))
pid_hid, pid_win, pid_kid = read_pid("hid"), read_pid("win"), read_pid("kid")
check("the programs really started", all((pid_hid, pid_win, pid_kid)), (pid_hid, pid_win, pid_kid))
time.sleep(1)
check("a hidden program stopped when the turn ended", not alive(pid_hid), pid_hid)
check("a program with a window kept running", alive(pid_win), pid_win)
check("and so did what it started", alive(pid_kid), pid_kid)
if EDGE:
    check("a real hidden Edge really started", seen.get("edge", 0) > 0, seen)
    end = time.time() + 5
    while time.time() < end and edge_count(edge_dir):
        time.sleep(0.3)
    check("every process of it stopped", edge_count(edge_dir) == 0, edge_count(edge_dir))
else:
    print("no Edge on this computer: skipped its checks")
subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid_win)], capture_output=True, creationflags=NO_WINDOW)
subprocess.run(["taskkill", "/F", "/PID", str(pid_kid)], capture_output=True, creationflags=NO_WINDOW)

# a turn that fails
hid2 = os.path.join(TOP, "hid2")
job, err = turn("leave programs then fail", [[sys.executable, HIDDEN, hid2]])
check("a failed turn says so", bool(err), err)
pid2 = read_pid("hid2")
time.sleep(1)
check("what a failed turn left stopped too", pid2 and not alive(pid2), pid2)

# a turn the user stops
hid3 = os.path.join(TOP, "hid3")
job, err = turn("leave programs then slow", [[sys.executable, HIDDEN, hid3]], stop_after=3)
pid3 = read_pid("hid3")
time.sleep(1)
check("what a stopped turn left stopped too", pid3 and not alive(pid3), pid3)

# something that isn't part of a turn is never touched
outside = subprocess.Popen([sys.executable, HIDDEN, os.path.join(TOP, "out")], creationflags=NO_WINDOW)
hid4 = os.path.join(TOP, "hid4")
turn("leave programs", [[sys.executable, HIDDEN, hid4]])
time.sleep(1)
check("a hidden program outside the turn is left alone", outside.poll() is None)
outside.kill()
outside.wait()

t = turn_programs.TurnPrograms()
check("finishing an empty job stops nothing, and twice is fine", t.finish() == 0 and t.finish() == 0)
check("Claude is told the rule", "no visible window" in ccode.SYSTEM)
shutil.rmtree(TOP, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
