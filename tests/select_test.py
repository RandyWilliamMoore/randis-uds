# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/select_test.py   (opens a hidden window with throwaway data; puts your clipboard back after)
"""Highlight, copy and paste (select.js): the bar over highlighted text, Copy / Cut / Paste, the right-click menus,
and a page that refreshes itself (the Bots tab) waiting while text is highlighted."""
import os, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_select_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_BOTS_DIR=os.path.join(TOP, "bots"))

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
    old_clip = api.clipboard_text()
    try:
        api._startup()
        _run(w)
    except Exception as e:
        check("test crashed", False, repr(e)[:300])
    finally:
        if isinstance(old_clip, str):
            api.clipboard_set(old_clip)
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
    until("typeof SelectTools === 'object' && typeof addTab === 'function'", 20)
    bar = "[...document.querySelectorAll('#sel-bar button')].map(b => b.textContent).join(',')"
    menu = "[...document.querySelectorAll('#ctx-menu button')].map(b => b.textContent).join(',')"
    box = "current().pane.querySelector('textarea')"

    # the bar over a highlight in a box
    js("addTab('notepad')")
    until(f"!!{box}", 5)
    js(f"(() => {{ const t = {box}; t.value = 'abc def'; t.focus(); t.setSelectionRange(0, 3);"
       " t.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, button: 0})); })()")
    check("highlighting in a box shows the bar: Cut, Copy, Paste, Select all, Find, Search web, Ask the chat (the notepad has a chat)",
          until("!document.getElementById('sel-bar').hidden", 3) and js(bar) == "Cut,Copy,Paste,Select all,Find,Search web,Ask the chat", js(bar))
    check("the bar sits on screen", js("(() => { const r = document.getElementById('sel-bar').getBoundingClientRect();"
                                       " return r.top >= 0 && r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight; })()"))
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
    check("Esc hides the bar", until("document.getElementById('sel-bar').hidden", 2))

    # Copy, Paste, Cut
    js(f"(() => {{ const t = {box}; t.focus(); t.setSelectionRange(0, 3); SelectTools.copy(t); }})()")
    time.sleep(0.6)
    check("Copy puts the highlighted text on the clipboard", api.clipboard_text() == "abc", api.clipboard_text())
    js(f"(() => {{ const t = {box}; t.focus(); t.setSelectionRange(7, 7); SelectTools.paste(t); }})()")
    check("Paste puts it in the box where the cursor is", until(f"{box}.value === 'abc defabc'", 5), js(f"{box}.value"))
    js(f"(() => {{ const t = {box}; t.focus(); t.setSelectionRange(0, 4); SelectTools.cut(t); }})()")
    check("Cut takes it out of the box", until(f"{box}.value === 'defabc'", 5), js(f"{box}.value"))
    check("and puts it on the clipboard", api.clipboard_text() == "abc ", api.clipboard_text())

    # right-click menus
    js(f"(() => {{ const t = {box}; t.focus(); t.setSelectionRange(0, 3); const r = t.getBoundingClientRect();"
       " t.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: r.left + 20, clientY: r.top + 10})); })()")
    check("right-click in a box: Undo, Redo, Cut, Copy, Paste, Delete, Select all",
          until("!document.getElementById('ctx-menu').hidden", 2) and js(menu) == "Undo,Redo,Cut,Copy,Paste,Delete,Select all", js(menu))
    js("document.body.click()")
    js("document.activeElement.blur()")
    js("(() => { const p = document.createElement('p'); p.id = 'sel-test-p'; p.textContent = 'Some words on the page'; current().pane.append(p);"
       " getSelection().removeAllRanges(); const r = p.getBoundingClientRect();"
       " p.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: r.left + 5, clientY: r.top + 5})); })()")
    check("right-click on the page: Copy this text, Select all, Find on page, Back, Forward, Reload tab",
          until("!document.getElementById('ctx-menu').hidden", 2) and js(menu) == "Copy this text,Select all,Find on page…,Back,Forward,Reload tab", js(menu))
    js("document.body.click()")
    js("(() => { const p = document.getElementById('sel-test-p'), r = new Range(); r.selectNodeContents(p); getSelection().removeAllRanges();"
       " getSelection().addRange(r); const b = p.getBoundingClientRect();"
       " p.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: b.left + 5, clientY: b.top + 5})); })()")
    check("right-click on highlighted text: Copy, Find it, Search the web for it, Select all",
          until("!document.getElementById('ctx-menu').hidden", 2) and js(menu).startswith("Copy,Find \"Some words on the page\" on this page,Search the web for")
          and js(menu).endswith("Select all"), js(menu))
    js("document.body.click(); getSelection().removeAllRanges()")
    js("(() => { const t = document.querySelector('#tabbar .tab'), r = t.getBoundingClientRect();"
       " t.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: r.left + 5, clientY: r.top + 5})); })()")
    check("a tab's right-click is still the tab menu", until("!document.getElementById('ctx-menu').hidden", 2)
          and "Copy this text" not in js(menu) and "Undo" not in js(menu), js(menu))
    js("document.body.click()")

    # a page that refreshes itself waits while text is highlighted (the Bots tab refreshes every 5 s)
    js("openBots()")
    first = "current().pane.querySelector('.bots-intro')"
    until(f"!!{first} && +current().pane.dataset.draws > 0", 8)
    js("document.activeElement && document.activeElement.blur()")
    js(f"(() => {{ const r = new Range(); r.selectNodeContents({first}); getSelection().removeAllRanges(); getSelection().addRange(r); }})()")
    d0 = int(js("current().pane.dataset.draws"))
    time.sleep(9)
    check("the Bots tab doesn't refresh while text in it is highlighted (the highlight stays)",
          int(js("current().pane.dataset.draws")) == d0 and len(js("String(getSelection())")) > 10, js("current().pane.dataset.draws"))
    js("getSelection().removeAllRanges(); SelectTools.hideBar()")
    check("once the highlight is gone it refreshes again", until(f"+current().pane.dataset.draws > {d0}", 10))

api = app.Api()
w = webview.create_window("select test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900, text_select=True)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for name, ok, d in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
