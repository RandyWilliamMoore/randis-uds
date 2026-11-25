# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ok = fail = 0
def check(name, cond):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name, flush=True)
    ok, fail = ok + bool(cond), fail + (not cond)


class FakeTabs:
    def __init__(self, metas): self.metas = metas
    def _meta(self, tab_id):
        if tab_id not in self.metas: raise ValueError("no tab")
        return self.metas[tab_id]

import app
api = app.Api.__new__(app.Api)
api._tabs = lambda: FakeTabs({"plain": {"id": "plain"}, "suite": {"osdesign": True}, "str": {"osdesign": "true"}})

check("plain tab refused", "error" in api.os_call("plain", "status"))
check("osdesign as text refused", "error" in api.os_call("str", "status"))
check("missing tab refused", "error" in api.os_call("gone", "status"))
check("unknown op refused", "error" in api.os_call("suite", "format_c"))
st = api.os_call("suite", "status")
check("status lists exported ISOs", "randis-udos.iso" in st.get("isos", []) and st.get("busy") is False)
check("no job yet", api.os_call("suite", "job").get("none") is True)
for bad in ("../app.py", "..\\..\\x.iso", "nothere.iso", "randis-data.img", ""):
    check(f"boot refuses {bad!r}", "error" in api.os_call("suite", "boot", {"iso": bad}))
for host in ("", "Bad Name", "../x", "a" * 70):
    check(f"build refuses hostname {host!r}", "error" in api.os_call("suite", "build", {"design": {"hostname": host}}))
check("build refuses a non-dict design", "error" in api.os_call("suite", "build", {"design": "x"}))


def wait(limit):
    end = time.time() + limit
    while time.time() < end:
        j = api.os_call("suite", "job")
        if not j.get("running"):
            return j
        time.sleep(1)
    api.os_call("suite", "stop")
    return api.os_call("suite", "job")


if "real" in sys.argv:
    sys.path.insert(0, os.path.join(app.HERE, "..", "os_design_studio"))
    import osbuild
    d = osbuild.default_design()
    d.update({"hostname": "udostest", "users": [{"name": "owner", "admin": True}]})
    r = api.os_call("suite", "build", {"design": d, "passwords": {"root": "rootpw-test", "owner": "userpw-test"}, "boot": True, "seconds": 240})
    check("build + boot started", r.get("started") == "build udostest + boot")
    check("second job refused while one runs", "error" in api.os_call("suite", "boot", {"iso": "randis-udos.iso"}))
    j = wait(300)
    log = j.get("log", "")
    check("build + boot finished with code 0", j.get("rc") == 0)
    check("ISO written", os.path.isfile(os.path.join(api.OS_DIR, "exports", "udostest.iso")))
    check("booted to udostest login", "udostest login:" in log and "reached the login prompt" in log)
    check("boot had no network card", "no network card" in log)
    check("passwords not in the log", "rootpw-test" not in log and "userpw-test" not in log)
    saved = open(os.path.join(api.OS_DIR, "udostest.osdesign.json"), encoding="utf-8").read()
    check("passwords not in the saved design", "rootpw-test" not in saved and "userpw-test" not in saved)
    r = api.os_call("suite", "build", {"design": d, "passwords": {"root": "rootpw-test"}})
    j = wait(120)
    check("build with a missing password fails cleanly", j.get("rc") not in (0, None) and "No password given for: owner" in j.get("log", ""))
    r = api.os_call("suite", "boot", {"iso": "udostest.iso", "seconds": 240})
    check("boot-only started", r.get("started") == "boot udostest.iso")
    j = wait(300)
    check("boot-only reached the login", j.get("rc") == 0 and "udostest login:" in j.get("log", ""))
    r = api.os_call("suite", "boot", {"iso": "udostest.iso", "seconds": 240}); time.sleep(3)
    api.os_call("suite", "stop"); j = wait(30)
    check("stop ends a boot", not j.get("running") and "(stopped)" in j.get("log", ""))
    for f in ("exports/udostest.iso", "udostest.osdesign.json"):
        try: os.remove(os.path.join(api.OS_DIR, f))
        except OSError: pass

print(f"{ok}/{ok + fail} passed")
sys.exit(1 if fail else 0)
