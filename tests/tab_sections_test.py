# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_tab_sections_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"))

import webview
import app

D = os.path.join(TOP, "data")
os.makedirs(os.path.join(D, "tabs"))
for i, (tid, name, old, icon, sec) in enumerate((
        ("29cf39b827", "Hotdog Tycoon", "hotdog tycoon, you start as …", "tab-hotdog", "Games"),
        ("emojiforge1", "Emoji Forge", None, "tab-emojiforge", "Create"),
        ("d2844775ac", "Dice Master", None, "tab-dice", "Games"),
        ("lifetree01", "Life Tree", None, "tab-lifetree", "Life & Family"))):
    os.makedirs(os.path.join(D, "tabs", tid))
    with open(os.path.join(D, "tabs", tid, "v001.html"), "w", encoding="utf-8") as f:
        f.write(f"<!DOCTYPE html><html><head><title>{name}</title></head><body><h1>{name}</h1></body></html>")
    meta = {"id": tid, "name": name, "created": 1794000000 + i, "origin_chat": None, "icon": icon, "section": sec, "current": 1,
            "versions": [{"n": 1, "file": "v001.html", "note": "test", "time": 1794000000 + i}]}
    if old:
        meta["old_names"] = [old]
    with open(os.path.join(D, "tabs", tid, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
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
    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0", 25))
    check("the built tabs are listed", until("(state.built || []).length === 4", 10), js("JSON.stringify((state.built||[]).map(b => b.name))"))
    check("the tab icons are in the emoji set", js("RandisEmoji.has('tab-hotdog') && RandisEmoji.has('tab-emojiforge') && RandisEmoji.has('tab-chat')"))
    js("localStorage.removeItem('uds.menuOpen'); document.getElementById('newtab').click()")
    check("+ menu opens", until("!document.getElementById('newtab-menu').hidden", 3))
    secs = js("JSON.stringify([...document.querySelectorAll('#newtab-menu .menu-sec > summary')].map(s => s.textContent))")
    check("built tabs sit in labeled sections", json.loads(secs) == ["Games (2)", "Create (1)", "Life & Family (1)"], secs)
    check("Basics label over the built-in pages", js("[...document.querySelectorAll('#newtab-menu > .menu-label')].some(l => l.textContent === 'Basics')"))
    check("sections start folded", js("[...document.querySelectorAll('#newtab-menu .menu-sec')].every(d => !d.open)"))
    js("document.querySelector('#newtab-menu .menu-sec[data-sec=\"Games\"] > summary').click()")
    check("a click opens a section", until("document.querySelector('#newtab-menu .menu-sec[data-sec=\"Games\"]').open", 2))
    check("its tabs are there, sorted, with their icons",
          until("(() => { const b = [...document.querySelectorAll('#newtab-menu .menu-sec[data-sec=\"Games\"] button')]; return b.length === 2 && b[0].textContent.includes('Dice Master') && b[1].textContent.includes('Hotdog Tycoon') && b.every(x => x.querySelector('img.rmo')); })()", 2),
          js("document.querySelector('#newtab-menu .menu-sec[data-sec=\"Games\"]').innerText"))
    check("the open section is remembered", until("JSON.parse(localStorage.getItem('uds.menuOpen') || '{}').Games === true", 2))
    js("document.body.click(); document.getElementById('newtab').click()")
    check("and stays open next time", until("document.querySelector('#newtab-menu .menu-sec[data-sec=\"Games\"]').open && !document.querySelector('#newtab-menu .menu-sec[data-sec=\"Create\"]').open", 3))
    js("document.querySelector('#newtab-menu .menu-sec[data-sec=\"Games\"] button[data-built=\"29cf39b827\"]').click()")
    check("picking one opens it as a tab", until("state.tabs.some(t => t.kind === 'built' && t.builtId === '29cf39b827')", 5))
    check("its tab shows the custom icon and the new name",
          until("(() => { const t = state.tabs.find(t => t.builtId === '29cf39b827'), el = document.querySelector('#tabs [data-tab=\"' + t.id + '\"]'); return el && el.querySelector('.tab-icon img.rmo') && el.querySelector('.title').textContent.startsWith('Hotdog Tycoon'); })()", 5),
          js("document.getElementById('tabs').innerText"))
    js("const t = state.tabs.find(t => t.builtId === '29cf39b827'); t.title = 'hotdog tycoon, you start as …'; renderTabs()")
    check("an old saved title shows the new name", js("[...document.querySelectorAll('#tabs .title')].some(x => x.textContent.startsWith('Hotdog Tycoon'))"))
    check("a built-in tab gets its custom icon too", js("!!document.querySelector('#tabs .tab .tab-icon img.rmo[alt=\":tab-welcome:\"], #tabs .tab .tab-icon img.rmo[alt=\":tab-chat:\"], #tabs .tab .tab-icon img.rmo[alt=\":tab-notepad:\"]')"),
          js("document.getElementById('tabs').innerHTML.slice(0, 400)"))


api = app.Api()
w = webview.create_window("tab sections test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for name, ok, d in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
