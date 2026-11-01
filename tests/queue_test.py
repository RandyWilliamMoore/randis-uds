# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""The local server must survive a burst of connections: the page asks for 11 files at once.
Runs pywebview's real server, no window. Passing a number as the first argument overrides the queue
size, to compare against the old default: python tests/queue_test.py 5
"""
import os
import socket
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

import app  # noqa: F401  (importing it applies the queue setting)
from webview.http import BottleServer
from wsgiref.simple_server import WSGIServer

if len(sys.argv) > 1:
    WSGIServer.request_queue_size = int(sys.argv[1])
    print("queue overridden to", WSGIServer.request_queue_size)

BURST, ROUNDS = 64, 20
failed = checks = 0


def check(name, ok, detail=""):
    global failed, checks
    checks += 1
    failed += not ok
    print(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""), flush=True)


check("the app sets a queue of at least 128", WSGIServer.request_queue_size >= 128, str(WSGIServer.request_queue_size))

address, _, server = BottleServer.start_server([os.path.join(HERE, "ui", "index.html")], None)
port = server.port
for _ in range(100):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        break
    except OSError:
        time.sleep(0.05)
time.sleep(0.2)
expected = os.path.getsize(os.path.join(HERE, "ui", "app.js"))
print("server", address, "app.js", expected, "bytes", flush=True)

errors, short = [], 0
slowest = 0.0
lock = threading.Lock()


def fetch(gate):
    global short, slowest
    gate.wait()
    t0 = time.time()
    try:
        body = urllib.request.urlopen(address + "app.js", timeout=30).read()
        with lock:
            short += len(body) != expected
            slowest = max(slowest, time.time() - t0)
    except Exception as e:
        with lock:
            errors.append(repr(e)[:120])


for _ in range(ROUNDS):
    gate = threading.Barrier(BURST)
    threads = [threading.Thread(target=fetch, args=(gate,)) for _ in range(BURST)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

total = BURST * ROUNDS
print(f"{total} requests: {len(errors)} errors, {short} short, slowest {slowest:.2f}s", flush=True)
for e in sorted(set(errors))[:5]:
    print("  ", e)
check("no connection fails in a burst", not errors, f"{len(errors)} of {total}")
check("every file arrives whole", short == 0, f"{short} of {total}")
print(f"{checks - failed}/{checks} passed", flush=True)
sys.exit(1 if failed else 0)
