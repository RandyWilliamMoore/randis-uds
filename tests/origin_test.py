# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/origin_test.py [picture.png]   (real windows moved off screen, on a throwaway data folder)
"""The line saying where this copy came from: always on screen, on every tab and window size, links to the original repo, and says derivative
in a project. The license terms that require it are checked too."""
import ctypes, json, os, shutil, stat, subprocess, sys, tempfile, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_origin_")
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"))
import webview, app, projects
app.DATA_DIR = TOP
app.SESSION_FILE = os.path.join(TOP, "session.json")
PICTURE = sys.argv[1] if len(sys.argv) > 1 else None
REPO = "https://github.com/RandyWilliamMoore/randis-uds"
SUPPORT = "https://ko-fi.com/moorescombinatoricsmatrix"

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

opened = []
app.webbrowser.open = lambda url: opened.append(url) or True
real_name = projects.name_of(APP)              # this copy's own name, before the test fakes it below
name = {"value": "Base"}
projects.name_of = lambda root: name["value"]

notice = open(os.path.join(APP, "NOTICE.md"), encoding="utf-8").read()
readme = open(os.path.join(APP, "README.md"), encoding="utf-8").read()
check("the license terms name the original repo", REPO in notice)
check("the terms require saying copy, clone or derivative", "copy, clone or derivative" in notice)
check("the terms name the support page", SUPPORT in notice)
check("the README has the support page", SUPPORT in readme)
check("the README has the Discord link", "https://discord.gg/83RmuHcQTR" in readme)
check("the README has both YouTube channels", "https://www.youtube.com/@Randis9000" in readme and "https://www.youtube.com/@MooresCombinatoricsMatrix" in readme)
check("the terms require attribution first and conspicuously", "at the very beginning of the work, blatantly and conspicuously" in notice)
check("the terms cover published content", "discusses it in published content" in notice)
for f in ("app.py", "launch.py", "ui/app.js", "ui/app.css", "ui/index.html"):
    check(f"{f} carries the notice near its top", "GPLv3 with additional terms" in open(os.path.join(APP, f), encoding="utf-8").read()[:600])
check("the README attributes in its first lines", "Randy Moore" in readme[:200] and "ko-fi.com" in readme[:300], readme[:300])
check("the terms cite GPL sections 7(b) and 7(c)", "7(b)" in notice and "7(c)" in notice)
check("the README points to the terms", "NOTICE.md" in readme)
if real_name == "Base":
    check("the README title and first line carry the mark", readme.startswith("# Randis UDS™\n") and "**Randis UDS™ by Randy Moore. This is the original.**" in readme)
else:
    check("a project's README has its own name and says derivative, never the original",
          readme.startswith(f"# {real_name}\n") and f"**{real_name} is a derivative of Randis UDS™ by Randy Moore." in readme and "This is the original" not in readme, readme[:200])
check("the terms keep the marked name and logos out of the GPL", 'The name "Randis UDS™" and the logos in `ui/logo` are not licensed under the GPL' in notice)
check("the GPL text itself is untouched", "GNU GENERAL PUBLIC LICENSE" in open(os.path.join(APP, "LICENSE"), encoding="utf-8").read()[:200])


def my_window():
    """This process's biggest visible window."""
    u = ctypes.windll.user32
    best = [0, 0]
    class R(ctypes.Structure):
        _fields_ = [(n, ctypes.c_long) for n in ("l", "t", "r", "b")]
    def each(h, _):
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        r = R()
        if pid.value == os.getpid() and u.IsWindowVisible(h) and u.GetWindowRect(h, ctypes.byref(r)):
            area = (r.r - r.l) * (r.b - r.t)
            if area > best[1]:
                best[:] = [h, area]
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(each), 0)
    return best[0]


def picture(path):
    ps = f"""Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class W {{ [StructLayout(LayoutKind.Sequential)] public struct R {{ public int L,T,Ri,B; }}
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f); }}
'@
$null = [W]::SetProcessDPIAware(); $h = [IntPtr]{my_window()}; $r = New-Object W+R; $null = [W]::GetWindowRect($h, [ref]$r)
$b = New-Object Drawing.Bitmap ($r.Ri - $r.L), ($r.B - $r.T); $g = [Drawing.Graphics]::FromImage($b); $d = $g.GetHdc()
$null = [W]::PrintWindow($h, $d, 2); $g.ReleaseHdc($d); $g.Dispose(); $b.Save('{path}'); $b.Dispose()"""
    p = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    check("a picture was taken", os.path.exists(path), p.stderr[-400:])


def run(w):
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
            time.sleep(0.1)
        return False
    BOX = "(() => { const o = document.getElementById('origin').getBoundingClientRect(), b = document.getElementById('tabbar').getBoundingClientRect(); return o.height >= 16 && o.top <= 1 && o.left >= 0 && o.right <= innerWidth + 1 && o.bottom <= b.top + 1 && document.getElementById('origin').scrollWidth <= document.getElementById('origin').clientWidth + 1 && document.body.firstElementChild.id === 'origin'; })()"
    try:
        api._startup()
        check("the app starts", until("typeof state !== 'undefined' && state.tabs.length > 0"))
        check("the line says what this is, on the original", until("document.getElementById('origin-what').textContent === 'Randis UDS™ by Randy Moore'"), js("document.getElementById('origin-what').textContent"))
        check("the line shows the original repo", "github.com/RandyWilliamMoore/randis-uds" in js("document.getElementById('origin-link').textContent"))
        check("it's the first thing on screen, at the very top", js(BOX))
        check("it's high contrast, not muted", js("getComputedStyle(document.getElementById('origin')).backgroundColor === getComputedStyle(document.body).color && getComputedStyle(document.getElementById('origin')).color === getComputedStyle(document.body).backgroundColor"))
        js("addTab('notepad', {})")
        check("still on screen on another tab", until(BOX, 5))
        if PICTURE:
            time.sleep(1)
            picture(PICTURE)
        js("document.getElementById('origin-link').click()")
        check("clicking opens the original repo", until("true") and (time.sleep(0.5) or opened == [REPO]), opened)
        check("the line shows the support page", "ko-fi.com/moorescombinatoricsmatrix" in js("document.getElementById('origin-support').textContent"))
        js("document.getElementById('origin-support').click()")
        check("clicking opens the support page", until("true") and (time.sleep(0.5) or opened == [REPO, SUPPORT]), opened)
        os.environ["UDS_TEST_HIDDEN"] = "1"      # the popped-out window stays hidden
        js("addTab('notepad', {}); popOut(current().id)")
        end = time.time() + 20
        while time.time() < end and not api._wins:
            time.sleep(0.1)
        pop = next(iter(api._wins.values()))["window"] if api._wins else None
        seen = ""
        while pop and time.time() < end:
            try:
                seen = pop.evaluate_js("document.getElementById('origin').textContent") or ""
            except Exception:
                seen = ""
            if "ko-fi.com" in seen and "randis-uds" in seen:
                break
            time.sleep(0.2)
        check("a tab popped out to its own window has the line too", "ko-fi.com" in seen and "randis-uds" in seen, seen)
        w.resize(480, 320)
        if PICTURE:
            time.sleep(1)
            picture(PICTURE.replace(".png", "_small.png"))
        check("at the smallest window it's still on screen and whole", until(BOX, 5), js("document.getElementById('origin').scrollWidth + ' ' + document.getElementById('origin').clientWidth"))
        w.resize(1100, 720)
        check("no way to hide it from the app's own feature switches", "origin" not in js("JSON.stringify(state.off)"))
        name["value"] = "My game app"
        js("location.reload()")
        time.sleep(0.5)
        check("in a project it says derivative", until("document.getElementById('origin-what').textContent === 'A derivative of Randis UDS™ by Randy Moore'"), js("document.getElementById('origin-what').textContent"))
        check("a project's line still points to the original", "github.com/RandyWilliamMoore/randis-uds" in js("document.getElementById('origin-link').textContent"))
        check("and to the support page", "ko-fi.com" in js("document.getElementById('origin-support').textContent"))
        check("no script errors", js("(window.__bootProblems || []).length === 0"), js("JSON.stringify(window.__bootProblems)"))
    except Exception as e:
        check("test crashed", False, repr(e)[:400])
    finally:
        w.destroy()


api = app.Api()
w = webview.create_window("origin test", url=os.path.join(APP, "ui", "index.html"), js_api=api, width=1100, height=720, x=-3000, y=0)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, onerror=lambda f, q, e: (os.chmod(q, stat.S_IWRITE), f(q)))
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
