# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run with the installed copy's own Python, and PATH cut to Windows' folders: <install>\python\python.exe packaging/smoke_installed.py <install>
"""Runs inside the INSTALLED copy, with its private Python and no git, claude or other Python on PATH. A real window (moved off screen), so
real frames draw. Checks what a stranger gets: first screen, PDF tab, Randis Paint, and sensible words when Git is missing."""
import json, os, sys, time
INST = sys.argv[1]
APPDIR = os.path.join(INST, "app")
sys.path.insert(0, APPDIR)
os.environ["UDS_BASE"] = APPDIR
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))
check("runs on the installed Python", os.path.normcase(sys.executable).startswith(os.path.normcase(INST)), sys.executable)
import webview, app, shutil
check("uses the installed pywebview", os.path.normcase(webview.__file__).startswith(os.path.normcase(INST)), webview.__file__)
check("this PC's git is hidden", shutil.which("git") is None, shutil.which("git"))
check("no other Python's packages leak in", not any("Python314\\Lib\\site-packages" in p and not p.lower().startswith(INST.lower()) for p in sys.path), sys.path)


def run(w):
    try:
        api._startup()
        def js(s):
            return w.evaluate_js(s)
        def until(cond, secs=30):
            end = time.time() + secs
            while time.time() < end:
                try:
                    if js(cond):
                        return True
                except Exception:
                    pass
                time.sleep(0.2)
            return False
        check("the app starts", until("typeof state !== 'undefined' && state.tabs.length > 0"))
        js("window.__errs = []; window.addEventListener('error', e => window.__errs.push(e.message)); window.addEventListener('unhandledrejection', e => window.__errs.push(String(e.reason)));")
        check("the neutral logo shows", until("document.getElementById('app-logo').src.includes('uds-base-mark')"), js("document.getElementById('app-logo').src"))
        check("the first tab is the welcome page", js("current().kind") == "welcome", js("current().kind"))
        check("Randis Paint is offered", until("(document.getElementById('newtab').click(), document.getElementById('built-menu').textContent.includes('Randis Paint'))", 8), js("JSON.stringify(state.built)"))
        js("(() => { const m = document.querySelector('#built-menu [data-built]'); if (document.getElementById('newtab-menu').hidden) document.getElementById('newtab').click(); m.click(); })()")
        check("Randis Paint opens", until("current().kind === 'built' && current().title === 'Randis Paint'", 10), js("current().title"))
        check("the old paint name is gone", "paint clone" not in js("document.documentElement.innerHTML").lower())
        js("document.querySelector('#newtab-menu [data-kind=pdf]').click()")
        check("the PDF tab opens", until("current().kind === 'pdf' && !!current().pdf"))
        js("""(async () => { window.__made = false; const { bytes } = await pdfBytesFromText('Hello from the installed app'); await current().pdf.load(bytes, { dirty: true });
              await current().pdf.draw(0); window.__made = true; })().catch(e => { window.__made = String(e); })""")
        check("makes and draws a PDF, with real frames", until("window.__made === true", 40) and until("!!current().pdf.state.pages[0].box.querySelector('canvas')", 5), js("window.__made"))
        ink = js("""(() => { const c = current().pdf.state.pages[0].box.querySelector('canvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
                    for (let j = 0; j < d.length; j += 4) if (d[j] < 128) n++; return n; })()""")
        check("the page has ink on it", (ink or 0) > 50, ink)
        js("window.__p = null; api().project_create('Try').then(r => { window.__p = JSON.stringify(r); })")
        until("window.__p !== null", 15)
        check("making a Project without Git says so", "git-scm.com" in (js("window.__p") or ""), js("window.__p"))
        check("no script errors", js("window.__errs.length === 0"), js("JSON.stringify(window.__errs)"))
    except Exception as e:
        check("test crashed", False, repr(e)[:400])
    finally:
        w.destroy()


api = app.Api()
w = webview.create_window("smoke", url=os.path.join(APPDIR, "ui", "index.html"), js_api=api, width=1100, height=720, x=-3000, y=0)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
