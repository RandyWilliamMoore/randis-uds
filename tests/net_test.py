# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Online play between two built tabs, through a real public relay (needs the internet).
A tab asks first; "Not now" keeps it offline; "Allow" is kept. One tab hosts and gets an invite code, the other joins with it,
and sealed messages go both ways. Also: the relay only ever carries sealed text, and bad codes are refused."""
import json, os, shutil, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TOP = tempfile.mkdtemp(prefix="uds_net_test_")
D = os.path.join(TOP, "data")
os.makedirs(D)
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"), UDS_TEST_HIDDEN="1")

import webview
import app
import net
import tabs
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:240]}]" if detail and not ok else ""), flush=True)


# A tiny game: it does what the test tells it and reports everything the app sends back.
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Net Demo</title></head><body><p>net demo</p><script>
const seen = [];
addEventListener('message', e => {
  if (e.source !== parent || !e.data) return;
  if (e.data.uds === 'net') { seen.push(e.data); parent.postMessage({demo: seen}, '*'); return; }
  if (e.data.go) parent.postMessage(Object.assign({uds: 'net'}, e.data.go), '*');
});
</script></body></html>"""
store = tabs.TabStore(os.path.join(D, "tabs"))
A = store.save_version(None, "Host Demo", PAGE, "test", new_id="netdemoaaa")["id"]
B = store.save_version(None, "Join Demo", PAGE, "test", new_id="netdemobbb")["id"]
api = app.Api()

# ---- no window: the app side refuses what it should
check("a tab isn't allowed online to start with", api.net_allowed(A) is False and "error" in api.net_open(A, None, "ruds/" + "0" * 32))
check("a bad tab id is refused", api.net_allowed("../x") is False)
check("a bad channel is refused", "error" in net.Hub().open("E", "not-a-channel"))
check("an unknown relay is refused", "error" in api.net_open(A, "Z", "ruds/" + "0" * 32) and "error" in net.Hub().open("Z", "ruds/" + "0" * 32))


def run(w):
    def js(x):
        return w.evaluate_js(x)

    def until(x, secs=10):
        end = time.time() + secs
        while time.time() < end:
            try:
                if js(x):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False

    def tell(tid, go):
        js(f"state.tabs.find(t => t.builtId === {json.dumps(tid)}).pane.querySelector('iframe').contentWindow.postMessage({{go: {json.dumps(go)}}}, '*')")

    def heard(tid):
        return json.loads(js(f"JSON.stringify(window.__demo[{json.dumps(tid)}] || [])") or "[]")

    try:
        api._window = w
        until("typeof state !== 'undefined' && typeof openBuilt === 'function'", 20)
        js("""window.__demo = {}; addEventListener('message', e => { if (!e.data || !e.data.demo) return;
          const t = state.tabs.find(t => t.pane && t.pane.querySelector('iframe') && t.pane.querySelector('iframe').contentWindow === e.source);
          if (t) __demo[t.builtId] = e.data.demo; });""")
        for tid in (A, B):
            js(f"openBuilt({json.dumps(tid)})")
            until(f"state.tabs.some(t => t.builtId === {json.dumps(tid)} && t.pane.querySelector('iframe'))")
        time.sleep(1.5)

        tell(A, {"op": "host"})
        check("hosting asks first", until("!$('#modal').hidden && !!document.querySelector('#modal [data-act=net-allow]')"))
        check("and opens nothing yet", api.net_allowed(A) is False and not heard(A))
        js("document.querySelector('#modal [data-act=net-deny]').click()")
        check("'Not now' tells the game online play is off", until(f"(window.__demo[{json.dumps(A)}] || []).some(m => m.ev === 'error')"), heard(A))
        check("and keeps the tab offline", api.net_allowed(A) is False)

        tell(A, {"op": "host"})
        until("!$('#modal').hidden && !!document.querySelector('#modal [data-act=net-allow]')")
        js("document.querySelector('#modal [data-act=net-allow]').click()")
        check("'Allow' is kept in the tab", until("$('#modal').hidden") and api.net_allowed(A) is True and store._meta(A).get("online") is True)
        check("the host gets an invite code", until(f"(window.__demo[{json.dumps(A)}] || []).some(m => m.ev === 'code')", 60), heard(A))
        code = next(m["code"] for m in heard(A) if m.get("ev") == "code")
        check("the code is a relay letter and 20 more", len(code.replace("-", "")) == 21, code)

        tell(B, {"op": "join", "code": "not a code"})
        until("!$('#modal').hidden && !!document.querySelector('#modal [data-act=net-allow]')")
        js("document.querySelector('#modal [data-act=net-allow]').click()")
        check("a bad code is refused", until(f"(window.__demo[{json.dumps(B)}] || []).some(m => m.ev === 'error')"), heard(B))
        tell(B, {"op": "join", "code": code.lower()})
        check("the friend joins with the code, without being asked again", until(f"(window.__demo[{json.dumps(B)}] || []).some(m => m.ev === 'open')", 60) and js("$('#modal').hidden") is True, heard(B))

        tell(B, {"op": "send", "data": {"t": "hello", "n": 1}})
        check("a message gets from the friend to the host", until(f"(window.__demo[{json.dumps(A)}] || []).some(m => m.ev === 'msg' && m.data && m.data.t === 'hello')", 20), heard(A))
        tell(A, {"op": "send", "data": {"t": "hi back", "list": [1, 2, 3]}})
        check("and one comes back, objects intact", until(f"(window.__demo[{json.dumps(B)}] || []).some(m => m.ev === 'msg' && m.data && m.data.t === 'hi back' && m.data.list.length === 3)", 20), heard(B))
        check("nobody hears their own messages", not any(m.get("ev") == "msg" and m["data"].get("t") == "hello" for m in heard(B)))

        tell(A, {"op": "leave"})
        time.sleep(1)
        check("leaving closes the host's link and only that one", len([l for l in api._net._links.values() if l.open]) == 1)
        check("no script errors", not js("(window.__errs || []).length"))
    except Exception as e:
        check("test crashed", False, repr(e))
    finally:
        w.destroy()


w = webview.create_window("test", url=os.path.join(HERE, "ui", "index.html"), js_api=api, x=-3000, y=-3000, width=1100, height=720)
api._window = w
webview.start(run, w)
api._net.close_all()
shutil.rmtree(TOP, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
