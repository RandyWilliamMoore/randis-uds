# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import glob, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

for path in sorted(glob.glob(os.path.join(HERE, "*.py"))):
    text = open(path, encoding="utf-8", errors="replace").read()
    if "webview.create_window" not in text and "webview.start" not in text:
        continue
    covered = re.search(r"^\s*(import (\w+, )*app\b|from app import|import app\b)", text, re.M) or "--mute-audio" in text
    check("muted: " + os.path.basename(path), covered, "opens a window but neither imports app nor sets --mute-audio")

import app, webview
check("app sets --mute-audio for test runs", "--mute-audio" in os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", ""))

def probe(w):
    time.sleep(4)
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe' and ParentProcessId=%d\" | Select -Expand CommandLine" % os.getpid()],
                         capture_output=True, text=True).stdout
    check("real test window's browser runs muted", "--mute-audio" in out, out[:300] or "no browser process found")
    w.destroy()
w = webview.create_window("mute guard test", html="<p>mute guard</p>", x=-3000, y=0, width=300, height=200)
webview.start(probe, w)

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
bad = [r for r in results if not r[1]]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
