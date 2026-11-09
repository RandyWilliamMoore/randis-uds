# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/os_switch_test.py   (opens a hidden window with throwaway data)
"""The top bar's Windows/Linux switch: on screen, Windows by default, a click changes it, it's kept across a reload,
every chat is told the system, and the help text follows it."""
import json, os, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_os_switch_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"))

import webview
import app

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


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
    picked = lambda: js("[...document.querySelectorAll('#os-switch button')].filter(b => b.getAttribute('aria-checked') === 'true').map(b => b.dataset.os).join()")
    saved = lambda: (json.load(open(app.SESSION_FILE, encoding="utf-8")) if os.path.isfile(app.SESSION_FILE) else {}).get("system")

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0", 25))
    check("the switch is in the top bar, on screen, with both choices",
          js("(() => { const s = document.getElementById('os-switch'), r = s.getBoundingClientRect(), bar = document.getElementById('tabbar').getBoundingClientRect();"
             " return s.offsetParent !== null && r.width > 60 && r.top >= bar.top && r.bottom <= bar.bottom + 1 && r.right <= innerWidth"
             " && s.innerText.includes('Windows') && s.innerText.includes('Linux'); })()"))
    check("Windows is picked by default", until("document.querySelector('#os-switch [data-os=windows]').getAttribute('aria-checked') === 'true'", 5), picked())
    check("chats are told Windows", "Windows" in api._hub.note, api._hub.note)

    js("document.querySelector('#os-switch [data-os=linux]').click()")
    check("clicking Linux picks it", until("document.querySelector('#os-switch [data-os=linux]').getAttribute('aria-checked') === 'true'", 3), picked())
    check("only one is picked", picked() == "linux", picked())
    check("it says so", "Linux" in (js("document.getElementById('toast').textContent") or ""))
    end = time.time() + 5
    while saved() != "linux" and time.time() < end:
        time.sleep(0.2)
    check("it's kept with the session", saved() == "linux", saved())
    import ccode
    check("Claude Code chats get it in their standing instructions, not their prompt", "Linux" in ccode.USER_NOTE[0], ccode.USER_NOTE)
    check("chats are told Linux", "Linux" in api._hub.note and "Windows" not in api._hub.note, api._hub.note)
    msgs = {}
    class Spy:
        def stream(self, messages, job, max_tokens):
            msgs["m"] = messages; job.done = True
    api._hub.backends["spy"] = Spy()
    try:
        api._hub.start({"id": "spy", "kind": "local"}, [{"role": "user", "content": "how do I open a terminal?"}], system="Be brief.")
        time.sleep(0.5)
    except Exception as e:
        msgs["err"] = repr(e)
    check("a chat's instructions carry the system", "Linux" in str(msgs.get("m", [{}])[0].get("content", "")), msgs)

    js("location.reload()")
    time.sleep(1.5)
    check("after a reload it's still Linux", until("typeof state !== 'undefined' && state.system === 'linux' && "
                                                     "document.querySelector('#os-switch [data-os=linux]').getAttribute('aria-checked') === 'true'", 20), picked())
    js("document.getElementById('mainmenu').click()")
    check("the Menu has it too, showing Linux", until("[...document.querySelectorAll('#main-menu .os-switch button')].map(b => b.dataset.os + ':' + b.getAttribute('aria-checked')).join() === 'windows:false,linux:true'", 3))
    js("document.querySelector('#main-menu .os-switch [data-os=windows]').click()")
    check("picking Windows in the Menu works and the bar follows", until("state.system === 'windows' && document.querySelector('#os-switch [data-os=windows]').getAttribute('aria-checked') === 'true'", 3))
    js("document.body.click()")
    w.resize(480, 600); time.sleep(1)
    check("in the smallest window the bar has no room, so it's only in the Menu",
          until("getComputedStyle(document.getElementById('os-switch')).display === 'none'", 3))
    js("document.getElementById('mainmenu').click()")
    check("and the Menu still has it", until("document.querySelectorAll('#main-menu .os-switch button').length === 2", 3))
    js("document.querySelector('#main-menu .os-switch [data-os=linux]').click()")
    check("picking in the Menu works there", until("state.system === 'linux'", 3))
    js("document.body.click()")
    w.resize(1375, 900); time.sleep(1)
    js("document.querySelector('#os-switch [data-os=windows]').click()")
    check("clicking Windows puts it back", until("document.querySelector('#os-switch [data-os=windows]').getAttribute('aria-checked') === 'true'", 3)
          and "Windows" in api._hub.note, api._hub.note)


api = app.Api()
w = webview.create_window("os switch test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for name, ok, d in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
