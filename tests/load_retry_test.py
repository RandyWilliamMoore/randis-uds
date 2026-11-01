# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/load_retry_test.py   (opens hidden windows on a copy of the page with app.js cut off)
"""When the browser gets app.js cut off, the page reloads itself and the app comes up; if it never loads, the page says so.
Works on a throwaway copy of the app's page, cut at the same 81,920 bytes seen in the real failure."""
import os, shutil, stat, sys, tempfile, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_load_retry_")
UI = os.path.join(TOP, "ui")
shutil.copytree(os.path.join(APP, "ui"), UI)
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"))
import webview, app
app.DATA_DIR = TOP
app.SESSION_FILE = os.path.join(TOP, "session.json")

full = open(os.path.join(APP, "ui", "app.js"), "rb").read()
def put_app_js(data):
    with open(os.path.join(UI, "app.js"), "wb") as f:
        f.write(data)

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

def run(w):
    def until(expr, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if w.evaluate_js(expr):
                    return True
            except Exception:       # the page is mid-load
                pass
            time.sleep(0.05)
        return False
    try:
        # never loads: three reloads, then it says so
        check("if app.js never loads, the page says so", until("document.body && document.body.innerText.includes(\"didn't load after 3 tries\")"))
        check("and it stops reloading", w.evaluate_js("sessionStorage.getItem('udsReloads')") is None)
        # loads on the next try: the app comes up
        put_app_js(full)
        w.evaluate_js("location.reload()")
        check("once app.js arrives whole, the app comes up", until("typeof state !== 'undefined' && state.tabs.length > 0"))
        check("the retry count is cleared", w.evaluate_js("sessionStorage.getItem('udsReloads')") is None)
    except Exception as e:
        check("test crashed", False, repr(e)[:300])
    finally:
        w.destroy()

put_app_js(full[:81920])
api = app.Api()
w = webview.create_window("load retry test", url=os.path.join(UI, "index.html"), js_api=api, hidden=True)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, onerror=lambda f, q, e: (os.chmod(q, stat.S_IWRITE), f(q)))
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
