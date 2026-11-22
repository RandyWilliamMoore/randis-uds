import os, sys, time, subprocess, tempfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import ramguard as rg

GB = rg.GB
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

tmp = tempfile.mkdtemp(prefix="ramguard_")
count = os.path.join(tmp, "count")
HOG = ("import sys, time, subprocess\n"
       "b = bytearray(300 * 1024 * 1024)\n"
       "for i in range(0, len(b), 4096): b[i] = 1\n"
       "kid = subprocess.Popen([sys.executable, '-c', 'import time\\nwhile True: time.sleep(1)'])\n"
       "n = 0\n"
       "while True:\n"
       "    n += 1; open(sys.argv[1], 'w').write(str(n)); time.sleep(0.05)\n")
hog = subprocess.Popen([sys.executable, "-c", HOG, count])
outsider = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(1)"], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
seen = []
try:
    t0 = time.time()
    while time.time() - t0 < 30 and not (os.path.exists(count) and any(p[0] == hog.pid and p[2] > 250 * 1024 ** 2 for p in rg.guarded())):
        time.sleep(0.3)
    g = {p[0]: p for p in rg.guarded()}
    ours = [pid for pid in g if pid not in (hog.pid, outsider.pid)]
    check("sees the job it started, with its memory", hog.pid in g and g[hog.pid][2] > 250 * 1024 ** 2, repr(g.get(hog.pid)))
    check("sees the job's own child too", bool(ours), repr(list(g)))
    check("never lists the app's own process", os.getpid() not in g)
    rg._state["me"] = os.getpid()
    rg._state["notify"] = seen.append

    def counting():
        a = open(count).read(); time.sleep(0.6); return open(count).read() != a
    check("plenty of RAM: does nothing", rg.tick(free=8 * GB) is None and counting())
    check("under 1.5 GB free: pauses the biggest job", rg.tick(free=int(1.3 * GB)) == "pause" and hog.pid in rg._paused)
    check("a paused job really stops (no progress)", not counting())
    check("the message says what and why", seen and "paused" in seen[-1]["message"] and "1 GB free" in seen[-1]["message"], seen[-1:] and seen[-1]["message"])
    check("waits for memory to settle before acting again", rg.tick(free=int(1.3 * GB)) is None)
    check("back over 2.5 GB: resumes it", rg.tick(free=4 * GB) == "resume" and hog.pid not in rg._paused)
    check("a resumed job carries on", counting())
    rg._state["last_act"] = 0
    check("under 1 GB free: stops the biggest job", rg.tick(free=int(0.8 * GB)) == "stop" and seen[-1]["pid"] == hog.pid)
    try:
        hog.wait(5)
    except subprocess.TimeoutExpired:
        pass
    check("the stopped job is gone", hog.poll() is not None)
    check("a process the app didn't start is untouched", outsider.poll() is None)
    check("extra roots (background bots) are guarded too", (rg.add_roots(lambda: [outsider.pid]), any(p[0] == outsider.pid for p in rg.guarded()))[1])
    rg._extra_roots.clear(); rg._state["me"] = -1
    started = rg._info(outsider.pid)[1] + rg._boot()
    rg.add_roots(lambda: [(outsider.pid, started - 3600)])
    check("a recorded job whose process id was reused is left alone", not any(p[0] == outsider.pid for p in rg.guarded()))
    rg._extra_roots.clear(); rg.add_roots(lambda: [(outsider.pid, started)])
    check("a recorded job with the right start time is guarded", any(p[0] == outsider.pid for p in rg.guarded()))
    rg._state["me"] = os.getpid()
    real_guarded, real_act, acted = rg.guarded, rg._act, []
    rg._act = lambda pid, what: acted.append((pid, what)) or True
    rg.guarded = lambda: [(901, "claude.exe", int(0.6 * GB)), (902, "powershell.exe", 60 * 1024 ** 2)]
    rg._state["last_act"] = 0
    check("never pauses a Claude session or a small process", rg.tick(free=int(1.3 * GB)) is None and not acted, repr(acted))
    check("never stops them either, even under the floor", rg.tick(free=int(0.8 * GB)) is None and not acted, repr(acted))
    rg.guarded = lambda: [(901, "claude.exe", int(0.6 * GB)), (903, "python.exe", int(0.4 * GB))]
    check("still pauses a big job beside them", rg.tick(free=int(1.3 * GB)) == "pause" and acted == [(903, "pause")], repr(acted))
    rg._paused.pop(903, None); rg.guarded, rg._act = real_guarded, real_act
    st = rg.status()
    check("status reports floor, events and free RAM", st["floor_gb"] == 1.0 and len(st["events"]) >= 3 and st["free_gb"] is not None)
finally:
    for p in (hog, outsider):
        try: p.kill()
        except OSError: pass
    for pid in globals().get("ours", []):
        rg._act(pid, "stop")

fails = [r for r in results if not r[1]]
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
