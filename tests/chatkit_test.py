# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import llm

failed = checks = 0


def check(name, ok, detail=""):
    global failed, checks
    checks += 1
    if not ok:
        failed += 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


class SlowLMS(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        try:
            for i in range(40):
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': f'w{i} '}}]})}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.1)
            self.wfile.write(b"data: [DONE]\n\n")
        except OSError:
            pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), SlowLMS)
threading.Thread(target=srv.serve_forever, daemon=True).start()
hub = llm.LLMHub()
rec = hub.link({"kind": "lmstudio", "url": f"http://127.0.0.1:{srv.server_port}"})

job = hub.start(rec, [{"role": "user", "content": "hi"}], chat_id="chatA")
time.sleep(0.6)
run = hub.running()
check("running reply listed with its chat", any(r["job"] == job and r["chat"] == "chatA" for r in run), str(run))
other = hub.start(rec, [{"role": "user", "content": "hi"}])
check("a reply with no chat isn't listed", all(r["job"] != other for r in hub.running()))
hub.stop(other)

check("pause says paused", hub.pause(job, True) is True)
time.sleep(0.3)
a = hub.poll(job)
time.sleep(0.8)
b = hub.poll(job)
check("no new text while paused", a["text"] == b["text"], f"{len(a['text'])} -> {len(b['text'])}")
check("meter says paused", b["meter"]["paused"] is True)
check("clock stopped while paused", abs(b["meter"]["elapsed"] - a["meter"]["elapsed"]) < 0.05, f"{a['meter']['elapsed']} -> {b['meter']['elapsed']}")
check("status says paused", b["status"].startswith("paused"), b["status"])
check("resume says not paused", hub.pause(job, False) is False)
time.sleep(0.6)
c = hub.poll(job)
check("text grows again after resume", len(c["text"]) > len(b["text"]), f"{len(b['text'])} -> {len(c['text'])}")
check("tokens counted", c["meter"].get("tokens_out", 0) >= 5, str(c["meter"]))
check("runs on this PC", c["meter"]["where"] == "pc")

hub.pause(job, True)
hub.stop(job)
t0 = time.time()
while time.time() - t0 < 5:
    r = hub.poll(job)
    if r["done"]:
        break
    time.sleep(0.05)
check("stop works while paused", r["done"] and time.time() - t0 < 3, str(r)[:200])
check("stopped reply no longer listed", all(x["job"] != job for x in hub.running()))

job2 = hub.start(rec, [{"role": "user", "content": "hi"}], chat_id="chatB")
j2 = hub.jobs[job2]
spin = subprocess.Popen([sys.executable, "-c", "while True: pass"])
j2.proc = spin
try:
    time.sleep(0.5); hub.poll(job2); time.sleep(1.0)
    m = hub.poll(job2)["meter"]
    check("process CPU and RAM measured", m.get("cpu", 0) > 1 and m.get("ram_mb", 0) > 0, str(m))
    hub.pause(job2, True)
    time.sleep(0.5); hub.poll(job2); time.sleep(1.0)
    m = hub.poll(job2)["meter"]
    check("paused process uses no CPU", m.get("cpu", 99) < 1, str(m))
    import psutil
    check("process really suspended", psutil.Process(spin.pid).status() == psutil.STATUS_STOPPED or os.name == "nt", psutil.Process(spin.pid).status())
    hub.pause(job2, False)
    time.sleep(0.5); hub.poll(job2); time.sleep(1.0)
    m = hub.poll(job2)["meter"]
    check("resumed process runs again", m.get("cpu", 0) > 1, str(m))
finally:
    hub.stop(job2)
    if spin.poll() is None:
        spin.kill()

job3 = hub.start(rec, [{"role": "user", "content": "hi"}], chat_id="chatC")
real = llm.meter
llm.meter = lambda j: (time.sleep(0.3), real(j))[1]
try:
    t0, lost, got = time.time(), False, None
    while time.time() - t0 < 15:
        r = hub.poll(job3)
        if r.get("error", "") and "lost" in r["error"]:
            lost = True; break
        if r["done"]:
            got = r; break
finally:
    llm.meter = real
check("reply finishing mid-poll isn't lost", not lost and got and got["text"].startswith("w0"), str(r)[:200])

srv.shutdown()
print(f"{checks - failed}/{checks} passed")
sys.exit(1 if failed else 0)
