# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/update_test.py   (a hidden window, a pretend install in a temp folder, and a local server standing in for GitHub)
"""Updates: picking the newest release, the download checks, only an installed copy updating, the automatic check asking first, and
the Menu's Update button and switch, clicked. Installing for real is tested by packaging/installer_test.py, on a real setup.exe."""
import functools, hashlib, http.server, json, os, shutil, stat, sys, tempfile, threading, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_update_")
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"), UDS_TEST_HIDDEN="1")
import webview, app, updater

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

# a pretend install: what setup leaves, with this copy's VERSION set to 0.1.2
INST = os.path.join(TOP, "RandisUDS")
FAKE = os.path.join(INST, "app")
os.makedirs(os.path.join(INST, "python"))
os.makedirs(os.path.join(FAKE, "data"))
for p in (os.path.join(INST, "Uninstall.exe"), os.path.join(INST, "python", "pythonw.exe"), os.path.join(FAKE, "shipped_files.json")):
    open(p, "w").write("{}")
open(os.path.join(FAKE, "VERSION"), "w").write("0.1.2\n")

SETUP = os.urandom(200_000)
served = {"setup": SETUP, "hits": 0, "ranges": []}


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        served["hits"] += 1
        if self.path == "/releases":
            body = json.dumps(served["releases"]).encode()
        elif self.path.startswith("/dl/"):
            body = served["setup"]
            rng = self.headers.get("Range")
            if rng:
                start = int(rng.split("=")[1].split("-")[0])
                served["ranges"].append(start)
                part = body[start:]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
                self.send_header("Content-Length", str(len(part)))
                self.end_headers()
                self.wfile.write(part)
                return
            if served.get("cut"):
                served["cut"] -= 1
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[:len(body) // 2])
                self.wfile.flush()
                self.connection.shutdown(2)
                return
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{srv.server_port}"
os.environ["UDS_UPDATE_API"] = U + "/releases"


def release(v, draft=False, name=None, url=None, digest=True, size=None):
    return {"tag_name": "v" + v, "draft": draft, "prerelease": True, "html_url": f"https://example/{v}", "body": f"What's new in {v}",
            "assets": [{"name": name or f"RandisUDS-Setup-{v}.exe", "browser_download_url": url or f"{U}/dl/{v}", "size": size or len(SETUP),
                        "digest": ("sha256:" + hashlib.sha256(SETUP).hexdigest()) if digest else None}]}


# ---------- the module ----------
served["releases"] = [release("0.1.2"), release("0.1.3"), release("0.2.0", draft=True), release("0.1.10", name="Other.exe"),
                      release("0.1.9", url="https://elsewhere.example/x.exe")]
best = updater.newest(served["releases"])
check("the newest release with its own setup.exe is picked; drafts, other files and other hosts are skipped", best and best["version"] == "0.1.3", best)
check("versions compare as numbers, not text", updater.version_tuple("v0.1.10") > updater.version_tuple("0.1.9"))
check("a copy run from its folder isn't an install", updater.install_folder(APP) is None)
check("the pretend install is one", updater.install_folder(FAKE) == INST)
r = updater.check(FAKE)
check("check sees 0.1.3 is newer than 0.1.2", r.get("newer") and r.get("latest") == "0.1.3" and r.get("current") == "0.1.2", r)
check("automatic checks are on by default", updater.auto_on(FAKE))
check("a check was just made, so another isn't due", not updater.due(FAKE))
updater.save_settings(FAKE, last_check=time.time() - updater.CHECK_EVERY - 1)
check("after the wait one is due", updater.due(FAKE))
updater.save_settings(FAKE, auto=False)
check("with the switch off none is due", not updater.due(FAKE))
updater.save_settings(FAKE, auto=True)
check("a copy run from its folder never checks by itself", not updater.due(APP))
got = updater.download(FAKE)
check("the download lands in data/updates and matches", os.path.isfile(got["path"]) and open(got["path"], "rb").read() == SETUP
      and os.path.dirname(got["path"]) == os.path.join(FAKE, "data", "updates"), got)
served["cut"] = 1
got = updater.download(FAKE)
check("a download cut partway carries on from where it stopped, and matches", served["ranges"] == [len(SETUP) // 2]
      and open(got["path"], "rb").read() == SETUP, served["ranges"])
served["setup"] = SETUP[:-1] + b"x"
try:
    updater.download(FAKE); bad = None
except ValueError as e:
    bad = str(e)
check("a download that doesn't match GitHub's SHA-256 is thrown away", bad and "didn't match" in bad
      and not [n for n in os.listdir(os.path.join(FAKE, "data", "updates")) if n.endswith((".exe", ".part"))], bad)
served["setup"] = SETUP
served["releases"] = [release("0.1.3", url="https://elsewhere.example/x.exe")]
try:
    updater.download(FAKE); bad = None
except ValueError as e:
    bad = str(e)
check("a file from anywhere but GitHub's own addresses isn't downloaded", bad is not None, bad)
served["releases"] = [release("0.1.3")]
try:
    updater.download(APP); bad = None
except ValueError as e:
    bad = str(e)
check("a copy run from its folder refuses to download an update", bad and "installed" in bad, bad)
outside = os.path.join(TOP, "RandisUDS-Setup-0.1.3.exe")
open(outside, "wb").write(SETUP)
started = []
real_popen = updater.subprocess.Popen
updater.subprocess.Popen = lambda *a, **k: started.append((a, k))
try:
    try:
        updater.start_install(FAKE, outside); bad = None
    except ValueError as e:
        bad = str(e)
    check("only a file in data/updates is ever installed", bad and not started, bad)
    got = updater.download(FAKE)
    updater.start_install(FAKE, got["path"])
    script = open(os.path.join(FAKE, "data", "updates", "install_update.ps1"), encoding="utf-8-sig").read()
    check("the helper waits for this copy's Python to close, installs silently into this install, then opens the app",
          started and "-File" in started[0][0][0] and INST in script and "'/S'" in script and "('/D=' + $inst)" in script
          and "launch.py" in script and "python\\'" in script, script[:400])
    flags = started[0][1].get("creationflags", 0) if started else 0
    check("the helper gets a hidden console, never DETACHED_PROCESS (PowerShell quits at once without one)", flags & 0x08000000 and not flags & 0x8, flags)
finally:
    updater.subprocess.Popen = real_popen

# ---------- the page ----------
app.DATA_DIR = TOP
app.SESSION_FILE = os.path.join(TOP, "session.json")
app.UPDATE_APP = FAKE
installs, closes = [], []
app.updater.start_install = lambda a, setup: installs.append(setup) or True


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
    def until_py(cond, secs):
        end = time.time() + secs
        while time.time() < end and not cond():
            time.sleep(0.1)
        return bool(cond())
    real_destroy = w.destroy
    try:
        api._startup()
        check("the app starts", until("typeof state !== 'undefined' && state.tabs.length > 0"))
        served["releases"] = [release("0.1.2"), release("0.1.3")]
        shutil.rmtree(os.path.join(FAKE, "data", "updates"))
        updater.save_settings(FAKE, last_check=0)
        check("an automatic check asks, by itself, when a newer version is out",
              until("!document.getElementById('modal').hidden && document.querySelector('#modal .modal-title').textContent === 'An update is ready'", 40),
              js("document.querySelector('#modal .modal-title').textContent"))
        check("it says which version and shows what's new", "0.1.3 is out. You have 0.1.2" in js("document.querySelector('#modal .modal-body').textContent")
              and "What's new in 0.1.3" in js("document.querySelector('#modal .modal-body').textContent"))
        check("nothing was downloaded just by asking", not os.path.exists(os.path.join(FAKE, "data", "updates")))
        js("document.querySelector('[data-act=update-later]').click()")
        check("Not now closes it", until("document.getElementById('modal').hidden", 5))
        js("document.getElementById('mainmenu').click()")
        check("the Menu has Update Randis UDS and the switch",
              until("!!document.querySelector('#main-menu [data-act=update-check]') && !!document.querySelector('#main-menu [data-update=auto]')", 5))
        check("the switch shows on, and the version", until("document.querySelector('[data-update=auto]').checked && !document.querySelector('[data-update=auto]').disabled"
              " && document.querySelector('.update-version').textContent === 'Version 0.1.2'", 5), js("document.querySelector('.update-version').textContent"))
        js("document.querySelector('[data-update=auto]').click()")
        check("turning it off is saved", until("true") and (time.sleep(1) or updater.load_settings(FAKE).get("auto") is False), updater.load_settings(FAKE))
        check("and the menu stays open to show it", js("!document.getElementById('main-menu').hidden"))
        updater.save_settings(FAKE, last_check=0)
        check("with it off, no automatic check is due", js("1") and api.update_due() is None)
        js("document.querySelector('[data-update=auto]').click()")
        check("turning it back on is saved", until("true") and (time.sleep(1) or updater.load_settings(FAKE).get("auto") is True))
        served["releases"] = [release("0.1.2")]
        js("document.querySelector('[data-act=update-check]').click()")
        check("the button says so when this is the newest", until("document.getElementById('toast').textContent === 'You have the newest version (0.1.2).'", 10),
              js("document.getElementById('toast').textContent"))
        served["releases"] = [release("0.1.2"), release("0.1.3")]
        w.destroy = lambda: closes.append(1)
        js("document.getElementById('mainmenu').click()")
        until("!!document.querySelector('#main-menu [data-act=update-check]')", 5)
        js("document.querySelector('[data-act=update-check]').click()")
        check("the button offers the newer one", until("!document.getElementById('modal').hidden && !!document.querySelector('[data-act=update-go]')", 10))
        js("document.querySelector('[data-act=update-go]').click()")
        check("Update now downloads it, hands it over and closes the app",
              until("document.querySelector('.update-status') && document.querySelector('.update-status').textContent.startsWith('Closing to install 0.1.3')", 15)
              and until_py(lambda: installs and installs[-1].endswith("RandisUDS-Setup-0.1.3.exe") and closes, 15), (installs, closes))
        check("the session was saved before closing", os.path.exists(app.SESSION_FILE))
        w.destroy = real_destroy
        js("closeModal()")
        app.UPDATE_APP = APP
        js("updateNow()")
        check("a copy run from its folder says it doesn't update itself", until("document.querySelector('#modal .modal-body').textContent.includes(\"doesn't update itself\")", 5))
        js("closeModal(); document.getElementById('mainmenu').click()")
        check("and its switch is greyed out", until("document.querySelector('[data-update=auto]') && document.querySelector('[data-update=auto]').disabled", 5))
        check("no script errors", js("(window.__bootProblems || []).length === 0"), js("JSON.stringify(window.__bootProblems)"))
    except Exception as e:
        check("test crashed", False, repr(e)[:400])
    finally:
        real_destroy()


api = app.Api()
w = webview.create_window("update test", url=os.path.join(APP, "ui", "index.html"), js_api=api, width=1100, height=720, hidden=True)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
srv.shutdown()
shutil.rmtree(TOP, onerror=lambda f, q, e: (os.chmod(q, stat.S_IWRITE), f(q)))
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
