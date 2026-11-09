# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/tabbar_test.py   (opens a hidden window with throwaway data)
"""The tab bar works like Chrome's: one row, tabs shrink as more open, and when there are too many the row scrolls and the
active tab stays in view. The buttons at the right never squeeze or wrap."""
import json, os, shutil, subprocess, sys, tempfile, time

SIZES = ((1375, 900), (1100, 720), (800, 600), (480, 320))     # the two window sizes in use, a small one, the app's minimum
if len(sys.argv) < 3:                              # a hidden window won't shrink on resize: one process and window per size
    failed = 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    total = passed = 0
    for width, height in SIZES:
        out = subprocess.run([sys.executable, os.path.abspath(__file__), str(width), str(height)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=env, timeout=240)
        lines = [l for l in out.stdout.splitlines() if l.startswith(("PASS ", "FAIL "))]
        print("\n".join(lines))
        if not lines:
            print("FAIL no results at", width, out.stderr[-400:])
        total += max(len(lines), 1)
        passed += sum(l.startswith("PASS ") for l in lines)
    print(f"{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)
WIDTH, HEIGHT = int(sys.argv[1]), int(sys.argv[2])

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_tabbar_test_")
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

# everything measured in one reading, so the numbers belong together
MEASURE = """JSON.stringify((() => {
  const rect = e => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height }; };
  const tabs = [...document.querySelectorAll('#tabs .tab')];
  const pill = id => { const e = document.getElementById(id), r = rect(e);
    const range = document.createRange(); range.selectNodeContents(e);
    return Object.assign(r, { lines: new Set([...range.getClientRects()].map(x => Math.round(x.top))).size,
                              cut: e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis' }); };
  const active = document.querySelector('#tabs .tab.active');
  const others = tabs.filter(t => t !== active);
  return { inner: innerWidth, bar: rect(document.getElementById('tabbar')), strip: rect(document.getElementById('tabs')),
           plus: rect(document.getElementById('newtab')), logo: rect(document.getElementById('app-logo')),
           menu: rect(document.getElementById('mainmenu')), base: pill('projects'), llm: pill('addllm'),
           tops: [...new Set(tabs.map(t => Math.round(rect(t).t)))], n: tabs.length,
           minW: Math.min(...tabs.map(t => rect(t).w)), maxW: Math.max(...tabs.map(t => rect(t).w)),
           active: rect(active), activeClose: rect(active.querySelector('.close')),
           otherClose: others.length ? rect(others[0].querySelector('.close')).w : 0,
           otherHoverless: others.length ? rect(others[0]).w : 0,
           scrolls: document.getElementById('tabs').scrollWidth > document.getElementById('tabs').clientWidth + 1 };
})())"""


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
    m = lambda: json.loads(js(MEASURE))
    def tabs_to(n):
        js(f"while (state.tabs.length < {n}) addTab('notepad', {{ title: 'Long enough tab name ' + state.tabs.length }});"
           f"while (state.tabs.length > {n}) closeTab(state.tabs[state.tabs.length - 1].id);")
        until(f"document.querySelectorAll('#tabs .tab').length === {n}", 5)
        time.sleep(0.3)
    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0"))

    tabs_to(16)
    a = m()
    label = f"{WIDTH} wide, 16 tabs:"
    check(f"{label} window really is that size", abs(a["inner"] - WIDTH) < 60, a["inner"])
    check(f"{label} one row of tabs", len(a["tops"]) == 1, a["tops"])
    check(f"{label} the bar stays one row tall", a["bar"]["h"] < 60, a["bar"]["h"])
    check(f"{label} tabs stop before the + button", a["strip"]["r"] <= a["plus"]["l"] + 1, a)
    check(f"{label} + stops before the buttons", a["plus"]["r"] <= a["base"]["l"] + 1, a)
    check(f"{label} project button on one line, not cut", a["base"]["lines"] == 1 and not a["base"]["cut"], a["base"])
    check(f"{label} + Add LLM on one line, not cut", a["llm"]["lines"] == 1 and not a["llm"]["cut"], a["llm"])
    check(f"{label} buttons fully on screen", a["llm"]["r"] <= a["inner"] + 1, a["llm"])
    check(f"{label} logo and Menu on the row, left of the tabs",
          a["logo"]["r"] <= a["menu"]["l"] + 1 and a["menu"]["r"] <= a["strip"]["l"] + 1 and a["logo"]["t"] - a["bar"]["t"] < 40, a)
    check(f"{label} the active tab keeps its close button", a["activeClose"]["w"] >= 16 and a["activeClose"]["r"] <= a["active"]["r"] + 1, a["activeClose"])
    if WIDTH >= 1375:     # Back, Forward, Reload and All tabs (browser.js) take ~120px: at 1100, 16 tabs scroll a little, like Chrome
        check(f"{label} all fit without scrolling", not a["scrolls"], a)
    check(f"{label} narrow tabs drop the close button to save room", a["otherHoverless"] >= 90 or a["otherClose"] == 0, a)
    js("selectTab(state.tabs[0].id)")
    until("!!document.querySelector('.pane:not([hidden]) .welcome-logo')", 3)
    check(f"{WIDTH} wide: the welcome logo stays below the tab bar and is on screen",
          until("(() => { const r = document.querySelector('.pane:not([hidden]) .welcome-logo').getBoundingClientRect(); "
                "return r.height > 40 && r.top >= document.getElementById('tabbar').getBoundingClientRect().bottom; })()", 3),
          js("JSON.stringify(document.querySelector('.pane:not([hidden]) .welcome-logo').getBoundingClientRect())"))

    # few tabs: normal width, and the buttons stay at the far right
    tabs_to(2)
    a = m()
    if WIDTH >= 800:      # at the 480 minimum even 2 tabs share the little room left, and that's right
        check(f"{WIDTH} wide, 2 tabs: normal width, not stretched", 120 <= a["maxW"] <= 220, a["maxW"])
    check(f"{WIDTH} wide, 2 tabs: the buttons stay at the right", a["llm"]["r"] >= a["inner"] - 20, a["llm"])

    # too many for the row: it scrolls, and the tab you pick is in view
    tabs_to(40)
    a = m()
    check(f"{WIDTH} wide, 40 tabs: still one row", len(a["tops"]) == 1, a["tops"])
    check(f"{WIDTH} wide, 40 tabs: the row scrolls", a["scrolls"], a)
    check(f"{WIDTH} wide, 40 tabs: + and the buttons stay on screen", a["plus"]["r"] <= a["base"]["l"] + 1 and a["llm"]["r"] <= a["inner"] + 1, a)
    in_view = "(() => { const r = document.querySelector('#tabs .tab.active').getBoundingClientRect(), s = document.getElementById('tabs').getBoundingClientRect(); return r.left >= s.left - 1 && r.right <= s.right + 1; })()"
    js("selectTab(state.tabs[39].id)")
    check("40 tabs: picking the last one brings it into view", until(in_view, 3))
    js("selectTab(state.tabs[0].id)")
    check("40 tabs: picking the first one brings it back", until(in_view, 3))
    js("selectTab(state.tabs[39].id)")
    until(in_view, 3)
    js("selectTab(state.tabs[38].id)")
    until(in_view, 3)
    left = js("document.getElementById('tabs').scrollLeft")
    js("state.tabs[38].dirty = true; renderTabs()")
    check("40 tabs: a redraw doesn't jump the row", abs(js("document.getElementById('tabs').scrollLeft") - left) <= 2 and left > 0, left)
    n = js("state.tabs.length")
    js("document.querySelector('#tabs .tab.active .close').click()")
    check("40 tabs: the close button still closes", until(f"state.tabs.length === {n - 1}", 3))

    # a long project name can't take the room: it's cut with dots
    tabs_to(16)
    js("document.getElementById('projects').textContent = 'A very long project name that goes on and on and on'")
    a = m()
    check("a long project name stays on one line and short", a["base"]["w"] <= 200 and a["base"]["lines"] == 1, a["base"])


api = app.Api()
w = webview.create_window("tab bar test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=WIDTH, height=HEIGHT)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
