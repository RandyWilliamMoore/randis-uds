# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os, sys, time, shutil
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["TEST_MUTE"] = "1"
import webview
import app

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "_test_data_scroll")
shutil.rmtree(D, ignore_errors=True)
os.makedirs(os.path.join(D, "tabs"))
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
os.environ["UDS_KEYS_DIR"] = os.path.join(D, "keys")
os.environ["UDS_TEST_HIDDEN"] = "1"
os.environ["UDS_BASE"] = os.path.join(D, "no_base")
results = []

def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

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
    def until(expr, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if js(expr):
                return True
            time.sleep(0.2)
        return False
    until("typeof state !== 'undefined' && state.tabs.length > 0", 30)
    js("window.__errs = []; window.addEventListener('error', e => window.__errs.push(String(e.message)));")
    check("followEnd is shared by every page", js("typeof followEnd === 'function'"))
    js("""window.B = Object.assign(document.createElement('div'), { style: 'height:100px;overflow:auto;position:fixed;top:0;left:0;width:200px' });
          document.body.append(B); for (let i = 0; i < 60; i++) B.append(Object.assign(document.createElement('div'), { textContent: 'line ' + i }));
          followEnd(B);""")
    bottom = "B.scrollHeight - B.scrollTop - B.clientHeight < 2"
    check("a new chat starts at the bottom", js(bottom))
    js("B.scrollTop = 200; B.dispatchEvent(new Event('scroll'));")
    time.sleep(0.2)
    js("for (let i = 0; i < 20; i++) B.append(Object.assign(document.createElement('div'), { textContent: 'more ' + i })); followEnd(B);")
    check("scrolled up: new text doesn't pull you down", js("B.scrollTop === 200"), js("B.scrollTop"))
    js("const kids = [...B.children]; B.textContent = ''; kids.forEach(k => B.append(k)); followEnd(B);")
    check("scrolled up: a full redraw keeps your place", js("B.scrollTop === 200"), js("B.scrollTop"))
    js("B.dispatchEvent(new WheelEvent('wheel', { deltaY: -50 })); B.scrollTop = B.scrollHeight; B.dispatchEvent(new Event('scroll'));")
    time.sleep(0.2)
    js("B.append(Object.assign(document.createElement('div'), { textContent: 'next' })); followEnd(B);")
    check("back at the bottom: it follows again", js(bottom))
    js("B.dispatchEvent(new WheelEvent('wheel', { deltaY: -50 })); B.append(Object.assign(document.createElement('div'), { textContent: 'x' })); followEnd(B);")
    check("a wheel turn up stops following at once, even mid-reply", not js(bottom))
    js("followEnd(B, true);")
    check("sending a message jumps to the bottom", js(bottom))

    ok = js("""(() => { const t = state.tabs.find(t => t.chatId && t.pane && t.pane.querySelector('.msgs')); if (!t) return false;
              window.T = t; const c = findChat(t.chatId); c.messages = [];
              for (let i = 0; i < 40; i++) c.messages.push({ role: i % 2 ? 'assistant' : 'user', content: 'message ' + i + ' ' + 'words '.repeat(30) });
              selectTab ? selectTab(t.id) : 0; renderMessages(t); return true; })()""")
    if not ok:
        js("addTab('chat')")
        ok = until("state.tabs.some(t => t.chatId && t.pane && t.pane.querySelector('.msgs'))", 10) and js("""(() => {
              const t = state.tabs.find(t => t.chatId && t.pane && t.pane.querySelector('.msgs')); window.T = t; const c = findChat(t.chatId); c.messages = [];
              for (let i = 0; i < 40; i++) c.messages.push({ role: i % 2 ? 'assistant' : 'user', content: 'message ' + i + ' ' + 'words '.repeat(30) });
              renderMessages(t); return true; })()""")
    check("found a chat tab to test", ok)
    if ok:
        js("window.M = T.pane.querySelector('.msgs'); T.pane.hidden = false; M.style.height = '300px'; M.style.overflow = 'auto';")
        js("renderMessages(T);")
        check("chat opens at the bottom", js("M.scrollHeight - M.scrollTop - M.clientHeight < 2"), js("[M.scrollHeight, M.scrollTop, M.clientHeight]"))
        js("M.dispatchEvent(new WheelEvent('wheel', { deltaY: -100 })); M.scrollTop = 100; M.dispatchEvent(new Event('scroll'));")
        time.sleep(0.2)
        for i in range(5):
            js(f"updateLastBubble(T, {{ role: 'assistant', content: 'reply growing ' + 'more '.repeat({(i + 1) * 60}) }});")
            time.sleep(0.1)
        check("reading up the chat while the reply streams: you stay put", js("M.scrollTop === 100"), js("M.scrollTop"))
        js("renderMessages(T);")
        check("a full chat redraw keeps your place too", js("M.scrollTop === 100"), js("M.scrollTop"))
    check("no page errors", js("window.__errs.length === 0"), js("window.__errs.join(' | ')"))

api = app.Api()
w = webview.create_window("scroll follow test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(D, ignore_errors=True)
fails = [r for r in results if not r[1]]
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
