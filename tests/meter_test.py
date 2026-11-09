# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/meter_test.py   (opens a hidden window with throwaway data)
"""The live computer meter on the top bar: real readings, red with the reason when the computer struggles, what each
number means on a click, out of the way in small windows."""
import os, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_meter_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_BOTS_DIR=os.path.join(TOP, "bots"))

import webview
import app
import machine

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


# the readings themselves
s = machine.sample()
check("free and total memory are read", s["free_gb"] and s["total_gb"] and 0 < s["free_gb"] < s["total_gb"], s)
time.sleep(0.5)
s = machine.sample()
check("processor load is read, as a percentage", s["cpu_pct"] is not None and 0 <= s["cpu_pct"] <= 100, s)
check("a temperature is a sane number or left out", s["temp_c"] is None or 5 < s["temp_c"] < 130, s)
real_sample = machine.sample


def run(w):
    try:
        api._startup()
        _run(w)
    except Exception as e:
        check("test crashed", False, repr(e)[:300])
    finally:
        machine.sample = real_sample
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
    M = "document.getElementById('machine-meter')"
    t0 = time.time()
    check("the meter is on the top bar, with free memory and processor load", until(f"!!{M} && !{M}.hidden && {M}.textContent.includes(' GB · ')", 40)
          and "%" in js(f"{M}.textContent"), [round(time.time() - t0, 1), js(f"{M} && {M}.textContent"), js(f"{M}.hidden")])
    check("it sits in the bar, beside the Windows/Linux switch", js(f"(() => {{ const r = {M}.getBoundingClientRect(), b = document.getElementById('tabbar').getBoundingClientRect();"
          " return r.top >= b.top && r.bottom <= b.bottom + 1 && r.right <= innerWidth && " + M + ".nextElementSibling.id === 'os-switch'; })()"))
    check("it isn't red when all is well", not js(f"{M}.classList.contains('hot')") or real_sample()["hot"])
    machine.sample = lambda: {"free_gb": 0.6, "total_gb": 16.0, "cpu_pct": 97.0, "temp_c": 93.0, "hot": True,
                              "why": ["free memory is low (0.6 GB)", "the processor is busy (97%)", "it's running hot (93 °C)"]}
    check("it turns red when the computer struggles, within 5 seconds", until(f"{M}.classList.contains('hot')", 8)
          and js(f"{M}.textContent") == "0.6 GB · 97% · 93°C", js(f"{M}.textContent"))
    check("and says why when you point at it", "free memory is low" in js(f"{M}.title") and "running hot" in js(f"{M}.title"), js(f"{M}.title"))
    js(f"{M}.click()")
    body = js("$('#modal').hidden ? '' : $('#modal .modal-body').textContent") or ""
    check("a click explains each number, the reason first", body.startswith("Why it's red:") and "Free memory: 0.6 GB of 16 GB" in body
          and "Processor load: 97%" in body and "Temperature: 93" in body, body)
    js("closeModal()")
    machine.sample = lambda: {"free_gb": 8.0, "total_gb": 16.0, "cpu_pct": 5.0, "temp_c": None, "hot": False, "why": []}
    check("a temperature the computer doesn't give is left out", until(f"{M}.textContent === '8 GB · 5%'", 8), js(f"{M}.textContent"))
    w.resize(700, 600); time.sleep(1)
    check("small windows keep the bar's room for tabs", until(f"getComputedStyle({M}).display === 'none'", 4),
          [js("innerWidth"), js(f"getComputedStyle({M}).display")])
    w.resize(1375, 900); time.sleep(0.5)


api = app.Api()
w = webview.create_window("meter test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1375, height=900, text_select=True)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
shutil.rmtree(TOP, ignore_errors=True)
for name, ok, d in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
