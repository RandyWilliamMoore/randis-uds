# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/tab_icons_test.py   (opens a hidden window with throwaway data)
"""Icons only when narrow: with many tabs open, tabs show just their icon and the active one its name.
With few tabs open, names come back. Unsaved and running tabs still say so with a dot on the icon."""
import json, os, shutil, sys, tempfile, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_tab_icons_test_")
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

READ = """JSON.stringify([...document.querySelectorAll('#tabs .tab')].map(t => {
  const r = t.getBoundingClientRect(), i = t.querySelector('.tab-icon').getBoundingClientRect(), n = t.querySelector('.title');
  return { active: t.classList.contains('active'), w: r.width, left: i.left - r.left, right: r.right - i.right, icon: i.width,
           name: getComputedStyle(n).display !== 'none' ? n.clientWidth : 0,
           close: getComputedStyle(t.querySelector('.close')).display !== 'none',
           dot: getComputedStyle(t.querySelector('.tab-icon'), '::after').display !== 'none'
                && getComputedStyle(t.querySelector('.tab-icon'), '::after').content !== 'none',
           tip: t.title };
}))"""


def run(w):
    try:
        api._startup()
        _run(w)
    except Exception as e:
        check("test crashed", False, repr(e)[:300])
    finally:
        w.destroy()


def _run(w):
    def js(s):
        return w.evaluate_js(s)
    def until(cond, secs=25):
        end = time.time() + secs
        while time.time() < end:
            try:
                if js(cond):
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False
    def tabs_to(n):
        js(f"while (state.tabs.length < {n}) addTab('notepad', {{ title: 'Long enough tab name ' + state.tabs.length }});"
           f"while (state.tabs.length > {n}) closeTab(state.tabs[state.tabs.length - 1].id);")
        until(f"document.querySelectorAll('#tabs .tab').length === {n}", 5)
        time.sleep(0.3)
    read = lambda: json.loads(js(READ))

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0"))
    tabs_to(16)
    tabs = read()
    others = [t for t in tabs if not t["active"]]
    active = [t for t in tabs if t["active"]]
    print("INFO 16 tabs at 1100 wide: inactive tabs", round(min(t["w"] for t in others)), "-", round(max(t["w"] for t in others)), "px")
    check("16 tabs: one is active", len(active) == 1)
    check("16 tabs: inactive tabs show no stray letters", all(t["name"] == 0 for t in others), others[0])
    check("16 tabs: every tab shows its icon", all(t["icon"] > 8 for t in tabs), others[0])
    check("16 tabs: the icon sits in the middle of the tab", all(abs(t["left"] - t["right"]) <= 6 for t in others), others[0])
    check("16 tabs: the active tab shows its name", active[0]["name"] >= 28, active[0])
    check("16 tabs: the active tab keeps its close button", active[0]["close"], active[0])
    check("16 tabs: inactive tabs have no close button to crowd the icon", not any(t["close"] for t in others), others[0])
    check("16 tabs: hovering gives the full name", all(t["tip"].startswith("Long enough tab name") or t["tip"] for t in tabs))

    # picking a tab moves the name to it
    js("selectTab(state.tabs[5].id)")
    time.sleep(0.3)
    tabs = read()
    check("16 tabs: the tab you pick gets its name", tabs[5]["active"] and tabs[5]["name"] >= 28, tabs[5])

    # the unsaved and running marks live in the title, so an icon-only tab needs its own
    check("16 tabs: a saved tab has no dot", not tabs[3]["dot"], tabs[3])
    js("state.tabs[3].dirty = true; renderTabs()")
    time.sleep(0.2)
    check("16 tabs: an unsaved icon-only tab shows a dot", read()[3]["dot"], read()[3])
    js("state.tabs[3].dirty = false; state.tabs[4].job = true; renderTabs()")
    time.sleep(0.2)
    now = read()
    check("16 tabs: a running icon-only tab shows a dot", now[4]["dot"] and not now[3]["dot"], now[4])
    js("state.tabs[4].job = null; renderTabs()")

    # the active tab shows its full name, whichever tab it is
    SHOW = """JSON.stringify((() => { const t = document.querySelector('#tabs .tab.active'), n = t.querySelector('.title'), r = t.getBoundingClientRect(),
      c = t.querySelector('.close').getBoundingClientRect(), s = document.getElementById('tabs');
      return { text: n.textContent, full: n.scrollWidth <= n.clientWidth, faded: getComputedStyle(n).webkitMaskImage !== 'none', w: r.width,
               inRow: r.left >= s.getBoundingClientRect().left - 1 && r.right <= s.getBoundingClientRect().right + 1,
               close: c.width >= 16 && c.right <= r.right + 1, scrolls: s.scrollWidth > s.clientWidth + 1,
               tops: new Set([...s.querySelectorAll('.tab')].map(e => Math.round(e.getBoundingClientRect().top))).size }; })())"""
    names = ["Monitor", "Battery", "Bot chat", "Group chat", "Status", "My to-do", "Team to-do", "Docs",
             "Task lists", "Self-map", "Claude Code", "Code", "Session tools", "Checkers game", "Rubber duck", "Untitled"]
    js(f"state.tabs.forEach((t, i) => t.title = {json.dumps(names)}[i]); renderTabs()")
    seen = []
    for i in range(16):
        js(f"selectTab(state.tabs[{i}].id)")
        time.sleep(0.15)
        seen.append(json.loads(js(SHOW)))
    print("INFO active tab widths", [round(s["w"]) for s in seen])
    check("16 real names: each tab shows its whole name when picked", all(s["full"] for s in seen), [s for s in seen if not s["full"]])
    check("16 real names: the end of the name isn't faded out", not any(s["faded"] for s in seen), seen[0])
    check("16 real names: the close button stays on the tab", all(s["close"] for s in seen), seen[0])
    check("16 real names: all fit without scrolling, whichever is picked", not any(s["scrolls"] for s in seen), [s for s in seen if s["scrolls"]])
    check("16 real names: still one row", all(s["tops"] == 1 for s in seen), seen[0])
    # a name too long for the row is cut with dots, and the tab stays usable
    js("current().title = 'A very long document name ' + 'that goes on and on '.repeat(12); renderTabs()")
    time.sleep(0.2)
    s = json.loads(js(SHOW))
    check("a name too long for the row: the tab stays inside the row, close button included", s["inRow"] and s["close"], s)
    check("a name too long for the row: still one row", s["tops"] == 1, s)
    js("current().title = 'Untitled'; renderTabs()")

    # few tabs: names and close buttons come back
    tabs_to(3)
    tabs = read()
    check("3 tabs: every tab shows its name", all(t["name"] >= 60 for t in tabs), tabs)
    check("3 tabs: every tab has a close button", all(t["close"] for t in tabs), tabs)
    js("current().title = 'Docs'; renderTabs()")
    time.sleep(0.2)
    tabs = read()
    check("3 tabs: a short name doesn't shrink the active tab", abs(max(t["w"] for t in tabs) - min(t["w"] for t in tabs)) <= 2, [t["w"] for t in tabs])


api = app.Api()
w = webview.create_window("tab icons test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1100, height=720)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
