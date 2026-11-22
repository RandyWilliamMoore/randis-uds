# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vm

ok = fail = 0
def check(name, cond):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name)
    ok, fail = ok + bool(cond), fail + (not cond)

check("letters map", vm.KEYS["KeyA"] == "a" and vm.KEYS["Enter"] == "ret" and vm.KEYS["F7"] == "f7")
check("unknown key ignored", vm.Machine("templeos").key("NotAKey", True) is False)
for bad in ("../evil", "_isos", "", "A B", "x" * 50, "no-such-machine"):
    try:
        vm.Hub().get(bad); check(f"bad machine id refused: {bad!r}", False)
    except ValueError:
        check(f"bad machine id refused: {bad!r}", True)
try:
    vm.Hub().download("not-in-catalog"); check("unknown download refused", False)
except ValueError:
    check("unknown download refused", True)


class FakeTabs:
    def __init__(self, metas): self.metas = metas
    def _meta(self, tab_id):
        if tab_id not in self.metas: raise ValueError("no tab")
        return self.metas[tab_id]

import app
api = app.Api.__new__(app.Api)
api._vm = vm.Hub()
api._tabs = lambda: FakeTabs({"plain": {"id": "plain"}, "temple": {"vm": "templeos"}, "suite": {"vm": "suite"},
                              "odd": {"vm": "../x"}, "num": {"vm": 5}})
check("plain tab refused", "error" in api.vm_call("plain", "status"))
check("odd machine name refused", "error" in api.vm_call("odd", "status"))
check("non-text vm refused", "error" in api.vm_call("num", "status"))
check("missing tab refused", "error" in api.vm_call("gone", "status"))
check("unknown op refused", "error" in api.vm_call("temple", "format_c"))
check("TempleOS tab can't make machines", "error" in api.vm_call("temple", "create", {"os": "alpine"}))
check("TempleOS tab can't list machines", "error" in api.vm_call("temple", "list"))
check("TempleOS tab can't drive another machine", api.vm_call("temple", "status", {"machine": "other"}).get("id") == "templeos")
s = api.vm_call("temple", "status")
check("TempleOS tab gets status", "running" in s)
check("suite lists machines", "machines" in api.vm_call("suite", "list"))
check("suite sees the catalog", len(api.vm_call("suite", "catalog").get("catalog", [])) == len(vm.CATALOG))
check("suite refuses unknown system", "error" in api.vm_call("suite", "create", {"os": "evil"}))

m = api.vm_call("suite", "create", {"os": "templeos"})
check("suite makes a machine", bool(m.get("id")) and os.path.isdir(os.path.join(vm.VM_DIR, m.get("id", "?"))))
c = api.vm_call("suite", "settings", {"machine": m["id"], "settings": {"ram": 999999, "cpus": -3, "mouse": "laser", "name": "  Test PC  ", "boost": "yes"}})
check("settings kept in range", c.get("ram") == 8192 and c.get("cpus") == 1 and c.get("mouse") == "ps2" and c.get("name") == "Test PC" and c.get("boost") is False)
check("suite removes a machine", api.vm_call("suite", "remove", {"machine": m["id"]}).get("ok") and not os.path.isdir(os.path.join(vm.VM_DIR, m["id"])))


def boots(tab, machine, wait, name):
    args = {"machine": machine} if machine else {}
    check(f"{name} starts", api.vm_call(tab, "start", {**args, "boot": "cd"}).get("ok"))
    time.sleep(wait)
    f = api.vm_call(tab, "frame", args)
    check(f"{name} shows a screen", str(f.get("png", "")).startswith("data:image/png;base64,"))
    check(f"{name} takes a key", api.vm_call(tab, "key", {**args, "code": "KeyN", "down": True}).get("ok"))
    api.vm_call(tab, "key", {**args, "code": "KeyN", "down": False})
    check(f"{name} takes the mouse", api.vm_call(tab, "mouse", {**args, "dx": 10, "dy": 5, "buttons": ["left"]}).get("ok"))
    check(f"{name} takes a pointer spot", api.vm_call(tab, "mouse", {**args, "x": 100, "y": 100, "buttons": []}).get("ok"))
    api.vm_call(tab, "stop", args)
    check(f"{name} stops", not api.vm_call(tab, "status", args).get("running"))
    return f

if s.get("qemu") and s.get("iso_ok") and not s.get("running"):
    boots("temple", None, 20, "TempleOS")
else:
    print("SKIP TempleOS boot (QEMU or its disc isn't here, or it's already running)")

if "download" in sys.argv[1:] and s.get("qemu"):
    m = api.vm_call("suite", "create", {"os": "tinycore"})
    for _ in range(300):
        st = api.vm_call("suite", "status", {"machine": m["id"]})
        d = next(c for c in api.vm_call("suite", "catalog")["catalog"] if c["key"] == "tinycore")
        if st.get("iso_ok") or (d.get("download") or {}).get("error"):
            break
        time.sleep(1)
    check("Tiny Core downloaded", st.get("iso_ok"))
    if st.get("iso_ok"):
        api.vm_call("suite", "settings", {"machine": m["id"], "settings": {"mouse": "tablet"}})
        f = boots("suite", m["id"], 40, "Tiny Core")
        if "png" in f and len(sys.argv) > 2:
            import base64
            open(sys.argv[2], "wb").write(base64.b64decode(f["png"].split(",", 1)[1]))
    api.vm_call("suite", "remove", {"machine": m["id"]})

print(f"{ok}/{ok + fail} passed")
sys.exit(1 if fail else 0)
