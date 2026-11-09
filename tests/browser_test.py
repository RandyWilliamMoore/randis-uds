# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/browser_test.py   (opens a hidden window with throwaway data)
"""Browser buttons (ui/browser.js): Back, Forward, Reload tab, All tabs, zoom, find on page, and the tab right-click items
Reload, Duplicate, Close other tabs, Close tabs to the right, Reopen closed tab, each clicked or keyed as a person would."""
import json, os, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_browser_test_")
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
    key = lambda k, **m: js(f"document.activeElement.dispatchEvent(new KeyboardEvent('keydown', Object.assign({{ key: {json.dumps(k)}, bubbles: true, cancelable: true }}, {json.dumps(m)})))")
    titles = lambda: js("JSON.stringify(state.tabs.map(t => t.title))")
    active = lambda: js("current() && current().title")
    def ctx(title, act):
        js(f"document.querySelector('#tabs .tab[data-tab=\"' + state.tabs.find(t => t.title === {json.dumps(title)}).id + '\"]')"
           ".dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 200, clientY: 40 }))")
        return js(f"(() => {{ const b = document.querySelector('#ctx-menu [data-ctx=\"{act}\"]'); if (!b || b.disabled) return false; b.click(); return true; }})()")

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0 && typeof Browser !== 'undefined'", 25))
    check("Back and Forward sit between the logo and the Menu; All tabs is hidden while every tab fits",
          js("(() => { const r = id => document.getElementById(id).getBoundingClientRect();"
             " return r('app-logo').right <= r('nav-back').left + 1 && r('nav-back').right <= r('nav-forward').left + 1"
             " && r('nav-forward').right <= r('mainmenu').left + 1 && r('alltabs').width === 0; })()"))
    js("while (state.tabs.length > 1) closeTab(state.tabs[1].id);"
       "for (const n of ['A', 'B', 'C']) addTab('notepad', { title: n, text: 'text of ' + n });")
    js("Browser.nav.list = []; Browser.nav.at = -1; for (const n of ['A', 'B', 'C']) selectTab(state.tabs.find(t => t.title === n).id)")
    check("Back is on and Forward is off after moving through tabs", js("!document.getElementById('nav-back').disabled && document.getElementById('nav-forward').disabled"))
    js("document.getElementById('nav-back').click()")
    check("Back goes to the tab you were on before", active() == "B", active())
    js("document.getElementById('nav-back').click()")
    js("document.getElementById('nav-forward').click()")
    check("Forward goes the other way", active() == "B", active())
    key("ArrowLeft", altKey=True)
    check("Alt+Left is Back", active() == "A", active())
    key("ArrowRight", altKey=True)
    check("Alt+Right is Forward", active() == "B", active())
    js("selectTab(state.tabs.find(t => t.title === 'C').id)")
    check("picking a new tab after Back clears Forward", js("document.getElementById('nav-forward').disabled"))

    # reopen closed tab
    n = js("state.tabs.length")
    js("closeTab(state.tabs.find(t => t.title === 'B').id)")
    check("Back skips a closed tab", js("(document.getElementById('nav-back').click(), current().title)") == "A", active())
    key("T", ctrlKey=True, shiftKey=True)
    check("Ctrl+Shift+T reopens the closed tab where it was, with its text, and makes no extra tab",
          json.loads(titles())[-3:] == ["A", "B", "C"] and js("state.tabs.length") == n and active() == "B"
          and js("current().text") == "text of B", titles())

    # duplicate
    ctx_items = ("reload", "duplicate", "close-others", "close-right", "reopen", "popout", "close")
    js(f"document.querySelector('#tabs .tab[data-tab=\"' + state.tabs.find(t => t.title === 'A').id + '\"]').dispatchEvent(new MouseEvent('contextmenu', {{ bubbles: true, clientX: 200, clientY: 40 }}))")
    have = js(f"JSON.stringify({json.dumps(list(ctx_items))}.filter(a => !!document.querySelector('#ctx-menu [data-ctx=\"' + a + '\"]')))")
    check("the tab menu has Reload, Duplicate, Close other tabs, Close tabs to the right, Reopen, and still the app's own items",
          json.loads(have) == list(ctx_items), have)
    js("toggleMenu('#none')")
    check("Duplicate puts a copy right after it, with the same text",
          ctx("A", "duplicate") and json.loads(titles())[-4:] == ["A", "A", "B", "C"] and active() == "A"
          and js("current().text") == "text of A" and js("current() !== state.tabs.find(t => t.title === 'A')"), titles())

    # reload
    js("current().pane.dataset.old = '1'")
    js("document.querySelector('#tabs .tab.active').dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 200, clientY: 40 }))")
    js("document.querySelector('#ctx-menu [data-ctx=\"reload\"]').click()")
    check("Reload (right-click) builds the tab again and keeps what's in it",
          js("!current().pane.dataset.old && !current().pane.hidden && document.body.contains(current().pane)")
          and js("current().pane.querySelector('textarea').value") == "text of A")
    js("current().pane.dataset.old = '1'")
    key("r", ctrlKey=True)
    check("Ctrl+R reloads the tab, not the app", js("!current().pane.dataset.old && typeof Browser !== 'undefined'"))
    js("current().job = 1")
    key("F5")
    check("a busy tab isn't reloaded; it says why", until("document.getElementById('toast').textContent.includes('busy')", 3))
    js("current().job = null")

    # tab keys
    key("1", ctrlKey=True)
    first = js("state.tabs[0].title")
    check("Ctrl+1 goes to the first tab", active() == first, active())
    key("9", ctrlKey=True)
    check("Ctrl+9 goes to the last tab", active() == "C", active())
    key("PageDown", ctrlKey=True)
    check("Ctrl+PageDown wraps to the first tab", active() == first, active())
    key("PageUp", ctrlKey=True)
    check("Ctrl+PageUp goes back", active() == "C", active())

    # close others / to the right, then reopen
    m = js("state.tabs.length")
    check("Close tabs to the right closes only those", ctx("B", "close-right") and json.loads(titles())[-1] == "B" and js("state.tabs.length") == m - 1, titles())
    check("Close other tabs leaves just that one", ctx("B", "close-others") and json.loads(titles()) == ["B"], titles())
    js("document.getElementById('nav-back').focus()")
    key("T", ctrlKey=True, shiftKey=True)
    check("they can be reopened one by one", js("state.tabs.length") == 2, titles())

    # all tabs
    js("for (const n of ['Shopping list', 'Recipe']) addTab('notepad', { title: n })")
    js("for (let i = 0; i < 30; i++) addTab('notepad', { title: 'filler ' + i })")
    check("All tabs shows once there are more tabs than fit", until("document.getElementById('alltabs').getBoundingClientRect().width > 0", 3))
    js("document.getElementById('alltabs').click()")
    check("All tabs lists every open tab", until("!document.getElementById('alltabs-menu').hidden")
          and js("document.querySelectorAll('#alltabs-menu .alltabs-list button').length") == js("state.tabs.length"))
    js("const q = document.querySelector('.alltabs-find'); q.value = 'shop'; q.dispatchEvent(new Event('input'))")
    check("typing narrows it down", js("document.querySelectorAll('#alltabs-menu .alltabs-list button').length") == 1)
    js("document.querySelector('.alltabs-find').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))")
    check("Enter opens the match and closes the list", active() == "Shopping list" and js("document.getElementById('alltabs-menu').hidden"), active())
    js("document.body.focus()")
    key("A", ctrlKey=True, shiftKey=True)
    check("Ctrl+Shift+A opens it too", until("!document.getElementById('alltabs-menu').hidden", 2))
    js("toggleMenu('#none')")

    # zoom
    key("=", ctrlKey=True)
    check("Ctrl+= zooms in and shows the level", js("document.documentElement.style.zoom") in ("1.1", 1.1)
          and js("!document.getElementById('zoom-level').hidden && document.getElementById('zoom-level').textContent.includes('110%')"))
    key("-", ctrlKey=True); key("-", ctrlKey=True)
    check("Ctrl+- zooms out", js("document.getElementById('zoom-level').textContent").endswith("90%"))
    js("document.getElementById('zoom-level').click()")
    check("clicking the level puts it back to 100% and hides it", js("document.documentElement.style.zoom") in ("", None)
          and js("document.getElementById('zoom-level').hidden"))
    key("=", ctrlKey=True); key("0", ctrlKey=True)
    check("Ctrl+0 resets too", js("document.getElementById('zoom-level').hidden"))

    # find
    js("document.body.focus()")
    key("f", ctrlKey=True)
    check("Ctrl+F opens the find bar with the cursor in it", js("!document.getElementById('find-bar').hidden && document.activeElement === document.querySelector('#find-bar input')"))
    js("const f = document.querySelector('#find-bar input'); f.value = 'Support'; f.dispatchEvent(new Event('input'))")
    check("typing finds the words on the page, marks them and says how many", js("CSS.highlights.get('uds-find').size") >= 1
          and js("document.querySelector('#find-bar .muted').textContent").startswith("1 of ")
          and js("[...CSS.highlights.get('uds-find-now')][0].toString()") == "Support", js("document.querySelector('#find-bar .muted').textContent"))
    js("addTab('notepad', { title: 'Support notes' })")
    js("Browser.search()")
    n2 = js("CSS.highlights.get('uds-find').size")
    key("F3")
    check("F3 goes to the next match", js("document.querySelector('#find-bar .muted').textContent") == f"2 of {n2}" and n2 >= 2, n2)
    js("const f = document.querySelector('#find-bar input'); f.value = 'zqxwv not here'; f.dispatchEvent(new Event('input'))")
    check("it says when nothing matches", "Not found" in js("document.querySelector('#find-bar').innerText"))
    js("document.querySelector('#find-bar input').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))")
    check("Esc closes it and clears the marks", js("document.getElementById('find-bar').hidden && CSS.highlights.get('uds-find').size === 0"))

    check("plain Ctrl+T still makes a new tab", (lambda c: (key("t", ctrlKey=True), js("state.tabs.length") == c + 1)[1])(js("state.tabs.length")))


api = app.Api()
w = webview.create_window("browser buttons test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
