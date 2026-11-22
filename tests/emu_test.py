# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64, json, os, shutil, sys, tempfile, time, urllib.error, urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_emu_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_WEB_PROFILE=os.path.join(TOP, "web"))

import webview
import app, emuserve, tabs, webpane

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

if len(sys.argv) < 2:
    raise SystemExit("give the emulator tab page to test, e.g. data/tabs/<id>/v002.html")
page = open(sys.argv[1], encoding="utf-8").read()
HOOK = """<script>window.addEventListener('message', function(e){ if (e.data && e.data.test){
  var r; try { r = (0, eval)(e.data.test); } catch(x){ r = 'ERR ' + x.message; }
  parent.postMessage({testResult: e.data.n, value: JSON.stringify(r === undefined ? null : r)}, '*'); } });</script>"""
k = page.rfind("</body>")
page = page[:k] + HOOK + page[k:]
tid = tabs.TabStore(os.path.join(D, "tabs")).save_version(None, "Emulators", page, "test copy")["id"]

prg = bytearray(16384); prg[0:3] = b"\x4c\x00\x80"; prg[-6:] = b"\x00\x80" * 3
ROM = b"NES\x1a\x01\x01" + bytes(10) + bytes(prg) + bytes(8192)


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, {}, b""

srv = emuserve.Server()
check("the emulator files are in the app", srv.ready())
base = srv.base()
check("it answers only on this computer", base.startswith("http://127.0.0.1:"), base)
st, hd, body = get(base + "play.html")
check("the player page comes", st == 200 and b"Offline emulator" in body, st)
check("with a rule that keeps it off the internet", "connect-src 'self' blob: data:" in hd.get("Content-Security-Policy", ""), hd)
st, hd, body = get(base + "data/loader.js")
check("the emulator's files come", st == 200 and hd.get("Content-Type", "").startswith("text/javascript"), (st, hd))
st, _, body = get(base + "data/cores/fceumm-wasm.data")
check("a system core comes", st == 200 and len(body) > 100000, st)
root = base.split("/", 3)
host = root[0] + "//" + root[2]
for bad in (host + "/", host + "/data/loader.js", host + "/wrongtoken/play.html", base + "data/../../app.py",
            base + "data/%2e%2e/%2e%2e/app.py", base + "data/..%5c..%5capp.py", base + "app.py", base + "data/"):
    check(f"refused: {bad.replace(base, '<base>/')}", get(bad)[0] == 404)
check("the same address is given again", srv.base() == base)
srv.stop()

check("a normal pane can't go to this computer", not webpane.pane_ok(None, base + "play.html"))
check("the emulator's pane can go to its own address", webpane.pane_ok(base, base + "play.html"))
check("the emulator's pane can't go to the internet", not webpane.pane_ok(base, "https://example.com/"))
check("nor to another address on this computer", not webpane.pane_ok(base, host + "/other/"))


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
            try:
                if fn():
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False
    n = [0]
    def inpage(code, secs=5):
        n[0] += 1
        js(f"window.__tr = window.__tr || {{}}; delete window.__tr[{n[0]}];"
           f"$('iframe', builtTab().pane).contentWindow.postMessage({{ test: {json.dumps(code)}, n: {n[0]} }}, '*')")
        if not until(f"window.__tr && {n[0]} in window.__tr", secs):
            return "NO ANSWER"
        return json.loads(js(f"window.__tr[{n[0]}]"))
    key = f"{tid}:emu:main"
    pane = lambda: api.webpane_state().get(key, {})
    def inpane(code, secs=10):
        edge = api._panes(None)
        task = edge._ui(lambda: edge.panes[key].CoreWebView2.ExecuteScriptAsync(code))
        if not task.Wait(secs * 1000):
            return "NO ANSWER"
        return json.loads(str(task.Result))

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0", 25))
    js("addEventListener('message', e => { if (e.data && e.data.testResult) window.__tr[e.data.testResult] = e.data.value; });"
       f"window.builtTab = () => state.tabs.find(t => t.builtId === {json.dumps(tid)});"
       f"refreshBuilt().then(() => openBuilt({json.dumps(tid)}))")
    check("the emulator tab opens", until("builtTab() && !$('iframe', builtTab().pane).hidden", 10))
    check("its page answers the test hook", any(inpage("1+1", 1) == 2 for _ in range(8)))
    check("Web view is off", js("!$('.web-on', builtTab().pane).checked"))

    check("the emulator view opens on this computer", wait(lambda: pane().get("url", "").startswith("http://127.0.0.1:")
                                                               and "/play.html" in pane().get("url", "") and pane().get("visible"), 20), pane())
    check("the tab hears it's ready", wait(lambda: inpage("emuState") == "on", 5), inpage("emuState"))
    check("the player page shows", wait(lambda: inpane("document.title") == "Offline emulator", 15))
    want = js("(() => { const b = $('iframe', builtTab().pane).getBoundingClientRect(), d = devicePixelRatio;"
              " return JSON.stringify([b.left, b.top, d]); })()")
    bl, bt, dpr = json.loads(want)
    area = inpage("(function(){ var r = document.getElementById('emuarea').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    exp = [round((bl + area[0]) * dpr), round((bt + area[1]) * dpr), round(area[2] * dpr), round(area[3] * dpr)]
    got = pane().get("bounds")
    check("the view sits over the tab's emulator area, below its sub tabs", got and all(abs(a - b) <= 2 for a, b in zip(got, exp)), (got, exp))
    check("the player can't reach the internet", wait(lambda: inpane(
        "fetch('https://example.com/').then(() => window.__net = 'got out', () => window.__net = 'blocked'); 1") == 1, 5)
          and wait(lambda: inpane("window.__net || null") == "blocked", 10), inpane("window.__net || null"))

    b64 = base64.b64encode(ROM).decode()
    inpane(f"(() => {{ const b = Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0));"
           " take(new File([b], 'test.nes')); return 1; })()")
    check("the system is guessed from the file", inpane("sys && sys.core") == "fceumm", inpane("sys && sys.core"))
    inpane("document.getElementById('start').click(); 1")
    check("the game starts in the NES core (from this computer)",
          wait(lambda: inpane("!!(window.EJS_emulator && EJS_emulator.started)") is True, 60),
          inpane("window.EJS_emulator ? JSON.stringify({f: EJS_emulator.failedToStart, s: EJS_emulator.started}) : 'no emulator'"))
    check("it can't be sent to a website", (inpane("location.href = 'https://example.com/'; 1") == 1) and time.sleep(2) is None
          and "127.0.0.1" in pane().get("url", ""), pane())

    inpage("document.querySelector('.sub[data-v=chip8]').click(); 1")
    check("on the CHIP-8 sub tab the emulator view hides", wait(lambda: not pane().get("visible"), 3), pane())
    inpage("document.getElementById('loadDemo').click(); 1")
    check("the CHIP-8 bouncing ball demo draws", wait(lambda: (inpage("c8.gfx.reduce((a, b) => a + b, 0)") or 0) >= 4, 4)
          and inpage("c8.pc >= 0x200 && c8.pc < 0x232") is True, inpage("[c8.pc, c8.gfx.reduce((a,b)=>a+b,0)]"))
    inpage("document.getElementById('demo').value = 'keys'; document.getElementById('loadDemo').click(); 1")
    wait(lambda: inpage("c8.wait") == 6, 5)
    inpage("keyEvt(0xA, true); keyEvt(0xA, false); 1")
    check("the keypad demo shows the key pressed", wait(lambda: (inpage("c8.V[6]") == 0xA) and (inpage("c8.gfx.reduce((a, b) => a + b, 0)") or 0) > 5, 6),
          inpage("[c8.V[6], c8.gfx.reduce((a,b)=>a+b,0)]"))
    inpage("document.querySelector('.sub[data-v=offline]').click(); 1")
    check("back on Offline emulator it shows again, still playing", wait(lambda: pane().get("visible"), 3)
          and inpane("!!(window.EJS_emulator && EJS_emulator.started)") is True, pane())
    js("const c = $('.web-on', builtTab().pane); c.checked = true; c.dispatchEvent(new Event('change'))")
    time.sleep(0.6)
    js("const c2 = $('.web-on', builtTab().pane); c2.checked = false; c2.dispatchEvent(new Event('change'))")
    check("turning Web view off leaves the emulator alone (it steps aside only while the note shows)",
          wait(lambda: pane().get("visible"), 8), pane())
    js("addTab('notepad', { title: 'Other' })")
    check("another app tab: the view hides", wait(lambda: not pane().get("visible"), 3))
    js("closeTab(builtTab().id)")
    check("closing the tab closes the view", wait(lambda: key not in api.webpane_state(), 3), api.webpane_state())


api = app.Api()
w = webview.create_window("emulator test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
api._emu.stop()
shutil.rmtree(TOP, ignore_errors=True)
for name, ok, d in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
