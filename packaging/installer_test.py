# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python packaging/installer_test.py   (after build_installer.py; needs NSIS, Pillow only for the screenshots)
"""Tests the built setup.exe the way a stranger meets it: the WebView2 check both ways, a silent install, the private Python with PATH cut to
Windows' folders, a reinstall over a user's changes, uninstall, and the real wizard clicked through by its own buttons (moved off screen).
It installs into a temp folder, but shortcuts and the Apps-list entry are this user's real ones: same-named shortcuts are saved and put back."""
import ctypes, ctypes.wintypes as wt, glob, os, shutil, subprocess, sys, tempfile, time, winreg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(os.path.dirname(ROOT), "randis_uds_dist")
version = open(os.path.join(ROOT, "VERSION"), encoding="ascii").read().strip()
SETUP = os.path.join(DIST, f"RandisUDS-Setup-{version}.exe")
MAKENSIS = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "NSIS", "makensis.exe")
KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\RandisUDS"
START = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Randis UDS.lnk")
DESK = os.path.join(os.environ["USERPROFILE"], "Desktop", "Randis UDS.lnk")
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="uds_installer_test_")  # NSIS needs backslashes
os.makedirs(OUT, exist_ok=True)
results = []


def check(name, ok, detail=""):
    results.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


def key_value(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def key_exists():
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY).Close()
        return True
    except OSError:
        return False


def shortcut(path):
    ps = f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}'); $s.TargetPath; $s.Arguments; $s.WorkingDirectory"
    return subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split("\n")


def wait_gone(path, secs=120):
    end = time.time() + secs
    while time.time() < end and os.path.exists(path):
        time.sleep(0.25)
    return not os.path.exists(path)


def uninstall(inst):
    subprocess.run([os.path.join(inst, "Uninstall.exe"), "/S"], check=True)  # it hands off to a temp copy and returns at once
    return wait_gone(os.path.join(inst, "Uninstall.exe"))


def test_webview2_check():
    src = os.path.join(OUT, "wv2.nsi")
    for guid, want, label in ((None, "1", "finds the WebView2 this PC has"), ("{00000000-0000-0000-0000-000000000000}", "0", "says so when WebView2 is missing")):
        res = os.path.join(OUT, "wv2_result.txt")
        exe = os.path.join(OUT, f"wv2_{want}.exe")  # a just-run exe can stay locked for a moment, so never rebuild over it
        with open(src, "w", encoding="ascii") as f:
            f.write(f'Unicode true\nRequestExecutionLevel user\nSilentInstall silent\nOutFile "{exe}"\n!include "{HERE}\\webview2_check.nsh"\n'
                    f'Section\n!insertmacro CheckWebView2 $0\nFileOpen $1 "{res}" w\nFileWrite $1 $0\nFileClose $1\nSectionEnd\n')
        cmd = [MAKENSIS, "/V1"] + ([f"/DWV2_GUID={guid}"] if guid else []) + [src]
        subprocess.run(cmd, check=True)
        subprocess.run([exe], check=True)
        check(f"setup's check {label}", open(res).read() == want, open(res).read())


def test_silent():
    inst = os.path.join(OUT, "silent")
    subprocess.run(f'"{SETUP}" /S /D={inst}', check=True)
    data = os.path.join(inst, "app", "data")
    check("silent install: Python and app are in place", all(os.path.exists(os.path.join(inst, p)) for p in (r"python\pythonw.exe", r"app\app.py", r"app\launch.py", r"app\LICENSE", r"app\NOTICE.md", r"app\ui\boot_watch.js", r"app\ui\index.html", "Uninstall.exe")))
    check("silent install: the shipped tabs are in data", os.path.isdir(os.path.join(data, "tabs")) and os.listdir(os.path.join(data, "tabs")))
    check("silent install: tests and packaging stay out", not any(os.path.exists(os.path.join(inst, "app", p)) for p in ("tests", "packaging", "docs")))
    check("silent install: the Start menu shortcut opens the private Python", (s := shortcut(START))[0].strip().lower() == os.path.join(inst, r"python\pythonw.exe").lower() and "launch.py" in s[1] and s[2].strip().lower() == os.path.join(inst, "app").lower(), s)
    check("silent install: the desktop shortcut opens the private Python", os.path.exists(DESK) and shortcut(DESK)[0].strip().lower() == os.path.join(inst, r"python\pythonw.exe").lower())
    check("silent install: listed in Apps, with the version", key_value("DisplayName") == "Randis UDS" and key_value("DisplayVersion") == version, (key_value("DisplayName"), key_value("DisplayVersion")))

    env = {k: v for k, v in os.environ.items() if k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
    sysroot = os.environ["SystemRoot"]
    env["PATH"] = f"{sysroot}\\system32;{sysroot};{sysroot}\\System32\\Wbem"
    r = subprocess.run([os.path.join(inst, "python", "python.exe"), os.path.join(HERE, "smoke_installed.py"), inst], env=env, capture_output=True, text=True, timeout=300)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
    done, _, total = last.partition(" ")[0].partition("/")
    check(f"the installed copy runs, PATH cut: {last}", done and done == total, r.stdout[-1500:] + r.stderr[-500:])

    # the watcher, started as the shortcut starts it: pythonw, PATH cut. Hidden window.
    log = os.path.join(data, "launch.log")
    watcher = subprocess.Popen([os.path.join(inst, "python", "pythonw.exe"), os.path.join(inst, "app", "launch.py")], cwd=os.path.join(inst, "app"),
                               env=dict(env, UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(inst, "app")))
    watcher.wait(timeout=150)
    words = open(log, encoding="utf-8").read() if os.path.exists(log) else ""
    check("the installed watcher starts the app and hears from its page", "ready in" in words, words)      # try 1 normally; a stall just takes another try
    print("installed start:", words.strip(), flush=True)
    lock = os.path.join(data, "app.lock")
    pid = int(open(lock, encoding="ascii").read().strip()) if os.path.exists(lock) else None
    check("the installed app stays open after the watcher is done", pid and str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout, pid)
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        time.sleep(1)

    # a user's work survives a reinstall; the shipped code is put back
    tab = next(f for f in glob.glob(os.path.join(data, "**", "*"), recursive=True) if os.path.isfile(f))
    with open(tab, "ab") as f:
        f.write(b"\nUSER EDIT")
    made = os.path.join(data, "made_by_user.txt")
    extra = os.path.join(inst, "app", "users_own_code.py")
    app_py = os.path.join(inst, "app", "app.py")
    for p in (made, extra):
        open(p, "w").write("mine")
    with open(app_py, "ab") as f:
        f.write(b"\n# changed")
    subprocess.run(f'"{SETUP}" /S /D={inst}', check=True)
    check("reinstall keeps an edited data file", open(tab, "rb").read().endswith(b"USER EDIT"))
    check("reinstall keeps a new data file", os.path.exists(made))
    check("reinstall puts the shipped code back", not open(app_py, "rb").read().endswith(b"# changed"))
    saved_dirs = glob.glob(os.path.join(data, "edited_before_update", "*"))
    saved_files = [os.path.relpath(f, saved_dirs[0]) for f in glob.glob(os.path.join(saved_dirs[0], "**", "*"), recursive=True) if os.path.isfile(f)] if saved_dirs else []
    check("the update saved the edited file first", len(saved_dirs) == 1 and open(os.path.join(saved_dirs[0], "app.py"), "rb").read().endswith(b"# changed"), saved_dirs)
    check("and only that file", saved_files == ["app.py"], saved_files)
    subprocess.run(f'"{SETUP}" /S /D={inst}', check=True)
    check("an update with nothing edited saves nothing", len(glob.glob(os.path.join(data, "edited_before_update", "*"))) == 1)
    manifest = os.path.join(inst, "app", "shipped_files.json")
    keep = open(manifest, "rb").read()
    os.remove(manifest)
    subprocess.run(f'"{SETUP}" /S /D={inst}', check=True)
    newest = max(glob.glob(os.path.join(data, "edited_before_update", "*")))
    check("with no list of what shipped, all the code is saved", os.path.exists(os.path.join(newest, "app.py")) and os.path.exists(os.path.join(newest, "ui", "index.html")) and not os.path.exists(os.path.join(newest, "data")), newest)
    check("setup puts the list back", open(manifest, "rb").read() == keep)
    check("reinstall leaves the user's own code file alone", os.path.exists(extra))

    check("uninstall finishes", uninstall(inst))
    check("uninstall removes Python and shipped code", not os.path.exists(os.path.join(inst, "python")) and not os.path.exists(app_py) and not os.path.exists(os.path.join(inst, "app", "ui")))
    check("uninstall keeps the user's data and own code", os.path.exists(made) and os.path.exists(tab) and os.path.exists(extra))
    check("uninstall removes the shortcut and the Apps entry", not os.path.exists(START) and not key_exists(), (os.path.exists(START), key_exists()))


# ---- the real wizard, driven through its own controls ----
u = ctypes.windll.user32
BM_CLICK, BM_GETCHECK = 0xF5, 0xF0
TV_FIRST = 0x1100
TVM_GETNEXTITEM, TVM_SELECTITEM = TV_FIRST + 10, TV_FIRST + 11
TVM_GETITEMSTATE = TV_FIRST + 39
TVIS_STATEIMAGEMASK = 0xF000
TVGN_ROOT, TVGN_NEXT, TVGN_CARET = 0, 1, 9
WM_CHAR, VK_SPACE = 0x102, 0x20
u.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u.SendMessageW.restype = ctypes.c_ssize_t
PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def text(h):
    b = ctypes.create_unicode_buffer(300)
    u.GetWindowTextW(h, b, 300)
    return b.value


def cls(h):
    b = ctypes.create_unicode_buffer(100)
    u.GetClassNameW(h, b, 100)
    return b.value


def top_window(pid):
    found = []
    def cb(h, _):
        p = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h) and cls(h) == "#32770":
            found.append(h)
        return True
    u.EnumWindows(PROC(cb), 0)
    return found[0] if found else None


def children(h):
    kids = []
    def cb(k, _):
        kids.append(k)
        return True
    u.EnumChildWindows(h, PROC(cb), 0)
    return kids


def visible_named(h, name):
    return next((k for k in children(h) if u.IsWindowVisible(k) and text(k).replace("&", "") == name), None)


def wait_for(fn, secs=120):
    end = time.time() + secs
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.1)
    return None


def picture(h, name):
    try:
        from PIL import Image
    except ImportError:
        return
    r = wt.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    w, ht = r.right - r.left, r.bottom - r.top
    g = ctypes.windll.gdi32
    dc = u.GetWindowDC(h)
    mem = g.CreateCompatibleDC(dc)
    bmp = g.CreateCompatibleBitmap(dc, w, ht)
    g.SelectObject(mem, bmp)
    u.PrintWindow(h, mem, 0)  # 0: the window draws itself now; 2 returned an old frame off screen
    buf = ctypes.create_string_buffer(w * ht * 4)
    head = (ctypes.c_uint32 * 10)(40, w, -ht & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    g.GetDIBits(mem, bmp, 0, ht, buf, head, 0)
    Image.frombuffer("RGBA", (w, ht), buf, "raw", "BGRA", 0, 1).convert("RGB").save(os.path.join(OUT, name))
    g.DeleteObject(bmp); g.DeleteDC(mem); u.ReleaseDC(h, dc)


def find_python(inst):
    ps = "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | ForEach-Object { \"$($_.ProcessId) $($_.ExecutablePath)\" }"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return [int(l.split(" ", 1)[0]) for l in out.splitlines() if inst.lower() in l.lower()]


def test_wizard():
    inst = os.path.join(OUT, "wizard")
    other = b"not this setup's shortcut"
    with open(DESK, "wb") as f:     # a same-named shortcut from another copy of the app
        f.write(other)
    p = subprocess.Popen(f'"{SETUP}" /D={inst}')
    try:
        h = wait_for(lambda: top_window(p.pid), 30)
        check("the wizard opens", h)
        u.SetWindowPos(h, 0, -3000, 0, 0, 0, 0x0001 | 0x0004 | 0x0010)  # off screen, no resize, no focus
        install = wait_for(lambda: visible_named(h, "Install"), 10)
        check("first page offers Install, with no folder or admin question", install, [text(k) for k in children(h)])
        picture(h, "wizard_1_choose.png")
        tree = next((k for k in children(h) if cls(k) == "SysTreeView32" and u.IsWindowVisible(k)), None)
        check("first page lists the desktop shortcut choice", tree)
        first = u.SendMessageW(tree, TVM_GETNEXTITEM, TVGN_ROOT, 0)
        second = u.SendMessageW(tree, TVM_GETNEXTITEM, TVGN_NEXT, first)
        before = u.SendMessageW(tree, TVM_GETITEMSTATE, second, TVIS_STATEIMAGEMASK) if second else None
        check("the desktop shortcut starts ticked", before is not None and before >> 12 == 2, (first, second, before))
        selected = u.SendMessageW(tree, TVM_SELECTITEM, TVGN_CARET, second)
        caret = u.SendMessageW(tree, TVM_GETNEXTITEM, TVGN_CARET, 0)
        u.SendMessageW(tree, WM_CHAR, VK_SPACE, 0)  # the character a real space key makes
        after = u.SendMessageW(tree, TVM_GETITEMSTATE, second, TVIS_STATEIMAGEMASK)
        check("the desktop shortcut can be unticked", after >> 12 == 1, dict(first=first, second=second, selected=selected, caret=caret, after=after))
        u.SendMessageW(tree, WM_CHAR, VK_SPACE, 0)
        check("and ticked again", u.SendMessageW(tree, TVM_GETITEMSTATE, second, TVIS_STATEIMAGEMASK) >> 12 == 2)
        time.sleep(1)  # let it repaint before the picture
        picture(h, "wizard_2_ticked.png")
        u.SendMessageW(install, BM_CLICK, 0, 0)
        # the Finish button's name changes a moment before the page's controls exist, so wait for the page itself
        box = wait_for(lambda: visible_named(h, "Open Randis UDS"), 180)
        finish = visible_named(h, "Finish")
        check("install finishes on the Finish page", box and finish, [text(k) for k in children(h)])
        time.sleep(1)
        picture(h, "wizard_3_finish.png")
        check("Finish page offers Open Randis UDS, ticked", u.SendMessageW(box, BM_GETCHECK, 0, 0) == 1)
        words = " ".join(text(k) for k in children(h) if u.IsWindowVisible(k))
        check("Finish page says it's installed", "Completing Randis UDS Setup" in words and "has been installed" in words, words)
        made = DESK.replace("Randis UDS.lnk", "Randis UDS (installed).lnk")
        check("the ticked desktop shortcut was made, under its own name", os.path.exists(made) and shortcut(made)[0].strip().lower() == os.path.join(inst, r"python\pythonw.exe").lower() and "launch.py" in shortcut(made)[1])
        check("another copy's shortcut with the same name is left alone", open(DESK, "rb").read() == other)
        u.SendMessageW(finish, BM_CLICK, 0, 0)
        check("the wizard closes", wait_for(lambda: p.poll() is not None, 15))
        pids = wait_for(lambda: find_python(inst), 20)
        check("Finish opens the installed app, on the private Python", pids)
        for pid in pids or []:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        wait_for(lambda: not find_python(inst), 15)
        time.sleep(1)
    finally:
        if p.poll() is None:
            p.kill()
    check("uninstall after a wizard install finishes", uninstall(inst))
    check("uninstall removes the shortcut it made", not os.path.exists(DESK.replace("Randis UDS.lnk", "Randis UDS (installed).lnk")))
    check("uninstall leaves another copy's shortcut alone", os.path.exists(DESK) and open(DESK, "rb").read() == other)
    check("uninstall removes the Apps entry", not key_exists())


def main():
    assert os.path.exists(SETUP), SETUP
    if key_exists():
        sys.exit("A Randis UDS install is already listed in Apps on this PC. This test would overwrite that entry; uninstall it first.")
    saved = {}
    for i, path in enumerate((START, DESK)):
        if os.path.exists(path):
            saved[path] = os.path.join(OUT, f"saved_{i}.lnk")
            shutil.move(path, saved[path])
    print("saved shortcuts:", list(saved), flush=True)
    try:
        test_webview2_check()
        test_silent()
        test_wizard()
    except Exception as e:
        check("test crashed", False, repr(e))
    finally:
        for path in (START, DESK, DESK.replace("Randis UDS.lnk", "Randis UDS (installed).lnk")):
            if os.path.exists(path):
                os.remove(path)
        for path, copy in saved.items():
            shutil.move(copy, path)
        print("shortcuts restored:", all(os.path.exists(p) for p in saved), flush=True)
    print(f"{sum(r[0] for r in results)}/{len(results)} passed. Folder: {OUT}")
    sys.exit(0 if all(r[0] for r in results) else 1)


if __name__ == "__main__":
    main()
