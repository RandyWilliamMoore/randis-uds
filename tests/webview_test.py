# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/webview_test.py <browser page.html>   (hidden window, throwaway data; needs the internet and Windows)
"""A built tab's Web view switch: off, the tab stays walled; on, the app shows the sites the tab asks for in real
browser views (webpane.py) laid over the tab's page, only real web addresses, never this machine. Sites that refuse to
sit in a frame (GitHub) show too. Also: back/forward, closing, stepping aside for dialogs and other tabs, the tab's own
store, and the pop-out. Drives a browser tab page with a test hook added. WEBVIEW_SHOT=<file.png> saves a picture."""
import json, os, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_webview_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_WEB_PROFILE=os.path.join(TOP, "web"))

import webview
import app, tabs

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
opened = []
app.webbrowser.open = lambda u, *a, **k: opened.append(u) or True
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

if len(sys.argv) < 2:
    raise SystemExit("give the browser tab page to test, e.g. data/tabs/<id>/v004.html")
page = open(sys.argv[1], encoding="utf-8").read()
HOOK = """<script>window.__got = []; window.addEventListener('message', function(e){ if (e.data && e.data.uds) __got.push(e.data.uds); if (e.data && e.data.test){
  var r; try { r = (0, eval)(e.data.test); } catch(x){ r = 'ERR ' + x.message; }
  parent.postMessage({testResult: e.data.n, value: JSON.stringify(r === undefined ? null : r)}, '*'); } });</script>"""
k = page.rfind("</body>")
page = page[:k] + HOOK + page[k:]
tid = tabs.TabStore(os.path.join(D, "tabs")).save_version(None, "Browser", page, "test copy")["id"]


def run(w):
    try:
        api._startup()
        _run(w)
    except Exception as e:
        check("test crashed", False, repr(e)[:300])
    finally:
        w.destroy()


def _run(w):
    js = w.evaluate_js
    def until(cond, secs=8):
        end = time.time() + secs
        while time.time() < end:
            try:
                if js(cond):
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        return False
    def wait(fn, secs=15):
        end = time.time() + secs
        while time.time() < end:
            if fn():
                return True
            time.sleep(0.25)
        return False
    n = [0]
    def inpage(code, secs=5):
        """Run code inside the walled tab page (through its test hook) and return the result."""
        n[0] += 1
        js(f"window.__tr = window.__tr || {{}}; delete window.__tr[{n[0]}];"
           f"$('iframe', builtTab().pane).contentWindow.postMessage({{ test: {json.dumps(code)}, n: {n[0]} }}, '*')")
        if not until(f"window.__tr && {n[0]} in window.__tr", secs):
            return "NO ANSWER"
        return json.loads(js(f"window.__tr[{n[0]}]"))
    panes = lambda: api.webpane_state()
    pane = lambda i: panes().get(f"{tid}:{i}", {})

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0", 25))
    js("addEventListener('message', e => { if (e.data && e.data.testResult) window.__tr[e.data.testResult] = e.data.value; });"
       f"window.builtTab = () => state.tabs.find(t => t.builtId === {json.dumps(tid)});"
       f"refreshBuilt().then(() => openBuilt({json.dumps(tid)}))")
    check("the browser tab opens", until("builtTab() && !$('iframe', builtTab().pane).hidden", 10))
    check("its page answers the test hook", any(inpage("1+1", 1) == 2 for _ in range(8)))

    # ---- switch off: walled ----
    check("Web view starts off", js("!$('.web-on', builtTab().pane).checked") and inpage("webOn") is False)
    inpage("$('addr').value = 'example.com'; $('go').click(); 1")
    time.sleep(0.8)
    check("off: no browser view is made", panes() == {}, panes())
    check("off: the page says Web view is off", inpage("!$('off').hidden") is True)

    # ---- switch on ----
    js("const c = $('.web-on', builtTab().pane); c.checked = true; c.dispatchEvent(new Event('change'))")
    meta_web = lambda: json.load(open(os.path.join(D, "tabs", tid, "meta.json"), encoding="utf-8")).get("web")
    check("on: the switch is saved in the tab's meta", wait(lambda: meta_web() is True, 5))
    check("on: the page hears it", wait(lambda: inpage("webOn") is True, 5))
    check("on: a real browser view shows example.com", wait(lambda: pane("t1").get("url", "").startswith("https://example.com")
                                                              and pane("t1").get("visible")), panes())
    check("on: the site loads and the tab shows its title (needs the internet)",
          wait(lambda: "Example" in str(inpage("document.querySelector('.tab.on span').textContent")), 20),
          inpage("document.querySelector('.tab.on span').textContent"))
    want = js("(() => { const b = $('iframe', builtTab().pane).getBoundingClientRect(), d = devicePixelRatio;"
              " return JSON.stringify([b.left, b.top, d]); })()")
    bl, bt, dpr = json.loads(want)
    view = inpage("(function(){ var r = $('view').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    exp = [round((bl + view[0]) * dpr), round((bt + view[1]) * dpr), round(view[2] * dpr), round(view[3] * dpr)]
    got = pane("t1").get("bounds")
    check("on: the view sits exactly over the tab's page area, not over its buttons",
          got and all(abs(a - b) <= 2 for a, b in zip(got, exp)), (got, exp))

    # ---- a site that refuses frames ----
    inpage("open('github.com'); 1")
    check("GitHub shows (it refused to sit in a frame before)",
          wait(lambda: pane("t1").get("url", "").startswith("https://github.com") and "GitHub" in pane("t1").get("title", ""), 25), pane("t1"))
    if os.environ.get("WEBVIEW_SHOT"):    # a picture of the tab showing a site, for a person to look at
        try:
            from PIL import ImageGrab
            w.move(0, 0); w.on_top = True; w.show(); time.sleep(3)
            ImageGrab.grab(bbox=(0, 0, round(1375 * dpr), round(900 * dpr))).save(os.environ["WEBVIEW_SHOT"])
        except Exception as e:
            print("no picture:", e)
        w.hide()
    check("the page's Back lights up from the browser's own history", wait(lambda: inpage("!$('back').disabled") is True, 5))
    inpage("$('back').click(); 1")
    check("Back goes to the site before", wait(lambda: pane("t1").get("url", "").startswith("https://example.com"), 15), pane("t1"))
    check("Forward lights up", wait(lambda: inpage("!$('fwd').disabled") is True, 5))
    inpage("$('fwd').click(); 1")
    check("Forward goes the other way", wait(lambda: pane("t1").get("url", "").startswith("https://github.com"), 15), pane("t1"))

    # ---- stepping aside ----
    js("openModal('Test', [el('p', {}, 'a dialog')])")
    check("a dialog over the view: the view steps aside", wait(lambda: not pane("t1").get("visible"), 3))
    js("closeModal()")
    check("dialog closed: the view comes back", wait(lambda: pane("t1").get("visible"), 3))
    js("addTab('notepad', { title: 'Other' })")
    check("another app tab: the view hides", wait(lambda: not pane("t1").get("visible"), 3))
    js("selectTab(builtTab().id)")
    check("back on the browser tab: the view shows again", wait(lambda: pane("t1").get("visible"), 3))

    # ---- tabs inside the browser ----
    inpage("newTab('example.org'); 1")
    check("a second tab gets its own view and the first hides",
          wait(lambda: pane("t2").get("url", "").startswith("https://example.org") and pane("t2").get("visible") and not pane("t1").get("visible")), panes())
    inpage("show(tabs[0]); 1")
    check("switching tabs swaps the views", wait(lambda: pane("t1").get("visible") and not pane("t2").get("visible"), 3), panes())
    inpage("closeTab(tabs[1]); 1")
    check("closing a tab closes its view", wait(lambda: f"{tid}:t2" not in panes(), 3), panes())

    # ---- only real web addresses ----
    for bad in ("http://127.0.0.1:8000/", "http://localhost/", "file:///C:/Windows/win.ini"):
        inpage("__got = []; 1")
        inpage(f"open({json.dumps(bad)}); 1")
        check(f"refused: {bad}", wait(lambda: inpage("__got.indexOf('web-refused') >= 0") is True, 3)
              and not pane("t1").get("url", "").startswith(bad[:12]), pane("t1"))
    check("refused: the app won't open a local file in a view even if asked directly",
          isinstance(api.webpane_go(None, f"{tid}:x", "file:///C:/Windows/win.ini"), dict) and f"{tid}:x" not in panes())

    # ---- pop-out ----
    inpage("open('example.net'); $('ext').click(); 1")
    check("pop-out opens the address in the person's web browser", wait(lambda: opened == ["https://example.net"], 3), opened)
    check("pop-out refuses a file address", api.web_open_outside("file:///C:/x").get("error") and opened == ["https://example.net"])

    # ---- the tab's own store ----
    inpage("$('msg').value = 'hello there'; $('send').click(); 1")
    store = os.path.join(D, "tabs", tid, "store.json")
    wait(lambda: os.path.isfile(store), 3)
    saved = json.load(open(store, encoding="utf-8")) if os.path.isfile(store) else {}
    check("the chat is kept in the tab's folder", any(m.get("t") == "hello there" for m in saved.get("chat", [])), saved)
    js("loadBuilt(builtTab())")
    until("!$('iframe', builtTab().pane).hidden", 5)
    check("the chat comes back after the page reloads",
          wait(lambda: "hello there" in str(inpage("document.getElementById('log').innerText", 1)), 6))
    check("reloading closes the old views", wait(lambda: panes() == {}, 3), panes())
    check("too much to keep is refused", api.built_store_set(tid, {"x": "a" * 1_100_000}).get("error"))

    # ---- switch off again ----
    inpage("open('example.com'); 1")
    wait(lambda: pane("t1").get("visible"), 10)
    js("const c = $('.web-on', builtTab().pane); c.checked = false; c.dispatchEvent(new Event('change'))")
    check("off again: the views close", wait(lambda: panes() == {}, 3), panes())
    inpage("open('example.org'); 1")
    time.sleep(0.6)
    check("off again: new addresses aren't shown", panes() == {} and inpage("!$('off').hidden") is True, panes())


api = app.Api()
w = webview.create_window("web view test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for name, ok, d in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
