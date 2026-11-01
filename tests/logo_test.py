# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/logo_test.py   (opens a hidden window through the app's real main(), never the user's real data)
"""The logo: the real main() gives the window the chosen version's icon, the tab bar and welcome page show it, the taskbar
identity is the project's own, and a project can pick another version with one word in data/project.json."""
import json, os, shutil, sys, tempfile, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_logo_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"))

import ctypes
import webview
from PIL import Image
import app
import projects

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
VERSIONS = ("base",)
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

# ---- the choice, without a window
root = os.path.join(TOP, "proj")
os.makedirs(os.path.join(root, "data"))
check("no project file: the default version", projects.logo_of(root) == projects.DEFAULT_LOGO)
with open(os.path.join(root, "data", "project.json"), "w", encoding="utf-8") as f:
    json.dump({"name": "X", "logo": "mine"}, f)
check("a project without that logo file gets the default", projects.logo_of(root) == projects.DEFAULT_LOGO)
os.makedirs(os.path.join(root, "ui", "logo"))
open(os.path.join(root, "ui", "logo", "uds-mine.ico"), "wb").close()
check("a project can pick a version it has", projects.logo_of(root) == "mine")
with open(os.path.join(root, "data", "project.json"), "w", encoding="utf-8") as f:
    json.dump({"name": "X", "logo": "../../evil"}, f)
check("an unknown version falls back to the default", projects.logo_of(root) == projects.DEFAULT_LOGO)

for v in VERSIONS:
    p = os.path.join(APP, "ui", "logo", f"uds-{v}.ico")
    ok = os.path.isfile(p) and {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(Image.open(p).info.get("sizes", ()))
    check(f"{v}: .ico has the small and big sizes", ok)
    for f in (f"uds-{v}-mark.png", f"uds-{v}-app-icon.png", f"randis-uds-{v}-logo-on-dark.png"):
        check(f"{v}: {f} is there", os.path.isfile(os.path.join(APP, "ui", "logo", f)))

# the small icons really carry each version's color, not the kit's amber
for v, rgb in (("base", (0xFF, 0xB5, 0x47)),):
    px = Image.open(os.path.join(APP, "ui", "logo", f"uds-{v}-mark.png")).convert("RGB").getpixel((82, 30))
    check(f"{v}: the small icon's + tab is its color", all(abs(px[i] - rgb[i]) < 12 for i in range(3)), px)

# ---- the real main(), hidden
real_create, real_start = webview.create_window, webview.start
windows, start_kw = [], {}
def hidden_create(*a, **k):
    k["hidden"] = True
    w = real_create(*a, **k)
    windows.append(w)
    return w
def run_checks():
    try:
        _checks(windows[0])
    except Exception as e:
        check("test crashed", False, repr(e)[:300])
    finally:
        windows[0].destroy()
def fake_start(func=None, *a, **k):
    start_kw.update(k)
    real_start(lambda: (func(), run_checks()), *a, **k)
webview.create_window, webview.start = hidden_create, fake_start

def _checks(w):
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
    want = projects.logo_of(APP)
    ico = os.path.join(APP, "ui", "logo", f"uds-{want}.ico")
    check("main() hands pywebview the chosen icon", os.path.samefile(start_kw.get("icon", ""), ico), start_kw)

    # what Windows actually shows: the form's own icon against the file, and not python's
    bmp = w.native.Icon.ToBitmap()
    frame = Image.open(ico)
    frame.size = (32, 32)
    frame.load()
    frame = frame.convert("RGBA")
    same = total = 0
    for y in range(0, 32):
        for x in range(0, 32):
            c, e = bmp.GetPixel(x, y), frame.getpixel((x, y))
            total += 1
            same += abs(c.R - e[0]) < 40 and abs(c.G - e[1]) < 40 and abs(c.B - e[2]) < 40
    check("the window's real icon is the logo", same / total > 0.9, f"{same}/{total}")

    buf = ctypes.c_wchar_p()
    ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(buf))
    check("the taskbar identity is this app's own", (buf.value or "").startswith("RandisUDS."), buf.value)

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0"))
    mark = "document.getElementById('app-logo')"
    check("the tab bar shows the logo", until(f"{mark}.complete && {mark}.naturalWidth > 0"))
    check("it's the chosen version", want in js(f"{mark}.src"), js(f"{mark}.src"))
    box = json.loads(js(f"(() => {{ const r = {mark}.getBoundingClientRect(); return JSON.stringify([r.width, r.height, r.left, r.top]); }})()"))
    check("the logo sits on screen at the top left", 20 <= box[0] <= 32 and 20 <= box[1] <= 32 and box[2] < 60 and box[3] < 60, box)
    img = "document.querySelector('.welcome-logo')"
    if js(f"!!{img}"):
        check("the welcome page shows the full logo", until(f"{img}.complete && {img}.naturalWidth > 0"))
        check("the welcome logo is the chosen version", want in js(f"{img}.src"), js(f"{img}.src"))
    else:
        check("the welcome page shows the full logo", False, "no welcome tab open")

    # a project that picks another version sees it in the page too
    os.makedirs(os.path.join(TOP, "other", "data"))
    os.makedirs(os.path.join(TOP, "other", "ui", "logo"))
    open(os.path.join(TOP, "other", "ui", "logo", "uds-mine.ico"), "wb").close()
    with open(os.path.join(TOP, "other", "data", "project.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "Y", "logo": "mine"}, f)
    real_here, app.HERE = app.HERE, os.path.join(TOP, "other")
    js("window.__l = null; applyLogo().then(() => window.__l = document.getElementById('app-logo').src)")
    check("the page follows the project's pick", until("window.__l && window.__l.includes('uds-mine-mark')"), js("window.__l"))
    app.HERE = real_here
    js("applyLogo()")

app.main()
webview.create_window, webview.start = real_create, real_start
shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
