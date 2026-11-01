# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/llm_test.py   (loads the real local GGUF once, plus a fake LM Studio server; prints PASS/FAIL)
"""Backend test of llm.py: finding models, linking, streaming replies, stopping, trimming long chats,
and the LM Studio link over real HTTP against a stand-in server."""
import json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
UDS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, UDS)
import llm

results = []

def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

def wait(hub, job_id, timeout=300):
    seen, t0 = set(), time.time()
    while time.time() - t0 < timeout:
        r = hub.poll(job_id)
        seen.add(r["status"])
        if r["done"]:
            r["seen"] = seen
            return r
        time.sleep(0.1)
    return {"done": False, "error": "timeout", "text": "", "seen": seen}

# ---- fake LM Studio ----
class FakeLMS(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeLMS.last = req
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for piece in ["Hello", " from", " LM Studio"]:
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n".encode()); self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")

srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLMS)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}"

hub = llm.LLMHub()
try:
    rec = hub.link({"kind": "lmstudio", "url": url})
    check("LM Studio link", rec["model"] == "fake-model" and rec["name"] == "LM Studio · fake-model", str(rec))
    r = wait(hub, hub.start(rec, [{"role": "user", "content": "hi"}]))
    check("LM Studio streams reply", r["text"] == "Hello from LM Studio" and not r["error"], str(r))
    check("LM Studio gets system + user", [m["role"] for m in FakeLMS.last["messages"]] == ["system", "user"] and FakeLMS.last["stream"])
except Exception as e:
    check("LM Studio block crashed", False, repr(e))
try:
    hub.link({"kind": "lmstudio", "url": "http://127.0.0.1:9"})
    check("LM Studio down -> clear error", False, "no error raised")
except ValueError as e:
    check("LM Studio down -> clear error", "isn't answering" in str(e), str(e))
srv.shutdown()

# ---- local GGUF ----
files = llm.find_gguf_files()
qwen = [f for f in files if f["name"] == "qwen2.5-3b-instruct-q4_k_m.gguf"]
check("finds the Qwen 3B GGUF", qwen, str([f["name"] for f in files]))
try:
    hub.link({"kind": "local", "path": r"C:\nope\missing.gguf"})
    check("missing file -> clear error", False, "no error raised")
except ValueError as e:
    check("missing file -> clear error", "File not found" in str(e), str(e))

if qwen:
    rec = hub.link({"kind": "local", "path": qwen[0]["path"]})
    check("local link named", rec["name"] == "qwen2.5-3b-instruct-q4_k_m.gguf", str(rec))
    t0 = time.time()
    r = wait(hub, hub.start(rec, [{"role": "user", "content": "Reply with exactly one word: hello"}]))
    check("local reply (first, loads model)", r["done"] and not r["error"] and r["text"].strip(),
          f"{r['text']!r} err={r['error']} {time.time() - t0:.1f}s")
    check("status showed loading", "loading model" in r["seen"], str(r["seen"]))
    print(f"  first reply {time.time() - t0:.1f}s: {r['text']!r}")
    # follow-up uses history
    hist = [{"role": "user", "content": "My name is Sam. Just say ok."}, {"role": "assistant", "content": "Ok."},
            {"role": "user", "content": "What is my name? One word."}]
    r = wait(hub, hub.start(rec, hist))
    check("local remembers chat history", "sam" in r["text"].lower(), repr(r["text"]))
    # stop mid-reply
    jid = hub.start(rec, [{"role": "user", "content": "Count from 1 to 300, one number per line."}])
    while len(hub.jobs[jid].text) < 20:
        time.sleep(0.05)
    t0 = time.time(); hub.stop(jid)
    r = wait(hub, jid, 30)
    check("stop ends the reply fast", r["done"] and time.time() - t0 < 3 and len(r["text"]) < 400,
          f"{time.time() - t0:.2f}s, {len(r['text'])} chars")
    # a chat longer than the context window still answers (oldest turns dropped)
    long = []
    for i in range(40):
        long += [{"role": "user", "content": f"Note {i}: " + "lorem ipsum dolor sit amet " * 30}, {"role": "assistant", "content": "Noted."}]
    long.append({"role": "user", "content": "Say ok."})
    r = wait(hub, hub.start(rec, long))
    check("over-long chat still answers", r["done"] and not r["error"] and r["text"].strip(), f"err={r['error']} {r['text'][:60]!r}")
    hub.unlink(rec["id"])
    check("unlink frees the model", rec["id"] not in hub.backends)

fails = [r for r in results if not r[1]]
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{len(results) - len(fails)}/{len(results)} passed")
